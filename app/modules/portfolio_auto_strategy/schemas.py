"""
portfolio_auto_strategy.schemas

Typed Pydantic response contracts for the Portfolio Auto-Strategy &
Intervention Prioritization Engine (PR-V7-06).

All schemas are read-only response models — the auto-strategy engine produces
recommendations only and never mutates any source data.

Schema hierarchy:
  PortfolioInterventionProjectCard  — per-project intervention summary card
  PortfolioTopActionItem            — lightweight action item for top-N lists
  PortfolioInterventionSummary      — portfolio-wide KPI roll-up
  PortfolioAutoStrategyResponse     — canonical portfolio endpoint envelope
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Intervention classification literals
# ---------------------------------------------------------------------------

InterventionPriority = Literal[
    "urgent_intervention",
    "recommended_intervention",
    "monitor_closely",
    "stable",
    "insufficient_data",
]

InterventionType = Literal[
    "pricing_intervention",
    "phasing_intervention",
    "mixed_intervention",
    "monitor_only",
    "insufficient_data",
]


# ---------------------------------------------------------------------------
# Per-project card
# ---------------------------------------------------------------------------


class PortfolioInterventionProjectCard(BaseModel):
    """Per-project intervention summary for portfolio-level ranking.

    Derived from project-level strategy outputs (PR-V7-05).
    No source records are mutated.
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
    recommended_strategy: Optional[str] = Field(
        None,
        description="Best release strategy: 'hold' | 'maintain' | 'accelerate'.",
    )
    best_irr: Optional[float] = Field(
        None,
        description=(
            "Best IRR from the top-ranked strategy scenario. "
            "Null when no scenarios could be generated."
        ),
    )
    irr_delta: Optional[float] = Field(
        None,
        description=(
            "IRR improvement vs the neutral maintain/no-change scenario. "
            "Null when a baseline reference cannot be computed."
        ),
    )
    risk_score: Optional[str] = Field(
        None,
        description="Risk classification for the best strategy: 'low' | 'medium' | 'high'.",
    )
    intervention_priority: InterventionPriority = Field(
        ...,
        description=(
            "Urgency classification: "
            "urgent_intervention | recommended_intervention | monitor_closely | stable | insufficient_data"
        ),
    )
    intervention_type: InterventionType = Field(
        ...,
        description=(
            "Type of intervention indicated: "
            "pricing_intervention | phasing_intervention | mixed_intervention | monitor_only | insufficient_data"
        ),
    )
    urgency_score: int = Field(
        ...,
        ge=0,
        le=100,
        description=(
            "Deterministic 0–100 urgency score. "
            "Derived from risk_score, baseline availability, price direction, and phase delay signals."
        ),
    )
    reason: str = Field(
        ..., description="Human-readable explanation of the intervention recommendation."
    )


# ---------------------------------------------------------------------------
# Top-action item (lightweight)
# ---------------------------------------------------------------------------


class PortfolioTopActionItem(BaseModel):
    """Lightweight action item surfaced in top-N portfolio action lists."""

    project_id: str
    project_name: str
    intervention_priority: InterventionPriority
    intervention_type: InterventionType
    urgency_score: int = Field(..., ge=0, le=100)
    reason: str


# ---------------------------------------------------------------------------
# Portfolio summary KPIs
# ---------------------------------------------------------------------------


class PortfolioInterventionSummary(BaseModel):
    """Portfolio-wide intervention KPI roll-up."""

    total_projects: int = Field(
        ..., description="Total projects evaluated in this portfolio pass."
    )
    analyzed_projects: int = Field(
        ...,
        description="Projects for which strategy analysis could be completed.",
    )
    projects_with_baseline: int = Field(
        ..., description="Projects with a calculated feasibility baseline."
    )
    urgent_intervention_count: int = Field(
        ..., description="Projects classified as urgent_intervention."
    )
    monitor_only_count: int = Field(
        ...,
        description="Projects classified as stable or monitor_closely (low urgency).",
    )
    no_data_count: int = Field(
        ..., description="Projects with insufficient_data (no strategy could be generated)."
    )


# ---------------------------------------------------------------------------
# Canonical response envelope
# ---------------------------------------------------------------------------


class PortfolioAutoStrategyResponse(BaseModel):
    """Portfolio Auto-Strategy & Intervention Prioritization response (PR-V7-06).

    Aggregates project-level strategy recommendations into a ranked portfolio
    intervention view.  All values are recommendation-only — no records are
    mutated.  The ranking is deterministic for a given portfolio state.

    Ranking rule:
      Primary   : intervention_priority severity descending
                  (urgent > recommended > monitor_closely > stable > insufficient_data)
      Secondary : risk_score severity descending
                  (high > medium > low > null)
      Tertiary  : urgency_score descending
      Quaternary: project_name ascending  (deterministic tie-break)
    """

    summary: PortfolioInterventionSummary
    top_actions: List[PortfolioTopActionItem] = Field(
        default_factory=list,
        description="Top 5 highest-urgency portfolio actions.",
    )
    top_risk_projects: List[PortfolioInterventionProjectCard] = Field(
        default_factory=list,
        description="Up to 5 projects with the highest urgency_score (risk-weighted).",
    )
    top_upside_projects: List[PortfolioInterventionProjectCard] = Field(
        default_factory=list,
        description="Up to 5 projects with the highest best_irr (upside opportunity).",
    )
    project_cards: List[PortfolioInterventionProjectCard] = Field(
        default_factory=list,
        description=(
            "All project intervention cards ordered by the four-key ranking rule: "
            "intervention_priority desc, risk_score desc, urgency_score desc, project_name asc."
        ),
    )
