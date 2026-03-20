"""
Tests for the IRR calculation engine.

Validates Newton-Raphson convergence, edge cases, and annualisation.
"""

import pytest

from app.modules.feasibility.irr_engine import (
    build_development_cashflows,
    calculate_irr,
)


# ---------------------------------------------------------------------------
# build_development_cashflows
# ---------------------------------------------------------------------------

def test_build_cashflows_length():
    cashflows = build_development_cashflows(1_000_000.0, 3_000_000.0, 24)
    assert len(cashflows) == 24


def test_build_cashflows_equal_outflows():
    cashflows = build_development_cashflows(1_200_000.0, 3_000_000.0, 12)
    # Each month should show -100_000 before the final revenue addition
    for cf in cashflows[:-1]:
        assert cf == pytest.approx(-100_000.0)


def test_build_cashflows_final_period_includes_revenue():
    cashflows = build_development_cashflows(1_200_000.0, 3_000_000.0, 12)
    # Final cashflow = -monthly_cost + gdv = -100_000 + 3_000_000
    assert cashflows[-1] == pytest.approx(2_900_000.0)


def test_build_cashflows_single_month():
    cashflows = build_development_cashflows(500_000.0, 700_000.0, 1)
    assert len(cashflows) == 1
    assert cashflows[0] == pytest.approx(200_000.0)


# ---------------------------------------------------------------------------
# calculate_irr — happy path
# ---------------------------------------------------------------------------

def test_calculate_irr_profitable_project_is_positive():
    irr = calculate_irr(
        total_cost=1_010_000.0,
        gdv=3_000_000.0,
        development_period_months=24,
    )
    assert irr > 0.0


def test_calculate_irr_unprofitable_project_is_negative():
    irr = calculate_irr(
        total_cost=3_500_000.0,
        gdv=3_000_000.0,
        development_period_months=24,
    )
    assert irr < 0.0


def test_calculate_irr_breakeven_project_near_zero():
    # GDV == total cost ⟹ zero profit ⟹ IRR ≈ 0 (small positive due to
    # timing: costs spent early, revenue received at end).
    irr = calculate_irr(
        total_cost=3_000_000.0,
        gdv=3_000_000.0,
        development_period_months=24,
    )
    # Near-zero but slightly negative because costs are spread monthly
    # while revenue is at end — a slight time-value discount applies.
    assert abs(irr) < 0.05


def test_calculate_irr_longer_period_reduces_annualised_irr():
    irr_short = calculate_irr(1_000_000.0, 3_000_000.0, 12)
    irr_long = calculate_irr(1_000_000.0, 3_000_000.0, 48)
    assert irr_short > irr_long


def test_calculate_irr_higher_gdv_increases_irr():
    irr_low = calculate_irr(1_000_000.0, 2_000_000.0, 24)
    irr_high = calculate_irr(1_000_000.0, 4_000_000.0, 24)
    assert irr_high > irr_low


# ---------------------------------------------------------------------------
# calculate_irr — edge cases
# ---------------------------------------------------------------------------

def test_calculate_irr_zero_total_cost_returns_zero():
    assert calculate_irr(0.0, 3_000_000.0, 24) == 0.0


def test_calculate_irr_negative_total_cost_returns_zero():
    assert calculate_irr(-500_000.0, 3_000_000.0, 24) == 0.0


def test_calculate_irr_zero_months_returns_zero():
    assert calculate_irr(1_000_000.0, 3_000_000.0, 0) == 0.0


def test_calculate_irr_negative_months_returns_zero():
    assert calculate_irr(1_000_000.0, 3_000_000.0, -5) == 0.0


def test_calculate_irr_returns_float():
    result = calculate_irr(1_000_000.0, 3_000_000.0, 24)
    assert isinstance(result, float)


def test_calculate_irr_zero_gdv_is_negative():
    irr = calculate_irr(1_000_000.0, 0.0, 24)
    assert irr < 0.0
