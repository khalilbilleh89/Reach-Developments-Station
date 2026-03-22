"""
app.core.calculation_engine.areas

Centralized area-based formulas.

Covers:
- Buildable area from land area and permitted FAR.
- Estimated sellable area from buildable area and sellable ratio.
- Internal vs attached area split for unit-level calculations.
- Weighted sellable proxies.

No zoning lookup, UI formatting, or persistence belongs here.
"""

from __future__ import annotations

from app.core.calculation_engine.types import AreaInputs, AreaOutputs


# ---------------------------------------------------------------------------
# Pure formula functions
# ---------------------------------------------------------------------------


def calculate_buildable_area(land_area_sqm: float, permitted_far: float) -> float:
    """Buildable area = land area × permitted FAR.

    Returns 0.0 for non-positive inputs to avoid nonsensical results.

    Parameters
    ----------
    land_area_sqm:
        Gross land area in square metres. Must be positive.
    permitted_far:
        Permitted floor-area ratio (e.g. 2.5 means 250 % of land area).
        Must be positive.
    """
    if land_area_sqm <= 0.0 or permitted_far <= 0.0:
        return 0.0
    return land_area_sqm * permitted_far


def calculate_sellable_area(buildable_area_sqm: float, sellable_ratio: float) -> float:
    """Estimated sellable area = buildable area × sellable ratio.

    Returns 0.0 for non-positive inputs.

    Parameters
    ----------
    buildable_area_sqm:
        Total buildable (gross floor) area. Must be positive.
    sellable_ratio:
        Fraction of buildable area that is sellable, e.g. 0.85 for 85 %.
        Must be positive. Values above 1.0 are accepted (e.g. when leasable
        gross floor area differs from net lettable area) but callers should
        ensure this reflects a valid underwriting assumption.
    """
    if buildable_area_sqm <= 0.0 or sellable_ratio <= 0.0:
        return 0.0
    return buildable_area_sqm * sellable_ratio


def calculate_internal_area(total_unit_area_sqm: float, attached_area_sqm: float) -> float:
    """Internal area = total unit area − attached area.

    Attached area covers balconies, terraces, and similar semi-external
    spaces that are priced at a different (usually lower) rate.

    Returns 0.0 when the result would be negative (i.e. attached area
    claimed to be larger than the total unit area).

    Parameters
    ----------
    total_unit_area_sqm:
        Total measured area of the unit.
    attached_area_sqm:
        Portion of the unit area classified as attached / semi-external.
    """
    internal = total_unit_area_sqm - max(attached_area_sqm, 0.0)
    return max(internal, 0.0)


def calculate_weighted_sellable_area(
    internal_area_sqm: float,
    attached_area_sqm: float,
    attached_area_weight: float = 0.5,
) -> float:
    """Weighted sellable area = internal area + (attached area × weight).

    Used when attached areas should count at a fractional rate for pricing
    or sellable-area totals.

    Parameters
    ----------
    internal_area_sqm:
        Fully weighted internal area.
    attached_area_sqm:
        Attached area (balcony, terrace). Must be non-negative.
    attached_area_weight:
        Fractional weight applied to attached area (default 0.5).
        Clamped to [0, 1].
    """
    weight = max(0.0, min(attached_area_weight, 1.0))
    return max(internal_area_sqm, 0.0) + max(attached_area_sqm, 0.0) * weight


# ---------------------------------------------------------------------------
# Composite runner
# ---------------------------------------------------------------------------


def run_area_calculations(inputs: AreaInputs) -> AreaOutputs:
    """Compute buildable and sellable area from structured inputs.

    Parameters
    ----------
    inputs:
        Validated :class:`~app.core.calculation_engine.types.AreaInputs`.

    Returns
    -------
    AreaOutputs
        Buildable and sellable area in square metres.
    """
    buildable = calculate_buildable_area(inputs.land_area_sqm, inputs.permitted_far)
    sellable = calculate_sellable_area(buildable, inputs.sellable_ratio)
    return AreaOutputs(
        buildable_area_sqm=buildable,
        sellable_area_sqm=sellable,
    )
