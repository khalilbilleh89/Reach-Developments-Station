"""
Tests for the centralized return and profitability metrics engine.

Validates ROI, ROE, IRR, NPV, payback period, break-even pricing, equity
multiple, and developer margin against real-estate feasibility expectations.
"""

import pytest

from app.core.calculation_engine.returns import (
    build_development_cashflows,
    calculate_break_even_price_per_sqm,
    calculate_break_even_sellable_sqm,
    calculate_developer_margin,
    calculate_equity_multiple,
    calculate_gross_profit,
    calculate_irr,
    calculate_npv,
    calculate_payback_period_months,
    calculate_roe,
    calculate_roi,
    run_return_calculations,
)
from app.core.calculation_engine.types import ReturnInputs


# ---------------------------------------------------------------------------
# calculate_gross_profit
# ---------------------------------------------------------------------------


def test_gross_profit_profitable():
    assert calculate_gross_profit(10_000_000.0, 8_000_000.0) == pytest.approx(2_000_000.0)


def test_gross_profit_loss():
    assert calculate_gross_profit(8_000_000.0, 10_000_000.0) == pytest.approx(-2_000_000.0)


def test_gross_profit_breakeven():
    assert calculate_gross_profit(5_000_000.0, 5_000_000.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# calculate_developer_margin
# ---------------------------------------------------------------------------


def test_developer_margin_standard():
    assert calculate_developer_margin(2_000_000.0, 10_000_000.0) == pytest.approx(0.20)


def test_developer_margin_zero_gdv_returns_zero():
    assert calculate_developer_margin(1_000_000.0, 0.0) == 0.0


def test_developer_margin_negative_profit():
    assert calculate_developer_margin(-1_000_000.0, 10_000_000.0) == pytest.approx(-0.10)


# ---------------------------------------------------------------------------
# calculate_roi
# ---------------------------------------------------------------------------


def test_roi_standard():
    """ROI = gross profit / total cost."""
    assert calculate_roi(2_000_000.0, 8_000_000.0) == pytest.approx(0.25)


def test_roi_zero_cost_returns_zero():
    assert calculate_roi(1_000_000.0, 0.0) == 0.0


def test_roi_loss_is_negative():
    assert calculate_roi(-500_000.0, 5_000_000.0) < 0.0


# ---------------------------------------------------------------------------
# calculate_roe
# ---------------------------------------------------------------------------


def test_roe_standard():
    assert calculate_roe(2_000_000.0, 4_000_000.0) == pytest.approx(0.50)


def test_roe_zero_equity_returns_zero():
    assert calculate_roe(1_000_000.0, 0.0) == 0.0


def test_roe_negative_equity_returns_zero():
    assert calculate_roe(1_000_000.0, -1_000_000.0) == 0.0


# ---------------------------------------------------------------------------
# calculate_equity_multiple
# ---------------------------------------------------------------------------


def test_equity_multiple_standard():
    assert calculate_equity_multiple(10_000_000.0, 8_000_000.0) == pytest.approx(1.25)


def test_equity_multiple_zero_cost_returns_zero():
    assert calculate_equity_multiple(10_000_000.0, 0.0) == 0.0


def test_equity_multiple_below_one_is_loss():
    assert calculate_equity_multiple(4_000_000.0, 5_000_000.0) < 1.0


# ---------------------------------------------------------------------------
# calculate_irr
# ---------------------------------------------------------------------------


def test_irr_profitable_project_is_positive():
    irr = calculate_irr(8_000_000.0, 12_000_000.0, 24)
    assert irr > 0.0


def test_irr_unprofitable_project_is_negative():
    irr = calculate_irr(12_000_000.0, 8_000_000.0, 24)
    assert irr < 0.0


def test_irr_breakeven_project_near_zero():
    irr = calculate_irr(5_000_000.0, 5_000_000.0, 24)
    assert abs(irr) < 0.05


def test_irr_zero_total_cost_returns_zero():
    assert calculate_irr(0.0, 5_000_000.0, 24) == 0.0


def test_irr_zero_months_returns_zero():
    assert calculate_irr(5_000_000.0, 8_000_000.0, 0) == 0.0


def test_irr_negative_months_returns_zero():
    assert calculate_irr(5_000_000.0, 8_000_000.0, -12) == 0.0


def test_irr_zero_gdv_returns_minus_one():
    assert calculate_irr(5_000_000.0, 0.0, 24) == -1.0


def test_irr_longer_period_reduces_annualised_irr():
    irr_short = calculate_irr(5_000_000.0, 8_000_000.0, 12)
    irr_long = calculate_irr(5_000_000.0, 8_000_000.0, 48)
    assert irr_short > irr_long


def test_irr_returns_float():
    assert isinstance(calculate_irr(5_000_000.0, 8_000_000.0, 24), float)


# ---------------------------------------------------------------------------
# build_development_cashflows
# ---------------------------------------------------------------------------


def test_build_cashflows_standard_length():
    cashflows = build_development_cashflows(1_000_000.0, 3_000_000.0, 24)
    assert len(cashflows) == 24


def test_build_cashflows_zero_months_returns_empty():
    assert build_development_cashflows(1_000_000.0, 3_000_000.0, 0) == []


def test_build_cashflows_negative_months_returns_empty():
    assert build_development_cashflows(1_000_000.0, 3_000_000.0, -6) == []


# ---------------------------------------------------------------------------
# calculate_npv
# ---------------------------------------------------------------------------


def test_npv_positive_for_profitable_cashflows():
    cashflows = build_development_cashflows(1_000_000.0, 2_000_000.0, 12)
    npv = calculate_npv(cashflows, 0.10)
    assert npv > 0.0


def test_npv_negative_for_unprofitable_cashflows():
    cashflows = build_development_cashflows(2_000_000.0, 1_000_000.0, 12)
    npv = calculate_npv(cashflows, 0.10)
    assert npv < 0.0


def test_npv_empty_cashflows_returns_zero():
    assert calculate_npv([], 0.10) == 0.0


def test_npv_discount_rate_exactly_minus_one_raises():
    cashflows = build_development_cashflows(1_000_000.0, 2_000_000.0, 12)
    with pytest.raises(ValueError, match="annual_discount_rate"):
        calculate_npv(cashflows, -1.0)


def test_npv_discount_rate_below_minus_one_raises():
    cashflows = build_development_cashflows(1_000_000.0, 2_000_000.0, 12)
    with pytest.raises(ValueError, match="annual_discount_rate"):
        calculate_npv(cashflows, -1.5)


def test_npv_higher_discount_reduces_value():
    cashflows = build_development_cashflows(1_000_000.0, 2_000_000.0, 24)
    npv_low = calculate_npv(cashflows, 0.05)
    npv_high = calculate_npv(cashflows, 0.20)
    assert npv_low > npv_high


# ---------------------------------------------------------------------------
# calculate_payback_period_months
# ---------------------------------------------------------------------------


def test_payback_period_standard():
    assert calculate_payback_period_months(12_000_000.0, 1_000_000.0) == pytest.approx(12.0)


def test_payback_period_zero_revenue_returns_zero():
    assert calculate_payback_period_months(5_000_000.0, 0.0) == 0.0


def test_payback_period_negative_revenue_returns_zero():
    assert calculate_payback_period_months(5_000_000.0, -500_000.0) == 0.0


# ---------------------------------------------------------------------------
# calculate_break_even_price_per_sqm
# ---------------------------------------------------------------------------


def test_break_even_price_per_sqm_standard():
    assert calculate_break_even_price_per_sqm(10_000_000.0, 1_000.0) == pytest.approx(10_000.0)


def test_break_even_price_per_sqm_zero_area_returns_zero():
    assert calculate_break_even_price_per_sqm(10_000_000.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# calculate_break_even_sellable_sqm
# ---------------------------------------------------------------------------


def test_break_even_sellable_sqm_standard():
    assert calculate_break_even_sellable_sqm(10_000_000.0, 10_000.0) == pytest.approx(1_000.0)


def test_break_even_sellable_sqm_zero_price_returns_zero():
    assert calculate_break_even_sellable_sqm(10_000_000.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# run_return_calculations — composite runner
# ---------------------------------------------------------------------------


def test_run_return_calculations_standard():
    inputs = ReturnInputs(
        gdv=10_000_000.0,
        total_cost=8_000_000.0,
        equity_invested=3_000_000.0,
        sellable_area_sqm=1_000.0,
        avg_sale_price_per_sqm=10_000.0,
        development_period_months=24,
    )
    outputs = run_return_calculations(inputs)
    assert outputs.gross_profit == pytest.approx(2_000_000.0)
    assert outputs.developer_margin == pytest.approx(0.20)
    assert outputs.roi == pytest.approx(0.25)
    assert outputs.roe > 0.0
    assert outputs.irr > 0.0
    assert outputs.equity_multiple == pytest.approx(1.25)
    assert outputs.break_even_price_per_sqm == pytest.approx(8_000.0)
    assert outputs.break_even_sellable_sqm == pytest.approx(800.0)


def test_run_return_calculations_negative_profit_scenario():
    """Negative profit project should yield negative margins and ROI."""
    inputs = ReturnInputs(
        gdv=5_000_000.0,
        total_cost=7_000_000.0,
        equity_invested=2_000_000.0,
        sellable_area_sqm=500.0,
        avg_sale_price_per_sqm=10_000.0,
        development_period_months=24,
    )
    outputs = run_return_calculations(inputs)
    assert outputs.gross_profit < 0.0
    assert outputs.developer_margin < 0.0
    assert outputs.roi < 0.0
    assert outputs.irr < 0.0


def test_run_return_calculations_zero_equity():
    """Zero equity invested yields ROE of 0.0 (no division by zero)."""
    inputs = ReturnInputs(
        gdv=10_000_000.0,
        total_cost=8_000_000.0,
        equity_invested=0.0,
        sellable_area_sqm=1_000.0,
        avg_sale_price_per_sqm=10_000.0,
        development_period_months=24,
    )
    outputs = run_return_calculations(inputs)
    assert outputs.roe == 0.0
