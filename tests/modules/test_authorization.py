"""Role enforcement.

Only roles and actions that exist today are tested. Future domain permissions
are not anticipated here.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import Role, User
from app.modules.access.service import LAST_ADMIN_DETAIL
from tests.factories import client_for, make_user

FORBIDDEN = "You do not have permission to perform this action."


@pytest.fixture
def admin(db: Session) -> User:
    return make_user(db, email="admin@example.com", roles=("system_admin",))


@pytest.fixture
def auditor(db: Session) -> User:
    return make_user(db, email="auditor@example.com", roles=("auditor",))


@pytest.fixture
def advisor(db: Session) -> User:
    return make_user(db, email="advisor@example.com", roles=("sales_advisor",))


def test_system_administrator_can_manage_users(admin: User) -> None:
    """Given an administrator, then user administration is available."""
    client = client_for(admin.email)

    listing = client.get("/api/v1/admin/users")
    created = client.post(
        "/api/v1/admin/users",
        json={
            "email": "new@example.com",
            "display_name": "New Person",
            "initial_password": "a-temporary-password",
            "role_keys": ["finance"],
        },
    )

    assert listing.status_code == 200
    assert created.status_code == 201
    assert created.json()["must_change_password"] is True
    assert created.json()["role_keys"] == ["finance"]


@pytest.mark.parametrize("actor", ["auditor", "advisor"])
def test_non_administrators_cannot_manage_users(request: pytest.FixtureRequest, actor: str) -> None:
    """Given any non-administrator, then user administration is refused."""
    user: User = request.getfixturevalue(actor)
    client = client_for(user.email)

    listing = client.get("/api/v1/admin/users")
    created = client.post(
        "/api/v1/admin/users",
        json={
            "email": "new@example.com",
            "display_name": "New",
            "initial_password": "a-temporary-password",
            "role_keys": [],
        },
    )

    assert listing.status_code == 403
    assert listing.json() == {"detail": FORBIDDEN}
    assert created.status_code == 403


def test_system_administrator_can_manage_country_settings(admin: User) -> None:
    """Given an administrator, then configuration writes are available."""
    response = client_for(admin.email).post(
        "/api/v1/settings/currencies", json={"code": "JOD", "name": "Jordanian Dinar"}
    )

    assert response.status_code == 201


@pytest.mark.parametrize("actor", ["auditor", "advisor"])
def test_non_administrators_cannot_mutate_configuration(
    request: pytest.FixtureRequest, actor: str
) -> None:
    """Given any non-administrator, then configuration writes are refused."""
    user: User = request.getfixturevalue(actor)

    response = client_for(user.email).post(
        "/api/v1/settings/currencies", json={"code": "JOD", "name": "Jordanian Dinar"}
    )

    assert response.status_code == 403


def test_any_authenticated_role_can_read_configuration(advisor: User) -> None:
    """Given an ordinary role, then reference configuration is readable.

    Every domain needs to resolve a currency or a lookup label; reading them is
    not a privilege.
    """
    client = client_for(advisor.email)

    assert client.get("/api/v1/settings/currencies").status_code == 200
    assert client.get("/api/v1/settings/country-packs").status_code == 200
    assert client.get("/api/v1/settings/reference-values").status_code == 200


def test_auditor_can_read_audit_history(auditor: User) -> None:
    """Given the auditor role, then audit history is readable."""
    response = client_for(auditor.email).get("/api/v1/audit-events")

    assert response.status_code == 200


def test_ordinary_roles_cannot_read_audit_history(advisor: User) -> None:
    """Given a role without oversight duties, then audit history is refused."""
    response = client_for(advisor.email).get("/api/v1/audit-events")

    assert response.status_code == 403


def test_the_role_catalogue_is_read_only(admin: User, db: Session) -> None:
    """Given the fixed catalogue, then the API exposes no way to change it."""
    client = client_for(admin.email)

    assert client.get("/api/v1/admin/roles").status_code == 200
    # No create, update or delete route exists for roles. The /api/v1 namespace
    # guard answers before Starlette can raise 405, so an absent method is
    # reported as an absent endpoint — still the JSON error contract.
    for response in (
        client.post("/api/v1/admin/roles", json={"key": "x", "label": "X"}),
        client.delete("/api/v1/admin/roles"),
        client.patch("/api/v1/admin/roles", json={}),
    ):
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found."}
    assert len(db.scalars(select(Role)).all()) == 11


def test_the_last_system_administrator_cannot_be_deactivated(admin: User) -> None:
    """Given a single administrator, then deactivating them is refused."""
    response = client_for(admin.email).patch(
        f"/api/v1/admin/users/{admin.id}", json={"is_active": False}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": LAST_ADMIN_DETAIL}


def test_the_last_system_administrator_cannot_lose_the_role(admin: User) -> None:
    """Given a single administrator, then removing their role is refused."""
    response = client_for(admin.email).patch(
        f"/api/v1/admin/users/{admin.id}", json={"role_keys": ["finance"]}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": LAST_ADMIN_DETAIL}


def test_an_administrator_may_step_down_when_another_remains(admin: User, db: Session) -> None:
    """Given a second administrator, then the first may hand over."""
    make_user(db, email="second-admin@example.com", roles=("system_admin",))

    response = client_for(admin.email).patch(
        f"/api/v1/admin/users/{admin.id}", json={"role_keys": ["finance"]}
    )

    assert response.status_code == 200
    assert response.json()["role_keys"] == ["finance"]


def test_an_inactive_administrator_does_not_count_towards_the_guard(
    admin: User, db: Session
) -> None:
    """Given a deactivated administrator, then the active one is still protected."""
    make_user(db, email="dormant@example.com", roles=("system_admin",), is_active=False)

    response = client_for(admin.email).patch(
        f"/api/v1/admin/users/{admin.id}", json={"is_active": False}
    )

    assert response.status_code == 409


def test_unknown_role_keys_are_rejected(admin: User) -> None:
    """Given a role key outside the fixed catalogue, then creation fails."""
    response = client_for(admin.email).post(
        "/api/v1/admin/users",
        json={
            "email": "new@example.com",
            "display_name": "New",
            "initial_password": "a-temporary-password",
            "role_keys": ["superuser"],
        },
    )

    assert response.status_code == 422
    assert "superuser" in response.json()["detail"]


def test_users_have_no_delete_endpoint(admin: User, db: Session) -> None:
    """Given the administration API, then users can be deactivated but never removed."""
    response = client_for(admin.email).delete(f"/api/v1/admin/users/{admin.id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found."}
    # The record is untouched.
    db.refresh(admin)
    assert admin.is_active is True
