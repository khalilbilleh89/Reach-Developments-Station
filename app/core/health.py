"""
app.core.health

Central health-check logic for platform observability.

Provides service liveness and readiness state with structured metadata.
Health endpoints belong to platform infrastructure and must not access
domain services or trigger business logic.
"""

from datetime import datetime, timezone


_SERVICE_NAME = "reach_developments"


def get_liveness() -> dict:
    """Return service liveness state.

    Liveness indicates that the application process is alive and running.
    This check never fails — if the process can respond, it is alive.
    """
    return {
        "status": "alive",
        "service": _SERVICE_NAME,
        "timestamp": _utc_now(),
    }


def get_health() -> dict:
    """Return basic service health metadata."""
    return {
        "status": "ok",
        "service": _SERVICE_NAME,
        "timestamp": _utc_now(),
    }


def get_readiness(database_connected: bool) -> dict:
    """Return service readiness state.

    Readiness indicates that the application is ready to accept requests.
    Readiness requires the database to be reachable.

    Args:
        database_connected: Whether the database connection was successful.

    Returns:
        Readiness payload with database and service metadata.
    """
    if database_connected:
        return {
            "status": "ready",
            "database": "connected",
            "service": _SERVICE_NAME,
            "timestamp": _utc_now(),
        }
    return {
        "status": "unavailable",
        "database": "unreachable",
        "service": _SERVICE_NAME,
        "timestamp": _utc_now(),
    }


def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
