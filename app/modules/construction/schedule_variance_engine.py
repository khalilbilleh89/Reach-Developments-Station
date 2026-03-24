"""
construction.schedule_variance_engine

Pure Schedule Variance Analytics Engine.

Computes contractor-level schedule deviation metrics from milestone
completion data.  No database access, no HTTP concerns.

Metrics produced
----------------
assessed_milestones
    Milestones with both ``completion_date`` and ``target_date`` set.
    Only these contribute to variance calculations.
delayed_milestones
    Milestones where delay_days > 0
    (i.e. completion_date > target_date).
total_delay_days
    Sum of delay_days across all delayed milestones.
average_delay_days
    Mean delay_days across delayed milestones.
    None if no delayed milestones.
median_delay_days
    Median delay_days across delayed milestones.
    None if no delayed milestones.
max_delay_days
    Maximum single-milestone delay in days.
    None if no delayed milestones.
delay_rate
    delayed_milestones / assessed_milestones.
    None if assessed_milestones == 0.

Delay definition
----------------
delay_days = (completion_date - target_date).days

    delay_days > 0   → delayed milestone
    delay_days <= 0  → on-time or early milestone

Only milestones that have **both** fields set are assessed.
Milestones missing either date are excluded from variance calculations.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

logger = logging.getLogger("construction_schedule_variance_engine")

# ---------------------------------------------------------------------------
# Input dataclass
# ---------------------------------------------------------------------------


@dataclass
class MilestoneVarianceInput:
    """Variance-relevant data for a single milestone.

    Parameters
    ----------
    milestone_id:
        Matches ConstructionMilestone.id.
    completion_date:
        Calendar date when the milestone was completed.
        None if the milestone has not been completed or the date is not set.
    target_date:
        Planned completion date for the milestone.
        None if not set.
    """

    milestone_id: str
    completion_date: Optional[date] = None
    target_date: Optional[date] = None


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class ScheduleVarianceResult:
    """Computed schedule variance metrics for a set of milestones.

    Parameters
    ----------
    assessed_milestones:
        Count of milestones with both ``completion_date`` and ``target_date``
        set.  Only these are used in calculations.
    delayed_milestones:
        Count of assessed milestones where completion_date > target_date.
    total_delay_days:
        Sum of delay_days across all delayed milestones.
    average_delay_days:
        Mean delay_days across delayed milestones.  None if no delayed
        milestones.
    median_delay_days:
        Median delay_days across delayed milestones.  None if no delayed
        milestones.
    max_delay_days:
        Maximum single-milestone delay in days.  None if no delayed
        milestones.
    delay_rate:
        delayed_milestones / assessed_milestones.  None if
        assessed_milestones == 0.
    """

    assessed_milestones: int = 0
    delayed_milestones: int = 0
    total_delay_days: int = 0
    average_delay_days: Optional[float] = None
    median_delay_days: Optional[float] = None
    max_delay_days: Optional[int] = None
    delay_rate: Optional[float] = None


# ---------------------------------------------------------------------------
# Engine entry point
# ---------------------------------------------------------------------------


def compute_schedule_variance(
    milestones: List[MilestoneVarianceInput],
) -> ScheduleVarianceResult:
    """Compute schedule variance metrics from a list of milestone inputs.

    Parameters
    ----------
    milestones:
        Milestone inputs to analyse.  Milestones with either
        ``completion_date`` or ``target_date`` absent are excluded from all
        calculations.

    Returns
    -------
    ScheduleVarianceResult
        Computed variance metrics.

        - If there are no milestones with both dates present (no assessed
          milestones), all delay-related fields in the result are ``None``.
        - If there are assessed milestones and at least one is delayed,
          delay metrics are populated according to the observed delays.
        - If there are assessed milestones but none are delayed, then
          ``delayed_milestones`` is ``0``, ``total_delay_days`` is ``0``,
          ``delay_rate`` is ``0.0``, and the average/median/max delay
          metrics remain ``None``.
    """
    if not milestones:
        return ScheduleVarianceResult()

    delay_days_list: List[int] = []

    for m in milestones:
        if m.completion_date is None or m.target_date is None:
            logger.debug(
                "Milestone '%s' excluded from variance: missing date(s).",
                m.milestone_id,
            )
            continue

        delay = (m.completion_date - m.target_date).days
        if delay > 0:
            delay_days_list.append(delay)

    assessed = sum(
        1
        for m in milestones
        if m.completion_date is not None and m.target_date is not None
    )

    if assessed == 0:
        return ScheduleVarianceResult()

    delayed = len(delay_days_list)
    total_delay = sum(delay_days_list)

    average_delay: Optional[float] = None
    median_delay: Optional[float] = None
    max_delay: Optional[int] = None
    delay_rate: Optional[float] = delayed / assessed

    if delayed > 0:
        average_delay = round(total_delay / delayed, 2)
        median_delay = round(statistics.median(delay_days_list), 2)
        max_delay = max(delay_days_list)

    return ScheduleVarianceResult(
        assessed_milestones=assessed,
        delayed_milestones=delayed,
        total_delay_days=total_delay,
        average_delay_days=average_delay,
        median_delay_days=median_delay,
        max_delay_days=max_delay,
        delay_rate=delay_rate,
    )
