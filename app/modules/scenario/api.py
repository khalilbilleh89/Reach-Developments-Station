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
from app.modules.scenario.schemas import (
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
