"""
Tests for the Schedule Variance Analytics Engine.

PR-CONSTR-046 — Contractor Schedule Variance Analytics Engine

Validates:
- delay calculation: completion_date > target_date
- early completion: completion_date < target_date (on-time, not delayed)
- zero-day boundary: completion_date == target_date (on-time)
- large delay cases
- empty input
- missing dates (excluded from assessment)
- mixed milestones (some delayed, some on-time, some missing dates)
- delay_rate calculation
- average, median, max delay calculations
- single delayed milestone
"""

from datetime import date

import pytest

from app.modules.construction.schedule_variance_engine import (
    MilestoneVarianceInput,
    ScheduleVarianceResult,
    compute_schedule_variance,
)


# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------


def _milestone(
    mid: str = "M1",
    completion: date | None = None,
    target: date | None = None,
) -> MilestoneVarianceInput:
    return MilestoneVarianceInput(
        milestone_id=mid,
        completion_date=completion,
        target_date=target,
    )


# ---------------------------------------------------------------------------
# Empty / no-data cases
# ---------------------------------------------------------------------------


def test_empty_input_returns_zero_result() -> None:
    result = compute_schedule_variance([])
    assert result.assessed_milestones == 0
    assert result.delayed_milestones == 0
    assert result.total_delay_days == 0
    assert result.average_delay_days is None
    assert result.median_delay_days is None
    assert result.max_delay_days is None
    assert result.delay_rate is None


def test_all_missing_dates_returns_zero_result() -> None:
    milestones = [
        _milestone("M1"),
        _milestone("M2", completion=date(2024, 6, 1)),
        _milestone("M3", target=date(2024, 6, 1)),
    ]
    result = compute_schedule_variance(milestones)
    assert result.assessed_milestones == 0
    assert result.delayed_milestones == 0
    assert result.delay_rate is None


# ---------------------------------------------------------------------------
# Zero-day boundary (on-time)
# ---------------------------------------------------------------------------


def test_zero_day_delay_is_on_time() -> None:
    """completion_date == target_date must NOT count as delayed."""
    m = _milestone(
        "M1",
        completion=date(2024, 6, 15),
        target=date(2024, 6, 15),
    )
    result = compute_schedule_variance([m])
    assert result.assessed_milestones == 1
    assert result.delayed_milestones == 0
    assert result.total_delay_days == 0
    assert result.average_delay_days is None
    assert result.max_delay_days is None
    assert result.delay_rate == 0.0


# ---------------------------------------------------------------------------
# Early completion (negative delay → on-time)
# ---------------------------------------------------------------------------


def test_early_completion_not_delayed() -> None:
    """completion_date < target_date must NOT count as delayed."""
    m = _milestone(
        "M1",
        completion=date(2024, 6, 10),
        target=date(2024, 6, 15),
    )
    result = compute_schedule_variance([m])
    assert result.assessed_milestones == 1
    assert result.delayed_milestones == 0
    assert result.total_delay_days == 0
    assert result.average_delay_days is None
    assert result.delay_rate == 0.0


# ---------------------------------------------------------------------------
# Single delayed milestone
# ---------------------------------------------------------------------------


def test_single_delayed_milestone() -> None:
    m = _milestone(
        "M1",
        completion=date(2024, 7, 5),
        target=date(2024, 6, 30),
    )
    result = compute_schedule_variance([m])
    assert result.assessed_milestones == 1
    assert result.delayed_milestones == 1
    assert result.total_delay_days == 5
    assert result.average_delay_days == pytest.approx(5.0)
    assert result.median_delay_days == pytest.approx(5.0)
    assert result.max_delay_days == 5
    assert result.delay_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Large delay
# ---------------------------------------------------------------------------


def test_large_delay() -> None:
    m = _milestone(
        "M1",
        completion=date(2024, 9, 30),
        target=date(2024, 6, 1),
    )
    result = compute_schedule_variance([m])
    assert result.total_delay_days == 121
    assert result.max_delay_days == 121
    assert result.average_delay_days == pytest.approx(121.0)


# ---------------------------------------------------------------------------
# Multiple milestones
# ---------------------------------------------------------------------------


def test_mixed_milestones_delay_rate() -> None:
    """3 assessed, 2 delayed → delay_rate = 2/3."""
    milestones = [
        _milestone("M1", completion=date(2024, 7, 10), target=date(2024, 6, 30)),  # 10d late
        _milestone("M2", completion=date(2024, 6, 28), target=date(2024, 6, 30)),  # 2d early
        _milestone("M3", completion=date(2024, 8, 1), target=date(2024, 7, 1)),   # 31d late
    ]
    result = compute_schedule_variance(milestones)
    assert result.assessed_milestones == 3
    assert result.delayed_milestones == 2
    assert result.total_delay_days == 41
    assert result.delay_rate == pytest.approx(2 / 3)
    assert result.max_delay_days == 31


