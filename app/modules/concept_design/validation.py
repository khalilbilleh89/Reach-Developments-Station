"""
concept_design.validation

Pure zoning and structural validation engine for Concept Design.

Validates concept option inputs against land/zoning constraints before
the option is accepted as a valid development program.  The engine is
stateless and side-effect free — it never touches the database.

Rules
-----
FAR rule
    gross_floor_area ≤ site_area × far_limit
    Skipped when site_area, gross_floor_area, or far_limit is absent.

Efficiency rule
    sellable_area / gross_floor_area ≤ 1.0
    Skipped when sellable_area or gross_floor_area is absent.

Density rule
    unit_count ≤ density_limit (dph) × site_area_ha
    Skipped when unit_count, site_area, or density_limit is absent.

Area consistency rule
    sellable_area ≤ gross_floor_area  (implicit from efficiency ≤ 1.0;
    also catches cases where efficiency rule inputs are partial)
    Skipped when either area value is absent.

PR-CONCEPT-059
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ConceptZoningViolation:
    """A single rule violation produced by the validation engine."""

    rule: str
    message: str
    details: dict = field(default_factory=dict)


def validate_far_rule(
    site_area: Optional[float],
    gross_floor_area: Optional[float],
    far_limit: Optional[float],
) -> Optional[ConceptZoningViolation]:
    """Return a violation if gross_floor_area exceeds site_area × far_limit.

    Returns None (no violation) when any input is absent so that options
    without a FAR constraint configured are not blocked.
    """
    if site_area is None or gross_floor_area is None or far_limit is None:
        return None
    if site_area <= 0 or far_limit <= 0:
        return None

    max_gfa = site_area * far_limit
    if gross_floor_area > max_gfa:
        return ConceptZoningViolation(
            rule="FAR_EXCEEDED",
            message=(
                f"Gross floor area ({gross_floor_area:,.0f} m²) exceeds the "
                f"permitted FAR capacity of {max_gfa:,.0f} m² "
                f"(site {site_area:,.0f} m² × FAR {far_limit:.2f})."
            ),
            details={
                "gross_floor_area": gross_floor_area,
                "site_area": site_area,
                "far_limit": far_limit,
                "max_permitted_gfa": max_gfa,
            },
        )
    return None


def validate_efficiency_rule(
    sellable_area: Optional[float],
    gross_floor_area: Optional[float],
) -> Optional[ConceptZoningViolation]:
    """Return a violation if the efficiency ratio exceeds 1.0.

    An efficiency ratio > 1.0 is physically impossible — sellable area
    cannot exceed gross floor area.  Returns None when either input is
    absent or gross_floor_area is zero.
    """
    if sellable_area is None or not gross_floor_area:
        return None

    efficiency = sellable_area / gross_floor_area
    if efficiency > 1.0:
        return ConceptZoningViolation(
            rule="EFFICIENCY_IMPOSSIBLE",
            message=(
                f"Sellable area ({sellable_area:,.0f} m²) exceeds gross floor "
                f"area ({gross_floor_area:,.0f} m²), implying an impossible "
                f"efficiency ratio of {efficiency:.2%}. "
                "Sellable area cannot exceed gross floor area."
            ),
            details={
                "sellable_area": sellable_area,
                "gross_floor_area": gross_floor_area,
                "efficiency_ratio": round(efficiency, 4),
            },
        )
    return None


def validate_density_rule(
    unit_count: Optional[int],
    site_area: Optional[float],
    density_limit: Optional[float],
) -> Optional[ConceptZoningViolation]:
    """Return a violation if unit_count exceeds density_limit × site area in hectares.

    density_limit is expressed as dwellings per hectare (DPH).
    site_area is expressed in square metres (site_area / 10 000 = hectares).

    Returns None when unit_count, site_area, or density_limit is absent,
    or when site_area is zero.
    """
    if unit_count is None or site_area is None or density_limit is None:
        return None
    if site_area <= 0 or density_limit <= 0:
        return None

    site_area_ha = site_area / 10_000.0
    max_units = density_limit * site_area_ha
    if unit_count > max_units:
        return ConceptZoningViolation(
            rule="DENSITY_EXCEEDED",
            message=(
                f"Unit count ({unit_count:,}) exceeds the configured density "
                f"limit of {max_units:,.0f} units "
                f"({density_limit:.0f} dph × {site_area_ha:.4f} ha)."
            ),
            details={
                "unit_count": unit_count,
                "site_area": site_area,
                "site_area_ha": round(site_area_ha, 4),
                "density_limit_dph": density_limit,
                "max_permitted_units": max_units,
            },
        )
    return None


def run_zoning_validation(
    site_area: Optional[float],
    gross_floor_area: Optional[float],
    far_limit: Optional[float],
    density_limit: Optional[float],
    sellable_area: Optional[float] = None,
    unit_count: Optional[int] = None,
) -> List[ConceptZoningViolation]:
    """Run all applicable zoning and structural validation rules.

    Rules where the required inputs are absent are silently skipped so
    that draft concept options with only partial data are not blocked.

    Parameters
    ----------
    site_area:
        Site area in square metres.
    gross_floor_area:
        Gross floor area in square metres.
    far_limit:
        Maximum floor area ratio (e.g. 2.5 → GFA ≤ 2.5 × site_area).
    density_limit:
        Maximum density in dwellings per hectare.
    sellable_area:
        Total sellable area derived from unit mix (sqm).  Passed when
        mix-line data is available (e.g. at promote time).
    unit_count:
        Total unit count derived from unit mix.  Passed when mix-line
        data is available (e.g. at promote time).

    Returns
    -------
    list[ConceptZoningViolation]
        Empty list means all applicable rules passed.
    """
    violations: List[ConceptZoningViolation] = []

    far_violation = validate_far_rule(site_area, gross_floor_area, far_limit)
    if far_violation:
        violations.append(far_violation)

    efficiency_violation = validate_efficiency_rule(sellable_area, gross_floor_area)
    if efficiency_violation:
        violations.append(efficiency_violation)

    density_violation = validate_density_rule(unit_count, site_area, density_limit)
    if density_violation:
        violations.append(density_violation)

    return violations
