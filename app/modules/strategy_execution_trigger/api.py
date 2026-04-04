"""
strategy_execution_trigger.api

Execution Trigger & Handoff Records API router (PR-V7-09).

Endpoints:
  POST /api/v1/projects/{project_id}/strategy-execution-trigger
    — Create a formal execution handoff trigger for an approved project strategy.
  GET  /api/v1/projects/{project_id}/strategy-execution-trigger
    — Return the latest execution trigger for a project (null if none exists).
  POST /api/v1/execution-triggers/{trigger_id}/start
    — Transition a triggered execution to in_progress.
  POST /api/v1/execution-triggers/{trigger_id}/complete
    — Transition an in_progress execution to completed.
  POST /api/v1/execution-triggers/{trigger_id}/cancel
    — Cancel a triggered or in_progress execution.
  GET  /api/v1/portfolio/execution-triggers
    — Return portfolio-level execution trigger summary.

Forbidden
---------
  Auto-execution endpoints
  Mutation of project, strategy, pricing, or phasing records
  Direct trigger creation without a prior approved strategy approval
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.strategy_execution_trigger.schemas import (
    CancelExecutionTriggerRequest,
    PortfolioExecutionTriggerSummaryResponse,
    StrategyExecutionTriggerResponse,
)
from app.modules.strategy_execution_trigger.service import (
    StrategyExecutionTriggerService,
)

projects_router = APIRouter(
    prefix="/projects",
    tags=["Strategy Execution Trigger"],
    dependencies=[Depends(get_current_user_payload)],
)

triggers_router = APIRouter(
    prefix="/execution-triggers",
    tags=["Strategy Execution Trigger"],
    dependencies=[Depends(get_current_user_payload)],
)

portfolio_router = APIRouter(
    prefix="/portfolio",
    tags=["Strategy Execution Trigger"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]
UserPayloadDep = Annotated[dict, Depends(get_current_user_payload)]


def _service(db: DbDep) -> StrategyExecutionTriggerService:
    return StrategyExecutionTriggerService(db)


ServiceDep = Annotated[StrategyExecutionTriggerService, Depends(_service)]


# ---------------------------------------------------------------------------
# Project-scoped endpoints
# ---------------------------------------------------------------------------


@projects_router.post(
    "/{project_id}/strategy-execution-trigger",
    response_model=StrategyExecutionTriggerResponse,
    status_code=201,
)
def create_execution_trigger(
    project_id: str,
    service: ServiceDep,
    user_payload: UserPayloadDep,
) -> StrategyExecutionTriggerResponse:
    """Create a formal execution handoff trigger for an approved project strategy.

    Captures verbatim snapshots from the latest approved strategy approval.
    Snapshots are stored immutably and form the audit trail for the handoff.

    Returns HTTP 401 when the authenticated user identity (sub) is absent.
    Returns HTTP 404 when the project does not exist.
    Returns HTTP 409 when an active execution trigger already exists for the project.
    Returns HTTP 422 when the latest strategy approval is not 'approved'.
    """
    triggered_by_user_id: Optional[str] = user_payload.get("sub")
    if not triggered_by_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user identity (sub) is missing from token.",
        )
    trigger = service.create_execution_trigger(
        project_id=project_id,
        triggered_by_user_id=triggered_by_user_id,
    )
    return StrategyExecutionTriggerResponse.model_validate(trigger)


@projects_router.get(
    "/{project_id}/strategy-execution-trigger",
    response_model=Optional[StrategyExecutionTriggerResponse],
)
def get_latest_execution_trigger(
    project_id: str,
    service: ServiceDep,
) -> Optional[StrategyExecutionTriggerResponse]:
    """Return the latest execution trigger record for a project.

    Returns null (HTTP 200 with null body) when no trigger has been created
    for the project yet.
    Returns HTTP 404 when the project does not exist.
    """
    trigger = service.get_latest_execution_trigger(project_id)
    if trigger is None:
        return None
    return StrategyExecutionTriggerResponse.model_validate(trigger)


# ---------------------------------------------------------------------------
# Trigger action endpoints
# ---------------------------------------------------------------------------


@triggers_router.post(
    "/{trigger_id}/start",
    response_model=StrategyExecutionTriggerResponse,
)
def start_execution_trigger(
    trigger_id: str,
    service: ServiceDep,
    user_payload: UserPayloadDep,
) -> StrategyExecutionTriggerResponse:
    """Transition a triggered execution to in_progress.

    Returns HTTP 404 when the trigger record does not exist.
    Returns HTTP 422 when the trigger is not in 'triggered' state.
    """
    user_id: str = user_payload.get("sub") or "unknown"
    trigger = service.mark_in_progress(trigger_id, user_id)
    return StrategyExecutionTriggerResponse.model_validate(trigger)


@triggers_router.post(
    "/{trigger_id}/complete",
    response_model=StrategyExecutionTriggerResponse,
)
def complete_execution_trigger(
    trigger_id: str,
    service: ServiceDep,
    user_payload: UserPayloadDep,
) -> StrategyExecutionTriggerResponse:
    """Transition an in_progress execution to completed.

    Returns HTTP 404 when the trigger record does not exist.
    Returns HTTP 422 when the trigger is not in 'in_progress' state.
    """
    user_id: str = user_payload.get("sub") or "unknown"
    trigger = service.mark_completed(trigger_id, user_id)
    return StrategyExecutionTriggerResponse.model_validate(trigger)


@triggers_router.post(
    "/{trigger_id}/cancel",
    response_model=StrategyExecutionTriggerResponse,
)
def cancel_execution_trigger(
    trigger_id: str,
    body: CancelExecutionTriggerRequest,
    service: ServiceDep,
    user_payload: UserPayloadDep,
) -> StrategyExecutionTriggerResponse:
    """Cancel a triggered or in_progress execution.

    A cancellation reason is required.

    Returns HTTP 404 when the trigger record does not exist.
    Returns HTTP 422 when the trigger is in a terminal state (completed or cancelled).
    """
    user_id: str = user_payload.get("sub") or "unknown"
    trigger = service.cancel_trigger(trigger_id, user_id, body.cancellation_reason)
    return StrategyExecutionTriggerResponse.model_validate(trigger)


# ---------------------------------------------------------------------------
# Portfolio endpoint
# ---------------------------------------------------------------------------


@portfolio_router.get(
    "/execution-triggers",
    response_model=PortfolioExecutionTriggerSummaryResponse,
)
def get_portfolio_execution_triggers(
    service: ServiceDep,
) -> PortfolioExecutionTriggerSummaryResponse:
    """Return portfolio-level execution trigger summary.

    Provides:
      - Status counts (triggered, in_progress, completed, cancelled)
      - Active execution handoffs with project names
      - Projects with approved strategies awaiting execution trigger
    """
    return service.get_portfolio_trigger_summary()
