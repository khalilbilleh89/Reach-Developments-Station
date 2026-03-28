"""
phasing_optimization.schemas

Typed Pydantic response contracts for the Phasing Optimization Engine (PR-V7-03).

All schemas are read-only response models — the phasing optimization layer produces
recommendations only and never mutates phase or inventory data.

Schema hierarchy:
  ProjectPhasingRecommendationResponse  — project-level phasing recommendation envelope
  PortfolioPhasingProjectCard           — per-project summary for portfolio view
  PortfolioPhasingInsightsSummary       — portfolio-wide phasing aggregates
  PortfolioPhasingInsightsResponse      — portfolio-level response envelope

Recommendation categories:
  Current phase:
    release_more_inventory    — release more units into the market
    maintain_current_release  — keep current release pace
    hold_current_inventory    — hold back remaining stock
    delay_further_release     — slow down or pause further releases
    insufficient_data         — no usable sales signal

  Next phase:
    prepare_next_phase        — begin preparation for next phase launch
    do_not_open_next_phase    — demand does not yet justify next phase
    defer_next_phase          — delay next phase until demand improves
    not_applicable            — no next phase exists in project structure
    insufficient_data         — insufficient data for recommendation

  Release urgency:  high | medium | low | none
  Confidence:       high | medium | low
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ProjectPhasingRecommendationResponse(BaseModel):
    """Project-level phasing recommendation response (PR-V7-03).

    Aggregates demand, availability, and readiness signals into a single
    phasing decision summary for a project.  No phase or inventory records
    are mutated — all outputs are recommendations only.
    """

    project_id: str
    project_name: str

    # Current active phase context
    current_phase_id: Optional[str] = Field(
        None, description="ID of the current active selling phase; null if no phases with units"
    )
    current_phase_name: Optional[str] = Field(
        None, description="Name of the current active selling phase"
    )

    # Recommendations
    current_phase_recommendation: str = Field(
        ...,
        description=(
            "Current-phase release strategy: "
            "'release_more_inventory' | 'maintain_current_release' | "
            "'hold_current_inventory' | 'delay_further_release' | 'insufficient_data'"
        ),
    )
    next_phase_recommendation: str = Field(
        ...,
        description=(
            "Next-phase readiness: "
            "'prepare_next_phase' | 'do_not_open_next_phase' | "
            "'defer_next_phase' | 'not_applicable' | 'insufficient_data'"
        ),
    )
    release_urgency: str = Field(
        ...,
        description="Release urgency signal: 'high' | 'medium' | 'low' | 'none'",
    )
    confidence: str = Field(
        ...,
        description="Confidence level for the recommendation: 'high' | 'medium' | 'low'",
    )
    reason: str = Field(..., description="Human-readable explanation of the recommendation")

    # Inventory context
    sold_units: int = Field(..., description="Total sold units across all phases (under_contract + registered)")
    available_units: int = Field(..., description="Total available units across all phases")
    sell_through_pct: Optional[float] = Field(
        None, description="Project-wide sell-through percentage (sold / total * 100); null when no units"
    )

    # Demand context
    absorption_status: str = Field(
        ...,
        description=(
            "Demand classification: "
            "'high_demand' | 'balanced' | 'low_demand' | 'no_data'"
        ),
    )

    # Next phase context
    has_next_phase: bool = Field(
        ..., description="True when a next phase exists in the project structure"
    )
    next_phase_id: Optional[str] = Field(
        None, description="ID of the next phase; null when not applicable"
    )
    next_phase_name: Optional[str] = Field(
        None, description="Name of the next phase; null when not applicable"
    )


class PortfolioPhasingProjectCard(BaseModel):
    """Per-project phasing intelligence summary for portfolio view."""

    project_id: str
    project_name: str
    current_phase_recommendation: str = Field(
        ...,
        description=(
            "Current-phase release strategy: "
            "'release_more_inventory' | 'maintain_current_release' | "
            "'hold_current_inventory' | 'delay_further_release' | 'insufficient_data'"
        ),
    )
    next_phase_recommendation: str = Field(
        ...,
        description=(
            "Next-phase readiness: "
            "'prepare_next_phase' | 'do_not_open_next_phase' | "
            "'defer_next_phase' | 'not_applicable' | 'insufficient_data'"
        ),
    )
    release_urgency: str = Field(
        ...,
        description="Release urgency signal: 'high' | 'medium' | 'low' | 'none'",
    )
    confidence: str = Field(
        ..., description="Confidence level: 'high' | 'medium' | 'low'"
    )
    sell_through_pct: Optional[float] = Field(
        None, description="Project-wide sell-through percentage; null when no units"
    )
    absorption_status: str = Field(
        ...,
        description="Demand classification: 'high_demand' | 'balanced' | 'low_demand' | 'no_data'",
    )
    has_next_phase: bool = Field(
        ..., description="True when a next phase exists in the project structure"
    )


class PortfolioPhasingInsightsSummary(BaseModel):
    """Portfolio-wide phasing intelligence aggregates."""

    total_projects: int
    projects_prepare_next_phase_count: int = Field(
        ..., description="Projects where next_phase_recommendation == 'prepare_next_phase'"
    )
    projects_hold_inventory_count: int = Field(
        ..., description="Projects where current_phase_recommendation == 'hold_current_inventory'"
    )
    projects_delay_release_count: int = Field(
        ..., description="Projects where current_phase_recommendation == 'delay_further_release'"
    )
    projects_insufficient_data_count: int = Field(
        ..., description="Projects where current_phase_recommendation == 'insufficient_data'"
    )


class PortfolioPhasingInsightsResponse(BaseModel):
    """Portfolio phasing intelligence response envelope (PR-V7-03).

    Aggregates project-level phasing recommendations into a portfolio view.
    Shows phase preparation opportunities, hold/delay risks, and insufficient-data projects.
    All values are recommendation-only — no phase records are mutated.
    """

    summary: PortfolioPhasingInsightsSummary
    projects: List[PortfolioPhasingProjectCard] = Field(
        default_factory=list,
        description="Per-project phasing cards ordered by release_urgency descending",
    )
    top_phase_opportunities: List[PortfolioPhasingProjectCard] = Field(
        default_factory=list,
        description="Top 5 projects that should prepare the next phase (high demand, low inventory)",
    )
    top_release_risks: List[PortfolioPhasingProjectCard] = Field(
        default_factory=list,
        description="Top 5 projects with hold/delay risk (low demand, high unsold inventory)",
    )
