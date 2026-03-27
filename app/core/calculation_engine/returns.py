"""
app.core.calculation_engine.returns

Centralized return and profitability metrics.

Covers:
- Gross profit and developer margin.
- ROI (return on total cost) and ROE (return on equity).
- IRR (Internal Rate of Return) via Newton-Raphson with bisection fallback.
- NPV (Net Present Value) at a given discount rate.
- Equity multiple.
- Payback period in months.
- Break-even price per sqm.
- Break-even sellable area.

No financing-table persistence, portfolio aggregation, or scenario management
belongs here.

IRR solver
----------
Primary:  Newton-Raphson iteration on monthly cashflows.
Fallback: Bisection within bounded monthly-rate range.
Cashflow model: equal monthly cost outflows, lump-sum GDV at end of period.
"""

from __future__ import annotations

from typing import List, Optional

from app.core.calculation_engine.types import ReturnInputs, ReturnOutputs


# ---------------------------------------------------------------------------
# NPV / IRR helpers (cashflow-based)
# ---------------------------------------------------------------------------


def _npv(rate: float, cashflows: List[float]) -> float:
    """Net Present Value at a given periodic rate."""
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))


def _npv_derivative(rate: float, cashflows: List[float]) -> float:
    """First derivative of NPV with respect to the periodic rate."""
    return sum(-t * cf / (1.0 + rate) ** (t + 1) for t, cf in enumerate(cashflows))


def _bisect_irr(
    cashflows: List[float],
    lo: float = -0.9999,
    hi: float = 10.0,
    max_iterations: int = 100,
    tolerance: float = 1e-10,
) -> Optional[float]:
    """Bisection root-finder for IRR (monthly rate).

    Returns the monthly rate where NPV changes sign, or ``None`` when no
    sign change exists in the search range.
    """
    f_lo = _npv(lo, cashflows)
    f_hi = _npv(hi, cashflows)
    if f_lo * f_hi > 0.0:
        return None
    for _ in range(max_iterations):
        mid = (lo + hi) / 2.0
        f_mid = _npv(mid, cashflows)
        if abs(f_mid) < tolerance or (hi - lo) / 2.0 < tolerance:
            return mid
        if f_lo * f_mid < 0.0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid
    return (lo + hi) / 2.0


def build_development_cashflows(
    total_cost: float,
    gdv: float,
    development_period_months: int,
) -> List[float]:
    """Construct monthly cashflows for a standard development project.

    Equal cost outflows over the development period with lump-sum revenue
    at the end.

    Parameters
    ----------
    total_cost:
        Total development cost (positive).
    gdv:
        Gross Development Value received at the end of the period.
    development_period_months:
        Length of the development period in months. Must be positive.
        Returns an empty list when this value is <= 0.
    """
    if development_period_months <= 0:
        return []
    n = development_period_months
    monthly_cost = total_cost / n
    cashflows: List[float] = [-monthly_cost] * n
    cashflows[-1] += gdv
    return cashflows


# ---------------------------------------------------------------------------
# Pure formula functions
# ---------------------------------------------------------------------------


def calculate_gross_profit(gdv: float, total_cost: float) -> float:
    """Gross profit = GDV − total development cost."""
    return gdv - total_cost


def calculate_developer_margin(gross_profit: float, gdv: float) -> float:
    """Developer margin = gross profit / GDV.

    Returns 0.0 when GDV is zero to avoid division by zero.
    """
    if gdv == 0.0:
        return 0.0
    return gross_profit / gdv


def calculate_roi(gross_profit: float, total_cost: float) -> float:
    """Return on Investment = gross profit / total cost.

    Returns 0.0 when total cost is zero.
    """
    if total_cost <= 0.0:
        return 0.0
    return gross_profit / total_cost


def calculate_roe(gross_profit: float, equity_invested: float) -> float:
    """Return on Equity = gross profit / equity invested.

    Returns 0.0 when equity invested is zero.
    """
    if equity_invested <= 0.0:
        return 0.0
    return gross_profit / equity_invested


def calculate_irr(
    total_cost: float,
    gdv: float,
    development_period_months: int,
    *,
    max_iterations: int = 200,
    tolerance: float = 1e-10,
) -> float:
    """Annualised IRR for a standard development project.

    Cashflow model: equal monthly cost outflows, lump-sum GDV at end.
    Primary solver: Newton-Raphson. Fallback: bisection.

    Special cases
    -------------
    - ``total_cost <= 0`` → 0.0
    - ``development_period_months <= 0`` → 0.0
    - ``gdv <= 0`` → -1.0 (full annualised loss)
    - solver fails to converge → 0.0 (sentinel)

    Returns
    -------
    float
        Annualised IRR: ``(1 + monthly_rate) ** 12 − 1``.
    """
    if total_cost <= 0.0 or development_period_months <= 0:
        return 0.0
    if gdv <= 0.0:
        return -1.0

    cashflows = build_development_cashflows(total_cost, gdv, development_period_months)
    n = development_period_months
    rate = (gdv / total_cost) ** (1.0 / n) - 1.0

    converged = False
    for _ in range(max_iterations):
        f_val = _npv(rate, cashflows)
        f_prime = _npv_derivative(rate, cashflows)
        if abs(f_prime) < 1e-15:
            break
        step = f_val / f_prime
        rate -= step
        rate = max(-0.9999, min(rate, 1000.0))
        if abs(step) < tolerance:
            converged = True
            break

    if not converged:
        monthly_rate = _bisect_irr(cashflows, tolerance=tolerance)
        if monthly_rate is None:
            return 0.0
        rate = monthly_rate

    return (1.0 + rate) ** 12 - 1.0


