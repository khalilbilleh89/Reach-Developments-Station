"""
strategy_execution_outcome.schemas

Typed Pydantic request and response contracts for the Strategy Execution
Outcome module (PR-V7-10).

Schema hierarchy
----------------
  Request schemas (inbound):
    RecordExecutionOutcomeRequest  — body for POST /execution-triggers/{id}/outcome

  Response schemas (outbound):
    ExecutionOutcomeComparisonBlock       — intended vs realized comparison data
    StrategyExecutionOutcomeResponse      — full outcome record with comparison
    ProjectExecutionOutcomeResponse       — project-scoped outcome view
    PortfolioOutcomeEntry                 — outcome entry with project name
    PortfolioOutcomeProjectEntry          — project with completed trigger but no outcome
    PortfolioExecutionOutcomeSummaryResponse — portfolio-level outcome summary

All response schemas are read-only output models.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Classification literals
# ---------------------------------------------------------------------------

OutcomeResult = Literal[
    "matched_strategy",
    "partially_matched",
    "diverged",
    "cancelled_execution",
    "insufficient_data",
]

OutcomeStatus = Literal["recorded", "superseded"]

MatchStatus = Literal[
    "exact_match",
    "minor_variance",
    "major_variance",
    "no_comparable_strategy",
]

ExecutionQuality = Literal["high", "medium", "low", "unknown"]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RecordExecutionOutcomeRequest(BaseModel):
    """Body for recording an execution outcome against a trigger.

    All actual-value fields are optional — not all outcomes have numeric
    comparable data.  outcome_result is required to classify the outcome.
    """

    actual_price_adjustment_pct: Optional[float] = Field(
        None,
        description="Actual price adjustment applied as a percentage. Null if not applicable.",
    )
    actual_phase_delay_months: Optional[float] = Field(
        None,
        ge=0,
        description="Actual phase delay in months. Null if not applicable.",
    )
    actual_release_strategy: Optional[str] = Field(
        None,
        description="Actual release strategy applied: 'hold' | 'maintain' | 'accelerate' or custom.",
    )
    execution_summary: Optional[str] = Field(
        None,
        description="Human-readable summary of what was executed.",
    )
    outcome_result: OutcomeResult = Field(
        ...,
        description=(
            "Outcome result classification: "
            "matched_strategy | partially_matched | diverged | cancelled_execution | insufficient_data"
        ),
    )
    outcome_notes: Optional[str] = Field(
        None,
        description="Additional notes about the outcome or deviations.",
    )


# ---------------------------------------------------------------------------
# Comparison block
# ---------------------------------------------------------------------------


class ExecutionOutcomeComparisonBlock(BaseModel):
    """Intended vs realized execution outcome comparison.

    Derived deterministically from the trigger's execution_package_snapshot
    (intended values) and the recorded outcome (actual values).

    match_status classification thresholds:
      price_adjustment_pct  — exact if |diff| < 1 pp, minor if 1-5 pp, major if > 5 pp
      phase_delay_months    — exact if diff = 0, minor if |diff| <= 1, major if |diff| > 1
      release_strategy      — exact if equal, major_variance if different

    Overall match_status is the worst classification across all comparable fields.
    no_comparable_strategy is returned when no intended values are available.
    """

    intended_price_adjustment_pct: Optional[float] = Field(
        None,
        description="Intended price adjustment % from the approved execution package.",
    )
    actual_price_adjustment_pct: Optional[float] = Field(
        None,
        description="Actual price adjustment % recorded in the outcome.",
    )
    intended_phase_delay_months: Optional[float] = Field(
        None,
        description="Intended phase delay months from the approved execution package.",
    )
    actual_phase_delay_months: Optional[float] = Field(
        None,
        description="Actual phase delay months recorded in the outcome.",
    )
    intended_release_strategy: Optional[str] = Field(
        None,
        description="Intended release strategy from the approved execution package.",
    )
    actual_release_strategy: Optional[str] = Field(
        None,
        description="Actual release strategy recorded in the outcome.",
    )
    match_status: MatchStatus = Field(
        ...,
        description=(
            "Overall match classification: "
            "exact_match | minor_variance | major_variance | no_comparable_strategy"
        ),
    )
    divergence_summary: str = Field(
        ...,
        description="Human-readable description of the divergence (or confirmation of match).",
    )
    execution_quality: ExecutionQuality = Field(
        ...,
        description="Derived quality score: high | medium | low | unknown.",
    )
    has_material_divergence: bool = Field(
        ...,
        description="True when match_status is major_variance.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class StrategyExecutionOutcomeResponse(BaseModel):
    """Full execution outcome record returned by outcome endpoints.

    Includes the persisted outcome fields and the live-derived comparison block.
    """

    id: str = Field(..., description="Unique outcome record identifier.")
    project_id: str = Field(..., description="Project the outcome belongs to.")
    execution_trigger_id: Optional[str] = Field(
        None,
        description="Execution trigger this outcome was recorded against (null if trigger deleted).",
    )
    approval_id: Optional[str] = Field(
        None,
        description="Approval that authorised the trigger (null if approval deleted).",
    )
    status: OutcomeStatus = Field(
        ...,
        description="Outcome record status: recorded | superseded.",
    )
    outcome_result: OutcomeResult = Field(
        ...,
        description=(
            "Outcome result classification: "
            "matched_strategy | partially_matched | diverged | cancelled_execution | insufficient_data"
        ),
    )
    actual_price_adjustment_pct: Optional[float] = Field(
        None,
        description="Actual price adjustment % applied.",
    )
    actual_phase_delay_months: Optional[float] = Field(
        None,
        description="Actual phase delay months applied.",
    )
    actual_release_strategy: Optional[str] = Field(
        None,
        description="Actual release strategy applied.",
    )
    execution_summary: Optional[str] = Field(
        None,
        description="Human-readable execution summary.",
    )
    outcome_notes: Optional[str] = Field(
        None,
        description="Additional outcome notes.",
    )
    recorded_by_user_id: str = Field(
        ...,
        description="User ID of the person who recorded this outcome.",
    )
    recorded_at: datetime = Field(
        ...,
        description="UTC timestamp when this outcome was recorded.",
    )
    created_at: datetime = Field(..., description="UTC timestamp of record creation.")
    updated_at: datetime = Field(..., description="UTC timestamp of last update.")
    comparison: ExecutionOutcomeComparisonBlock = Field(
        ...,
        description="Live-derived intended vs realized comparison block.",
    )
    has_material_divergence: bool = Field(
        ...,
        description="True when the comparison block identifies major_variance.",
    )

    model_config = ConfigDict(from_attributes=True)


class ProjectExecutionOutcomeResponse(BaseModel):
    """Project-scoped execution outcome view.

    Returns the latest trigger context alongside the latest recorded outcome
    (or null when none has been recorded yet) and a flag indicating whether
    the trigger is eligible for outcome recording.
    """

    project_id: str = Field(..., description="Project identifier.")
    execution_trigger_id: Optional[str] = Field(
        None,
        description="Latest execution trigger ID for this project (null if none).",
    )
    trigger_status: Optional[str] = Field(
        None,
        description="Current status of the latest trigger (null if none).",
    )
    outcome_eligible: bool = Field(
        ...,
        description=(
            "True when the latest trigger is in 'in_progress' or 'completed' state "
            "and outcome recording is permitted."
        ),
    )
    latest_outcome: Optional[StrategyExecutionOutcomeResponse] = Field(
        None,
        description="Most recently recorded outcome for this project (null if none).",
    )


class PortfolioOutcomeEntry(BaseModel):
    """Portfolio-level entry pairing an outcome record with its project name."""

    project_id: str = Field(..., description="Project identifier.")
    project_name: str = Field(..., description="Project display name.")
    outcome: StrategyExecutionOutcomeResponse = Field(
        ..., description="Latest recorded outcome for this project."
    )


class PortfolioOutcomeProjectEntry(BaseModel):
    """Portfolio-level entry for a project with completed trigger but no outcome."""

    project_id: str = Field(..., description="Project identifier.")
    project_name: str = Field(..., description="Project display name.")
    trigger_id: str = Field(
        ...,
        description="ID of the completed trigger awaiting outcome recording.",
    )


class PortfolioExecutionOutcomeSummaryResponse(BaseModel):
    """Portfolio-level execution outcome summary (PR-V7-10).

    Provides outcome result counts, divergence visibility, and projects with
    completed triggers that still need an outcome recorded.
    """

    matched_strategy_count: int = Field(
        ...,
        description="Number of recorded outcomes with result 'matched_strategy'.",
    )
    partially_matched_count: int = Field(
        ...,
        description="Number of recorded outcomes with result 'partially_matched'.",
    )
    diverged_count: int = Field(
        ...,
        description="Number of recorded outcomes with result 'diverged'.",
    )
    cancelled_execution_count: int = Field(
        ...,
        description="Number of recorded outcomes with result 'cancelled_execution'.",
    )
    insufficient_data_count: int = Field(
        ...,
        description="Number of recorded outcomes with result 'insufficient_data'.",
    )
    awaiting_outcome_count: int = Field(
        ...,
        description=(
            "Number of projects with a completed trigger that have no recorded outcome yet."
        ),
    )
    recent_outcomes: List[PortfolioOutcomeEntry] = Field(
        default_factory=list,
        description="Most recently recorded outcomes across all projects (up to 50).",
    )
    awaiting_outcome_projects: List[PortfolioOutcomeProjectEntry] = Field(
        default_factory=list,
        description="Projects with completed triggers awaiting outcome recording.",
    )
