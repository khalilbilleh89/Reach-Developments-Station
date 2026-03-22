"""
app.core.calculation_engine.cashflow

Centralized cashflow and schedule math.

Covers:
- Monthly net cashflow from inflow and outflow arrays.
- Cumulative cashflow series.
- Peak deficit detection.
- Months-to-breakeven calculation.
- Staged payment-plan cashflow rollup.

No receipt-matching, collections alert workflows, or accounting journal
generation belongs here.
"""

from __future__ import annotations

from typing import List

from app.core.calculation_engine.types import CashflowInputs, CashflowOutputs


# ---------------------------------------------------------------------------
# Pure formula functions
# ---------------------------------------------------------------------------


def calculate_net_monthly(
    monthly_inflows: List[float],
    monthly_outflows: List[float],
) -> List[float]:
    """Net monthly cashflow = inflow − outflow for each period.

    Arrays are aligned by index; the shorter array is treated as zero-padded
    to match the length of the longer one.

    Parameters
    ----------
    monthly_inflows:
        Positive revenue / receipt amounts per month.
    monthly_outflows:
        Positive cost / disbursement amounts per month.
    """
    length = max(len(monthly_inflows), len(monthly_outflows))
    net: List[float] = []
    for i in range(length):
        inflow = monthly_inflows[i] if i < len(monthly_inflows) else 0.0
        outflow = monthly_outflows[i] if i < len(monthly_outflows) else 0.0
        net.append(inflow - outflow)
    return net


def calculate_cumulative(net_monthly: List[float]) -> List[float]:
    """Cumulative cashflow series from a net monthly array.

    Each element is the running sum of all preceding and current net values.
    """
    cumulative: List[float] = []
    running = 0.0
    for cf in net_monthly:
        running += cf
        cumulative.append(running)
    return cumulative


def calculate_peak_deficit(cumulative: List[float]) -> float:
    """Peak deficit = the most negative value in the cumulative series.

    Returns 0.0 when the cumulative cashflow is always non-negative (no
    funding gap).
    """
    if not cumulative:
        return 0.0
    most_negative = min(cumulative)
    return most_negative if most_negative < 0.0 else 0.0


def calculate_months_to_breakeven(cumulative: List[float]) -> int:
    """First month index (0-based) where cumulative cashflow >= 0.

    Returns -1 when the series never reaches breakeven.
    """
    for i, value in enumerate(cumulative):
        if value >= 0.0:
            return i
    return -1


def aggregate_staged_installments(
    installment_schedule: List[dict],
    period_months: int,
) -> List[float]:
    """Roll up staged payment-plan installments into a monthly cashflow array.

    Each entry in ``installment_schedule`` must have:
    - ``month`` (int): zero-based month index within the development period.
    - ``amount`` (float): installment amount (positive inflow).

    Installments falling outside ``[0, period_months)`` are ignored.

    Parameters
    ----------
    installment_schedule:
        List of dicts with ``month`` and ``amount`` keys.
    period_months:
        Length of the cashflow array (number of months).

    Returns
    -------
    list[float]
        Monthly inflow array of length ``period_months``.
    """
    result: List[float] = [0.0] * max(period_months, 0)
    for entry in installment_schedule:
        month = entry.get("month", -1)
        amount = entry.get("amount", 0.0)
        if 0 <= month < period_months:
            result[month] += float(amount)
    return result


# ---------------------------------------------------------------------------
# Composite runner
# ---------------------------------------------------------------------------


def run_cashflow_analysis(inputs: CashflowInputs) -> CashflowOutputs:
    """Compute the full cashflow analysis from structured inputs.

    Parameters
    ----------
    inputs:
        Validated :class:`~app.core.calculation_engine.types.CashflowInputs`.

    Returns
    -------
    CashflowOutputs
        Net monthly, cumulative, totals, peak deficit, and breakeven month.
    """
    net_monthly = calculate_net_monthly(inputs.monthly_inflows, inputs.monthly_outflows)
    cumulative = calculate_cumulative(net_monthly)
    peak_deficit = calculate_peak_deficit(cumulative)
    months_to_breakeven = calculate_months_to_breakeven(cumulative)
    total_inflow = sum(max(cf, 0.0) for cf in inputs.monthly_inflows)
    total_outflow = sum(max(cf, 0.0) for cf in inputs.monthly_outflows)

    return CashflowOutputs(
        net_monthly=net_monthly,
        cumulative=cumulative,
        total_inflow=total_inflow,
        total_outflow=total_outflow,
        peak_deficit=peak_deficit,
        months_to_breakeven=months_to_breakeven,
    )
