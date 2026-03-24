"""
construction.cost_variance_engine

Pure Contractor Cost Variance Analytics Engine.

Computes contractor-level cost performance metrics from procurement package
data.  No database access, no HTTP concerns.

Metrics produced
----------------
assessed_packages
    Packages where both ``planned_cost`` and ``actual_cost`` are set.
    Only these contribute to cost variance calculations.
total_planned_cost
    Sum of ``planned_cost`` across all assessed packages.
total_actual_cost
    Sum of ``actual_cost`` across all assessed packages.
total_cost_variance
    total_actual_cost − total_planned_cost.
    Positive indicates an overrun; negative indicates under-budget delivery.
average_cost_variance_pct
    Mean (actual_cost − planned_cost) / planned_cost × 100 across
    assessed packages with a non-zero planned_cost.
    None if no such packages exist.
max_cost_overrun_pct
    Largest single-package cost overrun as a percentage.
    Only packages where actual_cost > planned_cost contribute.
    None if no package is over budget.
cost_overrun_rate
    over_budget_packages / assessed_packages.
    None if assessed_packages == 0.

Cost variance formula
---------------------
cost_variance     = actual_cost − planned_cost
cost_variance_pct = (actual_cost − planned_cost) / planned_cost × 100
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

logger = logging.getLogger("construction_cost_variance_engine")

# ---------------------------------------------------------------------------
# Input dataclass
# ---------------------------------------------------------------------------


@dataclass
class PackageCostInput:
    """Cost-relevant data for a single procurement package.

    Parameters
    ----------
    package_id:
        Matches ConstructionProcurementPackage.id.
    planned_cost:
        Budgeted value for the package (planned_value).
        None if not set.
    actual_cost:
        Awarded/actual value for the package (awarded_value).
        None if not recorded.
    """

    package_id: str
    planned_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class ContractorCostVarianceResult:
    """Computed cost variance metrics for a contractor's package portfolio.

    Parameters
    ----------
    assessed_packages:
        Count of packages with both ``planned_cost`` and ``actual_cost`` set.
    total_planned_cost:
        Sum of ``planned_cost`` across assessed packages.
    total_actual_cost:
        Sum of ``actual_cost`` across assessed packages.
    total_cost_variance:
        total_actual_cost − total_planned_cost.  Positive = overrun.
    average_cost_variance_pct:
        Mean percentage variance across assessed packages with non-zero
        planned_cost.  None if no such packages.
    max_cost_overrun_pct:
        Highest single-package overrun percentage.  None if no package
        is over budget.
    cost_overrun_rate:
        over_budget_packages / assessed_packages.  None if
        assessed_packages == 0.
    """

    assessed_packages: int = 0
    total_planned_cost: Decimal = field(default_factory=lambda: Decimal("0.00"))
    total_actual_cost: Decimal = field(default_factory=lambda: Decimal("0.00"))
    total_cost_variance: Decimal = field(default_factory=lambda: Decimal("0.00"))
    average_cost_variance_pct: Optional[float] = None
    max_cost_overrun_pct: Optional[float] = None
    cost_overrun_rate: Optional[float] = None


# ---------------------------------------------------------------------------
# Engine entry point
# ---------------------------------------------------------------------------


def compute_cost_variance(
    packages: List[PackageCostInput],
) -> ContractorCostVarianceResult:
    """Compute cost variance metrics from a list of package cost inputs.

    Parameters
    ----------
    packages:
        Package inputs to analyse.  Packages with either ``planned_cost``
        or ``actual_cost`` absent are excluded from all calculations.

    Returns
    -------
    ContractorCostVarianceResult
        Computed cost variance metrics.

        - If no packages have both cost fields set, all derived fields are
          zero or None.
        - If assessed packages exist but none are over budget,
          ``cost_overrun_rate`` is ``0.0`` and ``max_cost_overrun_pct``
          remains ``None``.
    """
    if not packages:
        return ContractorCostVarianceResult()

    assessed: List[PackageCostInput] = [
        p
        for p in packages
        if p.planned_cost is not None and p.actual_cost is not None
    ]

    if not assessed:
        logger.debug(
            "No assessed packages found — both planned_cost and actual_cost "
            "must be set for a package to contribute to cost variance."
        )
        return ContractorCostVarianceResult()

    total_planned = Decimal("0.00")
    total_actual = Decimal("0.00")
    for p in assessed:
        planned = p.planned_cost
        actual = p.actual_cost
        assert planned is not None and actual is not None
        total_planned += planned
        total_actual += actual
    total_variance = total_actual - total_planned

    over_budget_pkgs: List[PackageCostInput] = []
    for p in assessed:
        planned = p.planned_cost
        actual = p.actual_cost
        assert planned is not None and actual is not None
        if actual > planned:
            over_budget_pkgs.append(p)
    over_budget_count = len(over_budget_pkgs)
    cost_overrun_rate: Optional[float] = over_budget_count / len(assessed)

    # average_cost_variance_pct: mean % variance across packages with non-zero planned
    variance_pcts: List[float] = []
    for p in assessed:
        planned = p.planned_cost
        actual = p.actual_cost
        assert planned is not None and actual is not None
        if planned > Decimal("0"):
            variance_pcts.append(
                float((actual - planned) / planned * Decimal("100"))
            )
    average_cost_variance_pct: Optional[float] = None
    if variance_pcts:
        average_cost_variance_pct = round(sum(variance_pcts) / len(variance_pcts), 2)

    # max_cost_overrun_pct: highest single-package overrun %
    max_cost_overrun_pct: Optional[float] = None
    overrun_pcts: List[float] = []
    for p in over_budget_pkgs:
        planned = p.planned_cost
        actual = p.actual_cost
        assert planned is not None and actual is not None
        if planned > Decimal("0"):
            overrun_pcts.append(
                float((actual - planned) / planned * Decimal("100"))
            )
    if overrun_pcts:
        max_cost_overrun_pct = round(max(overrun_pcts), 2)

    return ContractorCostVarianceResult(
        assessed_packages=len(assessed),
        total_planned_cost=total_planned,
        total_actual_cost=total_actual,
        total_cost_variance=total_variance,
        average_cost_variance_pct=average_cost_variance_pct,
        max_cost_overrun_pct=max_cost_overrun_pct,
        cost_overrun_rate=cost_overrun_rate,
    )
