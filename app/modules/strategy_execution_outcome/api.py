"""
strategy_execution_outcome.api

Execution Outcome Capture & Feedback Loop Closure API router (PR-V7-10).

Endpoints:
  POST /api/v1/execution-triggers/{trigger_id}/outcome
    — Record the realized execution outcome for a trigger.
  GET  /api/v1/projects/{project_id}/strategy-execution-outcome
    — Return the latest execution outcome state for a project.
  GET  /api/v1/portfolio/execution-outcomes
    — Return portfolio-level execution outcome summary.

Forbidden
---------
  Direct project-data mutation endpoints.
  Pricing or phasing write endpoints.
  Automatic application of outcome changes to source records.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.strategy_execution_outcome.schemas import (
    PortfolioExecutionOutcomeSummaryResponse,
    ProjectExecutionOutcomeResponse,
    RecordExecutionOutcomeRequest,
    StrategyExecutionOutcomeResponse,
)
from app.modules.strategy_execution_outcome.service import (
    StrategyExecutionOutcomeService,
    _build_outcome_response,
)

triggers_router = APIRouter(
    prefix="/execution-triggers",
    tags=["Strategy Execution Outcome"],
    dependencies=[Depends(get_current_user_payload)],
)

projects_router = APIRouter(
    prefix="/projects",
    tags=["Strategy Execution Outcome"],
    dependencies=[Depends(get_current_user_payload)],
)

portfolio_router = APIRouter(
    prefix="/portfolio",
    tags=["Strategy Execution Outcome"],
    dependencies=[Depends(get_current_user_payload)],
)

DbDep = Annotated[Session, Depends(get_db)]
UserPayloadDep = Annotated[dict, Depends(get_current_user_payload)]


def _service(db: DbDep) -> StrategyExecutionOutcomeService:
    return StrategyExecutionOutcomeService(db)


ServiceDep = Annotated[StrategyExecutionOutcomeService, Depends(_service)]


# ---------------------------------------------------------------------------
# Outcome recording endpoint
# ---------------------------------------------------------------------------


@triggers_router.post(
    "/{trigger_id}/outcome",
    response_model=StrategyExecutionOutcomeResponse,
    status_code=201,
)
def record_execution_outcome(
    trigger_id: str,
    body: RecordExecutionOutcomeRequest,
    service: ServiceDep,
    user_payload: UserPayloadDep,
) -> StrategyExecutionOutcomeResponse:
    """Record the realized execution outcome for an in-progress or completed trigger.

    If a prior outcome has been recorded for this trigger, it will be marked
    'superseded' and the new outcome becomes the authoritative record.

    Returns HTTP 401 when the authenticated user identity (sub) is absent.
    Returns HTTP 404 when the trigger does not exist.
    Returns HTTP 422 when the trigger is not in 'in_progress' or 'completed' state.
    """
    recorded_by: Optional[str] = user_payload.get("sub")
    if not recorded_by:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user identity (sub) is missing from token.",
        )

    outcome = service.record_execution_outcome(
        trigger_id=trigger_id,
        payload=body,
        recorded_by_user_id=recorded_by,
    )

    # Reload trigger for comparison block derivation.
    trigger = service._repo.get_trigger(trigger_id)
    return _build_outcome_response(outcome, trigger)


# ---------------------------------------------------------------------------
# Project-scoped endpoint
# ---------------------------------------------------------------------------


@projects_router.get(
    "/{project_id}/strategy-execution-outcome",
    response_model=ProjectExecutionOutcomeResponse,
)
def get_project_execution_outcome(
    project_id: str,
    service: ServiceDep,
) -> ProjectExecutionOutcomeResponse:
    """Return the latest execution outcome state for a project.

    Returns the most recent trigger context, eligibility flag, and the latest
    recorded outcome (null when none has been recorded yet).

    Returns HTTP 404 when the project does not exist.
    """
    return service.get_project_execution_outcome(project_id)


# ---------------------------------------------------------------------------
# Portfolio endpoint
# ---------------------------------------------------------------------------


@portfolio_router.get(
    "/execution-outcomes",
    response_model=PortfolioExecutionOutcomeSummaryResponse,
)
def get_portfolio_execution_outcomes(
    service: ServiceDep,
) -> PortfolioExecutionOutcomeSummaryResponse:
    """Return portfolio-level execution outcome summary.

    Provides:
      - Outcome result counts (matched_strategy, partially_matched, diverged, etc.)
      - Recent recorded outcomes with project names
      - Projects with completed triggers awaiting outcome recording
    """
    return service.build_portfolio_execution_outcomes()
