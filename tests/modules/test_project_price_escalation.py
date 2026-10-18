"""Effective-dated strategy entries preserve percentages, custom stages and history."""

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.projects.escalation_models import PriceEscalation
from app.modules.projects.models import UserProjectAccess
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, project_payload

BODY = {
    "effective_date": "2026-10-18",
    "escalation_percent": "5.1256",
    "project_status": "Foundation complete / phase two",
}


def url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/price-escalations"


def create(client: TestClient, project_id: str, **values: object) -> dict:
    response = client.post(url(project_id), json={**BODY, **values})
    assert response.status_code == 201, response.text
    return response.json()


def test_percentage_custom_status_patch_and_order(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    row = create(admin_client, project_id, project_status="  Foundation complete / phase two  ")
    assert Decimal(row["escalation_percent"]) == Decimal("5.1256")
    assert row["project_status"] == BODY["project_status"]
    stored = db.get(PriceEscalation, uuid.UUID(row["id"]))
    assert stored.escalation_rate_fraction == Decimal("0.051256")
    db.rollback()
    create(admin_client, project_id, effective_date="2026-09-01", escalation_percent="150")
    base = f"{url(project_id)}/{row['id']}"
    patched = admin_client.patch(base, json={"version": 1, "project_status": "Superstructure"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["effective_date"] == BODY["effective_date"]
    assert Decimal(patched.json()["escalation_percent"]) == Decimal("5.1256")
    assert patched.json()["project_status"] == "Superstructure"
    assert (
        admin_client.patch(base, json={"version": 1, "escalation_percent": "10"}).status_code == 409
    )
    assert (
        admin_client.post(base + "/delete", json={"version": 1, "reason": "Stale"}).status_code
        == 409
    )
    rows = admin_client.get(url(project_id)).json()["entries"]
    assert [r["effective_date"] for r in rows] == ["2026-10-18", "2026-09-01"]


@pytest.mark.parametrize(
    "values",
    [
        {"effective_date": "invalid"},
        {"effective_date": None},
        {"escalation_percent": "0"},
        {"escalation_percent": "-1"},
        {"escalation_percent": "0.00001"},
        {"escalation_percent": "100000"},
        {"escalation_percent": "NaN"},
        {"escalation_percent": None},
        {"project_status": " "},
        {"project_status": None},
        {"project_status": "x" * 201},
        {"project_status": "x\x00y"},
        {"unknown": "field"},
    ],
)
def test_invalid_create_and_patch(admin_client: TestClient, project_id: str, values: dict) -> None:
    row = create(admin_client, project_id)
    assert admin_client.post(url(project_id), json={**BODY, **values}).status_code == 422
    assert (
        admin_client.patch(
            f"{url(project_id)}/{row['id']}", json={"version": 1, **values}
        ).status_code
        == 422
    )
    assert admin_client.get(url(project_id)).json()["entries"][0]["version"] == 1


def test_delete_retains_values_audit_and_refuses_replay(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    row = create(admin_client, project_id)
    base = f"{url(project_id)}/{row['id']}"
    assert (
        admin_client.post(base + "/delete", json={"version": 1, "reason": " "}).status_code == 422
    )
    assert (
        admin_client.post(
            base + "/delete", json={"version": 1, "reason": "Entered twice"}
        ).status_code
        == 204
    )
    assert admin_client.get(url(project_id)).json()["entries"] == []
    assert (
        admin_client.post(base + "/delete", json={"version": 2, "reason": "Again"}).status_code
        == 404
    )
    assert (
        admin_client.patch(base, json={"version": 2, "project_status": "Hidden"}).status_code == 404
    )
    saved = db.get(PriceEscalation, uuid.UUID(row["id"]))
    assert saved.is_deleted and saved.project_status == BODY["project_status"]
    event = db.scalar(
        select(AuditEvent).where(AuditEvent.entity_id == saved.id, AuditEvent.action == "delete")
    )
    assert event.reason == "Entered twice" and event.actor_user_id
    assert event.before_data["project_status"] == BODY["project_status"]


@pytest.mark.parametrize(
    "role,can_read,can_write",
    [
        ("project_manager", True, True),
        ("finance", True, True),
        ("master_admin", True, True),
        ("approver_cfo", True, False),
        ("executive_viewer", True, False),
        ("auditor", True, False),
        ("sales_operations", False, False),
        ("design_engineering", False, False),
    ],
)
def test_role_membership_and_phase_scope(
    admin_client: TestClient,
    project_id: str,
    db: Session,
    role: str,
    can_read: bool,
    can_write: bool,
) -> None:
    user = make_user(db, email=f"{role}@escalation.test", roles=(role,))
    client = client_for(user.email)
    if role != "master_admin":
        assert client.get(url(project_id)).status_code == 404
    grant_access(admin_client, project_id, user)
    row = create(admin_client, project_id)
    base = f"{url(project_id)}/{row['id']}"
    response = client.get(url(project_id))
    assert response.status_code == (200 if can_read else 403)
    if can_read:
        assert response.json()["can_manage"] is can_write
    assert client.post(url(project_id), json=BODY).status_code == (201 if can_write else 403)
    assert client.patch(base, json={"version": 1, "project_status": "Launch"}).status_code == (
        200 if can_write else 403
    )
    assert client.post(
        base + "/delete", json={"version": 2 if can_write else 1, "reason": "Correction"}
    ).status_code == (204 if can_write else 403)
    access = db.scalar(
        select(UserProjectAccess).where(
            UserProjectAccess.user_id == user.id,
            UserProjectAccess.project_id == uuid.UUID(project_id),
        )
    )
    access.phase_scope = "selected"
    db.commit()
    if role != "master_admin":
        assert client.get(url(project_id)).status_code == 404
        assert client.post(url(project_id), json=BODY).status_code == 404
        access.is_active = False
        db.commit()
        assert client.get(url(project_id)).status_code == 404


def test_other_project_and_missing_records(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    row = create(admin_client, project_id)
    base = f"{url(other)}/{row['id']}"
    assert (
        admin_client.patch(base, json={"version": 1, "project_status": "Wrong"}).status_code == 404
    )
    assert (
        admin_client.post(base + "/delete", json={"version": 1, "reason": "Wrong"}).status_code
        == 404
    )
    assert admin_client.get(url(other)).json()["entries"] == []


def test_escalation_migration_roundtrip(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0045_inventory_masterplans")
    command.upgrade(config, "head")
    command.check(config)
    row = create(admin_client, project_id)
    assert (
        admin_client.post(
            f"{url(project_id)}/{row['id']}/delete", json={"version": 1, "reason": "Retain"}
        ).status_code
        == 204
    )
    with pytest.raises(RuntimeError, match="Price escalation history"):
        command.downgrade(config, "0045_inventory_masterplans")
    command.upgrade(config, "head")
