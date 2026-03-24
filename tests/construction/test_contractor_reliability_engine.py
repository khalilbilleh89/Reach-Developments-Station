"""
Tests for the Contractor Reliability Index Engine.

PR-CONSTR-048 — Contractor Reliability Index & Ranking Engine

Validates:
- empty / no-evidence input returns Elite band at Low confidence
- excellent contractor (high on_time_rate, no cost overrun, no risk)
- strong but not elite contractor (good but not perfect metrics)
- contractor with severe delay and cost overrun reaches Critical band
- high risk signal penalties drive score down
- confidence banding based on evidence volume (Low/Medium/High)
- deterministic equal-score tie-breaking in scope ranking
- score is always bounded 0–100
- schedule discipline gates on assessed_milestones (no temporal evidence → 100)
- cost discipline gates on cost_overrun_rate is None → 100
- integration with contractor scorecard engine produces reliability fields
"""

from __future__ import annotations

import pytest

from app.modules.construction.contractor_reliability_engine import (
    BAND_CRITICAL,
    BAND_ELITE,
    BAND_STRONG,
    BAND_WATCH,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    ContractorReliabilityInput,
    compute_contractor_reliability,
)


# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------


def _inp(
    on_time_rate: float | None = None,
    delay_rate: float | None = None,
    average_delay_days: float | None = None,
    average_cost_variance_pct: float | None = None,
    cost_overrun_rate: float | None = None,
    risk_signal_count: int = 0,
    assessed_milestones: int = 0,
    assessed_packages: int = 0,
) -> ContractorReliabilityInput:
    return ContractorReliabilityInput(
        on_time_rate=on_time_rate,
        delay_rate=delay_rate,
        average_delay_days=average_delay_days,
        average_cost_variance_pct=average_cost_variance_pct,
        cost_overrun_rate=cost_overrun_rate,
        risk_signal_count=risk_signal_count,
        assessed_milestones=assessed_milestones,
        assessed_packages=assessed_packages,
    )


# ---------------------------------------------------------------------------
# Empty / no-evidence cases
# ---------------------------------------------------------------------------


def test_no_evidence_returns_elite_low_confidence() -> None:
    """No metrics → all components default to 100 → Elite band, Low confidence."""
    result = compute_contractor_reliability(_inp())
    assert result.reliability_index == 100.0
    assert result.reliability_band == BAND_ELITE
    assert result.reliability_confidence == CONFIDENCE_LOW


def test_no_evidence_ranking_sort_score_equals_index() -> None:
    """ranking_sort_score equals reliability_index."""
    result = compute_contractor_reliability(_inp())
    assert result.ranking_sort_score == result.reliability_index


def test_no_risk_signals_no_packages_no_milestones_is_100() -> None:
    """Contractor with no data has no negative evidence → 100.0."""
    result = compute_contractor_reliability(
        _inp(risk_signal_count=0, assessed_milestones=0, assessed_packages=0)
    )
    assert result.reliability_index == 100.0


# ---------------------------------------------------------------------------
# Excellent contractor (Elite band)
# ---------------------------------------------------------------------------


def test_excellent_contractor_elite_band() -> None:
    """100% on-time, no cost overrun, no risk signals, broad evidence → Elite + High."""
    result = compute_contractor_reliability(
        _inp(
            on_time_rate=1.0,
            delay_rate=0.0,
            cost_overrun_rate=0.0,
            average_cost_variance_pct=0.0,
            risk_signal_count=0,
            assessed_milestones=15,
            assessed_packages=6,
        )
    )
    assert result.reliability_index is not None
    assert result.reliability_index >= 85.0
    assert result.reliability_band == BAND_ELITE
    assert result.reliability_confidence == CONFIDENCE_HIGH


def test_excellent_contractor_score_bounded_at_100() -> None:
    """Score must never exceed 100."""
    result = compute_contractor_reliability(
        _inp(
            on_time_rate=1.0,
            delay_rate=0.0,
            cost_overrun_rate=0.0,
            risk_signal_count=0,
            assessed_milestones=20,
            assessed_packages=10,
        )
    )
    assert result.reliability_index is not None
    assert result.reliability_index <= 100.0


