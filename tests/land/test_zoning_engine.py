"""
Tests for the Land Zoning & Regulation Engine.

Validates individual calculation functions and the full engine (run_zoning_calculation)
across a variety of scenarios including FAR-limited, height-limited,
coverage-limited, setback-adjusted, and parking ratio cases.
"""

import dataclasses
from math import sqrt

import pytest

from app.modules.land.zoning_engine import (
    ZoningInputs,
    ZoningResult,
    calculate_effective_buildable_area,
    calculate_effective_footprint,
    calculate_estimated_unit_capacity,
    calculate_max_buildable_area,
    calculate_max_floors,
    calculate_max_footprint_area,
    calculate_parking_required,
    calculate_setback_adjusted_area,
    run_zoning_calculation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_inputs(**overrides) -> ZoningInputs:
    """Return a ZoningInputs instance with sensible defaults, accepting overrides."""
    defaults = dict(
        land_area=10_000.0,
        far=3.5,
        coverage_ratio=0.6,
        max_height_m=45.0,
        floor_height_m=3.0,
        parking_ratio=1.2,
    )
    defaults.update(overrides)
    return ZoningInputs(**defaults)


# ---------------------------------------------------------------------------
# Individual formula functions — calculate_max_buildable_area
# ---------------------------------------------------------------------------

def test_max_buildable_area_basic():
    """max_buildable_area = land_area × FAR."""
    assert calculate_max_buildable_area(10_000.0, 3.5) == pytest.approx(35_000.0)


def test_max_buildable_area_far_one():
    """FAR of 1.0 yields buildable area equal to land area."""
    assert calculate_max_buildable_area(5_000.0, 1.0) == pytest.approx(5_000.0)


def test_max_buildable_area_fractional_far():
    """Fractional FAR produces proportional result."""
    assert calculate_max_buildable_area(8_000.0, 0.5) == pytest.approx(4_000.0)


# ---------------------------------------------------------------------------
# Individual formula functions — calculate_max_footprint_area
# ---------------------------------------------------------------------------

def test_max_footprint_area_basic():
    """max_footprint_area = land_area × coverage_ratio."""
    assert calculate_max_footprint_area(10_000.0, 0.6) == pytest.approx(6_000.0)


def test_max_footprint_area_full_coverage():
    """Coverage ratio of 1.0 means footprint equals land area."""
    assert calculate_max_footprint_area(4_000.0, 1.0) == pytest.approx(4_000.0)


def test_max_footprint_area_low_coverage():
    """Low coverage ratio significantly constrains footprint."""
    assert calculate_max_footprint_area(10_000.0, 0.3) == pytest.approx(3_000.0)


# ---------------------------------------------------------------------------
# Individual formula functions — calculate_max_floors
# ---------------------------------------------------------------------------

def test_max_floors_exact_division():
    """Exact division: 45m / 3m = 15 floors."""
    assert calculate_max_floors(45.0, 3.0) == 15


def test_max_floors_floored():
    """Non-exact height is floored: 40m / 3m = floor(13.33) = 13 floors."""
    assert calculate_max_floors(40.0, 3.0) == 13


def test_max_floors_low_building():
    """Single storey building: 3.5m / 3.5m = 1 floor."""
    assert calculate_max_floors(3.5, 3.5) == 1


def test_max_floors_zero_floor_height():
    """Zero floor height returns 0 (avoids division by zero)."""
    assert calculate_max_floors(30.0, 0.0) == 0


def test_max_floors_tall_building():
    """High-rise: 120m / 4m = 30 floors."""
    assert calculate_max_floors(120.0, 4.0) == 30


# ---------------------------------------------------------------------------
# Individual formula functions — calculate_setback_adjusted_area
# ---------------------------------------------------------------------------

def test_setback_adjusted_area_no_setbacks():
    """Zero setbacks leave land area unchanged."""
    assert calculate_setback_adjusted_area(10_000.0, 0.0, 0.0, 0.0) == pytest.approx(10_000.0)


def test_setback_adjusted_area_reduces_area():
    """Setbacks reduce area from full land_area.

    Square plot: side = sqrt(10000) = 100m.
    effective_depth = 100 - 5 (front) - 5 (rear) = 90m
    effective_width = 100 - 2×3 (side) = 94m
    adjusted = 90 × 94 = 8460 sqm
    """
    result = calculate_setback_adjusted_area(10_000.0, 5.0, 3.0, 5.0)
    assert result == pytest.approx(8_460.0)


def test_setback_adjusted_area_symmetric_setbacks():
    """Equal front and rear setbacks with no side setbacks."""
    side = sqrt(10_000.0)  # 100
    result = calculate_setback_adjusted_area(10_000.0, 5.0, 0.0, 5.0)
    assert result == pytest.approx((side - 10.0) * side)


def test_setback_adjusted_area_clamped_to_zero():
    """Excessive setbacks produce zero area, not a negative value."""
    result = calculate_setback_adjusted_area(100.0, 50.0, 0.0, 50.0)  # side = 10m
    assert result == pytest.approx(0.0)


def test_setback_adjusted_area_zero_land_area():
    """Zero land_area returns 0.0 without raising an error."""
    assert calculate_setback_adjusted_area(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0)


def test_setback_adjusted_area_negative_land_area():
    """Negative land_area returns 0.0 without calling sqrt() or raising an error."""
    assert calculate_setback_adjusted_area(-500.0, 5.0, 3.0, 5.0) == pytest.approx(0.0)
    assert calculate_setback_adjusted_area(-500.0, 0.0, 0.0, 0.0) == pytest.approx(0.0)


def test_setback_adjusted_area_only_side_setbacks():
    """Only side setbacks reduce width, not depth."""
    side = sqrt(10_000.0)
    result = calculate_setback_adjusted_area(10_000.0, 0.0, 5.0, 0.0)
    assert result == pytest.approx(side * (side - 10.0))


# ---------------------------------------------------------------------------
# Individual formula functions — calculate_effective_footprint
# ---------------------------------------------------------------------------

def test_effective_footprint_setbacks_binding():
    """Setback-adjusted footprint is smaller → it binds over coverage-only limit."""
    max_fp = 6_000.0   # land_area=10000, coverage=0.6
    setback_adj = 8_000.0
    cov = 0.6
    # setback_footprint = 8000 × 0.6 = 4800 < 6000
    result = calculate_effective_footprint(max_fp, setback_adj, cov)
    assert result == pytest.approx(4_800.0)


def test_effective_footprint_coverage_binding():
    """Coverage limit is smaller when setbacks barely reduce area."""
    max_fp = 6_000.0
    setback_adj = 10_000.0  # no reduction
    cov = 0.6
    # setback_footprint = 10000 × 0.6 = 6000 == max_fp
    result = calculate_effective_footprint(max_fp, setback_adj, cov)
    assert result == pytest.approx(6_000.0)


# ---------------------------------------------------------------------------
# Individual formula functions — calculate_effective_buildable_area
# ---------------------------------------------------------------------------

def test_effective_buildable_far_binding():
    """FAR limits effective buildable area when footprint × floors > FAR limit."""
    # max_buildable=35000, footprint=6000, floors=15 → 6000×15=90000 > 35000
    result = calculate_effective_buildable_area(35_000.0, 6_000.0, 15)
    assert result == pytest.approx(35_000.0)


def test_effective_buildable_height_binding():
    """Height (footprint × floors) limits buildable area when < FAR limit."""
    # max_buildable=50000, footprint=3000, floors=10 → 3000×10=30000 < 50000
    result = calculate_effective_buildable_area(50_000.0, 3_000.0, 10)
    assert result == pytest.approx(30_000.0)


def test_effective_buildable_equal_limits():
    """When both limits are equal the result equals either."""
    result = calculate_effective_buildable_area(20_000.0, 4_000.0, 5)
    assert result == pytest.approx(20_000.0)


# ---------------------------------------------------------------------------
# Individual formula functions — calculate_estimated_unit_capacity
# ---------------------------------------------------------------------------

def test_estimated_unit_capacity_basic():
    """Unit capacity = floor(effective_buildable_area / avg_unit_size_sqm)."""
    assert calculate_estimated_unit_capacity(35_000.0, 100.0) == 350


def test_estimated_unit_capacity_floored():
    """Result is always an integer floor."""
    assert calculate_estimated_unit_capacity(35_500.0, 100.0) == 355


def test_estimated_unit_capacity_none_when_no_unit_size():
    """Returns None when avg_unit_size_sqm is not provided."""
    assert calculate_estimated_unit_capacity(35_000.0, None) is None


def test_estimated_unit_capacity_none_when_zero_unit_size():
    """Returns None when avg_unit_size_sqm is zero (avoids division by zero)."""
    assert calculate_estimated_unit_capacity(35_000.0, 0.0) is None


def test_estimated_unit_capacity_none_when_negative_unit_size():
    """Returns None when avg_unit_size_sqm is negative (non-positive guard)."""
    assert calculate_estimated_unit_capacity(35_000.0, -50.0) is None


# ---------------------------------------------------------------------------
# Individual formula functions — calculate_parking_required
# ---------------------------------------------------------------------------

def test_parking_required_basic():
    """Parking = round(units × parking_ratio)."""
    assert calculate_parking_required(200, 1.2) == 240


def test_parking_required_fractional_rounds():
    """Fractional parking is rounded."""
    # 210 × 1.2 = 252.0
    assert calculate_parking_required(210, 1.2) == 252


def test_parking_required_zero_when_no_units():
    """Returns 0 when estimated_unit_capacity is None."""
    assert calculate_parking_required(None, 1.5) == 0


def test_parking_required_zero_ratio():
    """Zero parking ratio produces zero parking spaces."""
    assert calculate_parking_required(200, 0.0) == 0


# ---------------------------------------------------------------------------
# run_zoning_calculation — full engine, FAR-limited
# ---------------------------------------------------------------------------

def test_far_limits_buildable_area():
    """FAR is the binding constraint when height × footprint > FAR limit.

    land_area = 10 000 sqm, FAR = 3.5 → max_buildable = 35 000 sqm
    coverage  = 0.6         → footprint = 6 000 sqm
    height    = 45m / 3m    → 15 floors
    footprint × floors = 6 000 × 15 = 90 000 > 35 000  → FAR binds.
    """
    inputs = _base_inputs()
    result = run_zoning_calculation(inputs)

    assert result.max_buildable_area == pytest.approx(35_000.0)
    assert result.effective_buildable_area == pytest.approx(35_000.0)
    assert result.max_floors == 15


def test_height_limits_floor_count():
    """Height divided by floor height determines max floors.

    30m / 3m = 10 floors; 30m / 4m = floor(7.5) = 7 floors.
    """
    inputs_10 = _base_inputs(max_height_m=30.0, floor_height_m=3.0)
    inputs_7 = _base_inputs(max_height_m=30.0, floor_height_m=4.0)

    assert run_zoning_calculation(inputs_10).max_floors == 10
    assert run_zoning_calculation(inputs_7).max_floors == 7


def test_height_limits_effective_buildable_area():
    """Low height cap makes footprint × floors the binding constraint.

    coverage=0.6  → footprint = 6 000 sqm
    height=9m / 3m/floor → 3 floors → 6000×3 = 18 000 sqm
    FAR=3.5 → max_buildable = 35 000 sqm
    18 000 < 35 000 → height binds.
    """
    inputs = _base_inputs(max_height_m=9.0, floor_height_m=3.0)
    result = run_zoning_calculation(inputs)

    assert result.max_floors == 3
    assert result.effective_buildable_area == pytest.approx(18_000.0)


def test_coverage_limits_footprint():
    """Coverage ratio directly controls the maximum footprint area."""
    inputs_60 = _base_inputs(coverage_ratio=0.6)
    inputs_30 = _base_inputs(coverage_ratio=0.3)

    result_60 = run_zoning_calculation(inputs_60)
    result_30 = run_zoning_calculation(inputs_30)

    assert result_60.max_footprint_area == pytest.approx(6_000.0)
    assert result_30.max_footprint_area == pytest.approx(3_000.0)
    assert result_60.max_footprint_area > result_30.max_footprint_area


def test_coverage_limits_effective_buildable_area():
    """Very low coverage makes footprint × floors the binding constraint.

    coverage=0.1 → footprint = 1000 sqm
    15 floors    → 1000×15 = 15 000 sqm
    FAR=3.5      → max_buildable = 35 000 sqm
    15 000 < 35 000 → coverage/height binds.
    """
    inputs = _base_inputs(coverage_ratio=0.1)
    result = run_zoning_calculation(inputs)

    assert result.max_footprint_area == pytest.approx(1_000.0)
    assert result.effective_buildable_area == pytest.approx(15_000.0)


# ---------------------------------------------------------------------------
# run_zoning_calculation — setback effects
# ---------------------------------------------------------------------------

def test_setback_reduces_buildable_footprint():
    """Setbacks reduce the effective footprint and effective buildable area.

    We use a high FAR (far=10) so that footprint × floors is the binding
    constraint, and setbacks then reduce the effective_buildable_area.

    Square plot side = 100m.
    With front=5, side=3, rear=5:
      setback_adjusted_area = 90×94 = 8460 sqm
      setback_footprint = 8460×0.6 = 5076 sqm  < max_footprint=6000
      effective_footprint = 5076 sqm
      effective_buildable = min(100000, 5076×15) = min(100000, 76140) = 76140

    No setbacks → effective_footprint = 6000 sqm
      effective_buildable = min(100000, 6000×15) = min(100000, 90000) = 90000
    """
    no_setback = _base_inputs(far=10.0)
    with_setback = _base_inputs(far=10.0, setback_front=5.0, setback_side=3.0, setback_rear=5.0)

    res_no = run_zoning_calculation(no_setback)
    res_with = run_zoning_calculation(with_setback)

    assert res_with.setback_adjusted_area < res_no.setback_adjusted_area
    assert res_with.effective_footprint < res_no.effective_footprint
    assert res_with.effective_buildable_area < res_no.effective_buildable_area


def test_setback_adjusted_area_stored_in_result():
    """Setback-adjusted area is reported in the result."""
    inputs = _base_inputs(setback_front=5.0, setback_side=3.0, setback_rear=5.0)
    result = run_zoning_calculation(inputs)
    assert result.setback_adjusted_area == pytest.approx(8_460.0)


def test_no_setbacks_adjusted_area_equals_land_area():
    """Without setbacks the setback_adjusted_area equals land_area."""
    inputs = _base_inputs()
    result = run_zoning_calculation(inputs)
    assert result.setback_adjusted_area == pytest.approx(inputs.land_area)


# ---------------------------------------------------------------------------
# run_zoning_calculation — parking ratio
# ---------------------------------------------------------------------------

def test_parking_ratio_requirement():
    """Parking spaces scale proportionally with unit capacity and parking ratio.

    avg_unit_size_sqm=100, effective_buildable≈35000 → ~350 units
    parking_ratio=1.2 → 350×1.2 = 420 spaces.
    """
    inputs = _base_inputs(avg_unit_size_sqm=100.0, parking_ratio=1.2)
    result = run_zoning_calculation(inputs)

    assert result.estimated_unit_capacity == 350
    assert result.parking_required == 420


def test_higher_parking_ratio_more_spaces():
    """Higher parking ratio yields more required spaces."""
    low = _base_inputs(avg_unit_size_sqm=100.0, parking_ratio=1.0)
    high = _base_inputs(avg_unit_size_sqm=100.0, parking_ratio=2.0)

    assert run_zoning_calculation(high).parking_required > run_zoning_calculation(low).parking_required


def test_parking_zero_without_unit_size():
    """parking_required is 0 when avg_unit_size_sqm is not provided."""
    inputs = _base_inputs(parking_ratio=1.5)
    result = run_zoning_calculation(inputs)
    assert result.parking_required == 0
    assert result.estimated_unit_capacity is None


# ---------------------------------------------------------------------------
# run_zoning_calculation — edge cases
# ---------------------------------------------------------------------------

def test_result_is_frozen():
    """ZoningResult dataclass is frozen (immutable)."""
    result = run_zoning_calculation(_base_inputs())
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.max_floors = 99  # type: ignore[misc]


def test_small_parcel():
    """Engine works correctly for a small parcel (500 sqm)."""
    inputs = ZoningInputs(
        land_area=500.0,
        far=2.0,
        coverage_ratio=0.5,
        max_height_m=12.0,
        floor_height_m=3.0,
        parking_ratio=1.0,
        avg_unit_size_sqm=80.0,
    )
    result = run_zoning_calculation(inputs)

    assert result.max_buildable_area == pytest.approx(1_000.0)
    assert result.max_footprint_area == pytest.approx(250.0)
    assert result.max_floors == 4
    # footprint × floors = 250 × 4 = 1000 == max_buildable → either limit
    assert result.effective_buildable_area == pytest.approx(1_000.0)


def test_large_parcel():
    """Engine works correctly for a large parcel (100 000 sqm)."""
    inputs = ZoningInputs(
        land_area=100_000.0,
        far=4.0,
        coverage_ratio=0.5,
        max_height_m=60.0,
        floor_height_m=3.0,
        parking_ratio=1.0,
    )
    result = run_zoning_calculation(inputs)
    assert result.max_buildable_area == pytest.approx(400_000.0)
    assert result.max_floors == 20


def test_far_sensitivity():
    """Higher FAR yields higher max_buildable_area."""
    low_far = _base_inputs(far=2.0)
    high_far = _base_inputs(far=5.0)

    assert (
        run_zoning_calculation(high_far).max_buildable_area
        > run_zoning_calculation(low_far).max_buildable_area
    )


def test_floor_height_sensitivity():
    """Taller floor height means fewer floors for the same max_height_m."""
    low_fh = _base_inputs(floor_height_m=3.0)
    high_fh = _base_inputs(floor_height_m=5.0)

    assert (
        run_zoning_calculation(low_fh).max_floors
        > run_zoning_calculation(high_fh).max_floors
    )


def test_inputs_are_frozen():
    """ZoningInputs dataclass is frozen (immutable)."""
    inputs = _base_inputs()
    with pytest.raises(dataclasses.FrozenInstanceError):
        inputs.land_area = 999.0  # type: ignore[misc]


def test_result_type():
    """run_zoning_calculation returns a ZoningResult instance."""
    assert isinstance(run_zoning_calculation(_base_inputs()), ZoningResult)
