"""
Tests for the feasibility calculation engine.

Validates that all formula functions produce deterministic and correct outputs.
"""

import pytest

from app.modules.feasibility.engines.feasibility_engine import (
    FeasibilityInputs,
    FeasibilityOutputs,
    calculate_construction_cost,
    calculate_finance_cost,
    calculate_gdv,
    calculate_profit,
    calculate_profit_margin,
    calculate_sales_cost,
    calculate_simple_irr,
    calculate_soft_cost,
    calculate_total_cost,
    run_feasibility,
)


# ---------------------------------------------------------------------------
# Individual formula unit tests
# ---------------------------------------------------------------------------

def test_calculate_gdv():
    assert calculate_gdv(1000.0, 3000.0) == pytest.approx(3_000_000.0)


def test_calculate_construction_cost():
    assert calculate_construction_cost(1000.0, 800.0) == pytest.approx(800_000.0)


def test_calculate_soft_cost():
    assert calculate_soft_cost(800_000.0, 0.10) == pytest.approx(80_000.0)


def test_calculate_finance_cost():
    assert calculate_finance_cost(800_000.0, 0.05) == pytest.approx(40_000.0)


def test_calculate_sales_cost():
    assert calculate_sales_cost(3_000_000.0, 0.03) == pytest.approx(90_000.0)


def test_calculate_total_cost():
    total = calculate_total_cost(800_000.0, 80_000.0, 40_000.0, 90_000.0)
    assert total == pytest.approx(1_010_000.0)


def test_calculate_profit():
    assert calculate_profit(3_000_000.0, 1_010_000.0) == pytest.approx(1_990_000.0)


def test_calculate_profit_margin():
    margin = calculate_profit_margin(1_990_000.0, 3_000_000.0)
    assert margin == pytest.approx(1_990_000.0 / 3_000_000.0)


def test_calculate_profit_margin_zero_gdv():
    assert calculate_profit_margin(0.0, 0.0) == 0.0


def test_calculate_simple_irr():
    irr = calculate_simple_irr(1_990_000.0, 1_010_000.0)
    assert irr == pytest.approx(1_990_000.0 / 1_010_000.0)


def test_calculate_simple_irr_zero_cost():
    assert calculate_simple_irr(100.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# End-to-end engine test
# ---------------------------------------------------------------------------

_STANDARD_INPUTS = FeasibilityInputs(
    sellable_area_sqm=1000.0,
    avg_sale_price_per_sqm=3000.0,
    construction_cost_per_sqm=800.0,
    soft_cost_ratio=0.10,
    finance_cost_ratio=0.05,
    sales_cost_ratio=0.03,
    development_period_months=24,
)


def test_run_feasibility_gdv():
    outputs = run_feasibility(_STANDARD_INPUTS)
    assert outputs.gdv == pytest.approx(3_000_000.0)


def test_run_feasibility_construction_cost():
    outputs = run_feasibility(_STANDARD_INPUTS)
    assert outputs.construction_cost == pytest.approx(800_000.0)


def test_run_feasibility_soft_cost():
    outputs = run_feasibility(_STANDARD_INPUTS)
    assert outputs.soft_cost == pytest.approx(80_000.0)


def test_run_feasibility_finance_cost():
    outputs = run_feasibility(_STANDARD_INPUTS)
    assert outputs.finance_cost == pytest.approx(40_000.0)


def test_run_feasibility_sales_cost():
    outputs = run_feasibility(_STANDARD_INPUTS)
    assert outputs.sales_cost == pytest.approx(90_000.0)


def test_run_feasibility_total_cost():
    outputs = run_feasibility(_STANDARD_INPUTS)
    assert outputs.total_cost == pytest.approx(1_010_000.0)


def test_run_feasibility_developer_profit():
    outputs = run_feasibility(_STANDARD_INPUTS)
    assert outputs.developer_profit == pytest.approx(1_990_000.0)


def test_run_feasibility_profit_margin():
    outputs = run_feasibility(_STANDARD_INPUTS)
    expected_margin = 1_990_000.0 / 3_000_000.0
    assert outputs.profit_margin == pytest.approx(expected_margin)


def test_run_feasibility_irr_estimate():
    outputs = run_feasibility(_STANDARD_INPUTS)
    expected_irr = 1_990_000.0 / 1_010_000.0
    assert outputs.irr_estimate == pytest.approx(expected_irr)


def test_run_feasibility_returns_dataclass():
    outputs = run_feasibility(_STANDARD_INPUTS)
    assert isinstance(outputs, FeasibilityOutputs)
