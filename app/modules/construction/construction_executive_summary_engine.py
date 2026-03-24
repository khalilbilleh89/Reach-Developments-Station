"""
construction.construction_executive_summary_engine

Pure Construction Executive Summary Engine.

Consolidates project-level construction analytics into a single
executive-ready health snapshot.  No database access, no HTTP concerns.

Construction Health Status
--------------------------
Status is assigned deterministically using escalation counts and the
composite project risk score:

    Critical   — any critical contractors OR project risk score >= 75
    Escalated  — any escalated contractors OR project risk score >= 50
    Watch      — any on-watch contractors OR project risk score >= 25
    Stable     — none of the above

Priority Actions
----------------
Rule-based guidance strings generated from the rollup data:

    - "Review critical contractor {contractor_id} immediately"
      (generated for every unique critical contractor; ordered by
      escalation score DESC then contractor_id ASC for determinism)
    - "Escalation density exceeds threshold for this project"
      (generated when (escalated + critical) / total > ESCALATION_DENSITY_THRESHOLD)
    - "Delay-related breaches are the dominant risk pattern"
      (generated when the leading top-breach reason contains a delay keyword)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from app.modules.construction.portfolio_risk_rollup_engine import (
    ProjectRiskRollup,
    ScorecardRollupInput,
)
from app.modules.construction.scope_escalation_engine import STATUS_CRITICAL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Health status constants
# ---------------------------------------------------------------------------

HEALTH_CRITICAL: str = "Critical"
HEALTH_ESCALATED: str = "Escalated"
HEALTH_WATCH: str = "Watch"
HEALTH_STABLE: str = "Stable"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

CRITICAL_RISK_SCORE_THRESHOLD: float = 75.0
ESCALATED_RISK_SCORE_THRESHOLD: float = 50.0
WATCH_RISK_SCORE_THRESHOLD: float = 25.0

# Fraction of (escalated + critical) / total contractors above which
# "escalation density exceeds threshold" guidance is generated.
ESCALATION_DENSITY_THRESHOLD: float = 0.5

# Keywords used to identify delay-related breach reasons (case-insensitive).
_DELAY_KEYWORDS: tuple[str, ...] = ("delay", "schedule")


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ScopeSummaryData:
    """Lightweight scope-level summary used by the executive summary engine.

    Parameters
    ----------
    scope_id:
        Matches ConstructionScope.id.
    contractors_on_watch:
        Count of on-watch contractors in this scope.
    contractors_escalated:
        Count of escalated contractors in this scope.
    contractors_critical:
        Count of critical contractors in this scope.
    """

    scope_id: str
    contractors_on_watch: int = 0
    contractors_escalated: int = 0
    contractors_critical: int = 0


@dataclass
class ConstructionExecutiveSummaryInput:
    """All data required to produce a project construction executive summary.

    Parameters
    ----------
    project_id:
        Matches the development project identifier.
    project_risk_rollup:
        Pre-computed project-level risk rollup.
    contractor_scorecards:
        Individual contractor escalation summaries from the rollup engine.
        Used to identify critical contractor IDs for priority actions.
    scope_summaries:
        Optional per-scope summary data.  Not currently used in health
        status calculation but retained for future enhancements.
    """

    project_id: str
    project_risk_rollup: ProjectRiskRollup
    contractor_scorecards: List[ScorecardRollupInput] = field(default_factory=list)
    scope_summaries: List[ScopeSummaryData] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class ConstructionExecutiveSummaryResult:
    """Executive-ready project construction health snapshot.

    Parameters
    ----------
    project_id:
        Matches the development project identifier.
    construction_health_status:
        Deterministic health tier: ``Stable`` / ``Watch`` / ``Escalated`` /
        ``Critical``.
    project_risk_score:
        Normalised composite risk indicator 0–100.
    contractors_total:
        Total number of contractor-scope entries assessed.
    contractors_on_watch:
        Count with watchlist_status == ``Watch``.
    contractors_escalated:
        Count with watchlist_status == ``Escalate``.
    contractors_critical:
        Count with watchlist_status == ``Critical``.
    top_breach_reasons:
        Most common breach reason strings across all non-Normal contractors.
    highest_risk_contractor:
        ``contractor_id`` of the highest-risk contractor.  ``None`` when no
        contractors are present.
    priority_actions:
        Deterministic rule-based guidance for immediate action.
    summary_generated_at:
        UTC timestamp when this summary was computed.
    """

    project_id: str
    construction_health_status: str
    project_risk_score: float
    contractors_total: int
    contractors_on_watch: int
    contractors_escalated: int
    contractors_critical: int
    top_breach_reasons: List[str]
    highest_risk_contractor: Optional[str]
    priority_actions: List[str]
    summary_generated_at: datetime


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _determine_health_status(
    contractors_critical: int,
    contractors_escalated: int,
    contractors_on_watch: int,
    project_risk_score: float,
) -> str:
    """Map escalation counts and risk score to a health status tier.

    Parameters
    ----------
    contractors_critical:
        Count of critical contractors.
    contractors_escalated:
        Count of escalated contractors.
    contractors_on_watch:
        Count of on-watch contractors.
    project_risk_score:
        Normalised risk score 0–100.

    Returns
    -------
    str
        One of ``Critical``, ``Escalated``, ``Watch``, or ``Stable``.
    """
    if contractors_critical > 0 or project_risk_score >= CRITICAL_RISK_SCORE_THRESHOLD:
        return HEALTH_CRITICAL
    if contractors_escalated > 0 or project_risk_score >= ESCALATED_RISK_SCORE_THRESHOLD:
        return HEALTH_ESCALATED
    if contractors_on_watch > 0 or project_risk_score >= WATCH_RISK_SCORE_THRESHOLD:
        return HEALTH_WATCH
    return HEALTH_STABLE


def _generate_priority_actions(
    rollup: ProjectRiskRollup,
    contractor_scorecards: List[ScorecardRollupInput],
) -> List[str]:
    """Generate deterministic rule-based priority guidance.

    Rules (in evaluation order):

    1.  For each unique critical contractor (deduplicated by ``contractor_id``
        across scopes; ordered by escalation_score DESC then contractor_id ASC)
        → ``"Review critical contractor {id} immediately"``
    2.  If (escalated + critical) / total > ESCALATION_DENSITY_THRESHOLD
        → ``"Escalation density exceeds threshold for this project"``
    3.  If the leading top-breach reason contains a delay keyword
        → ``"Delay-related breaches are the dominant risk pattern"``

    Parameters
    ----------
    rollup:
        Pre-computed project-level risk rollup.
    contractor_scorecards:
        Per-contractor escalation summaries.

    Returns
    -------
    list[str]
        Ordered priority action strings.
    """
    actions: List[str] = []

    # Rule 1: Critical contractors — deduplicate by contractor_id keeping the
    # highest escalation_score seen across scopes, then sort deterministically.
    critical_by_contractor: dict[str, int] = {}
    for sc in contractor_scorecards:
        if sc.watchlist_status != STATUS_CRITICAL:
            continue
        existing = critical_by_contractor.get(sc.contractor_id)
        if existing is None or sc.escalation_score > existing:
            critical_by_contractor[sc.contractor_id] = sc.escalation_score

    # Sort: escalation_score DESC then contractor_id ASC
    sorted_critical = sorted(
        critical_by_contractor.items(), key=lambda item: (-item[1], item[0])
    )
    for contractor_id, _ in sorted_critical:
        actions.append(f"Review critical contractor {contractor_id} immediately")

    # Rule 2: Escalation density
    total = rollup.contractors_total
    if total > 0:
        density = (rollup.contractors_escalated + rollup.contractors_critical) / total
        if density > ESCALATION_DENSITY_THRESHOLD:
            actions.append("Escalation density exceeds threshold for this project")

    # Rule 3: Delay-related breach pattern dominance
    if rollup.top_breach_reasons:
        leading_reason = rollup.top_breach_reasons[0].lower()
        if any(kw in leading_reason for kw in _DELAY_KEYWORDS):
            actions.append("Delay-related breaches are the dominant risk pattern")

    return actions


# ---------------------------------------------------------------------------
# Engine function
# ---------------------------------------------------------------------------


def compute_construction_executive_summary(
    inp: ConstructionExecutiveSummaryInput,
) -> ConstructionExecutiveSummaryResult:
    """Consolidate project construction analytics into an executive summary.

    Parameters
    ----------
    inp:
        Pre-computed rollup and contractor-level data.

    Returns
    -------
    ConstructionExecutiveSummaryResult
        Executive-ready health snapshot with deterministic status and
        rule-based priority actions.
    """
    rollup = inp.project_risk_rollup

    health_status = _determine_health_status(
        contractors_critical=rollup.contractors_critical,
        contractors_escalated=rollup.contractors_escalated,
        contractors_on_watch=rollup.contractors_on_watch,
        project_risk_score=rollup.project_risk_score,
    )

    priority_actions = _generate_priority_actions(
        rollup=rollup,
        contractor_scorecards=inp.contractor_scorecards,
    )

    logger.debug(
        "project=%s health=%s risk_score=%.1f critical=%d escalated=%d watch=%d",
        inp.project_id,
        health_status,
        rollup.project_risk_score,
        rollup.contractors_critical,
        rollup.contractors_escalated,
        rollup.contractors_on_watch,
    )

    return ConstructionExecutiveSummaryResult(
        project_id=inp.project_id,
        construction_health_status=health_status,
        project_risk_score=rollup.project_risk_score,
        contractors_total=rollup.contractors_total,
        contractors_on_watch=rollup.contractors_on_watch,
        contractors_escalated=rollup.contractors_escalated,
        contractors_critical=rollup.contractors_critical,
        top_breach_reasons=rollup.top_breach_reasons,
        highest_risk_contractor=rollup.highest_risk_contractor,
        priority_actions=priority_actions,
        summary_generated_at=datetime.now(tz=timezone.utc),
    )
