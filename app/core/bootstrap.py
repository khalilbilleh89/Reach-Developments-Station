"""
Core bootstrap module.

Provides idempotent startup initialization logic.  Currently handles seeding
the initial administrator user so that a fresh deployment is immediately
accessible without manual intervention.
"""

from sqlalchemy.exc import IntegrityError
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
    * If a user with ``ADMIN_EMAIL`` already exists, the function ensures the
      ``admin`` role exists and is assigned — without modifying email or password.
    * If no user exists yet, a new active user is created with the hashed
      password and the ``admin`` role is assigned.

    The function is resilient to partial prior executions and concurrent
    multi-worker startups: each step is individually protected with an
    ``IntegrityError`` catch + rollback-and-re-fetch, so duplicate creation
    races degrade gracefully rather than crashing.
    """
    email = settings.ADMIN_EMAIL
    password = settings.ADMIN_PASSWORD

    if not email or not password:
        logger.debug("Bootstrap: ADMIN_EMAIL / ADMIN_PASSWORD not set — skipping admin seed.")
        return

    repo = AuthRepository(db)

    # ------------------------------------------------------------------
    # Step 1: Ensure the admin user exists.
    # ------------------------------------------------------------------
    user = repo.get_user_by_email(email)
    if user is None:
        try:
            user = repo.create_user(email=email, password_hash=hash_password(password))
            logger.info("Bootstrap: admin user '%s' created.", email)
        except IntegrityError:
            # Another worker created the user concurrently — roll back the
            # failed transaction and re-fetch the now-existing user.
            db.rollback()
            user = repo.get_user_by_email(email)
            if user is None:
                raise
            logger.info("Bootstrap: admin user '%s' already exists (concurrent startup).", email)
    else:
        logger.info("Bootstrap: admin user '%s' already exists — ensuring role assignment.", email)

    # ------------------------------------------------------------------
    # Step 2: Ensure the 'admin' role exists.
    # ------------------------------------------------------------------
    role = repo.get_role_by_name("admin")
    if role is None:
        try:
            role = repo.create_role("admin", "System administrator")
        except IntegrityError:
            # Another worker created the role concurrently.
            db.rollback()
            role = repo.get_role_by_name("admin")
            if role is None:
                raise

    # ------------------------------------------------------------------
    # Step 3: Ensure the role is assigned (assign_role is already idempotent).
    # ------------------------------------------------------------------
    repo.assign_role(user.id, role.id)
    logger.info("Bootstrap: admin role confirmed for '%s'.", email)
