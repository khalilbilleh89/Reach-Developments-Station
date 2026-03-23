"""
finance.cashflow_engine

Centralized cash flow projection engine for the Financial Control layer.

This module is a pure calculation engine — no SQL, no HTTP, no side effects.
All input data is provided by the service layer; all outputs are plain Python
data objects returned to the service layer for response serialisation.

Forecast model
--------------
For each installment within the date window::

    remaining_unpaid  = max(scheduled_amount − collected_amount, 0)
    expected_amount   = remaining_unpaid × collection_probability

Baseline deterministic mode (PR-33 default):

* future PENDING/OVERDUE installments → collection_probability = 1.0
* PAID installments contribute only to collected_amount (not expected)
* CANCELLED installments are excluded entirely
* Overdue installments due *before* the window start are optionally carried
  forward into the first period bucket

The engine has no opinion on what "today" is; callers provide the window.

Architecture note
-----------------
All derived cashflow values live here.  No formula duplication in routers
or UI components is permitted.  Scenario logic (PR-34) will wrap this
engine; it must not be embedded here.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from app.modules.finance.constants import (
    DEFAULT_CARRY_FORWARD_OVERDUE,
    DEFAULT_COLLECTION_PROBABILITY,
)


# ---------------------------------------------------------------------------
# Input data transfer objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstallmentRecord:
    """A single installment row consumed by the forecast engine.

    Callers (service layer) are responsible for populating these from DB rows.
    CANCELLED installments must not be passed to the engine.
    """

    contract_id: str
    project_id: str
    due_date: date
    scheduled_amount: float  # contractual obligation amount
    collected_amount: float  # amount already settled (0 if not PAID)
    status: str  # "paid" | "pending" | "overdue"


@dataclass
class ForecastAssumptions:
    """User-controlled forecast parameters.

    Attributes
    ----------
    collection_probability:
        Fraction of outstanding balance expected to be collected (0–1).
        1.0 = deterministic 100% collection assumption.
    carry_forward_overdue:
        When True, installments with due_date < window start that are still
        outstanding are placed in the first period bucket.
    include_paid_in_schedule:
        When True, already-paid installments are counted toward scheduled
        and collected period totals so that scheduled_amount represents the
        full contractual amount regardless of payment state.
    """

    collection_probability: float = DEFAULT_COLLECTION_PROBABILITY
    carry_forward_overdue: bool = DEFAULT_CARRY_FORWARD_OVERDUE
    include_paid_in_schedule: bool = True


# ---------------------------------------------------------------------------
# Output data transfer objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CashflowPeriodResult:
    """Aggregated cashflow metrics for a single calendar-month period."""

    period_start: date
    period_end: date
    period_label: str  # YYYY-MM

    scheduled_amount: float  # contractual due amount in this period
    collected_amount: float  # amount already paid for installments in this period
    expected_amount: float  # expected future collections (outstanding × probability)
    variance_to_schedule: float  # expected_amount − scheduled_amount
    cumulative_expected_amount: float  # running total of expected_amount up to this period

    installment_count: int  # number of installments falling in this period


@dataclass(frozen=True)
class CashflowForecastSummary:
    """High-level totals across all periods in the forecast window."""

    scheduled_total: float
    collected_total: float
    expected_total: float
    variance_to_schedule: float  # expected_total − scheduled_total


@dataclass
class CashflowForecastResult:
    """Complete cashflow forecast for a single scope (contract / project / portfolio)."""

    scope_type: str  # "contract" | "project" | "portfolio"
    scope_id: str  # contract_id, project_id, or "portfolio"
    start_date: date
    end_date: date
    granularity: str  # "monthly"
    assumptions: ForecastAssumptions
    summary: CashflowForecastSummary
    periods: List[CashflowPeriodResult] = field(default_factory=list)


@dataclass
class PortfolioCashflowResult:
    """Cashflow forecast aggregated across multiple projects."""

    scope_type: str  # "portfolio"
    scope_id: str  # "portfolio"
    start_date: date
    end_date: date
    granularity: str  # "monthly"
    assumptions: ForecastAssumptions
    summary: CashflowForecastSummary
    periods: List[CashflowPeriodResult] = field(default_factory=list)
    project_forecasts: List[CashflowForecastResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _month_start(d: date) -> date:
    """Return the first day of the month containing *d*."""
    return date(d.year, d.month, 1)


def _month_end(d: date) -> date:
    """Return the last day of the month containing *d*."""
    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last)


def _month_label(d: date) -> str:
    """Return YYYY-MM label for the month containing *d*."""
    return f"{d.year:04d}-{d.month:02d}"


def _advance_month(d: date) -> date:
    """Return the first day of the month following *d*'s month."""
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _generate_monthly_buckets(start: date, end: date) -> List[tuple[date, date]]:
    """Return a list of (period_start, period_end) tuples for every month in [start, end].

    The first bucket starts on the first day of start's month.
    The last bucket ends on the last day of end's month.
    """
    buckets: List[tuple[date, date]] = []
    cursor = _month_start(start)
    window_end = _month_end(end)
    while cursor <= window_end:
        buckets.append((cursor, _month_end(cursor)))
        cursor = _advance_month(cursor)
    return buckets


