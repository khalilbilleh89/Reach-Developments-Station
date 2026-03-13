"""
Pricing calculation engine.

Deterministic formulas for unit sale price calculation.
All inputs and outputs use consistent units (sqm, currency).

Formulas
--------
base_unit_price  = base_price_per_sqm * unit_area

premium_total    = floor_premium
                 + view_premium
                 + corner_premium
                 + size_adjustment
                 + custom_adjustment

final_unit_price = base_unit_price + premium_total

Note: No discount, commission, tax, or dynamic demand logic is included.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PricingInputs:
    """Validated inputs required by the pricing engine."""

    unit_area: float
    base_price_per_sqm: float
    floor_premium: float
    view_premium: float
    corner_premium: float
    size_adjustment: float
    custom_adjustment: float


@dataclass(frozen=True)
class PricingOutputs:
    """Calculated outputs produced by the pricing engine."""

    base_unit_price: float
    premium_total: float
    final_unit_price: float


def calculate_base_price(unit_area: float, base_price_per_sqm: float) -> float:
    """Base unit price = unit area × base price per sqm."""
    return unit_area * base_price_per_sqm


def calculate_floor_premium(floor_premium: float) -> float:
    """Floor premium (absolute currency value)."""
    return floor_premium


def calculate_view_premium(view_premium: float) -> float:
    """View premium (absolute currency value)."""
    return view_premium


def calculate_corner_premium(corner_premium: float) -> float:
    """Corner premium (absolute currency value)."""
    return corner_premium


def calculate_adjustments(size_adjustment: float, custom_adjustment: float) -> float:
    """Size and custom adjustments (absolute currency values)."""
    return size_adjustment + custom_adjustment


def calculate_final_price(base_unit_price: float, premium_total: float) -> float:
    """Final unit price = base unit price + total premiums."""
    return base_unit_price + premium_total


def run_pricing(inputs: PricingInputs) -> PricingOutputs:
    """Execute the full unit pricing calculation from structured inputs.

    Parameters
    ----------
    inputs:
        Validated :class:`PricingInputs` dataclass.

    Returns
    -------
    PricingOutputs
        All derived pricing metrics.
    """
    base_unit_price = calculate_base_price(inputs.unit_area, inputs.base_price_per_sqm)
    floor_premium = calculate_floor_premium(inputs.floor_premium)
    view_premium = calculate_view_premium(inputs.view_premium)
    corner_premium = calculate_corner_premium(inputs.corner_premium)
    adjustments = calculate_adjustments(inputs.size_adjustment, inputs.custom_adjustment)
    premium_total = floor_premium + view_premium + corner_premium + adjustments
    final_unit_price = calculate_final_price(base_unit_price, premium_total)

    return PricingOutputs(
        base_unit_price=base_unit_price,
        premium_total=premium_total,
        final_unit_price=final_unit_price,
    )
