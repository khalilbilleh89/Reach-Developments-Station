"""Project-scoped access: who can see a project at all.

The row-level boundary this PR exists to establish. Holding a global role is not
access — a Project Manager sees the projects they are on, not every project.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.projects.models import UserProjectAccess
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, project_payload


def test_a_system_administrator_lists_every_project(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    """Given projects they are not a member of, then an administrator still sees them."""
    second = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="SECOND")
    )
    assert second.status_code == 201, second.text

    listing = admin_client.get(PROJECTS).json()

    assert sorted(item["code"] for item in listing) == ["GALINI-BLU", "SECOND"]


def test_a_global_role_alone_grants_no_project_visibility(manager: User, project_id: str) -> None:
    """Given a Project Manager with no membership, then the register is empty.

    The whole point of the access table: the role says what someone may do
    inside a project, never which projects exist for them.
    """
    client = client_for(manager.email)

    assert client.get(PROJECTS).json() == []
    assert client.get(f"{PROJECTS}/{project_id}").status_code == 404


def test_granted_access_makes_a_project_visible(
    admin_client: TestClient, manager: User, project_id: str
) -> None:
    """Given a membership row, then the project appears and can be read."""
    grant_access(admin_client, project_id, manager)
    client = client_for(manager.email)

    listing = client.get(PROJECTS).json()

    assert [item["id"] for item in listing] == [project_id]
    assert client.get(f"{PROJECTS}/{project_id}").status_code == 200


def test_revoking_access_removes_visibility_immediately(
    admin_client: TestClient, manager: User, project_id: str
) -> None:
    """Given access is revoked, then the next request cannot see the project."""
    grant_access(admin_client, project_id, manager)
    client = client_for(manager.email)
    assert client.get(f"{PROJECTS}/{project_id}").status_code == 200

    revoked = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{manager.id}", json={"is_active": False}
    )

    assert revoked.status_code == 200
    assert revoked.json()["is_active"] is False
    assert client.get(f"{PROJECTS}/{project_id}").status_code == 404
    assert client.get(PROJECTS).json() == []


def test_an_inaccessible_project_reports_not_found_rather_than_forbidden(
    advisor: User, project_id: str
) -> None:
    """Given no access, then 404 — a 403 would confirm the project exists."""
    client = client_for(advisor.email)

    response = client.get(f"{PROJECTS}/{project_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found."}


def test_regranting_revoked_access_reactivates_the_same_row(
    admin_client: TestClient, manager: User, project_id: str, db: Session
) -> None:
    """Given a revoked membership, then re-granting reuses it rather than adding one.

    One row per pairing keeps the grant/revoke history on a single readable line
    instead of scattering it across duplicates.
    """
    grant_access(admin_client, project_id, manager)
    original = db.scalars(select(UserProjectAccess)).one().id
    admin_client.patch(f"{PROJECTS}/{project_id}/access/{manager.id}", json={"is_active": False})

    grant_access(admin_client, project_id, manager)

    rows = db.scalars(select(UserProjectAccess)).all()
    assert len(rows) == 1
    assert rows[0].id == original
    assert rows[0].is_active is True
    assert rows[0].revoked_at is None


def test_duplicate_access_rows_cannot_exist(
    admin_client: TestClient, manager: User, project_id: str, db: Session
) -> None:
    """Given repeated grants, then exactly one membership row exists."""
    for _ in range(3):
        grant_access(admin_client, project_id, manager)

    assert len(db.scalars(select(UserProjectAccess)).all()) == 1


def test_an_inactive_user_cannot_be_granted_access(
    admin_client: TestClient, db: Session, project_id: str
) -> None:
    """Given a deactivated account, then it cannot be added to a project."""
    retired = make_user(db, email="retired@example.com", roles=("legal",), is_active=False)

    response = admin_client.put(f"{PROJECTS}/{project_id}/access/{retired.id}")

    assert response.status_code == 422
    assert response.json() == {"detail": "User must be an active user."}


def test_a_project_manager_creating_a_project_receives_access(
    manager_client: TestClient, country_pack_id: str, currency_id: str, reference_data: None
) -> None:
    """Given a manager creates a project, then they can open what they just made."""
    created = manager_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="PM-MADE")
    )

    assert created.status_code == 201, created.text
    project_id = created.json()["id"]
    assert manager_client.get(f"{PROJECTS}/{project_id}").status_code == 200
    assert [item["id"] for item in manager_client.get(PROJECTS).json()] == [project_id]


def test_assigning_a_project_manager_grants_them_access(
    admin_client: TestClient, manager: User, project_id: str, db: Session
) -> None:
    """Given a manager is assigned, then their access is created in the same change.

    A manager who cannot open the project is not managing it.
    """
    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"project_manager_user_id": str(manager.id)}
    )

    assert response.status_code == 200, response.text
    access = db.scalars(
        select(UserProjectAccess).where(UserProjectAccess.user_id == manager.id)
    ).one()
    assert access.is_active is True
    assert client_for(manager.email).get(f"{PROJECTS}/{project_id}").status_code == 200


def test_the_assigned_project_managers_access_cannot_be_revoked(
    admin_client: TestClient, manager: User, project_id: str
) -> None:
    """Given they are the assigned manager, then revoking access is refused."""
    admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"project_manager_user_id": str(manager.id)}
    )

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{manager.id}", json={"is_active": False}
    )

    assert response.status_code == 409
    assert "assigned project manager" in response.json()["detail"]


def test_clearing_the_manager_then_revoking_access_is_allowed(
    admin_client: TestClient, manager: User, project_id: str
) -> None:
    """Given the manager is cleared first, then their access can be withdrawn."""
    admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"project_manager_user_id": str(manager.id)}
    )
    cleared = admin_client.patch(f"{PROJECTS}/{project_id}", json={"project_manager_user_id": None})
    assert cleared.status_code == 200, cleared.text

    revoked = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{manager.id}", json={"is_active": False}
    )

    assert revoked.status_code == 200
    assert revoked.json()["is_active"] is False


def test_only_a_system_administrator_administers_access(
    admin_client: TestClient, manager: User, project_id: str
) -> None:
    """Given a member who is not an administrator, then access administration is 403.

    403 rather than 404: they can already see this project, so there is nothing
    left to conceal — only an action to refuse.
    """
    grant_access(admin_client, project_id, manager)
    client = client_for(manager.email)

    assert client.get(f"{PROJECTS}/{project_id}/access").status_code == 403
    assert client.put(f"{PROJECTS}/{project_id}/access/{manager.id}").status_code == 403


def test_access_administration_is_hidden_from_non_members(advisor: User, project_id: str) -> None:
    """Given no project access, then even the access endpoints report 404."""
    client = client_for(advisor.email)

    assert client.get(f"{PROJECTS}/{project_id}/access").status_code == 404


def test_access_changes_are_audited(
    admin_client: TestClient, manager: User, project_id: str, db: Session
) -> None:
    """Given a grant, a revoke and a re-grant, then each is recorded."""
    grant_access(admin_client, project_id, manager)
    admin_client.patch(f"{PROJECTS}/{project_id}/access/{manager.id}", json={"is_active": False})
    grant_access(admin_client, project_id, manager)

    actions = [
        event.action
        for event in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.action.like("project_access.%"))
            .order_by(AuditEvent.occurred_at)
        )
    ]

    assert actions == [
        "project_access.granted",
        "project_access.revoked",
        "project_access.reactivated",
    ]


def test_access_listing_exposes_identity_but_never_credentials(
    admin_client: TestClient, manager: User, project_id: str
) -> None:
    """Given the administration view, then it carries no password or session data."""
    grant_access(admin_client, project_id, manager)

    row = admin_client.get(f"{PROJECTS}/{project_id}/access").json()[0]

    assert row["email"] == manager.email
    assert row["role_keys"] == ["project_manager"]
    assert not {"password", "password_hash", "token", "session"}.intersection(row)


def test_revoking_access_a_user_never_had_is_not_found(
    admin_client: TestClient, advisor: User, project_id: str
) -> None:
    """Given no membership row, then there is nothing to revoke."""
    response = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{advisor.id}", json={"is_active": False}
    )

    assert response.status_code == 404


def test_access_cannot_be_granted_on_an_unknown_project(
    admin_client: TestClient, manager: User
) -> None:
    """Given an identifier that names nothing, then the answer is the same 404."""
    response = admin_client.put(f"{PROJECTS}/{uuid.uuid4()}/access/{manager.id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found."}
