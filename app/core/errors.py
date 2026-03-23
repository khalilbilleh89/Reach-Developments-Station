"""
core.errors

Platform-wide domain exception hierarchy.

Modules raise domain exceptions; HTTP translation happens centrally in
error_handlers.py so service code stays transport-layer agnostic.

All errors produced by this hierarchy serialise to the standard API
error contract::

    {
        "code": "ERROR_CODE",
        "message": "Human readable description",
        "details": { ... } | null
    }
"""

from typing import Any, Optional

from app.core.constants.error_codes import (
    CONFLICT,
    INTERNAL_ERROR,
    PERMISSION_DENIED,
    RESOURCE_NOT_FOUND,
    VALIDATION_ERROR,
)


class AppError(Exception):
    """Base class for all platform domain errors."""

    code: str = INTERNAL_ERROR
    message: str = "An unexpected application error occurred."

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.message = message if message is not None else self.__class__.message
        self.details = details
        super().__init__(self.message)


class ResourceNotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    code = RESOURCE_NOT_FOUND
    message = "Requested resource was not found."


class ValidationError(AppError):
    """Raised when domain validation rules are violated."""

    code = VALIDATION_ERROR
    message = "Invalid input."


class PermissionDeniedError(AppError):
    """Raised when the caller does not have permission to perform the operation."""

    code = PERMISSION_DENIED
    message = "Permission denied."


class ConflictError(AppError):
    """Raised when an operation would violate a uniqueness or state constraint."""

    code = CONFLICT
    message = "Resource conflict."
