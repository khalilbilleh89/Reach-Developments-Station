"""
app.core.db_health

Database connectivity verification for platform readiness checks.

Performs a lightweight ping to confirm that the database session is available.
This module must not trigger domain logic or access application data.
"""

from app.core.database import check_db_connection


def is_database_reachable() -> bool:
    """Return True if the database is reachable, False otherwise.

    Delegates to the existing engine-level connectivity check which executes
    a minimal ``SELECT 1`` statement and returns without side effects.
    """
    return check_db_connection()