def _bucket_label(period_start: date) -> str:
    return _month_label(period_start)


# ---------------------------------------------------------------------------
# Core engine functions
# ---------------------------------------------------------------------------


def _assign_installments_to_buckets(
    installments: List[InstallmentRecord],
    buckets: List[tuple[date, date]],
    assumptions: ForecastAssumptions,
) -> Dict[str, List[InstallmentRecord]]:
    """Assign each installment to a bucket label.

    Rules:
    * PAID installments are assigned to the bucket matching their due_date.
      They contribute to scheduled_amount and collected_amount.
    * PENDING/OVERDUE installments within the window are assigned normally.
    * If assumptions.carry_forward_overdue is True, OVERDUE installments
      whose due_date falls *before* the first bucket start are carried into
      the first bucket.
    * Installments with due_date after the last bucket end are excluded
      (outside the window).
    """
    if not buckets:
        return {}

    first_start = buckets[0][0]
    last_end = buckets[-1][1]

    # Build label → (start, end) lookup for O(1) lookup during assignment.
    label_lookup: Dict[str, tuple[date, date]] = {
        _bucket_label(s): (s, e) for s, e in buckets
    }
    first_label = _bucket_label(first_start)

    assigned: Dict[str, List[InstallmentRecord]] = {
        _bucket_label(s): [] for s, _ in buckets
    }

    for inst in installments:
        is_paid = inst.status == "paid"

        # Skip paid installments if caller does not want them in schedule.
        if is_paid and not assumptions.include_paid_in_schedule:
            continue

        due = inst.due_date

        if due < first_start:
            # Pre-window installment.
            if not is_paid and assumptions.carry_forward_overdue:
                assigned[first_label].append(inst)
            # Paid pre-window installments are outside the forecast window —
            # they are excluded to avoid double-counting collected amounts.
        elif due > last_end:
            # Post-window installment — exclude.
            pass
        else:
            # Normal assignment: find the bucket containing due_date.
            label = _month_label(due)
            if label in label_lookup:
                assigned[label].append(inst)

    return assigned


def compute_contract_forecast(
    contract_id: str,
    installments: List[InstallmentRecord],
    start_date: date,
    end_date: date,
    assumptions: Optional[ForecastAssumptions] = None,
) -> CashflowForecastResult:
    """Compute the cashflow forecast for a single contract.

    Parameters
    ----------
    contract_id:
        Identifier of the contract being forecast.
    installments:
        All non-cancelled installment records for this contract.
        PAID, PENDING, and OVERDUE are all accepted.
    start_date:
        Inclusive start of the forecast window.
    end_date:
        Inclusive end of the forecast window (must be >= start_date).
    assumptions:
        Forecast assumption parameters.  Defaults to deterministic 100%.

    Returns
    -------
    CashflowForecastResult
        Full period-by-period and summary forecast.
    """
    if assumptions is None:
        assumptions = ForecastAssumptions()

    buckets = _generate_monthly_buckets(start_date, end_date)
    assigned = _assign_installments_to_buckets(installments, buckets, assumptions)
    periods = _build_periods(buckets, assigned, assumptions)
    summary = _build_summary(periods)

    return CashflowForecastResult(
        scope_type="contract",
        scope_id=contract_id,
        start_date=start_date,
        end_date=end_date,
        granularity="monthly",
        assumptions=assumptions,
        summary=summary,
        periods=periods,
    )


def compute_project_forecast(
    project_id: str,
    installments: List[InstallmentRecord],
    start_date: date,
    end_date: date,
    assumptions: Optional[ForecastAssumptions] = None,
) -> CashflowForecastResult:
    """Compute the cashflow forecast for a single project.

    Parameters
    ----------
    project_id:
        Identifier of the project being forecast.
    installments:
        All non-cancelled installment records for contracts under this project.
    start_date:
        Inclusive start of the forecast window.
    end_date:
        Inclusive end of the forecast window.
    assumptions:
        Forecast assumption parameters.

    Returns
    -------
    CashflowForecastResult
        Full period-by-period and summary forecast for the project.
    """
    if assumptions is None:
        assumptions = ForecastAssumptions()

    buckets = _generate_monthly_buckets(start_date, end_date)
    assigned = _assign_installments_to_buckets(installments, buckets, assumptions)
    periods = _build_periods(buckets, assigned, assumptions)
    summary = _build_summary(periods)

    return CashflowForecastResult(
        scope_type="project",
        scope_id=project_id,
        start_date=start_date,
        end_date=end_date,
        granularity="monthly",
        assumptions=assumptions,
        summary=summary,
        periods=periods,
    )


