"""
Tests for the Financial Scenario Engine (pure calculation layer).

All tests exercise the engine directly without a database, validating:
  - base case scenario execution
  - price uplift override scenario
  - cost inflation override scenario
  - slower sales pace override scenario
  - financing (debt ratio) override scenario
  - scenario duplication / override isolation
  - comparison delta correctness
  - comparison consistency (baseline always has zero deltas)
  - edge cases (zero equity, single period, large overrides)
"""

import pytest

from app.modules.scenario.financial_scenario_engine import (
    FinancialScenarioAssumptions,
    FinancialScenarioRunResult,
    ScenarioOverrides,
    compare_financial_scenarios,
    run_financial_scenario,
    _apply_overrides,
    _resolve_effective_values,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _base_assumptions(**kwargs) -> FinancialScenarioAssumptions:
    """Return a valid base assumption set, optionally overriding any fields."""
    defaults = dict(
        gdv=10_000_000.0,
        total_cost=7_000_000.0,
        equity_invested=2_450_000.0,
        sellable_area_sqm=5_000.0,
        avg_sale_price_per_sqm=2_000.0,
        development_period_months=24,
        annual_discount_rate=0.10,
        label="Base Case",
    )
    defaults.update(kwargs)
    return FinancialScenarioAssumptions(**defaults)


# ---------------------------------------------------------------------------
# Base case scenario
# ---------------------------------------------------------------------------


def test_base_case_returns_irr_positive():
    assumptions = _base_assumptions()
    result = run_financial_scenario(assumptions)
    assert result.returns.irr > 0.0


def test_base_case_gross_profit():
    assumptions = _base_assumptions(gdv=10_000_000.0, total_cost=7_000_000.0)
    result = run_financial_scenario(assumptions)
    assert abs(result.returns.gross_profit - 3_000_000.0) < 1.0


def test_base_case_developer_margin():
    assumptions = _base_assumptions(gdv=10_000_000.0, total_cost=7_000_000.0)
    result = run_financial_scenario(assumptions)
    assert abs(result.returns.developer_margin - 0.30) < 1e-6


def test_base_case_roi():
    assumptions = _base_assumptions(gdv=10_000_000.0, total_cost=7_000_000.0)
    result = run_financial_scenario(assumptions)
    expected_roi = 3_000_000 / 7_000_000
    assert abs(result.returns.roi - expected_roi) < 1e-6


def test_base_case_npv_computed():
    assumptions = _base_assumptions()
    result = run_financial_scenario(assumptions)
    assert result.returns.npv != 0.0


def test_base_case_cashflows_length():
    assumptions = _base_assumptions(development_period_months=24)
    result = run_financial_scenario(assumptions)
    assert len(result.cashflows) == 24


def test_base_case_label_preserved():
    assumptions = _base_assumptions(label="My Base Case")
    result = run_financial_scenario(assumptions)
    assert result.label == "My Base Case"


def test_base_case_effective_values_match_inputs():
    assumptions = _base_assumptions(
        gdv=10_000_000.0, total_cost=7_000_000.0, equity_invested=2_450_000.0
    )
    result = run_financial_scenario(assumptions)
    assert result.effective_gdv == 10_000_000.0
    assert result.effective_total_cost == 7_000_000.0
    assert result.effective_equity_invested == 2_450_000.0


# ---------------------------------------------------------------------------
# Price uplift override scenario
# ---------------------------------------------------------------------------


def test_price_uplift_increases_gdv():
    assumptions = _base_assumptions(gdv=10_000_000.0, pricing_uplift_pct=0.10)
    result = run_financial_scenario(assumptions)
    assert abs(result.effective_gdv - 11_000_000.0) < 1.0


def test_price_uplift_increases_profit():
    base = _base_assumptions(gdv=10_000_000.0)
    uplift = _base_assumptions(gdv=10_000_000.0, pricing_uplift_pct=0.10)
    base_result = run_financial_scenario(base)
    uplift_result = run_financial_scenario(uplift)
    assert uplift_result.returns.gross_profit > base_result.returns.gross_profit


def test_price_uplift_increases_irr():
    base = _base_assumptions()
    uplift = _base_assumptions(pricing_uplift_pct=0.10)
    assert run_financial_scenario(uplift).returns.irr > run_financial_scenario(base).returns.irr


def test_price_uplift_via_override_dict():
    assumptions = _base_assumptions(gdv=10_000_000.0)
    overrides = ScenarioOverrides(values={"pricing_uplift_pct": 0.05, "label": "Price +5%"})
    result = run_financial_scenario(assumptions, overrides)
    assert abs(result.effective_gdv - 10_500_000.0) < 1.0
    assert result.label == "Price +5%"


# ---------------------------------------------------------------------------
# Cost inflation override scenario
# ---------------------------------------------------------------------------


def test_cost_inflation_increases_effective_cost():
    assumptions = _base_assumptions(total_cost=7_000_000.0, cost_inflation_pct=0.10)
    result = run_financial_scenario(assumptions)
    assert abs(result.effective_total_cost - 7_700_000.0) < 1.0


def test_cost_inflation_reduces_profit():
    base = _base_assumptions()
    inflated = _base_assumptions(cost_inflation_pct=0.10)
    assert (
        run_financial_scenario(inflated).returns.gross_profit
        < run_financial_scenario(base).returns.gross_profit
    )


def test_cost_inflation_reduces_irr():
    base = _base_assumptions()
    inflated = _base_assumptions(cost_inflation_pct=0.10)
    assert run_financial_scenario(inflated).returns.irr < run_financial_scenario(base).returns.irr


def test_cost_inflation_via_override_dict():
    assumptions = _base_assumptions(total_cost=7_000_000.0)
    overrides = ScenarioOverrides(values={"cost_inflation_pct": 0.05, "label": "Cost +5%"})
    result = run_financial_scenario(assumptions, overrides)
    assert abs(result.effective_total_cost - 7_350_000.0) < 1.0


# ---------------------------------------------------------------------------
# Slower sales pace override scenario
# ---------------------------------------------------------------------------


def test_slower_sales_pace_extends_period():
    assumptions = _base_assumptions(
        development_period_months=24, sales_pace_months_override=36
    )
    result = run_financial_scenario(assumptions)
    assert result.effective_development_period_months == 36
    assert len(result.cashflows) == 36


def test_slower_sales_pace_reduces_irr():
    base = _base_assumptions(development_period_months=24)
    slower = _base_assumptions(development_period_months=24, sales_pace_months_override=36)
    assert run_financial_scenario(slower).returns.irr < run_financial_scenario(base).returns.irr


def test_slower_sales_pace_via_override_dict():
    assumptions = _base_assumptions(development_period_months=24)
    overrides = ScenarioOverrides(values={"sales_pace_months_override": 30, "label": "Slow Sales"})
    result = run_financial_scenario(assumptions, overrides)
    assert result.effective_development_period_months == 30


# ---------------------------------------------------------------------------
# Financing (debt ratio) override scenario
# ---------------------------------------------------------------------------


def test_debt_ratio_recalculates_equity():
    assumptions = _base_assumptions(
        total_cost=7_000_000.0, equity_invested=2_450_000.0, debt_ratio=0.70
    )
    result = run_financial_scenario(assumptions)
    expected_equity = 7_000_000.0 * 0.30
    assert abs(result.effective_equity_invested - expected_equity) < 1.0


def test_debt_ratio_via_override_dict():
    assumptions = _base_assumptions(total_cost=7_000_000.0, equity_invested=2_450_000.0)
    overrides = ScenarioOverrides(values={"debt_ratio": 0.60, "label": "60% Debt"})
    result = run_financial_scenario(assumptions, overrides)
    expected_equity = 7_000_000.0 * 0.40
    assert abs(result.effective_equity_invested - expected_equity) < 1.0


def test_higher_debt_ratio_increases_roe():
    """Higher debt ratio → less equity → higher ROE for same gross profit."""
    low_debt = _base_assumptions(total_cost=7_000_000.0, debt_ratio=0.40)
    high_debt = _base_assumptions(total_cost=7_000_000.0, debt_ratio=0.80)
    low_result = run_financial_scenario(low_debt)
    high_result = run_financial_scenario(high_debt)
    assert high_result.returns.roe > low_result.returns.roe


# ---------------------------------------------------------------------------
# Override isolation (baseline should not be mutated)
# ---------------------------------------------------------------------------


def test_overrides_do_not_mutate_baseline():
    baseline = _base_assumptions(gdv=10_000_000.0, total_cost=7_000_000.0)
    overrides = ScenarioOverrides(values={"pricing_uplift_pct": 0.20, "cost_inflation_pct": 0.15})
    result = run_financial_scenario(baseline, overrides)
    # Baseline values unchanged
    assert baseline.gdv == 10_000_000.0
    assert baseline.total_cost == 7_000_000.0
    assert baseline.pricing_uplift_pct is None
    assert baseline.cost_inflation_pct is None


def test_unknown_overrides_are_ignored():
    assumptions = _base_assumptions()
    overrides = ScenarioOverrides(values={"non_existent_field": 999, "gdv": 12_000_000.0})
    result = run_financial_scenario(assumptions, overrides)
    # gdv override applied; unknown key silently dropped
    assert result.effective_gdv == 12_000_000.0


# ---------------------------------------------------------------------------
# Comparison delta correctness
# ---------------------------------------------------------------------------


def test_comparison_baseline_deltas_are_zero():
    base = run_financial_scenario(_base_assumptions(label="Base"))
    alt = run_financial_scenario(_base_assumptions(pricing_uplift_pct=0.10, label="Alt"))
    comparison = compare_financial_scenarios([base, alt])
    # Baseline (first) delta must be all zeros
    for value in comparison.deltas[0].values():
        assert value == 0.0


def test_comparison_irr_delta_is_correct():
    base = run_financial_scenario(_base_assumptions(label="Base"))
    alt = run_financial_scenario(_base_assumptions(pricing_uplift_pct=0.10, label="Alt"))
    comparison = compare_financial_scenarios([base, alt])
    expected_delta = alt.returns.irr - base.returns.irr
    assert abs(comparison.deltas[1]["irr"] - expected_delta) < 1e-8


def test_comparison_gross_profit_delta():
    base = run_financial_scenario(_base_assumptions(label="Base"))
    alt = run_financial_scenario(_base_assumptions(cost_inflation_pct=0.10, label="Inflated"))
    comparison = compare_financial_scenarios([base, alt])
    expected_delta = alt.returns.gross_profit - base.returns.gross_profit
    assert abs(comparison.deltas[1]["gross_profit"] - expected_delta) < 1.0


def test_comparison_baseline_label():
    base = run_financial_scenario(_base_assumptions(label="Baseline Run"))
    alt = run_financial_scenario(_base_assumptions(pricing_uplift_pct=0.10, label="Alt"))
    comparison = compare_financial_scenarios([base, alt])
    assert comparison.baseline_label == "Baseline Run"


def test_comparison_requires_at_least_two_runs():
    base = run_financial_scenario(_base_assumptions())
    with pytest.raises(ValueError, match="At least two"):
        compare_financial_scenarios([base])


def test_comparison_three_runs():
    base = run_financial_scenario(_base_assumptions(label="Base"))
    alt1 = run_financial_scenario(_base_assumptions(pricing_uplift_pct=0.05, label="Price +5%"))
    alt2 = run_financial_scenario(_base_assumptions(cost_inflation_pct=0.10, label="Cost +10%"))
    comparison = compare_financial_scenarios([base, alt1, alt2])
    assert len(comparison.runs) == 3
    assert len(comparison.deltas) == 3


# ---------------------------------------------------------------------------
# _apply_overrides unit tests
# ---------------------------------------------------------------------------


def test_apply_overrides_merges_values():
    base = _base_assumptions(gdv=10_000_000.0, label="Base")
    overrides = ScenarioOverrides(values={"gdv": 12_000_000.0, "label": "Override"})
    merged = _apply_overrides(base, overrides)
    assert merged.gdv == 12_000_000.0
    assert merged.label == "Override"
    # Non-overridden fields unchanged
    assert merged.total_cost == base.total_cost


def test_apply_overrides_ignores_unknown_keys():
    base = _base_assumptions()
    overrides = ScenarioOverrides(values={"completely_unknown": "value", "gdv": 9_000_000.0})
    merged = _apply_overrides(base, overrides)
    assert merged.gdv == 9_000_000.0
    # No attribute error for unknown keys
    assert not hasattr(merged, "completely_unknown")


# ---------------------------------------------------------------------------
# _resolve_effective_values unit tests
# ---------------------------------------------------------------------------


def test_resolve_no_modifiers():
    assumptions = _base_assumptions(
        gdv=10_000_000.0, total_cost=7_000_000.0, equity_invested=2_450_000.0,
        development_period_months=24
    )
    gdv, cost, equity, period = _resolve_effective_values(assumptions)
    assert gdv == 10_000_000.0
    assert cost == 7_000_000.0
    assert equity == 2_450_000.0
    assert period == 24


def test_resolve_pricing_uplift():
    assumptions = _base_assumptions(gdv=10_000_000.0, pricing_uplift_pct=0.20)
    gdv, _, _, _ = _resolve_effective_values(assumptions)
    assert abs(gdv - 12_000_000.0) < 1.0


def test_resolve_cost_inflation():
    assumptions = _base_assumptions(total_cost=7_000_000.0, cost_inflation_pct=0.10)
    _, cost, _, _ = _resolve_effective_values(assumptions)
    assert abs(cost - 7_700_000.0) < 1.0


def test_resolve_debt_ratio_overrides_equity():
    assumptions = _base_assumptions(
        total_cost=7_000_000.0, equity_invested=1_000.0, debt_ratio=0.65
    )
    _, cost, equity, _ = _resolve_effective_values(assumptions)
    assert abs(equity - cost * 0.35) < 1.0


def test_resolve_sales_pace_overrides_period():
    assumptions = _base_assumptions(
        development_period_months=24, sales_pace_months_override=30
    )
    _, _, _, period = _resolve_effective_values(assumptions)
    assert period == 30


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_single_month_period():
    assumptions = _base_assumptions(development_period_months=1)
    result = run_financial_scenario(assumptions)
    assert len(result.cashflows) == 1


def test_zero_equity_invested():
    assumptions = _base_assumptions(equity_invested=0.0)
    result = run_financial_scenario(assumptions)
    # ROE should be 0.0 when equity is zero (safe division guard in Calculation Engine)
    assert result.returns.roe == 0.0


def test_large_development_period():
    assumptions = _base_assumptions(development_period_months=120)
    result = run_financial_scenario(assumptions)
    assert len(result.cashflows) == 120
    assert result.returns.irr > 0.0


def test_assumptions_used_serialised_in_result():
    assumptions = _base_assumptions(gdv=9_000_000.0, label="Check Assumptions")
    result = run_financial_scenario(assumptions)
    assert result.assumptions_used["gdv"] == 9_000_000.0
    assert result.assumptions_used["label"] == "Check Assumptions"
