"""
Core logging module.

Initializes application logging respecting the configured LOG_LEVEL.
"""

import logging

from app.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger configured with the application log level."""
    return logging.getLogger(name)


logger = get_logger("reach_developments")
