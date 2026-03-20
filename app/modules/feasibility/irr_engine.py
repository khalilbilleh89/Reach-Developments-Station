"""
IRR (Internal Rate of Return) calculation engine.

Calculates annualized IRR from development cashflow projections.

Cashflow model
--------------
- Equal monthly cost outflows over the development period.
- Lump-sum revenue (GDV) received at the end of the development period.

Solver
------
Primary:  Newton-Raphson iteration (fast, quadratic convergence).
Fallback: Bisection within bounded monthly-rate range (robust, guaranteed).
If neither method finds a root, 0.0 is returned as a safe sentinel.

Annualized IRR = (1 + monthly_r) ** 12 - 1.
"""

from __future__ import annotations

from typing import Optional


def _npv(rate: float, cashflows: list) -> float:
    """Net Present Value at a given periodic rate."""
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))


def _npv_derivative(rate: float, cashflows: list) -> float:
    """First derivative of NPV with respect to the periodic rate."""
    return sum(-t * cf / (1.0 + rate) ** (t + 1) for t, cf in enumerate(cashflows))


def _bisect_irr(
    cashflows: list,
    lo: float = -0.9999,
    hi: float = 10.0,
    max_iterations: int = 100,
    tolerance: float = 1e-10,
) -> Optional[float]:
    """Bisection root-finder for IRR.

    Searches for a monthly rate in *[lo, hi]* where NPV changes sign.
    Returns the root (monthly rate) when found, or ``None`` when there is
    no sign change in the search range (no real root exists).
    """
    f_lo = _npv(lo, cashflows)
    f_hi = _npv(hi, cashflows)

    if f_lo * f_hi > 0.0:
        # No sign change — no real root within bounds.
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

    Primary solver: Newton-Raphson on monthly cashflows (equal cost outflows,
    lump-sum revenue at end of development period).
    Fallback solver: Bisection within monthly-rate bounds [-0.9999, 10.0].

    Parameters
    ----------
    total_cost:
        Total development cost. Must be positive for a meaningful result.
    gdv:
        Gross Development Value received at end of development.
    development_period_months:
        Length of the development period in months. Must be positive.
    max_iterations:
        Maximum Newton-Raphson iterations before falling back to bisection.
    tolerance:
        Convergence tolerance on the monthly rate step.

    Returns
    -------
    float
        Annualized IRR.

        Special cases:
        - ``total_cost <= 0`` → ``0.0``
        - ``development_period_months <= 0`` → ``0.0``
        - ``gdv <= 0`` → ``-1.0`` (full annualised loss: −100 %)
        - solver fails to converge and no root in bounds → ``0.0`` (sentinel)
    """
    if total_cost <= 0.0 or development_period_months <= 0:
        return 0.0

    # No revenue → total loss; IRR is -100 % annualised.
    if gdv <= 0.0:
        return -1.0

    cashflows = build_development_cashflows(total_cost, gdv, development_period_months)

    # Initial guess from the simplified two-point (lump-sum) cashflow.
    n = development_period_months
    rate = (gdv / total_cost) ** (1.0 / n) - 1.0

    converged = False
    for _ in range(max_iterations):
        f_val = _npv(rate, cashflows)
        f_prime = _npv_derivative(rate, cashflows)
        if abs(f_prime) < 1e-15:
            # Flat derivative — Newton-Raphson cannot continue.
            break
        step = f_val / f_prime
        rate -= step
        # Clamp to prevent divergence into undefined territory.
        rate = max(-0.9999, min(rate, 1000.0))
        if abs(step) < tolerance:
            converged = True
            break

    if not converged:
        # Newton-Raphson did not converge; fall back to bisection.
        monthly_rate = _bisect_irr(cashflows, tolerance=tolerance)
        if monthly_rate is None:
            # No real root found within search bounds.
            return 0.0
        rate = monthly_rate

    # Annualize the monthly rate.
    return (1.0 + rate) ** 12 - 1.0
