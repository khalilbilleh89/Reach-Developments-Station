"""Procedure graph validity, scoped lifecycle and retained migration history."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.projects.procedure_models import ProjectProcedure
from app.modules.projects.procedure_schemas import ProcedureFields
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access


def payload() -> dict:
    return {
        "title": "Collections example",
        "sop": "Synthetic demonstration",
        "steps": [
            {"id": "s", "kind": "start", "title": "Start", "next_id": "d"},
            {
                "id": "d",
                "kind": "decision",
                "title": "Payment received?",
                "yes_id": "e",
                "no_id": "a",
            },
            {"id": "a", "kind": "action", "title": "Follow up", "next_id": "d"},
            {"id": "e", "kind": "end", "title": "Complete"},
        ],
    }


def url(project_id: str | uuid.UUID) -> str:
    return f"/api/v1/projects/{project_id}/procedures"


def test_lifecycle_and_retention(admin_client: TestClient, project_id: str, db: Session) -> None:
    response = admin_client.post(url(project_id), json=payload())
    assert response.status_code == 201, response.text
    row = response.json()
    target = f"{url(project_id)}/{row['id']}"
    changed = admin_client.put(target, json={**payload(), "title": "Updated", "version": 1})
    assert changed.status_code == 200
    assert admin_client.put(target, json={**payload(), "version": 1}).status_code == 409
    assert (
        admin_client.post(target + "/delete", json={"version": 1, "reason": "Stale"}).status_code
        == 409
    )
    assert (
        admin_client.post(target + "/delete", json={"version": 2, "reason": " "}).status_code == 422
    )
    assert (
        admin_client.post(
            target + "/delete", json={"version": 2, "reason": "Superseded"}
        ).status_code
        == 204
    )
    assert (
        admin_client.post(target + "/delete", json={"version": 2, "reason": "Again"}).status_code
        == 404
    )
    assert admin_client.get(url(project_id)).json()["procedures"] == []
    saved = db.get(ProjectProcedure, uuid.UUID(row["id"]))
    assert saved.is_deleted and saved.payload["sop"] == "Synthetic demonstration"
    event = db.scalar(
        select(AuditEvent).where(AuditEvent.entity_id == saved.id, AuditEvent.action == "delete")
    )
    assert event.reason == "Superseded"


@pytest.mark.parametrize(
    "defect", ["duplicate", "missing", "unreachable", "closed_loop", "no_start", "blank", "nul"]
)
def test_invalid_graph(defect: str) -> None:
    body = payload()
    if defect == "duplicate":
        body["steps"][2]["id"] = "d"
    if defect == "missing":
        body["steps"][1]["no_id"] = "unknown"
    if defect == "unreachable":
        body["steps"].append({"id": "u", "kind": "end", "title": "Unused"})
    if defect == "closed_loop":
        body["steps"][1]["yes_id"] = "a"
    if defect == "no_start":
        body["steps"][0]["kind"] = "action"
    if defect == "blank":
        body["title"] = " "
    if defect == "nul":
        body["steps"][1]["description"] = "bad\x00text"
    with pytest.raises(ValidationError):
        ProcedureFields.model_validate(body)


@pytest.mark.parametrize("role,code", [("project_manager", 201), ("executive_viewer", 403)])
def test_scope_and_roles(
    admin_client: TestClient, project_id: str, db: Session, role: str, code: int
) -> None:
    user = make_user(db, email=f"{role}@procedure.test", roles=(role,))
    client = client_for(user.email)
    assert client.get(url(project_id)).status_code == 404
    grant_access(admin_client, project_id, user)
    assert client.get(url(project_id)).status_code == 200
    assert client.post(url(project_id), json=payload()).status_code == code
    row = admin_client.post(url(project_id), json=payload()).json()
    wrong = f"{url(uuid.uuid4())}/{row['id']}"
    assert admin_client.put(wrong, json={**payload(), "version": 1}).status_code == 404
    assert (
        admin_client.post(wrong + "/delete", json={"version": 1, "reason": "Denied"}).status_code
        == 404
    )
    if code == 403:
        target = f"{url(project_id)}/{row['id']}"
        assert client.put(target, json={**payload(), "version": 1}).status_code == 403
        assert (
            client.post(target + "/delete", json={"version": 1, "reason": "Denied"}).status_code
            == 403
        )


def test_migration_roundtrip_and_retention(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0059_marketing_assets")
    command.upgrade(config, "head")
    command.check(config)
    assert admin_client.post(url(project_id), json=payload()).status_code == 201
    with pytest.raises(RuntimeError, match="Procedure history"):
        command.downgrade(config, "0059_marketing_assets")
