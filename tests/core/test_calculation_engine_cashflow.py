"""
Tests for the centralized cashflow formula engine.

Validates monthly aggregation, cumulative cashflow, deficit detection,
staged payment-plan timing, and breakeven month detection against
real-estate cashflow expectations.
"""

import pytest

from app.core.calculation_engine.cashflow import (
    aggregate_staged_installments,
    calculate_cumulative,
    calculate_months_to_breakeven,
    calculate_net_monthly,
    calculate_peak_deficit,
    run_cashflow_analysis,
)
from app.core.calculation_engine.types import CashflowInputs


# ---------------------------------------------------------------------------
# calculate_net_monthly
# ---------------------------------------------------------------------------


def test_net_monthly_equal_length_arrays():
    inflows = [100.0, 200.0, 300.0]
    outflows = [50.0, 100.0, 150.0]
    net = calculate_net_monthly(inflows, outflows)
    assert net == pytest.approx([50.0, 100.0, 150.0])


def test_net_monthly_inflow_longer_than_outflow():
    inflows = [100.0, 200.0, 300.0]
    outflows = [50.0, 50.0]
    net = calculate_net_monthly(inflows, outflows)
    assert net == pytest.approx([50.0, 150.0, 300.0])


def test_net_monthly_outflow_longer_than_inflow():
    inflows = [100.0]
    outflows = [50.0, 80.0, 90.0]
    net = calculate_net_monthly(inflows, outflows)
    assert net == pytest.approx([50.0, -80.0, -90.0])


def test_net_monthly_empty_arrays():
    assert calculate_net_monthly([], []) == []


def test_net_monthly_all_zeros():
    net = calculate_net_monthly([0.0, 0.0], [0.0, 0.0])
    assert net == pytest.approx([0.0, 0.0])


def test_net_monthly_large_outflow_creates_deficit():
    inflows = [500_000.0]
    outflows = [1_000_000.0]
    net = calculate_net_monthly(inflows, outflows)
    assert net[0] < 0.0


# ---------------------------------------------------------------------------
# calculate_cumulative
# ---------------------------------------------------------------------------


def test_cumulative_standard():
    net = [100.0, -50.0, 200.0]
    cumulative = calculate_cumulative(net)
    assert cumulative == pytest.approx([100.0, 50.0, 250.0])


def test_cumulative_all_positive_increasing():
    net = [100.0, 100.0, 100.0]
    cumulative = calculate_cumulative(net)
    assert cumulative == pytest.approx([100.0, 200.0, 300.0])


def test_cumulative_dips_negative_then_recovers():
    net = [-200.0, -100.0, 500.0]
    cumulative = calculate_cumulative(net)
    assert cumulative[0] < 0.0
    assert cumulative[-1] > 0.0


def test_cumulative_empty():
    assert calculate_cumulative([]) == []


# ---------------------------------------------------------------------------
# calculate_peak_deficit
# ---------------------------------------------------------------------------


def test_peak_deficit_standard():
    cumulative = [100.0, -50.0, -200.0, 300.0]
    assert calculate_peak_deficit(cumulative) == pytest.approx(-200.0)


def test_peak_deficit_no_deficit_returns_zero():
    cumulative = [100.0, 200.0, 300.0]
    assert calculate_peak_deficit(cumulative) == 0.0


def test_peak_deficit_all_negative():
    cumulative = [-100.0, -200.0, -300.0]
    assert calculate_peak_deficit(cumulative) == pytest.approx(-300.0)


def test_peak_deficit_empty_returns_zero():
    assert calculate_peak_deficit([]) == 0.0


def test_peak_deficit_single_positive_returns_zero():
    assert calculate_peak_deficit([500.0]) == 0.0


def test_peak_deficit_single_negative():
    assert calculate_peak_deficit([-150.0]) == pytest.approx(-150.0)


# ---------------------------------------------------------------------------
# calculate_months_to_breakeven
# ---------------------------------------------------------------------------


def test_months_to_breakeven_immediate():
    """Breakeven at month 0 when first value is already non-negative."""
    assert calculate_months_to_breakeven([500.0, -100.0]) == 0


