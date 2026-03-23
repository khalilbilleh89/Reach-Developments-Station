"""
land.aggregation_engine

Pure parcel aggregation calculation engine for the Land Parcel Assembly workflow.

This engine is stateless — it accepts a list of per-parcel metric snapshots and
returns a deterministic, recomputable aggregate result.  No database access, no
HTTP concerns, and no feasibility formulas belong here.

Aggregation rules
-----------------
total_area_sqm              = sum of parcel land_area_sqm (parcels with None excluded)
total_frontage_m            = sum of parcel frontage_m (parcels with None excluded)
total_acquisition_price     = sum of parcel acquisition_price (parcels with None excluded)
total_transaction_cost      = sum of parcel transaction_cost (parcels with None excluded)
effective_land_basis        = total_acquisition_price + total_transaction_cost
weighted_permitted_far      = area-weighted average FAR across parcels that have both
                              land_area_sqm and permitted_far set; None when none qualify
dominant_zoning_category    = most common zoning_category across parcels (by count);
                              None when no parcel carries a zoning_category
mixed_zoning                = True when > 1 distinct zoning_category is present
has_utilities               = True when at least one parcel has utilities_available=True
has_corner_plot             = True when at least one parcel is a corner_plot
zoning_category_counts      = per-category occurrence counts (for diagnostics)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ParcelMetrics:
    """Per-parcel metrics snapshot consumed by the aggregation engine.

    These values are extracted from canonical parcel records by the service
    layer before being passed into the engine.  The engine never reads from
    the database directly.
    """

    parcel_id: str
    land_area_sqm: Optional[float] = None
    frontage_m: Optional[float] = None
    acquisition_price: Optional[float] = None
    transaction_cost: Optional[float] = None
    permitted_far: Optional[float] = None
    zoning_category: Optional[str] = None
    utilities_available: bool = False
    corner_plot: bool = False


@dataclass(frozen=True)
class AssemblyAggregationResult:
    """Outputs produced by the parcel aggregation engine.

    All numeric totals default to 0.0 when no parcels carry the relevant field,
    so consumers always receive a complete, consistent record.
    """

    parcel_count: int
    total_area_sqm: float
    total_frontage_m: float
    total_acquisition_price: float
    total_transaction_cost: float
    effective_land_basis: float               # total_acquisition_price + total_transaction_cost
    weighted_permitted_far: Optional[float]   # area-weighted average FAR; None if unavailable
    dominant_zoning_category: Optional[str]   # most frequent zoning category; None if unavailable
    mixed_zoning: bool                        # True when > 1 distinct zoning_category present
    has_utilities: bool                       # True if any parcel has utilities_available=True
    has_corner_plot: bool                     # True if any parcel is a corner_plot
    zoning_category_counts: Dict[str, int] = field(default_factory=dict)


def aggregate_parcels(parcels: List[ParcelMetrics]) -> AssemblyAggregationResult:
    """Execute the parcel aggregation calculation.

    Parameters
    ----------
    parcels:
        Non-empty list of :class:`ParcelMetrics` snapshots.  The caller is
        responsible for ensuring there are no duplicate ``parcel_id`` entries.

    Returns
    -------
    AssemblyAggregationResult
        Deterministic aggregate metrics derived from the supplied parcels.

    Raises
    ------
    ValueError
        When *parcels* is empty — an assembly must contain at least one parcel.
    """
    if not parcels:
        raise ValueError("Assembly must contain at least one parcel.")

    # -----------------------------------------------------------------------
    # Simple summation fields
    # -----------------------------------------------------------------------
    total_area_sqm = sum(p.land_area_sqm for p in parcels if p.land_area_sqm is not None)
    total_frontage_m = sum(p.frontage_m for p in parcels if p.frontage_m is not None)
    total_acquisition_price = sum(
        p.acquisition_price for p in parcels if p.acquisition_price is not None
    )
    total_transaction_cost = sum(
        p.transaction_cost for p in parcels if p.transaction_cost is not None
    )
    effective_land_basis = total_acquisition_price + total_transaction_cost

    # -----------------------------------------------------------------------
    # Area-weighted permitted FAR
    # -----------------------------------------------------------------------
    weighted_permitted_far: Optional[float] = None
    far_pairs = [
        (p.land_area_sqm, p.permitted_far)
        for p in parcels
        if p.land_area_sqm is not None
        and p.land_area_sqm > 0.0
        and p.permitted_far is not None
        and p.permitted_far > 0.0
    ]
    if far_pairs:
        total_far_weight = sum(area * far for area, far in far_pairs)
        total_far_area = sum(area for area, _ in far_pairs)
        if total_far_area > 0.0:
            weighted_permitted_far = total_far_weight / total_far_area

    # -----------------------------------------------------------------------
    # Zoning category analysis
    # -----------------------------------------------------------------------
    zoning_category_counts: Dict[str, int] = {}
    for p in parcels:
        if p.zoning_category is not None:
            zoning_category_counts[p.zoning_category] = (
                zoning_category_counts.get(p.zoning_category, 0) + 1
            )

    mixed_zoning = len(zoning_category_counts) > 1
    dominant_zoning_category: Optional[str] = None
    if zoning_category_counts:
        dominant_zoning_category = max(
            zoning_category_counts, key=lambda k: zoning_category_counts[k]
        )

    # -----------------------------------------------------------------------
    # Shared infrastructure flags
    # -----------------------------------------------------------------------
    has_utilities = any(p.utilities_available for p in parcels)
    has_corner_plot = any(p.corner_plot for p in parcels)

    return AssemblyAggregationResult(
        parcel_count=len(parcels),
        total_area_sqm=total_area_sqm,
        total_frontage_m=total_frontage_m,
        total_acquisition_price=total_acquisition_price,
        total_transaction_cost=total_transaction_cost,
        effective_land_basis=effective_land_basis,
        weighted_permitted_far=weighted_permitted_far,
        dominant_zoning_category=dominant_zoning_category,
        mixed_zoning=mixed_zoning,
        has_utilities=has_utilities,
        has_corner_plot=has_corner_plot,
        zoning_category_counts=zoning_category_counts,
    )
