"""
Tests for the Construction Executive Summary Engine.

PR-CONSTR-051 — Construction Intelligence Completion & Executive Summary API

Validates:
- empty project (no contractors) → Stable health, empty priority actions
- stable project → Stable health status
- watch project → Watch health status
- escalated project → Escalated health status
- critical project → Critical health status
- health status determined by critical count even when risk score < 75
- health status determined by risk score when no critical contractors
- priority action generated for each critical contractor
- critical contractors sorted deterministically (escalation_score DESC, id ASC)
- escalation density action generated when density > threshold
- escalation density action NOT generated when density <= threshold
- delay breach reason triggers delay priority action
- non-delay breach reason does NOT trigger delay priority action
- top_breach_reasons passed through unchanged
- highest_risk_contractor passed through unchanged
- summary_generated_at is a UTC datetime
- project_id passed through unchanged
- priority actions list is empty for stable project
"""

from __future__ import annotations

from datetime import timezone

from app.modules.construction.construction_executive_summary_engine import (
    ESCALATION_DENSITY_THRESHOLD,
    HEALTH_CRITICAL,
    HEALTH_ESCALATED,
    HEALTH_STABLE,
    HEALTH_WATCH,
    ConstructionExecutiveSummaryInput,
    compute_construction_executive_summary,
)
from app.modules.construction.portfolio_risk_rollup_engine import (
    ProjectRiskRollup,
    ScorecardRollupInput,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _rollup(
    project_id: str = "PRJ-001",
    contractors_total: int = 0,
    contractors_on_watch: int = 0,
    contractors_escalated: int = 0,
    contractors_critical: int = 0,
    project_risk_score: float = 0.0,
    top_breach_reasons: list[str] | None = None,
    highest_risk_contractor: str | None = None,
) -> ProjectRiskRollup:
    return ProjectRiskRollup(
        project_id=project_id,
        contractors_total=contractors_total,
        contractors_on_watch=contractors_on_watch,
        contractors_escalated=contractors_escalated,
        contractors_critical=contractors_critical,
        project_risk_score=project_risk_score,
        top_breach_reasons=top_breach_reasons or [],
        highest_risk_contractor=highest_risk_contractor,
    )


def _sc(
    contractor_id: str = "CTR-001",
    watchlist_status: str = "Normal",
    escalation_score: int = 0,
    breach_reasons: list[str] | None = None,
    reliability_index: float | None = None,
) -> ScorecardRollupInput:
    return ScorecardRollupInput(
        contractor_id=contractor_id,
        watchlist_status=watchlist_status,
        escalation_score=escalation_score,
        breach_reasons=breach_reasons or [],
        reliability_index=reliability_index,
    )


def _inp(
    project_id: str = "PRJ-001",
    rollup: ProjectRiskRollup | None = None,
    scorecards: list[ScorecardRollupInput] | None = None,
) -> ConstructionExecutiveSummaryInput:
    return ConstructionExecutiveSummaryInput(
        project_id=project_id,
        project_risk_rollup=rollup or _rollup(project_id=project_id),
        contractor_scorecards=scorecards or [],
    )


# ---------------------------------------------------------------------------
# Empty project
# ---------------------------------------------------------------------------


def test_empty_project_health_stable() -> None:
    """Empty project (no contractors) → Stable health status."""
    result = compute_construction_executive_summary(_inp())
    assert result.construction_health_status == HEALTH_STABLE


def test_empty_project_priority_actions_empty() -> None:
    """Empty project → no priority actions."""
    result = compute_construction_executive_summary(_inp())
    assert result.priority_actions == []


def test_empty_project_risk_score_zero() -> None:
    """Empty project → project_risk_score == 0.0."""
    result = compute_construction_executive_summary(_inp())
    assert result.project_risk_score == 0.0


def test_empty_project_contractors_total_zero() -> None:
    """Empty project → contractors_total == 0."""
    result = compute_construction_executive_summary(_inp())
    assert result.contractors_total == 0


def test_empty_project_highest_risk_none() -> None:
    """Empty project → highest_risk_contractor is None."""
    result = compute_construction_executive_summary(_inp())
    assert result.highest_risk_contractor is None


def test_empty_project_breach_reasons_empty() -> None:
    """Empty project → top_breach_reasons is empty."""
    result = compute_construction_executive_summary(_inp())
    assert result.top_breach_reasons == []


# ---------------------------------------------------------------------------
# Stable project
# ---------------------------------------------------------------------------


def test_stable_project_all_normal() -> None:
    """Project with all-Normal contractors and low risk score → Stable."""
    rollup = _rollup(
        contractors_total=3,
        contractors_on_watch=0,
        contractors_escalated=0,
        contractors_critical=0,
        project_risk_score=0.0,
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.construction_health_status == HEALTH_STABLE


def test_stable_project_priority_actions_empty() -> None:
    """Stable project → priority_actions list is empty."""
    rollup = _rollup(contractors_total=2, project_risk_score=0.0)
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.priority_actions == []


# ---------------------------------------------------------------------------
# Watch project
# ---------------------------------------------------------------------------


def test_watch_project_via_on_watch_count() -> None:
    """Project with on-watch contractors → Watch health status."""
    rollup = _rollup(
        contractors_total=2,
        contractors_on_watch=1,
        contractors_escalated=0,
        contractors_critical=0,
        project_risk_score=10.0,
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.construction_health_status == HEALTH_WATCH


def test_watch_project_via_risk_score() -> None:
    """Project with risk score >= 25 and no escalated/critical → Watch."""
    rollup = _rollup(
        contractors_total=3,
        contractors_on_watch=0,
        contractors_escalated=0,
        contractors_critical=0,
        project_risk_score=25.0,
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.construction_health_status == HEALTH_WATCH


def test_watch_project_score_below_25_no_watch_contractors() -> None:
    """Project with risk score < 25 and no flagged contractors → Stable."""
    rollup = _rollup(project_risk_score=24.9)
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.construction_health_status == HEALTH_STABLE


# ---------------------------------------------------------------------------
# Escalated project
# ---------------------------------------------------------------------------


def test_escalated_project_via_escalated_count() -> None:
    """Project with escalated contractors → Escalated health status."""
    rollup = _rollup(
        contractors_total=3,
        contractors_on_watch=0,
        contractors_escalated=1,
        contractors_critical=0,
        project_risk_score=10.0,
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.construction_health_status == HEALTH_ESCALATED


def test_escalated_project_via_risk_score() -> None:
    """Project with risk score >= 50 and no critical contractors → Escalated."""
    rollup = _rollup(
        contractors_total=4,
        contractors_on_watch=0,
        contractors_escalated=0,
        contractors_critical=0,
        project_risk_score=50.0,
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.construction_health_status == HEALTH_ESCALATED


# ---------------------------------------------------------------------------
# Critical project
# ---------------------------------------------------------------------------


def test_critical_project_via_critical_count() -> None:
    """Project with critical contractors → Critical health status."""
    rollup = _rollup(
        contractors_total=3,
        contractors_on_watch=0,
        contractors_escalated=0,
        contractors_critical=1,
        project_risk_score=30.0,
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.construction_health_status == HEALTH_CRITICAL


def test_critical_project_via_risk_score() -> None:
    """Project with risk score >= 75 and no critical contractors → Critical."""
    rollup = _rollup(
        contractors_total=4,
        contractors_on_watch=0,
        contractors_escalated=0,
        contractors_critical=0,
        project_risk_score=75.0,
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.construction_health_status == HEALTH_CRITICAL


def test_critical_overrides_lower_risk_score() -> None:
    """Critical contractor count triggers Critical even if risk score < 75."""
    rollup = _rollup(
        contractors_total=5,
        contractors_critical=1,
        project_risk_score=20.0,
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.construction_health_status == HEALTH_CRITICAL


# ---------------------------------------------------------------------------
# Priority action: critical contractor review
# ---------------------------------------------------------------------------


def test_priority_action_critical_contractor() -> None:
    """Each critical contractor generates a review action."""
    rollup = _rollup(contractors_total=1, contractors_critical=1, project_risk_score=33.3)
    scorecards = [_sc("CTR-001", watchlist_status="Critical", escalation_score=3)]
    result = compute_construction_executive_summary(
        _inp(rollup=rollup, scorecards=scorecards)
    )
    assert any("CTR-001" in action for action in result.priority_actions)


def test_priority_action_multiple_critical_contractors_ordered() -> None:
    """Multiple critical contractors appear deterministically ordered."""
    rollup = _rollup(
        contractors_total=2,
        contractors_critical=2,
        project_risk_score=66.7,
    )
    scorecards = [
        _sc("CTR-BBB", watchlist_status="Critical", escalation_score=3),
        _sc("CTR-AAA", watchlist_status="Critical", escalation_score=3),
    ]
    result = compute_construction_executive_summary(
        _inp(rollup=rollup, scorecards=scorecards)
    )
    # Both should appear
    ctr_actions = [a for a in result.priority_actions if "CTR-" in a]
    assert len(ctr_actions) == 2
    # Alphabetical tiebreak: CTR-AAA < CTR-BBB
    assert "CTR-AAA" in ctr_actions[0]
    assert "CTR-BBB" in ctr_actions[1]


def test_no_critical_no_review_action() -> None:
    """Project with no critical contractors generates no review action."""
    rollup = _rollup(contractors_total=2, contractors_on_watch=1)
    scorecards = [
        _sc("CTR-001", watchlist_status="Watch", escalation_score=1),
        _sc("CTR-002", watchlist_status="Normal", escalation_score=0),
    ]
    result = compute_construction_executive_summary(
        _inp(rollup=rollup, scorecards=scorecards)
    )
    assert not any("immediately" in a for a in result.priority_actions)


# ---------------------------------------------------------------------------
# Priority action: escalation density
# ---------------------------------------------------------------------------


def test_escalation_density_action_generated_above_threshold() -> None:
    """Escalation density action generated when density > threshold."""
    rollup = _rollup(
        contractors_total=2,
        contractors_escalated=1,
        contractors_critical=1,
        project_risk_score=50.0,
    )
    scorecards = [
        _sc("CTR-001", watchlist_status="Critical", escalation_score=3),
        _sc("CTR-002", watchlist_status="Escalate", escalation_score=2),
    ]
    result = compute_construction_executive_summary(
        _inp(rollup=rollup, scorecards=scorecards)
    )
    assert any("density" in a.lower() for a in result.priority_actions)


def test_escalation_density_action_not_generated_at_or_below_threshold() -> None:
    """Escalation density action NOT generated when density <= threshold."""
    # Density = 1/3 ≈ 0.33, below default threshold of 0.5
    rollup = _rollup(
        contractors_total=3,
        contractors_escalated=1,
        contractors_critical=0,
        project_risk_score=10.0,
    )
    scorecards = [
        _sc("CTR-001", watchlist_status="Escalate", escalation_score=2),
        _sc("CTR-002", watchlist_status="Normal", escalation_score=0),
        _sc("CTR-003", watchlist_status="Normal", escalation_score=0),
    ]
    result = compute_construction_executive_summary(
        _inp(rollup=rollup, scorecards=scorecards)
    )
    assert not any("density" in a.lower() for a in result.priority_actions)


def test_escalation_density_empty_project_no_action() -> None:
    """Escalation density action not generated for empty project."""
    result = compute_construction_executive_summary(_inp())
    assert not any("density" in a.lower() for a in result.priority_actions)


# ---------------------------------------------------------------------------
# Priority action: delay breach pattern
# ---------------------------------------------------------------------------


def test_delay_breach_reason_triggers_delay_action() -> None:
    """Leading breach reason containing 'delay' triggers delay action."""
    rollup = _rollup(
        contractors_total=1,
        contractors_on_watch=1,
        project_risk_score=10.0,
        top_breach_reasons=["delay rate 60% >= 50% threshold"],
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert any("delay" in a.lower() for a in result.priority_actions)


def test_non_delay_breach_reason_no_delay_action() -> None:
    """Leading breach reason not containing a delay keyword → no delay action."""
    rollup = _rollup(
        contractors_total=1,
        contractors_escalated=1,
        project_risk_score=20.0,
        top_breach_reasons=["cost overrun rate 60% >= 50% threshold"],
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert not any("delay" in a.lower() for a in result.priority_actions)


def test_schedule_breach_reason_triggers_delay_action() -> None:
    """'schedule' keyword in leading breach reason triggers delay action."""
    rollup = _rollup(
        contractors_total=1,
        contractors_on_watch=1,
        project_risk_score=10.0,
        top_breach_reasons=["schedule overrun detected"],
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert any("delay" in a.lower() for a in result.priority_actions)


def test_no_breach_reasons_no_delay_action() -> None:
    """Empty top_breach_reasons → no delay action."""
    rollup = _rollup(
        contractors_total=1,
        contractors_on_watch=1,
        project_risk_score=10.0,
        top_breach_reasons=[],
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert not any("delay" in a.lower() for a in result.priority_actions)


# ---------------------------------------------------------------------------
# Passthrough fields
# ---------------------------------------------------------------------------


def test_top_breach_reasons_passthrough() -> None:
    """top_breach_reasons from rollup are passed through unchanged."""
    reasons = ["delay rate 60% >= 50% threshold", "cost overrun rate 55% >= 50% threshold"]
    rollup = _rollup(
        contractors_total=1,
        contractors_critical=1,
        project_risk_score=33.3,
        top_breach_reasons=reasons,
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.top_breach_reasons == reasons


def test_highest_risk_contractor_passthrough() -> None:
    """highest_risk_contractor from rollup is passed through unchanged."""
    rollup = _rollup(
        contractors_total=1,
        contractors_critical=1,
        project_risk_score=33.3,
        highest_risk_contractor="CTR-ALPHA",
    )
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.highest_risk_contractor == "CTR-ALPHA"


def test_highest_risk_contractor_none_passthrough() -> None:
    """highest_risk_contractor is None when rollup has no contractors."""
    rollup = _rollup(highest_risk_contractor=None)
    result = compute_construction_executive_summary(_inp(rollup=rollup))
    assert result.highest_risk_contractor is None


def test_project_id_passthrough() -> None:
    """project_id is preserved in the result."""
    rollup = _rollup(project_id="PRJ-XYZ")
    result = compute_construction_executive_summary(_inp(project_id="PRJ-XYZ", rollup=rollup))
    assert result.project_id == "PRJ-XYZ"


# ---------------------------------------------------------------------------
# summary_generated_at
# ---------------------------------------------------------------------------


def test_summary_generated_at_is_utc() -> None:
    """summary_generated_at is a UTC-aware datetime."""
    result = compute_construction_executive_summary(_inp())
    assert result.summary_generated_at.tzinfo is not None
    assert result.summary_generated_at.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# Deterministic status mapping
# ---------------------------------------------------------------------------


def test_deterministic_status_all_score_boundaries() -> None:
    """Health status transitions at exact score boundaries are deterministic."""
    # score == 74.9 with no flagged contractors → Escalated (because 74.9 >= 50)
    assert (
        compute_construction_executive_summary(
            _inp(rollup=_rollup(project_risk_score=74.9))
        ).construction_health_status
        == HEALTH_ESCALATED
    )
    # score == 75.0 → Critical
    assert (
        compute_construction_executive_summary(
            _inp(rollup=_rollup(project_risk_score=75.0))
        ).construction_health_status
        == HEALTH_CRITICAL
    )
    # score == 49.9 → Watch (because 49.9 >= 25)
    assert (
        compute_construction_executive_summary(
            _inp(rollup=_rollup(project_risk_score=49.9))
        ).construction_health_status
        == HEALTH_WATCH
    )
    # score == 50.0 → Escalated
    assert (
        compute_construction_executive_summary(
            _inp(rollup=_rollup(project_risk_score=50.0))
        ).construction_health_status
        == HEALTH_ESCALATED
    )
    # score == 24.9 → Stable
    assert (
        compute_construction_executive_summary(
            _inp(rollup=_rollup(project_risk_score=24.9))
        ).construction_health_status
        == HEALTH_STABLE
    )
    # score == 25.0 → Watch
    assert (
        compute_construction_executive_summary(
            _inp(rollup=_rollup(project_risk_score=25.0))
        ).construction_health_status
        == HEALTH_WATCH
    )
