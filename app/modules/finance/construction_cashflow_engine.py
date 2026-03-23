"""
finance.construction_cashflow_engine

Construction Cashflow Forecast Engine for the Financial Control layer.

This module is a pure calculation engine — no SQL, no HTTP, no side effects.
All input data is provided by the service layer; all outputs are plain Python
data objects returned to the service layer for response serialisation.

Forecast model
--------------
For each construction cost record within the date window::

    monthly_cost     = planned_amount / duration_months          (linear spread)
    committed_cost   = committed_amount / duration_months        (linear spread)
    expected_cost    = monthly_cost × execution_probability

Baseline mode (PR-FIN-034 default):

* Costs are spread linearly across the execution window (start_date–end_date).
* Only months that overlap the forecast window receive allocated costs.
* execution_probability scales the planned_cost into expected_cost.
* committed_amount overrides plan when include_committed is True and
  committed_amount > 0.

The engine has no opinion on what "today" is; callers provide the window.

Architecture note
-----------------
All derived construction cashflow values live here.  No formula duplication
in routers or UI components is permitted.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from app.modules.finance.constants import (
    DEFAULT_EXECUTION_PROBABILITY,
    DEFAULT_SPREAD_METHOD,
)


# ---------------------------------------------------------------------------
# Input data transfer objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstructionCostRecord:
    """A single construction cost line consumed by the forecast engine.

    Callers (service layer) are responsible for populating these from DB rows.
    """

    project_id: str
    phase_id: str
    cost_category: str  # e.g. "structural" | "finishing" | "infrastructure"
    planned_amount: float  # planned construction cost (non-negative)
    committed_amount: float  # signed contractor commitments; must be >= 0 (0 if none)
    start_date: date  # execution start
    end_date: date  # execution completion


@dataclass
class ConstructionForecastAssumptions:
    """User-controlled construction forecast parameters.

    Attributes
    ----------
    execution_probability:
        Probability (0–1) that planned construction work will execute as
        scheduled.  1.0 = deterministic full execution.
    cost_spread_method:
        Distribution method for spreading costs across months.
        "linear" distributes costs uniformly; "s_curve" is reserved.
    include_committed:
        When True and committed_amount > 0, committed costs override the
        planned costs for committed line items.
    """

    execution_probability: float = DEFAULT_EXECUTION_PROBABILITY
    cost_spread_method: str = DEFAULT_SPREAD_METHOD
    include_committed: bool = True


# ---------------------------------------------------------------------------
# Output data transfer objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstructionCashflowPeriodResult:
    """Aggregated construction cost metrics for a single calendar-month period."""

    period_label: str  # YYYY-MM

    planned_cost: float  # planned cost allocated to this period
    committed_cost: float  # committed contractor cost allocated to this period
    expected_cost: float  # planned_cost × execution_probability
    variance_to_plan: float  # expected_cost − planned_cost
    cumulative_cost: float  # running cumulative expected_cost up to this period
    cost_item_count: int  # number of cost records contributing to this period


@dataclass(frozen=True)
class ConstructionCashflowSummary:
    """High-level totals across all periods in the forecast window."""

    planned_total: float
    expected_total: float
    variance_to_plan: float  # expected_total − planned_total


@dataclass
class ConstructionCashflowForecastResult:
    """Complete construction cashflow forecast for project or phase scope."""

    scope_type: str  # "project" | "phase"
    scope_id: str  # project_id or phase_id
    start_date: date
    end_date: date
    granularity: str  # "monthly"
    assumptions: ConstructionForecastAssumptions
    summary: ConstructionCashflowSummary
    periods: List[ConstructionCashflowPeriodResult] = field(default_factory=list)


@dataclass
class ConstructionPortfolioForecastResult:
    """Construction cashflow forecast aggregated across multiple projects."""

    scope_type: str  # "portfolio"
    start_date: date
    end_date: date
    granularity: str  # "monthly"
    assumptions: ConstructionForecastAssumptions
    summary: ConstructionCashflowSummary
    periods: List[ConstructionCashflowPeriodResult] = field(default_factory=list)
    project_forecasts: List[ConstructionCashflowForecastResult] = field(default_factory=list)


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


def _generate_monthly_buckets(start: date, end: date) -> List[str]:
    """Return a list of YYYY-MM labels for every month in [start, end]."""
    labels: List[str] = []
    cursor = _month_start(start)
    window_end = _month_end(end)
    while cursor <= window_end:
        labels.append(_month_label(cursor))
        cursor = _advance_month(cursor)
    return labels


def _count_months_in_window(start: date, end: date) -> int:
    """Return the number of calendar months that overlap the [start, end] window."""
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _spread_cost_to_buckets(
    record: ConstructionCostRecord,
    window_labels: List[str],
    assumptions: ConstructionForecastAssumptions,
) -> Dict[str, tuple[float, float]]:
    """Distribute a cost record's planned and committed amounts across bucket labels.

    Returns a mapping of period_label → (planned_per_period, committed_per_period).

    Rules:
    * Only months that fall within both the record's execution window
      (record.start_date – record.end_date) AND the forecast window are included.
    * Linear spread: total amount ÷ total execution months.
    * Partial windows receive the same per-month slice (no pro-ration for
      partial months at the boundary).
    """
    if record.start_date > record.end_date:
        return {}

    record_months = _count_months_in_window(record.start_date, record.end_date)
    if record_months == 0:
        return {}

    planned_per_month = record.planned_amount / record_months
    committed_per_month = (
        record.committed_amount / record_months
        if record.committed_amount > 0
        else 0.0
    )

    # Build set of labels covered by this record's execution window.
    record_labels: List[str] = []
    cursor = _month_start(record.start_date)
    rec_end = _month_end(record.end_date)
    while cursor <= rec_end:
        record_labels.append(_month_label(cursor))
        cursor = _advance_month(cursor)

    record_label_set = set(record_labels)
    forecast_label_set = set(window_labels)
    overlap = record_label_set & forecast_label_set

    result: Dict[str, tuple[float, float]] = {}
    for label in overlap:
        result[label] = (planned_per_month, committed_per_month)
    return result


# ---------------------------------------------------------------------------
# Core engine functions
# ---------------------------------------------------------------------------


def compute_project_construction_cashflow(
    project_id: str,
    cost_records: List[ConstructionCostRecord],
    start_date: date,
    end_date: date,
    assumptions: Optional[ConstructionForecastAssumptions] = None,
) -> ConstructionCashflowForecastResult:
    """Compute the construction cashflow forecast for a single project.

    Parameters
    ----------
    project_id:
        Identifier of the project being forecast.
    cost_records:
        All construction cost records for this project.
    start_date:
        Inclusive start of the forecast window.
    end_date:
        Inclusive end of the forecast window (must be >= start_date).
    assumptions:
        Forecast assumption parameters.  Defaults to deterministic 100%.

    Returns
    -------
    ConstructionCashflowForecastResult
        Full period-by-period and summary construction cashflow forecast.

    Raises
    ------
    ValueError
        If start_date is after end_date.
    """
    if start_date > end_date:
        raise ValueError(
            f"start_date ({start_date}) must not be after end_date ({end_date})"
        )

    if assumptions is None:
        assumptions = ConstructionForecastAssumptions()

    periods, summary = _compute_periods_and_summary(
        cost_records, start_date, end_date, assumptions
    )

    return ConstructionCashflowForecastResult(
        scope_type="project",
        scope_id=project_id,
        start_date=start_date,
        end_date=end_date,
        granularity="monthly",
        assumptions=assumptions,
        summary=summary,
        periods=periods,
    )


def compute_phase_construction_cashflow(
    phase_id: str,
    cost_records: List[ConstructionCostRecord],
    start_date: date,
    end_date: date,
    assumptions: Optional[ConstructionForecastAssumptions] = None,
) -> ConstructionCashflowForecastResult:
    """Compute the construction cashflow forecast for a single phase.

    Parameters
    ----------
    phase_id:
        Identifier of the phase being forecast.
    cost_records:
        All construction cost records for this phase.
    start_date:
        Inclusive start of the forecast window.
    end_date:
        Inclusive end of the forecast window (must be >= start_date).
    assumptions:
        Forecast assumption parameters.  Defaults to deterministic 100%.

    Returns
    -------
    ConstructionCashflowForecastResult
        Full period-by-period and summary construction cashflow forecast.

    Raises
    ------
    ValueError
        If start_date is after end_date.
    """
    if start_date > end_date:
        raise ValueError(
            f"start_date ({start_date}) must not be after end_date ({end_date})"
        )

    if assumptions is None:
        assumptions = ConstructionForecastAssumptions()

    periods, summary = _compute_periods_and_summary(
        cost_records, start_date, end_date, assumptions
    )

    return ConstructionCashflowForecastResult(
        scope_type="phase",
        scope_id=phase_id,
        start_date=start_date,
        end_date=end_date,
        granularity="monthly",
        assumptions=assumptions,
        summary=summary,
        periods=periods,
    )


def compute_portfolio_construction_cashflow(
    project_cost_records: Dict[str, List[ConstructionCostRecord]],
    start_date: date,
    end_date: date,
    assumptions: Optional[ConstructionForecastAssumptions] = None,
) -> ConstructionPortfolioForecastResult:
    """Compute the construction cashflow forecast aggregated across multiple projects.

    Parameters
    ----------
    project_cost_records:
        Mapping of project_id → list of construction cost records.
    start_date:
        Inclusive start of the forecast window.
    end_date:
        Inclusive end of the forecast window (must be >= start_date).
    assumptions:
        Forecast assumption parameters shared across all projects.

    Returns
    -------
    ConstructionPortfolioForecastResult
        Per-project forecasts plus combined portfolio-level totals.

    Raises
    ------
    ValueError
        If start_date is after end_date.
    """
    if start_date > end_date:
        raise ValueError(
            f"start_date ({start_date}) must not be after end_date ({end_date})"
        )

    if assumptions is None:
        assumptions = ConstructionForecastAssumptions()

    window_labels = _generate_monthly_buckets(start_date, end_date)

    # Compute individual project forecasts (sorted for determinism).
    project_forecasts: List[ConstructionCashflowForecastResult] = [
        compute_project_construction_cashflow(pid, records, start_date, end_date, assumptions)
        for pid, records in sorted(project_cost_records.items())
    ]

    # Merge per-project period data into portfolio-level buckets.
    merged_planned: Dict[str, float] = {label: 0.0 for label in window_labels}
    merged_committed: Dict[str, float] = {label: 0.0 for label in window_labels}
    merged_expected: Dict[str, float] = {label: 0.0 for label in window_labels}
    merged_count: Dict[str, int] = {label: 0 for label in window_labels}

    for pf in project_forecasts:
        for period in pf.periods:
            label = period.period_label
            if label in merged_planned:
                merged_planned[label] += period.planned_cost
                merged_committed[label] += period.committed_cost
                merged_expected[label] += period.expected_cost
                merged_count[label] += period.cost_item_count

    # Build portfolio periods with cumulative cost.
    portfolio_periods: List[ConstructionCashflowPeriodResult] = []
    cumulative = 0.0
    for label in window_labels:
        planned = round(merged_planned[label], 2)
        committed = round(merged_committed[label], 2)
        expected = round(merged_expected[label], 2)
        variance = round(expected - planned, 2)
        cumulative = round(cumulative + expected, 2)
        portfolio_periods.append(
            ConstructionCashflowPeriodResult(
                period_label=label,
                planned_cost=planned,
                committed_cost=committed,
                expected_cost=expected,
                variance_to_plan=variance,
                cumulative_cost=cumulative,
                cost_item_count=merged_count[label],
            )
        )

    planned_total = round(sum(p.planned_cost for p in portfolio_periods), 2)
    expected_total = round(sum(p.expected_cost for p in portfolio_periods), 2)
    summary = ConstructionCashflowSummary(
        planned_total=planned_total,
        expected_total=expected_total,
        variance_to_plan=round(expected_total - planned_total, 2),
    )

    return ConstructionPortfolioForecastResult(
        scope_type="portfolio",
        start_date=start_date,
        end_date=end_date,
        granularity="monthly",
        assumptions=assumptions,
        summary=summary,
        periods=portfolio_periods,
        project_forecasts=project_forecasts,
    )


# ---------------------------------------------------------------------------
# Shared period-building helper
# ---------------------------------------------------------------------------


def _compute_periods_and_summary(
    cost_records: List[ConstructionCostRecord],
    start_date: date,
    end_date: date,
    assumptions: ConstructionForecastAssumptions,
) -> tuple[List[ConstructionCashflowPeriodResult], ConstructionCashflowSummary]:
    """Distribute cost records across monthly buckets and derive summary totals.

    Returns
    -------
    tuple[List[ConstructionCashflowPeriodResult], ConstructionCashflowSummary]
    """
    window_labels = _generate_monthly_buckets(start_date, end_date)

    # Accumulate planned and committed per bucket label.
    bucket_planned: Dict[str, float] = {label: 0.0 for label in window_labels}
    bucket_committed: Dict[str, float] = {label: 0.0 for label in window_labels}
    bucket_count: Dict[str, int] = {label: 0 for label in window_labels}

    for record in cost_records:
        spread = _spread_cost_to_buckets(record, window_labels, assumptions)
        for label, (planned_slice, committed_slice) in spread.items():
            bucket_planned[label] += planned_slice
            bucket_committed[label] += committed_slice
            bucket_count[label] += 1

    # Build period results with cumulative cost.
    periods: List[ConstructionCashflowPeriodResult] = []
    cumulative = 0.0

    for label in window_labels:
        planned = round(bucket_planned[label], 2)
        committed = round(bucket_committed[label], 2)

        # When include_committed is True and committed_cost > 0, use committed
        # as the basis for expected_cost; otherwise use planned.
        if assumptions.include_committed and committed > 0:
            base_cost = committed
        else:
            base_cost = planned

        expected = round(base_cost * assumptions.execution_probability, 2)
        variance = round(expected - planned, 2)
        cumulative = round(cumulative + expected, 2)

        periods.append(
            ConstructionCashflowPeriodResult(
                period_label=label,
                planned_cost=planned,
                committed_cost=committed,
                expected_cost=expected,
                variance_to_plan=variance,
                cumulative_cost=cumulative,
                cost_item_count=bucket_count[label],
            )
        )

    planned_total = round(sum(p.planned_cost for p in periods), 2)
    expected_total = round(sum(p.expected_cost for p in periods), 2)
    summary = ConstructionCashflowSummary(
        planned_total=planned_total,
        expected_total=expected_total,
        variance_to_plan=round(expected_total - planned_total, 2),
    )

    return periods, summary
