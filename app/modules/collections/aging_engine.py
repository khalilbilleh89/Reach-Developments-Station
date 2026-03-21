"""
Aging analysis engine.

Calculates aging buckets for outstanding receivables:
  Current, 1-30 days, 31-60 days, 61-90 days, 90+ days

Rules:
  - Installments with due_date >= reference_date are CURRENT (not yet due).
  - days_overdue is calculated as (reference_date - due_date).days for past-due
    installments.
  - No database access occurs here; all inputs are passed by the caller.
"""

from datetime import date
from typing import Literal

AgingBucket = Literal["current", "1-30", "31-60", "61-90", "90+"]

BUCKET_CURRENT: AgingBucket = "current"
BUCKET_1_30: AgingBucket = "1-30"
BUCKET_31_60: AgingBucket = "31-60"
BUCKET_61_90: AgingBucket = "61-90"
BUCKET_90_PLUS: AgingBucket = "90+"

ALL_BUCKETS: list[AgingBucket] = [
    BUCKET_CURRENT,
    BUCKET_1_30,
    BUCKET_31_60,
    BUCKET_61_90,
    BUCKET_90_PLUS,
]


def calculate_receivable_age(due_date: date, reference_date: date) -> int:
    """Return the number of days an installment is overdue.

    Parameters
    ----------
    due_date:
        The date the installment payment was due.
    reference_date:
        The date against which aging is measured (typically today).

    Returns
    -------
    int
        Positive integer means the installment is overdue by that many days.
        Zero or negative means the installment is not yet due (CURRENT).
    """
    return (reference_date - due_date).days


def classify_receivable_bucket(days_overdue: int) -> AgingBucket:
    """Map a days-overdue count to an aging bucket label.

    Parameters
    ----------
    days_overdue:
        Output of :func:`calculate_receivable_age`.  Values <= 0 indicate
        installments that are not yet past due.

    Returns
    -------
    AgingBucket
        One of: ``"current"``, ``"1-30"``, ``"31-60"``, ``"61-90"``, ``"90+"``.
    """
    if days_overdue <= 0:
        return BUCKET_CURRENT
    if days_overdue <= 30:
        return BUCKET_1_30
    if days_overdue <= 60:
        return BUCKET_31_60
    if days_overdue <= 90:
        return BUCKET_61_90
    return BUCKET_90_PLUS
