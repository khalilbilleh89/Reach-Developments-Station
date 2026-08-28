"""Identity, session and role logic.

Every function here takes an open session and never commits: the caller owns the
transaction boundary, so a change and its audit event succeed or fail together.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access import security
from app.modules.access.models import (
    ROLE_SYSTEM_ADMIN,
    Role,
    User,
    UserRole,
    UserSession,
)
from app.modules.audit.service import record_event

ENTITY_USER = "user"

#: Conflict message used whenever the last administrator would be lost. Stated
#: once so the API and the tests cannot drift apart.
LAST_ADMIN_DETAIL = "This change would leave the system with no active System Administrator."


def _now() -> datetime:
    return datetime.now(UTC)


def user_snapshot(user: User) -> dict[str, Any]:
    """Audit-safe representation of a user. Never includes the password hash."""
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "role_keys": sorted(user.role_keys),
    }


# --------------------------------------------------------------------------- #
# Roles
# --------------------------------------------------------------------------- #


def list_roles(session: Session) -> list[Role]:
    """Return the fixed role catalogue, ordered for stable display."""
    return list(session.scalars(select(Role).order_by(Role.label)))


def _roles_by_keys(session: Session, role_keys: list[str]) -> list[Role]:
    """Resolve role keys, rejecting any the fixed catalogue does not contain."""
    requested = list(dict.fromkeys(role_keys))
    roles = list(session.scalars(select(Role).where(Role.key.in_(requested))))
    found = {role.key for role in roles}
    unknown = [key for key in requested if key not in found]
    if unknown:
        raise ValidationError(f"Unknown role keys: {', '.join(sorted(unknown))}.")
    return roles


def _active_system_admin_ids(session: Session, *, lock: bool) -> set[uuid.UUID]:
    """Ids of active System Administrators.

    ``lock`` takes ``FOR UPDATE`` on the user rows so that two concurrent
    requests cannot each observe the other's administrator and both proceed,
    removing the last one between them.
    """
    statement: Select[tuple[uuid.UUID]] = (
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.key == ROLE_SYSTEM_ADMIN, User.is_active.is_(True))
    )
    if lock:
        statement = statement.with_for_update(of=User)
    return set(session.scalars(statement))


def _guard_last_system_admin(session: Session, user: User, *, keeps_admin: bool) -> None:
    """Refuse a change that would remove the final active System Administrator."""
    admin_ids = _active_system_admin_ids(session, lock=True)
    if user.id not in admin_ids:
        return
    if keeps_admin:
        return
    if len(admin_ids) <= 1:
        raise ConflictError(LAST_ADMIN_DETAIL)


def _set_roles(session: Session, user: User, roles: list[Role]) -> None:
    """Replace a user's role set."""
    session.query(UserRole).filter(UserRole.user_id == user.id).delete(synchronize_session=False)
    for role in roles:
        session.add(UserRole(user_id=user.id, role_id=role.id))
    session.flush()
    session.refresh(user)


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #


def get_user(session: Session, user_id: uuid.UUID) -> User:
    """Return a user or raise :class:`NotFoundError`."""
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return user


def find_by_normalized_email(session: Session, email: str) -> User | None:
    """Return the user owning ``email``, or None."""
    normalized = security.normalize_email(email)
    return session.scalars(select(User).where(User.email_normalized == normalized)).first()


def list_users(
    session: Session,
    *,
    limit: int,
    offset: int,
    is_active: bool | None = None,
    search: str | None = None,
) -> tuple[list[User], int]:
    """Return one bounded page of users and the total matching count."""
    filters = []
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    if search:
        pattern = f"%{search.strip().casefold()}%"
        filters.append(
            func.lower(User.display_name).like(pattern) | User.email_normalized.like(pattern)
        )

    total = session.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    users = list(
        session.scalars(
            select(User).where(*filters).order_by(User.display_name).limit(limit).offset(offset)
        )
    )
    return users, total


def create_user(
    session: Session,
    *,
    email: str,
    display_name: str,
    password: str,
    role_keys: list[str],
    actor_user_id: uuid.UUID | None,
    correlation_id: uuid.UUID,
    source: str = "api",
) -> User:
    """Create a user who must change their password at first login."""
    security.validate_password(password)
    normalized = security.normalize_email(email)
    if not normalized:
        raise ValidationError("Email is required.")
    if find_by_normalized_email(session, normalized) is not None:
        raise ConflictError("A user with this email already exists.")

    roles = _roles_by_keys(session, role_keys)
    user = User(
        email=email.strip(),
        email_normalized=normalized,
        display_name=display_name.strip(),
        password_hash=security.hash_password(password),
        is_active=True,
        must_change_password=True,
        created_by_user_id=actor_user_id,
    )
    session.add(user)
    session.flush()
    _set_roles(session, user, roles)

    record_event(
        session,
        action="user.created",
        entity_type=ENTITY_USER,
        entity_id=user.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        source=source,
        after=user_snapshot(user),
    )
    session.commit()
    session.refresh(user)
    return user


