"""
concept_design.engine

Pure calculation engine for concept-level physical program metrics.

All inputs come from ConceptUnitMixLine records.  The engine derives:
  unit_count        — total units across all mix lines
  sellable_area     — sum of (units_count × avg_sellable_area) across lines
  efficiency_ratio  — sellable_area / gross_floor_area  (None when gfa == 0)
  average_unit_area — sellable_area / unit_count        (None when count == 0)

Rules
-----
- All derived values are computed, never manually trusted.
- Division-by-zero conditions return None rather than raising.

PR-CONCEPT-052
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class MixLineInput:
    """Immutable snapshot of one unit-mix line for engine consumption."""

    unit_type: str
    units_count: int
    avg_sellable_area: Optional[float]


@dataclass(frozen=True)
class ConceptProgramMetrics:
    """Derived physical-program metrics produced by the concept engine."""

    unit_count: int
    sellable_area: Optional[float]
    efficiency_ratio: Optional[float]
    average_unit_area: Optional[float]


def compute_unit_count(mix_lines: List[MixLineInput]) -> int:
    """Sum units_count across all mix lines."""
    return sum(line.units_count for line in mix_lines)


def compute_sellable_area(mix_lines: List[MixLineInput]) -> Optional[float]:
    """Sum (units_count × avg_sellable_area) for lines that have avg_sellable_area set.

    Returns None when no line carries an avg_sellable_area value.
    """
    total: float = 0.0
    any_area = False
    for line in mix_lines:
        if line.avg_sellable_area is not None:
            total += line.units_count * line.avg_sellable_area
            any_area = True
    return total if any_area else None


def compute_efficiency_ratio(
    sellable_area: Optional[float],
    gross_floor_area: Optional[float],
) -> Optional[float]:
    """sellable_area / gross_floor_area.

    Returns None when either value is absent or gross_floor_area is zero.
    """
    if sellable_area is None or not gross_floor_area:
        return None
    return sellable_area / gross_floor_area


def compute_average_unit_area(
    sellable_area: Optional[float],
    unit_count: int,
) -> Optional[float]:
    """sellable_area / unit_count.

    Returns None when sellable_area is absent or unit_count is zero.
    """
    if sellable_area is None or unit_count == 0:
        return None
    return sellable_area / unit_count


def run_concept_engine(
    mix_lines: List[MixLineInput],
    gross_floor_area: Optional[float],
) -> ConceptProgramMetrics:
    """Execute the full concept design calculation from mix-line inputs.

    Parameters
    ----------
    mix_lines:
        List of :class:`MixLineInput` snapshots from the concept option's
        unit mix.
    gross_floor_area:
        Gross floor area (sqm) stored on the parent ConceptOption, used to
        compute the efficiency ratio.  May be None.

    Returns
    -------
    ConceptProgramMetrics
        All derived physical-program metrics.
    """
    unit_count = compute_unit_count(mix_lines)
    sellable_area = compute_sellable_area(mix_lines)
    efficiency_ratio = compute_efficiency_ratio(sellable_area, gross_floor_area)
    average_unit_area = compute_average_unit_area(sellable_area, unit_count)

    return ConceptProgramMetrics(
        unit_count=unit_count,
        sellable_area=sellable_area,
        efficiency_ratio=efficiency_ratio,
        average_unit_area=average_unit_area,
    )
