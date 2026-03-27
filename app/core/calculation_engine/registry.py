"""
app.core.calculation_engine.registry

Stable façade exposing canonical entry points for the Calculation Engine.

Services and application-layer code should import from this module so that
internal engine restructuring never breaks downstream callers.

No hidden fallback formulas or module-specific overrides belong here.
"""

from __future__ import annotations

from typing import List

from app.core.calculation_engine.areas import (
    calculate_buildable_area,
    calculate_sellable_area,
    run_area_calculations,
)
from app.core.calculation_engine.cashflow import run_cashflow_analysis
from app.core.calculation_engine.land import (
    calculate_effective_land_basis,
    run_land_calculations,
)
from app.core.calculation_engine.pricing import run_unit_pricing
from app.core.calculation_engine.returns import (
    build_development_cashflows,
    calculate_break_even_price_per_sqm,
    calculate_break_even_sellable_sqm,
    calculate_equity_multiple,
    calculate_irr,
    calculate_npv,
    calculate_profit_per_sqm,
    run_return_calculations,
)
from app.core.calculation_engine.types import (
    AreaInputs,
    AreaOutputs,
    CashflowInputs,
    CashflowOutputs,
    LandInputs,
    LandOutputs,
    PricingInputs,
    PricingOutputs,
    ReturnInputs,
    ReturnOutputs,
)


def calculate_returns(inputs: ReturnInputs, *, annual_discount_rate: float = 0.10) -> ReturnOutputs:
    """Compute the full suite of return metrics.

    Parameters
    ----------
    inputs:
        Typed :class:`ReturnInputs` with GDV, cost, equity, area, and period.
    annual_discount_rate:
        Annual discount rate for NPV (default 10 %).
    """
    return run_return_calculations(inputs, annual_discount_rate=annual_discount_rate)


def calculate_land_basis(inputs: LandInputs) -> LandOutputs:
    """Compute land underwriting metrics including residual land value."""
    return run_land_calculations(inputs)


def calculate_land_underwriting_metrics(inputs: LandInputs) -> LandOutputs:
    """Compute the full set of land underwriting metrics from structured inputs.

    Stable façade for land basis hardening. Computes acquisition basis,
    effective basis (including transaction costs), and residual metrics
    from a single typed input.
    """
    return run_land_calculations(inputs)


def calculate_price_adjustment(inputs: PricingInputs) -> PricingOutputs:
    """Compute unit pricing with premiums, escalation, and discount."""
    return run_unit_pricing(inputs)


def calculate_areas(inputs: AreaInputs) -> AreaOutputs:
    """Compute buildable and sellable area from land area and FAR."""
    return run_area_calculations(inputs)


def calculate_cashflow(inputs: CashflowInputs) -> CashflowOutputs:
    """Compute cashflow analysis: net monthly, cumulative, and deficit."""
    return run_cashflow_analysis(inputs)


def calculate_project_irr(
    total_cost: float,
    gdv: float,
    development_period_months: int,
) -> float:
    """Convenience wrapper: annualised IRR for a standard development project."""
    return calculate_irr(total_cost, gdv, development_period_months)


def calculate_project_npv(
    cashflows: List[float],
    annual_discount_rate: float = 0.10,
) -> float:
    """Convenience wrapper: NPV at the given annual discount rate."""
    return calculate_npv(cashflows, annual_discount_rate)


__all__ = [
    # Composite runners
    "calculate_returns",
    "calculate_land_basis",
    "calculate_land_underwriting_metrics",
    "calculate_price_adjustment",
    "calculate_areas",
    "calculate_cashflow",
    # Scalar helpers
    "calculate_project_irr",
    "calculate_project_npv",
    "calculate_irr",
    "calculate_npv",
    "calculate_equity_multiple",
    "calculate_break_even_price_per_sqm",
    "calculate_break_even_sellable_sqm",
    "calculate_profit_per_sqm",
    "build_development_cashflows",
    "calculate_buildable_area",
    "calculate_sellable_area",
    "calculate_effective_land_basis",
    # Types
    "AreaInputs",
    "AreaOutputs",
    "PricingInputs",
    "PricingOutputs",
    "ReturnInputs",
    "ReturnOutputs",
    "CashflowInputs",
    "CashflowOutputs",
    "LandInputs",
    "LandOutputs",
]