# ---------------------------------------------------------------------------
# Strong but not Elite contractor
# ---------------------------------------------------------------------------


def test_strong_contractor_band() -> None:
    """Good on-time, small cost overrun, no risk → Strong band."""
    result = compute_contractor_reliability(
        _inp(
            on_time_rate=0.85,
            delay_rate=0.1,
            cost_overrun_rate=0.15,
            average_cost_variance_pct=3.0,
            risk_signal_count=0,
            assessed_milestones=12,
            assessed_packages=5,
        )
    )
    assert result.reliability_index is not None
    assert 70.0 <= result.reliability_index < 85.0
    assert result.reliability_band == BAND_STRONG


def test_moderate_performance_watch_band() -> None:
    """50% on-time, 40% overrun, 1 risk signal → Watch band."""
    result = compute_contractor_reliability(
        _inp(
            on_time_rate=0.5,
            delay_rate=0.4,
            cost_overrun_rate=0.4,
            average_cost_variance_pct=10.0,
            risk_signal_count=1,
            assessed_milestones=10,
            assessed_packages=5,
        )
    )
    assert result.reliability_index is not None
    assert 50.0 <= result.reliability_index < 70.0
    assert result.reliability_band == BAND_WATCH


# ---------------------------------------------------------------------------
# Severe delay and cost overrun (Critical band)
# ---------------------------------------------------------------------------


def test_severe_delay_and_cost_overrun_critical_band() -> None:
    """0% on-time, 100% overrun, 2 risk signals → Critical band."""
    result = compute_contractor_reliability(
        _inp(
            on_time_rate=0.0,
            delay_rate=1.0,
            cost_overrun_rate=1.0,
            average_cost_variance_pct=50.0,
            risk_signal_count=2,
            assessed_milestones=10,
            assessed_packages=4,
        )
    )
    assert result.reliability_index is not None
    assert result.reliability_index < 50.0
    assert result.reliability_band == BAND_CRITICAL


def test_all_delayed_no_cost_data() -> None:
    """100% delayed milestones, no packages → overall Watch band (~60 index)."""
    result = compute_contractor_reliability(
        _inp(
            on_time_rate=0.0,
            delay_rate=1.0,
            assessed_milestones=8,
            assessed_packages=0,
        )
    )
    assert result.reliability_index is not None
    # schedule_discipline = 0 - 20 penalty = 0 (clamped), cost=100, risk=100
    # index = 0*0.40 + 100*0.35 + 100*0.25 = 60.0 → Watch band
    assert result.reliability_index == pytest.approx(60.0, abs=0.1)
    assert result.reliability_band == BAND_WATCH


def test_no_on_time_with_delay_rate_only() -> None:
    """on_time_rate None but delay_rate available triggers secondary path."""
    result = compute_contractor_reliability(
        _inp(
            on_time_rate=None,
            delay_rate=0.8,
            assessed_milestones=5,
        )
    )
    # schedule_discipline = (1 - 0.8) * 100 - min(20, 80) = 20 - 20 = 0
    # cost = 100, risk = 100
    # index = 0 * 0.40 + 100 * 0.35 + 100 * 0.25 = 60.0
    assert result.reliability_index is not None
    assert result.reliability_index == pytest.approx(60.0, abs=0.1)


# ---------------------------------------------------------------------------
# Risk signal penalties
# ---------------------------------------------------------------------------


