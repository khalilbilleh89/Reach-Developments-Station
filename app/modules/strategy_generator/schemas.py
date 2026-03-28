"""
strategy_generator.schemas

Typed Pydantic response contracts for the Automated Strategy Generator
(PR-V7-05).

All schemas are read-only response models — the strategy generator produces
recommendations only and never mutates any source data.

Schema hierarchy:
  RecommendedStrategyResponse       — project-level strategy recommendation
  PortfolioStrategyProjectCard      — per-project summary for portfolio view
  PortfolioStrategyInsightsSummary  — portfolio-wide strategy aggregates
  PortfolioStrategyInsightsResponse — portfolio-level response envelope
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.modules.release_simulation.schemas import SimulationResult


class RecommendedStrategyResponse(BaseModel):
    """Project-level recommended strategy response (PR-V7-05).

    Synthesises candidate strategy simulations into a single ranked output.
    No source records are mutated — all outputs are recommendations only.
    """

    project_id: str
    project_name: str
    has_feasibility_baseline: bool = Field(
        ...,
        description=(
            "True when a calculated feasibility run exists for this project. "
            "When false, simulation uses default assumptions and results are indicative only."
        ),
    )
    best_strategy: Optional[SimulationResult] = Field(
        None,
        description=(
            "The highest-ranked strategy after applying primary (IRR), "
            "secondary (risk_score), and tertiary (delay) ranking rules. "
            "Null when no scenarios could be generated."
        ),
    )
    top_strategies: List[SimulationResult] = Field(
        default_factory=list,
        description="Top 3 ranked strategies (ranked by IRR desc, risk asc, delay asc).",
    )
    reason: str = Field(
        ...,
        description="Human-readable explanation of the best strategy recommendation.",
    )
    generated_scenario_count: int = Field(
        ...,
        description="Number of candidate scenarios evaluated before ranking.",
    )


class PortfolioStrategyProjectCard(BaseModel):
    """Per-project strategy intelligence summary for portfolio view."""

    project_id: str
    project_name: str
    has_feasibility_baseline: bool
    best_irr: Optional[float] = Field(
        None, description="Best IRR from top-ranked strategy; null when no baseline."
    )
    best_risk_score: Optional[str] = Field(
        None,
        description="Risk classification for the best strategy: 'low' | 'medium' | 'high'.",
    )
    best_release_strategy: Optional[str] = Field(
        None,
        description="Release strategy of the best scenario: 'hold' | 'maintain' | 'accelerate'.",
    )
    best_price_adjustment_pct: Optional[float] = Field(
        None, description="Price adjustment % of the best scenario."
    )
    best_phase_delay_months: Optional[int] = Field(
        None, description="Phase delay months of the best scenario."
    )
    reason: str = Field(..., description="Human-readable recommendation summary.")


class PortfolioStrategyInsightsSummary(BaseModel):
    """Portfolio-wide strategy intelligence aggregates."""

    total_projects: int
    projects_with_baseline: int = Field(
        ..., description="Projects with a calculated feasibility baseline."
    )
    projects_high_risk: int = Field(
        ...,
        description="Projects whose best strategy has risk_score == 'high'.",
    )
    projects_low_risk: int = Field(
        ...,
        description="Projects whose best strategy has risk_score == 'low'.",
    )


class PortfolioStrategyInsightsResponse(BaseModel):
    """Portfolio strategy intelligence response envelope (PR-V7-05).

    Aggregates project-level strategy recommendations into a portfolio view.
    Shows top strategies, risk flags, and projects requiring intervention.
    All values are recommendation-only — no records are mutated.
    """

    summary: PortfolioStrategyInsightsSummary
    projects: List[PortfolioStrategyProjectCard] = Field(
        default_factory=list,
        description="Per-project strategy cards ordered by best IRR descending.",
    )
    top_strategies: List[PortfolioStrategyProjectCard] = Field(
        default_factory=list,
        description="Top 3 projects by best simulated IRR.",
    )
    intervention_required: List[PortfolioStrategyProjectCard] = Field(
        default_factory=list,
        description="Projects whose best strategy carries a 'high' risk score.",
    )
