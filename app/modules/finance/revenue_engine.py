"""
finance.revenue_engine

Core revenue recognition calculation engine.

The engine is a pure function module — no database access, no side-effects.
All data flows in via :class:`~app.modules.finance.revenue_models.RevenueScheduleInput`
and the result is a :class:`~app.modules.finance.revenue_models.RevenueScheduleResult`.

Supported strategies
--------------------
ON_CONTRACT_SIGNING
    Each contract's total is allocated to the calendar month its
    contract_date falls in.

ON_UNIT_DELIVERY
    Each contract's total is allocated to the calendar month its
    delivery_date falls in.  Contracts without a delivery_date are
    allocated to the last period present in the schedule, or to
    the current month when the schedule is otherwise empty.

ON_CONSTRUCTION_PROGRESS
    Each contract's total is distributed across periods in proportion to
    the incremental construction completion percentage supplied per
    period.  When no milestone data is available for a contract the
    engine falls back to ON_CONTRACT_SIGNING behaviour for that unit.
"""

from collections import defaultdict
from datetime import date
from typing import Dict

from app.modules.finance.revenue_models import (
    RecognitionStrategy,
    RevenueScheduleEntry,
    RevenueScheduleInput,
    RevenueScheduleResult,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_revenue_schedule(inputs: RevenueScheduleInput) -> RevenueScheduleResult:
    """Generate a chronological revenue schedule for the supplied inputs.

    Dispatches to the appropriate strategy implementation and returns a
    fully populated :class:`RevenueScheduleResult`.

    Parameters
    ----------
    inputs:
        Immutable value object carrying the scenario identifier, the list of
        unit sales, and the recognition strategy to apply.

    Returns
    -------
    RevenueScheduleResult
        Chronologically ordered revenue schedule with per-period totals and
        an overall total.
    """
    strategy = inputs.strategy

    if strategy == RecognitionStrategy.ON_CONTRACT_SIGNING:
        buckets = _schedule_on_signing(inputs)
    elif strategy == RecognitionStrategy.ON_UNIT_DELIVERY:
        buckets = _schedule_on_delivery(inputs)
    elif strategy == RecognitionStrategy.ON_CONSTRUCTION_PROGRESS:
        buckets = _schedule_on_construction_progress(inputs)
    else:
        # Defensive fallback — treat unknown strategies as signing-date.
        buckets = _schedule_on_signing(inputs)

    revenue_schedule = _buckets_to_schedule(buckets)
    total_revenue = round(sum(e.revenue for e in revenue_schedule), 2)

    return RevenueScheduleResult(
        scenario_id=inputs.scenario_id,
        strategy=strategy.value,
        revenue_schedule=revenue_schedule,
        total_revenue=total_revenue,
    )


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------


def _period_from_date(d: date) -> str:
    """Return the ``YYYY-MM`` string for the given date."""
    return f"{d.year:04d}-{d.month:02d}"


def _schedule_on_signing(inputs: RevenueScheduleInput) -> Dict[str, float]:
    """Allocate each contract's full value to its contract_date period."""
    buckets: Dict[str, float] = defaultdict(float)
    for sale in inputs.unit_sales:
        period = _period_from_date(sale.contract_date)
        buckets[period] += sale.contract_total
    return buckets


def _schedule_on_delivery(inputs: RevenueScheduleInput) -> Dict[str, float]:
    """Allocate each contract's full value to its delivery_date period.

    Contracts without a delivery_date fall back to the contract_date period
    so that revenue is never silently dropped.
    """
    buckets: Dict[str, float] = defaultdict(float)
    for sale in inputs.unit_sales:
        recognition_date = sale.delivery_date if sale.delivery_date else sale.contract_date
        period = _period_from_date(recognition_date)
        buckets[period] += sale.contract_total
    return buckets


def _schedule_on_construction_progress(
    inputs: RevenueScheduleInput,
) -> Dict[str, float]:
    """Distribute each contract's value across periods via milestone percentages.

    For each unit sale:
    - If ``construction_completion_by_period`` is populated, the incremental
      completion delta for each period is multiplied by ``contract_total`` to
      arrive at the revenue to recognize in that period.
    - If no milestone data is supplied the contract falls back to
      ON_CONTRACT_SIGNING allocation.

    The milestones dictionary maps ``YYYY-MM`` period keys to *cumulative*
    completion percentages (0–100).  The engine derives incremental deltas
    internally so that callers do not need to pre-compute them.
    """
    buckets: Dict[str, float] = defaultdict(float)

    for sale in inputs.unit_sales:
        milestones = sale.construction_completion_by_period

        if not milestones:
            # No milestone data — fall back to signing date.
            period = _period_from_date(sale.contract_date)
            buckets[period] += sale.contract_total
            continue

        # Sort periods chronologically and derive incremental deltas.
        sorted_periods = sorted(milestones.keys())
        previous_pct = 0.0
        allocated = 0.0

        for i, period in enumerate(sorted_periods):
            cumulative_pct = float(milestones[period])
            incremental_pct = max(cumulative_pct - previous_pct, 0.0)
            previous_pct = cumulative_pct

            if i < len(sorted_periods) - 1:
                period_revenue = round(
                    sale.contract_total * incremental_pct / 100.0, 2
                )
            else:
                # Last milestone: allocate the remainder to avoid rounding drift.
                period_revenue = round(sale.contract_total - allocated, 2)

            buckets[period] += period_revenue
            allocated += period_revenue

    return buckets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _buckets_to_schedule(buckets: Dict[str, float]) -> list:
    """Convert period → amount mapping to a sorted list of RevenueScheduleEntry."""
    return [
        RevenueScheduleEntry(period=period, revenue=round(amount, 2))
        for period, amount in sorted(buckets.items())
    ]
