from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.db.base import Base
from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.cashflow.models import CashflowDevelopmentMovement
from app.modules.pricing.models import PricingConfiguration, UnitPriceVersion
from app.modules.projects import currency_correction
from app.modules.projects.models import LandParcel, Project
from app.modules.sales.models import Reservation, SaleContract, SaleLegalEvent
from tests.factories import client_for
from tests.modules.conftest import (
    PROJECTS,
    SETTINGS,
    approve_areas,
    grant_access,
    parcel_payload,
    pricing_url,
    released_unit,
    sales_url,
)


def _currency(client: TestClient, code: str) -> str:
    response = client.post(
        f"{SETTINGS}/currencies",
        json={"code": code, "name": f"{code} currency"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _payload(old_currency_id: str, target_currency_id: str) -> dict[str, object]:
    return {
        "expected_base_currency_id": old_currency_id,
        "target_currency_id": target_currency_id,
        "reason": "The original project denomination was entered incorrectly.",
        "keep_amounts_unchanged": True,
    }


def test_every_project_currency_column_has_a_reviewed_policy() -> None:
    actual = {
        table.name: frozenset(column.name for column in table.c if "currency" in column.name)
        for table in Base.metadata.tables.values()
        if "project_id" in table.c and any("currency" in column.name for column in table.c)
    }
    reviewed = {
        table: frozenset(columns) for table, columns in currency_correction.FIELD_POLICIES.items()
    }
    assert reviewed == actual
    currency_correction.require_complete_currency_review()


def test_unreviewed_currency_column_disables_correction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incomplete = dict(currency_correction.FIELD_POLICIES)
    incomplete.pop("sale_legal_events")
    monkeypatch.setattr(currency_correction, "FIELD_POLICIES", incomplete)
    with pytest.raises(ConflictError, match="every currency-bearing project record"):
        currency_correction.require_complete_currency_review()


def test_only_system_administrators_can_correct_a_project_currency(
    admin_client: TestClient,
    manager: User,
    advisor: User,
    project_id: str,
    currency_id: str,
) -> None:
    target = _currency(admin_client, "USD")
    for user in (manager, advisor):
        grant_access(admin_client, project_id, user)
        response = client_for(user.email).post(
            f"{PROJECTS}/{project_id}/currency-corrections",
            json=_payload(currency_id, target),
        )
        assert response.status_code == 403


def test_correction_relabels_inherited_rows_without_changing_numbers(
    admin: User,
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    target = _currency(admin_client, "USD")
    parcel_response = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels",
        json=parcel_payload(purchase_price="1000000.00", acquisition_fees="25000.00"),
    )
    assert parcel_response.status_code == 201, parcel_response.text
    movement = CashflowDevelopmentMovement(
        project_id=uuid.UUID(project_id),
        movement_reference="DEV-000001",
        category="consultants",
        amount=Decimal("1234.56"),
        currency_id=uuid.UUID(currency_id),
        movement_date=date(2026, 9, 27),
        recorded_by_user_id=admin.id,
    )
    db.add(movement)
    db.commit()

    response = admin_client.post(
        f"{PROJECTS}/{project_id}/currency-corrections",
        json=_payload(currency_id, target),
    )
    assert response.status_code == 200, response.text

    db.expire_all()
    project = db.get(Project, uuid.UUID(project_id))
    parcel = db.scalars(select(LandParcel)).one()
    corrected = db.scalars(select(CashflowDevelopmentMovement)).one()
    audit = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "project_currency.corrected")
    ).one()
    assert project is not None
    assert project.base_currency_id == uuid.UUID(target)
    assert project.reporting_currency_id == uuid.UUID(target)
    assert parcel.purchase_price == Decimal("1000000.00")
    assert parcel.acquisition_fees == Decimal("25000.00")
    assert corrected.amount == Decimal("1234.56")
    assert corrected.currency_id == uuid.UUID(target)
    assert audit.actor_user_id == admin.id
    assert audit.reason == _payload(currency_id, target)["reason"]
    assert audit.after_data is not None
    assert audit.after_data["amounts_unchanged"] is True
    assert audit.after_data["corrected_rows"] == {"cashflow_development_movements.currency_id": 1}


