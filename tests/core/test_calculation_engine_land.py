"""
Tests for the centralized land underwriting formula engine.

Validates land price per sqm basis, residual land value, maximum supported
acquisition price, and sensitivity of RLV to margin targets and cost changes.
"""

import pytest

from app.core.calculation_engine.land import (
    calculate_effective_land_basis,
    calculate_land_price_per_buildable_sqm,
    calculate_land_price_per_sellable_sqm,
    calculate_land_price_per_sqm,
    calculate_margin_impact,
    calculate_residual_land_value,
    run_land_calculations,
)
from app.core.calculation_engine.types import LandInputs


# ---------------------------------------------------------------------------
# calculate_land_price_per_sqm
# ---------------------------------------------------------------------------


def test_land_price_per_sqm_standard():
    assert calculate_land_price_per_sqm(5_000_000.0, 1_000.0) == pytest.approx(5_000.0)


def test_land_price_per_sqm_zero_area_returns_zero():
    assert calculate_land_price_per_sqm(5_000_000.0, 0.0) == 0.0


def test_land_price_per_sqm_negative_area_returns_zero():
    assert calculate_land_price_per_sqm(5_000_000.0, -500.0) == 0.0


def test_land_price_per_sqm_zero_acquisition_price():
    assert calculate_land_price_per_sqm(0.0, 1_000.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# calculate_land_price_per_buildable_sqm
# ---------------------------------------------------------------------------


def test_land_price_per_buildable_sqm_standard():
    assert calculate_land_price_per_buildable_sqm(5_000_000.0, 2_500.0) == pytest.approx(2_000.0)


def test_land_price_per_buildable_sqm_zero_area_returns_zero():
    assert calculate_land_price_per_buildable_sqm(5_000_000.0, 0.0) == 0.0


def test_land_price_per_buildable_sqm_negative_area_returns_zero():
    assert calculate_land_price_per_buildable_sqm(5_000_000.0, -100.0) == 0.0


# ---------------------------------------------------------------------------
# calculate_land_price_per_sellable_sqm
# ---------------------------------------------------------------------------


def test_land_price_per_sellable_sqm_standard():
    assert calculate_land_price_per_sellable_sqm(5_000_000.0, 2_000.0) == pytest.approx(2_500.0)


def test_land_price_per_sellable_sqm_zero_area_returns_zero():
    assert calculate_land_price_per_sellable_sqm(5_000_000.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# calculate_residual_land_value
# ---------------------------------------------------------------------------


def test_rlv_standard_positive():
    # gdv=10M, cost=7M, target=20% → target_profit=2M → RLV=1M
    rlv = calculate_residual_land_value(10_000_000.0, 7_000_000.0, 0.20)
    assert rlv == pytest.approx(1_000_000.0)


def test_rlv_negative_when_cost_too_high():
    """High costs should produce a negative RLV (development unviable)."""
    rlv = calculate_residual_land_value(10_000_000.0, 12_000_000.0, 0.20)
    assert rlv < 0.0


def test_rlv_zero_margin_target():
    """With zero margin target, RLV = GDV − cost."""
    rlv = calculate_residual_land_value(10_000_000.0, 8_000_000.0, 0.0)
    assert rlv == pytest.approx(2_000_000.0)


def test_rlv_full_margin_target():
    """With 100 % margin target, developer takes all revenue — RLV is negative."""
    rlv = calculate_residual_land_value(10_000_000.0, 5_000_000.0, 1.0)
    assert rlv == pytest.approx(-5_000_000.0)


def test_rlv_breakeven_scenario():
    """When cost + target_profit exactly equals GDV, RLV is zero."""
    # gdv=10M, cost=8M, target=0.20 → target_profit=2M → RLV=0
    rlv = calculate_residual_land_value(10_000_000.0, 8_000_000.0, 0.20)
    assert rlv == pytest.approx(0.0)


def test_rlv_higher_cost_reduces_rlv():
    rlv_low_cost = calculate_residual_land_value(10_000_000.0, 6_000_000.0, 0.20)
    rlv_high_cost = calculate_residual_land_value(10_000_000.0, 7_000_000.0, 0.20)
    assert rlv_low_cost > rlv_high_cost


def test_rlv_higher_margin_target_reduces_rlv():
    rlv_low = calculate_residual_land_value(10_000_000.0, 7_000_000.0, 0.10)
    rlv_high = calculate_residual_land_value(10_000_000.0, 7_000_000.0, 0.20)
    assert rlv_low > rlv_high


# ---------------------------------------------------------------------------
# calculate_margin_impact
# ---------------------------------------------------------------------------


def test_margin_impact_standard():
    assert calculate_margin_impact(2_000_000.0, 10_000_000.0) == pytest.approx(0.20)


def test_margin_impact_zero_gdv_returns_zero():
    assert calculate_margin_impact(2_000_000.0, 0.0) == 0.0


def test_margin_impact_negative_rlv():
    """Negative RLV produces a negative margin impact."""
    assert calculate_margin_impact(-1_000_000.0, 10_000_000.0) == pytest.approx(-0.10)


# ---------------------------------------------------------------------------
# run_land_calculations — composite runner
# ---------------------------------------------------------------------------


def test_run_land_calculations_standard():
    inputs = LandInputs(
        land_area_sqm=1_000.0,
        acquisition_price=5_000_000.0,
        buildable_area_sqm=2_500.0,
        sellable_area_sqm=2_000.0,
        gdv=20_000_000.0,
        total_development_cost=14_000_000.0,
        developer_margin_target=0.20,
    )
    outputs = run_land_calculations(inputs)
    # land_price_per_sqm = 5M / 1000 = 5000
    assert outputs.land_price_per_sqm == pytest.approx(5_000.0)
    # land_price_per_buildable_sqm = 5M / 2500 = 2000
    assert outputs.land_price_per_buildable_sqm == pytest.approx(2_000.0)
    # land_price_per_sellable_sqm = 5M / 2000 = 2500
    assert outputs.land_price_per_sellable_sqm == pytest.approx(2_500.0)
    # rlv = 20M - 14M - 0.20*20M = 20M - 14M - 4M = 2M
    assert outputs.residual_land_value == pytest.approx(2_000_000.0)
    assert outputs.max_supported_acquisition_price == pytest.approx(2_000_000.0)
    # margin_impact = 2M / 20M = 0.10
    assert outputs.margin_impact == pytest.approx(0.10)


def test_run_land_calculations_negative_rlv():
    """Unviable development: RLV and max_supported_acquisition_price are negative."""
    inputs = LandInputs(
        land_area_sqm=1_000.0,
        acquisition_price=8_000_000.0,
        buildable_area_sqm=2_000.0,
        sellable_area_sqm=1_500.0,
        gdv=10_000_000.0,
        total_development_cost=12_000_000.0,
        developer_margin_target=0.20,
    )
    outputs = run_land_calculations(inputs)
    assert outputs.residual_land_value < 0.0
    assert outputs.max_supported_acquisition_price < 0.0
    assert outputs.margin_impact < 0.0


def test_run_land_calculations_zero_areas_return_zero_basis():
    inputs = LandInputs(
        land_area_sqm=0.0,
        acquisition_price=5_000_000.0,
        buildable_area_sqm=0.0,
        sellable_area_sqm=0.0,
        gdv=10_000_000.0,
        total_development_cost=8_000_000.0,
        developer_margin_target=0.20,
    )
    outputs = run_land_calculations(inputs)
    assert outputs.land_price_per_sqm == 0.0
    assert outputs.land_price_per_buildable_sqm == 0.0
    assert outputs.land_price_per_sellable_sqm == 0.0


# ---------------------------------------------------------------------------
# calculate_effective_land_basis
# ---------------------------------------------------------------------------


def test_effective_land_basis_with_transaction_cost():
    """Effective basis includes acquisition price AND transaction costs."""
    # AED 5M acquisition + AED 250K transaction costs → AED 5.25M effective
    basis = calculate_effective_land_basis(5_000_000.0, 250_000.0)
    assert basis == pytest.approx(5_250_000.0)


def test_effective_land_basis_zero_transaction_cost():
    """Effective basis equals acquisition price when transaction cost is zero."""
    basis = calculate_effective_land_basis(5_000_000.0, 0.0)
    assert basis == pytest.approx(5_000_000.0)


def test_effective_land_basis_high_transaction_cost():
    """Transaction costs materially change effective basis."""
    # 10 % transaction cost on a 10M parcel → 11M effective
    basis = calculate_effective_land_basis(10_000_000.0, 1_000_000.0)
    assert basis == pytest.approx(11_000_000.0)


# ---------------------------------------------------------------------------
# run_land_calculations — effective basis fields
# ---------------------------------------------------------------------------


def test_run_land_calculations_effective_basis_included():
    """run_land_calculations populates effective_land_basis correctly."""
    # acquisition=5M, transaction_cost=500K → effective=5.5M
    inputs = LandInputs(
        land_area_sqm=1_000.0,
        acquisition_price=5_000_000.0,
        buildable_area_sqm=2_500.0,
        sellable_area_sqm=2_000.0,
        gdv=20_000_000.0,
        total_development_cost=14_000_000.0,
        developer_margin_target=0.20,
        transaction_cost=500_000.0,
    )
    outputs = run_land_calculations(inputs)

    assert outputs.effective_land_basis == pytest.approx(5_500_000.0)
    # effective per gross sqm = 5.5M / 1000 = 5500
    assert outputs.effective_land_price_per_gross_sqm == pytest.approx(5_500.0)
    # effective per buildable sqm = 5.5M / 2500 = 2200
    assert outputs.effective_land_price_per_buildable_sqm == pytest.approx(2_200.0)
    # effective per sellable sqm = 5.5M / 2000 = 2750
    assert outputs.effective_land_price_per_sellable_sqm == pytest.approx(2_750.0)


def test_run_land_calculations_zero_transaction_cost_effective_equals_acquisition():
    """With zero transaction cost, effective basis == acquisition price."""
    inputs = LandInputs(
        land_area_sqm=1_000.0,
        acquisition_price=5_000_000.0,
        buildable_area_sqm=2_500.0,
        sellable_area_sqm=2_000.0,
        gdv=20_000_000.0,
        total_development_cost=14_000_000.0,
        developer_margin_target=0.20,
        transaction_cost=0.0,
    )
    outputs = run_land_calculations(inputs)

    assert outputs.effective_land_basis == pytest.approx(5_000_000.0)
    assert outputs.effective_land_price_per_gross_sqm == pytest.approx(5_000.0)
    assert outputs.effective_land_price_per_buildable_sqm == pytest.approx(2_000.0)
    assert outputs.effective_land_price_per_sellable_sqm == pytest.approx(2_500.0)


def test_run_land_calculations_default_transaction_cost_backward_compat():
    """LandInputs without transaction_cost defaults to 0 (backward compat)."""
    inputs = LandInputs(
        land_area_sqm=1_000.0,
        acquisition_price=5_000_000.0,
        buildable_area_sqm=2_500.0,
        sellable_area_sqm=2_000.0,
        gdv=20_000_000.0,
        total_development_cost=14_000_000.0,
        developer_margin_target=0.20,
    )
    outputs = run_land_calculations(inputs)
    # With default transaction_cost=0, effective basis == acquisition price
    assert outputs.effective_land_basis == pytest.approx(5_000_000.0)
    assert outputs.effective_land_price_per_gross_sqm == pytest.approx(5_000.0)


def test_run_land_calculations_effective_basis_zero_areas_return_zero():
    """Effective per-sqm metrics return 0.0 when areas are zero."""
    inputs = LandInputs(
        land_area_sqm=0.0,
        acquisition_price=5_000_000.0,
        buildable_area_sqm=0.0,
        sellable_area_sqm=0.0,
        gdv=10_000_000.0,
        total_development_cost=8_000_000.0,
        developer_margin_target=0.20,
        transaction_cost=500_000.0,
    )
    outputs = run_land_calculations(inputs)
    assert outputs.effective_land_basis == pytest.approx(5_500_000.0)
    assert outputs.effective_land_price_per_gross_sqm == 0.0
    assert outputs.effective_land_price_per_buildable_sqm == 0.0
    assert outputs.effective_land_price_per_sellable_sqm == 0.0


def test_run_land_calculations_transaction_cost_increases_effective_prices():
    """Adding transaction cost increases all effective per-sqm prices."""
    base_inputs = LandInputs(
        land_area_sqm=1_000.0,
        acquisition_price=5_000_000.0,
        buildable_area_sqm=2_500.0,
        sellable_area_sqm=2_000.0,
        gdv=20_000_000.0,
        total_development_cost=14_000_000.0,
        developer_margin_target=0.20,
        transaction_cost=0.0,
    )
    with_cost_inputs = LandInputs(
        land_area_sqm=1_000.0,
        acquisition_price=5_000_000.0,
        buildable_area_sqm=2_500.0,
        sellable_area_sqm=2_000.0,
        gdv=20_000_000.0,
        total_development_cost=14_000_000.0,
        developer_margin_target=0.20,
        transaction_cost=500_000.0,
    )
    base_out = run_land_calculations(base_inputs)
    with_cost_out = run_land_calculations(with_cost_inputs)

    assert with_cost_out.effective_land_price_per_gross_sqm > base_out.effective_land_price_per_gross_sqm
    assert with_cost_out.effective_land_price_per_buildable_sqm > base_out.effective_land_price_per_buildable_sqm
    assert with_cost_out.effective_land_price_per_sellable_sqm > base_out.effective_land_price_per_sellable_sqm
