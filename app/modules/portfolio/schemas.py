"""
portfolio.schemas

Typed Pydantic response contracts for the Portfolio Intelligence dashboard.

All schemas are read-only response models — no request/create schemas exist
because the portfolio layer is a read-only aggregation surface.

Schema hierarchy:
  PortfolioSummary           — top-line portfolio KPIs
  PortfolioProjectCard       — per-project snapshot card
  PortfolioPipelineSummary   — scenario / feasibility pipeline signals
  PortfolioCollectionsSummary — collections health overview
  PortfolioRiskFlag          — individual risk / alert item
  PortfolioDashboardResponse — top-level envelope returned by the dashboard endpoint
"""

from typing import List, Optional

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
    contracted_revenue: float = Field(
        ..., description="Sum of contract_price for all non-cancelled sales contracts (AED)"
    )
    collected_cash: float = Field(
        ..., description="Sum of amount_paid across all receivables (AED)"
    )
    outstanding_balance: float = Field(
        ..., description="Sum of balance_due across all open receivables (AED)"
    )


class PortfolioProjectCard(BaseModel):
    """Snapshot card for a single project, suitable for a portfolio grid view."""

    project_id: str
    project_name: str
    project_code: str
    status: str
    total_units: int
    available_units: int
    reserved_units: int
    under_contract_units: int
    registered_units: int
    contracted_revenue: float = Field(
        ..., description="Contracted revenue for this project (AED)"
    )
    collected_cash: float = Field(
        ..., description="Cash collected for this project (AED)"
    )
    outstanding_balance: float = Field(
        ..., description="Outstanding receivable balance for this project (AED)"
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
    overdue_balance: float = Field(
        ..., description="Sum of balance_due for overdue receivables (AED)"
    )
    collection_rate_pct: Optional[float] = Field(
        None,
        description=(
            "amount_paid / (amount_paid + balance_due) expressed as a percentage; "
            "null when no receivables exist"
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
