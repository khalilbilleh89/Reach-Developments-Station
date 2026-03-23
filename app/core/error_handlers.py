"""
core.error_handlers

FastAPI global exception handlers for the platform error framework.

Registers handlers that translate domain errors, FastAPI HTTP exceptions,
and request-validation errors into consistent JSON responses.  All API
errors produced by these handlers follow the contract::

    {
        "code": "ERROR_CODE",
        "message": "Human readable description",
        "details": { ... } | null
    }

HTTP status mapping (domain errors)
------------------------------------
ResourceNotFoundError  → 404
ValidationError        → 422
PermissionDeniedError  → 403
ConflictError          → 409
AppError               → 500

Framework errors
----------------
HTTPException          → original status_code  (code: "HTTP_<status>")
RequestValidationError → 422                   (code: "VALIDATION_ERROR")
"""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.constants.error_codes import INTERNAL_ERROR, VALIDATION_ERROR
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


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Translate AppError (and subclasses) into a structured JSON response."""
    return JSONResponse(
        status_code=_status_for(exc),
        content=jsonable_encoder(_error_body(exc)),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Normalize FastAPI/Starlette HTTPException into the platform envelope.

    The ``code`` field is derived from the HTTP status so clients always
    receive the same three-key structure regardless of error origin.
    """
    detail = exc.detail
    if isinstance(detail, str):
        message = detail
        details = None
    else:
        message = "HTTP error: see details."
        details = jsonable_encoder(detail) if detail is not None else None
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": f"HTTP_{exc.status_code}",
            "message": message,
            "details": details,
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Normalize Pydantic/FastAPI request-validation errors into the envelope.

    ``details.validation_errors`` carries the full per-field error list so
    clients can surface field-level messages without parsing a non-standard
    structure.
    """
    return JSONResponse(
        status_code=422,
        content={
            "code": VALIDATION_ERROR,
            "message": "Request validation failed.",
            "details": {
                "validation_errors": jsonable_encoder(exc.errors()),
            },
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all platform error handlers on the FastAPI application."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
