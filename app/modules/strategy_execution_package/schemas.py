"""
strategy_execution_package.schemas

Typed Pydantic response contracts for the Strategy Execution Package
Generator (PR-V7-07).

All schemas are read-only response models — the execution package generator
produces action guidance only and never mutates any source data.

Schema hierarchy:
  StrategyExecutionActionItem        — one ordered action step
  StrategyExecutionDependencyItem    — one dependency / blocker check
  StrategyExecutionCautionItem       — one caution / risk note
  StrategyExecutionSupportingMetrics — raw strategy metrics for reference
  ProjectStrategyExecutionPackageResponse — full project-level package
  PortfolioPackagedInterventionCard  — compact card for portfolio view
  PortfolioExecutionPackageSummary   — portfolio KPI roll-up
  PortfolioExecutionPackageResponse  — canonical portfolio endpoint envelope
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Classification literals
# ---------------------------------------------------------------------------

ExecutionReadiness = Literal[
    "ready_for_review",
    "blocked_by_dependency",
    "caution_required",
    "insufficient_data",
]

ActionType = Literal[
    "baseline_dependency_review",
    "simulation_review",
    "pricing_update_preparation",
    "phase_release_preparation",
    "holdback_validation",
    "executive_review",
]

DependencyStatus = Literal["cleared", "blocked"]

CautionSeverity = Literal["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Action item
# ---------------------------------------------------------------------------


class StrategyExecutionActionItem(BaseModel):
    """One ordered execution action step within a project package.

    Actions are numbered sequentially (step_number 1…N).
    Each step carries an urgency, optional dependency reference, and a flag
    indicating whether human review is required before it can proceed.
    """

    step_number: int = Field(
        ..., ge=1, description="Execution sequence position (1 = first step)."
    )
    action_type: ActionType = Field(
        ...,
        description=(
            "Structured action category: "
            "baseline_dependency_review | simulation_review | pricing_update_preparation | "
            "phase_release_preparation | holdback_validation | executive_review"
        ),
    )
    action_title: str = Field(..., description="Short human-readable action title.")
    action_description: str = Field(
        ..., description="Full description of what this action requires."
    )
    target_area: str = Field(
        ...,
        description="Platform area the action targets: feasibility | pricing | phasing | release | review.",
    )
    urgency: str = Field(
        ..., description="Action urgency: 'high' | 'medium' | 'low'."
    )
    depends_on: Optional[str] = Field(
        None,
        description="Reference to a blocking step or dependency (e.g. 'Step 1'). Null when none.",
    )
    review_required: bool = Field(
        ...,
        description="True when this action requires explicit human review before proceeding.",
    )


# ---------------------------------------------------------------------------
# Dependency item
# ---------------------------------------------------------------------------


class StrategyExecutionDependencyItem(BaseModel):
    """One dependency check in the execution package.

    A 'blocked' dependency means the execution package cannot be acted upon
    until the dependency is resolved.  A 'cleared' dependency is informational.
    """

    dependency_type: str = Field(
        ...,
        description="Dependency category: 'feasibility_baseline' | 'strategy_data'.",
    )
    dependency_label: str = Field(
        ..., description="Human-readable label for this dependency."
    )
    dependency_status: DependencyStatus = Field(
        ..., description="'cleared' when satisfied; 'blocked' when not."
    )
    blocking_reason: Optional[str] = Field(
        None,
        description="Explanation of why this dependency is blocked. Null when cleared.",
    )


# ---------------------------------------------------------------------------
# Caution item
# ---------------------------------------------------------------------------


class StrategyExecutionCautionItem(BaseModel):
    """One caution note attached to an execution package.

    Cautions surface risk signals that do not block execution but require
    attention before the recommended strategy is implemented.
    """

    severity: CautionSeverity = Field(
        ..., description="Caution severity: 'high' | 'medium' | 'low'."
    )
    caution_title: str = Field(..., description="Short caution title.")
    caution_description: str = Field(
        ..., description="Full description of the caution and its implications."
    )


# ---------------------------------------------------------------------------
# Supporting metrics
# ---------------------------------------------------------------------------


class StrategyExecutionSupportingMetrics(BaseModel):
    """Raw strategy metrics included in the package for reference.

    These are the simulation outputs that informed the recommended strategy.
    They are read-only — not inputs to any downstream calculation.
    """

    best_irr: Optional[float] = Field(
        None, description="Best simulated IRR. Null when no scenarios could be generated."
    )
    risk_score: Optional[str] = Field(
        None, description="Risk classification of the best strategy: 'low' | 'medium' | 'high'."
    )
    price_adjustment_pct: Optional[float] = Field(
        None, description="Recommended price adjustment % from the best strategy."
    )
    phase_delay_months: Optional[int] = Field(
        None, description="Recommended phase delay months from the best strategy."
    )
    release_strategy: Optional[str] = Field(
        None,
        description="Best release strategy: 'hold' | 'maintain' | 'accelerate'.",
    )


# ---------------------------------------------------------------------------
# Project-level execution package
# ---------------------------------------------------------------------------


class ProjectStrategyExecutionPackageResponse(BaseModel):
    """Full strategy execution package for a single project (PR-V7-07).

    Translates the recommended strategy output into an ordered, dependency-
    aware action bundle.  Read-only — no source records are mutated.

    Execution readiness classification:
      ready_for_review      — baseline available, strategy data present, risk is low/medium
      blocked_by_dependency — no feasibility baseline (simulation is indicative only)
      caution_required      — strategy has a high risk classification
      insufficient_data     — no strategy could be generated for this project
    """

    project_id: str
    project_name: str
    has_feasibility_baseline: bool = Field(
        ...,
        description="True when an approved feasibility baseline exists for this project.",
    )
    recommended_strategy: Optional[str] = Field(
        None,
        description="Best release strategy: 'hold' | 'maintain' | 'accelerate'.",
    )
    execution_readiness: ExecutionReadiness = Field(
        ...,
        description=(
            "Execution readiness classification: "
            "ready_for_review | blocked_by_dependency | caution_required | insufficient_data"
        ),
    )
    summary: str = Field(
        ..., description="Human-readable summary of this execution package."
    )
    actions: List[StrategyExecutionActionItem] = Field(
        default_factory=list,
        description="Ordered execution action steps.",
    )
    dependencies: List[StrategyExecutionDependencyItem] = Field(
        default_factory=list,
        description="Dependency checks (cleared or blocked).",
    )
    cautions: List[StrategyExecutionCautionItem] = Field(
        default_factory=list,
        description="Risk cautions that apply to this package.",
    )
    supporting_metrics: StrategyExecutionSupportingMetrics = Field(
        ..., description="Raw strategy metrics for reference."
    )
    expected_impact: str = Field(
        ..., description="Human-readable expected impact summary."
    )
    requires_manual_review: bool = Field(
        ...,
        description=(
            "True when any action in this package requires human review, "
            "or when the execution readiness is blocked or caution_required."
        ),
    )


# ---------------------------------------------------------------------------
# Portfolio packaged intervention card (compact)
# ---------------------------------------------------------------------------


class PortfolioPackagedInterventionCard(BaseModel):
    """Compact execution package card for portfolio-level views.

    Derived from ProjectStrategyExecutionPackageResponse and portfolio_auto_strategy
    intervention classification.  Read-only.
    """

    project_id: str
    project_name: str
    recommended_strategy: Optional[str] = Field(
        None,
        description="Best release strategy: 'hold' | 'maintain' | 'accelerate'.",
    )
    intervention_priority: str = Field(
        ...,
        description=(
            "Urgency classification: "
            "urgent_intervention | recommended_intervention | monitor_closely | stable | insufficient_data"
        ),
    )
    intervention_type: str = Field(
        ...,
        description=(
            "Type of intervention indicated: "
            "pricing_intervention | phasing_intervention | mixed_intervention | monitor_only | insufficient_data"
        ),
    )
    execution_readiness: ExecutionReadiness = Field(
        ..., description="Execution readiness classification for this project."
    )
    has_feasibility_baseline: bool
    requires_manual_review: bool
    next_best_action: Optional[str] = Field(
        None, description="Title of the first action step in the execution package."
    )
    blockers: List[str] = Field(
        default_factory=list,
        description="Labels of blocked dependencies preventing execution.",
    )
    urgency_score: int = Field(
        ..., ge=0, le=100, description="Deterministic 0–100 urgency score."
    )
    expected_impact: str = Field(
        ..., description="Human-readable expected impact summary."
    )


# ---------------------------------------------------------------------------
# Portfolio summary KPIs
# ---------------------------------------------------------------------------


class PortfolioExecutionPackageSummary(BaseModel):
    """Portfolio-wide execution package KPI roll-up."""

    total_projects: int = Field(
        ..., description="Total projects in this portfolio pass."
    )
    ready_for_review_count: int = Field(
        ..., description="Projects with execution_readiness = ready_for_review."
    )
    blocked_count: int = Field(
        ..., description="Projects with execution_readiness = blocked_by_dependency."
    )
    caution_required_count: int = Field(
        ..., description="Projects with execution_readiness = caution_required."
    )
    insufficient_data_count: int = Field(
        ..., description="Projects with execution_readiness = insufficient_data."
    )


# ---------------------------------------------------------------------------
# Canonical portfolio response envelope
# ---------------------------------------------------------------------------


class PortfolioExecutionPackageResponse(BaseModel):
    """Portfolio execution package response (PR-V7-07).

    Aggregates project-level execution packages into a portfolio action view.
    All values are read-only — no records are mutated.

    Ordering for packages list:
      Primary   : execution_readiness (ready_for_review first, insufficient_data last)
      Secondary : urgency_score descending
      Tertiary  : project_name ascending (deterministic tie-break)
    """

    summary: PortfolioExecutionPackageSummary
    top_ready_actions: List[PortfolioPackagedInterventionCard] = Field(
        default_factory=list,
        description="Up to 5 projects that are ready_for_review, ordered by urgency_score desc.",
    )
    top_blocked_actions: List[PortfolioPackagedInterventionCard] = Field(
        default_factory=list,
        description="Up to 5 projects that are blocked_by_dependency, ordered by urgency_score desc.",
    )
    top_high_risk_packages: List[PortfolioPackagedInterventionCard] = Field(
        default_factory=list,
        description="Up to 5 projects that are caution_required, ordered by urgency_score desc.",
    )
    packages: List[PortfolioPackagedInterventionCard] = Field(
        default_factory=list,
        description=(
            "All project execution package cards ordered by readiness priority desc, "
            "urgency_score desc, project_name asc."
        ),
    )
