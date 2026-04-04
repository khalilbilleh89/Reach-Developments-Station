"""
strategy_approval.api

Strategy Review & Approval Workflow API router (PR-V7-08).

Endpoints:
  POST /api/v1/projects/{project_id}/strategy-approval
    — Create a new pending approval request for a project strategy.
  POST /api/v1/approvals/{approval_id}/approve
    — Approve a pending strategy approval request.
  POST /api/v1/approvals/{approval_id}/reject
    — Reject a pending strategy approval request.
  GET  /api/v1/projects/{project_id}/strategy-approval
    — Return the latest approval record for a project (null if none exists).

Forbidden
---------
  Execution endpoints
  Mutation of project, strategy, or execution-package records
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.strategy_approval.schemas import (
    ApproveStrategyRequest,
    RejectStrategyRequest,
    StrategyApprovalCreateRequest,
    StrategyApprovalResponse,
)
from app.modules.strategy_approval.service import StrategyApprovalService

projects_router = APIRouter(
    prefix="/projects",
    tags=["Strategy Approval"],
    dependencies=[Depends(get_current_user_payload)],
)

approvals_router = APIRouter(
    prefix="/approvals",
    tags=["Strategy Approval"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]
UserPayloadDep = Annotated[dict, Depends(get_current_user_payload)]


def _service(db: DbDep) -> StrategyApprovalService:
    return StrategyApprovalService(db)


ServiceDep = Annotated[StrategyApprovalService, Depends(_service)]


# ---------------------------------------------------------------------------
# Project-scoped endpoints
# ---------------------------------------------------------------------------


@projects_router.post(
    "/{project_id}/strategy-approval",
    response_model=StrategyApprovalResponse,
    status_code=201,
)
def create_approval_request(
    project_id: str,
    body: StrategyApprovalCreateRequest,
    service: ServiceDep,
) -> StrategyApprovalResponse:
    """Create a new pending strategy approval request for a project.

    Captures verbatim snapshots of the recommended strategy and execution
    package at the time of the request.  These snapshots are stored
    immutably and form the audit trail for the decision.

    Returns HTTP 404 when the project does not exist.
    Returns HTTP 409 when a pending approval already exists for the project.
    """
    approval = service.create_approval_request(
        project_id=project_id,
        strategy_snapshot=body.strategy_snapshot,
        execution_package_snapshot=body.execution_package_snapshot,
    )
    return StrategyApprovalResponse.model_validate(approval)


@projects_router.get(
    "/{project_id}/strategy-approval",
    response_model=Optional[StrategyApprovalResponse],
)
def get_latest_approval(
    project_id: str,
    service: ServiceDep,
) -> Optional[StrategyApprovalResponse]:
    """Return the latest approval record for a project.

    Returns null (HTTP 200 with null body) when no approval has been
    requested for the project yet.
    Returns HTTP 404 when the project does not exist.
    """
    approval = service.get_latest_approval(project_id)
    if approval is None:
        return None
    return StrategyApprovalResponse.model_validate(approval)


# ---------------------------------------------------------------------------
# Approval action endpoints
# ---------------------------------------------------------------------------


@approvals_router.post(
    "/{approval_id}/approve",
    response_model=StrategyApprovalResponse,
)
def approve_strategy(
    approval_id: str,
    body: ApproveStrategyRequest,
    service: ServiceDep,
    user_payload: UserPayloadDep,
) -> StrategyApprovalResponse:
    """Approve a pending strategy approval request.

    Transitions the approval from pending → approved and records the
    approving user ID and timestamp.

    Returns HTTP 404 when the approval record does not exist.
    Returns HTTP 422 when the approval is not in pending state.
    """
    approved_by_user_id: str = user_payload.get("sub", "unknown")
    approval = service.approve_strategy(
        approval_id=approval_id,
        approved_by_user_id=approved_by_user_id,
    )
    return StrategyApprovalResponse.model_validate(approval)


@approvals_router.post(
    "/{approval_id}/reject",
    response_model=StrategyApprovalResponse,
)
def reject_strategy(
    approval_id: str,
    body: RejectStrategyRequest,
    service: ServiceDep,
) -> StrategyApprovalResponse:
    """Reject a pending strategy approval request.

    Transitions the approval from pending → rejected and stores the
    rejection reason.

    Returns HTTP 404 when the approval record does not exist.
    Returns HTTP 422 when the approval is not in pending state.
    """
    approval = service.reject_strategy(
        approval_id=approval_id,
        rejection_reason=body.rejection_reason,
    )
    return StrategyApprovalResponse.model_validate(approval)
