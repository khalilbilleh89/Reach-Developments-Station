"""
Request logging middleware.

Assigns a correlation ID to every inbound HTTP request and emits a
structured log record after the application has generated the response,
including:

    - request_id  — unique correlation ID for the request
    - method      — HTTP method (GET, POST, …)
    - path        — request path
    - status      — HTTP response status code
    - duration_ms — elapsed time in milliseconds to generate the response

Unhandled exceptions are caught, logged at ERROR level with status 500,
and then re-raised so that registered error handlers can still process
the response.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.logging import get_logger
from app.core.request_id import generate_request_id, set_request_id

_logger = get_logger("reach_developments.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with its correlation ID and duration."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = generate_request_id()
        set_request_id(request_id)

        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.monotonic() - start) * 1000)
            log_context = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "duration_ms": duration_ms,
            }
            _logger.error(
                "%(method)s %(path)s → %(status)s (%(duration_ms)sms)",
                log_context,
                extra=log_context,
            )
            raise

        duration_ms = round((time.monotonic() - start) * 1000)
        log_context = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        }

        _logger.info(
            "%(method)s %(path)s → %(status)s (%(duration_ms)sms)",
            log_context,
            extra=log_context,
        )

        response.headers["X-Request-ID"] = request_id
        return response
