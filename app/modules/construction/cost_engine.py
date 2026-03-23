"""
construction.cost_engine

Pure Construction Cost Variance Engine.

Computes milestone-level cost variance by comparing planned vs actual costs.
No database access, no HTTP concerns.

Concepts
--------
cost_variance
    actual_cost − planned_cost.
    Positive = over budget.  Negative = under budget.

cost_variance_percent
    (cost_variance / planned_cost) × 100 when planned_cost > 0.
    None when planned_cost is None or zero.

project_budget
    Sum of planned_cost across all milestones that have a planned_cost.

project_actual_cost
    Sum of actual_cost across all milestones that have an actual_cost.

project_overrun_percent
    (project_actual_cost − project_budget) / project_budget × 100
    when project_budget > 0.  None otherwise.

All inputs/outputs use plain Python dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MilestoneCostData:
    """Cost data for a single milestone.

    Parameters
    ----------
    milestone_id:
        Matches ConstructionMilestone.id.
    planned_cost:
        The budgeted cost for this milestone.  None if not set.
    actual_cost:
        The actual recorded cost for this milestone.  None if not recorded.
    """

    milestone_id: str
    planned_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MilestoneCostVariance:
    """Cost variance result for a single milestone.

    Parameters
    ----------
    milestone_id:
        Matches input MilestoneCostData.milestone_id.
    planned_cost:
        As supplied in input; None if not set.
    actual_cost:
        As supplied in input; None if not recorded.
    cost_variance:
        actual_cost − planned_cost.
        None if either value is missing.
    cost_variance_percent:
        cost_variance / planned_cost × 100.
        None if planned_cost is None or zero, or cost_variance is None.
    """

    milestone_id: str
    planned_cost: Optional[Decimal]
    actual_cost: Optional[Decimal]
    cost_variance: Optional[Decimal]
    cost_variance_percent: Optional[Decimal]


@dataclass
class CostVarianceResult:
    """Aggregated cost variance result for an entire construction scope.

    Parameters
    ----------
    scope_id:
        ID of the construction scope.
    project_budget:
        Sum of planned_cost for milestones that have a planned_cost.
    project_actual_cost:
        Sum of actual_cost for milestones that have an actual_cost.
    project_cost_variance:
        project_actual_cost − project_budget.
    project_overrun_percent:
        project_cost_variance / project_budget × 100 when project_budget > 0.
        None otherwise.
    milestones:
        Per-milestone cost variance results.
    """

    scope_id: str
    project_budget: Decimal
    project_actual_cost: Decimal
    project_cost_variance: Decimal
    project_overrun_percent: Optional[Decimal]
    milestones: List[MilestoneCostVariance] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main engine entry point
# ---------------------------------------------------------------------------


def compute_cost_variance(
    scope_id: str,
    milestones: List[MilestoneCostData],
) -> CostVarianceResult:
    """Compute cost variance for a construction scope.

    Parameters
    ----------
    scope_id:
        ID of the construction scope (passed through to the result).
    milestones:
        List of :class:`MilestoneCostData` objects built from DB milestone
        records.

    Returns
    -------
    CostVarianceResult
        Per-milestone cost variance rows plus project-level cost summary.
    """
    if not milestones:
        return CostVarianceResult(
            scope_id=scope_id,
            project_budget=Decimal("0.00"),
            project_actual_cost=Decimal("0.00"),
            project_cost_variance=Decimal("0.00"),
            project_overrun_percent=None,
            milestones=[],
        )

    results: List[MilestoneCostVariance] = []
    total_planned = Decimal("0.00")
    total_actual = Decimal("0.00")

    for mc in milestones:
        planned = mc.planned_cost if mc.planned_cost is not None else None
        actual = mc.actual_cost if mc.actual_cost is not None else None

        if planned is not None:
            total_planned += planned
        if actual is not None:
            total_actual += actual

        # Compute per-milestone variance only when both values are present
        if planned is not None and actual is not None:
            variance = actual - planned
            if planned > Decimal("0.00"):
                variance_pct: Optional[Decimal] = (variance / planned * Decimal("100")).quantize(
                    Decimal("0.01")
                )
            else:
                variance_pct = None
        else:
            variance = None
            variance_pct = None

        results.append(
            MilestoneCostVariance(
                milestone_id=mc.milestone_id,
                planned_cost=planned,
                actual_cost=actual,
                cost_variance=variance,
                cost_variance_percent=variance_pct,
            )
        )

    project_variance = total_actual - total_planned

    if total_planned > Decimal("0.00"):
        overrun_pct: Optional[Decimal] = (
            project_variance / total_planned * Decimal("100")
        ).quantize(Decimal("0.01"))
    else:
        overrun_pct = None

    return CostVarianceResult(
        scope_id=scope_id,
        project_budget=total_planned,
        project_actual_cost=total_actual,
        project_cost_variance=project_variance,
        project_overrun_percent=overrun_pct,
        milestones=results,
    )
