"""Team contacts persist without granting access or imposing a member quota."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.projects.models import UserProjectAccess
from app.modules.projects.team_models import ProjectTeamMember
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, project_payload


def url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/team"


def create(client: TestClient, project_id: str, **values: object) -> dict:
    response = client.post(
        url(project_id), json={"team": "operations", "name": "Example Person", **values}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_both_teams_patch_clear_move_and_no_user_created(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    users_before = db.scalar(select(func.count()).select_from(User))
    access_before = db.scalar(select(func.count()).select_from(UserProjectAccess))
    db.rollback()
    row = create(
        admin_client,
        project_id,
        name="  Example Person  ",
        title="Coordinator",
        scope_of_work="Line one\nLine two",
        email="example@example.test",
    )
    create(admin_client, project_id, team="engineering", email="example@example.test")
    assert row["name"] == "Example Person"
    base = f"{url(project_id)}/{row['id']}"
    changed = admin_client.patch(base, json={"version": 1, "team": "engineering", "title": None})
    assert changed.status_code == 200, changed.text
    assert changed.json()["title"] is None
    assert changed.json()["scope_of_work"] == "Line one\nLine two"
    assert changed.json()["version"] == 2
    assert admin_client.patch(base, json={"version": 1, "name": "Stale"}).status_code == 409
    assert (
        admin_client.post(f"{base}/delete", json={"version": 1, "reason": "stale"}).status_code
        == 409
    )
    response = admin_client.get(url(project_id)).json()
    assert response["can_manage"] is True
    assert len(response["members"]) == 2
    assert {person["team"] for person in response["members"]} == {"engineering"}
    assert db.scalar(select(func.count()).select_from(User)) == users_before
    assert db.scalar(select(func.count()).select_from(UserProjectAccess)) == access_before


def test_directory_does_not_truncate_or_limit_additions(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    db.add_all(
        [
            ProjectTeamMember(
                project_id=uuid.UUID(project_id),
                team="operations" if i % 2 else "engineering",
                name=f"Person {i:03d}",
            )
            for i in range(205)
        ]
    )
    db.commit()
    create(admin_client, project_id, name="Last member")
    rows = admin_client.get(url(project_id)).json()["members"]
    assert len(rows) == 206
    assert any(row["name"] == "Person 204" for row in rows)


@pytest.mark.parametrize(
    "payload",
    [
        {"name": " "},
        {"name": None},
        {"team": "other"},
        {"team": None},
        {"email": "invalid"},
        {"email": "a@b\nInjected"},
        {"unknown": "field"},
    ],
)
def test_validation_on_create_and_patch(
    admin_client: TestClient, project_id: str, payload: dict
) -> None:
    row = create(admin_client, project_id)
    assert (
        admin_client.post(
            url(project_id), json={"name": "Valid", "team": "operations", **payload}
        ).status_code
        == 422
    )
    assert (
        admin_client.patch(
            f"{url(project_id)}/{row['id']}", json={"version": 1, **payload}
        ).status_code
        == 422
    )


def test_nul_character_is_a_validation_error_and_writes_nothing(
    admin_client: TestClient, project_id: str
) -> None:
    row = create(admin_client, project_id)
    created = admin_client.post(url(project_id), json={"team": "operations", "name": "A\x00B"})
    assert created.status_code == 422, created.text
    assert created.json() == {"detail": "Text cannot contain the NUL (0x00) character."}
    changed = admin_client.patch(
        f"{url(project_id)}/{row['id']}", json={"version": 1, "scope_of_work": "x\x00"}
    )
    assert changed.status_code == 422
    members = admin_client.get(url(project_id)).json()["members"]
    assert [(m["name"], m["version"]) for m in members] == [(row["name"], 1)]


def test_delete_retains_details_reason_actor_and_audit(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    row = create(admin_client, project_id)
    base = f"{url(project_id)}/{row['id']}"
    assert (
        admin_client.post(f"{base}/delete", json={"version": 1, "reason": " "}).status_code == 422
    )
    assert (
        admin_client.post(
            f"{base}/delete", json={"version": 1, "reason": "Left project"}
        ).status_code
        == 204
    )
    assert (
        admin_client.post(f"{base}/delete", json={"version": 1, "reason": "Again"}).status_code
        == 404
    )
    assert admin_client.patch(base, json={"version": 2, "name": "Hidden"}).status_code == 404
    assert admin_client.get(url(project_id)).json()["members"] == []
    saved = db.get(ProjectTeamMember, uuid.UUID(row["id"]))
    assert saved.is_deleted and saved.name == row["name"]
    events = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == saved.id)).all()
    assert {event.action for event in events} == {"create", "delete"}
    event = next(item for item in events if item.action == "delete")
    assert event.reason == "Left project" and event.actor_user_id
    assert event.before_data["name"] == row["name"]


@pytest.mark.parametrize(
    "role,write_status",
    [
        ("project_manager", 201),
        ("master_admin", 201),
        ("sales_operations", 403),
        ("design_engineering", 403),
        ("executive_viewer", 403),
    ],
)
def test_permissions_membership_and_phase_scope(
    admin_client: TestClient, project_id: str, db: Session, role: str, write_status: int
) -> None:
    user = make_user(db, email=f"{role}@team.test", roles=(role,))
    client = client_for(user.email)
    if role != "master_admin":
        assert client.get(url(project_id)).status_code == 404
    grant_access(admin_client, project_id, user)
    row = create(admin_client, project_id)
    base = f"{url(project_id)}/{row['id']}"
    assert client.get(url(project_id)).status_code == 200
    assert (
        client.post(url(project_id), json={"team": "operations", "name": "Allowed?"}).status_code
        == write_status
    )
    if write_status == 403:
        assert client.get(url(project_id)).json()["can_manage"] is False
        assert client.patch(base, json={"version": 1, "name": "Denied"}).status_code == 403
        assert (
            client.post(f"{base}/delete", json={"version": 1, "reason": "Denied"}).status_code
            == 403
        )
    access = db.scalar(
        select(UserProjectAccess).where(
            UserProjectAccess.user_id == user.id,
            UserProjectAccess.project_id == uuid.UUID(project_id),
        )
    )
    access.phase_scope = "selected"
    db.commit()
    assert client.get(url(project_id)).status_code == 200  # Contact directory is project-wide.
    if role != "master_admin":
        assert client.get(url(project_id)).json()["can_manage"] is False
        assert client.patch(base, json={"version": 1, "name": "Denied"}).status_code == 403
        access.is_active = False
        db.commit()
        assert client.get(url(project_id)).status_code == 404


def test_wrong_project_cannot_mutate_contact(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    row = create(admin_client, project_id)
    base = f"{url(other)}/{row['id']}"
    assert admin_client.patch(base, json={"version": 1, "name": "Wrong project"}).status_code == 404
    assert (
        admin_client.post(f"{base}/delete", json={"version": 1, "reason": "Wrong"}).status_code
        == 404
    )
    assert admin_client.get(url(other)).json()["members"] == []


def test_team_migration_roundtrip_and_retained_history(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0039_project_images")
    command.upgrade(config, "head")
    command.check(config)
    row = create(admin_client, project_id)
    assert (
        admin_client.post(
            f"{url(project_id)}/{row['id']}/delete", json={"version": 1, "reason": "Keep history"}
        ).status_code
        == 204
    )
    with pytest.raises(RuntimeError, match="Team history"):
        command.downgrade(config, "0039_project_images")
    command.upgrade(config, "head")