def calculate_npv(
    cashflows: List[float],
    annual_discount_rate: float,
) -> float:
    """Net Present Value at the given annual discount rate.

    Converts the annual rate to a monthly equivalent before discounting.

    Parameters
    ----------
    cashflows:
        Monthly cashflow array (period 0 first).
    annual_discount_rate:
        Annual discount rate as a decimal fraction (e.g. 0.10 for 10 %).
    """
    if not cashflows:
        return 0.0
    if annual_discount_rate <= -1.0:
        raise ValueError("annual_discount_rate must be greater than -1.0")
    monthly_rate = (1.0 + annual_discount_rate) ** (1.0 / 12) - 1.0
    return _npv(monthly_rate, cashflows)


def calculate_equity_multiple(gdv: float, total_cost: float) -> float:
    """Equity multiple = GDV / total cost.

    Returns 0.0 when total cost is zero.
    """
    if total_cost <= 0.0:
        return 0.0
    return gdv / total_cost


def calculate_payback_period_months(
    total_cost: float,
    monthly_revenue: float,
) -> float:
    """Payback period = total cost / monthly revenue.

    Assumes equal monthly revenue inflows.
    Returns 0.0 when monthly revenue is zero or negative.

    Parameters
    ----------
    total_cost:
        Total amount to be recovered.
    monthly_revenue:
        Equal monthly revenue inflow amount.
    """
    if monthly_revenue <= 0.0:
        return 0.0
    return total_cost / monthly_revenue


def calculate_break_even_price_per_sqm(
    total_cost: float,
    sellable_area_sqm: float,
) -> float:
    """Minimum selling price per sqm to cover all development costs.

    Returns 0.0 when sellable area is zero.
    """
    if sellable_area_sqm <= 0.0:
        return 0.0
    return total_cost / sellable_area_sqm


def calculate_break_even_sellable_sqm(
    total_cost: float,
    avg_sale_price_per_sqm: float,
) -> float:
    """Minimum sellable area (sqm) to recover all costs at the given price.

    Returns 0.0 when avg_sale_price_per_sqm is zero.
    """
    if avg_sale_price_per_sqm <= 0.0:
        return 0.0
    return total_cost / avg_sale_price_per_sqm


def calculate_profit_per_sqm(
    developer_profit: float,
    sellable_area_sqm: float,
) -> float:
    """Developer profit per sellable square metre.

    Returns 0.0 when sellable_area_sqm is zero to avoid division by zero.
    """
    if sellable_area_sqm <= 0.0:
        return 0.0
    return developer_profit / sellable_area_sqm


# ---------------------------------------------------------------------------
# Composite runner
# ---------------------------------------------------------------------------


def run_return_calculations(
    inputs: ReturnInputs,
    *,
    annual_discount_rate: float = 0.10,
) -> ReturnOutputs:
    """Compute the full suite of return metrics from structured inputs.

    Parameters
    ----------
    inputs:
        Validated :class:`~app.core.calculation_engine.types.ReturnInputs`.
    annual_discount_rate:
        Discount rate used for NPV (default 10 %).

    Returns
    -------
    ReturnOutputs
        All derived profitability and return metrics.
    """
    gross_profit = calculate_gross_profit(inputs.gdv, inputs.total_cost)
    developer_margin = calculate_developer_margin(gross_profit, inputs.gdv)
    roi = calculate_roi(gross_profit, inputs.total_cost)
    roe = calculate_roe(gross_profit, inputs.equity_invested)
    irr = calculate_irr(inputs.total_cost, inputs.gdv, inputs.development_period_months)
    cashflows = build_development_cashflows(
        inputs.total_cost, inputs.gdv, inputs.development_period_months
    )
    npv = calculate_npv(cashflows, annual_discount_rate)
    equity_multiple = calculate_equity_multiple(inputs.gdv, inputs.total_cost)
    n = max(inputs.development_period_months, 1)
    monthly_revenue = inputs.gdv / n
    payback = calculate_payback_period_months(inputs.total_cost, monthly_revenue)
    break_even_price = calculate_break_even_price_per_sqm(
        inputs.total_cost, inputs.sellable_area_sqm
    )
    break_even_sqm = calculate_break_even_sellable_sqm(
        inputs.total_cost, inputs.avg_sale_price_per_sqm
    )

    return ReturnOutputs(
        gross_profit=gross_profit,
        developer_margin=developer_margin,
        roi=roi,
        roe=roe,
        irr=irr,
        npv=npv,
        equity_multiple=equity_multiple,
        payback_period_months=payback,
        break_even_price_per_sqm=break_even_price,
        break_even_sellable_sqm=break_even_sqm,
    )
