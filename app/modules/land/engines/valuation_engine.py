"""
Land valuation engine.

Computes residual land value using development economics.

Formulas
--------
soft_costs         = construction_cost × soft_cost_percentage
total_cost         = construction_cost + soft_costs
target_profit      = gdv × developer_margin_target
land_value         = gdv − total_cost − target_profit
land_value_per_sqm = land_value / sellable_area_sqm   (sellable_area_sqm > 0)
max_land_bid       = land_value
residual_margin    = land_value / gdv                  (gdv > 0)

Note: land_value may be negative, indicating the development economics do not
support a positive land residual at the given inputs. Callers should detect
and surface this condition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ValuationInputs:
    """Validated inputs required by the land valuation engine."""

    gdv: float
    construction_cost: float
    soft_cost_percentage: float  # decimal fraction, e.g. 0.10 for 10 %
    developer_margin_target: float  # decimal fraction, e.g. 0.20 for 20 %
    sellable_area_sqm: float


@dataclass(frozen=True)
class ValuationOutputs:
    """Calculated outputs produced by the land valuation engine."""

    soft_costs: float
    total_cost: float
    target_profit: float
    land_value: float
    land_value_per_sqm: float
    max_land_bid: float
    residual_margin: float


def calculate_soft_costs(construction_cost: float, soft_cost_percentage: float) -> float:
    """Soft costs = construction cost × soft cost percentage."""
    return construction_cost * soft_cost_percentage


def calculate_total_cost(construction_cost: float, soft_costs: float) -> float:
    """Total cost = construction cost + soft costs."""
    return construction_cost + soft_costs


def calculate_target_profit(gdv: float, developer_margin_target: float) -> float:
    """Target profit = GDV × developer margin target."""
    return gdv * developer_margin_target


def calculate_land_value(gdv: float, total_cost: float, target_profit: float) -> float:
    """Residual land value = GDV − total cost − target profit."""
    return gdv - total_cost - target_profit


def calculate_land_value_per_sqm(land_value: float, sellable_area_sqm: float) -> float:
    """Land value per sqm = land value / sellable area.

    Returns 0.0 when sellable area is zero to avoid division by zero.
    """
    if sellable_area_sqm == 0.0:
        return 0.0
    return land_value / sellable_area_sqm


def calculate_residual_margin(land_value: float, gdv: float) -> float:
    """Residual margin = land value / GDV.

    Returns 0.0 when GDV is zero to avoid division by zero.
    """
    if gdv == 0.0:
        return 0.0
    return land_value / gdv


def run_land_valuation(inputs: ValuationInputs) -> ValuationOutputs:
    """Execute the full land valuation from structured inputs.

    Parameters
    ----------
    inputs:
        Validated :class:`ValuationInputs` dataclass.

    Returns
    -------
    ValuationOutputs
        All derived land valuation metrics. Note that ``land_value`` and
        ``max_land_bid`` may be negative when the development economics do not
        support a positive land residual at the given inputs.
    """
    soft_costs = calculate_soft_costs(inputs.construction_cost, inputs.soft_cost_percentage)
    total_cost = calculate_total_cost(inputs.construction_cost, soft_costs)
    target_profit = calculate_target_profit(inputs.gdv, inputs.developer_margin_target)
    land_value = calculate_land_value(inputs.gdv, total_cost, target_profit)
    land_value_per_sqm = calculate_land_value_per_sqm(land_value, inputs.sellable_area_sqm)
    max_land_bid = land_value
    residual_margin = calculate_residual_margin(land_value, inputs.gdv)

    return ValuationOutputs(
        soft_costs=soft_costs,
        total_cost=total_cost,
        target_profit=target_profit,
        land_value=land_value,
        land_value_per_sqm=land_value_per_sqm,
        max_land_bid=max_land_bid,
        residual_margin=residual_margin,
    )
