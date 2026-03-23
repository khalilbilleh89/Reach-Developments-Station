"""
finance.construction_financing_engine

Construction Financing & Draw Schedule Engine for the Financial Control layer.

This module is a pure calculation engine — no SQL, no HTTP, no side effects.
All input data is provided by the service layer; all outputs are plain Python
data objects returned to the service layer for response serialisation.

Financing model
---------------
For each construction cashflow period::

    debt_draw            = period_cost × debt_ratio
    equity_contribution  = period_cost × equity_ratio
    cumulative_debt      = running total of debt_draw
    cumulative_equity    = running total of equity_contribution

Capital stack:

    debt_ratio + equity_ratio must equal 1.0  (enforced by caller assumptions)

Default (pro-rata) draw method:

* Each period's cost is split into debt and equity contributions based on the
  capital stack ratios.
* financing_probability scales the period cost before allocation, enabling
  probabilistic financing models.
* financing_start_offset delays the first period in which financing begins
  (0 = financing starts immediately from period 0).

Architecture note
-----------------
All derived construction financing values live here.  No formula duplication
in routers or UI components is permitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.modules.finance.constants import (
    DEFAULT_DEBT_RATIO,
    DEFAULT_EQUITY_RATIO,
    DEFAULT_FINANCING_PROBABILITY,
    DEFAULT_FINANCING_START_OFFSET,
    ConstructionEquityInjectionMethod,
    ConstructionLoanDrawMethod,
)
from app.modules.finance.construction_cashflow_engine import ConstructionCashflowPeriodResult


# ---------------------------------------------------------------------------
# Input data transfer objects
# ---------------------------------------------------------------------------


@dataclass
class ConstructionFinancingAssumptions:
    """User-controlled construction financing assumption parameters.

    Attributes
    ----------
    debt_ratio:
        Proportion of each period's construction cost funded by debt (0–1).
        Default 0.60.
    equity_ratio:
        Proportion of each period's construction cost funded by equity (0–1).
        Default 0.40.  debt_ratio + equity_ratio should equal 1.0.
    loan_draw_method:
        Method used to determine how debt drawdowns are scheduled.
        Default PRO_RATA.
    equity_injection_method:
        Method used to determine how equity contributions are scheduled.
        Default PRO_RATA.
    financing_start_offset:
        Number of periods (months) from period index 0 before financing begins.
        Default 0 (financing begins in the first period).
    financing_probability:
        Probability (0–1) that financing will be required in each period.
        Scales period costs before debt/equity allocation.  Default 1.0.
    """

    debt_ratio: float = DEFAULT_DEBT_RATIO
    equity_ratio: float = DEFAULT_EQUITY_RATIO
    loan_draw_method: str = ConstructionLoanDrawMethod.PRO_RATA.value
    equity_injection_method: str = ConstructionEquityInjectionMethod.PRO_RATA.value
    financing_start_offset: int = DEFAULT_FINANCING_START_OFFSET
    financing_probability: float = DEFAULT_FINANCING_PROBABILITY


# ---------------------------------------------------------------------------
# Output data transfer objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstructionDrawPeriodResult:
    """Financing activity for a single calendar-month period."""

    period_label: str  # YYYY-MM

    period_cost: float  # construction cost for this period (expected_cost basis)
    debt_draw: float  # debt drawdown allocated to this period
    equity_contribution: float  # equity injection allocated to this period
    cumulative_debt: float  # running cumulative debt drawn up to this period
    cumulative_equity: float  # running cumulative equity contributed up to this period


@dataclass(frozen=True)
class ConstructionDrawScheduleSummary:
    """Aggregated financing summary across all periods."""

    total_cost: float  # sum of period_cost across all periods
    total_debt: float  # sum of debt_draw across all periods
    total_equity: float  # sum of equity_contribution across all periods
    debt_to_cost_ratio: float  # total_debt / total_cost (0 if total_cost == 0)
    equity_to_cost_ratio: float  # total_equity / total_cost (0 if total_cost == 0)


@dataclass
class ProjectConstructionFinancingResult:
    """Complete construction financing draw schedule for a project or phase."""

    scope_type: str  # "project" | "phase"
    scope_id: str  # project_id or phase_id
    summary: ConstructionDrawScheduleSummary
    periods: List[ConstructionDrawPeriodResult] = field(default_factory=list)


@dataclass
class PortfolioConstructionFinancingResult:
    """Construction financing draw schedule aggregated across multiple projects."""

    scope_type: str  # "portfolio"
    summary: ConstructionDrawScheduleSummary
    periods: List[ConstructionDrawPeriodResult] = field(default_factory=list)
    project_results: List[ProjectConstructionFinancingResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core engine functions
# ---------------------------------------------------------------------------


def compute_project_construction_financing(
    project_id: str,
    cashflow_periods: List[ConstructionCashflowPeriodResult],
    assumptions: Optional[ConstructionFinancingAssumptions] = None,
) -> ProjectConstructionFinancingResult:
    """Compute the construction financing draw schedule for a single project.

    Parameters
    ----------
    project_id:
        Identifier of the project being financed.
    cashflow_periods:
        Period-by-period construction cashflow results from the cashflow engine.
        Each period's expected_cost is used as the financing basis.
    assumptions:
        Financing assumption parameters.  Defaults to 60/40 pro-rata split.

    Returns
    -------
    ProjectConstructionFinancingResult
        Period-by-period debt/equity draw schedule plus summary totals.
    """
    if assumptions is None:
        assumptions = ConstructionFinancingAssumptions()

    periods, summary = _compute_draw_periods_and_summary(cashflow_periods, assumptions)

    return ProjectConstructionFinancingResult(
        scope_type="project",
        scope_id=project_id,
        summary=summary,
        periods=periods,
    )


def compute_phase_construction_financing(
    phase_id: str,
    cashflow_periods: List[ConstructionCashflowPeriodResult],
    assumptions: Optional[ConstructionFinancingAssumptions] = None,
) -> ProjectConstructionFinancingResult:
    """Compute the construction financing draw schedule for a single phase.

    Parameters
    ----------
    phase_id:
        Identifier of the phase being financed.
    cashflow_periods:
        Period-by-period construction cashflow results from the cashflow engine.
    assumptions:
        Financing assumption parameters.  Defaults to 60/40 pro-rata split.

    Returns
    -------
    ProjectConstructionFinancingResult
        Period-by-period debt/equity draw schedule plus summary totals.
        scope_type will be "phase".
    """
    if assumptions is None:
        assumptions = ConstructionFinancingAssumptions()

    periods, summary = _compute_draw_periods_and_summary(cashflow_periods, assumptions)

    return ProjectConstructionFinancingResult(
        scope_type="phase",
        scope_id=phase_id,
        summary=summary,
        periods=periods,
    )


def compute_portfolio_construction_financing(
    project_cashflow_periods: Dict[str, List[ConstructionCashflowPeriodResult]],
    assumptions: Optional[ConstructionFinancingAssumptions] = None,
) -> PortfolioConstructionFinancingResult:
    """Compute the construction financing draw schedule across multiple projects.

    Parameters
    ----------
    project_cashflow_periods:
        Mapping of project_id → list of ConstructionCashflowPeriodResult.
    assumptions:
        Financing assumption parameters shared across all projects.

    Returns
    -------
    PortfolioConstructionFinancingResult
        Per-project draw schedules plus combined portfolio-level totals.
    """
    if assumptions is None:
        assumptions = ConstructionFinancingAssumptions()

    # Compute individual project results (sorted for determinism).
    project_results: List[ProjectConstructionFinancingResult] = [
        compute_project_construction_financing(pid, periods, assumptions)
        for pid, periods in sorted(project_cashflow_periods.items())
    ]

    # Merge per-project period data into portfolio-level buckets.
    merged: Dict[str, tuple[float, float, float]] = {}  # label → (cost, debt, equity)
    for pr in project_results:
        for period in pr.periods:
            label = period.period_label
            if label not in merged:
                merged[label] = (0.0, 0.0, 0.0)
            c, d, e = merged[label]
            merged[label] = (
                c + period.period_cost,
                d + period.debt_draw,
                e + period.equity_contribution,
            )

    # Build portfolio periods in sorted label order with cumulative tracking.
    portfolio_periods: List[ConstructionDrawPeriodResult] = []
    cumulative_debt = 0.0
    cumulative_equity = 0.0
    for label in sorted(merged.keys()):
        cost, debt, equity = merged[label]
        cost = round(cost, 2)
        debt = round(debt, 2)
        equity = round(equity, 2)
        cumulative_debt = round(cumulative_debt + debt, 2)
        cumulative_equity = round(cumulative_equity + equity, 2)
        portfolio_periods.append(
            ConstructionDrawPeriodResult(
                period_label=label,
                period_cost=cost,
                debt_draw=debt,
                equity_contribution=equity,
                cumulative_debt=cumulative_debt,
                cumulative_equity=cumulative_equity,
            )
        )

    summary = _build_summary(portfolio_periods)

    return PortfolioConstructionFinancingResult(
        scope_type="portfolio",
        summary=summary,
        periods=portfolio_periods,
        project_results=project_results,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_draw_periods_and_summary(
    cashflow_periods: List[ConstructionCashflowPeriodResult],
    assumptions: ConstructionFinancingAssumptions,
) -> tuple[List[ConstructionDrawPeriodResult], ConstructionDrawScheduleSummary]:
    """Distribute cashflow period costs into debt and equity contributions.

    Parameters
    ----------
    cashflow_periods:
        Ordered list of construction cashflow period results.  The
        expected_cost field is used as the financing basis.
    assumptions:
        Financing parameters controlling the debt/equity split and timing.

    Returns
    -------
    tuple[List[ConstructionDrawPeriodResult], ConstructionDrawScheduleSummary]
    """
    periods: List[ConstructionDrawPeriodResult] = []
    cumulative_debt = 0.0
    cumulative_equity = 0.0

    for idx, cp in enumerate(cashflow_periods):
        # Periods before the financing start offset receive no financing.
        if idx < assumptions.financing_start_offset:
            periods.append(
                ConstructionDrawPeriodResult(
                    period_label=cp.period_label,
                    period_cost=round(cp.expected_cost, 2),
                    debt_draw=0.0,
                    equity_contribution=0.0,
                    cumulative_debt=round(cumulative_debt, 2),
                    cumulative_equity=round(cumulative_equity, 2),
                )
            )
            continue

        # Scale cost by financing probability.
        financed_cost = round(cp.expected_cost * assumptions.financing_probability, 2)

        debt_draw = round(financed_cost * assumptions.debt_ratio, 2)
        equity_contribution = round(financed_cost * assumptions.equity_ratio, 2)

        cumulative_debt = round(cumulative_debt + debt_draw, 2)
        cumulative_equity = round(cumulative_equity + equity_contribution, 2)

        periods.append(
            ConstructionDrawPeriodResult(
                period_label=cp.period_label,
                period_cost=round(cp.expected_cost, 2),
                debt_draw=debt_draw,
                equity_contribution=equity_contribution,
                cumulative_debt=cumulative_debt,
                cumulative_equity=cumulative_equity,
            )
        )

    summary = _build_summary(periods)
    return periods, summary


def _build_summary(
    periods: List[ConstructionDrawPeriodResult],
) -> ConstructionDrawScheduleSummary:
    """Derive summary totals from a list of draw period results."""
    total_cost = round(sum(p.period_cost for p in periods), 2)
    total_debt = round(sum(p.debt_draw for p in periods), 2)
    total_equity = round(sum(p.equity_contribution for p in periods), 2)
    debt_to_cost_ratio = round(total_debt / total_cost, 6) if total_cost > 0 else 0.0
    equity_to_cost_ratio = round(total_equity / total_cost, 6) if total_cost > 0 else 0.0
    return ConstructionDrawScheduleSummary(
        total_cost=total_cost,
        total_debt=total_debt,
        total_equity=total_equity,
        debt_to_cost_ratio=debt_to_cost_ratio,
        equity_to_cost_ratio=equity_to_cost_ratio,
    )
