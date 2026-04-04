"""
Feasibility calculation engine.

Deterministic formulas for development economics.
All inputs and outputs use consistent units (sqm, currency, ratios, months).

Formulas
--------
gdv                = sellable_area_sqm * avg_sale_price_per_sqm
construction_cost  = sellable_area_sqm * construction_cost_per_sqm
soft_cost          = construction_cost * soft_cost_ratio
finance_cost       = construction_cost * finance_cost_ratio
sales_cost         = gdv * sales_cost_ratio
total_cost         = construction_cost + soft_cost + finance_cost + sales_cost
developer_profit   = gdv - total_cost
profit_margin      = developer_profit / gdv          (gdv > 0)
irr_estimate       = developer_profit / total_cost   (total_cost > 0, placeholder)

Note: irr_estimate is a simple return-on-cost placeholder.
A fully discounted IRR model is out of scope for this PR.
"""

from dataclasses import dataclass

from app.core.constants.currency import DEFAULT_CURRENCY


@dataclass(frozen=True)
class FeasibilityInputs:
    """Validated inputs required by the feasibility engine."""

    sellable_area_sqm: float
    avg_sale_price_per_sqm: float
    construction_cost_per_sqm: float
    soft_cost_ratio: float
    finance_cost_ratio: float
    sales_cost_ratio: float
    development_period_months: int
    currency: str = DEFAULT_CURRENCY  # denomination of all monetary inputs/outputs


@dataclass(frozen=True)
class FeasibilityOutputs:
    """Calculated outputs produced by the feasibility engine."""

    gdv: float
    construction_cost: float
    soft_cost: float
    finance_cost: float
    sales_cost: float
    total_cost: float
    developer_profit: float
    profit_margin: float
    irr_estimate: float
    currency: str = DEFAULT_CURRENCY  # denomination — inherited from FeasibilityInputs


def calculate_gdv(sellable_area_sqm: float, avg_sale_price_per_sqm: float) -> float:
    """Gross Development Value = sellable area × average sale price per sqm."""
    return sellable_area_sqm * avg_sale_price_per_sqm


def calculate_construction_cost(sellable_area_sqm: float, construction_cost_per_sqm: float) -> float:
    """Construction cost = sellable area × construction cost per sqm."""
    return sellable_area_sqm * construction_cost_per_sqm


def calculate_soft_cost(construction_cost: float, soft_cost_ratio: float) -> float:
    """Soft cost = construction cost × soft cost ratio."""
    return construction_cost * soft_cost_ratio


def calculate_finance_cost(construction_cost: float, finance_cost_ratio: float) -> float:
    """Finance cost = construction cost × finance cost ratio."""
    return construction_cost * finance_cost_ratio


def calculate_sales_cost(gdv: float, sales_cost_ratio: float) -> float:
    """Sales cost = GDV × sales cost ratio."""
    return gdv * sales_cost_ratio


def calculate_total_cost(
    construction_cost: float,
    soft_cost: float,
    finance_cost: float,
    sales_cost: float,
) -> float:
    """Total cost = construction + soft + finance + sales costs."""
    return construction_cost + soft_cost + finance_cost + sales_cost


def calculate_profit(gdv: float, total_cost: float) -> float:
    """Developer profit = GDV − total cost."""
    return gdv - total_cost


def calculate_profit_margin(developer_profit: float, gdv: float) -> float:
    """Profit margin = developer profit / GDV.

    Returns 0.0 when GDV is zero to avoid division by zero.
    """
    if gdv == 0.0:
        return 0.0
    return developer_profit / gdv


def calculate_simple_irr(developer_profit: float, total_cost: float) -> float:
    """Simple IRR estimate = developer profit / total cost (return-on-cost proxy).

    Returns 0.0 when total cost is zero to avoid division by zero.
    This is a placeholder; a full discounted IRR is out of scope for this PR.
    """
    if total_cost == 0.0:
        return 0.0
    return developer_profit / total_cost


def run_feasibility(inputs: FeasibilityInputs) -> FeasibilityOutputs:
    """Execute the full feasibility calculation from structured inputs.

    Parameters
    ----------
    inputs:
        Validated :class:`FeasibilityInputs` dataclass.

    Returns
    -------
    FeasibilityOutputs
        All derived financial metrics.
    """
    gdv = calculate_gdv(inputs.sellable_area_sqm, inputs.avg_sale_price_per_sqm)
    construction_cost = calculate_construction_cost(
        inputs.sellable_area_sqm, inputs.construction_cost_per_sqm
    )
    soft_cost = calculate_soft_cost(construction_cost, inputs.soft_cost_ratio)
    finance_cost = calculate_finance_cost(construction_cost, inputs.finance_cost_ratio)
    sales_cost = calculate_sales_cost(gdv, inputs.sales_cost_ratio)
    total_cost = calculate_total_cost(construction_cost, soft_cost, finance_cost, sales_cost)
    developer_profit = calculate_profit(gdv, total_cost)
    profit_margin = calculate_profit_margin(developer_profit, gdv)
    irr_estimate = calculate_simple_irr(developer_profit, total_cost)

    return FeasibilityOutputs(
        gdv=gdv,
        construction_cost=construction_cost,
        soft_cost=soft_cost,
        finance_cost=finance_cost,
        sales_cost=sales_cost,
        total_cost=total_cost,
        developer_profit=developer_profit,
        profit_margin=profit_margin,
        irr_estimate=irr_estimate,
        currency=inputs.currency,
    )
