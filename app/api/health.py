"""
app.api.health

Health and diagnostics HTTP endpoints.

Exposes safe operational signals for infrastructure monitoring and
deployment verification. These endpoints do not require authentication
and must not expose sensitive information.

Endpoints:
    GET /health          — basic service health with timestamp
    GET /health/live     — liveness: confirms the process is running
    GET /health/ready    — readiness: confirms DB connectivity
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.db_health import is_database_reachable
from app.core.health import get_health, get_liveness, get_readiness

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> JSONResponse:
    """Return basic service health with timestamp."""
    return JSONResponse(get_health())


@router.get("/health/live")
def health_live() -> JSONResponse:
    """Liveness check — confirms the application process is running."""
    return JSONResponse(get_liveness())


@router.get("/health/ready")
def health_ready() -> JSONResponse:
    """Readiness check — confirms the application can serve requests.

    Returns HTTP 200 when the database is reachable.
    Returns HTTP 503 when the database is unavailable.
    """
    db_ok = is_database_reachable()
    payload = get_readiness(db_ok)
    status_code = 200 if db_ok else 503
    return JSONResponse(payload, status_code=status_code)
