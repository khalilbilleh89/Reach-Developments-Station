"""
Tests for the Construction Schedule Engine (CPM calculations).

Validates:
- Simple linear dependency chain
- Parallel phases
- Lag day handling
- Earliest/latest date calculation
- Total float calculation
- Critical path detection
- Delay propagation
- Cycle rejection
- Empty input
- Single milestone (no dependencies)
"""

import pytest

from app.modules.construction.schedule_engine import (
    ScheduleOutput,
    SchedulePhase,
    ScheduleResult,
    compute_schedule,
    detect_cycle,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _phase(
    phase_id: str,
    duration: int,
    predecessors: list[str] | None = None,
    lag_days: dict[str, int] | None = None,
    actual_start_day: int | None = None,
) -> SchedulePhase:
    return SchedulePhase(
        phase_id=phase_id,
        duration_days=duration,
        predecessor_ids=predecessors or [],
        lag_days=lag_days or {},
        actual_start_day=actual_start_day,
    )


def _find(output: ScheduleOutput, phase_id: str) -> ScheduleResult:
    for r in output.phases:
        if r.phase_id == phase_id:
            return r
    raise KeyError(f"Phase '{phase_id}' not in output")


# ---------------------------------------------------------------------------
# Basic cases
# ---------------------------------------------------------------------------


def test_empty_input_returns_zero_duration() -> None:
    output = compute_schedule([])
    assert output.project_duration == 0
    assert output.critical_path == []
    assert output.phases == []


def test_single_milestone_no_dependencies() -> None:
    phases = [_phase("A", 10)]
    output = compute_schedule(phases)

    r = _find(output, "A")
    assert r.earliest_start == 0
    assert r.earliest_finish == 10
    assert r.latest_start == 0
    assert r.latest_finish == 10
    assert r.total_float == 0
    assert r.is_critical is True
    assert output.project_duration == 10
    assert output.critical_path == ["A"]


def test_single_milestone_zero_duration() -> None:
    phases = [_phase("A", 0)]
    output = compute_schedule(phases)
    r = _find(output, "A")
    assert r.earliest_start == 0
    assert r.earliest_finish == 0
    assert r.total_float == 0
    assert r.is_critical is True


# ---------------------------------------------------------------------------
# Linear chain
# ---------------------------------------------------------------------------


def test_linear_chain_two_phases() -> None:
    """A → B (10 days each) — single critical path A→B."""
    phases = [
        _phase("A", 10),
        _phase("B", 10, predecessors=["A"]),
    ]
    output = compute_schedule(phases)

    a = _find(output, "A")
    b = _find(output, "B")

    assert a.earliest_start == 0
    assert a.earliest_finish == 10
    assert a.latest_start == 0
    assert a.latest_finish == 10
    assert a.total_float == 0
    assert a.is_critical is True

    assert b.earliest_start == 10
    assert b.earliest_finish == 20
    assert b.latest_start == 10
    assert b.latest_finish == 20
    assert b.total_float == 0
    assert b.is_critical is True

    assert output.project_duration == 20
    assert set(output.critical_path) == {"A", "B"}


def test_linear_chain_three_phases() -> None:
    """A(5) → B(3) → C(7) — total 15."""
    phases = [
        _phase("A", 5),
        _phase("B", 3, predecessors=["A"]),
        _phase("C", 7, predecessors=["B"]),
    ]
    output = compute_schedule(phases)

    a = _find(output, "A")
    b = _find(output, "B")
    c = _find(output, "C")

    assert a.earliest_finish == 5
    assert b.earliest_start == 5
    assert b.earliest_finish == 8
    assert c.earliest_start == 8
    assert c.earliest_finish == 15
    assert output.project_duration == 15
    assert all(r.is_critical for r in [a, b, c])


# ---------------------------------------------------------------------------
# Parallel phases
# ---------------------------------------------------------------------------


def test_parallel_phases_with_join() -> None:
    """
    A(10) ─┐
            ├─ C(5)
    B(15) ─┘

    Critical path: B → C (total 20).
    A has 5 days of float.
    """
    phases = [
        _phase("A", 10),
        _phase("B", 15),
        _phase("C", 5, predecessors=["A", "B"]),
    ]
    output = compute_schedule(phases)

    a = _find(output, "A")
    b = _find(output, "B")
    c = _find(output, "C")

    assert b.earliest_start == 0
    assert b.earliest_finish == 15
    assert c.earliest_start == 15  # driven by B
    assert c.earliest_finish == 20
    assert output.project_duration == 20

    assert b.total_float == 0
    assert b.is_critical is True
    assert c.total_float == 0
    assert c.is_critical is True

    assert a.total_float == 5
    assert a.is_critical is False

    assert set(output.critical_path) == {"B", "C"}


def test_two_independent_paths() -> None:
    """
    A(5) → B(3)   (total 8)
    C(10)           (total 10 — drives project end)

    Path C is the critical path.
    Path A→B has float.
    """
    phases = [
        _phase("A", 5),
        _phase("B", 3, predecessors=["A"]),
        _phase("C", 10),
    ]
    output = compute_schedule(phases)

    a = _find(output, "A")
    b = _find(output, "B")
    c = _find(output, "C")

    assert c.earliest_finish == 10
    assert output.project_duration == 10
    assert c.total_float == 0
    assert c.is_critical is True

    assert a.total_float == 2
    assert b.total_float == 2
    assert a.is_critical is False
    assert b.is_critical is False

    assert output.critical_path == ["C"]


# ---------------------------------------------------------------------------
# Lag days
# ---------------------------------------------------------------------------


def test_lag_shifts_successor_start() -> None:
    """A(10) → [lag=5] → B(5) — B starts at day 15."""
    phases = [
        _phase("A", 10),
        _phase("B", 5, predecessors=["A"], lag_days={"A": 5}),
    ]
    output = compute_schedule(phases)

    b = _find(output, "B")
    assert b.earliest_start == 15
    assert b.earliest_finish == 20
    assert output.project_duration == 20


def test_lag_zero_behaves_like_no_lag() -> None:
    phases = [
        _phase("A", 10),
        _phase("B", 5, predecessors=["A"], lag_days={"A": 0}),
    ]
    output = compute_schedule(phases)
    b = _find(output, "B")
    assert b.earliest_start == 10


def test_multiple_predecessors_max_lag_wins() -> None:
    """
    A(10, lag=2) ─┐
                   ├─ C(5)   => C starts at max(12, 8) = 12
    B(8, lag=0)  ─┘
    """
    phases = [
        _phase("A", 10),
        _phase("B", 8),
        _phase("C", 5, predecessors=["A", "B"], lag_days={"A": 2, "B": 0}),
    ]
    output = compute_schedule(phases)
    c = _find(output, "C")
    assert c.earliest_start == 12


# ---------------------------------------------------------------------------
# Total float
# ---------------------------------------------------------------------------


def test_total_float_non_critical_path() -> None:
    """
    A(3) → C(2)    (total 5)
    B(1)            (total 1 → 4 days of float driving project end is 5)
    """
    phases = [
        _phase("A", 3),
        _phase("B", 1),
        _phase("C", 2, predecessors=["A"]),
    ]
    output = compute_schedule(phases)

    b = _find(output, "B")
    assert b.total_float == 4
    assert b.is_critical is False


def test_all_phases_on_critical_path() -> None:
    """Linear chain: all float = 0."""
    phases = [
        _phase("A", 5),
        _phase("B", 5, predecessors=["A"]),
        _phase("C", 5, predecessors=["B"]),
    ]
    output = compute_schedule(phases)
    for r in output.phases:
        assert r.total_float == 0
        assert r.is_critical is True


# ---------------------------------------------------------------------------
# Delay propagation
# ---------------------------------------------------------------------------


def test_actual_start_later_than_es_creates_delay() -> None:
    """A was planned to start at day 0 but actually started at day 5."""
    phases = [_phase("A", 10, actual_start_day=5)]
    output = compute_schedule(phases)
    a = _find(output, "A")
    assert a.delay_days == 5
    assert a.earliest_start == 5
    assert a.earliest_finish == 15


def test_delay_propagates_to_successor() -> None:
    """A delayed by 3 days; B (successor) ES shifts forward."""
    phases = [
        _phase("A", 10, actual_start_day=3),
        _phase("B", 5, predecessors=["A"]),
    ]
    output = compute_schedule(phases)

    a = _find(output, "A")
    b = _find(output, "B")

    assert a.earliest_finish == 13   # started at 3, 10 days duration
    assert b.earliest_start == 13    # must wait for A to finish
    assert b.earliest_finish == 18


def test_no_delay_when_actual_start_equals_es() -> None:
    phases = [_phase("A", 10, actual_start_day=0)]
    output = compute_schedule(phases)
    a = _find(output, "A")
    assert a.delay_days == 0


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def test_direct_cycle_raises_value_error() -> None:
    """A → B → A is a cycle."""
    phases = [
        _phase("A", 5, predecessors=["B"]),
        _phase("B", 5, predecessors=["A"]),
    ]
    with pytest.raises(ValueError, match="[Cc]ircular"):
        compute_schedule(phases)


def test_indirect_cycle_raises_value_error() -> None:
    """A → B → C → A is a cycle."""
    phases = [
        _phase("A", 5, predecessors=["C"]),
        _phase("B", 5, predecessors=["A"]),
        _phase("C", 5, predecessors=["B"]),
    ]
    with pytest.raises(ValueError, match="[Cc]ircular"):
        compute_schedule(phases)


def test_self_reference_cycle_raises_value_error() -> None:
    """A → A is a self-dependency cycle."""
    phases = [_phase("A", 5, predecessors=["A"])]
    with pytest.raises(ValueError, match="[Cc]ircular"):
        compute_schedule(phases)


def test_detect_cycle_returns_none_for_dag() -> None:
    phases = [
        _phase("A", 5),
        _phase("B", 5, predecessors=["A"]),
    ]
    assert detect_cycle(phases) is None


def test_detect_cycle_returns_cycle_path() -> None:
    phases = [
        _phase("A", 5, predecessors=["B"]),
        _phase("B", 5, predecessors=["A"]),
    ]
    cycle = detect_cycle(phases)
    assert cycle is not None
    assert len(cycle) >= 2


# ---------------------------------------------------------------------------
# Diamond / complex graphs
# ---------------------------------------------------------------------------


def test_diamond_dependency_graph() -> None:
    """
        A(10)
       /      \\
    B(5)    C(8)
       \\      /
        D(3)

    Project end = 10 + 8 + 3 = 21.
    Critical path: A → C → D.
    B has float: 10 + 5 = 15 ≤ 21; B float = (21 - 3 - 5 - 10) = 3.
    """
    phases = [
        _phase("A", 10),
        _phase("B", 5, predecessors=["A"]),
        _phase("C", 8, predecessors=["A"]),
        _phase("D", 3, predecessors=["B", "C"]),
    ]
    output = compute_schedule(phases)

    d = _find(output, "D")
    assert d.earliest_start == 18   # A(10) + C(8)
    assert d.earliest_finish == 21
    assert output.project_duration == 21

    c = _find(output, "C")
    assert c.is_critical is True

    b = _find(output, "B")
    assert b.is_critical is False
    assert b.total_float == 3


def test_predecessor_outside_phase_set_treated_as_day_zero() -> None:
    """Predecessor not in the provided phase list is treated as completing at day 0."""
    phases = [
        _phase("B", 5, predecessors=["EXTERNAL"]),
    ]
    output = compute_schedule(phases)
    b = _find(output, "B")
    assert b.earliest_start == 0
    assert b.earliest_finish == 5
