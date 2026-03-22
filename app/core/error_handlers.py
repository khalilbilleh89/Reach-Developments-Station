"""
core.error_handlers

FastAPI global exception handlers for the platform error framework.

Registers handlers that translate AppError subclasses into consistent
JSON responses.  All API errors produced by this handler follow the
contract::

    {
        "code": "ERROR_CODE",
        "message": "Human readable description",
        "details": { ... } | null
    }

HTTP status mapping
-------------------
ResourceNotFoundError  → 404
ValidationError        → 422
PermissionDeniedError  → 403
ConflictError          → 409
AppError               → 500
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import (
    AppError,
    ConflictError,
    PermissionDeniedError,
    ResourceNotFoundError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# HTTP status mapping
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[type[AppError], int] = {
    ResourceNotFoundError: 404,
    ValidationError: 422,
    PermissionDeniedError: 403,
    ConflictError: 409,
}


def _status_for(exc: AppError) -> int:
    """Return the HTTP status code for a domain exception.

    Walks the MRO so that future subclasses inherit their parent's mapping
    without requiring an explicit entry in the map.
    """
    for cls in type(exc).__mro__:
        if cls in _STATUS_MAP:
            return _STATUS_MAP[cls]
    return 500


def _error_body(exc: AppError) -> dict:
    return {
        "code": exc.code,
        "message": exc.message,
        "details": exc.details,
    }


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Translate AppError (and subclasses) into a structured JSON response."""
    return JSONResponse(
        status_code=_status_for(exc),
        content=_error_body(exc),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all platform error handlers on the FastAPI application."""
    app.add_exception_handler(AppError, app_error_handler)
