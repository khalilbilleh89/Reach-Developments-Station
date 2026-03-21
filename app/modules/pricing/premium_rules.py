"""
Premium rule evaluator.

Applies configured premium rules (floor, view, corner, size, custom) to base prices.
Returns a deterministic, settings-driven breakdown of each premium component.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PremiumBreakdownResult:
    """Structured breakdown of premium components for a unit.

    All monetary values are absolute currency amounts.
    base_unit_price = base_price_per_sqm * unit_area.
    premium_total   = sum of all individual premium components.
    final_unit_price = base_unit_price + premium_total.
    """

    unit_id: str
    base_price_per_sqm: float
    unit_area: float
    base_unit_price: float
    floor_premium: float
    view_premium: float
    corner_premium: float
    size_adjustment: float
    custom_adjustment: float
    premium_total: float
    final_unit_price: float


def calculate_premium_breakdown(
    unit_id: str,
    unit_area: float,
    base_price_per_sqm: float,
    floor_premium: float = 0.0,
    view_premium: float = 0.0,
    corner_premium: float = 0.0,
    size_adjustment: float = 0.0,
    custom_adjustment: float = 0.0,
) -> PremiumBreakdownResult:
    """Calculate a deterministic premium breakdown for a unit.

    All premium inputs are absolute currency values.  ``base_price_per_sqm``
    is currency per sqm; ``unit_area`` is in sqm.

    The result is a frozen dataclass so that callers cannot mutate it
    after construction — this enforces the deterministic contract.

    Parameters
    ----------
    unit_id:
        The unit identifier for traceability.
    unit_area:
        Effective unit area in sqm (gross_area when available, else internal_area).
    base_price_per_sqm:
        Base price per sqm in the platform currency.
    floor_premium:
        Absolute premium for floor level.
    view_premium:
        Absolute premium for view orientation.
    corner_premium:
        Absolute premium for corner positioning.
    size_adjustment:
        Absolute size-based adjustment (can be negative).
    custom_adjustment:
        Absolute custom adjustment (can be negative).

    Returns
    -------
    PremiumBreakdownResult
        Frozen breakdown of all premium components and the derived totals.
    """
    base_unit_price = base_price_per_sqm * unit_area
    premium_total = (
        floor_premium
        + view_premium
        + corner_premium
        + size_adjustment
        + custom_adjustment
    )
    final_unit_price = base_unit_price + premium_total

    return PremiumBreakdownResult(
        unit_id=unit_id,
        base_price_per_sqm=base_price_per_sqm,
        unit_area=unit_area,
        base_unit_price=base_unit_price,
        floor_premium=floor_premium,
        view_premium=view_premium,
        corner_premium=corner_premium,
        size_adjustment=size_adjustment,
        custom_adjustment=custom_adjustment,
        premium_total=premium_total,
        final_unit_price=final_unit_price,
    )
