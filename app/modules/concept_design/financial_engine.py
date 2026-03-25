"""
concept_design.financial_engine

Pure GDV estimation engine for the Concept Design module.

Rules enforced here:
  - No DB access, no HTTP concerns, no side effects.
  - All derived values are computed from program metrics and pricing inputs.
  - No IRR, NPV, margin, or construction cost formulas here.
  - No feasibility logic duplicated here.

Estimation Logic
----------------
Primary path (preferred):
    estimated_gdv = sellable_area * price_per_sqm

Fallback path (when price_per_sqm or sellable_area is unavailable):
    estimated_gdv = unit_count * price_per_unit

When neither path is available:
    estimated_gdv = None (no pricing data supplied)

Derived metrics:
    estimated_revenue_per_sqm = estimated_gdv / sellable_area
    estimated_revenue_per_unit = estimated_gdv / unit_count

Both derived metrics are None when the required denominator is zero or None.

PR-CONCEPT-062
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ConceptFinancialMetrics:
    """Derived financial metrics for a single concept option.

    All values are live-computed and are never persisted to the database.

    Attributes
    ----------
    estimated_gdv:
        Gross Development Value estimate.  None when insufficient pricing
        data is available.
    estimated_revenue_per_sqm:
        GDV divided by sellable area.  None when sellable_area is absent.
    estimated_revenue_per_unit:
        GDV divided by unit count.  None when unit_count is zero.
    """

    estimated_gdv: Optional[float]
    estimated_revenue_per_sqm: Optional[float]
    estimated_revenue_per_unit: Optional[float]


def estimate_concept_financials(
    *,
    sellable_area: Optional[float],
    unit_count: int,
    price_per_sqm: Optional[float] = None,
    price_per_unit: Optional[float] = None,
) -> ConceptFinancialMetrics:
    """Derive GDV and revenue metrics for a concept option.

    Parameters
    ----------
    sellable_area:
        Total sellable area in square metres, from the concept engine.
        May be None when no mix lines have avg_sellable_area set.
    unit_count:
        Total unit count from the concept engine.  Should be >= 0.
    price_per_sqm:
        Average sale price per square metre (scenario pricing assumption).
        When provided together with a non-None sellable_area, this is the
        primary GDV input path.
    price_per_unit:
        Average sale price per unit (scenario pricing assumption).
        Used as a fallback when price_per_sqm or sellable_area is absent.

    Returns
    -------
    ConceptFinancialMetrics
        Derived financial metrics.  All fields are None when the required
        pricing inputs are not available.
    """
    # Guard: treat non-finite pricing inputs as absent to prevent inf/nan in output
    if price_per_sqm is not None and not math.isfinite(price_per_sqm):
        price_per_sqm = None
    if price_per_unit is not None and not math.isfinite(price_per_unit):
        price_per_unit = None

    estimated_gdv: Optional[float] = None

    # Primary path: area-based GDV
    if (
        price_per_sqm is not None
        and price_per_sqm > 0
        and sellable_area is not None
        and sellable_area > 0
    ):
        estimated_gdv = sellable_area * price_per_sqm
    # Fallback path: unit-based GDV
    elif price_per_unit is not None and price_per_unit > 0 and unit_count > 0:
        estimated_gdv = unit_count * price_per_unit

    # Guard: non-finite computed GDV (e.g. from extreme inputs) is treated as absent
    if estimated_gdv is not None and not math.isfinite(estimated_gdv):
        estimated_gdv = None

    estimated_revenue_per_sqm: Optional[float] = None
    if estimated_gdv is not None and sellable_area is not None and sellable_area > 0:
        estimated_revenue_per_sqm = estimated_gdv / sellable_area

    estimated_revenue_per_unit: Optional[float] = None
    if estimated_gdv is not None and unit_count > 0:
        estimated_revenue_per_unit = estimated_gdv / unit_count

    return ConceptFinancialMetrics(
        estimated_gdv=estimated_gdv,
        estimated_revenue_per_sqm=estimated_revenue_per_sqm,
        estimated_revenue_per_unit=estimated_revenue_per_unit,
    )
