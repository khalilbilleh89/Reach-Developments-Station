"""Physical checklist maintenance, access boundaries and retained history."""

import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.models import SYSTEM_ROLES, User
from app.modules.audit.models import AuditEvent
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, construction_url, grant_access, project_payload


def snapshot(stage: dict, **changes: object) -> dict:
    return {
        **{f"expected_{key}": stage[key] for key in ("name", "planned_date", "sequence")},
        **changes,
    }


def test_downgrade_refuses_retained_checklist(
    manager_member_client: TestClient,
    project_id: str,
    unit_id: str,
    db: Session,
) -> None:
    root = construction_url(project_id)
    stage = manager_member_client.post(f"{root}/stages", json={"name": "Retained"}).json()
    path = f"{root}/units/{unit_id}/stages"
    assert (
        manager_member_client.post(
            f"{path}/{stage['id']}/completion",
            json={
                "completed_date": "2026-08-02",
                "reason": "Evidence",
                "expected_revision": 0,
            },
        ).status_code
        == 204
    )
    before = manager_member_client.get(path).json()
    starting_revision = db.scalar(text("SELECT version_num FROM alembic_version"))
    # Release fixture reads before later migrations drop foreign keys to users.
    db.rollback()
    with pytest.raises(RuntimeError, match="Construction stages exist"):
        command.downgrade(alembic_config(), "0014_direct_unit_price")
    assert manager_member_client.get(path).json() == before
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == starting_revision


def test_reorder_rejects_changed_neighbors_even_when_target_position_is_unchanged(
    manager_member_client: TestClient,
    project_id: str,
) -> None:
    client = manager_member_client
    root = construction_url(project_id)
    rows = [client.post(f"{root}/stages", json={"name": name}).json() for name in ("A", "B", "C")]
    order = [row["id"] for row in rows]
    moved = client.patch(
        f"{root}/stages/{rows[2]['id']}", json=snapshot(rows[2], sequence=2, expected_order=order)
    )
    assert moved.status_code == 200, moved.text
    stale = client.patch(
        f"{root}/stages/{rows[0]['id']}", json=snapshot(rows[0], sequence=2, expected_order=order)
    )
    assert stale.status_code == 409
    duplicate = client.patch(f"{root}/stages/{rows[0]['id']}", json=snapshot(rows[0], name=" b "))
    assert duplicate.status_code == 409
    assert [row["name"] for row in client.get(f"{root}/stages").json()] == ["A", "C", "B"]


def test_edit_move_clear_and_preserve_history(
    manager_member_client: TestClient,
    project_id: str,
    unit_id: str,
    db: Session,
) -> None:
    client = manager_member_client
    root = construction_url(project_id)
    stages = [client.post(f"{root}/stages", json={"name": name}).json() for name in ("A", "B", "C")]
    stage = stages[0]
    path = f"{root}/stages/{stage['id']}"
    progress = f"{root}/units/{unit_id}/stages"
    assert (
        client.post(
            f"{progress}/{stage['id']}/completion",
            json={
                "completed_date": "2026-08-02",
                "reason": "Inspection",
                "expected_revision": 0,
            },
        ).status_code
        == 204
    )
    history = client.get(progress).json()["stages"][0]["history"]
    saved = client.patch(path, json=snapshot(stage, name=" Structure ", planned_date="2026-09-01"))
    assert saved.status_code == 200, saved.text
    assert saved.json()["name"] == "Structure"
    assert client.patch(path, json=snapshot(stage, name="Stale")).status_code == 409
    saved = client.patch(path, json=snapshot(saved.json(), planned_date=None))
    assert saved.status_code == 200, saved.text
    assert saved.json()["planned_date"] is None
    for position in (3, 1, 2):
        rows = client.get(f"{root}/stages").json()
        saved = client.patch(
            path,
            json=snapshot(
                saved.json(), sequence=position, expected_order=[row["id"] for row in rows]
            ),
        )
        assert saved.status_code == 200, saved.text
        rows = client.get(f"{root}/stages").json()
        assert [row["sequence"] for row in rows] == [1, 2, 3]
        assert rows[position - 1]["id"] == stage["id"]
    current = client.get(progress).json()
    assert next(row for row in current["stages"] if row["id"] == stage["id"])["history"] == history
    events = list(
        db.scalars(select(AuditEvent).where(AuditEvent.action == "construction.stage_updated"))
    )
    assert len(events) == 5
    assert events[-1].before_data["sequence"] == 1
    assert events[-1].after_data["sequence"] == 2
    assert events[-1].actor_user_id is not None
    assert events[-1].correlation_id is not None


