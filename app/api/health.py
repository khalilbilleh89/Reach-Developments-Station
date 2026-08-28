"""Health probes.

Two endpoints with deliberately different contracts:

* ``/health/live``  — is this process alive? Never touches the database.
* ``/health/ready`` — are this process's runtime dependencies usable? For
  MVP 1.0 the only dependency is PostgreSQL.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import check_database_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

#: Returned verbatim when a readiness dependency is down. Deliberately free of
#: host names, credentials, connection strings and exception text.
_NOT_READY_DETAIL = "Service dependencies are not ready."


class LivenessResponse(BaseModel):
    """Public contract of ``GET /health/live``."""

    status: Literal["ok"]
    service: str


class ReadinessResponse(BaseModel):
    """Public contract of ``GET /health/ready``."""

    status: Literal["ok"]
    service: str
    database: Literal["ok"]


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description="Confirms the application process is running. Does not require a database.",
)
def read_liveness() -> LivenessResponse:
    """Report that the process is up."""
    return LivenessResponse(status="ok", service=get_settings().APP_NAME)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description="Confirms PostgreSQL is reachable via a minimal SELECT 1 probe.",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": (
                "A required runtime dependency is unavailable. The response body is a "
                "generic message; connection details are written to the server log only."
            )
        }
    },
)
def read_readiness() -> ReadinessResponse:
    """Report readiness after probing PostgreSQL."""
    try:
        check_database_connection()
    except SQLAlchemyError:
        # Full diagnostics stay server-side; the client gets nothing exploitable.
        logger.exception("Readiness probe failed: PostgreSQL is unreachable.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_NOT_READY_DETAIL,
        ) from None

    return ReadinessResponse(status="ok", service=get_settings().APP_NAME, database="ok")
