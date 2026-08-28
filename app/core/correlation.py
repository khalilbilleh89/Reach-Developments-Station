"""Per-request correlation identity.

Every request is given a server-generated UUID, returned as ``X-Correlation-ID``
and recorded on the audit events the request produces. That is what makes an
audit row answer "through which request did this happen".

Deliberately small: a request-state key, a header name and one middleware. Not
a context framework.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"

#: Attribute name used on ``request.state``.
_STATE_ATTRIBUTE = "correlation_id"


async def correlation_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach a fresh correlation id to the request and echo it on the response.

    The identifier is always generated here and never taken from an inbound
    header: a client-supplied value could be forged or repeated, which would
    corrupt the audit trail it feeds.
    """
    correlation_id = uuid.uuid4()
    setattr(request.state, _STATE_ATTRIBUTE, correlation_id)
    response = await call_next(request)
    response.headers[CORRELATION_HEADER] = str(correlation_id)
    return response


def get_correlation_id(request: Request) -> uuid.UUID:
    """Return this request's correlation id.

    Falls back to a fresh value if the middleware did not run, so that a caller
    can never write an audit row without one.
    """
    existing = getattr(request.state, _STATE_ATTRIBUTE, None)
    if isinstance(existing, uuid.UUID):
        return existing
    return uuid.uuid4()