def test_single_risk_signal_reduces_score() -> None:
    """One HIGH-severity signal deducts 15 points from risk_load."""
    no_risk = compute_contractor_reliability(
        _inp(risk_signal_count=0, assessed_milestones=10, assessed_packages=5)
    )
    one_risk = compute_contractor_reliability(
        _inp(risk_signal_count=1, assessed_milestones=10, assessed_packages=5)
    )
    assert no_risk.reliability_index is not None
    assert one_risk.reliability_index is not None
    assert one_risk.reliability_index < no_risk.reliability_index
    # Difference should be 15 * RISK_LOAD_WEIGHT = 15 * 0.25 = 3.75
    diff = no_risk.reliability_index - one_risk.reliability_index
    assert diff == pytest.approx(3.75, abs=0.01)


def test_many_risk_signals_floors_at_zero() -> None:
    """7+ risk signals → risk_load = 0 (floor), not negative."""
    result = compute_contractor_reliability(
        _inp(risk_signal_count=7, assessed_milestones=10, assessed_packages=5)
    )
    assert result.reliability_index is not None
    assert result.reliability_index >= 0.0


def test_risk_score_floor_zero() -> None:
    """Even with extreme risk signal count, index stays >= 0."""
    result = compute_contractor_reliability(
        _inp(risk_signal_count=100)
    )
    assert result.reliability_index is not None
    assert result.reliability_index >= 0.0


# ---------------------------------------------------------------------------
# Confidence banding
# ---------------------------------------------------------------------------


def test_confidence_low_no_evidence() -> None:
    result = compute_contractor_reliability(_inp())
    assert result.reliability_confidence == CONFIDENCE_LOW


def test_confidence_low_below_thresholds() -> None:
    result = compute_contractor_reliability(
        _inp(assessed_milestones=2, assessed_packages=1)
    )
    assert result.reliability_confidence == CONFIDENCE_LOW


def test_confidence_medium_by_milestones() -> None:
    result = compute_contractor_reliability(
        _inp(assessed_milestones=3, assessed_packages=0)
    )
    assert result.reliability_confidence == CONFIDENCE_MEDIUM


def test_confidence_medium_by_packages() -> None:
    result = compute_contractor_reliability(
        _inp(assessed_milestones=0, assessed_packages=2)
    )
    assert result.reliability_confidence == CONFIDENCE_MEDIUM


def test_confidence_high_by_milestones() -> None:
    result = compute_contractor_reliability(
        _inp(assessed_milestones=10, assessed_packages=0)
    )
    assert result.reliability_confidence == CONFIDENCE_HIGH


def test_confidence_high_by_packages() -> None:
    result = compute_contractor_reliability(
        _inp(assessed_milestones=0, assessed_packages=5)
    )
    assert result.reliability_confidence == CONFIDENCE_HIGH


def test_confidence_high_both_thresholds_met() -> None:
    result = compute_contractor_reliability(
        _inp(assessed_milestones=15, assessed_packages=8)
    )
    assert result.reliability_confidence == CONFIDENCE_HIGH


# ---------------------------------------------------------------------------
# Schedule discipline gating on assessed_milestones
# ---------------------------------------------------------------------------


def test_no_temporal_evidence_schedule_discipline_100() -> None:
    """When assessed_milestones == 0, schedule discipline is 100 regardless of on_time_rate."""
    # A completed milestone with on_time_rate=0.0 but no date evidence
    result_no_evidence = compute_contractor_reliability(
        _inp(on_time_rate=0.0, delay_rate=None, assessed_milestones=0)
    )
    result_full_evidence = compute_contractor_reliability(
        _inp(on_time_rate=1.0, delay_rate=0.0, assessed_milestones=10)
    )
    # Both should have perfect schedule discipline → same index
    assert result_no_evidence.reliability_index == result_full_evidence.reliability_index


def test_zero_on_time_with_date_evidence_penalizes() -> None:
    """0% on_time_rate with assessed milestones is a real penalty."""
    good = compute_contractor_reliability(
        _inp(on_time_rate=1.0, assessed_milestones=10)
    )
    bad = compute_contractor_reliability(
        _inp(on_time_rate=0.0, assessed_milestones=10)
    )
    assert good.reliability_index is not None
    assert bad.reliability_index is not None
    assert bad.reliability_index < good.reliability_index


