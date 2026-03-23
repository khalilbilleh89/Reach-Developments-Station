"""
Tests for the Construction Variance Engine.

Validates:
- Schedule variance calculation (actual_start vs planned_start)
- Completion variance calculation (actual_finish vs planned_finish)
- Milestone status derivation (NOT_STARTED, IN_PROGRESS, DELAYED, AHEAD, COMPLETED)
- Delay propagation on critical path (risk_exposed flag)
- Project delay calculation
- Critical path shift detection
- Empty input handling
- Edge cases (zero variance, completed milestones, off-critical-path delays)
"""

import pytest

from app.modules.construction.variance_engine import (
    MilestoneProgress,
    MilestoneVarianceResult,
    ScopeVarianceResult,
    VarianceMilestoneStatus,
    compute_variance,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _mp(
    milestone_id: str,
    planned_start: int,
    planned_finish: int,
    is_critical: bool = True,
    actual_start_day: int | None = None,
    actual_finish_day: int | None = None,
    progress_percent: float | None = None,
) -> MilestoneProgress:
    return MilestoneProgress(
        milestone_id=milestone_id,
        planned_start=planned_start,
        planned_finish=planned_finish,
        is_critical=is_critical,
        actual_start_day=actual_start_day,
        actual_finish_day=actual_finish_day,
        progress_percent=progress_percent,
    )


def _find(result: ScopeVarianceResult, milestone_id: str) -> MilestoneVarianceResult:
    for r in result.milestones:
        if r.milestone_id == milestone_id:
            return r
    raise KeyError(f"Milestone '{milestone_id}' not in result")


# ---------------------------------------------------------------------------
# Basic cases
# ---------------------------------------------------------------------------


def test_empty_input_returns_zero_delay() -> None:
    result = compute_variance("scope-1", [], [])
    assert result.project_delay_days == 0
    assert result.critical_path_shift is False
    assert result.affected_milestones == []
    assert result.milestones == []


def test_single_not_started_milestone() -> None:
    milestones = [_mp("A", planned_start=0, planned_finish=10)]
    result = compute_variance("scope-1", milestones, ["A"])

    r = _find(result, "A")
    assert r.milestone_status == VarianceMilestoneStatus.NOT_STARTED
    assert r.schedule_variance_days is None
    assert r.completion_variance_days is None
    assert r.risk_exposed is False
    assert result.project_delay_days == 0
    assert result.critical_path_shift is False


# ---------------------------------------------------------------------------
# Schedule variance calculation
# ---------------------------------------------------------------------------


def test_on_time_start_zero_variance() -> None:
    milestones = [_mp("A", 0, 10, actual_start_day=0, progress_percent=50.0)]
    result = compute_variance("scope-1", milestones, ["A"])

    r = _find(result, "A")
    assert r.schedule_variance_days == 0
    assert r.milestone_status == VarianceMilestoneStatus.IN_PROGRESS
    assert result.project_delay_days == 0


def test_late_start_positive_variance() -> None:
    milestones = [_mp("A", 0, 10, actual_start_day=5, progress_percent=30.0)]
    result = compute_variance("scope-1", milestones, ["A"])

    r = _find(result, "A")
    assert r.schedule_variance_days == 5
    assert r.milestone_status == VarianceMilestoneStatus.DELAYED
    assert result.project_delay_days == 5
    assert result.critical_path_shift is True


def test_early_start_negative_variance() -> None:
    milestones = [_mp("A", 5, 15, actual_start_day=2, progress_percent=20.0)]
    result = compute_variance("scope-1", milestones, ["A"])

    r = _find(result, "A")
    assert r.schedule_variance_days == -3
    assert r.milestone_status == VarianceMilestoneStatus.AHEAD
    assert result.project_delay_days == 0


# ---------------------------------------------------------------------------
# Completion variance
# ---------------------------------------------------------------------------


def test_on_time_completion_zero_completion_variance() -> None:
    milestones = [
        _mp("A", 0, 10, actual_start_day=0, actual_finish_day=10, progress_percent=100.0)
    ]
    result = compute_variance("scope-1", milestones, ["A"])

    r = _find(result, "A")
    assert r.completion_variance_days == 0
    assert r.milestone_status == VarianceMilestoneStatus.COMPLETED


def test_late_finish_positive_completion_variance() -> None:
    milestones = [
        _mp("A", 0, 10, actual_start_day=0, actual_finish_day=14, progress_percent=100.0)
    ]
    result = compute_variance("scope-1", milestones, ["A"])

    r = _find(result, "A")
    assert r.completion_variance_days == 4
    assert r.milestone_status == VarianceMilestoneStatus.COMPLETED


def test_early_finish_negative_completion_variance() -> None:
    milestones = [
        _mp("A", 0, 10, actual_start_day=0, actual_finish_day=7, progress_percent=100.0)
    ]
    result = compute_variance("scope-1", milestones, ["A"])

    r = _find(result, "A")
    assert r.completion_variance_days == -3
    assert r.milestone_status == VarianceMilestoneStatus.COMPLETED


def test_completion_variance_none_when_not_finished() -> None:
    milestones = [_mp("A", 0, 10, actual_start_day=0, progress_percent=60.0)]
    result = compute_variance("scope-1", milestones, ["A"])

    r = _find(result, "A")
    assert r.completion_variance_days is None


# ---------------------------------------------------------------------------
# Milestone status derivation
# ---------------------------------------------------------------------------


def test_status_completed_from_progress_100() -> None:
    milestones = [_mp("A", 0, 10, actual_start_day=0, progress_percent=100.0)]
    result = compute_variance("scope-1", milestones, ["A"])
    assert _find(result, "A").milestone_status == VarianceMilestoneStatus.COMPLETED


def test_status_completed_from_actual_finish_day() -> None:
    milestones = [
        _mp("A", 0, 10, actual_start_day=0, actual_finish_day=10, progress_percent=None)
    ]
    result = compute_variance("scope-1", milestones, ["A"])
    assert _find(result, "A").milestone_status == VarianceMilestoneStatus.COMPLETED


def test_status_not_started_no_actual_start() -> None:
    milestones = [_mp("A", 0, 10)]
    result = compute_variance("scope-1", milestones, ["A"])
    assert _find(result, "A").milestone_status == VarianceMilestoneStatus.NOT_STARTED


def test_status_not_started_zero_progress_no_actual_start() -> None:
    milestones = [_mp("A", 0, 10, progress_percent=0.0)]
    result = compute_variance("scope-1", milestones, ["A"])
    assert _find(result, "A").milestone_status == VarianceMilestoneStatus.NOT_STARTED


def test_status_in_progress_on_time() -> None:
    milestones = [_mp("A", 5, 15, actual_start_day=5, progress_percent=40.0)]
    result = compute_variance("scope-1", milestones, ["A"])
    assert _find(result, "A").milestone_status == VarianceMilestoneStatus.IN_PROGRESS


def test_status_delayed_late_start() -> None:
    milestones = [_mp("A", 0, 10, actual_start_day=3, progress_percent=20.0)]
    result = compute_variance("scope-1", milestones, ["A"])
    assert _find(result, "A").milestone_status == VarianceMilestoneStatus.DELAYED


def test_status_ahead_early_start() -> None:
    milestones = [_mp("A", 5, 15, actual_start_day=3, progress_percent=10.0)]
    result = compute_variance("scope-1", milestones, ["A"])
    assert _find(result, "A").milestone_status == VarianceMilestoneStatus.AHEAD


# ---------------------------------------------------------------------------
# Delay propagation
# ---------------------------------------------------------------------------


def test_delay_propagation_to_downstream_critical_milestones() -> None:
    """Delayed critical milestone A exposes downstream critical milestone B."""
    milestones = [
        _mp("A", 0, 10, is_critical=True, actual_start_day=3, progress_percent=20.0),
        _mp("B", 10, 20, is_critical=True),  # not started yet
    ]
    result = compute_variance("scope-1", milestones, ["A", "B"])

    a = _find(result, "A")
    b = _find(result, "B")

    assert a.milestone_status == VarianceMilestoneStatus.DELAYED
    assert b.risk_exposed is True
    assert "B" in result.affected_milestones
    assert result.project_delay_days == 3
    assert result.critical_path_shift is True


def test_delay_does_not_expose_non_critical_milestone() -> None:
    """A delayed critical milestone does not expose off-critical-path milestones."""
    milestones = [
        _mp("A", 0, 10, is_critical=True, actual_start_day=5, progress_percent=10.0),
        _mp("B", 0, 8, is_critical=False),  # parallel, off critical path
    ]
    result = compute_variance("scope-1", milestones, ["A"])

    b = _find(result, "B")
    assert b.risk_exposed is False


def test_completed_downstream_milestone_not_risk_exposed() -> None:
    """A completed downstream milestone is not risk-exposed even if a predecessor delayed."""
    milestones = [
        _mp("A", 0, 10, is_critical=True, actual_start_day=3, progress_percent=30.0),
        _mp("B", 10, 20, is_critical=True, actual_start_day=10, actual_finish_day=20,
            progress_percent=100.0),
    ]
    result = compute_variance("scope-1", milestones, ["A", "B"])

    b = _find(result, "B")
    assert b.risk_exposed is False
    assert "B" not in result.affected_milestones


def test_no_delay_no_propagation() -> None:
    """On-time execution — no risk exposed, no project delay."""
    milestones = [
        _mp("A", 0, 10, is_critical=True, actual_start_day=0, progress_percent=50.0),
        _mp("B", 10, 20, is_critical=True),
    ]
    result = compute_variance("scope-1", milestones, ["A", "B"])

    assert result.project_delay_days == 0
    assert result.critical_path_shift is False
    assert all(not r.risk_exposed for r in result.milestones)
    assert result.affected_milestones == []


def test_multiple_delayed_critical_milestones_takes_maximum() -> None:
    """When multiple critical milestones are delayed, project_delay_days is the max."""
    milestones = [
        _mp("A", 0, 10, is_critical=True, actual_start_day=2, progress_percent=20.0),
        _mp("B", 10, 20, is_critical=True, actual_start_day=15, progress_percent=10.0),
        _mp("C", 20, 30, is_critical=True),
    ]
    result = compute_variance("scope-1", milestones, ["A", "B", "C"])

    assert result.project_delay_days == 5  # max of (2, 5)
    assert result.critical_path_shift is True


def test_three_phase_chain_delay_propagates_to_all_downstream() -> None:
    """Delay in A (first critical) exposes B and C downstream."""
    milestones = [
        _mp("A", 0, 5, is_critical=True, actual_start_day=2, progress_percent=30.0),
        _mp("B", 5, 10, is_critical=True),
        _mp("C", 10, 20, is_critical=True),
    ]
    result = compute_variance("scope-1", milestones, ["A", "B", "C"])

    b = _find(result, "B")
    c = _find(result, "C")

    assert b.risk_exposed is True
    assert c.risk_exposed is True
    assert "B" in result.affected_milestones
    assert "C" in result.affected_milestones


# ---------------------------------------------------------------------------
# Passthrough fields
# ---------------------------------------------------------------------------


def test_result_preserves_planned_dates() -> None:
    milestones = [_mp("X", 5, 15)]
    result = compute_variance("scope-1", milestones, ["X"])

    r = _find(result, "X")
    assert r.planned_start == 5
    assert r.planned_finish == 15


def test_result_preserves_actual_fields() -> None:
    milestones = [
        _mp("X", 0, 10, actual_start_day=1, actual_finish_day=12, progress_percent=100.0)
    ]
    result = compute_variance("scope-1", milestones, ["X"])

    r = _find(result, "X")
    assert r.actual_start_day == 1
    assert r.actual_finish_day == 12
    assert r.progress_percent == 100.0


def test_result_scope_id_is_passed_through() -> None:
    result = compute_variance("my-scope-id", [], [])
    assert result.scope_id == "my-scope-id"
