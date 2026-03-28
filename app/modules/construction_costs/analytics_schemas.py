"""
construction_costs.analytics_schemas

Pydantic response schemas for the Construction Analytics & Project Scorecard
layer (PR-V6-14).

Schema families
---------------
ConstructionProjectScorecardResponse   — full project scorecard payload.
ConstructionPortfolioScorecardItem     — per-project summary for portfolio view.
ConstructionPortfolioScorecardsResponse — top-level portfolio envelope.

Health status values
--------------------
  "healthy"    — all key metrics within acceptable thresholds.
  "warning"    — one or more metrics exceed warning thresholds.
  "critical"   — one or more metrics exceed critical thresholds.
  "incomplete" — no approved baseline exists; scorecard cannot be finalised.

Classification thresholds (documented for traceability)
  cost_status:
    healthy   → cost_variance_pct ≤ 5 % (or negative — under budget)
    warning   → 5 % < cost_variance_pct ≤ 15 %
    critical  → cost_variance_pct > 15 %
  contingency_status:
    healthy   → contingency_pressure_pct ≤ 10 %
    warning   → 10 % < contingency_pressure_pct ≤ 25 %
    critical  → contingency_pressure_pct > 25 %
  overall_health_status:
    incomplete → has_approved_baseline is False
    critical   → any component is critical
    warning    → any component is warning
    healthy    → all components are healthy
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Controlled health status values
# ---------------------------------------------------------------------------

HealthStatus = str  # "healthy" | "warning" | "critical" | "incomplete"


# ---------------------------------------------------------------------------
# Project-level scorecard
# ---------------------------------------------------------------------------


class ConstructionProjectScorecardResponse(BaseModel):
    """Complete construction health scorecard for a single project.

    All monetary values are Decimal serialised as strings by FastAPI,
    consistent with the platform Decimal field convention.

    When has_approved_baseline is False the scorecard fields that depend on
    the baseline are None and overall_health_status is "incomplete".
    """

    project_id: str = Field(..., description="Project identifier")
    project_name: str = Field(..., description="Human-readable project name")

    # ── Baseline context ──────────────────────────────────────────────────────
    has_approved_baseline: bool = Field(
        ...,
        description="True when an approved tender baseline exists for this project",
    )
    approved_baseline_set_id: Optional[str] = Field(
        None, description="ID of the approved baseline comparison set"
    )
    approved_baseline_amount: Optional[Decimal] = Field(
        None,
        description=(
            "Total comparison amount from the approved baseline set lines (AED). "
            "None when has_approved_baseline is False."
        ),
    )
    approved_at: Optional[datetime] = Field(
        None, description="Timestamp when the baseline was approved"
    )

    # ── Current forecast (from active construction cost records) ──────────────
    current_forecast_amount: Decimal = Field(
        ...,
        description="Sum of all active construction cost records for this project (AED)",
    )

    # ── Cost variance ─────────────────────────────────────────────────────────
    cost_variance_amount: Optional[Decimal] = Field(
        None,
        description=(
            "Absolute cost variance (current_forecast - approved_baseline). "
            "Positive → overrun; negative → saving. "
            "None when has_approved_baseline is False."
        ),
    )
    cost_variance_pct: Optional[Decimal] = Field(
        None,
        description=(
            "Cost variance as a percentage of approved_baseline_amount. "
            "None when baseline is zero or has_approved_baseline is False."
        ),
    )
    cost_status: HealthStatus = Field(
        ...,
        description="'healthy' | 'warning' | 'critical' | 'incomplete'",
    )

    # ── Contingency ───────────────────────────────────────────────────────────
    contingency_amount: Decimal = Field(
        ...,
        description=(
            "Sum of active construction cost records with category 'contingency' (AED)"
        ),
    )
    contingency_pressure_pct: Optional[Decimal] = Field(
        None,
        description=(
            "Contingency amount as a percentage of approved_baseline_amount. "
            "None when baseline is zero or has_approved_baseline is False."
        ),
    )
    contingency_status: HealthStatus = Field(
        ...,
        description="'healthy' | 'warning' | 'critical' | 'incomplete'",
    )

    # ── Overall health ────────────────────────────────────────────────────────
    overall_health_status: HealthStatus = Field(
        ...,
        description="'healthy' | 'warning' | 'critical' | 'incomplete'",
    )

    # ── Metadata ─────────────────────────────────────────────────────────────
    last_updated_at: Optional[datetime] = Field(
        None,
        description=(
            "Most recent update timestamp from cost records or baseline approval, "
            "whichever is later."
        ),
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Portfolio-level scorecard item
# ---------------------------------------------------------------------------


class ConstructionPortfolioScorecardItem(BaseModel):
    """Compact construction health summary for one project within a portfolio view."""

    project_id: str
    project_name: str
    has_approved_baseline: bool
    approved_baseline_amount: Optional[Decimal]
    current_forecast_amount: Decimal
    cost_variance_amount: Optional[Decimal]
    cost_variance_pct: Optional[Decimal]
    contingency_amount: Decimal
    contingency_pressure_pct: Optional[Decimal]
    overall_health_status: HealthStatus


# ---------------------------------------------------------------------------
# Portfolio construction scorecard summary
# ---------------------------------------------------------------------------


class ConstructionPortfolioScorecardSummary(BaseModel):
    """Aggregate counts and totals across all project construction scorecards."""

    total_projects_scored: int = Field(
        ..., description="Total number of projects included in this scorecard roll-up"
    )
    healthy_count: int = Field(
        ..., description="Projects with overall_health_status == 'healthy'"
    )
    warning_count: int = Field(
        ..., description="Projects with overall_health_status == 'warning'"
    )
    critical_count: int = Field(
        ..., description="Projects with overall_health_status == 'critical'"
    )
    incomplete_count: int = Field(
        ...,
        description=(
            "Projects with overall_health_status == 'incomplete' "
            "(no approved baseline)"
        ),
    )
    projects_missing_baseline: int = Field(
        ..., description="Alias for incomplete_count; projects without an approved baseline"
    )


# ---------------------------------------------------------------------------
# Top-level portfolio response
# ---------------------------------------------------------------------------


class ConstructionPortfolioScorecardsResponse(BaseModel):
    """Top-level portfolio construction scorecard response envelope.

    Provides aggregate health summary, per-project scorecard items, and
    prioritised lists for triage.  All values are computed live on every
    request from source records — no data is persisted or cached.
    """

    summary: ConstructionPortfolioScorecardSummary
    projects: List[ConstructionPortfolioScorecardItem] = Field(
        default_factory=list,
        description="All project scorecards, ordered by overall_health_status severity then cost_variance_pct descending",
    )
    top_risk_projects: List[ConstructionPortfolioScorecardItem] = Field(
        default_factory=list,
        description="Projects requiring executive attention (critical or warning status), ordered by cost_variance_pct descending",
    )
    missing_baseline_projects: List[ConstructionPortfolioScorecardItem] = Field(
        default_factory=list,
        description="Projects that have no approved baseline (incomplete state)",
    )