# ---------------------------------------------------------------------------
# Cost discipline
# ---------------------------------------------------------------------------


def test_cost_discipline_no_packages_is_100() -> None:
    """When cost_overrun_rate is None → cost_discipline = 100."""
    result = compute_contractor_reliability(
        _inp(cost_overrun_rate=None, assessed_packages=0)
    )
    assert result.reliability_index == 100.0


def test_cost_variance_penalty_applied() -> None:
    """average_cost_variance_pct applies a secondary cost discipline penalty."""
    no_variance = compute_contractor_reliability(
        _inp(cost_overrun_rate=0.0, average_cost_variance_pct=0.0, assessed_packages=3)
    )
    with_variance = compute_contractor_reliability(
        _inp(cost_overrun_rate=0.0, average_cost_variance_pct=40.0, assessed_packages=3)
    )
    assert no_variance.reliability_index is not None
    assert with_variance.reliability_index is not None
    assert with_variance.reliability_index < no_variance.reliability_index


def test_negative_cost_variance_not_penalised() -> None:
    """Under-budget (negative average_cost_variance_pct) should not apply a penalty."""
    under_budget = compute_contractor_reliability(
        _inp(cost_overrun_rate=0.0, average_cost_variance_pct=-10.0, assessed_packages=3)
    )
    on_budget = compute_contractor_reliability(
        _inp(cost_overrun_rate=0.0, average_cost_variance_pct=0.0, assessed_packages=3)
    )
    assert under_budget.reliability_index == on_budget.reliability_index


# ---------------------------------------------------------------------------
# Score bounds
# ---------------------------------------------------------------------------


def test_score_always_0_to_100() -> None:
    """Verify multiple extreme inputs all produce scores within [0, 100]."""
    test_cases = [
        _inp(),
        _inp(on_time_rate=0.0, delay_rate=1.0, cost_overrun_rate=1.0,
             average_cost_variance_pct=200.0, risk_signal_count=10,
             assessed_milestones=20, assessed_packages=10),
        _inp(on_time_rate=1.0, delay_rate=0.0, cost_overrun_rate=0.0,
             average_cost_variance_pct=-50.0, risk_signal_count=0,
             assessed_milestones=50, assessed_packages=20),
    ]
    for inp in test_cases:
        result = compute_contractor_reliability(inp)
        assert result.reliability_index is not None
        assert 0.0 <= result.reliability_index <= 100.0


# ---------------------------------------------------------------------------
# Deterministic equal-score tie behavior
# ---------------------------------------------------------------------------


def test_equal_inputs_produce_equal_scores() -> None:
    """Identical inputs must produce identical reliability scores."""
    inp = _inp(
        on_time_rate=0.8,
        delay_rate=0.2,
        cost_overrun_rate=0.2,
        risk_signal_count=1,
        assessed_milestones=10,
        assessed_packages=5,
    )
    r1 = compute_contractor_reliability(inp)
    r2 = compute_contractor_reliability(inp)
    assert r1.reliability_index == r2.reliability_index
    assert r1.reliability_band == r2.reliability_band
    assert r1.reliability_confidence == r2.reliability_confidence


def test_scope_ranking_tie_broken_by_contractor_id() -> None:
    """Equal reliability inputs → rank is deterministic by contractor_id ascending."""
    from app.modules.construction.contractor_scorecard_engine import (
        ContractorScorecardInput,
        compute_scope_contractor_ranking,
    )

    # Both contractors have identical inputs (no evidence) → equal reliability_index
    inp_z = ContractorScorecardInput(
        contractor_id="CTR-Z",
        contractor_name="Zeta",
        milestones=[],
        packages=[],
        risk_signal_count=0,
    )
    inp_a = ContractorScorecardInput(
        contractor_id="CTR-A",
        contractor_name="Alpha",
        milestones=[],
        packages=[],
        risk_signal_count=0,
    )
    rows = compute_scope_contractor_ranking([inp_z, inp_a])
    # CTR-A < CTR-Z alphabetically → CTR-A ranked first
    assert rows[0].contractor_id == "CTR-A"
    assert rows[1].contractor_id == "CTR-Z"


