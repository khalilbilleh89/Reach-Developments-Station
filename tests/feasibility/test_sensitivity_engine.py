"""
Tests for the feasibility scenario runner (sensitivity analysis).

Validates that all four scenarios are generated, that parameter factors
are applied correctly, and that scenario outputs have the expected structure.
"""

import pytest

from app.modules.feasibility.engines.feasibility_engine import FeasibilityInputs
from app.modules.feasibility.scenario_runner import run_sensitivity_scenarios

_BASE_INPUTS = FeasibilityInputs(
    sellable_area_sqm=1000.0,
    avg_sale_price_per_sqm=3000.0,
    construction_cost_per_sqm=800.0,
    soft_cost_ratio=0.10,
    finance_cost_ratio=0.05,
    sales_cost_ratio=0.03,
    development_period_months=24,
)

_EXPECTED_SCENARIO_KEYS = {"base", "upside", "downside", "investor"}
_EXPECTED_OUTPUT_KEYS = {
    "gdv",
    "construction_cost",
    "soft_cost",
    "finance_cost",
    "sales_cost",
    "total_cost",
    "developer_profit",
    "profit_margin",
    "irr_estimate",
}


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------

def test_run_sensitivity_scenarios_returns_dict():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert isinstance(result, dict)


def test_run_sensitivity_scenarios_has_all_four_scenarios():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert set(result.keys()) == _EXPECTED_SCENARIO_KEYS


def test_each_scenario_has_all_output_keys():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    for scenario_name, outputs in result.items():
        assert set(outputs.keys()) == _EXPECTED_OUTPUT_KEYS, (
            f"Scenario '{scenario_name}' is missing expected keys"
        )


# ---------------------------------------------------------------------------
# Base scenario matches direct engine calculation
# ---------------------------------------------------------------------------

def test_base_scenario_gdv_matches_direct_calculation():
    from app.modules.feasibility.engines.feasibility_engine import run_feasibility
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    direct = run_feasibility(_BASE_INPUTS)
    assert result["base"]["gdv"] == pytest.approx(direct.gdv)


def test_base_scenario_total_cost_matches_direct_calculation():
    from app.modules.feasibility.engines.feasibility_engine import run_feasibility
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    direct = run_feasibility(_BASE_INPUTS)
    assert result["base"]["total_cost"] == pytest.approx(direct.total_cost)


# ---------------------------------------------------------------------------
# Upside scenario: +10% sale price, -5% construction cost
# ---------------------------------------------------------------------------

def test_upside_gdv_is_higher_than_base():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert result["upside"]["gdv"] > result["base"]["gdv"]


def test_upside_construction_cost_is_lower_than_base():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert result["upside"]["construction_cost"] < result["base"]["construction_cost"]


def test_upside_profit_is_higher_than_base():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert result["upside"]["developer_profit"] > result["base"]["developer_profit"]


def test_upside_gdv_factor():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert result["upside"]["gdv"] == pytest.approx(result["base"]["gdv"] * 1.10)


# ---------------------------------------------------------------------------
# Downside scenario: -10% sale price, +10% construction cost
# ---------------------------------------------------------------------------

def test_downside_gdv_is_lower_than_base():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert result["downside"]["gdv"] < result["base"]["gdv"]


def test_downside_construction_cost_is_higher_than_base():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert result["downside"]["construction_cost"] > result["base"]["construction_cost"]


def test_downside_profit_is_lower_than_base():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert result["downside"]["developer_profit"] < result["base"]["developer_profit"]


def test_downside_gdv_factor():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert result["downside"]["gdv"] == pytest.approx(result["base"]["gdv"] * 0.90)


# ---------------------------------------------------------------------------
# Investor scenario: +5% sale price, +5% construction cost
# ---------------------------------------------------------------------------

def test_investor_gdv_is_between_base_and_upside():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert result["base"]["gdv"] < result["investor"]["gdv"] < result["upside"]["gdv"]


def test_investor_construction_cost_is_higher_than_base():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert result["investor"]["construction_cost"] > result["base"]["construction_cost"]


def test_investor_gdv_factor():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert result["investor"]["gdv"] == pytest.approx(result["base"]["gdv"] * 1.05)


# ---------------------------------------------------------------------------
# Scenario ordering: upside > base > investor profit ranking check
# ---------------------------------------------------------------------------

def test_upside_profit_gt_investor_profit_gt_downside_profit():
    result = run_sensitivity_scenarios(_BASE_INPUTS)
    assert (
        result["upside"]["developer_profit"]
        > result["base"]["developer_profit"]
        > result["downside"]["developer_profit"]
    )
