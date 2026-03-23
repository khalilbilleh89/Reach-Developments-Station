"""
Core logging module.

Initializes application logging respecting the configured LOG_LEVEL.

In production (APP_ENV=production) logs are emitted as structured JSON.
In all other environments a human-readable text format is used instead.

A request-correlation filter is attached to the root handler so that
every log record automatically carries the current ``request_id`` from
the async context, enabling end-to-end traceability without threading
the ID through every function call.
"""

import json
import logging
from datetime import datetime, timezone

from app.core.config import settings

_LOG_LEVEL = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

# Derive the set of built-in LogRecord field names dynamically from a sample
# record so the exclusion list stays accurate across Python versions.
_STANDARD_LOG_RECORD_FIELDS: frozenset = frozenset(
    logging.LogRecord(
        name="__probe__",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__.keys()
) | {"message", "asctime"}


class _RequestIdFilter(logging.Filter):
    """Inject the current request correlation ID into every log record.

    Reads from ``app.core.request_id.get_request_id()`` at filter time so
    that all loggers automatically carry the correlation ID without requiring
    callers to pass it explicitly via ``extra=``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Import here to avoid a circular import at module load time.
        from app.core.request_id import get_request_id  # noqa: PLC0415

        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()  # type: ignore[attr-defined]
        return True


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects.

    The ``timestamp`` field is derived from ``record.created`` (the time
    the log record was produced) rather than ``datetime.now()``, ensuring
    the emitted value accurately reflects when the event occurred even when
    handlers queue or buffer records.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include extra fields injected via `extra=` or by filters.
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_FIELDS:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload["exception"] = record.exc_text

        return json.dumps(payload, default=str)


def _configure_logging() -> None:
    """Configure root and application loggers."""
    is_production = (settings.APP_ENV or "").lower() == "production"

    if is_production:
        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )

    request_id_filter = _RequestIdFilter()

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(request_id_filter)

    root = logging.getLogger()
    root.setLevel(_LOG_LEVEL)
    # Avoid adding duplicate handlers when the module is re-imported.
    if not root.handlers:
        root.addHandler(handler)
    else:
        for h in root.handlers:
            h.setFormatter(formatter)
            # Only add the filter once.
            if not any(isinstance(f, _RequestIdFilter) for f in h.filters):
                h.addFilter(request_id_filter)


_configure_logging()


def get_logger(name: str) -> logging.Logger:
    """Return a named logger configured with the application log level.

    Also resets ``disabled=False`` so that external libraries that call
    ``logging.config.fileConfig(disable_existing_loggers=True)`` (e.g.
    Alembic) cannot silence platform loggers.
    """
    lg = logging.getLogger(name)
    lg.setLevel(_LOG_LEVEL)
    lg.disabled = False
    return lg


logger = get_logger("reach_developments")