def compute_portfolio_forecast(
    project_installments: Dict[str, List[InstallmentRecord]],
    start_date: date,
    end_date: date,
    assumptions: Optional[ForecastAssumptions] = None,
) -> PortfolioCashflowResult:
    """Compute the cashflow forecast aggregated across multiple projects.

    Parameters
    ----------
    project_installments:
        Mapping of project_id → list of non-cancelled installment records.
    start_date:
        Inclusive start of the forecast window.
    end_date:
        Inclusive end of the forecast window.
    assumptions:
        Forecast assumption parameters shared across all projects.

    Returns
    -------
    PortfolioCashflowResult
        Per-project forecasts plus combined portfolio-level totals.
    """
    if assumptions is None:
        assumptions = ForecastAssumptions()

    buckets = _generate_monthly_buckets(start_date, end_date)

    # Compute individual project forecasts (sorted for determinism).
    project_forecasts: List[CashflowForecastResult] = [
        compute_project_forecast(pid, lines, start_date, end_date, assumptions)
        for pid, lines in sorted(project_installments.items())
    ]

    # Merge per-project period data into portfolio-level buckets.
    merged: Dict[str, Dict[str, float]] = {
        _bucket_label(s): {
            "scheduled": 0.0,
            "collected": 0.0,
            "expected": 0.0,
            "count": 0,
        }
        for s, _ in buckets
    }

    for pf in project_forecasts:
        for period in pf.periods:
            label = period.period_label
            if label in merged:
                merged[label]["scheduled"] += period.scheduled_amount
                merged[label]["collected"] += period.collected_amount
                merged[label]["expected"] += period.expected_amount
                merged[label]["count"] += period.installment_count

    portfolio_periods = _build_merged_periods(buckets, merged)
    summary = _build_summary(portfolio_periods)

    return PortfolioCashflowResult(
        scope_type="portfolio",
        scope_id="portfolio",
        start_date=start_date,
        end_date=end_date,
        granularity="monthly",
        assumptions=assumptions,
        summary=summary,
        periods=portfolio_periods,
        project_forecasts=project_forecasts,
    )


# ---------------------------------------------------------------------------
# Period-building helpers (shared by contract, project, portfolio paths)
# ---------------------------------------------------------------------------


def _build_periods(
    buckets: List[tuple[date, date]],
    assigned: Dict[str, List[InstallmentRecord]],
    assumptions: ForecastAssumptions,
) -> List[CashflowPeriodResult]:
    """Convert bucket→installment assignments into CashflowPeriodResult rows.

    Cumulative expected amount is computed over the sorted bucket sequence.
    """
    cumulative = 0.0
    periods: List[CashflowPeriodResult] = []

    for period_start, period_end in buckets:
        label = _bucket_label(period_start)
        lines = assigned.get(label, [])

        scheduled = 0.0
        collected = 0.0

        for inst in lines:
            scheduled += inst.scheduled_amount
            collected += inst.collected_amount

        remaining_unpaid = max(round(scheduled - collected, 2), 0.0)
        expected = round(remaining_unpaid * assumptions.collection_probability, 2)
        variance = round(expected - scheduled, 2)
        cumulative = round(cumulative + expected, 2)

        periods.append(
            CashflowPeriodResult(
                period_start=period_start,
                period_end=period_end,
                period_label=label,
                scheduled_amount=round(scheduled, 2),
                collected_amount=round(collected, 2),
                expected_amount=expected,
                variance_to_schedule=variance,
                cumulative_expected_amount=cumulative,
                installment_count=len(lines),
            )
        )

    return periods


def _build_merged_periods(
    buckets: List[tuple[date, date]],
    merged: Dict[str, Dict[str, float]],
) -> List[CashflowPeriodResult]:
    """Build portfolio-level CashflowPeriodResult rows from pre-merged bucket data."""
    cumulative = 0.0
    periods: List[CashflowPeriodResult] = []

    for period_start, period_end in buckets:
        label = _bucket_label(period_start)
        data = merged.get(label, {"scheduled": 0.0, "collected": 0.0, "expected": 0.0, "count": 0})

        scheduled = round(data["scheduled"], 2)
        collected = round(data["collected"], 2)
        expected = round(data["expected"], 2)
        variance = round(expected - scheduled, 2)
        cumulative = round(cumulative + expected, 2)

        periods.append(
            CashflowPeriodResult(
                period_start=period_start,
                period_end=period_end,
                period_label=label,
                scheduled_amount=scheduled,
                collected_amount=collected,
                expected_amount=expected,
                variance_to_schedule=variance,
                cumulative_expected_amount=cumulative,
                installment_count=int(data["count"]),
            )
        )

    return periods


def _build_summary(periods: List[CashflowPeriodResult]) -> CashflowForecastSummary:
    """Derive summary totals from a list of period results."""
    scheduled_total = round(sum(p.scheduled_amount for p in periods), 2)
    collected_total = round(sum(p.collected_amount for p in periods), 2)
    expected_total = round(sum(p.expected_amount for p in periods), 2)
    variance = round(expected_total - scheduled_total, 2)

    return CashflowForecastSummary(
        scheduled_total=scheduled_total,
        collected_total=collected_total,
        expected_total=expected_total,
        variance_to_schedule=variance,
    )
