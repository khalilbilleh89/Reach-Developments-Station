"""
Tests for the Concept Option Comparison Engine.

Validates pure comparison logic — no database or HTTP layer involved.

PR-CONCEPT-053
"""

import pytest

from app.modules.concept_design.comparison_engine import (
    ConceptOptionComparisonInput,
    compute_concept_comparison,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_input(
    option_id: str,
    name: str = "Option",
    status: str = "draft",
    unit_count: int = 0,
    sellable_area: float | None = None,
    efficiency_ratio: float | None = None,
    average_unit_area: float | None = None,
    building_count: int | None = None,
    floor_count: int | None = None,
) -> ConceptOptionComparisonInput:
    return ConceptOptionComparisonInput(
        concept_option_id=option_id,
        name=name,
        status=status,
        unit_count=unit_count,
        sellable_area=sellable_area,
        efficiency_ratio=efficiency_ratio,
        average_unit_area=average_unit_area,
        building_count=building_count,
        floor_count=floor_count,
    )


# ---------------------------------------------------------------------------
# Empty comparison
# ---------------------------------------------------------------------------


def test_empty_comparison_returns_empty_result():
    result = compute_concept_comparison([], comparison_basis="project")
    assert result.option_count == 0
    assert result.rows == []
    assert result.best_sellable_area_option_id is None
    assert result.best_efficiency_option_id is None
    assert result.best_unit_count_option_id is None
    assert result.comparison_basis == "project"


def test_empty_comparison_scenario_basis():
    result = compute_concept_comparison([], comparison_basis="scenario")
    assert result.comparison_basis == "scenario"
    assert result.option_count == 0


# ---------------------------------------------------------------------------
# Single option
# ---------------------------------------------------------------------------


def test_single_option_is_best_in_all_metrics():
    opt = _make_input(
        "opt-1",
        name="Solo",
        unit_count=100,
        sellable_area=9100.0,
        efficiency_ratio=0.758,
        average_unit_area=91.0,
        building_count=2,
        floor_count=10,
    )
    result = compute_concept_comparison([opt], comparison_basis="project")

    assert result.option_count == 1
    assert result.best_sellable_area_option_id == "opt-1"
    assert result.best_efficiency_option_id == "opt-1"
    assert result.best_unit_count_option_id == "opt-1"

    row = result.rows[0]
    assert row.is_best_sellable_area is True
    assert row.is_best_efficiency is True
    assert row.is_best_unit_count is True
    assert row.sellable_area_delta_vs_best == pytest.approx(0.0)
    assert row.efficiency_delta_vs_best == pytest.approx(0.0)
    assert row.unit_count_delta_vs_best == 0
    assert row.building_count == 2
    assert row.floor_count == 10


def test_single_option_none_metrics_delta_is_none():
    opt = _make_input("opt-1", unit_count=50)
    result = compute_concept_comparison([opt], comparison_basis="project")

    row = result.rows[0]
    assert row.sellable_area_delta_vs_best is None
    assert row.efficiency_delta_vs_best is None
    assert row.unit_count_delta_vs_best == 0
    assert row.is_best_sellable_area is False
    assert row.is_best_efficiency is False
    assert row.is_best_unit_count is True


# ---------------------------------------------------------------------------
# Multi-option comparison
# ---------------------------------------------------------------------------


def test_multi_option_best_sellable_area_flagged():
    opts = [
        _make_input("opt-A", unit_count=100, sellable_area=9100.0, efficiency_ratio=0.758),
        _make_input("opt-B", unit_count=92, sellable_area=9600.0, efficiency_ratio=0.800),
        _make_input("opt-C", unit_count=84, sellable_area=8500.0, efficiency_ratio=0.720),
    ]
    result = compute_concept_comparison(opts, comparison_basis="project")

    assert result.best_sellable_area_option_id == "opt-B"
    assert result.best_efficiency_option_id == "opt-B"
    assert result.best_unit_count_option_id == "opt-A"
    assert result.option_count == 3

    rows_by_id = {r.concept_option_id: r for r in result.rows}

    row_b = rows_by_id["opt-B"]
    assert row_b.is_best_sellable_area is True
    assert row_b.is_best_efficiency is True
    assert row_b.is_best_unit_count is False
    assert row_b.sellable_area_delta_vs_best == pytest.approx(0.0)
    assert row_b.efficiency_delta_vs_best == pytest.approx(0.0)
    assert row_b.unit_count_delta_vs_best == 92 - 100  # -8

    row_a = rows_by_id["opt-A"]
    assert row_a.is_best_sellable_area is False
    assert row_a.is_best_unit_count is True
    assert row_a.sellable_area_delta_vs_best == pytest.approx(9100.0 - 9600.0)
    assert row_a.unit_count_delta_vs_best == 0

    row_c = rows_by_id["opt-C"]
    assert row_c.is_best_sellable_area is False
    assert row_c.sellable_area_delta_vs_best == pytest.approx(8500.0 - 9600.0)
    assert row_c.unit_count_delta_vs_best == 84 - 100  # -16


# ---------------------------------------------------------------------------
# Best metric flagging with None values
# ---------------------------------------------------------------------------


def test_best_sellable_skips_none_values():
    opts = [
        _make_input("opt-1", unit_count=10, sellable_area=None),
        _make_input("opt-2", unit_count=20, sellable_area=5000.0),
    ]
    result = compute_concept_comparison(opts, comparison_basis="project")

    assert result.best_sellable_area_option_id == "opt-2"

    row_1 = result.rows[0]
    assert row_1.is_best_sellable_area is False
    assert row_1.sellable_area_delta_vs_best is None


def test_best_sellable_none_when_all_none():
    opts = [
        _make_input("opt-1", unit_count=10),
        _make_input("opt-2", unit_count=20),
    ]
    result = compute_concept_comparison(opts, comparison_basis="project")

    assert result.best_sellable_area_option_id is None
    assert result.best_efficiency_option_id is None
    for row in result.rows:
        assert row.is_best_sellable_area is False
        assert row.sellable_area_delta_vs_best is None


# ---------------------------------------------------------------------------
# Delta calculations
# ---------------------------------------------------------------------------


def test_delta_values_are_zero_or_negative():
    opts = [
        _make_input("a", unit_count=80, sellable_area=8000.0, efficiency_ratio=0.70),
        _make_input("b", unit_count=100, sellable_area=10000.0, efficiency_ratio=0.85),
        _make_input("c", unit_count=60, sellable_area=6000.0, efficiency_ratio=0.60),
    ]
    result = compute_concept_comparison(opts, comparison_basis="project")

    for row in result.rows:
        if row.sellable_area_delta_vs_best is not None:
            assert row.sellable_area_delta_vs_best <= 0.0 + 1e-9
        if row.efficiency_delta_vs_best is not None:
            assert row.efficiency_delta_vs_best <= 0.0 + 1e-9
        assert row.unit_count_delta_vs_best <= 0


def test_delta_exact_values():
    opts = [
        _make_input("x", unit_count=50, sellable_area=5000.0, efficiency_ratio=0.5),
        _make_input("y", unit_count=100, sellable_area=10000.0, efficiency_ratio=0.8),
    ]
    result = compute_concept_comparison(opts, comparison_basis="project")
    rows = {r.concept_option_id: r for r in result.rows}

    assert rows["x"].sellable_area_delta_vs_best == pytest.approx(-5000.0)
    assert rows["x"].efficiency_delta_vs_best == pytest.approx(-0.3)
    assert rows["x"].unit_count_delta_vs_best == -50

    assert rows["y"].sellable_area_delta_vs_best == pytest.approx(0.0)
    assert rows["y"].efficiency_delta_vs_best == pytest.approx(0.0)
    assert rows["y"].unit_count_delta_vs_best == 0


# ---------------------------------------------------------------------------
# Tie handling — determinism
# ---------------------------------------------------------------------------


def test_tie_handling_is_deterministic():
    """When two options have identical metrics, repeated calls return same winner."""
    opts = [
        _make_input("id-001", unit_count=100, sellable_area=9000.0, efficiency_ratio=0.75),
        _make_input("id-002", unit_count=100, sellable_area=9000.0, efficiency_ratio=0.75),
    ]
    result1 = compute_concept_comparison(opts, comparison_basis="project")
    result2 = compute_concept_comparison(opts, comparison_basis="project")

    assert result1.best_sellable_area_option_id == result2.best_sellable_area_option_id
    assert result1.best_efficiency_option_id == result2.best_efficiency_option_id
    assert result1.best_unit_count_option_id == result2.best_unit_count_option_id


def test_tie_produces_zero_delta_for_both():
    opts = [
        _make_input("id-aaa", unit_count=100, sellable_area=9000.0),
        _make_input("id-bbb", unit_count=100, sellable_area=9000.0),
    ]
    result = compute_concept_comparison(opts, comparison_basis="project")

    for row in result.rows:
        assert row.sellable_area_delta_vs_best == pytest.approx(0.0)
        assert row.unit_count_delta_vs_best == 0
