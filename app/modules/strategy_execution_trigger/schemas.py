"""
strategy_execution_trigger.schemas

Typed Pydantic request and response contracts for the Strategy Execution
Trigger module (PR-V7-09).

Schema hierarchy
----------------
  Request schemas (inbound):
    CancelExecutionTriggerRequest  — body for POST /execution-triggers/{id}/cancel

  Response schemas (outbound):
    StrategyExecutionTriggerResponse      — full trigger record
    PortfolioTriggerEntry                 — trigger record with project name
    PortfolioProjectEntry                 — project awaiting trigger
    PortfolioExecutionTriggerSummaryResponse — portfolio-level summary

All response schemas are read-only output models.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Classification literals
# ---------------------------------------------------------------------------

ExecutionTriggerStatus = Literal["triggered", "in_progress", "completed", "cancelled"]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CancelExecutionTriggerRequest(BaseModel):
    """Body for cancelling an active execution trigger.

    A cancellation reason is required — the decision must be documented.
    """

    cancellation_reason: str = Field(
        ...,
        min_length=1,
        description="Required reason for cancelling the execution trigger.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class StrategyExecutionTriggerResponse(BaseModel):
    """Full execution trigger record returned by project-scoped endpoints.

    The response includes immutable snapshots so callers can reconstruct
    the approved strategy context at the time of handoff without a separate
    lookup.
    """

    id: str = Field(..., description="Unique trigger record identifier.")
    project_id: str = Field(..., description="Project the trigger belongs to.")
    approval_id: Optional[str] = Field(
        None,
        description="Approval record that authorised this trigger (null if approval deleted).",
    )
    status: ExecutionTriggerStatus = Field(
        ...,
        description="Current execution lifecycle state: triggered | in_progress | completed | cancelled.",
    )
    triggered_by_user_id: str = Field(
        ...,
        description="User ID of the person who triggered the handoff.",
    )
    triggered_at: datetime = Field(
        ...,
        description="UTC timestamp when the trigger was created.",
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="UTC timestamp of execution completion (populated on completion).",
    )
    cancelled_at: Optional[datetime] = Field(
        None,
        description="UTC timestamp of cancellation (populated on cancellation).",
    )
    cancellation_reason: Optional[str] = Field(
        None,
        description="Cancellation reason (populated on cancellation).",
    )
    strategy_snapshot: Optional[Dict[str, Any]] = Field(
        None,
        description="Immutable snapshot of the approved strategy at trigger time.",
    )
    execution_package_snapshot: Optional[Dict[str, Any]] = Field(
        None,
        description="Immutable snapshot of the execution package at trigger time.",
    )
    created_at: datetime = Field(..., description="UTC timestamp of record creation.")
    updated_at: datetime = Field(..., description="UTC timestamp of last update.")

    model_config = ConfigDict(from_attributes=True)


class PortfolioTriggerEntry(BaseModel):
    """Portfolio-level entry pairing a trigger record with its project name."""

    project_id: str = Field(..., description="Project identifier.")
    project_name: str = Field(..., description="Project display name.")
    trigger: StrategyExecutionTriggerResponse = Field(
        ..., description="Active trigger record for this project."
    )


class PortfolioProjectEntry(BaseModel):
    """Portfolio-level entry for a project awaiting execution trigger."""

    project_id: str = Field(..., description="Project identifier.")
    project_name: str = Field(..., description="Project display name.")


class PortfolioExecutionTriggerSummaryResponse(BaseModel):
    """Portfolio-level execution trigger summary.

    Provides status counts, active handoff records, and projects that have
    an approved strategy but have not yet been formally triggered.
    """

    triggered_count: int = Field(
        ..., description="Number of execution triggers in 'triggered' state."
    )
    in_progress_count: int = Field(
        ..., description="Number of execution triggers in 'in_progress' state."
    )
    completed_count: int = Field(
        ..., description="Number of execution triggers in 'completed' state."
    )
    cancelled_count: int = Field(
        ..., description="Number of execution triggers in 'cancelled' state."
    )
    awaiting_trigger_count: int = Field(
        ...,
        description=(
            "Number of projects with an approved strategy that have not yet "
            "been formally triggered for execution."
        ),
    )
    active_triggers: List[PortfolioTriggerEntry] = Field(
        default_factory=list,
        description="Active execution handoffs (triggered or in_progress), with project names.",
    )
    awaiting_trigger_projects: List[PortfolioProjectEntry] = Field(
        default_factory=list,
        description="Projects with an approved strategy awaiting execution trigger.",
    )
