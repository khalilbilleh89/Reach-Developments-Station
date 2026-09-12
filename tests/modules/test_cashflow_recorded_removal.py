"""The existing reversal contract also removes unconfirmed cash claims."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from tests.modules.conftest import (
    PROJECTS,
    cashflow_url,
    grant_access,
    project_payload,
    record_development,
    record_financing,
)


@pytest.mark.parametrize("kind", ["development", "financing"])
def test_recorded_removal_is_scoped_retained_audited_and_never_cash(
    kind: str,
    finance_client: TestClient,
    auditor_client: TestClient,
    admin_client: TestClient,
    finance: User,
    country_pack_id: str,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    record = record_development if kind == "development" else record_financing
    created = record(finance_client, project_id, currency_id)
    assert created.status_code == 201, created.text
    movement_id = created.json()["id"]
    register = f"{cashflow_url(project_id)}/{kind}-movements"
    url = f"{register}/{movement_id}/reverse"
    reason = {"reason": "Duplicate unconfirmed entry"}
    assert auditor_client.post(url, json=reason).status_code == 403
    assert finance_client.post(url, json={"reason": ""}).status_code == 422
    assert finance_client.post(f"{register}/{uuid.uuid4()}/reverse", json=reason).status_code == 404
    assert (
        finance_client.post(
            f"{cashflow_url(str(uuid.uuid4()))}/{kind}-movements/{movement_id}/reverse",
            json=reason,
        ).status_code
        == 404
    )
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER-REMOVAL")
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]
    grant_access(admin_client, other_id, finance)
    assert (
        finance_client.post(
            f"{cashflow_url(other_id)}/{kind}-movements/{movement_id}/reverse", json=reason
        ).status_code
        == 404
    )
    removed = finance_client.post(url, json=reason)
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "reversed"
    assert removed.json()["counts_as_cash"] is False
    assert finance_client.post(url, json=reason).status_code == 409
    assert finance_client.post(f"{register}/{movement_id}/confirm", json={}).status_code == 409
    listing = finance_client.get(register)
    assert listing.status_code == 200
    assert any(row["id"] == movement_id and not row["counts_as_cash"] for row in listing.json())
    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.entity_id == uuid.UUID(movement_id),
            AuditEvent.action == f"cashflow.{kind}_movement_reversed",
        )
    ).all()
    assert len(events) == 1
    assert events[0].reason == reason["reason"]
    assert events[0].actor_user_id is not None
    assert events[0].before_data["status"] == "recorded"
    assert events[0].after_data["status"] == "reversed"
