"""
feasibility.api

REST API router for the Feasibility Engine module.
Endpoints under /feasibility/runs.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.feasibility.schemas import (
    FeasibilityAssumptionsCreate,
    FeasibilityAssumptionsResponse,
    FeasibilityResultResponse,
    FeasibilityRunCreate,
    FeasibilityRunList,
    FeasibilityRunRequest,
    FeasibilityRunResponse,
    FeasibilityRunUpdate,
)
from app.modules.feasibility.service import FeasibilityService

router = APIRouter(prefix="/feasibility", tags=["feasibility"], dependencies=[Depends(get_current_user_payload)])


def get_service(db: Session = Depends(get_db)) -> FeasibilityService:
    return FeasibilityService(db)


# ---------------------------------------------------------------------------
# Run endpoints
# ---------------------------------------------------------------------------

@router.post("/runs", response_model=FeasibilityRunResponse, status_code=201)
def create_run(
    data: FeasibilityRunCreate,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityRunResponse:
    """Create a new feasibility scenario run. project_id is optional — runs may be created before any project exists."""
    return service.create_feasibility_run(data)


@router.get("/runs", response_model=FeasibilityRunList)
def list_runs(
    service: Annotated[FeasibilityService, Depends(get_service)],
    project_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> FeasibilityRunList:
    """List feasibility runs, optionally filtered by project."""
    return service.list_feasibility_runs(project_id=project_id, skip=skip, limit=limit)


@router.get("/runs/{run_id}", response_model=FeasibilityRunResponse)
def get_run(
    run_id: str,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityRunResponse:
    """Get a feasibility run by ID."""
    return service.get_feasibility_run(run_id)


@router.patch("/runs/{run_id}", response_model=FeasibilityRunResponse)
def update_run(
    run_id: str,
    data: FeasibilityRunUpdate,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityRunResponse:
    """Update a feasibility run's metadata."""
    return service.update_feasibility_run(run_id, data)


# ---------------------------------------------------------------------------
# Assumptions endpoints
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/assumptions", response_model=FeasibilityAssumptionsResponse, status_code=201)
def upsert_assumptions(
    run_id: str,
    data: FeasibilityAssumptionsCreate,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityAssumptionsResponse:
    """Create or replace assumptions for a feasibility run."""
    return service.update_assumptions(run_id, data)


@router.get("/runs/{run_id}/assumptions", response_model=FeasibilityAssumptionsResponse)
def get_assumptions(
    run_id: str,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityAssumptionsResponse:
    """Get the assumptions for a feasibility run."""
    return service.get_assumptions(run_id)


# ---------------------------------------------------------------------------
# Calculation and result endpoints
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/calculate", response_model=FeasibilityResultResponse, status_code=200)
def calculate(
    run_id: str,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityResultResponse:
    """Execute the feasibility calculation for a run and persist results."""
    return service.run_feasibility_calculation(run_id)


@router.get("/runs/{run_id}/results", response_model=FeasibilityResultResponse)
def get_results(
    run_id: str,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityResultResponse:
    """Get the calculated feasibility results for a run."""
    return service.get_feasibility_result(run_id)


# ---------------------------------------------------------------------------
# Convenience endpoints
# ---------------------------------------------------------------------------

@router.post("/run", response_model=FeasibilityResultResponse, status_code=201)
def run_feasibility(
    data: FeasibilityRunRequest,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityResultResponse:
    """Create a run, set assumptions, execute calculation, and return results in one request.

    This convenience endpoint combines run creation, assumption setting, and
    calculation into a single atomic operation for scenario-based evaluation.
    """
    return service.run_feasibility_for_scenario(data)


@router.get("/{run_id}", response_model=FeasibilityResultResponse)
def get_feasibility_result_by_run(
    run_id: str,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityResultResponse:
    """Get the calculated feasibility results for a run (convenience alias)."""
    return service.get_feasibility_result(run_id)

