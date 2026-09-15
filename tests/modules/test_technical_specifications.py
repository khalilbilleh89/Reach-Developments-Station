"""Sales delivery guide: persisted facts, authorization and retained confirmations."""

import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access


def url(project: str | uuid.UUID) -> str:
    return f"/api/v1/projects/{project}/construction/technical-specifications"


def payload(**changes: object) -> dict:
    return {
        "category": "finishes",
        "title": "Bathroom floor tiles",
        "scope": "units",
        "applies_to": "All unit bathrooms",
        "description": "Synthetic sample: porcelain tiles.",
        **changes,
    }


def test_create_edit_stale_delete_and_audit(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    response = admin_client.post(url(project_id), json=payload())
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["status"] == "draft" and row["inclusion"] == "undecided"
    path = f"{url(project_id)}/{row['id']}"
    updated = admin_client.put(path, json=payload(description="Revised synthetic tiles", version=1))
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert admin_client.put(path, json=payload(version=1)).status_code == 409
    assert admin_client.get(url(project_id)).json()[0]["description"] == "Revised synthetic tiles"
    assert admin_client.delete(path, params={"reason": " "}).status_code == 422
    assert admin_client.delete(path, params={"reason": "Duplicate draft"}).status_code == 204
    assert admin_client.get(url(project_id)).json() == []
    assert admin_client.delete(path, params={"reason": "Again"}).status_code == 404
    assert db.scalar(text("SELECT count(*) FROM technical_specifications")) == 0
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == "technical_specification")
            .order_by(AuditEvent.occurred_at)
        )
    )
    assert len(events) == 3
    assert events[-1].before_data["description"] == "Revised synthetic tiles"
    assert events[-1].reason == "Duplicate draft"


@pytest.mark.parametrize("role", ["sales_advisor", "sales_operations"])
def test_sales_reads_specs_without_cost_access(
    admin_client: TestClient, project_id: str, db: Session, role: str
) -> None:
    actor = make_user(db, email=f"{role}@example.com", roles=(role,))
    grant_access(admin_client, project_id, actor)
    reader = client_for(actor.email)
    created = admin_client.post(url(project_id), json=payload()).json()
    assert reader.get(url(project_id)).json()[0]["id"] == created["id"]
    assert reader.get(f"/api/v1/projects/{project_id}/construction/summary").status_code == 403
    assert reader.post(url(project_id), json=payload()).status_code == 403
    assert reader.put(f"{url(project_id)}/{created['id']}", json=payload()).status_code == 403
    assert (
        reader.delete(f"{url(project_id)}/{created['id']}", params={"reason": "No"}).status_code
        == 403
    )
    assert reader.get(url(uuid.uuid4())).status_code == 404


def test_confirmed_specs_require_evidence_and_retain_deleted_history(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    assert (
        admin_client.post(
            url(project_id), json=payload(status="confirmed", inclusion="included")
        ).status_code
        == 422
    )
    assert (
        admin_client.post(
            url(project_id), json=payload(status="confirmed", source_reference="Drawing A1")
        ).status_code
        == 422
    )
    row = admin_client.post(
        url(project_id),
        json=payload(
            status="confirmed", inclusion="included", source_reference="Synthetic schedule Rev A"
        ),
    ).json()
    assert (
        admin_client.delete(
            f"{url(project_id)}/{row['id']}", params={"reason": "Superseded"}
        ).status_code
        == 204
    )
    assert admin_client.get(url(project_id)).json() == []
    assert (
        db.scalar(
            text("SELECT count(*) FROM technical_specifications WHERE removed_at IS NOT NULL")
        )
        == 1
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="retained confirmations"):
        command.downgrade(alembic_config(), "0030_unit_removal")


def test_wrong_project_and_phase_scope_are_refused(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    from app.modules.projects.models import UserProjectAccess

    actor = make_user(db, email="limited@example.com", roles=("design_engineering",))
    grant_access(admin_client, project_id, actor)
    access = db.scalar(select(UserProjectAccess).where(UserProjectAccess.user_id == actor.id))
    access.phase_scope = "selected"
    db.commit()
    limited = client_for(actor.email)
    assert limited.get(url(project_id)).status_code == 403
    assert limited.post(url(project_id), json=payload()).status_code == 403
    row = admin_client.post(url(project_id), json=payload()).json()
    assert admin_client.put(f"{url(uuid.uuid4())}/{row['id']}", json=payload()).status_code == 404
    assert (
        admin_client.delete(
            f"{url(uuid.uuid4())}/{row['id']}", params={"reason": "Wrong project"}
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"applies_to": " "},
        {"description": " "},
        {"category": "invented"},
        {"unexpected": True},
        {"description": None},
    ],
)
def test_invalid_specification_refused(
    admin_client: TestClient, project_id: str, changes: dict
) -> None:
    assert admin_client.post(url(project_id), json=payload(**changes)).status_code == 422


def test_specification_migration_roundtrip(db: Session) -> None:
    db.rollback()
    command.downgrade(alembic_config(), "0030_unit_removal")
    command.upgrade(alembic_config(), "head")
    assert db.scalar(text("SELECT count(*) FROM technical_specifications")) == 0
