"""
Break-even analysis engine.

Calculates break-even selling price, break-even sellable area, and
equity multiple from feasibility cost and revenue inputs.

Formulas
--------
break_even_price_per_sqm = total_cost / sellable_area_sqm
break_even_units_sqm     = total_cost / avg_sale_price_per_sqm
equity_multiple          = gdv / total_cost
"""

from __future__ import annotations


def calculate_break_even_price_per_sqm(
    total_cost: float,
    sellable_area_sqm: float,
) -> float:
    """Minimum sale price per sqm required to cover all development costs.

    Returns 0.0 when sellable_area_sqm is zero to avoid division by zero.
    """
    if sellable_area_sqm <= 0.0:
        return 0.0
    return total_cost / sellable_area_sqm


def calculate_break_even_units_sqm(
    total_cost: float,
    avg_sale_price_per_sqm: float,
) -> float:
    """Minimum sellable area (sqm) that must be sold to recover all costs.

    Returns 0.0 when avg_sale_price_per_sqm is zero to avoid division by zero.
    """
    if avg_sale_price_per_sqm <= 0.0:
        return 0.0
    return total_cost / avg_sale_price_per_sqm


def calculate_equity_multiple(gdv: float, total_cost: float) -> float:
    """Equity multiple = GDV / total cost.

    Measures how many times total investment is returned as revenue.
    Returns 0.0 when total_cost is zero to avoid division by zero.
    """
    if total_cost <= 0.0:
        return 0.0
    return gdv / total_cost
