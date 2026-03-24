"""
Tests for the Contractor Scorecard Engine.

PR-CONSTR-045 — Contractor Scorecards & Trend Analytics

Validates:
- delayed ratio calculation
- overrun ratio calculation
- on-time completion ratio
- combined performance score composition
- ranking tie-break behavior (deterministic by contractor_id)
- trend delta calculations
- contractor milestone deduplication across packages
- empty / edge-case inputs
- scoring floor (never below 0)
- trend direction derivation
"""

from datetime import date
from decimal import Decimal

import pytest

from app.modules.construction.contractor_scorecard_engine import (
    TREND_MIN_DELTA,
    ContractorScorecardInput,
    ContractorTrendPoint,
    MilestoneScorecardData,
    PackageScorecardData,
    _determine_trend_direction,
    compute_contractor_scorecard,
    compute_contractor_trend,
    compute_scope_contractor_ranking,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _milestone(
    mid: str = "M1",
    status: str = "pending",
    planned_cost: str | None = None,
    actual_cost: str | None = None,
    completion_date: date | None = None,
) -> MilestoneScorecardData:
    return MilestoneScorecardData(
        milestone_id=mid,
        status=status,
        planned_cost=Decimal(planned_cost) if planned_cost is not None else None,
        actual_cost=Decimal(actual_cost) if actual_cost is not None else None,
        completion_date=completion_date,
    )


def _package(pkg_id: str = "PKG-1", status: str = "draft") -> PackageScorecardData:
    return PackageScorecardData(package_id=pkg_id, status=status)


def _contractor(
    cid: str = "CTR-1",
    name: str = "Test Corp",
    milestones: list[MilestoneScorecardData] | None = None,
    packages: list[PackageScorecardData] | None = None,
    ratio_alert_count: int = 0,
) -> ContractorScorecardInput:
    return ContractorScorecardInput(
        contractor_id=cid,
        contractor_name=name,
        milestones=milestones or [],
        packages=packages or [],
        ratio_alert_count=ratio_alert_count,
    )


# ---------------------------------------------------------------------------
# Empty / trivial cases
# ---------------------------------------------------------------------------


def test_empty_contractor_scorecard_defaults() -> None:
    sc = compute_contractor_scorecard(_contractor())
    assert sc.total_milestones == 0
    assert sc.completed_milestones == 0
    assert sc.delayed_milestones == 0
    assert sc.delayed_ratio is None
    assert sc.completion_ratio is None
    assert sc.overrun_ratio is None
    assert sc.avg_cost_variance_percent is None
    assert sc.active_packages == 0
    assert sc.completed_packages == 0
    assert sc.ratio_alert_count == 0
    # All components should be 100 with no negative data
    assert sc.schedule_score == 100.0
    assert sc.cost_score == 100.0
    assert sc.risk_score == 100.0
    assert sc.performance_score == 100.0


# ---------------------------------------------------------------------------
# Delayed ratio calculation
# ---------------------------------------------------------------------------


def test_delayed_ratio_one_of_two() -> None:
    milestones = [
        _milestone("M1", status="delayed"),
        _milestone("M2", status="completed"),
    ]
    sc = compute_contractor_scorecard(_contractor(milestones=milestones))
    assert sc.total_milestones == 2
    assert sc.delayed_milestones == 1
    assert sc.delayed_ratio == pytest.approx(0.5)


def test_delayed_ratio_all_delayed() -> None:
    milestones = [_milestone(f"M{i}", status="delayed") for i in range(4)]
    sc = compute_contractor_scorecard(_contractor(milestones=milestones))
    assert sc.delayed_ratio == pytest.approx(1.0)
    assert sc.schedule_score == pytest.approx(0.0)


def test_delayed_ratio_none_when_no_milestones() -> None:
    sc = compute_contractor_scorecard(_contractor())
    assert sc.delayed_ratio is None


def test_delayed_ratio_zero_when_no_delays() -> None:
    milestones = [_milestone("M1", status="completed"), _milestone("M2", status="pending")]
    sc = compute_contractor_scorecard(_contractor(milestones=milestones))
    assert sc.delayed_milestones == 0
    assert sc.delayed_ratio == pytest.approx(0.0)
    assert sc.schedule_score == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Overrun ratio calculation
# ---------------------------------------------------------------------------


def test_overrun_ratio_one_of_two_costed() -> None:
    milestones = [
        _milestone("M1", planned_cost="1000", actual_cost="1200"),  # over budget
        _milestone("M2", planned_cost="1000", actual_cost="900"),   # on budget
    ]
    sc = compute_contractor_scorecard(_contractor(milestones=milestones))
    assert sc.assessed_cost_milestones == 2
    assert sc.over_budget_milestones == 1
    assert sc.overrun_ratio == pytest.approx(0.5)


def test_overrun_ratio_none_when_no_costed_milestones() -> None:
    milestones = [_milestone("M1", status="pending")]
    sc = compute_contractor_scorecard(_contractor(milestones=milestones))
    assert sc.overrun_ratio is None
    assert sc.cost_score == 100.0


def test_overrun_ratio_ignores_milestones_without_both_costs() -> None:
    milestones = [
        _milestone("M1", planned_cost="1000", actual_cost=None),  # no actual
        _milestone("M2", planned_cost=None, actual_cost="500"),   # no planned
        _milestone("M3", planned_cost="1000", actual_cost="1200"),  # over budget
    ]
    sc = compute_contractor_scorecard(_contractor(milestones=milestones))
    assert sc.assessed_cost_milestones == 1
    assert sc.over_budget_milestones == 1
    assert sc.overrun_ratio == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Completion ratio calculation
# ---------------------------------------------------------------------------


def test_completion_ratio_some_completed() -> None:
    milestones = [
        _milestone("M1", status="completed"),
        _milestone("M2", status="pending"),
        _milestone("M3", status="delayed"),
        _milestone("M4", status="completed"),
    ]
    sc = compute_contractor_scorecard(_contractor(milestones=milestones))
    assert sc.completed_milestones == 2
    assert sc.completion_ratio == pytest.approx(0.5)


def test_completion_ratio_none_when_no_milestones() -> None:
    sc = compute_contractor_scorecard(_contractor())
    assert sc.completion_ratio is None


def test_completion_ratio_zero_when_no_completions() -> None:
    milestones = [_milestone("M1", status="pending")]
    sc = compute_contractor_scorecard(_contractor(milestones=milestones))
    assert sc.completion_ratio == pytest.approx(0.0)


def test_completion_ratio_one_when_all_completed() -> None:
    milestones = [
        _milestone("M1", status="completed"),
        _milestone("M2", status="completed"),
    ]
    sc = compute_contractor_scorecard(_contractor(milestones=milestones))
    assert sc.completed_milestones == 2
    assert sc.completion_ratio == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Combined performance score composition
# ---------------------------------------------------------------------------


def test_performance_score_is_weighted_composite() -> None:
    # 2 of 4 delayed (50 % delay) → schedule_score = 50.0
    # 0 overrun → cost_score = 100.0
    # 0 alerts → risk_score = 100.0
    # performance = 50*0.4 + 100*0.4 + 100*0.2 = 80.0
    milestones = [
        _milestone("M1", status="delayed"),
        _milestone("M2", status="delayed"),
        _milestone("M3", status="completed"),
        _milestone("M4", status="completed"),
    ]
    sc = compute_contractor_scorecard(_contractor(milestones=milestones))
    assert sc.schedule_score == pytest.approx(50.0)
    assert sc.cost_score == pytest.approx(100.0)
    assert sc.risk_score == pytest.approx(100.0)
    assert sc.performance_score == pytest.approx(80.0)


def test_risk_score_deducted_per_high_alert() -> None:
    sc = compute_contractor_scorecard(_contractor(ratio_alert_count=3))
    # 100 - 3*10 = 70
    assert sc.risk_score == pytest.approx(70.0)


def test_risk_score_floors_at_zero() -> None:
    sc = compute_contractor_scorecard(_contractor(ratio_alert_count=15))
    assert sc.risk_score == pytest.approx(0.0)


def test_performance_score_floors_at_zero() -> None:
    # 100 % delay + 100 % overrun + 15 alerts
    milestones = [
        _milestone("M1", status="delayed", planned_cost="100", actual_cost="200"),
    ]
    sc = compute_contractor_scorecard(
        _contractor(milestones=milestones, ratio_alert_count=15)
    )
    assert sc.performance_score >= 0.0


# ---------------------------------------------------------------------------
# Milestone deduplication
# ---------------------------------------------------------------------------


def test_milestone_deduplication_across_packages() -> None:
    # Same milestone_id appearing twice (as if linked to two packages)
    milestones = [
        _milestone("M1", status="delayed"),
        _milestone("M1", status="delayed"),  # duplicate
        _milestone("M2", status="completed"),
    ]
    sc = compute_contractor_scorecard(_contractor(milestones=milestones))
    # Should count only 2 unique milestones
    assert sc.total_milestones == 2
    assert sc.delayed_milestones == 1


# ---------------------------------------------------------------------------
# Package counts
# ---------------------------------------------------------------------------


def test_active_package_count() -> None:
    packages = [
        _package("P1", status="tendering"),
        _package("P2", status="evaluation"),
        _package("P3", status="awarded"),
        _package("P4", status="draft"),       # not active
        _package("P5", status="completed"),   # not active
    ]
    sc = compute_contractor_scorecard(_contractor(packages=packages))
    assert sc.active_packages == 3
    assert sc.completed_packages == 1


# ---------------------------------------------------------------------------
# Ranking tie-break behavior
# ---------------------------------------------------------------------------


def test_ranking_order_by_performance_score_desc() -> None:
    # CTR-A: no delays → score ~100
    # CTR-B: all delayed → score ~0
    inp_a = _contractor("CTR-A", "Alpha", milestones=[_milestone("M1", status="completed")])
    inp_b = _contractor("CTR-B", "Beta", milestones=[_milestone("M2", status="delayed")])
    rows = compute_scope_contractor_ranking([inp_a, inp_b])
    assert rows[0].contractor_id == "CTR-A"
    assert rows[1].contractor_id == "CTR-B"
    assert rows[0].contractor_rank == 1
    assert rows[1].contractor_rank == 2


def test_ranking_tie_break_by_contractor_id_ascending() -> None:
    # Both contractors have identical inputs → tie broken by contractor_id
    inp_a = _contractor("CTR-Z", "Zeta")
    inp_b = _contractor("CTR-A", "Alpha")
    rows = compute_scope_contractor_ranking([inp_a, inp_b])
    assert rows[0].contractor_id == "CTR-A"
    assert rows[1].contractor_id == "CTR-Z"


def test_ranking_empty_scope_returns_empty_list() -> None:
    rows = compute_scope_contractor_ranking([])
    assert rows == []


def test_ranking_single_contractor_rank_one() -> None:
    rows = compute_scope_contractor_ranking([_contractor()])
    assert len(rows) == 1
    assert rows[0].contractor_rank == 1


# ---------------------------------------------------------------------------
# Trend delta calculations
# ---------------------------------------------------------------------------


def test_trend_empty_no_completion_dates() -> None:
    # Milestones without completion_date → no trend points
    milestones = [_milestone("M1", status="delayed")]
    data = _contractor(milestones=milestones)
    trend = compute_contractor_trend(data)
    assert trend.periods_analysed == 0
    assert trend.trend_points == []
    assert trend.trend_direction == "stable"


def test_trend_single_period_no_delta() -> None:
    milestones = [
        _milestone("M1", status="completed", completion_date=date(2024, 1, 15)),
        _milestone("M2", status="completed", completion_date=date(2024, 1, 20)),
    ]
    data = _contractor(milestones=milestones)
    trend = compute_contractor_trend(data)
    assert trend.periods_analysed == 1
    assert trend.trend_points[0].period_label == "2024-01"
    assert trend.trend_points[0].score_delta is None
    assert trend.trend_direction == "stable"


def test_trend_improving_direction() -> None:
    # Period 1: all delayed → low score
    # Period 2: all completed → high score  →  delta should be large positive
    milestones = [
        _milestone("M1", status="delayed", completion_date=date(2024, 1, 15)),
        _milestone("M2", status="completed", completion_date=date(2024, 2, 15)),
    ]
    data = _contractor(milestones=milestones)
    trend = compute_contractor_trend(data)
    assert trend.periods_analysed == 2
    last_delta = trend.trend_points[-1].score_delta
    assert last_delta is not None
    assert last_delta >= TREND_MIN_DELTA
    assert trend.trend_direction == "improving"


def test_trend_deteriorating_direction() -> None:
    # Period 1: all completed → high score
    # Period 2: all delayed → low score  →  delta should be large negative
    milestones = [
        _milestone("M1", status="completed", completion_date=date(2024, 1, 15)),
        _milestone("M2", status="delayed", completion_date=date(2024, 2, 15)),
    ]
    data = _contractor(milestones=milestones)
    trend = compute_contractor_trend(data)
    assert trend.periods_analysed == 2
    last_delta = trend.trend_points[-1].score_delta
    assert last_delta is not None
    assert last_delta <= -TREND_MIN_DELTA
    assert trend.trend_direction == "deteriorating"


def test_trend_stable_when_small_change() -> None:
    milestones = [
        _milestone("M1", status="completed", completion_date=date(2024, 1, 15)),
        _milestone("M2", status="completed", completion_date=date(2024, 2, 15)),
    ]
    data = _contractor(milestones=milestones)
    trend = compute_contractor_trend(data)
    # Both periods have the same inputs → delta == 0 → stable
    assert trend.trend_direction == "stable"


def test_trend_points_are_chronologically_sorted() -> None:
    milestones = [
        _milestone("M1", status="completed", completion_date=date(2024, 3, 1)),
        _milestone("M2", status="completed", completion_date=date(2024, 1, 1)),
        _milestone("M3", status="completed", completion_date=date(2024, 2, 1)),
    ]
    data = _contractor(milestones=milestones)
    trend = compute_contractor_trend(data)
    labels = [tp.period_label for tp in trend.trend_points]
    assert labels == sorted(labels)


# ---------------------------------------------------------------------------
# Determine trend direction helper
# ---------------------------------------------------------------------------


def test_determine_trend_direction_empty() -> None:
    assert _determine_trend_direction([]) == "stable"


def test_determine_trend_direction_one_point() -> None:
    pt = ContractorTrendPoint(
        period_label="2024-01",
        total_milestones=1,
        completed_milestones=1,
        delayed_milestones=0,
        over_budget_milestones=0,
        delayed_ratio=0.0,
        overrun_ratio=None,
        performance_score=90.0,
        score_delta=None,
    )
    assert _determine_trend_direction([pt]) == "stable"


def test_determine_trend_direction_improving_exact_threshold() -> None:
    pt1 = ContractorTrendPoint(
        period_label="2024-01",
        total_milestones=1, completed_milestones=0, delayed_milestones=1,
        over_budget_milestones=0, delayed_ratio=1.0, overrun_ratio=None,
        performance_score=60.0, score_delta=None,
    )
    pt2 = ContractorTrendPoint(
        period_label="2024-02",
        total_milestones=1, completed_milestones=1, delayed_milestones=0,
        over_budget_milestones=0, delayed_ratio=0.0, overrun_ratio=None,
        performance_score=60.0 + TREND_MIN_DELTA, score_delta=TREND_MIN_DELTA,
    )
    assert _determine_trend_direction([pt1, pt2]) == "improving"


def test_trend_overall_score_reflects_all_milestones() -> None:
    # Mix of completed and delayed across periods
    milestones = [
        _milestone("M1", status="completed", completion_date=date(2024, 1, 15)),
        _milestone("M2", status="delayed", completion_date=date(2024, 2, 15)),
    ]
    data = _contractor(milestones=milestones)
    trend = compute_contractor_trend(data)
    # overall_score should match the scorecard computed from all milestones
    from app.modules.construction.contractor_scorecard_engine import compute_contractor_scorecard
    sc = compute_contractor_scorecard(data)
    assert trend.overall_score == pytest.approx(sc.performance_score)