@pytest.mark.parametrize(
    "change",
    [
        {"name": None},
        {"name": " "},
        {"sequence": None},
        {"sequence": 0},
        {"sequence": 2},
        {"sequence": 1},
        {"delivery_status": "completed"},
    ],
)
def test_strict_update(manager_member_client: TestClient, project_id: str, change: dict) -> None:
    client = manager_member_client
    root = construction_url(project_id)
    stage = client.post(f"{root}/stages", json={"name": "A"}).json()
    refused = client.patch(f"{root}/stages/{stage['id']}", json=snapshot(stage, **change))
    assert refused.status_code == 422, refused.text
    assert client.get(f"{root}/stages").json() == [stage]


@pytest.mark.parametrize("role", [key for key, _ in SYSTEM_ROLES if key != "project_manager"])
def test_other_roles_read_but_cannot_configure(
    db: Session,
    admin_client: TestClient,
    manager_member_client: TestClient,
    project_id: str,
    unit_id: str,
    role: str,
) -> None:
    user = make_user(db, email=f"{role}@closure.example", roles=(role,))
    grant_access(admin_client, project_id, user)
    client = client_for(user.email)
    root = construction_url(project_id)
    stage = manager_member_client.post(f"{root}/stages", json={"name": "A"}).json()
    assert client.get(f"{root}/stages").status_code == 200
    assert client.get(f"{root}/units/{unit_id}/stages").status_code == 200
    assert client.post(f"{root}/stages", json={"name": "B"}).status_code == 403
    for changes in ({"name": "B"}, {"sequence": 1, "expected_order": [stage["id"]]}):
        assert (
            client.patch(
                f"{root}/stages/{stage['id']}", json=snapshot(stage, **changes)
            ).status_code
            == 403
        )


def test_selected_pm_and_cross_project_boundaries(
    admin_client: TestClient,
    manager_member_client: TestClient,
    manager: User,
    project_id: str,
    phase_id: str,
    unit_id: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    client = manager_member_client
    root = construction_url(project_id)
    stage = client.post(f"{root}/stages", json={"name": "A"}).json()
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    grant_access(admin_client, other, manager)
    other_root = construction_url(other)
    foreign = client.post(f"{other_root}/stages", json={"name": "Foreign"}).json()
    assert (
        client.patch(
            f"{root}/stages/{foreign['id']}", json=snapshot(foreign, name="Attack")
        ).status_code
        == 404
    )
    body = {"completed_date": "2026-08-02", "reason": "Inspection", "expected_revision": 0}
    assert (
        client.post(
            f"{root}/units/{unit_id}/stages/{foreign['id']}/completion", json=body
        ).status_code
        == 404
    )
    assert (
        admin_client.patch(
            f"{PROJECTS}/{project_id}/access/{manager.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    assert client.get(f"{root}/units/{unit_id}/stages").status_code == 404
    assert (
        client.post(
            f"{root}/units/{unit_id}/stages/{stage['id']}/completion", json=body
        ).status_code
        == 404
    )
    assert admin_client.put(
        f"{PROJECTS}/{project_id}/access/{manager.id}/phases/{phase_id}"
    ).status_code in {200, 201}
    assert client.get(f"{root}/units/{unit_id}/stages").status_code == 200
    assert (
        client.post(
            f"{root}/units/{unit_id}/stages/{stage['id']}/completion", json=body
        ).status_code
        == 204
    )
    assert client.post(f"{root}/stages", json={"name": "B"}).status_code == 403
    for changes in ({"name": "B"}, {"sequence": 1, "expected_order": [stage["id"]]}):
        assert (
            client.patch(
                f"{root}/stages/{stage['id']}", json=snapshot(stage, **changes)
            ).status_code
            == 403
        )


@pytest.mark.parametrize("foreign_key", ["unit", "stage"])
def test_database_rejects_cross_project_events(
    db: Session,
    admin_client: TestClient,
    manager_member_client: TestClient,
    manager: User,
    project_id: str,
    unit_id: str,
    country_pack_id: str,
    currency_id: str,
    foreign_key: str,
) -> None:
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    grant_access(admin_client, other, manager)
    foreign = manager_member_client.post(
        f"{construction_url(other)}/stages", json={"name": "Foreign"}
    ).json()["id"]
    # Choosing either parent project proves each composite FK independently.
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO unit_stage_events "
                "(id, project_id, unit_id, stage_id, sequence, reason, actor_user_id) "
                "VALUES (:id, :project, :unit, :stage, 1, 'test', :actor)"
            ),
            {
                "id": uuid.uuid4(),
                "project": other if foreign_key == "unit" else project_id,
                "unit": unit_id,
                "stage": foreign,
                "actor": manager.id,
            },
        )