def test_explicit_pricing_and_distinct_reporting_currency_are_preserved(
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
    draft_configuration: str,
    db: Session,
) -> None:
    target = _currency(admin_client, "USD")
    reporting = _currency(admin_client, "EUR")
    project = db.get(Project, uuid.UUID(project_id))
    assert project is not None
    project.reporting_currency_id = uuid.UUID(reporting)
    db.commit()

    response = admin_client.post(
        f"{PROJECTS}/{project_id}/currency-corrections",
        json=_payload(currency_id, target),
    )
    assert response.status_code == 200, response.text

    db.expire_all()
    project = db.get(Project, uuid.UUID(project_id))
    configuration = db.get(PricingConfiguration, uuid.UUID(draft_configuration))
    assert project is not None and configuration is not None
    assert project.reporting_currency_id == uuid.UUID(reporting)
    assert configuration.pricing_currency_id == uuid.UUID(currency_id)


def test_configured_sale_and_legal_fee_evidence_keep_their_explicit_currency(
    admin: User,
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
    sale_id: str,
    db: Session,
) -> None:
    target = _currency(admin_client, "USD")
    event = SaleLegalEvent(
        project_id=uuid.UUID(project_id),
        sale_contract_id=uuid.UUID(sale_id),
        event_type="spa_drafted",
        event_date=date(2026, 9, 27),
        fee_amount=Decimal("775.25"),
        currency_id=uuid.UUID(currency_id),
        entered_by_user_id=admin.id,
    )
    db.add(event)
    db.commit()

    response = admin_client.post(
        f"{PROJECTS}/{project_id}/currency-corrections",
        json=_payload(currency_id, target),
    )
    assert response.status_code == 200, response.text

    db.expire_all()
    sale = db.get(SaleContract, uuid.UUID(sale_id))
    preserved = db.get(SaleLegalEvent, event.id)
    assert sale is not None and preserved is not None
    assert sale.currency_id == uuid.UUID(currency_id)
    assert preserved.currency_id == uuid.UUID(currency_id)
    assert preserved.fee_amount == Decimal("775.25")


def test_direct_price_sale_chain_is_relabelled_without_recalculating_money(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    sales_ops_client: TestClient,
    buyer_id: str,
    project_id: str,
    currency_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    target = _currency(admin_client, "USD")
    approve_areas(admin_client, project_id, unit_id, area_types)
    price_response = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions",
        json={"selling_price": "200000.00", "change_reason": "Launch"},
    )
    assert price_response.status_code == 201, price_response.text
    price_id = price_response.json()["id"]
    price_url = f"{pricing_url(project_id)}/price-versions/{price_id}"
    assert finance_client.post(f"{price_url}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{price_url}/approve", json={"reason": "Reviewed"}).status_code == 200
    assert cfo_client.post(f"{price_url}/activate").status_code == 200
    released_unit.__wrapped__(admin_client, project_id, unit_id, price_id)

    today = date.today()
    reservation_response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations",
        json={
            "unit_id": unit_id,
            "client_id": buyer_id,
            "sales_channel_code": "DIRECT",
            "sales_branch_code": "AMMAN",
            "deposit_required_amount": "5000.00",
            "expires_on": (today + timedelta(days=7)).isoformat(),
            "price_locked_until": (today + timedelta(days=14)).isoformat(),
        },
    )
    assert reservation_response.status_code == 201, reservation_response.text
    reservation_id = reservation_response.json()["reservation"]["id"]
    reservation_url = f"{sales_url(project_id)}/reservations/{reservation_id}"
    assert (
        sales_ops_client.post(
            f"{reservation_url}/confirm-deposit", json={"evidence_reference": "BANK-REF"}
        ).status_code
        == 200
    )
    assert sales_ops_client.post(f"{reservation_url}/activate", json={}).status_code == 200
    sale_response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts",
        json={"reservation_id": reservation_id, "spa_number": "DIRECT-01"},
    )
    assert sale_response.status_code == 201, sale_response.text
    sale_id = sale_response.json()["sale"]["id"]

    response = admin_client.post(
        f"{PROJECTS}/{project_id}/currency-corrections",
        json=_payload(currency_id, target),
    )
    assert response.status_code == 200, response.text

    db.expire_all()
    price = db.get(UnitPriceVersion, uuid.UUID(price_id))
    reservation = db.get(Reservation, uuid.UUID(reservation_id))
    sale = db.get(SaleContract, uuid.UUID(sale_id))
    assert price is not None and reservation is not None and sale is not None
    assert price.currency_id == uuid.UUID(target)
    assert reservation.currency_id == uuid.UUID(target)
    assert reservation.deposit_currency_id == uuid.UUID(target)
    assert sale.currency_id == uuid.UUID(target)
    assert price.reference_price_ex_tax == Decimal("200000.00")
    assert reservation.net_contract_price_ex_tax == Decimal("200000.00")
    assert reservation.deposit_required_amount == Decimal("5000.00")
    assert sale.net_contract_price_ex_tax == Decimal("200000.00")


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"keep_amounts_unchanged": False}, 422),
        ({"reason": "short"}, 422),
    ],
)
def test_correction_requires_reason_and_no_conversion_acknowledgement(
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
    change: dict[str, object],
    status: int,
) -> None:
    target = _currency(admin_client, "USD")
    payload = _payload(currency_id, target)
    payload.update(change)
    response = admin_client.post(f"{PROJECTS}/{project_id}/currency-corrections", json=payload)
    assert response.status_code == status