def test_average_delay_computed_over_delayed_only() -> None:
    """Average is computed only from delayed milestones, not all assessed."""
    milestones = [
        _milestone("M1", completion=date(2024, 7, 10), target=date(2024, 6, 30)),  # 10d late
        _milestone("M2", completion=date(2024, 6, 28), target=date(2024, 6, 30)),  # on-time
        _milestone("M3", completion=date(2024, 7, 20), target=date(2024, 6, 30)),  # 20d late
    ]
    result = compute_schedule_variance(milestones)
    # Average of 10 and 20 = 15.0
    assert result.average_delay_days == pytest.approx(15.0)


def test_median_delay_odd_count() -> None:
    milestones = [
        _milestone("M1", completion=date(2024, 7, 5), target=date(2024, 6, 30)),   # 5
        _milestone("M2", completion=date(2024, 7, 12), target=date(2024, 6, 30)),  # 12
        _milestone("M3", completion=date(2024, 7, 3), target=date(2024, 6, 30)),   # 3
    ]
    result = compute_schedule_variance(milestones)
    # Sorted delays: [3, 5, 12] → median = 5
    assert result.median_delay_days == pytest.approx(5.0)


def test_median_delay_even_count() -> None:
    milestones = [
        _milestone("M1", completion=date(2024, 7, 4), target=date(2024, 6, 30)),   # 4
        _milestone("M2", completion=date(2024, 7, 10), target=date(2024, 6, 30)),  # 10
    ]
    result = compute_schedule_variance(milestones)
    # Sorted delays: [4, 10] → median = 7.0
    assert result.median_delay_days == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# Missing dates excluded from assessment
# ---------------------------------------------------------------------------


def test_milestones_with_missing_dates_excluded() -> None:
    """Only milestones with both dates set are assessed."""
    milestones = [
        _milestone("M1", completion=date(2024, 7, 10), target=date(2024, 6, 30)),  # delayed
        _milestone("M2"),                                                             # no dates
        _milestone("M3", completion=date(2024, 6, 28)),                             # no target
        _milestone("M4", target=date(2024, 6, 30)),                                 # no completion
    ]
    result = compute_schedule_variance(milestones)
    assert result.assessed_milestones == 1
    assert result.delayed_milestones == 1
    assert result.delay_rate == 1.0


# ---------------------------------------------------------------------------
# All on-time (no delayed milestones)
# ---------------------------------------------------------------------------


def test_all_on_time() -> None:
    milestones = [
        _milestone("M1", completion=date(2024, 6, 28), target=date(2024, 6, 30)),
        _milestone("M2", completion=date(2024, 6, 30), target=date(2024, 6, 30)),
    ]
    result = compute_schedule_variance(milestones)
    assert result.assessed_milestones == 2
    assert result.delayed_milestones == 0
    assert result.total_delay_days == 0
    assert result.average_delay_days is None
    assert result.median_delay_days is None
    assert result.max_delay_days is None
    assert result.delay_rate == 0.0


# ---------------------------------------------------------------------------
# Integration: schedule_variance_engine via contractor_scorecard_engine
# ---------------------------------------------------------------------------


def test_compute_schedule_variance_integrates_with_scorecard() -> None:
    """Verify the scorecard engine correctly exposes variance fields."""
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
            completion_date=date(2024, 7, 10),
            target_date=date(2024, 6, 30),
        ),
        MilestoneScorecardData(
            milestone_id="M2",
            status="completed",
            completion_date=date(2024, 6, 28),
            target_date=date(2024, 6, 30),
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

    assert sc.average_delay_days == pytest.approx(10.0)
    assert sc.median_delay_days == pytest.approx(10.0)
    assert sc.max_delay_days == 10
    assert sc.delay_rate == pytest.approx(0.5)


def test_scorecard_no_dates_variance_fields_none() -> None:
    """Scorecard with no date information should have None variance fields."""
    from app.modules.construction.contractor_scorecard_engine import (
        ContractorScorecardInput,
        MilestoneScorecardData,
        compute_contractor_scorecard,
    )

    milestones = [
        MilestoneScorecardData(milestone_id="M1", status="pending"),
        MilestoneScorecardData(milestone_id="M2", status="in_progress"),
    ]
    inp = ContractorScorecardInput(
        contractor_id="CTR-1",
        contractor_name="Test Corp",
        milestones=milestones,
        packages=[],
        risk_signal_count=0,
    )
    sc = compute_contractor_scorecard(inp)

    assert sc.average_delay_days is None
    assert sc.median_delay_days is None
    assert sc.max_delay_days is None
    assert sc.delay_rate is None
