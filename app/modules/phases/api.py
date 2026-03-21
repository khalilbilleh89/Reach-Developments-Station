"""
phases.api

CRUD API router for the Phase entity.

Provides two route groups:
  /api/v1/projects/{project_id}/phases    — project-scoped phase listing and creation
  /api/v1/projects/{project_id}/lifecycle — project lifecycle view
  /api/v1/phases/{phase_id}               — individual phase operations (get, update, delete)
  /api/v1/phases/{phase_id}/advance       — lifecycle advancement
  /api/v1/phases/{phase_id}/reopen        — reopen a completed phase
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.phases.schemas import (
    PhaseCreate,
    PhaseCreateForProject,
    PhaseList,
    PhaseResponse,
    PhaseUpdate,
    ProjectLifecycle,
)
from app.modules.phases.service import PhaseService

router = APIRouter(tags=["phases"], dependencies=[Depends(get_current_user_payload)])


def get_service(db: Session = Depends(get_db)) -> PhaseService:
    return PhaseService(db)


# ── Project-scoped endpoints ────────────────────────────────────────────────

@router.get("/projects/{project_id}/phases", response_model=PhaseList)
def list_phases_by_project(
    project_id: str,
    service: Annotated[PhaseService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> PhaseList:
    """List all phases for a specific project."""
    return service.list_phases_by_project(project_id=project_id, skip=skip, limit=limit)


@router.post("/projects/{project_id}/phases", response_model=PhaseResponse, status_code=201)
def create_phase_for_project(
    project_id: str,
    data: PhaseCreateForProject,
    service: Annotated[PhaseService, Depends(get_service)],
) -> PhaseResponse:
    """Create a new phase within a specific project."""
    return service.create_phase_for_project(project_id, data)


@router.get("/projects/{project_id}/lifecycle", response_model=ProjectLifecycle)
def get_project_lifecycle(
    project_id: str,
    service: Annotated[PhaseService, Depends(get_service)],
) -> ProjectLifecycle:
    """Get the ordered lifecycle view for a project, showing phase progression."""
    return service.get_project_lifecycle(project_id)


# ── Generic phase endpoints ─────────────────────────────────────────────────

@router.post("/phases", response_model=PhaseResponse, status_code=201)
def create_phase(
    data: PhaseCreate,
    service: Annotated[PhaseService, Depends(get_service)],
) -> PhaseResponse:
    """Create a new phase."""
    return service.create_phase(data)


@router.get("/phases", response_model=PhaseList)
def list_phases(
    service: Annotated[PhaseService, Depends(get_service)],
    project_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> PhaseList:
    """List phases, optionally filtered by project."""
    return service.list_phases(project_id=project_id, skip=skip, limit=limit)


@router.get("/phases/{phase_id}", response_model=PhaseResponse)
def get_phase(
    phase_id: str,
    service: Annotated[PhaseService, Depends(get_service)],
) -> PhaseResponse:
    """Get a phase by ID."""
    return service.get_phase(phase_id)


@router.patch("/phases/{phase_id}", response_model=PhaseResponse)
def update_phase(
    phase_id: str,
    data: PhaseUpdate,
    service: Annotated[PhaseService, Depends(get_service)],
) -> PhaseResponse:
    """Update a phase."""
    return service.update_phase(phase_id, data)


@router.post("/phases/{phase_id}/advance", response_model=PhaseResponse)
def advance_phase(
    phase_id: str,
    service: Annotated[PhaseService, Depends(get_service)],
) -> PhaseResponse:
    """Advance the lifecycle: mark the phase as completed and activate the next phase."""
    return service.advance_project_phase(phase_id)


@router.post("/phases/{phase_id}/reopen", response_model=PhaseResponse)
def reopen_phase(
    phase_id: str,
    service: Annotated[PhaseService, Depends(get_service)],
) -> PhaseResponse:
    """Explicitly reopen a completed phase back to active status."""
    return service.reopen_phase(phase_id)


@router.delete("/phases/{phase_id}", status_code=204)
def delete_phase(
    phase_id: str,
    service: Annotated[PhaseService, Depends(get_service)],
) -> Response:
    """Delete a phase."""
    service.delete_phase(phase_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