def test_same_and_inactive_targets_are_rejected(
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    same = admin_client.post(
        f"{PROJECTS}/{project_id}/currency-corrections",
        json=_payload(currency_id, currency_id),
    )
    inactive = _currency(admin_client, "USD")
    disabled = admin_client.patch(f"{SETTINGS}/currencies/{inactive}", json={"is_active": False})
    assert disabled.status_code == 200, disabled.text
    refused = admin_client.post(
        f"{PROJECTS}/{project_id}/currency-corrections",
        json=_payload(currency_id, inactive),
    )
    assert same.status_code == 422
    assert refused.status_code == 422


def test_two_correction_attempts_serialize_and_only_one_commits(
    admin: User,
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    targets = (_currency(admin_client, "USD"), _currency(admin_client, "EUR"))

    def attempt(target: str) -> int:
        with client_for(admin.email) as client:
            return client.post(
                f"{PROJECTS}/{project_id}/currency-corrections",
                json=_payload(currency_id, target),
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(attempt, targets))

    assert statuses == [200, 409]
    db.expire_all()
    project = db.get(Project, uuid.UUID(project_id))
    assert project is not None and str(project.base_currency_id) in targets
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "project_currency.corrected")
        )
        == 1
    )


def test_stale_second_attempt_conflicts_without_a_partial_change(
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    usd = _currency(admin_client, "USD")
    eur = _currency(admin_client, "EUR")
    first = admin_client.post(
        f"{PROJECTS}/{project_id}/currency-corrections", json=_payload(currency_id, usd)
    )
    second = admin_client.post(
        f"{PROJECTS}/{project_id}/currency-corrections", json=_payload(currency_id, eur)
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 409, second.text
    db.expire_all()
    project = db.get(Project, uuid.UUID(project_id))
    assert project is not None and project.base_currency_id == uuid.UUID(usd)
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "project_currency.corrected")
        )
        == 1
    )


def test_domain_failure_rolls_back_every_change_and_audit(
    admin: User,
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _currency(admin_client, "USD")
    movement = CashflowDevelopmentMovement(
        project_id=uuid.UUID(project_id),
        movement_reference="DEV-000001",
        category="consultants",
        amount=Decimal("45.67"),
        currency_id=uuid.UUID(currency_id),
        movement_date=date(2026, 9, 27),
        recorded_by_user_id=admin.id,
    )
    db.add(movement)
    db.commit()

    def fail(*_: object, **__: object) -> dict[str, int]:
        raise RuntimeError("simulated participating-domain failure")

    monkeypatch.setattr(
        currency_correction.construction_correction, "correct_project_base_currency", fail
    )
    with pytest.raises(RuntimeError, match="participating-domain failure"):
        currency_correction.correct_project_base_currency(
            db,
            project_id=uuid.UUID(project_id),
            expected_base_currency_id=uuid.UUID(currency_id),
            target_currency_id=uuid.UUID(target),
            keep_amounts_unchanged=True,
            reason="Correct the denomination after source-document review.",
            actor_user_id=admin.id,
            correlation_id=uuid.uuid4(),
        )

    db.expire_all()
    project = db.get(Project, uuid.UUID(project_id))
    movement = db.scalars(select(CashflowDevelopmentMovement)).one()
    assert project is not None and project.base_currency_id == uuid.UUID(currency_id)
    assert movement.currency_id == uuid.UUID(currency_id)
    assert (
        db.scalars(
            select(AuditEvent).where(AuditEvent.action == "project_currency.corrected")
        ).all()
        == []
    )
