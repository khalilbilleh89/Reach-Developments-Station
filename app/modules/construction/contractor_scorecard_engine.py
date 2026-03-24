"""
construction.contractor_scorecard_engine

Pure Contractor Scorecard & Trend Analytics Engine.

Derives deterministic KPIs and ranking outputs for construction contractors
from execution source data (milestones, packages, risk alerts).
No database access, no HTTP concerns.

Scorecard metrics produced per contractor
-----------------------------------------
total_milestones
    Unique milestones linked via all contractor packages.
completed_milestones
    Milestones with status ``completed``.
delayed_milestones
    Milestones with status ``delayed``.
on_time_milestones
    Completed milestones where completion_date <= target_date (both set).
over_budget_milestones
    Milestones where actual_cost > planned_cost (both fields set).
assessed_cost_milestones
    Milestones where both planned_cost and actual_cost are present.
delayed_ratio
    delayed_milestones / total_milestones.  None if total == 0.
on_time_rate
    on_time_milestones / completed_milestones.  None if completed == 0.
overrun_ratio
    over_budget_milestones / assessed_cost_milestones.  None if no costed.
avg_cost_variance_percent
    Mean (actual_cost - planned_cost) / planned_cost * 100 across assessed.
    None if no costed milestones.
active_packages
    Packages in tendering / evaluation / awarded status.
completed_packages
    Packages with status ``completed``.
risk_signal_count
    Caller-supplied count of HIGH-severity contractor ratio alerts
    (delay ratio and overrun ratio alerts) from the risk alert engine.

Scores (all 0–100, higher is better)
--------------------------------------
schedule_score
    Derived from delayed_ratio.  100 when delay_ratio == 0.
cost_score
    Derived from overrun_ratio and avg_cost_variance_percent.
risk_score
    Derived from risk_signal_count (10 points deducted per alert, floor 0).
performance_score
    Weighted composite: 40 % schedule + 40 % cost + 20 % risk.

Ranking
-------
contractor_rank
    Position within scope, 1 = best performance_score.
    Ties broken deterministically by contractor_id (ascending).

Trend
-----
Trend is computed by grouping milestones with a completion_date by
calendar month (YYYY-MM) and computing per-period scorecard metrics.
Periods with no completed/delayed milestones are excluded from the trend.
A trend_direction is derived from the last two periods:
    improving     — performance_score increased ≥ TREND_MIN_DELTA
    deteriorating — performance_score decreased ≥ TREND_MIN_DELTA
    stable        — change is below the delta threshold or only one period
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Scoring weights and thresholds
# ---------------------------------------------------------------------------

SCHEDULE_WEIGHT: float = 0.40
COST_WEIGHT: float = 0.40
RISK_WEIGHT: float = 0.20

# Points deducted per high-severity alert (floor: 0)
ALERT_PENALTY_POINTS: float = 10.0

# Minimum absolute performance_score change to be called improving/deteriorating
TREND_MIN_DELTA: float = 5.0

# Package statuses that count as active
_ACTIVE_PACKAGE_STATUSES = {"tendering", "evaluation", "awarded"}

# Completed milestone status
_COMPLETED_STATUS = "completed"
_DELAYED_STATUS = "delayed"


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MilestoneScorecardData:
    """Scorecard-relevant data for a single milestone.

    Parameters
    ----------
    milestone_id:
        Matches ConstructionMilestone.id.
    status:
        MilestoneStatus value string (e.g. "completed", "delayed").
    planned_cost:
        Budgeted cost for the milestone.  None if not set.
    actual_cost:
        Actual recorded cost.  None if not recorded.
    completion_date:
        Calendar date when the milestone was completed.  Used for trend
        period grouping and on-time rate calculation.  None if not completed
        or not set.
    target_date:
        Planned completion date for the milestone.  Used to determine whether
        a completed milestone was delivered on time
        (completion_date <= target_date).  None if not set.
    """

    milestone_id: str
    status: str
    planned_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None
    completion_date: Optional[date] = None
    target_date: Optional[date] = None


@dataclass
class PackageScorecardData:
    """Scorecard-relevant data for a single procurement package.

    Parameters
    ----------
    package_id:
        Matches ConstructionProcurementPackage.id.
    status:
        ProcurementPackageStatus value string.
    planned_value:
        Budgeted value for the package.  None if not set.
    awarded_value:
        Awarded/actual value for the package.  None if not recorded.
    """

    package_id: str
    status: str
    planned_value: Optional[Decimal] = None
    awarded_value: Optional[Decimal] = None


@dataclass
class ContractorScorecardInput:
    """All data needed to compute a scorecard for a single contractor.

    Parameters
    ----------
    contractor_id:
        Matches ConstructionContractor.id.
    contractor_name:
        Human-readable contractor name.
    milestones:
        All milestones from all packages assigned to this contractor.
        Duplicates (same milestone_id) are deduplicated by the engine.
    packages:
        All procurement packages assigned to this contractor.
    risk_signal_count:
        Count of HIGH-severity contractor ratio alerts (delay ratio and
        overrun ratio alerts) from the risk alert engine.
    """

    contractor_id: str
    contractor_name: str
    milestones: List[MilestoneScorecardData] = field(default_factory=list)
    packages: List[PackageScorecardData] = field(default_factory=list)
    risk_signal_count: int = 0


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ContractorScorecard:
    """Derived scorecard for a single contractor.

    Parameters
    ----------
    contractor_id:
        Matches ConstructionContractor.id.
    contractor_name:
        Human-readable contractor name.
    total_milestones:
        Unique milestone count across all linked packages.
    completed_milestones:
        Count with status ``completed``.
    delayed_milestones:
        Count with status ``delayed``.
    over_budget_milestones:
        Count where actual_cost > planned_cost (both set).
    assessed_cost_milestones:
        Count where both planned_cost and actual_cost are set.
    delayed_ratio:
        delayed / total.  None when total == 0.
    on_time_milestones:
        Count of completed milestones where completion_date <= target_date
        (both fields must be set).
    on_time_rate:
        on_time_milestones / completed_milestones.  None when completed == 0.
    overrun_ratio:
        over_budget / assessed.  None when assessed == 0.
    avg_cost_variance_percent:
        Mean percentage cost overrun across assessed milestones.  None if
        no assessed milestones or planned_cost == 0 for all.
    active_packages:
        Packages in tendering / evaluation / awarded status.
    completed_packages:
        Packages with status ``completed``.
    risk_signal_count:
        Count of HIGH-severity contractor ratio alerts (caller-supplied).
    schedule_score:
        Score 0–100 derived from delay_ratio.
    cost_score:
        Score 0–100 derived from overrun_ratio and avg cost variance.
    risk_score:
        Score 0–100 derived from risk_signal_count.
    performance_score:
        Weighted composite score 0–100.
    average_delay_days:
        Mean delay in days across delayed milestones (completion_date >
        target_date).  None if no milestones were delayed or no milestones
        have both dates set.
    median_delay_days:
        Median delay in days across delayed milestones.  None if no delayed
        milestones.
    max_delay_days:
        Maximum single-milestone delay in days.  None if no delayed
        milestones.
    delay_rate:
        delayed_milestones / assessed_milestones where ``assessed`` means
        the milestone has both completion_date and target_date set.  None
        if no assessed milestones.
    total_cost_variance:
        Sum of (actual_cost − planned_cost) across assessed packages.
        None if no assessed packages.
    average_cost_variance_pct:
        Mean percentage cost variance across assessed packages.
        None if no assessed packages with non-zero planned value.
    max_cost_overrun_pct:
        Highest single-package overrun percentage.  None if no package
        is over budget.
    cost_overrun_rate:
        over_budget_packages / assessed_packages.  None if no assessed
        packages.
    """

    contractor_id: str
    contractor_name: str
    total_milestones: int
    completed_milestones: int
    delayed_milestones: int
    on_time_milestones: int
    over_budget_milestones: int
    assessed_cost_milestones: int
    delayed_ratio: Optional[float]
    on_time_rate: Optional[float]
    overrun_ratio: Optional[float]
    avg_cost_variance_percent: Optional[float]
    active_packages: int
    completed_packages: int
    risk_signal_count: int
    schedule_score: float
    cost_score: float
    risk_score: float
    performance_score: float
    average_delay_days: Optional[float] = None
    median_delay_days: Optional[float] = None
    max_delay_days: Optional[int] = None
    delay_rate: Optional[float] = None
    total_cost_variance: Optional[Decimal] = None
    average_cost_variance_pct: Optional[float] = None
    max_cost_overrun_pct: Optional[float] = None
    cost_overrun_rate: Optional[float] = None


@dataclass
class ScopeContractorRankingRow:
    """Ranking row for a contractor within a scope.

    Parameters
    ----------
    contractor_rank:
        Position within scope (1 = best performance_score).
    contractor_id:
        Matches ConstructionContractor.id.
    contractor_name:
        Human-readable contractor name.
    performance_score:
        Weighted composite score 0–100.
    schedule_score:
        Schedule component score 0–100.
    cost_score:
        Cost component score 0–100.
    risk_score:
        Risk component score 0–100.
    total_milestones:
        Unique milestone count for this contractor.
    delayed_ratio:
        Delayed milestones fraction.  None if no milestones.
    overrun_ratio:
        Over-budget milestones fraction.  None if no costed milestones.
    """

    contractor_rank: int
    contractor_id: str
    contractor_name: str
    performance_score: float
    schedule_score: float
    cost_score: float
    risk_score: float
    total_milestones: int
    delayed_ratio: Optional[float]
    overrun_ratio: Optional[float]


@dataclass
class ContractorTrendPoint:
    """Scorecard snapshot for a single time period.

    Parameters
    ----------
    period_label:
        Calendar month string in ``YYYY-MM`` format.
    total_milestones:
        Milestones active (completed or delayed) in this period.
    completed_milestones:
        Milestones completed in this period.
    delayed_milestones:
        Milestones that were delayed in this period.
    over_budget_milestones:
        Over-budget milestones in this period.
    delayed_ratio:
        delayed / total for this period.  None if total == 0.
    overrun_ratio:
        over_budget / assessed for this period.  None if assessed == 0.
    performance_score:
        Computed performance score for this period.
    score_delta:
        performance_score − previous period's performance_score.
        None for the first period.
    """

    period_label: str
    total_milestones: int
    completed_milestones: int
    delayed_milestones: int
    over_budget_milestones: int
    delayed_ratio: Optional[float]
    overrun_ratio: Optional[float]
    performance_score: float
    score_delta: Optional[float]


@dataclass
class ContractorTrendSummary:
    """Trend summary for a single contractor across time periods.

    Parameters
    ----------
    contractor_id:
        Matches ConstructionContractor.id.
    contractor_name:
        Human-readable contractor name.
    trend_points:
        Chronologically sorted list of per-period snapshots.
    trend_direction:
        "improving" / "stable" / "deteriorating" based on the last two periods.
        "stable" when fewer than two periods exist.
    overall_score:
        Current overall performance_score (from full scorecard, not just last period).
    periods_analysed:
        Number of distinct calendar months included in the trend.
    """

    contractor_id: str
    contractor_name: str
    trend_points: List[ContractorTrendPoint]
    trend_direction: str
    overall_score: float
    periods_analysed: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _deduplicate_milestones(
    milestones: List[MilestoneScorecardData],
) -> List[MilestoneScorecardData]:
    """Return unique milestones by milestone_id (first occurrence wins)."""
    seen: set[str] = set()
    result: List[MilestoneScorecardData] = []
    for m in milestones:
        if m.milestone_id not in seen:
            seen.add(m.milestone_id)
            result.append(m)
    return result


def _compute_schedule_score(delayed_ratio: Optional[float]) -> float:
    """Compute schedule score 0–100 from delayed ratio."""
    if delayed_ratio is None:
        return 100.0
    return max(0.0, 100.0 - delayed_ratio * 100.0)


def _compute_cost_score(
    overrun_ratio: Optional[float],
    avg_cost_variance_percent: Optional[float],
) -> float:
    """Compute cost score 0–100 from overrun ratio and average variance."""
    if overrun_ratio is None:
        return 100.0
    # Primary driver: overrun ratio
    base = max(0.0, 100.0 - overrun_ratio * 100.0)
    # Secondary adjustment: average variance severity (max 20-point reduction)
    if avg_cost_variance_percent is not None and avg_cost_variance_percent > 0:
        penalty = min(20.0, avg_cost_variance_percent / 5.0)
        base = max(0.0, base - penalty)
    return base


def _compute_risk_score(risk_signal_count: int) -> float:
    """Compute risk score 0–100 from count of HIGH-severity ratio alerts."""
    return max(0.0, 100.0 - risk_signal_count * ALERT_PENALTY_POINTS)


def _compute_performance_score(
    schedule_score: float,
    cost_score: float,
    risk_score: float,
) -> float:
    """Compute weighted composite performance score."""
    return round(
        schedule_score * SCHEDULE_WEIGHT
        + cost_score * COST_WEIGHT
        + risk_score * RISK_WEIGHT,
        2,
    )


def _compute_metrics(
    milestones: List[MilestoneScorecardData],
) -> dict:
    """Compute raw counts and ratios from a list of deduplicated milestones."""
    total = len(milestones)
    completed = sum(1 for m in milestones if m.status == _COMPLETED_STATUS)
    delayed = sum(1 for m in milestones if m.status == _DELAYED_STATUS)

    # on_time: completed milestones where completion_date <= target_date
    on_time = sum(
        1
        for m in milestones
        if m.status == _COMPLETED_STATUS
        and m.completion_date is not None
        and m.target_date is not None
        and m.completion_date <= m.target_date
    )

    costed = [
        m
        for m in milestones
        if m.planned_cost is not None and m.actual_cost is not None
    ]
    assessed = len(costed)
    over_budget = sum(
        1 for m in costed if m.actual_cost is not None and m.actual_cost > m.planned_cost  # type: ignore[operator]
    )

    delayed_ratio: Optional[float] = delayed / total if total > 0 else None
    on_time_rate: Optional[float] = on_time / completed if completed > 0 else None
    overrun_ratio: Optional[float] = over_budget / assessed if assessed > 0 else None

    avg_cv_pct: Optional[float] = None
    if costed:
        variances = [
            float((m.actual_cost - m.planned_cost) / m.planned_cost * 100)  # type: ignore[operator]
            for m in costed
            if m.planned_cost is not None and m.planned_cost > Decimal("0")
        ]
        if variances:
            avg_cv_pct = round(sum(variances) / len(variances), 2)

    return {
        "total": total,
        "completed": completed,
        "delayed": delayed,
        "on_time": on_time,
        "assessed": assessed,
        "over_budget": over_budget,
        "delayed_ratio": delayed_ratio,
        "on_time_rate": on_time_rate,
        "overrun_ratio": overrun_ratio,
        "avg_cost_variance_percent": avg_cv_pct,
    }


# ---------------------------------------------------------------------------
# Main engine entry points
# ---------------------------------------------------------------------------


def compute_contractor_scorecard(
    data: ContractorScorecardInput,
) -> ContractorScorecard:
    """Compute a deterministic scorecard for a single contractor.

    Parameters
    ----------
    data:
        Contractor scorecard input including all linked milestones,
        packages, and high-risk alert count.

    Returns
    -------
    ContractorScorecard
        Derived KPIs and scores for the contractor.
    """
    from app.modules.construction.cost_variance_engine import (
        PackageCostInput,
        compute_cost_variance,
    )
    from app.modules.construction.schedule_variance_engine import (
        MilestoneVarianceInput,
        compute_schedule_variance,
    )

    milestones = _deduplicate_milestones(data.milestones)
    metrics = _compute_metrics(milestones)

    active_pkgs = sum(1 for p in data.packages if p.status in _ACTIVE_PACKAGE_STATUSES)
    completed_pkgs = sum(1 for p in data.packages if p.status == _COMPLETED_STATUS)

    schedule_score = _compute_schedule_score(metrics["delayed_ratio"])
    cost_score = _compute_cost_score(
        metrics["overrun_ratio"],
        metrics["avg_cost_variance_percent"],
    )
    risk_score = _compute_risk_score(data.risk_signal_count)
    performance_score = _compute_performance_score(schedule_score, cost_score, risk_score)

    variance = compute_schedule_variance(
        [
            MilestoneVarianceInput(
                milestone_id=m.milestone_id,
                completion_date=m.completion_date,
                target_date=m.target_date,
            )
            for m in milestones
        ]
    )

    cost_metrics = compute_cost_variance(
        [
            PackageCostInput(
                package_id=p.package_id,
                planned_cost=p.planned_value,
                actual_cost=p.awarded_value,
            )
            for p in data.packages
        ]
    )

    return ContractorScorecard(
        contractor_id=data.contractor_id,
        contractor_name=data.contractor_name,
        total_milestones=metrics["total"],
        completed_milestones=metrics["completed"],
        delayed_milestones=metrics["delayed"],
        on_time_milestones=metrics["on_time"],
        over_budget_milestones=metrics["over_budget"],
        assessed_cost_milestones=metrics["assessed"],
        delayed_ratio=metrics["delayed_ratio"],
        on_time_rate=metrics["on_time_rate"],
        overrun_ratio=metrics["overrun_ratio"],
        avg_cost_variance_percent=metrics["avg_cost_variance_percent"],
        active_packages=active_pkgs,
        completed_packages=completed_pkgs,
        risk_signal_count=data.risk_signal_count,
        schedule_score=round(schedule_score, 2),
        cost_score=round(cost_score, 2),
        risk_score=round(risk_score, 2),
        performance_score=performance_score,
        average_delay_days=variance.average_delay_days,
        median_delay_days=variance.median_delay_days,
        max_delay_days=variance.max_delay_days,
        delay_rate=variance.delay_rate,
        total_cost_variance=(
            cost_metrics.total_cost_variance if cost_metrics.assessed_packages > 0 else None
        ),
        average_cost_variance_pct=cost_metrics.average_cost_variance_pct,
        max_cost_overrun_pct=cost_metrics.max_cost_overrun_pct,
        cost_overrun_rate=cost_metrics.cost_overrun_rate,
    )


def compute_scope_contractor_ranking(
    inputs: List[ContractorScorecardInput],
) -> List[ScopeContractorRankingRow]:
    """Rank all contractors within a scope by performance_score.

    Parameters
    ----------
    inputs:
        One :class:`ContractorScorecardInput` per contractor in the scope.

    Returns
    -------
    List[ScopeContractorRankingRow]
        Rows sorted by performance_score descending.  Ties broken by
        contractor_id ascending for deterministic output.
    """
    scorecards = [compute_contractor_scorecard(inp) for inp in inputs]
    # Sort: higher performance_score first, tie-break by contractor_id ascending
    scorecards.sort(key=lambda s: (-s.performance_score, s.contractor_id))

    rows: List[ScopeContractorRankingRow] = []
    for rank, sc in enumerate(scorecards, start=1):
        rows.append(
            ScopeContractorRankingRow(
                contractor_rank=rank,
                contractor_id=sc.contractor_id,
                contractor_name=sc.contractor_name,
                performance_score=sc.performance_score,
                schedule_score=sc.schedule_score,
                cost_score=sc.cost_score,
                risk_score=sc.risk_score,
                total_milestones=sc.total_milestones,
                delayed_ratio=sc.delayed_ratio,
                overrun_ratio=sc.overrun_ratio,
            )
        )
    return rows


def compute_contractor_trend(
    data: ContractorScorecardInput,
    overall_scorecard: Optional[ContractorScorecard] = None,
) -> ContractorTrendSummary:
    """Compute trend analytics for a contractor by grouping milestones by month.

    Only milestones that have a ``completion_date`` set contribute to trend
    periods.  Milestones without a completion_date are excluded from trend
    points but are included in the overall scorecard.

    Parameters
    ----------
    data:
        Contractor scorecard input.
    overall_scorecard:
        Optional pre-computed overall scorecard.  If not provided, it is
        computed from ``data``.

    Returns
    -------
    ContractorTrendSummary
        Chronologically sorted trend points plus trend direction.
    """
    if overall_scorecard is None:
        overall_scorecard = compute_contractor_scorecard(data)

    milestones = _deduplicate_milestones(data.milestones)

    # Group milestones that have completion_date by YYYY-MM period
    periods: Dict[str, List[MilestoneScorecardData]] = {}
    for m in milestones:
        if m.completion_date is not None:
            label = m.completion_date.strftime("%Y-%m")
            periods.setdefault(label, []).append(m)

    sorted_labels = sorted(periods.keys())
    trend_points: List[ContractorTrendPoint] = []
    prev_score: Optional[float] = None

    for label in sorted_labels:
        period_milestones = periods[label]
        metrics = _compute_metrics(period_milestones)

        schedule_score = _compute_schedule_score(metrics["delayed_ratio"])
        cost_score = _compute_cost_score(
            metrics["overrun_ratio"],
            metrics["avg_cost_variance_percent"],
        )
        # Use overall risk score per period (no per-period alert history)
        risk_score = _compute_risk_score(data.risk_signal_count)
        period_score = _compute_performance_score(schedule_score, cost_score, risk_score)

        delta = round(period_score - prev_score, 2) if prev_score is not None else None

        trend_points.append(
            ContractorTrendPoint(
                period_label=label,
                total_milestones=metrics["total"],
                completed_milestones=metrics["completed"],
                delayed_milestones=metrics["delayed"],
                over_budget_milestones=metrics["over_budget"],
                delayed_ratio=metrics["delayed_ratio"],
                overrun_ratio=metrics["overrun_ratio"],
                performance_score=period_score,
                score_delta=delta,
            )
        )
        prev_score = period_score

    trend_direction = _determine_trend_direction(trend_points)

    return ContractorTrendSummary(
        contractor_id=data.contractor_id,
        contractor_name=data.contractor_name,
        trend_points=trend_points,
        trend_direction=trend_direction,
        overall_score=overall_scorecard.performance_score,
        periods_analysed=len(trend_points),
    )


def _determine_trend_direction(points: List[ContractorTrendPoint]) -> str:
    """Derive trend direction from the last two trend points."""
    if len(points) < 2:
        return "stable"
    last_delta = points[-1].score_delta
    if last_delta is None:
        return "stable"
    if last_delta >= TREND_MIN_DELTA:
        return "improving"
    if last_delta <= -TREND_MIN_DELTA:
        return "deteriorating"
    return "stable"
