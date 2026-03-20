"""
Tests for the land valuation engine.

Validates the residual land value calculation, edge cases, and
sensitivity to margin targets.
"""

import pytest

from app.modules.land.engines.valuation_engine import (
    ValuationInputs,
    ValuationOutputs,
    calculate_land_value,
    calculate_land_value_per_sqm,
    calculate_residual_margin,
    calculate_soft_costs,
    calculate_target_profit,
    calculate_total_cost,
    run_land_valuation,
)


# ---------------------------------------------------------------------------
# Individual formula functions
# ---------------------------------------------------------------------------

def test_calculate_soft_costs():
    """Soft costs = construction cost × soft cost percentage."""
    assert calculate_soft_costs(10_000_000.0, 0.10) == pytest.approx(1_000_000.0)


def test_calculate_total_cost():
    """Total cost = construction cost + soft costs."""
    assert calculate_total_cost(10_000_000.0, 1_000_000.0) == pytest.approx(11_000_000.0)


def test_calculate_target_profit():
    """Target profit = GDV × developer margin target."""
    assert calculate_target_profit(20_000_000.0, 0.20) == pytest.approx(4_000_000.0)


def test_calculate_land_value():
    """Residual land value = GDV − total cost − target profit."""
    # 20M − 11M − 4M = 5M
    assert calculate_land_value(20_000_000.0, 11_000_000.0, 4_000_000.0) == pytest.approx(5_000_000.0)


def test_calculate_land_value_per_sqm():
    """Land value per sqm = land value / sellable area."""
    assert calculate_land_value_per_sqm(5_000_000.0, 1_000.0) == pytest.approx(5_000.0)


def test_calculate_land_value_per_sqm_zero_area():
    """Returns 0.0 when sellable area is zero to avoid division by zero."""
    assert calculate_land_value_per_sqm(5_000_000.0, 0.0) == 0.0


def test_calculate_residual_margin():
    """Residual margin = land value / GDV."""
    assert calculate_residual_margin(5_000_000.0, 20_000_000.0) == pytest.approx(0.25)


def test_calculate_residual_margin_zero_gdv():
    """Returns 0.0 when GDV is zero to avoid division by zero."""
    assert calculate_residual_margin(5_000_000.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# run_land_valuation — full engine
# ---------------------------------------------------------------------------

def test_run_land_valuation_correct_residual():
    """Engine produces correct residual land value for a standard deal.

    GDV        = 20 000 000
    Constr.    = 10 000 000
    Soft (10%) =  1 000 000
    Total cost = 11 000 000
    Margin 20% =  4 000 000
    Land value =  5 000 000  (= GDV − total_cost − target_profit)
    LV / sqm   =    500.00   (5 000 000 / 10 000 sqm)
    Max bid    =  5 000 000
    Residual % =      0.25   (5 000 000 / 20 000 000)
    """
    inputs = ValuationInputs(
        gdv=20_000_000.0,
        construction_cost=10_000_000.0,
        soft_cost_percentage=0.10,
        developer_margin_target=0.20,
        sellable_area_sqm=10_000.0,
    )
    out = run_land_valuation(inputs)

    assert isinstance(out, ValuationOutputs)
    assert out.soft_costs == pytest.approx(1_000_000.0)
    assert out.total_cost == pytest.approx(11_000_000.0)
    assert out.target_profit == pytest.approx(4_000_000.0)
    assert out.land_value == pytest.approx(5_000_000.0)
    assert out.land_value_per_sqm == pytest.approx(500.0)
    assert out.max_land_bid == pytest.approx(5_000_000.0)
    assert out.residual_margin == pytest.approx(0.25)


def test_run_land_valuation_negative_land_value():
    """Engine detects negative residual when costs exceed GDV minus margin.

    When construction cost is too high relative to GDV the residual land
    value is negative, meaning the deal does not support a positive land bid.
    """
    inputs = ValuationInputs(
        gdv=10_000_000.0,
        construction_cost=9_000_000.0,
        soft_cost_percentage=0.10,
        developer_margin_target=0.20,
        sellable_area_sqm=5_000.0,
    )
    out = run_land_valuation(inputs)

    # total_cost = 9 000 000 + 900 000 = 9 900 000
    # target_profit = 10 000 000 * 0.20 = 2 000 000
    # land_value = 10 000 000 - 9 900 000 - 2 000 000 = -1 900 000
    assert out.land_value < 0
    assert out.max_land_bid < 0
    assert out.residual_margin < 0


def test_run_land_valuation_zero_soft_cost():
    """Engine works correctly when soft cost percentage is zero."""
    inputs = ValuationInputs(
        gdv=10_000_000.0,
        construction_cost=6_000_000.0,
        soft_cost_percentage=0.0,
        developer_margin_target=0.15,
        sellable_area_sqm=4_000.0,
    )
    out = run_land_valuation(inputs)

    # total_cost = 6 000 000
    # target_profit = 1 500 000
    # land_value = 2 500 000
    assert out.soft_costs == pytest.approx(0.0)
    assert out.total_cost == pytest.approx(6_000_000.0)
    assert out.land_value == pytest.approx(2_500_000.0)
    assert out.land_value_per_sqm == pytest.approx(625.0)


def test_run_land_valuation_margin_sensitivity():
    """Higher developer margin target reduces residual land value."""
    base_inputs = ValuationInputs(
        gdv=20_000_000.0,
        construction_cost=10_000_000.0,
        soft_cost_percentage=0.10,
        developer_margin_target=0.10,
        sellable_area_sqm=10_000.0,
    )
    high_margin_inputs = ValuationInputs(
        gdv=20_000_000.0,
        construction_cost=10_000_000.0,
        soft_cost_percentage=0.10,
        developer_margin_target=0.30,
        sellable_area_sqm=10_000.0,
    )
    base_out = run_land_valuation(base_inputs)
    high_out = run_land_valuation(high_margin_inputs)

    assert base_out.land_value > high_out.land_value


def test_run_land_valuation_outputs_are_frozen():
    """ValuationOutputs dataclass is frozen (immutable)."""
    inputs = ValuationInputs(
        gdv=10_000_000.0,
        construction_cost=6_000_000.0,
        soft_cost_percentage=0.10,
        developer_margin_target=0.20,
        sellable_area_sqm=5_000.0,
    )
    out = run_land_valuation(inputs)

    with pytest.raises(Exception):
        out.land_value = 999  # type: ignore[misc]


def test_run_land_valuation_max_land_bid_equals_land_value():
    """max_land_bid always equals land_value (same concept, explicit alias)."""
    inputs = ValuationInputs(
        gdv=15_000_000.0,
        construction_cost=8_000_000.0,
        soft_cost_percentage=0.12,
        developer_margin_target=0.18,
        sellable_area_sqm=6_000.0,
    )
    out = run_land_valuation(inputs)

    assert out.max_land_bid == out.land_value
