"""Consultant correction evidence against real PostgreSQL."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_session_factory
from app.core.errors import ConflictError
from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.consultant_engineering import models, service
from app.modules.projects.models import Project
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access
from tests.modules.test_commissions_review import actor, snapshot


def root(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/consultant-engineering"


def engagement(client: TestClient, project_id: str, name: str = "Main") -> dict:
    result = client.post(
        f"{root(project_id)}/engagements",
        json={
            "consultant_name": name,
            "agreement_reference": name,
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


def test_lifecycle_ownership_and_financial_independence(
    manager_member_client: TestClient,
    project_id: str,
    db: Session,
    manager: User,
    engineer_client: TestClient,
    active_sale: str,
) -> None:
    del active_sale
    client = manager_member_client
    before = snapshot(
        db,
        (
            "audit_events",
            "consultant_engagements",
            "consultant_disciplines",
            "consultant_design_stages",
            "consultant_deliverables",
        ),
    )
    first = engagement(client, project_id)
    second = engagement(client, project_id, "Replacement")
    workspace = client.get(root(project_id)).json()
    assert workspace["active_engagement"] is None
    assert {x["id"] for x in workspace["engagements"]} == {first["id"], second["id"]}
    changed = client.put(
        f"{root(project_id)}/engagements/{first['id']}",
        json={
            "consultant_name": "Updated",
            "agreement_reference": "A-2",
            "planned_completion_date": "2026-12-01",
            "expected_updated_at": first["updated_at"],
        },
    )
    assert changed.status_code == 200, changed.text
    assert client.post(f"{root(project_id)}/engagements/{first['id']}/activate").status_code == 200
    assert client.post(f"{root(project_id)}/engagements/{second['id']}/activate").status_code == 409
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "consultant.engagement_active")
    ).one()
    assert event.actor_user_id == manager.id and str(event.entity_id) == first["id"]
    assert event.before_data == {"status": "draft"}
    assert event.after_data == {"status": "active", "project_id": project_id}
    children = []
    for item in (first, second):
        path = f"{root(project_id)}/engagements/{item['id']}"
        discipline = engineer_client.post(f"{path}/disciplines", json={"name": "Landscape"})
        stage = engineer_client.post(f"{path}/stages", json={"name": "Concept"})
        assert discipline.status_code == stage.status_code == 201
        children.append((discipline.json(), stage.json()))
    discipline, stage = children[0]
    response = engineer_client.put(
        f"{root(project_id)}/disciplines/{discipline['id']}",
        json={
            "name": "Civil",
            "lead_name": "Engineering lead",
            "status": "active",
            "notes": "Reviewed",
        },
    )
    assert response.status_code == 200, response.text
    second_stage = client.post(
        f"{root(project_id)}/engagements/{first['id']}/stages", json={"name": "Detailed"}
    ).json()
    moved = client.put(
        f"{root(project_id)}/stages/{second_stage['id']}",
        json={
            "name": "Detailed",
            "sequence": 1,
            "status": "completed",
            "planned_date": "2026-05-01",
            "forecast_date": "2026-05-03",
            "actual_completion_date": "2026-05-04",
            "expected_updated_at": second_stage["updated_at"],
            "expected_order": [stage["id"], second_stage["id"]],
        },
    )
    assert moved.status_code == 200, moved.text
    ordered = [
        x
        for x in client.get(root(project_id)).json()["stages"]
        if x["engagement_id"] == first["id"]
    ]
    assert [(x["id"], x["sequence"]) for x in ordered] == [
        (second_stage["id"], 1),
        (stage["id"], 2),
    ]
    path = f"{root(project_id)}/engagements/{first['id']}/deliverables"
    for stage_id, discipline_id in (
        (children[1][1]["id"], discipline["id"]),
        (stage["id"], children[1][0]["id"]),
    ):
        assert (
            client.post(
                path,
                json={"name": "Wrong owner", "stage_id": stage_id, "discipline_id": discipline_id},
            ).status_code
            == 422
        )
    created = client.post(
        path, json={"name": "Drawings", "stage_id": stage["id"], "discipline_id": discipline["id"]}
    )
    assert created.status_code == 201
    row = created.json()
    body = {
        "name": "Drawings",
        "stage_id": stage["id"],
        "discipline_id": discipline["id"],
        "category": "Package",
        "revision_reference": "R1",
        "document_reference": "DMS-1",
        "due_date": "2026-06-01",
        "submitted_date": "2026-05-30",
        "status": "submitted",
        "notes": "For acceptance",
        "expected_updated_at": row["updated_at"],
    }
    submitted = client.put(f"{root(project_id)}/deliverables/{row['id']}", json=body)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["accepted_date"] is None
    body.update(
        status="accepted",
        accepted_date="2026-06-02",
        expected_updated_at=submitted.json()["updated_at"],
    )
    accepted = client.put(f"{root(project_id)}/deliverables/{row['id']}", json=body)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["document_reference"] == "DMS-1"
    assert client.post(f"{root(project_id)}/engagements/{first['id']}/complete").status_code == 200
    assert client.post(f"{root(project_id)}/engagements/{second['id']}/activate").status_code == 200
    assert (
        client.post(f"{root(project_id)}/engagements/{second['id']}/terminate").status_code == 200
    )
    assert {x["status"] for x in client.get(root(project_id)).json()["engagements"]} == {
        "completed",
        "terminated",
    }
    assert (
        snapshot(
            db,
            (
                "audit_events",
                "consultant_engagements",
                "consultant_disciplines",
                "consultant_design_stages",
                "consultant_deliverables",
            ),
        )
        == before
    )


def test_retained_consultant_refuses_downgrade(
    manager_member_client: TestClient,
    project_id: str,
    db: Session,
) -> None:
    engagement(manager_member_client, project_id)
    before = snapshot(db)
    db.rollback()
    try:
        with pytest.raises(
            SQLAlchemyError, match="cannot downgrade while consultant or commission"
        ):
            command.downgrade(alembic_config(), "0016_prelaunch_utilities")
        assert snapshot(db) == before
        assert (
            db.scalar(text("SELECT version_num FROM alembic_version")) == "0018_management_actions"
        )
    finally:
        db.rollback()
        command.upgrade(alembic_config(), "head")


def test_competing_activations_leave_one_active(
    manager_member_client: TestClient,
    project_id: str,
    manager: User,
    db: Session,
) -> None:
    rows = [engagement(manager_member_client, project_id, name) for name in ("A", "B")]
    principal = actor(manager)
    barrier = Barrier(2)

    def activate(identifier: str) -> object:
        with get_session_factory()() as session:
            project = session.get(Project, uuid.UUID(project_id))
            session.get(models.ConsultantEngagement, uuid.UUID(identifier))
            barrier.wait(timeout=15)
            try:
                return service.transition_engagement(
                    session, project, principal, uuid.UUID(identifier), "active"
                )
            except ConflictError as exc:
                return exc

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(activate, row["id"]) for row in rows]
        outcomes = [future.result(timeout=30) for future in futures]
    assert sum(isinstance(x, ConflictError) for x in outcomes) == 1
    assert db.scalar(text("SELECT count(*) FROM consultant_engagements WHERE status='active'")) == 1
    assert (
        db.scalar(
            text("SELECT count(*) FROM audit_events WHERE action='consultant.engagement_active'")
        )
        == 1
    )


def test_selected_phase_and_commercial_writer_refused(
    admin_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    phase_id: str,
    db: Session,
) -> None:
    assert (
        sales_ops_client.post(
            f"{root(project_id)}/engagements",
            json={"consultant_name": "Denied", "agreement_reference": "X"},
        ).status_code
        == 403
    )
    scoped = make_user(db, email="phase-consultant@example.com", roles=("design_engineering",))
    grant_access(admin_client, project_id, scoped)
    assert (
        admin_client.patch(
            f"/api/v1/projects/{project_id}/access/{scoped.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    admin_client.put(f"/api/v1/projects/{project_id}/access/{scoped.id}/phases/{phase_id}")
    assert client_for(scoped.email).get(root(project_id)).status_code == 403


@pytest.mark.parametrize("transition", ["complete", "terminate"])
def test_historical_engagement_child_mutations_refused(
    manager_member_client: TestClient, project_id: str, db: Session, transition: str
) -> None:
    client = manager_member_client
    agreement = engagement(client, project_id)
    path = f"{root(project_id)}/engagements/{agreement['id']}"
    discipline = client.post(f"{path}/disciplines", json={"name": "Civil"})
    stage = client.post(f"{path}/stages", json={"name": "Concept"})
    assert discipline.status_code == stage.status_code == 201
    discipline, stage = discipline.json(), stage.json()
    body = {"name": "Open drawings", "stage_id": stage["id"], "discipline_id": discipline["id"]}
    deliverable = client.post(f"{path}/deliverables", json=body)
    assert deliverable.status_code == 201
    deliverable = deliverable.json()
    assert deliverable["status"] == "not_started"
    assert client.post(f"{path}/activate").status_code == 200
    assert client.post(f"{path}/{transition}").status_code == 200
    before = snapshot(db)
    visible = client.get(root(project_id))
    assert visible.status_code == 200
    attempts = [
        ("POST", f"{path}/disciplines", {"name": "New discipline"}),
        ("PUT", f"{root(project_id)}/disciplines/{discipline['id']}", {"name": "Changed"}),
        ("POST", f"{path}/stages", {"name": "New stage"}),
        (
            "PUT",
            f"{root(project_id)}/stages/{stage['id']}",
            {
                "name": "Changed",
                "sequence": 1,
                "expected_order": [stage["id"]],
                "expected_updated_at": stage["updated_at"],
            },
        ),
        ("POST", f"{path}/deliverables", {**body, "name": "New deliverable"}),
        (
            "PUT",
            f"{root(project_id)}/deliverables/{deliverable['id']}",
            {
                **body,
                "name": "Changed",
                "expected_updated_at": deliverable["updated_at"],
            },
        ),
    ]
    for method, url, payload in attempts:
        response = client.request(method, url, json=payload)
        assert response.status_code == 409, response.text
        assert "read-only" in response.text
        # Includes all child values/timestamps, row membership and audit events.
        assert snapshot(db) == before, (transition, method, url)
        assert client.get(root(project_id)).json() == visible.json()


def test_draft_programme_update_validation(
    manager_member_client: TestClient, project_id: str, db: Session
) -> None:
    client = manager_member_client
    path = f"{root(project_id)}/engagements"
    body = {
        "consultant_name": "Programme",
        "agreement_reference": "P-1",
        "planned_start_date": "2026-12-10",
        "planned_completion_date": "2026-12-20",
    }
    before_create = snapshot(db)
    invalid = {**body, "planned_completion_date": "2026-12-01"}
    response = client.post(path, json=invalid)
    assert response.status_code == 422, response.text
    assert snapshot(db) == before_create
    created = client.post(path, json=body)
    assert created.status_code == 201, created.text
    row = created.json()
    before = snapshot(db)
    response = client.put(
        f"{path}/{row['id']}",
        json={
            **invalid,
            "expected_updated_at": row["updated_at"],
        },
    )
    assert response.status_code == 422, response.text
    assert "Planned completion cannot precede planned start" in response.text
    assert snapshot(db) == before
    assert client.get(root(project_id)).json()["engagements"] == [row]
    response = client.put(
        f"{path}/{row['id']}",
        json={
            **body,
            "planned_completion_date": "2026-12-25",
            "expected_updated_at": row["updated_at"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["planned_completion_date"] == "2026-12-25"
    assert client.get(root(project_id)).json()["engagements"] == [response.json()]
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "consultant.engagement_updated")
    ).all()
    assert len(events) == 1
    assert str(events[0].entity_id) == row["id"]
    assert events[0].after_data["planned_completion_date"] == "2026-12-25"


@pytest.mark.parametrize(
    "dates",
    [
        {"planned_start_date": "2026-12-10"},
        {"planned_completion_date": "2026-12-01"},
        {},
    ],
)
def test_open_ended_engagement_programme_remains_valid(
    manager_member_client: TestClient, project_id: str, dates: dict
) -> None:
    client = manager_member_client
    path = f"{root(project_id)}/engagements"
    body = {"consultant_name": "Open", "agreement_reference": "O-1", **dates}
    response = client.post(path, json=body)
    assert response.status_code == 201, response.text
    row = response.json()
    response = client.put(
        f"{path}/{row['id']}",
        json={
            **body,
            "notes": "Valid update",
            "expected_updated_at": row["updated_at"],
        },
    )
    assert response.status_code == 200, response.text
    for key in ("planned_start_date", "planned_completion_date"):
        assert response.json()[key] == dates.get(key)
