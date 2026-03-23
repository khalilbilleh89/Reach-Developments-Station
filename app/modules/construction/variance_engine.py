"""
construction.variance_engine

Pure Construction Schedule Variance Engine.

Computes schedule variance by comparing planned CPM schedule against actual
milestone progress.  No database access, no HTTP concerns.

Concepts
--------
schedule_variance_days
    actual_start_day − planned_start (earliest_start from CPM).
    Positive = late start.  Negative = early start.

completion_variance_days
    actual_finish_day − planned_finish (earliest_finish from CPM).
    Only meaningful when actual_finish_day is set.
    Positive = late finish.  Negative = early finish.

VarianceMilestoneStatus
    NOT_STARTED  — no actual_start_day and progress_percent is None/0
    IN_PROGRESS  — actual_start_day set and progress < 100
    DELAYED      — actual_start_day > planned_start (slipped)
    AHEAD        — actual_start_day < planned_start (early)
    COMPLETED    — progress_percent == 100 (or actual_finish_day set)

Delay propagation
    If a delayed milestone lies on the critical path, all downstream
    milestones that also appear on the critical path are flagged
    risk_exposed = True.

All inputs/outputs use plain Python dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class VarianceMilestoneStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DELAYED = "delayed"
    AHEAD = "ahead"
    COMPLETED = "completed"


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MilestoneProgress:
    """Actual execution progress for a single milestone.

    Parameters
    ----------
    milestone_id:
        Matches ConstructionMilestone.id.
    planned_start:
        Earliest Start day from CPM (ScheduleResult.earliest_start).
    planned_finish:
        Earliest Finish day from CPM (ScheduleResult.earliest_finish).
    is_critical:
        Whether this milestone lies on the CPM critical path.
    actual_start_day:
        Day the milestone actually started, relative to project day 0.
        None if not yet started.
    actual_finish_day:
        Day the milestone actually finished.  None if not yet finished.
    progress_percent:
        Percentage complete (0–100).  None treated as 0.
    """

    milestone_id: str
    planned_start: int
    planned_finish: int
    is_critical: bool
    actual_start_day: Optional[int] = None
    actual_finish_day: Optional[int] = None
    progress_percent: Optional[float] = None


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MilestoneVarianceResult:
    """Variance result for a single milestone.

    Parameters
    ----------
    milestone_id:
        Matches input MilestoneProgress.milestone_id.
    planned_start:
        CPM earliest start day.
    planned_finish:
        CPM earliest finish day.
    actual_start_day:
        As supplied in input; None if not started.
    actual_finish_day:
        As supplied in input; None if not finished.
    progress_percent:
        As supplied in input (0–100); None treated as 0 for status logic.
    schedule_variance_days:
        actual_start_day − planned_start.
        None if actual_start_day is not set.
    completion_variance_days:
        actual_finish_day − planned_finish.
        None if actual_finish_day is not set.
    milestone_status:
        Derived execution state.
    is_critical:
        Whether the milestone is on the critical path.
    risk_exposed:
        True if a delayed predecessor on the critical path may affect
        this milestone's ability to start on time.
    """

    milestone_id: str
    planned_start: int
    planned_finish: int
    actual_start_day: Optional[int]
    actual_finish_day: Optional[int]
    progress_percent: Optional[float]
    schedule_variance_days: Optional[int]
    completion_variance_days: Optional[int]
    milestone_status: VarianceMilestoneStatus
    is_critical: bool
    risk_exposed: bool = False


@dataclass
class ScopeVarianceResult:
    """Aggregated variance result for an entire construction scope.

    Parameters
    ----------
    scope_id:
        ID of the construction scope.
    project_delay_days:
        Maximum schedule slippage on the critical path (0 if none).
    critical_path_shift:
        Whether the critical path has been displaced by actual delays.
    affected_milestones:
        IDs of critical-path milestones that are delayed or risk-exposed.
    milestones:
        Per-milestone variance results.
    """

    scope_id: str
    project_delay_days: int
    critical_path_shift: bool
    affected_milestones: List[str] = field(default_factory=list)
    milestones: List[MilestoneVarianceResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------


def _derive_status(mp: MilestoneProgress) -> VarianceMilestoneStatus:
    """Derive the execution status for a single milestone."""
    pct = mp.progress_percent or 0.0

    # Completed: either 100% or actual_finish_day is set
    if pct >= 100.0 or mp.actual_finish_day is not None:
        return VarianceMilestoneStatus.COMPLETED

    # Not started
    if mp.actual_start_day is None:
        return VarianceMilestoneStatus.NOT_STARTED

    # Started: check whether it is delayed vs ahead vs on time
    if mp.actual_start_day > mp.planned_start:
        return VarianceMilestoneStatus.DELAYED

    if mp.actual_start_day < mp.planned_start:
        return VarianceMilestoneStatus.AHEAD

    return VarianceMilestoneStatus.IN_PROGRESS


# ---------------------------------------------------------------------------
# Main engine entry point
# ---------------------------------------------------------------------------


def compute_variance(
    scope_id: str,
    milestones: List[MilestoneProgress],
    critical_path: List[str],
) -> ScopeVarianceResult:
    """Compute schedule variance for a construction scope.

    Parameters
    ----------
    scope_id:
        ID of the construction scope (passed through to the result).
    milestones:
        List of :class:`MilestoneProgress` objects built from DB milestone
        records merged with CPM schedule results.
    critical_path:
        Ordered list of milestone IDs on the critical path (from CPM output).

    Returns
    -------
    ScopeVarianceResult
        Per-milestone variance rows plus project-level delay summary.
    """
    if not milestones:
        return ScopeVarianceResult(
            scope_id=scope_id,
            project_delay_days=0,
            critical_path_shift=False,
            affected_milestones=[],
            milestones=[],
        )

    # Build ordered critical-path position map for delay propagation
    cp_index: Dict[str, int] = {mid: i for i, mid in enumerate(critical_path)}

    # ── Per-milestone variance ────────────────────────────────────────────────
    results: List[MilestoneVarianceResult] = []
    # Track worst delay on critical path (used for project_delay_days)
    max_critical_delay = 0
    # Track which critical milestones are delayed (for propagation)
    delayed_critical_indices: List[int] = []

    for mp in milestones:
        schedule_variance: Optional[int] = None
        if mp.actual_start_day is not None:
            schedule_variance = mp.actual_start_day - mp.planned_start

        completion_variance: Optional[int] = None
        if mp.actual_finish_day is not None:
            completion_variance = mp.actual_finish_day - mp.planned_finish

        derived_status = _derive_status(mp)

        # Accumulate critical-path delay
        if mp.is_critical and schedule_variance is not None and schedule_variance > 0:
            max_critical_delay = max(max_critical_delay, schedule_variance)
            if mp.milestone_id in cp_index:
                delayed_critical_indices.append(cp_index[mp.milestone_id])

        results.append(
            MilestoneVarianceResult(
                milestone_id=mp.milestone_id,
                planned_start=mp.planned_start,
                planned_finish=mp.planned_finish,
                actual_start_day=mp.actual_start_day,
                actual_finish_day=mp.actual_finish_day,
                progress_percent=mp.progress_percent,
                schedule_variance_days=schedule_variance,
                completion_variance_days=completion_variance,
                milestone_status=derived_status,
                is_critical=mp.is_critical,
                risk_exposed=False,
            )
        )

    # ── Delay propagation ─────────────────────────────────────────────────────
    # Any critical-path milestone whose position index is AFTER a delayed
    # critical-path milestone is considered risk-exposed.
    affected_milestone_ids: List[str] = []

    if delayed_critical_indices:
        min_delayed_cp_index = min(delayed_critical_indices)
        result_map: Dict[str, MilestoneVarianceResult] = {r.milestone_id: r for r in results}

        for mid in critical_path:
            if mid not in cp_index:
                continue
            pos = cp_index[mid]
            if pos > min_delayed_cp_index:
                mvr = result_map.get(mid)
                if mvr is not None and mvr.milestone_status != VarianceMilestoneStatus.COMPLETED:
                    mvr.risk_exposed = True
                    if mid not in affected_milestone_ids:
                        affected_milestone_ids.append(mid)

        # Also include the delayed milestones themselves as affected
        for idx in delayed_critical_indices:
            mid = critical_path[idx]
            if mid not in affected_milestone_ids:
                affected_milestone_ids.insert(0, mid)

    return ScopeVarianceResult(
        scope_id=scope_id,
        project_delay_days=max_critical_delay,
        critical_path_shift=max_critical_delay > 0,
        affected_milestones=affected_milestone_ids,
        milestones=results,
    )
