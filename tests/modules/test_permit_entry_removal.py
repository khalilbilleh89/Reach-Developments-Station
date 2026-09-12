"""Single-save permit entry and audited removal against real PostgreSQL."""

import uuid
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.projects.batch import positions, reporting_permits
from app.modules.projects.models import Permit, PermitStatusEvent, Project
from app.modules.settings.models import ReferenceValue
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, permit_payload


def add(client: TestClient, project_id: str, **changes: object) -> dict:
    response = client.post(f"{PROJECTS}/{project_id}/permits", json=permit_payload(**changes))
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("initial_status", ["issued", "submitted", "expired"])
def test_one_save_records_current_status_and_full_details(
    admin_client: TestClient, project_id: str, db: Session, initial_status: str
) -> None:
    result = add(
        admin_client,
        project_id,
        initial_status=initial_status,
        permit_type_code="NEW_CONSENT",
        new_permit_type={"code": "NEW_CONSENT", "label": "New consent"},
        authority_reference="AUTH-TEST",
        consultant="Sample consultant",
        fee_amount="123.45",
        conditions="Sample condition",
        notes="Test only",
        actual_submission_date="2025-12-01",
        issue_date="2026-01-01",
        expiry_date="2027-01-01",
        is_blocking=True,
        is_critical_path=True,
    )
    assert result["status"] == initial_status
    assert result["fee_amount"] == "123.45"
    assert result["conditions"] == "Sample condition"
    assert result["expiry_date"] == "2027-01-01"
    history = admin_client.get(
        f"{PROJECTS}/{project_id}/permits/{result['id']}/status-history"
    ).json()
    assert len(history) == 1
    assert history[0]["reason"] == "Initial recorded status"
    assert (
        db.scalar(
            select(func.count())
            .select_from(ReferenceValue)
            .where(ReferenceValue.code == "NEW_CONSENT")
        )
        == 1
    )


def test_failed_permit_does_not_leave_new_type_or_audit(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    add(admin_client, project_id)
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/permits",
        json=permit_payload(
            permit_type_code="ROLLBACK_TEST",
            new_permit_type={"code": "ROLLBACK_TEST", "label": "Must roll back"},
        ),
    )
    assert response.status_code == 409, response.text
    assert (
        db.scalar(
            select(func.count())
            .select_from(ReferenceValue)
            .where(ReferenceValue.code == "ROLLBACK_TEST")
        )
        == 0
    )
    assert len(admin_client.get(f"{PROJECTS}/{project_id}/permits").json()["permits"]) == 1


def test_remove_hides_counts_preserves_history_and_allows_reusing_test_code(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    result = add(admin_client, project_id, initial_status="issued", is_blocking=True)
    url = f"{PROJECTS}/{project_id}/permits/{result['id']}"
    response = admin_client.delete(url)
    assert response.status_code == 204, response.text
    assert admin_client.get(url).status_code == 404
    assert admin_client.patch(url, json={"notes": "cannot modify"}).status_code == 404
    register = admin_client.get(f"{PROJECTS}/{project_id}/permits").json()
    assert register["total"] == register["blocking_count"] == 0
    db.expire_all()
    retained = db.get(Permit, uuid.UUID(result["id"]))
    assert retained.deleted_at is not None
    assert db.scalar(select(func.count()).select_from(PermitStatusEvent)) == 1
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "permit.removed")
        )
        == 1
    )
    scope = select(Project.id).where(Project.id == uuid.UUID(project_id))
    assert reporting_permits(db, scope) == []
    assert positions(db, scope, date(2026, 1, 1)).get(uuid.UUID(project_id)) is None
    assert add(admin_client, project_id)["id"] != result["id"]


def test_remove_requires_admin_and_explicit_dependency_clearance(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    parent = add(admin_client, project_id)
    child = add(admin_client, project_id, permit_code="CHILD", prerequisite_permit_id=parent["id"])
    url = f"{PROJECTS}/{project_id}/permits/{parent['id']}"
    denied = admin_client.delete(url)
    assert denied.status_code == 409 and "CHILD" in denied.text
    user = make_user(db, email="permit-engineer@example.com", roles=("design_engineering",))
    grant_access(admin_client, project_id, user)
    assert client_for(user.email).delete(url).status_code == 403
    assert (
        admin_client.delete(f"{PROJECTS}/{uuid.uuid4()}/permits/{parent['id']}").status_code == 404
    )
    assert (
        admin_client.patch(
            f"{PROJECTS}/{project_id}/permits/{child['id']}", json={"prerequisite_permit_id": None}
        ).status_code
        == 200
    )
    assert admin_client.delete(url).status_code == 204
    denied_link = admin_client.post(
        f"{PROJECTS}/{project_id}/permits",
        json=permit_payload(permit_code="BAD-LINK", prerequisite_permit_id=parent["id"]),
    )
    assert denied_link.status_code == 422


def test_master_admin_can_remove_without_approval(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    result = add(admin_client, project_id)
    user = make_user(db, email="permit-master@example.com", roles=("master_admin",))
    assert (
        client_for(user.email).delete(f"{PROJECTS}/{project_id}/permits/{result['id']}").status_code
        == 204
    )


def test_permit_removal_migration_round_trip(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    result = add(admin_client, project_id)
    db.rollback()
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    try:
        command.downgrade(config, "0022_land_analytics")
        command.upgrade(config, "head")
        command.check(config)
        db.expire_all()
        assert db.get(Permit, uuid.UUID(result["id"])).deleted_at is None
    finally:
        db.rollback()
        command.upgrade(config, "head")
