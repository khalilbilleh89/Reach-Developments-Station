"""
scenario.api

REST API router for the Scenario Engine module.

All scenario creation, duplication, versioning, approval, archival, and
comparison passes through this router.  No scenario logic is permitted inside
other feature modules.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.scenario.financial_scenario_service import FinancialScenarioService
from app.modules.scenario.schemas import (
    FinancialScenarioCompareRequest,
    FinancialScenarioCompareResponse,
    FinancialScenarioRunCreate,
    FinancialScenarioRunList,
    FinancialScenarioRunResponse,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioCreate,
    ScenarioDuplicateRequest,
    ScenarioList,
    ScenarioResponse,
    ScenarioUpdate,
    ScenarioVersionCreate,
    ScenarioVersionList,
    ScenarioVersionResponse,
)
from app.modules.scenario.service import ScenarioService

router = APIRouter(
    prefix="/scenarios",
    tags=["scenarios"],
    dependencies=[Depends(get_current_user_payload)],
)


def get_service(db: Session = Depends(get_db)) -> ScenarioService:
    return ScenarioService(db)


def get_financial_service(db: Session = Depends(get_db)) -> FinancialScenarioService:
    return FinancialScenarioService(db)


# ---------------------------------------------------------------------------
# Scenario CRUD
# ---------------------------------------------------------------------------


@router.post("", response_model=ScenarioResponse, status_code=201)
def create_scenario(
    data: ScenarioCreate,
    service: Annotated[ScenarioService, Depends(get_service)],
) -> ScenarioResponse:
    """Create a new scenario. project_id and land_id are optional."""
    return service.create_scenario(data)


@router.get("", response_model=ScenarioList)
def list_scenarios(
    service: Annotated[ScenarioService, Depends(get_service)],
    source_type: Optional[str] = Query(default=None),
    project_id: Optional[str] = Query(default=None),
    land_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ScenarioList:
    """List scenarios with optional filters."""
    return service.list_scenarios(
        skip=skip,
        limit=limit,
        source_type=source_type,
        project_id=project_id,
        land_id=land_id,
        status_filter=status,
    )


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: str,
    service: Annotated[ScenarioService, Depends(get_service)],
) -> ScenarioResponse:
    """Get a scenario by ID."""
    return service.get_scenario(scenario_id)


@router.patch("/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(
    scenario_id: str,
    data: ScenarioUpdate,
    service: Annotated[ScenarioService, Depends(get_service)],
) -> ScenarioResponse:
    """Update scenario name, code, or notes."""
    return service.update_scenario(scenario_id, data)


# ---------------------------------------------------------------------------
# Duplication
# ---------------------------------------------------------------------------


@router.post("/{scenario_id}/duplicate", response_model=ScenarioResponse, status_code=201)
def duplicate_scenario(
    scenario_id: str,
    request: ScenarioDuplicateRequest,
    service: Annotated[ScenarioService, Depends(get_service)],
) -> ScenarioResponse:
    """Duplicate a scenario. The new scenario records lineage and resets to draft."""
    return service.duplicate_scenario(scenario_id, request)


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


@router.post("/{scenario_id}/versions", response_model=ScenarioVersionResponse, status_code=201)
def create_version(
    scenario_id: str,
    data: ScenarioVersionCreate,
    service: Annotated[ScenarioService, Depends(get_service)],
    payload: Annotated[dict, Depends(get_current_user_payload)],
) -> ScenarioVersionResponse:
    """Add a new version snapshot to a scenario.

    created_by is populated server-side from the authenticated user (JWT sub).
    """
    return service.create_version(scenario_id, data, created_by=payload.get("sub"))


@router.get("/{scenario_id}/versions", response_model=ScenarioVersionList)
def list_versions(
    scenario_id: str,
    service: Annotated[ScenarioService, Depends(get_service)],
) -> ScenarioVersionList:
    """List all versions of a scenario."""
    return service.list_versions(scenario_id)


@router.get("/{scenario_id}/versions/latest", response_model=ScenarioVersionResponse)
def get_latest_version(
    scenario_id: str,
    service: Annotated[ScenarioService, Depends(get_service)],
) -> ScenarioVersionResponse:
    """Get the latest version of a scenario."""
    return service.get_latest_version(scenario_id)


# ---------------------------------------------------------------------------
# Approval / archival
# ---------------------------------------------------------------------------


@router.post("/{scenario_id}/approve", response_model=ScenarioResponse)
def approve_scenario(
    scenario_id: str,
    service: Annotated[ScenarioService, Depends(get_service)],
) -> ScenarioResponse:
    """Approve a scenario. The latest version is marked as approved."""
    return service.approve_scenario(scenario_id)


@router.post("/{scenario_id}/archive", response_model=ScenarioResponse)
def archive_scenario(
    scenario_id: str,
    service: Annotated[ScenarioService, Depends(get_service)],
) -> ScenarioResponse:
    """Archive a scenario."""
    return service.archive_scenario(scenario_id)


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


@router.post("/compare", response_model=ScenarioCompareResponse)
def compare_scenarios(
    request: ScenarioCompareRequest,
    service: Annotated[ScenarioService, Depends(get_service)],
) -> ScenarioCompareResponse:
    """Return side-by-side comparison metadata for a list of scenario IDs."""
    return service.compare_scenarios(request)


# ---------------------------------------------------------------------------
# Financial scenario runs
# ---------------------------------------------------------------------------


@router.post(
    "/{scenario_id}/financial-runs",
    response_model=FinancialScenarioRunResponse,
    status_code=201,
)
def create_financial_run(
    scenario_id: str,
    payload: FinancialScenarioRunCreate,
    service: Annotated[FinancialScenarioService, Depends(get_financial_service)],
) -> FinancialScenarioRunResponse:
    """Create and execute a financial scenario run.

    Merges optional override values on top of baseline assumptions, delegates
    all financial calculations to the Calculation Engine via the Financial
    Scenario Engine, and persists the result.
    """
    return service.create_run(scenario_id, payload)


@router.get(
    "/{scenario_id}/financial-runs",
    response_model=FinancialScenarioRunList,
)
def list_financial_runs(
    scenario_id: str,
    service: Annotated[FinancialScenarioService, Depends(get_financial_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> FinancialScenarioRunList:
    """List all financial scenario runs for a given scenario."""
    return service.list_runs(scenario_id, skip=skip, limit=limit)


@router.get(
    "/{scenario_id}/financial-runs/{run_id}",
    response_model=FinancialScenarioRunResponse,
)
def get_financial_run(
    scenario_id: str,
    run_id: str,
    service: Annotated[FinancialScenarioService, Depends(get_financial_service)],
) -> FinancialScenarioRunResponse:
    """Get a specific financial scenario run by ID."""
    return service.get_run(scenario_id, run_id)


@router.delete("/{scenario_id}/financial-runs/{run_id}", status_code=204)
def delete_financial_run(
    scenario_id: str,
    run_id: str,
    service: Annotated[FinancialScenarioService, Depends(get_financial_service)],
) -> None:
    """Delete a financial scenario run."""
    service.delete_run(scenario_id, run_id)


# ---------------------------------------------------------------------------
# Financial scenario run comparison
# ---------------------------------------------------------------------------


@router.post(
    "/financial-runs/compare",
    response_model=FinancialScenarioCompareResponse,
)
def compare_financial_runs(
    request: FinancialScenarioCompareRequest,
    service: Annotated[FinancialScenarioService, Depends(get_financial_service)],
) -> FinancialScenarioCompareResponse:
    """Compare multiple financial scenario runs side-by-side.

    The first run ID in the list is treated as the baseline.  Delta metrics
    for all other runs are expressed relative to the baseline.
    """
    return service.compare_runs(request)
