"""
concept_design.comparison_engine

Pure comparison engine for concept design options.

Accepts a list of ConceptOptionComparisonInput snapshots (derived from
the existing concept summary pipeline) and produces a structured
side-by-side comparison with best-option flags and delta metrics.

Comparison Rules
----------------
- best_sellable_area  → max sellable_area  (ignoring options with None)
- best_efficiency     → max efficiency_ratio (ignoring options with None)
- best_unit_count     → max unit_count

If all options have None for a metric, no best option is chosen for that
metric (the corresponding best_*_option_id is None and all flags are False).

Tie-breaking: when two options share the same metric value the option
with the lexicographically-smallest concept_option_id wins.  This
guarantees fully deterministic output across processes and deployments.

Delta values
------------
  <metric>_delta_vs_best = row.<metric> - best_<metric>

Deltas are zero for the best option and negative for all others.
When a metric value is None the delta is also None.

PR-CONCEPT-053
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Input dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConceptOptionComparisonInput:
    """Immutable snapshot of a single concept option for comparison."""

    concept_option_id: str
    name: str
    status: str
    unit_count: int
    sellable_area: Optional[float]
    efficiency_ratio: Optional[float]
    average_unit_area: Optional[float]
    building_count: Optional[int]
    floor_count: Optional[int]


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ConceptOptionComparisonRow:
    """Enriched comparison row for a single concept option."""

    concept_option_id: str
    name: str
    status: str
    unit_count: int
    sellable_area: Optional[float]
    efficiency_ratio: Optional[float]
    average_unit_area: Optional[float]
    building_count: Optional[int]
    floor_count: Optional[int]
    # Delta vs best
    sellable_area_delta_vs_best: Optional[float]
    efficiency_delta_vs_best: Optional[float]
    unit_count_delta_vs_best: int
    # Best-option flags
    is_best_sellable_area: bool
    is_best_efficiency: bool
    is_best_unit_count: bool


@dataclass
class ConceptOptionComparisonResult:
    """Full comparison result for a project or scenario basis."""

    comparison_basis: str  # "project" | "scenario"
    option_count: int
    best_sellable_area_option_id: Optional[str]
    best_efficiency_option_id: Optional[str]
    best_unit_count_option_id: Optional[str]
    rows: List[ConceptOptionComparisonRow] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Comparison logic helpers
# ---------------------------------------------------------------------------


def _best_by_sellable_area(
    options: List[ConceptOptionComparisonInput],
) -> Optional[str]:
    """Return the concept_option_id with the highest sellable_area.

    Options with None sellable_area are excluded.  Returns None when all
    options have None sellable_area.  Ties are broken by the
    lexicographically-smallest concept_option_id.
    """
    candidates = [o for o in options if o.sellable_area is not None]
    if not candidates:
        return None
    winner = sorted(candidates, key=lambda o: (-o.sellable_area, o.concept_option_id))[0]  # type: ignore[operator]
    return winner.concept_option_id


def _best_by_efficiency(
    options: List[ConceptOptionComparisonInput],
) -> Optional[str]:
    """Return the concept_option_id with the highest efficiency_ratio.

    Ties are broken by the lexicographically-smallest concept_option_id.
    """
    candidates = [o for o in options if o.efficiency_ratio is not None]
    if not candidates:
        return None
    winner = sorted(candidates, key=lambda o: (-o.efficiency_ratio, o.concept_option_id))[0]  # type: ignore[operator]
    return winner.concept_option_id


def _best_by_unit_count(
    options: List[ConceptOptionComparisonInput],
) -> Optional[str]:
    """Return the concept_option_id with the highest unit_count.

    Ties are broken by the lexicographically-smallest concept_option_id.
    """
    if not options:
        return None
    winner = sorted(options, key=lambda o: (-o.unit_count, o.concept_option_id))[0]
    return winner.concept_option_id


# ---------------------------------------------------------------------------
# Public comparison function
# ---------------------------------------------------------------------------


def compute_concept_comparison(
    options: List[ConceptOptionComparisonInput],
    comparison_basis: str,
) -> ConceptOptionComparisonResult:
    """Build a structured side-by-side comparison from a list of option inputs.

    Parameters
    ----------
    options:
        List of :class:`ConceptOptionComparisonInput` snapshots, usually
        ordered by concept_option_id ascending for determinism.
    comparison_basis:
        Either ``"project"`` or ``"scenario"``.

    Returns
    -------
    ConceptOptionComparisonResult
        Complete comparison with per-row deltas and best-option flags.
        Returns an empty result when *options* is empty.
    """
    if not options:
        return ConceptOptionComparisonResult(
            comparison_basis=comparison_basis,
            option_count=0,
            best_sellable_area_option_id=None,
            best_efficiency_option_id=None,
            best_unit_count_option_id=None,
            rows=[],
        )

    best_sellable_id = _best_by_sellable_area(options)
    best_efficiency_id = _best_by_efficiency(options)
    best_unit_count_id = _best_by_unit_count(options)

    # Resolve best metric values for delta computation
    best_sellable: Optional[float] = None
    best_efficiency: Optional[float] = None
    best_unit_count: int = 0

    if best_sellable_id is not None:
        best_opt = next(o for o in options if o.concept_option_id == best_sellable_id)
        best_sellable = best_opt.sellable_area

    if best_efficiency_id is not None:
        best_opt = next(o for o in options if o.concept_option_id == best_efficiency_id)
        best_efficiency = best_opt.efficiency_ratio

    if best_unit_count_id is not None:
        best_opt = next(o for o in options if o.concept_option_id == best_unit_count_id)
        best_unit_count = best_opt.unit_count

    rows: List[ConceptOptionComparisonRow] = []
    for opt in options:
        sellable_delta: Optional[float] = (
            opt.sellable_area - best_sellable  # type: ignore[operator]
            if opt.sellable_area is not None and best_sellable is not None
            else None
        )
        efficiency_delta: Optional[float] = (
            opt.efficiency_ratio - best_efficiency  # type: ignore[operator]
            if opt.efficiency_ratio is not None and best_efficiency is not None
            else None
        )
        unit_count_delta: int = opt.unit_count - best_unit_count

        rows.append(
            ConceptOptionComparisonRow(
                concept_option_id=opt.concept_option_id,
                name=opt.name,
                status=opt.status,
                unit_count=opt.unit_count,
                sellable_area=opt.sellable_area,
                efficiency_ratio=opt.efficiency_ratio,
                average_unit_area=opt.average_unit_area,
                building_count=opt.building_count,
                floor_count=opt.floor_count,
                sellable_area_delta_vs_best=sellable_delta,
                efficiency_delta_vs_best=efficiency_delta,
                unit_count_delta_vs_best=unit_count_delta,
                is_best_sellable_area=opt.concept_option_id == best_sellable_id,
                is_best_efficiency=opt.concept_option_id == best_efficiency_id,
                is_best_unit_count=opt.concept_option_id == best_unit_count_id,
            )
        )

    return ConceptOptionComparisonResult(
        comparison_basis=comparison_basis,
        option_count=len(options),
        best_sellable_area_option_id=best_sellable_id,
        best_efficiency_option_id=best_efficiency_id,
        best_unit_count_option_id=best_unit_count_id,
        rows=rows,
    )
