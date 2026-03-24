"""
construction.portfolio_risk_rollup_engine

Pure Portfolio Construction Risk Rollup Engine.

Aggregates pre-computed contractor scorecards (including watchlist
escalation outputs) from a project's scopes into a single project-level
construction risk summary.  No database access, no HTTP concerns.

Project Risk Score Formula
--------------------------
Each contractor carries an ``escalation_score`` derived from the scope
escalation engine:

    Normal   = 0
    Watch    = 1
    Escalate = 2
    Critical = 3

The composite project risk score is normalised to a 0–100 scale:

    project_risk_score = sum(escalation_score) / (contractors_total * 3) * 100

When no contractors are present the score is 0.0.

Top Breach Reasons
------------------
Breach reasons are collected from all contractor scorecards that carry a
non-Normal watchlist status.  Reasons are counted and the most-frequent
reasons (up to TOP_BREACH_REASON_LIMIT) are returned.

Highest-Risk Contractor
-----------------------
The contractor with the highest ``escalation_score`` is identified.  Ties
are broken by the lowest ``reliability_index`` (worst performer first), then
alphabetically by ``contractor_id`` for determinism.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional

from app.modules.construction.scope_escalation_engine import (
    STATUS_CRITICAL,
    STATUS_ESCALATE,
    STATUS_NORMAL,
    STATUS_WATCH,
)

logger = logging.getLogger(__name__)

# Number of top breach reasons to surface in the rollup
TOP_BREACH_REASON_LIMIT: int = 5

# Maximum possible escalation score per contractor
_MAX_ESCALATION_SCORE_PER_CONTRACTOR: int = 3


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ScorecardRollupInput:
    """Condensed view of a contractor scorecard used by the rollup engine.

    Parameters
    ----------
    contractor_id:
        Matches ConstructionContractor.id.
    watchlist_status:
        Highest-severity escalation tier: ``Critical`` / ``Escalate`` /
        ``Watch`` / ``Normal``.
    escalation_score:
        Numeric severity: Critical=3, Escalate=2, Watch=1, Normal=0.
    breach_reasons:
        Human-readable list of breach conditions triggered for this
        contractor's winning escalation tier.
    reliability_index:
        Composite reliability score 0–100.  None if not yet computed.
        Used as a tiebreaker when selecting the highest-risk contractor.
    """

    contractor_id: str
    watchlist_status: str
    escalation_score: int = 0
    breach_reasons: List[str] = field(default_factory=list)
    reliability_index: Optional[float] = None


@dataclass
class ProjectRiskInput:
    """All scorecard data needed to compute a project-level risk rollup.

    Parameters
    ----------
    project_id:
        Matches the development project identifier.
    contractor_scorecards:
        One ``ScorecardRollupInput`` per contractor across all project
        scopes.  A contractor that appears in multiple scopes will
        contribute multiple entries, each evaluated independently.
    """

    project_id: str
    contractor_scorecards: List[ScorecardRollupInput] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class ProjectRiskRollup:
    """Project-level construction risk aggregation result.

    Parameters
    ----------
    project_id:
        Matches the development project identifier.
    contractors_total:
        Total number of contractor-scope entries assessed.
    contractors_on_watch:
        Count with watchlist_status == ``Watch``.
    contractors_escalated:
        Count with watchlist_status == ``Escalate``.
    contractors_critical:
        Count with watchlist_status == ``Critical``.
    project_risk_score:
        Normalised composite risk indicator 0–100.
    top_breach_reasons:
        Most common breach reason strings across all non-Normal contractors,
        limited to ``TOP_BREACH_REASON_LIMIT`` entries.
    highest_risk_contractor:
        ``contractor_id`` of the contractor with the highest escalation
        severity.  ``None`` when no contractors are present.
    """

    project_id: str
    contractors_total: int
    contractors_on_watch: int
    contractors_escalated: int
    contractors_critical: int
    project_risk_score: float
    top_breach_reasons: List[str]
    highest_risk_contractor: Optional[str]


# ---------------------------------------------------------------------------
# Engine function
# ---------------------------------------------------------------------------


def compute_project_construction_risk(
    inp: ProjectRiskInput,
) -> ProjectRiskRollup:
    """Aggregate contractor escalation outputs into a project risk rollup.

    Parameters
    ----------
    inp:
        Pre-computed contractor scorecard summaries for the project.

    Returns
    -------
    ProjectRiskRollup
        Project-level risk counts, composite score, top breach reasons,
        and the highest-risk contractor identifier.
    """
    scorecards = inp.contractor_scorecards
    contractors_total = len(scorecards)

    if contractors_total == 0:
        logger.debug("project=%s no contractors — risk score = 0", inp.project_id)
        return ProjectRiskRollup(
            project_id=inp.project_id,
            contractors_total=0,
            contractors_on_watch=0,
            contractors_escalated=0,
            contractors_critical=0,
            project_risk_score=0.0,
            top_breach_reasons=[],
            highest_risk_contractor=None,
        )

    # ── Escalation distribution counts ───────────────────────────────────────
    contractors_on_watch = sum(
        1 for sc in scorecards if sc.watchlist_status == STATUS_WATCH
    )
    contractors_escalated = sum(
        1 for sc in scorecards if sc.watchlist_status == STATUS_ESCALATE
    )
    contractors_critical = sum(
        1 for sc in scorecards if sc.watchlist_status == STATUS_CRITICAL
    )

    # ── Composite risk score ──────────────────────────────────────────────────
    total_score = sum(sc.escalation_score for sc in scorecards)
    max_possible = contractors_total * _MAX_ESCALATION_SCORE_PER_CONTRACTOR
    project_risk_score = round(total_score / max_possible * 100, 1)

    logger.debug(
        "project=%s total_score=%d max_possible=%d project_risk_score=%.1f",
        inp.project_id,
        total_score,
        max_possible,
        project_risk_score,
    )

    # ── Top breach reasons ────────────────────────────────────────────────────
    reason_counter: Counter[str] = Counter()
    for sc in scorecards:
        if sc.watchlist_status != STATUS_NORMAL:
            reason_counter.update(sc.breach_reasons)

    # Sort count DESC then reason ASC for deterministic output under tied counts
    sorted_reasons = sorted(
        reason_counter.items(),
        key=lambda item: (-item[1], item[0]),
    )
    top_breach_reasons = [reason for reason, _ in sorted_reasons[:TOP_BREACH_REASON_LIMIT]]

    # ── Highest-risk contractor ───────────────────────────────────────────────
    # Primary sort key  : escalation_score DESC (highest severity first)
    # Secondary sort key: reliability_index ASC (worst performer first;
    #                     None treated as -inf so it sorts first)
    # Tertiary sort key : contractor_id ASC (deterministic tiebreaker)
    def _risk_sort_key(sc: ScorecardRollupInput) -> tuple:
        ri = sc.reliability_index if sc.reliability_index is not None else float("-inf")
        return (-sc.escalation_score, ri, sc.contractor_id)

    highest_risk_sc = min(scorecards, key=_risk_sort_key)
    highest_risk_contractor = highest_risk_sc.contractor_id

    return ProjectRiskRollup(
        project_id=inp.project_id,
        contractors_total=contractors_total,
        contractors_on_watch=contractors_on_watch,
        contractors_escalated=contractors_escalated,
        contractors_critical=contractors_critical,
        project_risk_score=project_risk_score,
        top_breach_reasons=top_breach_reasons,
        highest_risk_contractor=highest_risk_contractor,
    )
