"""
feasibility.api

REST API router for the Feasibility Engine module.
Endpoints under /feasibility/runs.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.concept_design.schemas import SeedConceptFromFeasibilityResponse
from app.modules.concept_design.service import ConceptDesignService
from app.modules.feasibility.schemas import (
    FeasibilityAssumptionsCreate,
    FeasibilityAssumptionsResponse,
    FeasibilityAssumptionsUpdate,
    FeasibilityConstructionCostContextResponse,
    FeasibilityLineageResponse,
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


def get_concept_service(db: Session = Depends(get_db)) -> ConceptDesignService:
    return ConceptDesignService(db)


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
    scenario_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> FeasibilityRunList:
    """List feasibility runs, optionally filtered by project and/or scenario."""
    return service.list_feasibility_runs(project_id=project_id, scenario_id=scenario_id, skip=skip, limit=limit)


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


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(
    run_id: str,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> Response:
    """Delete a feasibility run and its owned assumptions and result.

    Returns HTTP 204 No Content on success.
    Returns HTTP 404 if the run does not exist.
    """
    service.delete_feasibility_run(run_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Reverse-seed concept from feasibility run — PR-CONCEPT-064
# ---------------------------------------------------------------------------

@router.post(
    "/runs/{run_id}/create-concept",
    response_model=SeedConceptFromFeasibilityResponse,
    status_code=201,
)
def create_concept_from_feasibility_run(
    run_id: str,
    concept_service: Annotated[ConceptDesignService, Depends(get_concept_service)],
) -> SeedConceptFromFeasibilityResponse:
    """Create a new concept option seeded from a feasibility run.

    Closes the bidirectional design-finance loop:
      Concept → Feasibility → Concept

    The new concept option is created in ``draft`` status with a name derived
    from the run's ``scenario_name``.  The concept inherits the run's
    ``scenario_id`` and ``project_id`` (when set), and records
    ``source_feasibility_run_id`` for deterministic lineage.

    Returns HTTP 404 when the feasibility run does not exist.
    """
    return concept_service.create_from_feasibility_run(run_id)


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


@router.patch("/runs/{run_id}/assumptions", response_model=FeasibilityAssumptionsResponse)
def patch_assumptions(
    run_id: str,
    data: FeasibilityAssumptionsUpdate,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityAssumptionsResponse:
    """Partially update assumptions for a feasibility run.

    Only fields present in the request body are updated; omitted fields retain
    their existing values.  Returns 404 if no assumptions record exists yet —
    use POST to create the initial assumptions first.
    """
    return service.patch_assumptions(run_id, data)


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
    calculation into a single request for scenario-based evaluation.

    Note: run creation, assumption upsert, and result persistence are sequential
    DB operations.  If the calculation step fails after earlier steps have
    committed, the run and assumptions will remain.  Retry via
    POST /feasibility/runs/{id}/calculate once the error is resolved.
    """
    return service.run_feasibility_for_scenario(data)


@router.get("/{run_id}", response_model=FeasibilityResultResponse)
def get_feasibility_result_by_run(
    run_id: str,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityResultResponse:
    """Get the calculated feasibility result for a run.

    Returns the FeasibilityResult record (financial metrics + viability decision)
    for the given run_id.  Returns 404 if the run does not exist or has not been
    calculated yet.  This is a convenience alias for
    GET /feasibility/runs/{run_id}/results.
    """
    return service.get_feasibility_result(run_id)



# ---------------------------------------------------------------------------
# Lineage endpoint — PR-CONCEPT-065
# ---------------------------------------------------------------------------

@router.get(
    "/runs/{run_id}/lineage",
    response_model=FeasibilityLineageResponse,
)
def get_feasibility_run_lineage(
    run_id: str,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityLineageResponse:
    """Return lifecycle traceability for a feasibility run.

    Surfaces:
    - the concept option that seeded this run (upstream lineage)
    - all concept options reverse-seeded from this run (downstream lineage)
    - linked project context

    Returns a partial lineage (with empty lists / null IDs) for runs that
    were created manually without seeding context.

    Returns HTTP 404 when the feasibility run does not exist.
    """
    return service.get_feasibility_run_lineage(run_id)


# ---------------------------------------------------------------------------
# Construction cost context — PR-V6-10
# ---------------------------------------------------------------------------

@router.get(
    "/runs/{run_id}/construction-cost-context",
    response_model=FeasibilityConstructionCostContextResponse,
)
def get_construction_cost_context(
    run_id: str,
    service: Annotated[FeasibilityService, Depends(get_service)],
) -> FeasibilityConstructionCostContextResponse:
    """Return a read-only construction cost context for a feasibility run.

    Surfaces recorded project construction cost totals alongside the
    feasibility-side assumed construction cost so reviewers can compare
    both without any auto-recalculation.

    The response is always null-safe:
    - run has no project → note explains; cost fields are null
    - project has no cost records → note explains; recorded fields are null
    - no assumptions defined → note explains; assumed_construction_cost is null
    - both sides present → variance_amount and variance_pct are populated

    Returns HTTP 404 when the feasibility run does not exist.
    """
    return service.get_construction_cost_context(run_id)
