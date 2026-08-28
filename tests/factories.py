"""Helpers for arranging governance test state.

Users are created directly in the database rather than through the API so that
a test about, say, tax rules does not depend on the user-administration
endpoints working.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import create_app
from app.modules.access import security
from app.modules.access.models import Role, User, UserRole, UserSession

#: Argon2 is deliberately slow, which is correct in production and wasteful in a
#: suite that reuses a handful of passwords. Hashes are cached per password so
#: the cost is paid once, not once per fixture.
_HASH_CACHE: dict[str, str] = {}

DEFAULT_PASSWORD = "correct-horse-battery"

#: An origin that is never the test host, for cross-origin rejection tests.
FOREIGN_ORIGIN = "https://evil.example.com"


def _cached_hash(password: str) -> str:
    if password not in _HASH_CACHE:
        _HASH_CACHE[password] = security.hash_password(password)
    return _HASH_CACHE[password]


def make_user(
    db: Session,
    *,
    email: str,
    password: str = DEFAULT_PASSWORD,
    display_name: str | None = None,
    roles: tuple[str, ...] = (),
    is_active: bool = True,
    must_change_password: bool = False,
) -> User:
    """Insert a user holding ``roles`` and commit."""
    user = User(
        email=email,
        email_normalized=security.normalize_email(email),
        display_name=display_name or email.split("@")[0].title(),
        password_hash=_cached_hash(password),
        is_active=is_active,
        must_change_password=must_change_password,
    )
    db.add(user)
    db.flush()
    for key in roles:
        role = db.scalars(select(Role).where(Role.key == key)).one()
        db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


def client_for(user_email: str, password: str = DEFAULT_PASSWORD) -> TestClient:
    """Return a client already logged in as ``user_email``."""
    client = TestClient(create_app())
    response = client.post("/api/v1/auth/login", json={"email": user_email, "password": password})
    assert response.status_code == 200, response.text
    return client


def anonymous_client() -> TestClient:
    """Return a client with no session."""
    return TestClient(create_app())


def session_row(db: Session, user_id: uuid.UUID) -> UserSession:
    """Return the user's single session row."""
    return db.scalars(
        select(UserSession).where(UserSession.user_id == user_id).order_by(UserSession.created_at)
    ).all()[-1]


def expire_sessions(db: Session, user_id: uuid.UUID) -> None:
    """Backdate every session for a user so it is past its expiry.

    Both ends move: the table enforces ``expires_at > created_at``, so a session
    that expired in the past must also have started further in the past.
    """
    now = datetime.now(UTC)
    for row in db.scalars(select(UserSession).where(UserSession.user_id == user_id)):
        row.created_at = now - timedelta(hours=2)
        row.expires_at = now - timedelta(hours=1)
    db.commit()


def cookie_attributes(response_headers: object) -> dict[str, str]:
    """Parse the Set-Cookie header into a lower-cased attribute map."""
    raw = response_headers.get("set-cookie", "")  # type: ignore[attr-defined]
    attributes: dict[str, str] = {}
    for part in raw.split(";"):
        piece = part.strip()
        if not piece:
            continue
        key, _, value = piece.partition("=")
        attributes[key.strip().casefold()] = value.strip()
    return attributes
