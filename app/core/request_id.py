"""
Core request ID utility.

Provides request-scoped correlation IDs that are injected into each
HTTP request by the request logging middleware.  The ID is stored in
a context variable so it can be included in service-level log records
without being threaded through every function call.
"""

import uuid
from contextvars import ContextVar

_REQUEST_ID_CTX_VAR: ContextVar[str] = ContextVar("request_id", default="")


def generate_request_id() -> str:
    """Return a new unique request correlation ID."""
    return f"req-{uuid.uuid4().hex[:8]}"


def set_request_id(request_id: str) -> None:
    """Store *request_id* in the current async context."""
    _REQUEST_ID_CTX_VAR.set(request_id)


def get_request_id() -> str:
    """Return the request ID for the current async context.

    Returns an empty string when called outside of a request context
    (e.g. during startup or background tasks).
    """
    return _REQUEST_ID_CTX_VAR.get()
