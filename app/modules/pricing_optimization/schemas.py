"""
pricing_optimization.schemas

Typed Pydantic response contracts for the Pricing Optimization Engine (PR-V7-02).

All schemas are read-only response models — the optimization layer produces
recommendations only and never mutates pricing data.

Schema hierarchy:
  UnitTypePricingRecommendation       — per unit-type recommendation card
  ProjectPricingRecommendationsResponse — project-level response envelope
  PortfolioPricingProjectCard         — per-project summary for portfolio view
  PortfolioPricingInsightsSummary     — portfolio-wide pricing aggregates
  PortfolioPricingInsightsResponse    — portfolio-level response envelope
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class UnitTypePricingRecommendation(BaseModel):
    """Pricing recommendation for a single unit type within a project.

    Derived from absorption metrics, unit inventory, and price data.
    No pricing records are mutated — this is a recommendation only.
    """

    unit_type: str = Field(..., description="Unit type identifier (e.g. '1BR', '2BR', 'studio')")
    current_avg_price: Optional[float] = Field(
        None,
        description=(
            "Average final_price from active (non-archived) pricing records for this unit type. "
            "Null when no formal pricing records exist."
        ),
    )
    recommended_price: Optional[float] = Field(
        None,
        description=(
            "Suggested price computed from current_avg_price * (1 + change_pct / 100). "
            "Null when current_avg_price or change_pct is unavailable."
        ),
    )
    change_pct: Optional[float] = Field(
        None,
        description=(
            "Recommended price adjustment as a percentage. "
            "Positive → increase, negative → decrease, 0 → hold. "
            "Null when demand data is insufficient."
        ),
    )
    confidence: str = Field(
        ...,
        description=(
            "Confidence level for the recommendation: "
            "'high' | 'medium' | 'low' | 'insufficient_data'"
        ),
    )
    reason: str = Field(..., description="Human-readable explanation of the recommendation")
    demand_status: str = Field(
        ...,
        description=(
            "Demand classification for this unit type: "
            "'high_demand' | 'balanced' | 'low_demand' | 'no_data'"
        ),
    )
    total_units: int = Field(..., description="Total units of this type in the project")
    available_units: int = Field(..., description="Available (unsold) units of this type")
    sold_units: int = Field(..., description="Sold units (under_contract + registered) of this type")
    availability_pct: Optional[float] = Field(
        None,
        description="available_units / total_units * 100; null when total_units is zero",
    )


class ProjectPricingRecommendationsResponse(BaseModel):
    """Project-level pricing recommendations response envelope (PR-V7-02).

    Aggregates per-unit-type pricing recommendations derived from live absorption
    and inventory data.  No pricing records are mutated.  All values are
    recommendation-only.
    """

    project_id: str
    project_name: str
    recommendations: List[UnitTypePricingRecommendation] = Field(
        default_factory=list,
        description="Per unit-type pricing recommendations ordered by unit type",
    )
    has_pricing_data: bool = Field(
        ...,
        description="True when at least one unit type has active formal pricing records",
    )
    demand_context: Optional[str] = Field(
        None,
        description=(
            "Project-level demand context note derived from absorption vs plan. "
            "Null when absorption data is unavailable."
        ),
    )


class PortfolioPricingProjectCard(BaseModel):
    """Per-project pricing intelligence summary for portfolio view."""

    project_id: str
    project_name: str
    pricing_status: str = Field(
        ...,
        description=(
            "Portfolio-level pricing direction: "
            "'underpriced' | 'overpriced' | 'balanced' | 'no_data'"
        ),
    )
    avg_recommended_adjustment_pct: Optional[float] = Field(
        None,
        description=(
            "Average recommended price adjustment across all unit types. "
            "Positive → project is underpriced; negative → overpriced. "
            "Null when no recommendations are available."
        ),
    )
    recommendation_count: int = Field(
        ..., description="Number of unit types with actionable recommendations (change_pct != 0)"
    )
    high_demand_unit_types: List[str] = Field(
        default_factory=list,
        description="Unit types classified as high_demand",
    )
    low_demand_unit_types: List[str] = Field(
        default_factory=list,
        description="Unit types classified as low_demand",
    )


class PortfolioPricingInsightsSummary(BaseModel):
    """Portfolio-wide pricing intelligence aggregates."""

    total_projects: int
    projects_with_pricing_data: int = Field(
        ..., description="Projects that have at least one unit type with formal pricing records"
    )
    avg_recommended_adjustment_pct: Optional[float] = Field(
        None,
        description=(
            "Average recommended adjustment across all projects and unit types. "
            "Null when no recommendations exist."
        ),
    )
    projects_underpriced: int = Field(
        ..., description="Projects where avg_recommended_adjustment_pct > 0"
    )
    projects_overpriced: int = Field(
        ..., description="Projects where avg_recommended_adjustment_pct < 0"
    )
    projects_balanced: int = Field(
        ..., description="Projects where avg_recommended_adjustment_pct == 0"
    )


class PortfolioPricingInsightsResponse(BaseModel):
    """Portfolio pricing intelligence response envelope (PR-V7-02).

    Aggregates project-level pricing recommendations into a portfolio view.
    Shows underpriced projects, overpriced projects, and pricing risk zones.
    All values are recommendation-only — no pricing records are mutated.
    """

    summary: PortfolioPricingInsightsSummary
    projects: List[PortfolioPricingProjectCard] = Field(
        default_factory=list,
        description="Per-project pricing cards ordered by avg_recommended_adjustment_pct descending",
    )
    top_opportunities: List[PortfolioPricingProjectCard] = Field(
        default_factory=list,
        description="Top 5 projects with highest upward price opportunity (underpriced)",
    )
    pricing_risk_zones: List[PortfolioPricingProjectCard] = Field(
        default_factory=list,
        description="Projects classified as overpriced (negative recommended adjustment)",
    )
