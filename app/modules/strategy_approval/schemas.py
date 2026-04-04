"""
strategy_approval.schemas

Typed Pydantic request and response contracts for the Strategy Approval
Workflow (PR-V7-08).

Schema hierarchy
----------------
  Request schemas (inbound):
    StrategyApprovalCreateRequest  — body for POST /projects/{id}/strategy-approval
    ApproveStrategyRequest         — body for POST /approvals/{id}/approve
    RejectStrategyRequest          — body for POST /approvals/{id}/reject

  Response schemas (outbound):
    StrategyApprovalResponse       — full approval record returned by all endpoints

All response schemas are read-only output models.
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Classification literals
# ---------------------------------------------------------------------------

ApprovalStatus = Literal["pending", "approved", "rejected"]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class StrategyApprovalCreateRequest(BaseModel):
    """Body for creating a new strategy approval request.

    Callers must supply verbatim snapshots of the recommended strategy and
    execution package at the time of the request.  These snapshots are stored
    immutably and form the audit trail for the decision.
    """

    strategy_snapshot: Dict[str, Any] = Field(
        ...,
        description="Verbatim snapshot of the recommended strategy output.",
    )
    execution_package_snapshot: Dict[str, Any] = Field(
        ...,
        description="Verbatim snapshot of the execution package output.",
    )


class ApproveStrategyRequest(BaseModel):
    """Body placeholder for approving a pending strategy approval request.

    The approve action requires no additional fields beyond authentication.
    This class is retained so the endpoint can accept an empty JSON body
    without FastAPI raising a validation error.
    """


class RejectStrategyRequest(BaseModel):
    """Body for rejecting a pending strategy approval request.

    A rejection reason is required — the decision must be documented.
    """

    rejection_reason: str = Field(
        ...,
        min_length=1,
        description="Required reason for rejecting the strategy.",
    )


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class StrategyApprovalResponse(BaseModel):
    """Full approval record returned by all strategy approval endpoints.

    The response includes the full snapshots so callers can reconstruct the
    context of the decision without a separate lookup.
    """

    id: str = Field(..., description="Unique approval record identifier.")
    project_id: str = Field(..., description="Project the approval belongs to.")
    status: ApprovalStatus = Field(
        ..., description="Current approval state: pending | approved | rejected."
    )
    strategy_snapshot: Optional[Dict[str, Any]] = Field(
        None,
        description="Snapshot of the recommended strategy at request time.",
    )
    execution_package_snapshot: Optional[Dict[str, Any]] = Field(
        None,
        description="Snapshot of the execution package at request time.",
    )
    approved_by_user_id: Optional[str] = Field(
        None,
        description="User ID of the approver (populated on approval).",
    )
    approved_at: Optional[datetime] = Field(
        None,
        description="UTC timestamp of the approval decision.",
    )
    rejection_reason: Optional[str] = Field(
        None,
        description="Rejection reason (populated on rejection).",
    )
    created_at: datetime = Field(..., description="UTC timestamp of record creation.")
    updated_at: datetime = Field(..., description="UTC timestamp of last update.")

    model_config = ConfigDict(from_attributes=True)
