"""Service-layer error types.

Services raise these; :mod:`app.main` maps them to HTTP status codes in one
place. That keeps HTTP concerns out of domain logic without scattering an
identical ``try``/``except`` through every route handler.

Every message here reaches a client, so none of them may carry internals.
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for errors a client is entitled to see."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class AuthenticationError(ServiceError):
    """The caller is not authenticated. Maps to 401."""


class PermissionDeniedError(ServiceError):
    """The caller is authenticated but not allowed. Maps to 403."""


class NotFoundError(ServiceError):
    """The addressed resource does not exist. Maps to 404."""


class ConflictError(ServiceError):
    """The request conflicts with current state or a business rule. Maps to 409."""


class ValidationError(ServiceError):
    """The request is well-formed but semantically invalid. Maps to 422."""