def test_months_to_breakeven_after_deficit():
    cumulative = [-200.0, -100.0, 0.0, 100.0]
    assert calculate_months_to_breakeven(cumulative) == 2


def test_months_to_breakeven_never_returns_minus_one():
    cumulative = [-100.0, -200.0, -300.0]
    assert calculate_months_to_breakeven(cumulative) == -1


def test_months_to_breakeven_empty_returns_minus_one():
    assert calculate_months_to_breakeven([]) == -1


def test_months_to_breakeven_exactly_zero_counts():
    cumulative = [-500.0, 0.0, 100.0]
    assert calculate_months_to_breakeven(cumulative) == 1


# ---------------------------------------------------------------------------
# aggregate_staged_installments
# ---------------------------------------------------------------------------


def test_aggregate_staged_installments_standard():
    schedule = [
        {"month": 0, "amount": 100_000.0},
        {"month": 3, "amount": 200_000.0},
        {"month": 11, "amount": 300_000.0},
    ]
    result = aggregate_staged_installments(schedule, 12)
    assert result[0] == pytest.approx(100_000.0)
    assert result[3] == pytest.approx(200_000.0)
    assert result[11] == pytest.approx(300_000.0)
    assert sum(result) == pytest.approx(600_000.0)


def test_aggregate_staged_installments_out_of_range_ignored():
    schedule = [{"month": 15, "amount": 500_000.0}]
    result = aggregate_staged_installments(schedule, 12)
    assert all(v == 0.0 for v in result)


def test_aggregate_staged_installments_multiple_same_month():
    schedule = [
        {"month": 2, "amount": 100_000.0},
        {"month": 2, "amount": 50_000.0},
    ]
    result = aggregate_staged_installments(schedule, 6)
    assert result[2] == pytest.approx(150_000.0)


def test_aggregate_staged_installments_empty_schedule():
    result = aggregate_staged_installments([], 6)
    assert result == [0.0] * 6


def test_aggregate_staged_installments_zero_period():
    result = aggregate_staged_installments([{"month": 0, "amount": 100.0}], 0)
    assert result == []


# ---------------------------------------------------------------------------
# run_cashflow_analysis — composite runner
# ---------------------------------------------------------------------------


def test_run_cashflow_analysis_standard():
    inputs = CashflowInputs(
        monthly_inflows=[0.0, 0.0, 0.0, 1_000_000.0, 1_000_000.0],
        monthly_outflows=[200_000.0, 200_000.0, 200_000.0, 0.0, 0.0],
    )
    outputs = run_cashflow_analysis(inputs)
    assert outputs.total_inflow == pytest.approx(2_000_000.0)
    assert outputs.total_outflow == pytest.approx(600_000.0)
    assert outputs.peak_deficit < 0.0
    assert outputs.months_to_breakeven >= 0


def test_run_cashflow_analysis_always_positive():
    inputs = CashflowInputs(
        monthly_inflows=[500_000.0, 500_000.0, 500_000.0],
        monthly_outflows=[100_000.0, 100_000.0, 100_000.0],
    )
    outputs = run_cashflow_analysis(inputs)
    assert outputs.peak_deficit == 0.0
    assert outputs.months_to_breakeven == 0


def test_run_cashflow_analysis_never_recovers():
    inputs = CashflowInputs(
        monthly_inflows=[0.0, 0.0, 0.0],
        monthly_outflows=[100_000.0, 100_000.0, 100_000.0],
    )
    outputs = run_cashflow_analysis(inputs)
    assert outputs.peak_deficit < 0.0
    assert outputs.months_to_breakeven == -1


def test_run_cashflow_analysis_cumulative_length_matches_period():
    inputs = CashflowInputs(
        monthly_inflows=[100_000.0] * 6,
        monthly_outflows=[50_000.0] * 6,
    )
    outputs = run_cashflow_analysis(inputs)
    assert len(outputs.net_monthly) == 6
    assert len(outputs.cumulative) == 6
