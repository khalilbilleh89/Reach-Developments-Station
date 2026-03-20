"""
Feasibility scenario runner.

Runs sensitivity scenarios by systematically varying key inputs
(sale price, construction cost) and returning per-scenario outputs.

Scenarios
---------
base:       Unmodified base inputs.
upside:     Sale price +10 %, construction cost −5 %.
downside:   Sale price −10 %, construction cost +10 %.
investor:   Sale price +5 %, construction cost +5 % (investor stress-test).
"""

from __future__ import annotations

from typing import Any, Dict

from app.modules.feasibility.engines.feasibility_engine import (
    FeasibilityInputs,
    FeasibilityOutputs,
    run_feasibility,
)

# Scenario parameter multipliers applied to sale price and construction cost.
_SCENARIO_PARAMETERS: Dict[str, Dict[str, float]] = {
    "base": {
        "sale_price_factor": 1.00,
        "construction_cost_factor": 1.00,
    },
    "upside": {
        "sale_price_factor": 1.10,
        "construction_cost_factor": 0.95,
    },
    "downside": {
        "sale_price_factor": 0.90,
        "construction_cost_factor": 1.10,
    },
    "investor": {
        "sale_price_factor": 1.05,
        "construction_cost_factor": 1.05,
    },
}


def _apply_scenario(
    base_inputs: FeasibilityInputs,
    sale_price_factor: float,
    construction_cost_factor: float,
) -> FeasibilityInputs:
    """Return a new FeasibilityInputs with scenario factors applied."""
    return FeasibilityInputs(
        sellable_area_sqm=base_inputs.sellable_area_sqm,
        avg_sale_price_per_sqm=base_inputs.avg_sale_price_per_sqm * sale_price_factor,
        construction_cost_per_sqm=base_inputs.construction_cost_per_sqm * construction_cost_factor,
        soft_cost_ratio=base_inputs.soft_cost_ratio,
        finance_cost_ratio=base_inputs.finance_cost_ratio,
        sales_cost_ratio=base_inputs.sales_cost_ratio,
        development_period_months=base_inputs.development_period_months,
    )


def _outputs_to_dict(outputs: FeasibilityOutputs) -> Dict[str, Any]:
    """Convert FeasibilityOutputs dataclass to a plain dict."""
    return {
        "gdv": outputs.gdv,
        "construction_cost": outputs.construction_cost,
        "soft_cost": outputs.soft_cost,
        "finance_cost": outputs.finance_cost,
        "sales_cost": outputs.sales_cost,
        "total_cost": outputs.total_cost,
        "developer_profit": outputs.developer_profit,
        "profit_margin": outputs.profit_margin,
        "irr_estimate": outputs.irr_estimate,
    }


def run_sensitivity_scenarios(base_inputs: FeasibilityInputs) -> Dict[str, Any]:
    """Run sensitivity scenarios on the feasibility inputs.

    Parameters
    ----------
    base_inputs:
        Validated FeasibilityInputs for the base scenario.

    Returns
    -------
    dict
        Mapping of scenario name → output metrics dict.
        Keys: ``base``, ``upside``, ``downside``, ``investor``.
    """
    results: Dict[str, Any] = {}
    for scenario_name, params in _SCENARIO_PARAMETERS.items():
        scenario_inputs = _apply_scenario(
            base_inputs,
            sale_price_factor=params["sale_price_factor"],
            construction_cost_factor=params["construction_cost_factor"],
        )
        outputs = run_feasibility(scenario_inputs)
        results[scenario_name] = _outputs_to_dict(outputs)
    return results
