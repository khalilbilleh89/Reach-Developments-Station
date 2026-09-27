"""A mistaken project denomination is corrected without moving numeric amounts."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.audit.models import AuditEvent
from app.modules.cashflow.models import CashflowDevelopmentMovement
from app.modules.projects.currency_correction import CURRENCY_COLUMNS
from tests.modules.conftest import PROJECTS, SETTINGS, grant_access, parcel_payload, project_payload


def test_every_project_scoped_currency_column_has_a_correction_contract() -> None:
    actual = {
        table.name: frozenset(column.name for column in table.c if "currency" in column.name)
        for table in Base.metadata.tables.values()
        if "project_id" in table.c and any("currency" in column.name for column in table.c)
    }
    assert actual == {table: frozenset(columns) for table, columns in CURRENCY_COLUMNS.items()}


def test_currency_correction_relabels_project_rows_without_changing_amounts(
    admin_client: TestClient,
    admin: object,
    project_id: str,
    currency_id: str,
    country_pack_id: str,
    db: Session,
) -> None:
    new_currency = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "USD", "name": "US dollar", "symbol": "$"}
    ).json()["id"]
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    parcel = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels",
        json=parcel_payload(purchase_price="1000000.00"),
    )
    assert parcel.status_code == 201, parcel.text
    db.add_all(
        [
            CashflowDevelopmentMovement(
                project_id=uuid.UUID(pid),
                movement_reference=f"DEV-{number:06d}",
                category="consultants",
                amount=Decimal("123.45"),
                currency_id=uuid.UUID(currency_id),
                movement_date=date.today(),
                recorded_by_user_id=admin.id,
            )
            for number, pid in enumerate((project_id, other), start=1)
        ]
    )
    db.commit()
    assert (
        admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": "active"}).status_code == 200
    )
    assert (
        admin_client.patch(
            f"{PROJECTS}/{project_id}", json={"base_currency_id": new_currency}
        ).status_code
        == 409
    )

    corrected = admin_client.post(
        f"{PROJECTS}/{project_id}/currency-corrections",
        json={
            "new_base_currency_id": new_currency,
            "keep_amounts_unchanged": True,
            "reason": "Original currency entered incorrectly",
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["base_currency_code"] == "USD"
    assert corrected.json()["reporting_currency_code"] == "USD"
    parcel_after = admin_client.get(f"{PROJECTS}/{project_id}/parcels").json()[0]
    assert parcel_after["purchase_price"] == "1000000.00"
    assert parcel_after["base_currency_code"] == "USD"
    db.expire_all()
    movements = db.scalars(
        select(CashflowDevelopmentMovement).order_by(CashflowDevelopmentMovement.movement_reference)
    ).all()
    assert [row.amount for row in movements] == [Decimal("123.45"), Decimal("123.45")]
    assert [row.currency_id for row in movements] == [
        uuid.UUID(new_currency),
        uuid.UUID(currency_id),
    ]
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "project_currency.corrected"))
    assert event is not None
    assert event.reason == "Original currency entered incorrectly"
    assert event.after_data["amounts_unchanged"] is True
    assert event.after_data["corrected_rows"]["cashflow_development_movements.currency_id"] == 1


def test_correction_requires_admin_acknowledgement_and_reason(
    admin_client: TestClient,
    manager_client: TestClient,
    manager: object,
    project_id: str,
    db: Session,
) -> None:
    new_currency = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "USD", "name": "US dollar"}
    ).json()["id"]
    grant_access(admin_client, project_id, manager)
    path = f"{PROJECTS}/{project_id}/currency-corrections"
    payload = {
        "new_base_currency_id": new_currency,
        "reason": "Wrong opening currency",
        "keep_amounts_unchanged": True,
    }
    assert manager_client.post(path, json=payload).status_code == 403
    assert (
        admin_client.post(path, json={**payload, "keep_amounts_unchanged": False}).status_code
        == 422
    )
    assert admin_client.post(path, json={**payload, "reason": "short"}).status_code == 422
