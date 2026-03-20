"""
IRR (Internal Rate of Return) calculation engine.

Calculates annualized IRR from development cashflow projections.

Cashflow model
--------------
- Equal monthly cost outflows over the development period.
- Lump-sum revenue (GDV) received at the end of the development period.

Solver
------
Newton-Raphson iteration finds the monthly rate r satisfying NPV = 0.
Annualized IRR = (1 + monthly_r) ** 12 - 1.
"""

from __future__ import annotations


def _npv(rate: float, cashflows: list) -> float:
    """Net Present Value at a given periodic rate."""
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))


def _npv_derivative(rate: float, cashflows: list) -> float:
    """First derivative of NPV with respect to the periodic rate."""
    return sum(-t * cf / (1.0 + rate) ** (t + 1) for t, cf in enumerate(cashflows))


def build_development_cashflows(
    total_cost: float,
    gdv: float,
    development_period_months: int,
) -> list:
    """Construct monthly cashflows for a standard development project.

    Equal cost outflows over the development period, lump-sum revenue at end.

    Parameters
    ----------
    total_cost:
        Total development cost (positive number).
    gdv:
        Gross Development Value — revenue received at the end.
    development_period_months:
        Number of months in the development period.

    Returns
    -------
    list[float]
        Monthly cashflow array indexed from month 0 (first outflow).
    """
    n = max(development_period_months, 1)
    monthly_cost = total_cost / n
    cashflows = [-monthly_cost] * n
    cashflows[-1] += gdv
    return cashflows


def calculate_irr(
    total_cost: float,
    gdv: float,
    development_period_months: int,
    *,
    max_iterations: int = 200,
    tolerance: float = 1e-10,
) -> float:
    """Calculate annualized IRR for a development project.

    Uses Newton-Raphson iteration on monthly cashflows (equal cost
    outflows, lump-sum revenue).

    Parameters
    ----------
    total_cost:
        Total development cost (must be positive for a meaningful result).
    gdv:
        Gross Development Value received at end of development.
    development_period_months:
        Length of the development period in months.
    max_iterations:
        Maximum Newton-Raphson iterations.
    tolerance:
        Convergence tolerance on the monthly rate step.

    Returns
    -------
    float
        Annualized IRR.  Returns 0.0 when inputs are non-positive.
    """
    if total_cost <= 0.0 or development_period_months <= 0:
        return 0.0

    # No revenue → total loss; IRR is -100 % (annualised).
    if gdv <= 0.0:
        return -1.0

    cashflows = build_development_cashflows(total_cost, gdv, development_period_months)

    # Analytical initial guess from simplified two-point cashflow
    if gdv > 0.0:
        n = development_period_months
        rate = (gdv / total_cost) ** (1.0 / n) - 1.0
    else:
        rate = -0.01  # unprofitable starting guess

    for _ in range(max_iterations):
        f_val = _npv(rate, cashflows)
        f_prime = _npv_derivative(rate, cashflows)
        if abs(f_prime) < 1e-15:
            break
        step = f_val / f_prime
        rate -= step
        # Clamp to prevent undefined/divergent rate
        rate = max(-0.9999, min(rate, 1000.0))
        if abs(step) < tolerance:
            break

    # Annualize the monthly rate
    return (1.0 + rate) ** 12 - 1.0
