"""
Tests for the Construction Cost Engine.

PR-CONSTR-042 — Construction Cost Tracking & Budget Variance

Validates:
- Cost variance calculation (actual_cost vs planned_cost)
- Cost variance percent calculation
- Project-level budget aggregation
- Project overrun percent calculation
- Empty input handling
- Edge cases (zero planned_cost, missing costs, partial data)
"""

from decimal import Decimal

from app.modules.construction.cost_engine import (
    CostVarianceResult,
    MilestoneCostData,
    MilestoneCostVariance,
    compute_cost_variance,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _mc(
    milestone_id: str,
    planned_cost: str | None = None,
    actual_cost: str | None = None,
) -> MilestoneCostData:
    return MilestoneCostData(
        milestone_id=milestone_id,
        planned_cost=Decimal(planned_cost) if planned_cost is not None else None,
        actual_cost=Decimal(actual_cost) if actual_cost is not None else None,
    )


def _find(result: CostVarianceResult, milestone_id: str) -> MilestoneCostVariance:
    for r in result.milestones:
        if r.milestone_id == milestone_id:
            return r
    raise KeyError(f"Milestone '{milestone_id}' not in result")


# ---------------------------------------------------------------------------
# Empty / trivial cases
# ---------------------------------------------------------------------------


def test_empty_input_returns_zero_budget() -> None:
    result = compute_cost_variance("scope-1", [])
    assert result.project_budget == Decimal("0.00")
    assert result.project_actual_cost == Decimal("0.00")
    assert result.project_cost_variance == Decimal("0.00")
    assert result.project_overrun_percent is None
    assert result.milestones == []


def test_single_milestone_no_costs() -> None:
    result = compute_cost_variance("scope-1", [_mc("A")])
    r = _find(result, "A")
    assert r.planned_cost is None
    assert r.actual_cost is None
    assert r.cost_variance is None
    assert r.cost_variance_percent is None
    assert result.project_budget == Decimal("0.00")
    assert result.project_actual_cost == Decimal("0.00")


# ---------------------------------------------------------------------------
# Per-milestone variance
# ---------------------------------------------------------------------------


def test_single_milestone_on_budget() -> None:
    milestones = [_mc("A", planned_cost="10000.00", actual_cost="10000.00")]
    result = compute_cost_variance("scope-1", milestones)
    r = _find(result, "A")
    assert r.cost_variance == Decimal("0.00")
    assert r.cost_variance_percent == Decimal("0.00")


def test_single_milestone_over_budget() -> None:
    milestones = [_mc("A", planned_cost="10000.00", actual_cost="12500.00")]
    result = compute_cost_variance("scope-1", milestones)
    r = _find(result, "A")
    assert r.cost_variance == Decimal("2500.00")
    assert r.cost_variance_percent == Decimal("25.00")


def test_single_milestone_under_budget() -> None:
    milestones = [_mc("A", planned_cost="10000.00", actual_cost="8000.00")]
    result = compute_cost_variance("scope-1", milestones)
    r = _find(result, "A")
    assert r.cost_variance == Decimal("-2000.00")
    assert r.cost_variance_percent == Decimal("-20.00")


def test_variance_percent_fractional() -> None:
    milestones = [_mc("A", planned_cost="3000.00", actual_cost="4000.00")]
    result = compute_cost_variance("scope-1", milestones)
    r = _find(result, "A")
    # 1000 / 3000 * 100 = 33.33...
    assert r.cost_variance_percent == Decimal("33.33")


def test_milestone_only_planned_cost_no_actual() -> None:
    milestones = [_mc("A", planned_cost="5000.00")]
    result = compute_cost_variance("scope-1", milestones)
    r = _find(result, "A")
    assert r.planned_cost == Decimal("5000.00")
    assert r.actual_cost is None
    assert r.cost_variance is None
    assert r.cost_variance_percent is None
    assert result.project_budget == Decimal("5000.00")
    assert result.project_actual_cost == Decimal("0.00")


def test_milestone_only_actual_cost_no_planned() -> None:
    milestones = [_mc("A", actual_cost="7000.00")]
    result = compute_cost_variance("scope-1", milestones)
    r = _find(result, "A")
    assert r.planned_cost is None
    assert r.actual_cost == Decimal("7000.00")
    assert r.cost_variance is None
    assert r.cost_variance_percent is None
    assert result.project_budget == Decimal("0.00")
    assert result.project_actual_cost == Decimal("7000.00")


def test_zero_planned_cost_no_variance_percent() -> None:
    milestones = [_mc("A", planned_cost="0.00", actual_cost="5000.00")]
    result = compute_cost_variance("scope-1", milestones)
    r = _find(result, "A")
    assert r.cost_variance == Decimal("5000.00")
    assert r.cost_variance_percent is None  # planned == 0, no division


# ---------------------------------------------------------------------------
# Project-level aggregation
# ---------------------------------------------------------------------------


def test_project_budget_aggregation() -> None:
    milestones = [
        _mc("A", planned_cost="10000.00", actual_cost="12000.00"),
        _mc("B", planned_cost="20000.00", actual_cost="18000.00"),
        _mc("C", planned_cost="5000.00", actual_cost="5000.00"),
    ]
    result = compute_cost_variance("scope-1", milestones)
    assert result.project_budget == Decimal("35000.00")
    assert result.project_actual_cost == Decimal("35000.00")
    assert result.project_cost_variance == Decimal("0.00")
    assert result.project_overrun_percent == Decimal("0.00")


def test_project_overrun() -> None:
    milestones = [
        _mc("A", planned_cost="10000.00", actual_cost="15000.00"),
        _mc("B", planned_cost="10000.00", actual_cost="10000.00"),
    ]
    result = compute_cost_variance("scope-1", milestones)
    assert result.project_budget == Decimal("20000.00")
    assert result.project_actual_cost == Decimal("25000.00")
    assert result.project_cost_variance == Decimal("5000.00")
    assert result.project_overrun_percent == Decimal("25.00")


def test_project_under_budget() -> None:
    milestones = [
        _mc("A", planned_cost="10000.00", actual_cost="8000.00"),
        _mc("B", planned_cost="10000.00", actual_cost="9000.00"),
    ]
    result = compute_cost_variance("scope-1", milestones)
    assert result.project_budget == Decimal("20000.00")
    assert result.project_actual_cost == Decimal("17000.00")
    assert result.project_cost_variance == Decimal("-3000.00")
    assert result.project_overrun_percent == Decimal("-15.00")


def test_project_overrun_percent_zero_budget() -> None:
    milestones = [_mc("A", actual_cost="5000.00")]
    result = compute_cost_variance("scope-1", milestones)
    assert result.project_budget == Decimal("0.00")
    assert result.project_overrun_percent is None


def test_project_mixed_partial_costs() -> None:
    """Milestones with only planned OR only actual contribute to totals."""
    milestones = [
        _mc("A", planned_cost="10000.00"),   # only planned
        _mc("B", actual_cost="5000.00"),     # only actual
        _mc("C", planned_cost="8000.00", actual_cost="9000.00"),  # both
    ]
    result = compute_cost_variance("scope-1", milestones)
    assert result.project_budget == Decimal("18000.00")
    assert result.project_actual_cost == Decimal("14000.00")
    assert result.project_cost_variance == Decimal("-4000.00")


def test_scope_id_passed_through() -> None:
    result = compute_cost_variance("scope-XYZ", [])
    assert result.scope_id == "scope-XYZ"


def test_multiple_milestones_all_fields_correct() -> None:
    milestones = [
        _mc("A", planned_cost="1000.00", actual_cost="1100.00"),
        _mc("B", planned_cost="2000.00", actual_cost="1900.00"),
    ]
    result = compute_cost_variance("scope-1", milestones)
    a = _find(result, "A")
    b = _find(result, "B")
    assert a.cost_variance == Decimal("100.00")
    assert a.cost_variance_percent == Decimal("10.00")
    assert b.cost_variance == Decimal("-100.00")
    assert b.cost_variance_percent == Decimal("-5.00")
    assert result.project_budget == Decimal("3000.00")
    assert result.project_actual_cost == Decimal("3000.00")
    assert result.project_cost_variance == Decimal("0.00")