def update_user(
    session: Session,
    *,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    display_name: str | None = None,
    is_active: bool | None = None,
    role_keys: list[str] | None = None,
    reason: str | None = None,
) -> User:
    """Apply an explicit set of mutable fields, auditing before and after."""
    user = get_user(session, user_id)
    before = user_snapshot(user)

    will_be_active = user.is_active if is_active is None else is_active
    keeps_admin = (
        ROLE_SYSTEM_ADMIN in (set(role_keys) if role_keys is not None else user.role_keys)
        and will_be_active
    )
    if (is_active is not None and not is_active) or role_keys is not None:
        _guard_last_system_admin(session, user, keeps_admin=keeps_admin)

    if display_name is not None:
        user.display_name = display_name.strip()
    if role_keys is not None:
        _set_roles(session, user, _roles_by_keys(session, role_keys))
    if is_active is not None and is_active != user.is_active:
        user.is_active = is_active
        if not is_active:
            # A deactivated user must lose access immediately, not at expiry.
            revoke_all_sessions(session, user.id)

    session.flush()
    session.refresh(user)

    record_event(
        session,
        action="user.updated",
        entity_type=ENTITY_USER,
        entity_id=user.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        reason=reason,
        before=before,
        after=user_snapshot(user),
    )
    session.commit()
    session.refresh(user)
    return user


def reset_password(
    session: Session,
    *,
    user_id: uuid.UUID,
    new_password: str,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> User:
    """Set an administrator-issued temporary password and revoke every session."""
    security.validate_password(new_password)
    user = get_user(session, user_id)
    before = user_snapshot(user)

    user.password_hash = security.hash_password(new_password)
    user.must_change_password = True
    revoke_all_sessions(session, user.id)
    session.flush()

    record_event(
        session,
        action="user.password_reset",
        entity_type=ENTITY_USER,
        entity_id=user.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=user_snapshot(user),
    )
    session.commit()
    session.refresh(user)
    return user


def change_own_password(
    session: Session,
    *,
    user: User,
    current_password: str | None,
    new_password: str,
    correlation_id: uuid.UUID,
) -> None:
    """Replace the caller's own password and revoke all of their sessions.

    ``current_password`` may be omitted only while ``must_change_password`` is
    set, which is the administrator-issued temporary password flow: the user has
    already proved possession of that password by logging in with it.
    """
    if not user.must_change_password and (
        not current_password or not security.verify_password(user.password_hash, current_password)
    ):
        raise ValidationError("Current password is incorrect.")

    security.validate_password(new_password)
    before = user_snapshot(user)

    user.password_hash = security.hash_password(new_password)
    user.must_change_password = False
    revoke_all_sessions(session, user.id)
    session.flush()

    record_event(
        session,
        action="user.password_changed",
        entity_type=ENTITY_USER,
        entity_id=user.id,
        correlation_id=correlation_id,
        actor_user_id=user.id,
        before=before,
        after=user_snapshot(user),
    )
    session.commit()


# --------------------------------------------------------------------------- #
# Authentication and sessions
# --------------------------------------------------------------------------- #


def authenticate(session: Session, *, email: str, password: str) -> User | None:
    """Return the matching active user, or None.

    One outcome for every failure — unknown email, wrong password, deactivated
    account — and the same Argon2 work on each path, so neither the response
    body nor its timing reveals whether an account exists.
    """
    user = find_by_normalized_email(session, email)
    if user is None:
        security.verify_dummy_password(password)
        return None
    if not security.verify_password(user.password_hash, password):
        return None
    if not user.is_active:
        return None
    return user


def login(session: Session, *, email: str, password: str) -> tuple[User, str] | None:
    """Authenticate and open a session, or return None on any failure.

    Owns its transaction: the session row and the ``last_login_at`` stamp commit
    together, or neither does.
    """
    user = authenticate(session, email=email, password=password)
    if user is None:
        return None
    raw_token, _ = start_session(session, user=user)
    session.commit()
    session.refresh(user)
    return user, raw_token


def logout(session: Session, raw_token: str) -> None:
    """Revoke the caller's session. Idempotent: logging out twice is not an error."""
    revoke_session(session, raw_token)
    session.commit()


def start_session(session: Session, *, user: User) -> tuple[str, UserSession]:
    """Create a server-side session and return its raw token.

    The raw token is returned once, for the cookie. Only its digest is stored.
    """
    settings = get_settings()
    raw_token = security.generate_session_token()
    now = _now()
    user_session = UserSession(
        user_id=user.id,
        token_hash=security.hash_session_token(raw_token),
        created_at=now,
        expires_at=now + timedelta(minutes=settings.SESSION_TTL_MINUTES),
    )
    session.add(user_session)
    user.last_login_at = now
    session.flush()
    return raw_token, user_session


def resolve_session(session: Session, raw_token: str) -> User | None:
    """Return the authenticated user for a raw token, or None.

    None covers every unusable case: unknown token, revoked, expired, or an
    account that has since been deactivated.
    """
    if not raw_token:
        return None
    token_hash = security.hash_session_token(raw_token)
    user_session = session.scalars(
        select(UserSession).where(UserSession.token_hash == token_hash)
    ).first()
    if user_session is None or user_session.revoked_at is not None:
        return None
    if user_session.expires_at <= _now():
        return None
    user = session.get(User, user_session.user_id)
    if user is None or not user.is_active:
        return None
    return user


def revoke_session(session: Session, raw_token: str) -> bool:
    """Revoke the session identified by ``raw_token``. Idempotent."""
    if not raw_token:
        return False
    token_hash = security.hash_session_token(raw_token)
    user_session = session.scalars(
        select(UserSession).where(UserSession.token_hash == token_hash)
    ).first()
    if user_session is None or user_session.revoked_at is not None:
        return False
    user_session.revoked_at = _now()
    session.flush()
    return True


def revoke_all_sessions(session: Session, user_id: uuid.UUID) -> int:
    """Revoke every live session for a user. Returns the number revoked."""
    now = _now()
    revoked = (
        session.query(UserSession)
        .filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .update({UserSession.revoked_at: now}, synchronize_session=False)
    )
    session.flush()
    return int(revoked)
