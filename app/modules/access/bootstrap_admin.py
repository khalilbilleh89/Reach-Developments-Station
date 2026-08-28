"""Create the first System Administrator.

Run once, by hand, after the database has been migrated::

    python -m app.modules.access.bootstrap_admin

Deliberately a CLI and not a startup hook. Creating an administrator is a
privileged, one-off act: it must be a decision someone takes, not a hidden write
that runs on every boot, and it must not require a standing password in the
environment.

The password is read with :func:`getpass.getpass`, so it never appears in shell
history, in a process listing or in this program's output.
"""

from __future__ import annotations

import getpass
import sys
import uuid

from sqlalchemy import inspect, select

from app.core.database import get_session_factory
from app.core.errors import ServiceError
from app.modules.access import service
from app.modules.access.models import ROLE_SYSTEM_ADMIN, Role, User, UserRole
from app.modules.access.security import MIN_PASSWORD_LENGTH
from app.modules.audit.models import AUDIT_SOURCE_BOOTSTRAP

_REQUIRED_TABLES = ("users", "roles", "user_roles")


class BootstrapError(RuntimeError):
    """The environment is not in a state where bootstrap can safely proceed."""


def _check_schema_ready(session: object) -> None:
    inspector = inspect(session.bind)  # type: ignore[attr-defined]
    existing = set(inspector.get_table_names())
    missing = [table for table in _REQUIRED_TABLES if table not in existing]
    if missing:
        raise BootstrapError(
            "Database schema is not ready. Run `alembic upgrade head` first "
            f"(missing: {', '.join(missing)})."
        )


def _check_no_existing_admin(session) -> None:  # noqa: ANN001 - Session, kept import-light
    """Refuse to run twice.

    A second bootstrap would silently mint another privileged account outside
    the audited administration flow. Once an administrator exists, further users
    are created through the API by that administrator.
    """
    existing = session.scalars(
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.key == ROLE_SYSTEM_ADMIN, User.is_active.is_(True))
    ).first()
    if existing is not None:
        raise BootstrapError(
            "An active System Administrator already exists. "
            "Create further users through the administration API."
        )


def _prompt_password() -> str:
    """Read and confirm a password without echoing it."""
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise BootstrapError("Passwords do not match.")
    return password


def bootstrap(email: str, display_name: str, password: str) -> uuid.UUID:
    """Create the first administrator and return the new user id.

    Runs as one transaction: the user, the role assignment and the audit event
    all commit together or not at all.
    """
    session = get_session_factory()()
    try:
        _check_schema_ready(session)
        _check_no_existing_admin(session)
        user = service.create_user(
            session,
            email=email,
            display_name=display_name,
            password=password,
            role_keys=[ROLE_SYSTEM_ADMIN],
            actor_user_id=None,
            correlation_id=uuid.uuid4(),
            source=AUDIT_SOURCE_BOOTSTRAP,
        )
        return user.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> int:
    """Interactive entry point. Returns a process exit code."""
    print("Reach Developments Station — create the first System Administrator.")
    print(f"The password is not echoed and must be at least {MIN_PASSWORD_LENGTH} characters.\n")

    try:
        email = input("Email: ").strip()
        display_name = input("Display name: ").strip()
        if not email or not display_name:
            raise BootstrapError("Email and display name are both required.")
        password = _prompt_password()
        user_id = bootstrap(email, display_name, password)
    except (BootstrapError, ServiceError) as exc:
        # Never echo the password or hash — only why it stopped.
        print(f"\nBootstrap failed: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nBootstrap cancelled.", file=sys.stderr)
        return 130

    print(f"\nCreated System Administrator {email} (id {user_id}).")
    print("Sign in through the application; you will be asked to set a new password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
