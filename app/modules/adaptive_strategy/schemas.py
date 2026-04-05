"""
adaptive_strategy.schemas

Typed Pydantic response contracts for the Adaptive Strategy Influence Layer
(PR-V7-12).

All schemas are read-only output models.  The adaptive layer produces
confidence-weighted recommendations only and never mutates any source data.

Schema hierarchy:
  AdaptiveStrategyComparisonBlock       — raw vs adaptive metric comparison
  AdaptiveStrategyResponse              — project-level adaptive strategy payload
  PortfolioAdaptiveStrategyProjectCard  — per-project summary for portfolio view
  PortfolioAdaptiveStrategySummaryResponse — portfolio-level adaptive summary
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Classification literals
# ---------------------------------------------------------------------------

ConfidenceBand = Literal["high", "medium", "low", "insufficient"]


# ---------------------------------------------------------------------------
# Comparison block
# ---------------------------------------------------------------------------


class AdaptiveStrategyComparisonBlock(BaseModel):
    """Side-by-side comparison of raw simulation-best vs confidence-adjusted best.

    When raw and adaptive strategies are identical, changed_by_confidence is
    False.  When confidence influence shifted the selection, changed_by_confidence
    is True and the differing fields reflect the two strategies.
    """

    raw_irr: Optional[float] = Field(
        None,
        description="IRR of the raw simulation-best strategy (before confidence influence).",
    )
    adaptive_irr: Optional[float] = Field(
        None,
        description="IRR of the confidence-adjusted best strategy.",
    )
    raw_risk_score: Optional[str] = Field(
        None,
        description="Risk score of the raw best strategy: 'low' | 'medium' | 'high'.",
    )
    adaptive_risk_score: Optional[str] = Field(
        None,
        description="Risk score of the confidence-adjusted best strategy.",
    )
    raw_release_strategy: Optional[str] = Field(
        None,
        description="Release strategy of the raw best: 'hold' | 'maintain' | 'accelerate'.",
    )
    adaptive_release_strategy: Optional[str] = Field(
        None,
        description="Release strategy of the confidence-adjusted best.",
    )
    raw_price_adjustment_pct: Optional[float] = Field(
        None,
        description="Price adjustment % of the raw best strategy.",
    )
    adaptive_price_adjustment_pct: Optional[float] = Field(
        None,
        description="Price adjustment % of the confidence-adjusted best strategy.",
    )
    raw_phase_delay_months: Optional[int] = Field(
        None,
        description="Phase delay months of the raw best strategy.",
    )
    adaptive_phase_delay_months: Optional[int] = Field(
        None,
        description="Phase delay months of the confidence-adjusted best strategy.",
    )
    changed_by_confidence: bool = Field(
        ...,
        description=(
            "True when the confidence-adjusted best strategy differs from the "
            "raw simulation-best strategy."
        ),
    )


# ---------------------------------------------------------------------------
# Project-level response
# ---------------------------------------------------------------------------


class AdaptiveStrategyResponse(BaseModel):
    """Project-level adaptive strategy payload (PR-V7-12).

    Synthesises raw simulation ranking with learning-derived confidence to
    produce a confidence-adjusted recommendation.  The raw best strategy is
    always preserved for comparison so leadership can see both outputs.
    """

    project_id: str = Field(..., description="Project identifier.")
    project_name: str = Field(..., description="Project display name.")

    # Raw simulation output (from strategy_generator, unmodified)
    raw_best_strategy: Optional[str] = Field(
        None,
        description=(
            "Release strategy label of the raw simulation-best scenario "
            "('hold' | 'maintain' | 'accelerate'). Null when no scenarios were generated."
        ),
    )
    raw_best_irr: Optional[float] = Field(
        None,
        description="IRR of the raw simulation-best scenario.",
    )
    raw_best_risk_score: Optional[str] = Field(
        None,
        description="Risk score of the raw simulation-best scenario.",
    )
    raw_best_price_adjustment_pct: Optional[float] = Field(
        None,
        description="Price adjustment % of the raw simulation-best scenario.",
    )
    raw_best_phase_delay_months: Optional[int] = Field(
        None,
        description="Phase delay months of the raw simulation-best scenario.",
    )

    # Confidence-adjusted output
    adaptive_best_strategy: Optional[str] = Field(
        None,
        description=(
            "Release strategy label of the confidence-adjusted best scenario. "
            "Null when no scenarios were generated."
        ),
    )
    adaptive_best_irr: Optional[float] = Field(
        None,
        description="IRR of the confidence-adjusted best scenario.",
    )
    adaptive_best_risk_score: Optional[str] = Field(
        None,
        description="Risk score of the confidence-adjusted best scenario.",
    )
    adaptive_best_price_adjustment_pct: Optional[float] = Field(
        None,
        description="Price adjustment % of the confidence-adjusted best scenario.",
    )
    adaptive_best_phase_delay_months: Optional[int] = Field(
        None,
        description="Phase delay months of the confidence-adjusted best scenario.",
    )

    # Confidence metadata
    confidence_score: Optional[float] = Field(
        None,
        description=(
            "Project-wide learning confidence score in [0, 1]. "
            "None when no learning metrics exist."
        ),
    )
    confidence_band: ConfidenceBand = Field(
        ...,
        description=(
            "Confidence band derived from confidence_score: "
            "'high' (>= 0.7), 'medium' (0.4–0.7), 'low' (< 0.4), "
            "'insufficient' (no metrics)."
        ),
    )
    confidence_influence_applied: bool = Field(
        ...,
        description=(
            "True when a non-neutral confidence signal existed and was applied "
            "to influence ranking."
        ),
    )
    low_confidence_flag: bool = Field(
        ...,
        description=(
            "True when the project's confidence band is 'low' or 'insufficient'. "
            "Surfaces a caution signal in the UI."
        ),
    )
    sample_size: int = Field(
        0,
        description="Number of recorded outcomes contributing to the confidence score.",
    )
    trend_direction: str = Field(
        "insufficient_data",
        description=(
            "Direction of confidence change: improving | declining | stable | insufficient_data."
        ),
    )
    adjusted_reason: str = Field(
        ...,
        description=(
            "Human-readable explanation of how confidence influenced "
            "(or did not influence) the strategy selection."
        ),
    )

    # Comparison block
    comparison: AdaptiveStrategyComparisonBlock = Field(
        ...,
        description="Side-by-side raw vs adaptive metric comparison.",
    )


# ---------------------------------------------------------------------------
# Portfolio-level response
# ---------------------------------------------------------------------------


class PortfolioAdaptiveStrategyProjectCard(BaseModel):
    """Per-project adaptive strategy summary for portfolio view."""

    project_id: str = Field(..., description="Project identifier.")
    project_name: str = Field(..., description="Project display name.")
    raw_best_strategy: Optional[str] = Field(
        None,
        description="Release strategy of the raw simulation-best scenario.",
    )
    adaptive_best_strategy: Optional[str] = Field(
        None,
        description="Release strategy of the confidence-adjusted best scenario.",
    )
    confidence_score: Optional[float] = Field(
        None,
        description="Project-wide learning confidence score in [0, 1].",
    )
    confidence_band: ConfidenceBand = Field(
        ...,
        description="Confidence band: 'high' | 'medium' | 'low' | 'insufficient'.",
    )
    confidence_influence_applied: bool = Field(
        ...,
        description="True when confidence influence shifted the recommendation.",
    )
    low_confidence_flag: bool = Field(
        ...,
        description="True when confidence band is 'low' or 'insufficient'.",
    )
    sample_size: int = Field(0, description="Number of outcomes used for confidence.")
    trend_direction: str = Field(
        "insufficient_data",
        description="Direction of confidence change.",
    )
    adjusted_reason: str = Field(
        ...,
        description="Human-readable summary of confidence influence.",
    )


class PortfolioAdaptiveStrategySummaryResponse(BaseModel):
    """Portfolio-level adaptive strategy summary response (PR-V7-12).

    Provides an overview of confidence-adjusted recommendations across all
    projects.  No source records are mutated.
    """

    total_projects: int = Field(
        ...,
        description="Total number of projects evaluated.",
    )
    high_confidence_projects: int = Field(
        ...,
        description="Projects with confidence_band == 'high'.",
    )
    low_confidence_projects: int = Field(
        ...,
        description="Projects with confidence_band == 'low' or 'insufficient'.",
    )
    confidence_adjusted_projects: int = Field(
        ...,
        description="Projects where confidence influence changed the recommendation.",
    )
    neutral_projects: int = Field(
        ...,
        description=(
            "Projects where confidence was neutral (no influence applied, "
            "raw and adaptive recommendations are identical)."
        ),
    )
    top_confident_recommendations: List[PortfolioAdaptiveStrategyProjectCard] = Field(
        default_factory=list,
        description="Top 5 projects by confidence_score (descending).",
    )
    top_low_confidence_projects: List[PortfolioAdaptiveStrategyProjectCard] = Field(
        default_factory=list,
        description="Up to 5 projects with the lowest confidence (low/insufficient band).",
    )
    project_cards: List[PortfolioAdaptiveStrategyProjectCard] = Field(
        default_factory=list,
        description="All project cards ordered by confidence_score descending.",
    )
