"""Authentication behaviour: credentials, sessions, cookies and password change."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.access import security
from app.modules.access.dependencies import SESSION_COOKIE_NAME
from app.modules.access.models import User, UserSession
from tests.factories import (
    DEFAULT_PASSWORD,
    FOREIGN_ORIGIN,
    anonymous_client,
    client_for,
    cookie_attributes,
    expire_sessions,
    make_user,
    session_row,
)

LOGIN_URL = "/api/v1/auth/login"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"
CHANGE_PASSWORD_URL = "/api/v1/auth/change-password"
INVALID_CREDENTIALS = "Invalid email or password."


@pytest.fixture
def member(db: Session) -> User:
    return make_user(db, email="member@example.com", roles=("finance",))


def test_valid_credentials_open_a_session(member: User) -> None:
    """Given correct credentials, then login succeeds and returns the caller."""
    client = anonymous_client()

    response = client.post(LOGIN_URL, json={"email": member.email, "password": DEFAULT_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == member.email
    assert body["must_change_password"] is False
    assert [role["key"] for role in body["roles"]] == ["finance"]
    assert [role["label"] for role in body["roles"]] == ["Finance"]


def test_wrong_password_is_rejected(member: User) -> None:
    """Given a wrong password, then login fails with the generic message."""
    response = anonymous_client().post(
        LOGIN_URL, json={"email": member.email, "password": "not-the-password"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": INVALID_CREDENTIALS}


def test_unknown_email_is_indistinguishable_from_a_wrong_password(member: User) -> None:
    """Given an email nobody owns, then the response is byte-identical.

    Anything else turns the login form into an account enumerator.
    """
    client = anonymous_client()

    unknown = client.post(
        LOGIN_URL, json={"email": "nobody@example.com", "password": "not-the-password"}
    )
    wrong = client.post(LOGIN_URL, json={"email": member.email, "password": "not-the-password"})

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": INVALID_CREDENTIALS}


def test_inactive_users_cannot_log_in(db: Session) -> None:
    """Given a deactivated account, then correct credentials still fail."""
    user = make_user(db, email="gone@example.com", is_active=False)

    response = anonymous_client().post(
        LOGIN_URL, json={"email": user.email, "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": INVALID_CREDENTIALS}


def test_session_cookie_is_http_only_strict_and_scoped(member: User) -> None:
    """Given a successful login, then the cookie cannot be read or sent cross-site."""
    response = anonymous_client().post(
        LOGIN_URL, json={"email": member.email, "password": DEFAULT_PASSWORD}
    )

    attributes = cookie_attributes(response.headers)
    assert "httponly" in attributes
    assert attributes["samesite"].casefold() == "strict"
    assert attributes["path"] == "/"
    assert SESSION_COOKIE_NAME in attributes
    # Not marked Secure outside production, so local http development works.
    assert "secure" not in attributes


def test_production_marks_the_session_cookie_secure(
    member: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given production settings, then the cookie is Secure."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DEBUG", "false")
    get_settings.cache_clear()

    response = anonymous_client().post(
        LOGIN_URL, json={"email": member.email, "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    assert "secure" in cookie_attributes(response.headers)


def test_the_raw_session_token_is_never_stored(member: User, db: Session) -> None:
    """Given a session, then the database holds only its digest.

    A database dump must not yield a usable session.
    """
    response = anonymous_client().post(
        LOGIN_URL, json={"email": member.email, "password": DEFAULT_PASSWORD}
    )
    raw_token = response.cookies[SESSION_COOKIE_NAME]

    stored = session_row(db, member.id)
    assert stored.token_hash != raw_token
    assert stored.token_hash == security.hash_session_token(raw_token)
    by_raw_token = select(UserSession).where(UserSession.token_hash == raw_token)
    assert db.scalars(by_raw_token).first() is None


def test_the_session_digest_resolves_the_right_user(member: User, db: Session) -> None:
    """Given a stored digest, then it maps back to its owner."""
    client = client_for(member.email)

    assert session_row(db, member.id).user_id == member.id
    assert client.get(ME_URL).json()["id"] == str(member.id)


def test_expired_sessions_are_rejected(member: User, db: Session) -> None:
    """Given a session past its expiry, then it no longer authenticates."""
    client = client_for(member.email)
    assert client.get(ME_URL).status_code == 200

    expire_sessions(db, member.id)

    assert client.get(ME_URL).status_code == 401


def test_logout_revokes_the_session_and_clears_the_cookie(member: User, db: Session) -> None:
    """Given a logout, then the session is revoked and cannot be reused."""
    client = client_for(member.email)

    response = client.post(LOGOUT_URL)

    assert response.status_code == 204
    assert session_row(db, member.id).revoked_at is not None
    assert client.get(ME_URL).status_code == 401


def test_logout_is_idempotent(member: User) -> None:
    """Given a second logout, then it still succeeds."""
    client = client_for(member.email)

    assert client.post(LOGOUT_URL).status_code == 204
    assert client.post(LOGOUT_URL).status_code == 204


def test_a_revoked_session_is_rejected(member: User, db: Session) -> None:
    """Given a session revoked out of band, then it stops working immediately."""
    client = client_for(member.email)
    row = session_row(db, member.id)
    row.revoked_at = datetime.now(UTC)
    db.commit()

    assert client.get(ME_URL).status_code == 401


def test_changing_a_password_revokes_every_session(member: User, db: Session) -> None:
    """Given a password change, then the caller must log in again."""
    client = client_for(member.email)

    response = client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": DEFAULT_PASSWORD, "new_password": "a-brand-new-password"},
    )

    assert response.status_code == 204
    assert client.get(ME_URL).status_code == 401
    assert all(
        row.revoked_at is not None
        for row in db.scalars(select(UserSession).where(UserSession.user_id == member.id))
    )
    # The new password works; the old one does not.
    assert (
        anonymous_client()
        .post(LOGIN_URL, json={"email": member.email, "password": "a-brand-new-password"})
        .status_code
        == 200
    )
    assert (
        anonymous_client()
        .post(LOGIN_URL, json={"email": member.email, "password": DEFAULT_PASSWORD})
        .status_code
        == 401
    )


def test_changing_a_password_requires_the_current_one(member: User) -> None:
    """Given a wrong current password, then the change is refused."""
    client = client_for(member.email)

    response = client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": "wrong-current-value", "new_password": "a-brand-new-password"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Current password is incorrect."}


def test_deactivating_a_user_revokes_their_sessions(db: Session) -> None:
    """Given a deactivation, then the user's live session stops working."""
    admin = make_user(db, email="admin@example.com", roles=("system_admin",))
    victim = make_user(db, email="victim@example.com", roles=("finance",))
    victim_client = client_for(victim.email)
    assert victim_client.get(ME_URL).status_code == 200

    response = client_for(admin.email).patch(
        f"/api/v1/admin/users/{victim.id}", json={"is_active": False}
    )

    assert response.status_code == 200
    assert victim_client.get(ME_URL).status_code == 401


