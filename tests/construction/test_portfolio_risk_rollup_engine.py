"""
Tests for the Portfolio Construction Risk Rollup Engine.

PR-CONSTR-050 — Construction Portfolio Risk Rollup Engine

Validates:
- zero contractors → score 0.0 and None highest_risk_contractor
- all Normal contractors → score 0.0
- single Critical contractor → score 100.0
- mixed escalation tiers → correct score normalisation
- correct escalation distribution counts (on_watch, escalated, critical)
- top_breach_reasons aggregation and ordering
- top_breach_reasons limited to TOP_BREACH_REASON_LIMIT entries
- highest_risk_contractor selection by escalation_score DESC
- tiebreaker by reliability_index ASC (lower = worse)
- tiebreaker by contractor_id ASC for determinism when both equal
- breach_reasons from Normal contractors excluded
- score formula: sum(scores) / (total * 3) * 100
- multiple projects independent of each other
"""

from __future__ import annotations

from app.modules.construction.portfolio_risk_rollup_engine import (
    TOP_BREACH_REASON_LIMIT,
    ProjectRiskInput,
    ScorecardRollupInput,
    compute_project_construction_risk,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


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
    scorecards: list[ScorecardRollupInput] | None = None,
) -> ProjectRiskInput:
    return ProjectRiskInput(
        project_id=project_id,
        contractor_scorecards=scorecards or [],
    )


# ---------------------------------------------------------------------------
# Zero contractors
# ---------------------------------------------------------------------------


def test_zero_contractors_score_zero() -> None:
    """No contractors → project_risk_score == 0.0."""
    result = compute_project_construction_risk(_inp())
    assert result.project_risk_score == 0.0


def test_zero_contractors_counts_zero() -> None:
    """No contractors → all count fields are 0."""
    result = compute_project_construction_risk(_inp())
    assert result.contractors_total == 0
    assert result.contractors_on_watch == 0
    assert result.contractors_escalated == 0
    assert result.contractors_critical == 0


def test_zero_contractors_no_highest_risk() -> None:
    """No contractors → highest_risk_contractor is None."""
    result = compute_project_construction_risk(_inp())
    assert result.highest_risk_contractor is None


def test_zero_contractors_no_breach_reasons() -> None:
    """No contractors → top_breach_reasons is empty."""
    result = compute_project_construction_risk(_inp())
    assert result.top_breach_reasons == []


def test_zero_contractors_project_id_preserved() -> None:
    """project_id is passed through unchanged."""
    result = compute_project_construction_risk(_inp(project_id="PRJ-ZERO"))
    assert result.project_id == "PRJ-ZERO"


# ---------------------------------------------------------------------------
# All Normal contractors
# ---------------------------------------------------------------------------


