"""
Tests for app/core/bootstrap.py — seed_admin_user.

Validates that the bootstrap function creates an admin user when credentials
are configured, is idempotent on repeated calls, skips when credentials are
absent, assigns the admin role, and repairs missing role assignments on
existing users.
"""

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.bootstrap import seed_admin_user
from app.modules.auth.models import User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.security import hash_password, verify_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_settings(email: str | None, password: str | None):
    """Return a context manager that patches ADMIN_EMAIL and ADMIN_PASSWORD."""
    return patch(
        "app.core.bootstrap.settings",
        ADMIN_EMAIL=email,
        ADMIN_PASSWORD=password,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_seed_admin_creates_user(db_session: Session):
    """Admin user is created when ADMIN_EMAIL and ADMIN_PASSWORD are set."""
    with _patch_settings("admin@example.com", "SecurePassword123"):
        seed_admin_user(db_session)

    repo = AuthRepository(db_session)
    user = repo.get_user_by_email("admin@example.com")
    assert user is not None
    assert user.is_active is True
    assert verify_password("SecurePassword123", user.password_hash)


def test_seed_admin_assigns_admin_role(db_session: Session):
    """The seeded user is assigned the 'admin' role."""
    with _patch_settings("admin@example.com", "SecurePassword123"):
        seed_admin_user(db_session)

    repo = AuthRepository(db_session)
    user = repo.get_user_by_email("admin@example.com")
    assert user is not None
    roles = repo.get_user_roles(user.id)
    role_names = [r.name for r in roles]
    assert "admin" in role_names


def test_seed_admin_idempotent(db_session: Session):
    """Calling seed_admin_user twice must not create duplicate users."""
    with _patch_settings("admin@example.com", "SecurePassword123"):
        seed_admin_user(db_session)
        seed_admin_user(db_session)

    users = (
        db_session.query(User)
        .filter_by(email="admin@example.com")
        .all()
    )
    assert len(users) == 1


def test_seed_admin_skips_when_email_missing(db_session: Session):
    """No user is created when ADMIN_EMAIL is not set."""
    with _patch_settings(None, "SecurePassword123"):
        seed_admin_user(db_session)

    count = db_session.query(User).count()
    assert count == 0


def test_seed_admin_skips_when_password_missing(db_session: Session):
    """No user is created when ADMIN_PASSWORD is not set."""
    with _patch_settings("admin@example.com", None):
        seed_admin_user(db_session)

    repo = AuthRepository(db_session)
    user = repo.get_user_by_email("admin@example.com")
    assert user is None


def test_seed_admin_skips_when_both_missing(db_session: Session):
    """No user is created when neither ADMIN_EMAIL nor ADMIN_PASSWORD is set."""
    with _patch_settings(None, None):
        seed_admin_user(db_session)

    count = db_session.query(User).count()
    assert count == 0


def test_seed_admin_does_not_overwrite_existing_user(db_session: Session):
    """Existing user with ADMIN_EMAIL is not modified on bootstrap."""
    # Pre-create the user with a different password
    repo = AuthRepository(db_session)
    repo.create_user(email="admin@example.com", password_hash=hash_password("OriginalPass1"))

    with _patch_settings("admin@example.com", "DifferentPass2"):
        seed_admin_user(db_session)

    user = repo.get_user_by_email("admin@example.com")
    assert user is not None
    # Password must still match the original, not the bootstrap value
    assert verify_password("OriginalPass1", user.password_hash)
    assert not verify_password("DifferentPass2", user.password_hash)


def test_seed_admin_repairs_missing_role_on_existing_user(db_session: Session):
    """Bootstrap assigns admin role to an existing user who lacks it."""
    repo = AuthRepository(db_session)
    # Create user without assigning any role (simulates partial prior startup)
    repo.create_user(email="admin@example.com", password_hash=hash_password("Pass123!"))

    # Confirm no roles yet
    user = repo.get_user_by_email("admin@example.com")
    assert repo.get_user_roles(user.id) == []

    with _patch_settings("admin@example.com", "Pass123!"):
        seed_admin_user(db_session)

    # Admin role must now be assigned
    roles = repo.get_user_roles(user.id)
    assert "admin" in [r.name for r in roles]


def test_seed_admin_role_already_assigned_remains_idempotent(db_session: Session):
    """Bootstrap does not duplicate the admin role if it is already assigned."""
    with _patch_settings("admin@example.com", "SecurePassword123"):
        seed_admin_user(db_session)
        seed_admin_user(db_session)

    repo = AuthRepository(db_session)
    user = repo.get_user_by_email("admin@example.com")
    roles = repo.get_user_roles(user.id)
    assert [r.name for r in roles].count("admin") == 1


def test_seed_admin_existing_admin_role_not_duplicated(db_session: Session):
    """Bootstrap reuses an existing 'admin' role rather than creating a second one."""
    repo = AuthRepository(db_session)
    # Pre-create the admin role
    existing_role = repo.create_role("admin", "Pre-existing admin role")

    with _patch_settings("admin@example.com", "SecurePassword123"):
        seed_admin_user(db_session)

    # Still exactly one admin role
    from app.modules.auth.models import Role
    role_count = db_session.query(Role).filter_by(name="admin").count()
    assert role_count == 1
    # And it's the same role (id unchanged)
    user = repo.get_user_by_email("admin@example.com")
    assigned_roles = repo.get_user_roles(user.id)
    assert any(r.id == existing_role.id for r in assigned_roles)
