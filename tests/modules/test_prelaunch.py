"""Pre-Launch is a permissioned facade, never a second cash source."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from alembic import command
from fastapi.testclient import TestClient
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
    assert (
        finance_client.post(f"{root(project_id)}/{movement_id}/confirm", json={}).status_code == 403
    )

    confirmed = second_finance_client.post(f"{root(project_id)}/{movement_id}/confirm", json={})
    assert confirmed.status_code == 200 and confirmed.json()["counts_as_cash"] is True
    register = finance_client.get(root(project_id)).json()
    assert register["recorded_amount"] == "0.00"
    assert register["confirmed_paid_amount"] == "1250.25"
    assert db.scalar(select(func.count()).select_from(CashflowDevelopmentMovement)) == 1

    reversed_response = second_finance_client.post(
        f"{root(project_id)}/{movement_id}/reverse", json={"reason": "Duplicate invoice"}
    )
    assert reversed_response.status_code == 200
    assert finance_client.get(root(project_id)).json()["confirmed_paid_amount"] == "0.00"
    assert db.scalar(select(func.count()).select_from(CashflowDevelopmentMovement)) == 1
    actions = set(db.scalars(select(AuditEvent.action)).all())
    assert {
        "cashflow.development_movement_recorded",
        "cashflow.development_movement_confirmed",
        "cashflow.development_movement_reversed",
    } <= actions


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
    second_finance_client.post(f"{root(project_id)}/{created.json()['id']}/confirm", json={})
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
    try:
        with pytest.raises(
            SQLAlchemyError, match="cannot downgrade while utilities movements exist"
        ):
            command.downgrade(alembic_config(), "0015_construction_stages")

        with get_engine().connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == ("0016_prelaunch_utilities")
        assert retained_row() == ("utilities", Decimal("1250.25"))
    finally:
        # The refusal is transactional, but restoring head explicitly keeps the
        # test isolated even if a future dialect changes failure semantics.
        command.upgrade(alembic_config(), "head")
