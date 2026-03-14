"""
Core bootstrap module.

Provides idempotent startup initialization logic.  Currently handles seeding
the initial administrator user so that a fresh deployment is immediately
accessible without manual intervention.
"""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.modules.auth.repository import AuthRepository
from app.modules.auth.security import hash_password


def seed_admin_user(db: Session) -> None:
    """Create the initial administrator user if required.

    This function is safe to call on every application startup:

    * If ``ADMIN_EMAIL`` or ``ADMIN_PASSWORD`` is not configured, the function
      exits immediately without touching the database.
    * If a user with ``ADMIN_EMAIL`` already exists, the function exits
      without making any changes (idempotent).
    * Otherwise a new active user is created and the ``admin`` role is
      assigned to it.
    """
    email = settings.ADMIN_EMAIL
    password = settings.ADMIN_PASSWORD

    if not email or not password:
        logger.debug("Bootstrap: ADMIN_EMAIL / ADMIN_PASSWORD not set — skipping admin seed.")
        return

    repo = AuthRepository(db)

    if repo.get_user_by_email(email):
        logger.info("Bootstrap: admin user '%s' already exists — skipping.", email)
        return

    password_hash = hash_password(password)
    user = repo.create_user(email=email, password_hash=password_hash)

    # Assign the admin role so the seeded account has elevated privileges.
    role = repo.get_role_by_name("admin")
    if role is None:
        role = repo.create_role("admin", "System administrator")
    repo.assign_role(user.id, role.id)

    logger.info("Bootstrap: admin user '%s' created successfully.", email)
