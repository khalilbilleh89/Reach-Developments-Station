"""
strategy_learning.schemas

Typed Pydantic request and response contracts for the Strategy Learning
module (PR-V7-11).

Schema hierarchy
----------------
  Response schemas (outbound):
    StrategyLearningMetricsResponse     — single (project, strategy_type) metrics row
    AccuracyBreakdown                   — per-dimension accuracy sub-scores
    StrategyLearningResponse            — project-level learning panel payload
    PortfolioLearningProjectEntry       — one project's summary within portfolio
    PortfolioLearningSummaryResponse    — portfolio-level learning panel payload

All schemas are read-only output models (no request bodies needed —
learning data is derived, not user-submitted).
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Classification literals
# ---------------------------------------------------------------------------

TrendDirection = Literal["improving", "declining", "stable", "insufficient_data"]


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------


class AccuracyBreakdown(BaseModel):
    """Per-dimension accuracy sub-scores for a strategy type.

    Each score is the fraction of outcomes (in [0, 1]) where that dimension
    matched the intended strategy.  None when no comparable data exists.
    """

    pricing_accuracy_score: Optional[float] = Field(
        None,
        description=(
            "Fraction of outcomes where the price adjustment matched the intended "
            "strategy (exact or minor variance). None if no pricing comparisons exist."
        ),
    )
    phasing_accuracy_score: Optional[float] = Field(
        None,
        description=(
            "Fraction of outcomes where the phase delay matched the intended "
            "strategy (exact or minor variance). None if no phasing comparisons exist."
        ),
    )
    overall_strategy_accuracy: float = Field(
        ...,
        description="Fraction of outcomes classified as 'matched_strategy'.",
    )


class StrategyLearningMetricsResponse(BaseModel):
    """Full metrics row for a (project, strategy_type) pair."""

    id: str = Field(..., description="Unique metrics record identifier.")
    project_id: str = Field(..., description="Project the metrics belong to.")
    strategy_type: str = Field(
        ...,
        description=(
            "Strategy type label (e.g. 'maintain', 'accelerate', 'hold', '_all_' "
            "for the project-wide aggregate row)."
        ),
    )
    sample_size: int = Field(
        ...,
        description="Number of recorded outcomes contributing to these metrics.",
    )
    match_rate: float = Field(
        ...,
        description="Fraction of outcomes classified as 'matched_strategy'.",
    )
    partial_rate: float = Field(
        ...,
        description="Fraction of outcomes classified as 'partially_matched'.",
    )
    divergence_rate: float = Field(
        ...,
        description="Fraction of outcomes classified as 'diverged'.",
    )
    confidence_score: float = Field(
        ...,
        description=(
            "Composite confidence score in [0, 1]. "
            "Capped at 0.5 when sample_size < 5."
        ),
    )
    accuracy_breakdown: AccuracyBreakdown = Field(
        ...,
        description="Per-dimension accuracy sub-scores.",
    )
    trend_direction: TrendDirection = Field(
        ...,
        description=(
            "Direction of confidence change: improving | declining | stable | insufficient_data."
        ),
    )
    last_updated: datetime = Field(
        ...,
        description="UTC timestamp when these metrics were last recalculated.",
    )
    created_at: datetime = Field(..., description="UTC timestamp of record creation.")
    updated_at: datetime = Field(..., description="UTC timestamp of last update.")

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Project-level response
# ---------------------------------------------------------------------------


class StrategyLearningResponse(BaseModel):
    """Project-level strategy learning panel payload.

    Contains the project-wide aggregate metrics plus per-strategy-type
    breakdowns.  When no outcomes have been recorded for the project, all
    metrics rows are empty and has_sufficient_data is False.
    """

    project_id: str = Field(..., description="Project identifier.")
    has_sufficient_data: bool = Field(
        ...,
        description=(
            "True when at least one 'recorded' outcome exists for this project."
        ),
    )
    overall_metrics: Optional[StrategyLearningMetricsResponse] = Field(
        None,
        description=(
            "Project-wide aggregate metrics (strategy_type='_all_'). "
            "None when no outcomes exist."
        ),
    )
    strategy_breakdowns: List[StrategyLearningMetricsResponse] = Field(
        default_factory=list,
        description=(
            "Per-strategy-type metrics rows (excluding the '_all_' aggregate)."
        ),
    )


# ---------------------------------------------------------------------------
# Portfolio-level response
# ---------------------------------------------------------------------------


class PortfolioLearningProjectEntry(BaseModel):
    """One project's learning summary within the portfolio payload."""

    project_id: str = Field(..., description="Project identifier.")
    project_name: str = Field(..., description="Project display name.")
    confidence_score: float = Field(
        ...,
        description="Project-wide confidence score (from strategy_type='_all_' row).",
    )
    sample_size: int = Field(
        ...,
        description="Number of outcomes contributing to this project's metrics.",
    )
    trend_direction: TrendDirection = Field(
        ...,
        description="Direction of confidence change for this project.",
    )
    overall_strategy_accuracy: float = Field(
        ...,
        description="Fraction of outcomes classified as 'matched_strategy'.",
    )


class PortfolioLearningSummaryResponse(BaseModel):
    """Portfolio-level learning panel payload.

    Provides an overview of system confidence and learning progress across
    all projects.
    """

    total_projects_with_data: int = Field(
        ...,
        description="Number of projects that have at least one recorded outcome.",
    )
    average_confidence_score: Optional[float] = Field(
        None,
        description=(
            "Mean confidence score across all projects with data. "
            "None when no projects have data."
        ),
    )
    high_confidence_count: int = Field(
        ...,
        description="Number of projects with confidence_score >= 0.7.",
    )
    low_confidence_count: int = Field(
        ...,
        description="Number of projects with confidence_score < 0.4.",
    )
    improving_count: int = Field(
        ...,
        description="Number of projects with trend_direction='improving'.",
    )
    declining_count: int = Field(
        ...,
        description="Number of projects with trend_direction='declining'.",
    )
    top_performing_projects: List[PortfolioLearningProjectEntry] = Field(
        default_factory=list,
        description=(
            "Top 5 projects by confidence_score (descending). "
            "Only projects with sample_size >= 2 are included."
        ),
    )
    weak_area_projects: List[PortfolioLearningProjectEntry] = Field(
        default_factory=list,
        description=(
            "Up to 5 projects with the lowest confidence scores "
            "(only projects with sample_size >= 2 and confidence_score < 0.5)."
        ),
    )
    all_project_entries: List[PortfolioLearningProjectEntry] = Field(
        default_factory=list,
        description="All projects with learning data, ordered by confidence_score descending.",
    )
