"""
Core logging module.

Initializes application logging respecting the configured LOG_LEVEL.

In production (APP_ENV=production) logs are emitted as structured JSON.
In all other environments a human-readable text format is used instead.
"""

import json
import logging
from datetime import datetime, timezone

from app.core.config import settings

_LOG_LEVEL = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include extra fields injected via `extra=` in logger calls.
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }:
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

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(_LOG_LEVEL)
    # Avoid adding duplicate handlers when the module is re-imported.
    if not root.handlers:
        root.addHandler(handler)
    else:
        for h in root.handlers:
            h.setFormatter(formatter)


_configure_logging()


def get_logger(name: str) -> logging.Logger:
    """Return a named logger configured with the application log level."""
    lg = logging.getLogger(name)
    lg.setLevel(_LOG_LEVEL)
    return lg


logger = get_logger("reach_developments")