def test_a_temporary_password_blocks_everything_but_the_change(db: Session) -> None:
    """Given a first login, then only self-service endpoints are reachable."""
    user = make_user(
        db, email="fresh@example.com", roles=("system_admin",), must_change_password=True
    )
    client = client_for(user.email)

    assert client.get(ME_URL).status_code == 200
    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.get("/api/v1/settings/currencies").status_code == 403

    changed = client.post(CHANGE_PASSWORD_URL, json={"new_password": "a-brand-new-password"})
    assert changed.status_code == 204

    reauthenticated = client_for(user.email, "a-brand-new-password")
    assert reauthenticated.get("/api/v1/admin/users").status_code == 200


@pytest.mark.parametrize("weak", ["short", "elevenchars", ""])
def test_short_passwords_are_rejected(db: Session, weak: str) -> None:
    """Given a password under the minimum length, then the change is refused."""
    user = make_user(db, email="weak@example.com")
    client = client_for(user.email)

    response = client.post(
        CHANGE_PASSWORD_URL, json={"current_password": DEFAULT_PASSWORD, "new_password": weak}
    )

    assert response.status_code == 422


def test_password_hashes_never_appear_in_a_response(db: Session) -> None:
    """Given any user-facing payload, then no hash is present."""
    admin = make_user(db, email="admin@example.com", roles=("system_admin",))
    client = client_for(admin.email)

    bodies = [
        client.get(ME_URL).text,
        client.get("/api/v1/admin/users").text,
        client.get(f"/api/v1/admin/users/{admin.id}").text,
    ]

    for body in bodies:
        assert "argon2" not in body
        assert "password_hash" not in body
        assert DEFAULT_PASSWORD not in body


def test_login_records_the_last_login_time(member: User, db: Session) -> None:
    """Given a login, then last_login_at is stamped."""
    assert member.last_login_at is None

    client_for(member.email)

    db.refresh(member)
    assert member.last_login_at is not None
    assert (datetime.now(UTC) - member.last_login_at).total_seconds() < 60


def test_cross_origin_state_change_is_rejected(member: User) -> None:
    """Given a cookie-authenticated unsafe request from another origin, then 403."""
    client = client_for(member.email)

    response = client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": DEFAULT_PASSWORD, "new_password": "a-brand-new-password"},
        headers={"Origin": FOREIGN_ORIGIN},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-origin request rejected."}


def test_same_origin_state_change_is_allowed(member: User) -> None:
    """Given the request's own origin, then the change proceeds."""
    client = client_for(member.email)

    response = client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": DEFAULT_PASSWORD, "new_password": "a-brand-new-password"},
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 204


@pytest.mark.parametrize(
    "method,url",
    [
        ("GET", ME_URL),
        ("GET", "/api/v1/admin/users"),
        ("GET", "/api/v1/admin/roles"),
        ("POST", "/api/v1/admin/users"),
        ("GET", "/api/v1/settings/currencies"),
        ("POST", "/api/v1/settings/currencies"),
        ("GET", "/api/v1/audit-events"),
    ],
)
def test_protected_endpoints_require_authentication(method: str, url: str) -> None:
    """Given no session, then every protected endpoint answers 401."""
    response = anonymous_client().request(method, url, json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_every_response_carries_a_correlation_id(member: User) -> None:
    """Given any request, then the response identifies it for the audit trail."""
    client: TestClient = anonymous_client()

    unauthorised = client.get(ME_URL)
    ok = client.post(LOGIN_URL, json={"email": member.email, "password": DEFAULT_PASSWORD})
    missing = client.get("/api/v1/nope")

    for response in (unauthorised, ok, missing):
        assert response.headers.get("X-Correlation-ID")
    assert unauthorised.headers["X-Correlation-ID"] != ok.headers["X-Correlation-ID"]