def test_all_normal_score_zero() -> None:
    """All Normal contractors → score 0.0."""
    scorecards = [
        _sc("CTR-001", "Normal", 0),
        _sc("CTR-002", "Normal", 0),
        _sc("CTR-003", "Normal", 0),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.project_risk_score == 0.0


def test_all_normal_no_breach_reasons() -> None:
    """All Normal → no top_breach_reasons."""
    scorecards = [
        _sc("CTR-001", "Normal", 0, breach_reasons=["reason X"]),
        _sc("CTR-002", "Normal", 0, breach_reasons=["reason Y"]),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.top_breach_reasons == []


# ---------------------------------------------------------------------------
# Single contractor edge cases
# ---------------------------------------------------------------------------


def test_single_critical_contractor_score_100() -> None:
    """One Critical contractor → score 100.0."""
    scorecards = [_sc("CTR-001", "Critical", 3)]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.project_risk_score == 100.0


def test_single_watch_contractor_score_33() -> None:
    """One Watch contractor → score 33.3 (round(1/3 * 100, 1))."""
    scorecards = [_sc("CTR-001", "Watch", 1)]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.project_risk_score == 33.3


def test_single_escalate_contractor_score_66() -> None:
    """One Escalate contractor → score 66.7 (round(2/3 * 100, 1))."""
    scorecards = [_sc("CTR-001", "Escalate", 2)]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.project_risk_score == 66.7


# ---------------------------------------------------------------------------
# Score normalisation
# ---------------------------------------------------------------------------


def test_mixed_escalation_score_normalisation() -> None:
    """Watch=1 + Escalate=2 + Critical=3 → (6 / 9) * 100 = 66.7."""
    scorecards = [
        _sc("CTR-A", "Watch", 1),
        _sc("CTR-B", "Escalate", 2),
        _sc("CTR-C", "Critical", 3),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.project_risk_score == 66.7


def test_partial_escalation_score() -> None:
    """2 Normal + 1 Watch → (0 + 0 + 1) / (3 * 3) * 100 = 11.1."""
    scorecards = [
        _sc("CTR-001", "Normal", 0),
        _sc("CTR-002", "Normal", 0),
        _sc("CTR-003", "Watch", 1),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.project_risk_score == 11.1


# ---------------------------------------------------------------------------
# Distribution counts
# ---------------------------------------------------------------------------


def test_escalation_distribution_counts() -> None:
    """on_watch, escalated, critical counts are correct."""
    scorecards = [
        _sc("CTR-001", "Normal", 0),
        _sc("CTR-002", "Watch", 1),
        _sc("CTR-003", "Watch", 1),
        _sc("CTR-004", "Escalate", 2),
        _sc("CTR-005", "Critical", 3),
        _sc("CTR-006", "Critical", 3),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.contractors_total == 6
    assert result.contractors_on_watch == 2
    assert result.contractors_escalated == 1
    assert result.contractors_critical == 2


def test_normal_not_counted_in_distributions() -> None:
    """Normal contractors do not add to watch/escalated/critical counts."""
    scorecards = [_sc("CTR-001", "Normal", 0)]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.contractors_on_watch == 0
    assert result.contractors_escalated == 0
    assert result.contractors_critical == 0


# ---------------------------------------------------------------------------
# Top breach reasons
# ---------------------------------------------------------------------------


def test_breach_reasons_aggregated_from_non_normal() -> None:
    """Breach reasons from Watch/Escalate/Critical are aggregated."""
    scorecards = [
        _sc("CTR-001", "Watch", 1, breach_reasons=["delay rate elevated"]),
        _sc("CTR-002", "Escalate", 2, breach_reasons=["delay rate elevated", "cost overrun"]),
        _sc("CTR-003", "Critical", 3, breach_reasons=["reliability band Critical"]),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert "delay rate elevated" in result.top_breach_reasons
    assert "cost overrun" in result.top_breach_reasons
    assert "reliability band Critical" in result.top_breach_reasons


def test_most_common_breach_reason_appears_first() -> None:
    """The most frequent breach reason is first in top_breach_reasons."""
    scorecards = [
        _sc("CTR-001", "Watch", 1, breach_reasons=["common reason"]),
        _sc("CTR-002", "Watch", 1, breach_reasons=["common reason"]),
        _sc("CTR-003", "Escalate", 2, breach_reasons=["common reason", "rare reason"]),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.top_breach_reasons[0] == "common reason"


def test_breach_reasons_limited_to_top_limit() -> None:
    """top_breach_reasons never exceeds TOP_BREACH_REASON_LIMIT entries."""
    reasons = [f"reason_{i}" for i in range(TOP_BREACH_REASON_LIMIT + 3)]
    scorecards = [
        _sc(f"CTR-{i:03d}", "Critical", 3, breach_reasons=[reasons[i]])
        for i in range(len(reasons))
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert len(result.top_breach_reasons) <= TOP_BREACH_REASON_LIMIT


def test_normal_breach_reasons_excluded() -> None:
    """Breach reasons on Normal contractors are not counted."""
    scorecards = [
        _sc("CTR-001", "Normal", 0, breach_reasons=["should be ignored"]),
        _sc("CTR-002", "Watch", 1, breach_reasons=["real reason"]),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert "should be ignored" not in result.top_breach_reasons
    assert "real reason" in result.top_breach_reasons


# ---------------------------------------------------------------------------
# Highest-risk contractor selection
# ---------------------------------------------------------------------------


def test_highest_risk_contractor_by_escalation_score() -> None:
    """Contractor with highest escalation_score is selected."""
    scorecards = [
        _sc("CTR-001", "Normal", 0),
        _sc("CTR-002", "Watch", 1),
        _sc("CTR-003", "Critical", 3),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.highest_risk_contractor == "CTR-003"


def test_highest_risk_tiebreaker_by_reliability_index() -> None:
    """Among equal escalation scores, lower reliability_index wins (worst performer)."""
    scorecards = [
        _sc("CTR-001", "Critical", 3, reliability_index=70.0),
        _sc("CTR-002", "Critical", 3, reliability_index=30.0),
        _sc("CTR-003", "Critical", 3, reliability_index=50.0),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.highest_risk_contractor == "CTR-002"


def test_highest_risk_tiebreaker_none_reliability_index() -> None:
    """None reliability_index is treated as the worst (selected first in tie)."""
    scorecards = [
        _sc("CTR-001", "Critical", 3, reliability_index=50.0),
        _sc("CTR-002", "Critical", 3, reliability_index=None),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.highest_risk_contractor == "CTR-002"


def test_highest_risk_tiebreaker_by_contractor_id() -> None:
    """When both escalation_score and reliability_index are equal, alphabetically
    lowest contractor_id is selected for determinism."""
    scorecards = [
        _sc("CTR-BBB", "Watch", 1, reliability_index=50.0),
        _sc("CTR-AAA", "Watch", 1, reliability_index=50.0),
    ]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.highest_risk_contractor == "CTR-AAA"


def test_highest_risk_single_contractor() -> None:
    """Single contractor is always selected as highest_risk_contractor."""
    scorecards = [_sc("CTR-SOLO", "Normal", 0)]
    result = compute_project_construction_risk(_inp(scorecards=scorecards))
    assert result.highest_risk_contractor == "CTR-SOLO"


# ---------------------------------------------------------------------------
# Multiple projects independence
# ---------------------------------------------------------------------------


def test_multiple_project_inputs_independent() -> None:
    """Two different project_id inputs produce independent results."""
    scorecards_a = [_sc("CTR-001", "Critical", 3)]
    scorecards_b = [_sc("CTR-002", "Normal", 0)]

    result_a = compute_project_construction_risk(
        _inp(project_id="PRJ-A", scorecards=scorecards_a)
    )
    result_b = compute_project_construction_risk(
        _inp(project_id="PRJ-B", scorecards=scorecards_b)
    )

    assert result_a.project_id == "PRJ-A"
    assert result_a.project_risk_score == 100.0
    assert result_b.project_id == "PRJ-B"
    assert result_b.project_risk_score == 0.0
