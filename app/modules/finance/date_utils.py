"""
finance.date_utils

Shared date helpers for the finance module.

This module provides utility functions that are reused across multiple
finance services (e.g. portfolio summary, treasury monitoring).  Keeping
them here avoids cross-module imports of private helpers.
"""

from __future__ import annotations

from datetime import date


def next_month_key() -> str:
    """Return the YYYY-MM key for the calendar month after today."""
    today = date.today()
    if today.month == 12:
        return f"{today.year + 1:04d}-01"
    return f"{today.year:04d}-{today.month + 1:02d}"
