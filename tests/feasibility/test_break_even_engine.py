"""
Tests for the break-even analysis engine.

Validates break-even price, break-even units, and equity multiple formulas.
"""

import pytest

from app.modules.feasibility.break_even_engine import (
    calculate_break_even_price_per_sqm,
    calculate_break_even_units_sqm,
    calculate_equity_multiple,
)


# ---------------------------------------------------------------------------
# calculate_break_even_price_per_sqm
# ---------------------------------------------------------------------------

def test_break_even_price_basic():
    result = calculate_break_even_price_per_sqm(1_010_000.0, 1000.0)
    assert result == pytest.approx(1010.0)


def test_break_even_price_exact():
    # 500_000 / 500 sqm = 1000 per sqm
    assert calculate_break_even_price_per_sqm(500_000.0, 500.0) == pytest.approx(1000.0)


def test_break_even_price_zero_area_returns_zero():
    assert calculate_break_even_price_per_sqm(1_000_000.0, 0.0) == 0.0


def test_break_even_price_negative_area_returns_zero():
    assert calculate_break_even_price_per_sqm(1_000_000.0, -100.0) == 0.0


def test_break_even_price_increases_with_cost():
    low = calculate_break_even_price_per_sqm(500_000.0, 1000.0)
    high = calculate_break_even_price_per_sqm(1_000_000.0, 1000.0)
    assert high > low


def test_break_even_price_decreases_with_larger_area():
    small = calculate_break_even_price_per_sqm(1_000_000.0, 500.0)
    large = calculate_break_even_price_per_sqm(1_000_000.0, 1000.0)
    assert large < small


# ---------------------------------------------------------------------------
# calculate_break_even_units_sqm
# ---------------------------------------------------------------------------

def test_break_even_units_basic():
    # 1_010_000 / 3000 per sqm ≈ 336.67 sqm
    result = calculate_break_even_units_sqm(1_010_000.0, 3000.0)
    assert result == pytest.approx(1_010_000.0 / 3000.0)


def test_break_even_units_zero_price_returns_zero():
    assert calculate_break_even_units_sqm(1_000_000.0, 0.0) == 0.0


def test_break_even_units_negative_price_returns_zero():
    assert calculate_break_even_units_sqm(1_000_000.0, -500.0) == 0.0


def test_break_even_units_increases_with_cost():
    low = calculate_break_even_units_sqm(500_000.0, 3000.0)
    high = calculate_break_even_units_sqm(1_000_000.0, 3000.0)
    assert high > low


def test_break_even_units_decreases_with_higher_price():
    low_price = calculate_break_even_units_sqm(1_000_000.0, 2000.0)
    high_price = calculate_break_even_units_sqm(1_000_000.0, 4000.0)
    assert high_price < low_price


# ---------------------------------------------------------------------------
# calculate_equity_multiple
# ---------------------------------------------------------------------------

def test_equity_multiple_basic():
    result = calculate_equity_multiple(3_000_000.0, 1_010_000.0)
    assert result == pytest.approx(3_000_000.0 / 1_010_000.0)


def test_equity_multiple_profitable_project_gt_one():
    result = calculate_equity_multiple(3_000_000.0, 1_000_000.0)
    assert result > 1.0


def test_equity_multiple_breakeven_equals_one():
    result = calculate_equity_multiple(1_000_000.0, 1_000_000.0)
    assert result == pytest.approx(1.0)


def test_equity_multiple_zero_total_cost_returns_zero():
    assert calculate_equity_multiple(3_000_000.0, 0.0) == 0.0


def test_equity_multiple_negative_total_cost_returns_zero():
    assert calculate_equity_multiple(3_000_000.0, -1_000_000.0) == 0.0


def test_equity_multiple_increases_with_gdv():
    low = calculate_equity_multiple(2_000_000.0, 1_000_000.0)
    high = calculate_equity_multiple(4_000_000.0, 1_000_000.0)
    assert high > low