# ---------------------------------------------------------------------------
# Integration with contractor scorecard engine
# ---------------------------------------------------------------------------


def test_scorecard_has_reliability_fields() -> None:
    """ContractorScorecard produced by compute_contractor_scorecard has reliability fields."""
    from datetime import date

    from app.modules.construction.contractor_scorecard_engine import (
        ContractorScorecardInput,
        MilestoneScorecardData,
        compute_contractor_scorecard,
    )

    milestones = [
        MilestoneScorecardData(
            milestone_id="M1",
            status="completed",
            completion_date=date(2024, 3, 1),
            target_date=date(2024, 3, 1),
        ),
        MilestoneScorecardData(
            milestone_id="M2",
            status="completed",
            completion_date=date(2024, 4, 1),
            target_date=date(2024, 3, 28),  # 4 days late
        ),
    ]
    inp = ContractorScorecardInput(
        contractor_id="CTR-1",
        contractor_name="Test Corp",
        milestones=milestones,
        packages=[],
        risk_signal_count=0,
    )
    sc = compute_contractor_scorecard(inp)

    assert sc.reliability_index is not None
    assert 0.0 <= sc.reliability_index <= 100.0
    assert sc.reliability_band in {BAND_ELITE, BAND_STRONG, BAND_WATCH, BAND_CRITICAL}
    assert sc.reliability_confidence in {CONFIDENCE_LOW, CONFIDENCE_MEDIUM, CONFIDENCE_HIGH}
    assert sc.ranking_sort_score == sc.reliability_index


def test_scorecard_reliability_elite_for_perfect_delivery() -> None:
    """Contractor with all on-time milestones gets Elite band."""
    from datetime import date

    from app.modules.construction.contractor_scorecard_engine import (
        ContractorScorecardInput,
        MilestoneScorecardData,
        compute_contractor_scorecard,
    )

    milestones = [
        MilestoneScorecardData(
            milestone_id=f"M{i}",
            status="completed",
            completion_date=date(2024, i % 12 + 1, 15),
            target_date=date(2024, i % 12 + 1, 20),  # always early
        )
        for i in range(1, 13)
    ]
    inp = ContractorScorecardInput(
        contractor_id="CTR-ELITE",
        contractor_name="Elite Corp",
        milestones=milestones,
        packages=[],
        risk_signal_count=0,
    )
    sc = compute_contractor_scorecard(inp)

    assert sc.reliability_band == BAND_ELITE
    assert sc.reliability_index is not None
    assert sc.reliability_index >= 85.0


def test_scorecard_reliability_critical_for_worst_case() -> None:
    """Contractor with all delayed milestones and high risk → Critical or Watch."""
    from datetime import date

    from decimal import Decimal

    from app.modules.construction.contractor_scorecard_engine import (
        ContractorScorecardInput,
        MilestoneScorecardData,
        PackageScorecardData,
        compute_contractor_scorecard,
    )

    milestones = [
        MilestoneScorecardData(
            milestone_id=f"M{i}",
            status="completed",
            completion_date=date(2024, 3, 30),
            target_date=date(2024, 1, 1),  # very late
        )
        for i in range(1, 6)
    ]
    packages = [
        PackageScorecardData(
            package_id=f"P{i}",
            status="completed",
            planned_value=Decimal("100000"),
            awarded_value=Decimal("160000"),  # 60% overrun
        )
        for i in range(1, 4)
    ]
    inp = ContractorScorecardInput(
        contractor_id="CTR-WORST",
        contractor_name="Problem Corp",
        milestones=milestones,
        packages=packages,
        risk_signal_count=3,
    )
    sc = compute_contractor_scorecard(inp)

    assert sc.reliability_band in {BAND_CRITICAL, BAND_WATCH}
    assert sc.reliability_index is not None
    assert sc.reliability_index < 70.0
