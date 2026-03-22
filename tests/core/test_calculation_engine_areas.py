"""
Tests for the centralized area formula engine.

Validates buildable area, sellable area, internal/attached area split, and
weighted sellable proxy calculations against real estate underwriting assumptions.
"""

import pytest

from app.core.calculation_engine.areas import (
    calculate_buildable_area,
    calculate_internal_area,
    calculate_sellable_area,
    calculate_weighted_sellable_area,
    run_area_calculations,
)
from app.core.calculation_engine.types import AreaInputs


# ---------------------------------------------------------------------------
# calculate_buildable_area
# ---------------------------------------------------------------------------


def test_buildable_area_standard():
    """Buildable area = land area × FAR."""
    assert calculate_buildable_area(10_000.0, 2.5) == pytest.approx(25_000.0)


def test_buildable_area_far_one():
    """FAR of 1.0 means buildable area equals land area."""
    assert calculate_buildable_area(5_000.0, 1.0) == pytest.approx(5_000.0)


def test_buildable_area_zero_land_returns_zero():
    assert calculate_buildable_area(0.0, 2.5) == 0.0


def test_buildable_area_negative_land_returns_zero():
    assert calculate_buildable_area(-100.0, 2.5) == 0.0


def test_buildable_area_zero_far_returns_zero():
    assert calculate_buildable_area(10_000.0, 0.0) == 0.0


def test_buildable_area_negative_far_returns_zero():
    assert calculate_buildable_area(10_000.0, -1.0) == 0.0


def test_buildable_area_returns_float():
    result = calculate_buildable_area(10_000.0, 2.5)
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# calculate_sellable_area
# ---------------------------------------------------------------------------


def test_sellable_area_standard():
    """Sellable area = buildable area × sellable ratio."""
    assert calculate_sellable_area(25_000.0, 0.85) == pytest.approx(21_250.0)


def test_sellable_area_full_ratio():
    """Ratio of 1.0 means all buildable area is sellable."""
    assert calculate_sellable_area(20_000.0, 1.0) == pytest.approx(20_000.0)


def test_sellable_area_zero_buildable_returns_zero():
    assert calculate_sellable_area(0.0, 0.85) == 0.0


def test_sellable_area_negative_buildable_returns_zero():
    assert calculate_sellable_area(-500.0, 0.85) == 0.0


def test_sellable_area_zero_ratio_returns_zero():
    assert calculate_sellable_area(25_000.0, 0.0) == 0.0


def test_sellable_area_negative_ratio_returns_zero():
    assert calculate_sellable_area(25_000.0, -0.1) == 0.0


# ---------------------------------------------------------------------------
# calculate_internal_area
# ---------------------------------------------------------------------------


def test_internal_area_standard():
    """Internal area = total area − attached area."""
    assert calculate_internal_area(120.0, 20.0) == pytest.approx(100.0)


def test_internal_area_no_attached():
    """No attached area: internal area equals total area."""
    assert calculate_internal_area(100.0, 0.0) == pytest.approx(100.0)


def test_internal_area_negative_attached_treated_as_zero():
    """Negative attached area is treated as zero (no deduction)."""
    assert calculate_internal_area(100.0, -5.0) == pytest.approx(100.0)


def test_internal_area_attached_exceeds_total_clamped_to_zero():
    """When attached area exceeds total, result clamps to 0.0."""
    assert calculate_internal_area(50.0, 60.0) == 0.0


def test_internal_area_zero_total_returns_zero():
    assert calculate_internal_area(0.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# calculate_weighted_sellable_area
# ---------------------------------------------------------------------------


def test_weighted_sellable_area_default_weight():
    """Default weight = 0.5; attached area counts at 50 %."""
    result = calculate_weighted_sellable_area(100.0, 20.0)
    assert result == pytest.approx(110.0)


def test_weighted_sellable_area_full_weight():
    """Weight of 1.0 means attached area is fully counted."""
    result = calculate_weighted_sellable_area(100.0, 20.0, attached_area_weight=1.0)
    assert result == pytest.approx(120.0)


def test_weighted_sellable_area_zero_weight():
    """Weight of 0.0 means attached area is ignored."""
    result = calculate_weighted_sellable_area(100.0, 20.0, attached_area_weight=0.0)
    assert result == pytest.approx(100.0)


def test_weighted_sellable_area_weight_clamped_above_one():
    """Weight above 1.0 is clamped to 1.0."""
    result = calculate_weighted_sellable_area(100.0, 20.0, attached_area_weight=5.0)
    assert result == pytest.approx(120.0)


def test_weighted_sellable_area_weight_clamped_below_zero():
    """Negative weight is clamped to 0.0."""
    result = calculate_weighted_sellable_area(100.0, 20.0, attached_area_weight=-1.0)
    assert result == pytest.approx(100.0)


def test_weighted_sellable_area_negative_internal_treated_as_zero():
    result = calculate_weighted_sellable_area(-50.0, 20.0)
    assert result == pytest.approx(10.0)


def test_weighted_sellable_area_negative_attached_treated_as_zero():
    result = calculate_weighted_sellable_area(100.0, -10.0)
    assert result == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# run_area_calculations — composite runner
# ---------------------------------------------------------------------------


def test_run_area_calculations_standard():
    inputs = AreaInputs(land_area_sqm=10_000.0, permitted_far=2.5, sellable_ratio=0.85)
    outputs = run_area_calculations(inputs)
    assert outputs.buildable_area_sqm == pytest.approx(25_000.0)
    assert outputs.sellable_area_sqm == pytest.approx(21_250.0)


def test_run_area_calculations_zero_land():
    inputs = AreaInputs(land_area_sqm=0.0, permitted_far=2.5, sellable_ratio=0.85)
    outputs = run_area_calculations(inputs)
    assert outputs.buildable_area_sqm == 0.0
    assert outputs.sellable_area_sqm == 0.0


def test_run_area_calculations_proportional():
    """Doubling FAR should double both buildable and sellable area."""
    inputs_single = AreaInputs(land_area_sqm=5_000.0, permitted_far=1.0, sellable_ratio=0.80)
    inputs_double = AreaInputs(land_area_sqm=5_000.0, permitted_far=2.0, sellable_ratio=0.80)
    out1 = run_area_calculations(inputs_single)
    out2 = run_area_calculations(inputs_double)
    assert out2.buildable_area_sqm == pytest.approx(out1.buildable_area_sqm * 2)
    assert out2.sellable_area_sqm == pytest.approx(out1.sellable_area_sqm * 2)
