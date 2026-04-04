"""
portfolio.schemas

Typed Pydantic response contracts for the Portfolio Intelligence dashboard.

All schemas are read-only response models — no request/create schemas exist
because the portfolio layer is a read-only aggregation surface.

Schema hierarchy:
  PortfolioSummary              — top-line portfolio KPIs
  PortfolioProjectCard          — per-project snapshot card
  PortfolioPipelineSummary      — scenario / feasibility pipeline signals
  PortfolioCollectionsSummary   — collections health overview
  PortfolioRiskFlag             — individual risk / alert item
  PortfolioDashboardResponse    — top-level envelope returned by the dashboard endpoint

  PortfolioCostVarianceSummary        — portfolio-wide cost variance totals
  PortfolioCostVarianceProjectCard    — per-project cost variance snapshot
  PortfolioCostVarianceFlag           — portfolio-level cost variance signals
  PortfolioCostVarianceResponse       — top-level cost variance envelope
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PortfolioSummary(BaseModel):
    """Top-line portfolio KPI strip."""

    total_projects: int = Field(..., description="Total number of projects in the portfolio")
    active_projects: int = Field(..., description="Projects with status 'active'")
    total_units: int = Field(..., description="Total inventory units across all projects")
    available_units: int = Field(..., description="Units with status 'available'")
    reserved_units: int = Field(..., description="Units with status 'reserved'")
    under_contract_units: int = Field(..., description="Units with status 'under_contract'")
    registered_units: int = Field(..., description="Units with status 'registered'")
    contracted_revenue: Dict[str, float] = Field(
        ...,
        description=(
            "Sum of contract_price for all non-cancelled sales contracts, "
            "grouped by currency code (e.g. {\"AED\": 1200000.0, \"USD\": 500000.0})"
        ),
    )
    collected_cash: Dict[str, float] = Field(
        ...,
        description="Sum of amount_paid across all receivables, grouped by currency code",
    )
    outstanding_balance: Dict[str, float] = Field(
        ...,
        description="Sum of balance_due across all open receivables, grouped by currency code",
    )


class PortfolioProjectCard(BaseModel):
    """Snapshot card for a single project, suitable for a portfolio grid view."""

    project_id: str
    project_name: str
    project_code: str
    status: str
    currency: str = Field(..., description="Project base currency (denomination of all monetary fields)")
    total_units: int
    available_units: int
    reserved_units: int
    under_contract_units: int
    registered_units: int
    contracted_revenue: float = Field(
        ...,
        description="Contracted revenue for this project (denominated in currency)",
    )
    collected_cash: float = Field(
        ..., description="Cash collected for this project (denominated in currency)"
    )
    outstanding_balance: float = Field(
        ..., description="Outstanding receivable balance for this project (denominated in currency)"
    )
    sell_through_pct: Optional[float] = Field(
        None,
        description="Percentage of units sold (under_contract + registered) out of total units",
    )
    health_badge: Optional[str] = Field(
        None,
        description="Simple health indicator: 'on_track' | 'needs_attention' | 'at_risk'",
    )


class PortfolioPipelineSummary(BaseModel):
    """Scenario and feasibility pipeline signals."""

    total_scenarios: int = Field(..., description="Total scenarios in the system")
    approved_scenarios: int = Field(..., description="Scenarios with status 'approved'")
    total_feasibility_runs: int = Field(..., description="Total feasibility runs")
    calculated_feasibility_runs: int = Field(
        ..., description="Feasibility runs with status 'calculated'"
    )
    projects_with_no_feasibility: int = Field(
        ..., description="Projects that have zero feasibility runs"
    )


class PortfolioCollectionsSummary(BaseModel):
    """Collections health overview."""

    total_receivables: int = Field(..., description="Total receivable records")
    overdue_receivables: int = Field(
        ..., description="Receivables with status 'overdue'"
    )
    overdue_balance: Dict[str, float] = Field(
        ...,
        description=(
            "Sum of balance_due for overdue receivables, grouped by currency code "
            "(e.g. {\"AED\": 50000.0})"
        ),
    )
    collection_rate_pct: Optional[float] = Field(
        None,
        description=(
            "Portfolio-wide collection rate: amount_paid / (amount_paid + balance_due) "
            "expressed as a percentage; "
            "null when no receivables exist or when receivables span multiple currencies "
            "(cross-currency summing is invalid without FX conversion)"
        ),
    )


class PortfolioRiskFlag(BaseModel):
    """A single risk or alert signal derived from source data."""

    flag_type: str = Field(
        ...,
        description=(
            "Machine-readable flag type: "
            "'overdue_receivables' | 'low_sell_through' | 'low_collections'"
        ),
    )
    severity: str = Field(
        ..., description="'warning' | 'critical'"
    )
    description: str = Field(..., description="Human-readable description of the risk")
    affected_project_id: Optional[str] = Field(
        None, description="Project ID if the flag is project-scoped"
    )
    affected_project_name: Optional[str] = Field(
        None, description="Project name if the flag is project-scoped"
    )


class PortfolioDashboardResponse(BaseModel):
    """Top-level dashboard response envelope.

    All sections are populated from live source data on every request.
    Sections may be empty (empty list / zero values) when source data is absent.
    """

    summary: PortfolioSummary
    projects: List[PortfolioProjectCard] = Field(
        default_factory=list, description="Per-project snapshot cards"
    )
    pipeline: PortfolioPipelineSummary
    collections: PortfolioCollectionsSummary
    risk_flags: List[PortfolioRiskFlag] = Field(
        default_factory=list, description="Portfolio-level risk/alert signals"
    )


# ---------------------------------------------------------------------------
# Portfolio Cost Variance Roll-Up schemas (PR-V6-12)
# ---------------------------------------------------------------------------


class PortfolioCostVarianceSummary(BaseModel):
    """Portfolio-wide cost variance totals derived from active tender comparison sets."""

    projects_with_comparison_sets: int = Field(
        ..., description="Number of projects that have at least one active comparison set"
    )
    total_baseline_amount: Dict[str, float] = Field(
        ...,
        description=(
            "Sum of all baseline amounts across active comparison lines, "
            "grouped by currency code (e.g. {\"AED\": 1000000.0})"
        ),
    )
    total_comparison_amount: Dict[str, float] = Field(
        ...,
        description=(
            "Sum of all comparison amounts across active comparison lines, "
            "grouped by currency code"
        ),
    )
    total_variance_amount: Dict[str, float] = Field(
        ...,
        description=(
            "Total variance amount (comparison - baseline) across active comparison lines, "
            "grouped by currency code. "
            "Positive → net overrun; negative → net saving."
        ),
    )
    total_variance_pct: Dict[str, Optional[float]] = Field(
        default_factory=dict,
        description=(
            "Total variance as a percentage of total baseline, grouped by currency code; "
            "per-currency value is null when that currency's baseline is zero."
        ),
    )


class PortfolioCostVarianceProjectCard(BaseModel):
    """Per-project cost variance snapshot derived from active tender comparison sets."""

    project_id: str
    project_name: str
    currency: str = Field(
        ..., description="Project base currency (denomination of all monetary fields)"
    )
    comparison_set_count: int = Field(
        ..., description="Number of active comparison sets for this project"
    )
    latest_comparison_stage: Optional[str] = Field(
        None, description="Stage of the most recently created active comparison set"
    )
    baseline_total: float = Field(
        ...,
        description="Sum of baseline amounts across all active comparison lines (denominated in currency)",
    )
    comparison_total: float = Field(
        ...,
        description="Sum of comparison amounts across all active comparison lines (denominated in currency)",
    )
    variance_amount: float = Field(
        ...,
        description=(
            "Net variance (comparison - baseline) across all active comparison lines "
            "(denominated in currency). Positive → overrun; negative → saving."
        ),
    )
    variance_pct: Optional[float] = Field(
        None,
        description="Variance as percentage of baseline; null when baseline is zero",
    )
    variance_status: str = Field(
        ...,
        description=(
            "Transparent status derived from variance_amount: "
            "'overrun' (positive) | 'saving' (negative) | 'neutral' (zero)"
        ),
    )


class PortfolioCostVarianceFlag(BaseModel):
    """A cost-variance-specific signal derived from portfolio comparison data."""

    flag_type: str = Field(
        ...,
        description=(
            "Machine-readable flag type: "
            "'major_overrun' | 'major_saving' | 'missing_comparison_data'"
        ),
    )
    description: str = Field(..., description="Human-readable description of the signal")
    affected_project_id: Optional[str] = Field(
        None, description="Project ID if project-scoped"
    )
    affected_project_name: Optional[str] = Field(
        None, description="Project name if project-scoped"
    )


class PortfolioCostVarianceResponse(BaseModel):
    """Top-level cost variance roll-up response envelope.

    Aggregates tender comparison data across projects into a portfolio-level
    cost variance view.  All values are live-read from governed comparison
    records on every request.  No source records are mutated.
    """

    summary: PortfolioCostVarianceSummary
    projects: List[PortfolioCostVarianceProjectCard] = Field(
        default_factory=list,
        description="Per-project cost variance cards, ordered by variance_amount descending",
    )
    top_overruns: List[PortfolioCostVarianceProjectCard] = Field(
        default_factory=list,
        description="Projects with the largest positive variance (overruns)",
    )
    top_savings: List[PortfolioCostVarianceProjectCard] = Field(
        default_factory=list,
        description="Projects with the largest negative variance (savings)",
    )
    flags: List[PortfolioCostVarianceFlag] = Field(
        default_factory=list,
        description="Portfolio-level cost variance signals",
    )


# ---------------------------------------------------------------------------
# Portfolio Absorption schemas (PR-V7-01)
# ---------------------------------------------------------------------------


class PortfolioAbsorptionProjectCard(BaseModel):
    """Per-project absorption snapshot for portfolio comparison."""

    project_id: str
    project_name: str
    project_code: str
    total_units: int
    sold_units: int
    sell_through_pct: Optional[float] = Field(
        None,
        description="Sold units / total units * 100; null when no units exist",
    )
    absorption_rate_per_month: Optional[float] = Field(
        None,
        description="Actual absorption rate (units/month); null when < 2 sales",
    )
    planned_absorption_rate_per_month: Optional[float] = Field(
        None,
        description="Planned rate from feasibility assumptions; null when unavailable",
    )
    absorption_vs_plan_pct: Optional[float] = Field(
        None,
        description="Actual / planned * 100; null when either rate is unavailable",
    )
    contracted_revenue: float
    absorption_status: Optional[str] = Field(
        None,
        description=(
            "Derived badge: 'ahead_of_plan' | 'on_plan' | 'behind_plan' | 'no_data'; "
            "null when no units exist"
        ),
    )


class PortfolioAbsorptionSummary(BaseModel):
    """Portfolio-wide absorption aggregates."""

    total_projects: int
    projects_with_absorption_data: int = Field(
        ...,
        description="Projects that have at least 2 contracts (rate calculable)",
    )
    portfolio_avg_sell_through_pct: Optional[float] = Field(
        None,
        description="Average sell-through across all projects with units",
    )
    portfolio_avg_absorption_rate: Optional[float] = Field(
        None,
        description="Average absorption rate across projects where it can be calculated",
    )
    projects_ahead_of_plan: int
    projects_on_plan: int
    projects_behind_plan: int
    projects_no_absorption_data: int


class PortfolioAbsorptionResponse(BaseModel):
    """Portfolio absorption aggregation response (PR-V7-01)."""

    summary: PortfolioAbsorptionSummary
    projects: List[PortfolioAbsorptionProjectCard] = Field(
        ...,
        description="Per-project absorption cards ordered by sell-through descending",
    )
    fastest_projects: List[PortfolioAbsorptionProjectCard] = Field(
        ...,
        description="Top 5 projects by absorption rate",
    )
    slowest_projects: List[PortfolioAbsorptionProjectCard] = Field(
        ...,
        description="Bottom 5 projects by absorption rate (excluding no-data projects)",
    )
    below_plan_projects: List[PortfolioAbsorptionProjectCard] = Field(
        ...,
        description="Projects with absorption_vs_plan_pct < 80% (below plan threshold)",
    )


# ---------------------------------------------------------------------------
# Portfolio Construction Scorecards schemas (PR-V6-14)
# Re-export the canonical schemas from construction_costs.analytics_schemas
# so that the portfolio API surface has a single import path.
# ---------------------------------------------------------------------------

from app.modules.construction_costs.analytics_schemas import (  # noqa: E402
    ConstructionPortfolioScorecardItem,
    ConstructionPortfolioScorecardSummary,
    ConstructionPortfolioScorecardsResponse,
    ConstructionProjectScorecardResponse,
)

__all__ = [
    "PortfolioSummary",
    "PortfolioProjectCard",
    "PortfolioPipelineSummary",
    "PortfolioCollectionsSummary",
    "PortfolioRiskFlag",
    "PortfolioDashboardResponse",
    "PortfolioCostVarianceSummary",
    "PortfolioCostVarianceProjectCard",
    "PortfolioCostVarianceFlag",
    "PortfolioCostVarianceResponse",
    "PortfolioAbsorptionProjectCard",
    "PortfolioAbsorptionSummary",
    "PortfolioAbsorptionResponse",
    "ConstructionPortfolioScorecardItem",
    "ConstructionPortfolioScorecardSummary",
    "ConstructionPortfolioScorecardsResponse",
    "ConstructionProjectScorecardResponse",
]
