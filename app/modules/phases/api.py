"""
phases.api

CRUD API router for the Phase entity.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.phases.schemas import PhaseCreate, PhaseList, PhaseResponse, PhaseUpdate
from app.modules.phases.service import PhaseService

router = APIRouter(prefix="/phases", tags=["phases"])


def get_service(db: Session = Depends(get_db)) -> PhaseService:
    return PhaseService(db)


@router.post("", response_model=PhaseResponse, status_code=201)
def create_phase(
    data: PhaseCreate,
    service: Annotated[PhaseService, Depends(get_service)],
) -> PhaseResponse:
    """Create a new phase."""
    return service.create_phase(data)


@router.get("", response_model=PhaseList)
def list_phases(
    service: Annotated[PhaseService, Depends(get_service)],
    project_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> PhaseList:
    """List phases, optionally filtered by project."""
    return service.list_phases(project_id=project_id, skip=skip, limit=limit)


@router.get("/{phase_id}", response_model=PhaseResponse)
def get_phase(
    phase_id: str,
    service: Annotated[PhaseService, Depends(get_service)],
) -> PhaseResponse:
    """Get a phase by ID."""
    return service.get_phase(phase_id)


@router.patch("/{phase_id}", response_model=PhaseResponse)
def update_phase(
    phase_id: str,
    data: PhaseUpdate,
    service: Annotated[PhaseService, Depends(get_service)],
) -> PhaseResponse:
    """Update a phase."""
    return service.update_phase(phase_id, data)
