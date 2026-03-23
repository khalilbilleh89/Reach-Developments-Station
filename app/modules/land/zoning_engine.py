"""
land.zoning_engine

Land Zoning & Regulation Engine.

Converts parcel attributes and zoning rules into derived development limits.

Formulas
--------
max_buildable_area       = land_area × FAR
max_footprint_area       = land_area × coverage_ratio
max_floors               = floor(max_height_m / floor_height_m)
setback_adjusted_area    = area of parcel after setback deductions
                           (assumes square plot when setbacks are provided)
effective_footprint      = min(max_footprint_area,
                               setback_adjusted_area × coverage_ratio)
effective_buildable_area = min(max_buildable_area,
                               effective_footprint × max_floors)
estimated_unit_capacity  = floor(effective_buildable_area / avg_unit_size_sqm)
                           (None when avg_unit_size_sqm is not provided)
parking_required         = round(estimated_unit_capacity × parking_ratio)
                           (0 when estimated_unit_capacity is None)

Note: setback_adjusted_area assumes a square plot with side = sqrt(land_area).
When all setbacks are zero the full land_area is used unchanged.
"""

from dataclasses import dataclass, field
from math import floor, sqrt
from typing import Optional


@dataclass(frozen=True)
class ZoningInputs:
    """Validated inputs required by the land zoning regulation engine."""

    land_area: float           # sqm — total parcel area
    far: float                 # Floor Area Ratio (e.g. 3.5 = 3.5× land area)
    coverage_ratio: float      # site coverage fraction (e.g. 0.6 = 60 %)
    max_height_m: float        # maximum permitted building height in metres
    floor_height_m: float      # storey height in metres (e.g. 3.0)
    parking_ratio: float       # parking spaces per unit (e.g. 1.2)
    setback_front: float = 0.0   # metres
    setback_side: float = 0.0    # metres
    setback_rear: float = 0.0    # metres
    avg_unit_size_sqm: Optional[float] = field(default=None)  # for unit-count derivation


@dataclass(frozen=True)
class ZoningResult:
    """Outputs from the land zoning regulation engine."""

    max_buildable_area: float        # = land_area × FAR
    max_footprint_area: float        # = land_area × coverage_ratio
    max_floors: int                  # = floor(max_height_m / floor_height_m)
    setback_adjusted_area: float     # parcel area after setback deductions
    effective_footprint: float       # footprint bounded by setbacks + coverage
    effective_buildable_area: float  # min(FAR-limit, height×footprint-limit)
    estimated_unit_capacity: Optional[int]  # None when avg_unit_size_sqm not provided
    parking_required: int            # estimated_unit_capacity × parking_ratio


# ---------------------------------------------------------------------------
# Individual calculation functions
# ---------------------------------------------------------------------------

def calculate_max_buildable_area(land_area: float, far: float) -> float:
    """Maximum buildable area = land area × FAR."""
    return land_area * far


def calculate_max_footprint_area(land_area: float, coverage_ratio: float) -> float:
    """Maximum footprint area = land area × coverage ratio."""
    return land_area * coverage_ratio


def calculate_max_floors(max_height_m: float, floor_height_m: float) -> int:
    """Maximum floors = floor(max_height_m / floor_height_m).

    Returns 0 when floor_height_m is non-positive (<= 0.0) to avoid invalid division.
    """
    if floor_height_m <= 0.0:
        return 0
    return floor(max_height_m / floor_height_m)


def calculate_setback_adjusted_area(
    land_area: float,
    setback_front: float,
    setback_side: float,
    setback_rear: float,
) -> float:
    """Land area remaining after applying front, side, and rear setbacks.

    Assumes a square plot: side = sqrt(land_area).
    When all setbacks are zero the original land_area is returned unchanged.
    The result is clamped to a minimum of 0.0.

    Returns 0.0 when land_area is non-positive to avoid a ValueError from sqrt().
    """
    if land_area <= 0.0:
        return 0.0
    if setback_front == 0.0 and setback_side == 0.0 and setback_rear == 0.0:
        return land_area
    side = sqrt(land_area)
    effective_depth = max(0.0, side - setback_front - setback_rear)
    effective_width = max(0.0, side - 2.0 * setback_side)
    return effective_depth * effective_width


def calculate_effective_footprint(
    max_footprint_area: float,
    setback_adjusted_area: float,
    coverage_ratio: float,
) -> float:
    """Effective footprint bounded by both coverage ratio and setbacks.

    effective_footprint = min(max_footprint_area,
                              setback_adjusted_area × coverage_ratio)
    """
    setback_footprint = setback_adjusted_area * coverage_ratio
    return min(max_footprint_area, setback_footprint)


def calculate_effective_buildable_area(
    max_buildable_area: float,
    effective_footprint: float,
    max_floors: int,
) -> float:
    """Effective buildable area bounded by both FAR and height × footprint.

    effective_buildable_area = min(max_buildable_area,
                                   effective_footprint × max_floors)
    """
    return min(max_buildable_area, effective_footprint * max_floors)


def calculate_estimated_unit_capacity(
    effective_buildable_area: float,
    avg_unit_size_sqm: Optional[float],
) -> Optional[int]:
    """Estimated unit capacity = floor(effective_buildable_area / avg_unit_size_sqm).

    Returns None when avg_unit_size_sqm is not provided or is non-positive.
    """
    if avg_unit_size_sqm is None or avg_unit_size_sqm <= 0.0:
        return None
    return floor(effective_buildable_area / avg_unit_size_sqm)


def calculate_parking_required(
    estimated_unit_capacity: Optional[int],
    parking_ratio: float,
) -> int:
    """Parking spaces required = round(estimated_unit_capacity × parking_ratio).

    Returns 0 when estimated_unit_capacity is None.
    """
    if estimated_unit_capacity is None:
        return 0
    return round(estimated_unit_capacity * parking_ratio)


# ---------------------------------------------------------------------------
# Main engine entry point
# ---------------------------------------------------------------------------

def run_zoning_calculation(inputs: ZoningInputs) -> ZoningResult:
    """Execute the full zoning regulation calculation from structured inputs.

    Parameters
    ----------
    inputs:
        Validated :class:`ZoningInputs` dataclass.

    Returns
    -------
    ZoningResult
        All derived zoning regulation metrics.
    """
    max_buildable_area = calculate_max_buildable_area(inputs.land_area, inputs.far)
    max_footprint_area = calculate_max_footprint_area(inputs.land_area, inputs.coverage_ratio)
    max_floors = calculate_max_floors(inputs.max_height_m, inputs.floor_height_m)
    setback_adjusted_area = calculate_setback_adjusted_area(
        inputs.land_area,
        inputs.setback_front,
        inputs.setback_side,
        inputs.setback_rear,
    )
    effective_footprint = calculate_effective_footprint(
        max_footprint_area,
        setback_adjusted_area,
        inputs.coverage_ratio,
    )
    effective_buildable_area = calculate_effective_buildable_area(
        max_buildable_area,
        effective_footprint,
        max_floors,
    )
    estimated_unit_capacity = calculate_estimated_unit_capacity(
        effective_buildable_area,
        inputs.avg_unit_size_sqm,
    )
    parking_required = calculate_parking_required(estimated_unit_capacity, inputs.parking_ratio)

    return ZoningResult(
        max_buildable_area=max_buildable_area,
        max_footprint_area=max_footprint_area,
        max_floors=max_floors,
        setback_adjusted_area=setback_adjusted_area,
        effective_footprint=effective_footprint,
        effective_buildable_area=effective_buildable_area,
        estimated_unit_capacity=estimated_unit_capacity,
        parking_required=parking_required,
    )
