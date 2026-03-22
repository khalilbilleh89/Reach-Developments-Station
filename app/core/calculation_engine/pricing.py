"""
app.core.calculation_engine.pricing

Centralized pricing math.

Covers:
- Base selling price per sqm applied to internal area.
- Attached-area pricing at a discounted rate.
- Feature / premium adjustments (floor, view, corner, size, custom).
- Price-escalation application.
- Discount / allowance impact.

No contract creation, sales state changes, or commission logic belongs here.
"""

from __future__ import annotations

from app.core.calculation_engine.types import PricingInputs, PricingOutputs


# ---------------------------------------------------------------------------
# Pure formula functions
# ---------------------------------------------------------------------------


def calculate_base_unit_price(
    internal_area_sqm: float,
    base_price_per_sqm: float,
) -> float:
    """Base unit price = internal area × base price per sqm.

    Returns 0.0 for non-positive inputs.
    """
    if internal_area_sqm <= 0.0 or base_price_per_sqm <= 0.0:
        return 0.0
    return internal_area_sqm * base_price_per_sqm


def calculate_attached_area_price(
    attached_area_sqm: float,
    attached_area_rate_per_sqm: float,
) -> float:
    """Attached-area price = attached area × attached-area rate per sqm.

    Balconies, terraces, and similar semi-external spaces are priced at
    a lower rate than internal area.

    Returns 0.0 for non-positive inputs.
    """
    if attached_area_sqm <= 0.0 or attached_area_rate_per_sqm <= 0.0:
        return 0.0
    return attached_area_sqm * attached_area_rate_per_sqm


def calculate_premium_total(
    floor_premium: float = 0.0,
    view_premium: float = 0.0,
    corner_premium: float = 0.0,
    size_adjustment: float = 0.0,
    custom_adjustment: float = 0.0,
) -> float:
    """Total premium = sum of all feature adjustment amounts.

    All premiums are absolute currency values, not percentages.
    Negative values represent deductions.
    """
    return floor_premium + view_premium + corner_premium + size_adjustment + custom_adjustment


def apply_escalation(price: float, escalation_rate: float) -> float:
    """Escalated price = price × (1 + escalation_rate).

    Parameters
    ----------
    price:
        Price before escalation.
    escalation_rate:
        Escalation rate as a decimal fraction (e.g. 0.05 for 5 %).
        Negative rates produce a price reduction.
    """
    return price * (1.0 + escalation_rate)


def apply_discount(price: float, discount_amount: float) -> float:
    """Final price after discount = price − discount_amount.

    The result is clamped to 0.0 so price cannot go negative.

    Parameters
    ----------
    price:
        Price before discount.
    discount_amount:
        Absolute currency amount to subtract. Non-positive values are ignored.
    """
    return max(price - max(discount_amount, 0.0), 0.0)


# ---------------------------------------------------------------------------
# Composite runner
# ---------------------------------------------------------------------------


def run_unit_pricing(inputs: PricingInputs) -> PricingOutputs:
    """Compute the full unit price from structured inputs.

    Calculation sequence
    --------------------
    1. base_unit_price      = internal_area × base_price_per_sqm
    2. attached_area_price  = attached_area × attached_area_rate
    3. premium_total        = sum of all feature premiums / adjustments
    4. pre_escalation_price = base_unit_price + attached_area_price + premium_total
    5. escalated_price      = pre_escalation_price × (1 + escalation_rate)
    6. final_unit_price     = escalated_price − discount_amount

    Parameters
    ----------
    inputs:
        Validated :class:`~app.core.calculation_engine.types.PricingInputs`.

    Returns
    -------
    PricingOutputs
        All intermediate and final pricing values.
    """
    base_unit_price = calculate_base_unit_price(
        inputs.internal_area_sqm, inputs.base_price_per_sqm
    )
    attached_area_price = calculate_attached_area_price(
        inputs.attached_area_sqm, inputs.attached_area_rate_per_sqm
    )
    premium_total = calculate_premium_total(
        floor_premium=inputs.floor_premium,
        view_premium=inputs.view_premium,
        corner_premium=inputs.corner_premium,
        size_adjustment=inputs.size_adjustment,
        custom_adjustment=inputs.custom_adjustment,
    )
    pre_escalation_price = base_unit_price + attached_area_price + premium_total
    escalated_price = apply_escalation(pre_escalation_price, inputs.escalation_rate)
    final_unit_price = apply_discount(escalated_price, inputs.discount_amount)

    return PricingOutputs(
        base_unit_price=base_unit_price,
        attached_area_price=attached_area_price,
        premium_total=premium_total,
        pre_escalation_price=pre_escalation_price,
        escalated_price=escalated_price,
        final_unit_price=final_unit_price,
    )
