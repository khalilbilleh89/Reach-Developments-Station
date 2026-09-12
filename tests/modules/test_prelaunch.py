"""Pre-Launch is a permissioned facade, never a second cash source."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

import pytest
from alembic import command
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.cashflow.models import CashflowDevelopmentMovement
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access


def root(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/pre-launch/expenses"


def payload(currency_id: str, *, category: str = "utilities") -> dict[str, object]:
    return {
        "category": category,
        "amount": "1250.25",
        "movement_date": date.today().isoformat(),
        "currency_id": currency_id,
        "counterparty_reference": "Water Authority",
        "invoice_reference": "WA-19",
        "evidence_reference": "proof://wa-19",
        "notes": "Utility connection fee",
    }


def manager_member(admin_client: TestClient, project_id: str, manager: User) -> TestClient:
    grant_access(admin_client, project_id, manager)
    return client_for(manager.email)


def editable(row: dict) -> dict:
    return {
        key: row[key]
        for key in (
            "category",
            "amount",
            "movement_date",
            "counterparty_reference",
            "invoice_reference",
            "evidence_reference",
            "notes",
        )
    }


def test_owner_corrects_and_removes_without_confirming_cash(
    admin_client: TestClient,
    second_finance_client: TestClient,
    manager: User,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    client = manager_member(admin_client, project_id, manager)
    original = client.post(
        root(project_id),
        json={
            **payload(currency_id),
            "bank_reference": "keep-bank",
            "value_date": "2026-01-01",
        },
    ).json()
    url = f"{root(project_id)}/{original['id']}"
    assert original["can_edit"] and original["can_remove"]
    corrected = client.patch(
        url,
        json={
            "expected": editable(original),
            "changes": {**editable(original), "amount": "99.99", "notes": "Corrected fee"},
        },
    )
    assert corrected.status_code == 200, corrected.text
    row = corrected.json()
    assert row["amount"] == "99.99" and not row["counts_as_cash"]
    assert row["bank_reference"] == "keep-bank" and row["value_date"] == "2026-01-01"
    assert row["movement_reference"] == original["movement_reference"]
    assert client.get(root(project_id)).json()["recorded_amount"] == "99.99"
    assert (
        second_finance_client.post(
            url + "/confirm", json={"expected": editable(original)}
        ).status_code
        == 409
    )
    # A stale edit AND stale remove must not overwrite/remove the corrected entry.
    assert (
        client.patch(
            url, json={"expected": editable(original), "changes": editable(original)}
        ).status_code
        == 409
    )
    assert (
        client.post(
            url + "/remove", json={"expected": editable(original), "reason": "Duplicate"}
        ).status_code
        == 409
    )
    assert (
        client.post(url + "/remove", json={"expected": editable(row), "reason": "   "}).status_code
        == 422
    )
    removed = client.post(
        url + "/remove", json={"expected": editable(row), "reason": "Duplicate invoice"}
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["removed_without_confirmation"] is True
    assert removed.json()["reversal_reason"] == "Duplicate invoice"
    assert not removed.json()["can_edit"] and not removed.json()["can_remove"]
    assert (
        client.post(
            url + "/remove", json={"expected": editable(row), "reason": "Duplicate"}
        ).status_code
        == 409
    )
    register = client.get(root(project_id)).json()
    assert register["recorded_amount"] == register["confirmed_paid_amount"] == "0.00"
    stored = db.scalars(select(CashflowDevelopmentMovement)).one()
    assert stored.recorded_by_user_id == manager.id and stored.confirmed_at is None
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "cashflow.development_movement_corrected")
    ).one()
    assert event.actor_user_id == manager.id
    assert event.before_data["amount"] == "1250.25"
    assert event.after_data["amount"] == "99.99"
    assert event.before_data["notes"] == "Utility connection fee"
    assert event.after_data["notes"] == "Corrected fee"
    assert event.after_data["invoice_reference"] == "WA-19"


def test_correction_permissions_and_confirmation_race(
    finance_client: TestClient,
    second_finance_client: TestClient,
    executive_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    row = finance_client.post(root(project_id), json=payload(currency_id)).json()
    url = f"{root(project_id)}/{row['id']}"
    body = {"expected": editable(row), "changes": {**editable(row), "amount": "10.00"}}
    for client in (second_finance_client, executive_client, admin_client):
        assert client.patch(url, json=body).status_code == 403
        visible = client.get(root(project_id)).json()["expenses"][0]
        assert not visible["can_edit"] and visible["edit_blocker"]
    for client in (executive_client, admin_client):
        assert (
            client.post(
                url + "/remove", json={"expected": editable(row), "reason": "Duplicate"}
            ).status_code
            == 403
        )
    # Confirmation arriving after the dialog opened wins; Remove cannot become Reverse.
    assert (
        second_finance_client.post(url + "/confirm", json={"expected": editable(row)}).status_code
        == 200
    )
    assert finance_client.patch(url, json=body).status_code == 409
    assert (
        finance_client.post(
            url + "/remove", json={"expected": editable(row), "reason": "Duplicate"}
        ).status_code
        == 409
    )
    assert finance_client.get(root(project_id)).json()["confirmed_paid_amount"] == "1250.25"


def test_correction_validation_and_category_boundary(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    row = finance_client.post(root(project_id), json=payload(currency_id)).json()
    url = f"{root(project_id)}/{row['id']}"
    for changes in (
        {"amount": "0"},
        {"amount": "-1"},
        {"amount": "1.001"},
        {"category": "commissions"},
        {"movement_date": "2999-01-01"},
        {"invoice_reference": "x" * 201},
        {"currency_id": currency_id},
    ):
        response = finance_client.patch(
            url, json={"expected": editable(row), "changes": {**editable(row), **changes}}
        )
        assert response.status_code == 422, response.text
    generic = finance_client.post(
        f"{PROJECTS}/{project_id}/cashflow/development-movements",
        json=payload(currency_id, category="commissions"),
    )
    assert generic.status_code == 201, generic.text
    other = generic.json()
    assert (
        finance_client.patch(
            f"{root(project_id)}/{other['id']}",
            json={"expected": editable(other), "changes": editable(row)},
        ).status_code
        == 422
    )


def test_correction_scope_and_other_finance_removal(
    finance_client: TestClient,
    finance: User,
    second_finance_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
    country_pack_id: str,
    phase_id: str,
) -> None:
    from tests.modules.conftest import project_payload

    row = finance_client.post(
        root(project_id), json={**payload(currency_id), "phase_id": phase_id}
    ).json()
    other_project = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    grant_access(admin_client, other_project, finance)
    body = {"expected": editable(row), "changes": editable(row)}
    assert finance_client.patch(f"{root(other_project)}/{row['id']}", json=body).status_code == 404
    updated = finance_client.patch(f"{root(project_id)}/{row['id']}", json=body)
    assert updated.status_code == 200 and updated.json()["phase_id"] == phase_id
    removed = second_finance_client.post(
        f"{root(project_id)}/{row['id']}/remove",
        json={"expected": editable(row), "reason": "Duplicate"},
    )
    assert removed.status_code == 200 and removed.json()["removed_without_confirmation"]


def test_contextual_setup_does_not_grant_configuration_admin(
    manager_client: TestClient, currency_id: str
) -> None:
    currency = manager_client.post(
        "/api/v1/settings/currencies", json={"code": "USD", "name": "US dollar"}
    )
    pack = manager_client.post(
        "/api/v1/settings/country-packs",
        json={
            "country_code": "US",
            "name": "United States",
            "locale": "en-US",
            "timezone": "America/New_York",
            "default_currency_id": currency_id,
            "area_unit": "sqft",
            "fiscal_year_start_month": 1,
        },
    )
    assert currency.status_code == 403 and pack.status_code == 403


@pytest.mark.parametrize("operation", ["edit", "remove"])
def test_simultaneous_correction_and_confirmation_have_one_consistent_outcome(
    finance_client: TestClient,
    second_finance_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
    operation: str,
) -> None:
    row = finance_client.post(root(project_id), json=payload(currency_id)).json()
    url = f"{root(project_id)}/{row['id']}"
    barrier = Barrier(2)
    db.rollback()

    def correct() -> Response:
        barrier.wait(timeout=10)
        if operation == "remove":
            return finance_client.post(
                url + "/remove", json={"expected": editable(row), "reason": "Duplicate"}
            )
        return finance_client.patch(
            url, json={"expected": editable(row), "changes": {**editable(row), "amount": "10.00"}}
        )

    def confirm() -> Response:
        barrier.wait(timeout=10)
        return second_finance_client.post(url + "/confirm", json={"expected": editable(row)})

    with ThreadPoolExecutor(max_workers=2) as pool:
        correction_future = pool.submit(correct)
        confirmation_future = pool.submit(confirm)
        correction = correction_future.result(timeout=30)
        confirmation = confirmation_future.result(timeout=30)
    register = finance_client.get(root(project_id)).json()
    if operation == "remove":
        assert register["recorded_amount"] == "0.00"
        assert sorted([correction.status_code, confirmation.status_code]) == [200, 409]
        assert register["confirmed_paid_amount"] == (
            "0.00" if correction.status_code == 200 else "1250.25"
        )
    else:
        assert sorted([correction.status_code, confirmation.status_code]) == [200, 409]
        assert register["confirmed_paid_amount"] == (
            "0.00" if correction.status_code == 200 else "1250.25"
        )
        assert register["recorded_amount"] == ("10.00" if correction.status_code == 200 else "0.00")


def test_project_manager_records_the_same_unconfirmed_cashflow_row(
    admin_client: TestClient,
    manager: User,
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    client = manager_member(admin_client, project_id, manager)
    response = client.post(root(project_id), json=payload(currency_id))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "recorded" and body["counts_as_cash"] is False
    assert body["can_confirm"] is False and body["confirmation_blocker"]
    stored = db.scalars(select(CashflowDevelopmentMovement)).one()
    assert str(stored.id) == body["id"] and stored.amount == Decimal("1250.25")
    generic = finance_client.get(f"{PROJECTS}/{project_id}/cashflow/development-movements")
    assert generic.json()[0]["id"] == body["id"]
    register = client.get(root(project_id)).json()
    assert register["recorded_amount"] == "1250.25"
    assert register["confirmed_paid_amount"] == "0.00"


def test_maker_checker_confirmation_and_reversal_count_the_row_once(
    finance_client: TestClient,
    second_finance_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    created = finance_client.post(root(project_id), json=payload(currency_id))
    movement_id = created.json()["id"]
    assert created.json()["can_confirm"] is False
    assert "another authorized" in created.json()["confirmation_blocker"]
    maker_view = finance_client.get(root(project_id)).json()["expenses"][0]
    checker_view = second_finance_client.get(root(project_id)).json()["expenses"][0]
    assert maker_view["can_confirm"] is False
    assert checker_view["can_confirm"] is True and checker_view["confirmation_blocker"] is None
    assert (
        finance_client.post(
            f"{root(project_id)}/{movement_id}/confirm", json={"expected": editable(created.json())}
        ).status_code
        == 403
    )

    confirmed = second_finance_client.post(
        f"{root(project_id)}/{movement_id}/confirm", json={"expected": editable(created.json())}
    )
    assert confirmed.status_code == 200 and confirmed.json()["counts_as_cash"] is True
    assert confirmed.json()["can_confirm"] is False
    # Eligibility is guidance, not a capability token: the previously eligible
    # actor cannot confirm an already confirmed expense again.
    assert (
        second_finance_client.post(
            f"{root(project_id)}/{movement_id}/confirm", json={"expected": editable(created.json())}
        ).status_code
        == 409
    )
    register = finance_client.get(root(project_id)).json()
    assert register["recorded_amount"] == "0.00"
    assert register["confirmed_paid_amount"] == "1250.25"
    assert db.scalar(select(func.count()).select_from(CashflowDevelopmentMovement)) == 1

    reversed_response = second_finance_client.post(
        f"{root(project_id)}/{movement_id}/reverse", json={"reason": "Duplicate invoice"}
    )
    assert reversed_response.status_code == 200
    assert reversed_response.json()["can_confirm"] is False
    assert finance_client.get(root(project_id)).json()["confirmed_paid_amount"] == "0.00"
    assert db.scalar(select(func.count()).select_from(CashflowDevelopmentMovement)) == 1
    actions = set(db.scalars(select(AuditEvent.action)).all())
    assert {
        "cashflow.development_movement_recorded",
        "cashflow.development_movement_confirmed",
        "cashflow.development_movement_reversed",
    } <= actions


def test_read_only_actor_gets_no_confirmation_authority(
    finance_client: TestClient, executive_client: TestClient, project_id: str, currency_id: str
) -> None:
    created = finance_client.post(root(project_id), json=payload(currency_id)).json()
    row = executive_client.get(root(project_id)).json()["expenses"][0]
    assert row["can_confirm"] is False and row["confirmation_blocker"]
    assert "recorded_by_user_id" not in row
    assert (
        executive_client.post(
            f"{root(project_id)}/{created['id']}/confirm", json={"expected": editable(created)}
        ).status_code
        == 403
    )


def test_master_can_self_confirm_and_keeps_other_confirmation_authority(
    db: Session, finance_client: TestClient, project_id: str, currency_id: str
) -> None:
    master = make_user(db, email="ux11-master@example.com", roles=("master_admin",))
    client = client_for(master.email)
    response = client.post(root(project_id), json=payload(currency_id))
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["can_confirm"] is True and row["confirmation_blocker"] is None
    assert client.get(root(project_id)).json()["expenses"][0]["can_confirm"] is True
    confirmed = client.post(
        f"{root(project_id)}/{row['id']}/confirm", json={"expected": editable(row)}
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["counts_as_cash"] is True
    other = finance_client.post(root(project_id), json=payload(currency_id)).json()
    eligible = next(
        x for x in client.get(root(project_id)).json()["expenses"] if x["id"] == other["id"]
    )
    assert eligible["can_confirm"] is True and eligible["confirmation_blocker"] is None
    assert (
        client.post(
            f"{root(project_id)}/{other['id']}/confirm", json={"expected": editable(other)}
        ).status_code
        == 200
    )


def test_prelaunch_never_grants_broader_cash_authority(
    admin_client: TestClient,
    manager: User,
    project_id: str,
    currency_id: str,
) -> None:
    client = manager_member(admin_client, project_id, manager)
    assert client.post(root(project_id), json=payload(currency_id)).status_code == 201
    assert (
        client.post(
            f"{PROJECTS}/{project_id}/cashflow/financing-movements",
            json={
                "movement_type": "debt_drawdown",
                "amount": "1.00",
                "movement_date": date.today().isoformat(),
                "currency_id": currency_id,
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            root(project_id), json=payload(currency_id, category="construction")
        ).status_code
        == 422
    )
    assert (
        client.post(root(project_id), json=payload(currency_id, category="commissions")).status_code
        == 422
    )


def test_prelaunch_lifecycle_is_cross_domain_independent(
    finance_client: TestClient,
    second_finance_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    unrelated = (
        "sale_contracts",
        "payment_plan_versions",
        "collection_receipts",
        "construction_payments",
        "unit_price_versions",
        "unit_economics_unit_costs",
        "unit_status_events",
    )
    before = {table: db.scalar(text(f"SELECT count(*) FROM {table}")) for table in unrelated}
    created = finance_client.post(root(project_id), json=payload(currency_id))
    second_finance_client.post(
        f"{root(project_id)}/{created.json()['id']}/confirm",
        json={"expected": editable(created.json())},
    )
    after = {table: db.scalar(text(f"SELECT count(*) FROM {table}")) for table in unrelated}
    assert after == before


def test_sales_advisor_and_phase_scoped_reader_get_no_prelaunch_details(
    advisor_client: TestClient,
    admin_client: TestClient,
    db: Session,
    phase_id: str,
    project_id: str,
) -> None:
    assert advisor_client.get(root(project_id)).status_code == 403
    scoped_reader = make_user(db, email="scoped.prelaunch@example.com", roles=("finance",))
    grant_access(admin_client, project_id, scoped_reader)
    admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{scoped_reader.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    admin_client.put(f"{PROJECTS}/{project_id}/access/{scoped_reader.id}/phases/{phase_id}")
    assert client_for(scoped_reader.email).get(root(project_id)).status_code == 403


def test_utilities_row_survives_refused_downgrade_to_0015(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    """0016 refuses a lossy downgrade and leaves both data and revision intact."""
    created = finance_client.post(root(project_id), json=payload(currency_id))
    assert created.status_code == 201, created.text
    movement_id = created.json()["id"]

    def retained_row() -> tuple[str, Decimal]:
        with get_engine().connect() as connection:
            row = connection.execute(
                text(
                    "SELECT category, amount FROM cashflow_development_movements "
                    "WHERE id = CAST(:movement_id AS uuid)"
                ),
                {"movement_id": movement_id},
            ).one()
            return row.category, row.amount

    assert retained_row() == ("utilities", Decimal("1250.25"))
    # Release fixture reads before DDL drops 0017's foreign keys to users.
    db.rollback()
    with get_engine().connect() as connection:
        starting_revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    try:
        with pytest.raises(
            SQLAlchemyError, match="cannot downgrade while utilities movements exist"
        ):
            command.downgrade(alembic_config(), "0015_construction_stages")

        with get_engine().connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == starting_revision
            )
        assert retained_row() == ("utilities", Decimal("1250.25"))
    finally:
        # The refusal is transactional, but restoring head explicitly keeps the
        # test isolated even if a future dialect changes failure semantics.
        command.upgrade(alembic_config(), "head")
