"""
buildings.api

CRUD API router for the Building entity.

Provides two route groups:
  /api/v1/phases/{phase_id}/buildings  — phase-scoped building listing and creation
  /api/v1/buildings/{building_id}      — individual building operations (get, update, delete)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.buildings.schemas import BuildingCreateForPhase, BuildingList, BuildingResponse, BuildingUpdate
from app.modules.buildings.service import BuildingService

router = APIRouter(tags=["buildings"])


def get_service(db: Session = Depends(get_db)) -> BuildingService:
    return BuildingService(db)


# ── Phase-scoped endpoints ───────────────────────────────────────────────────

@router.get("/phases/{phase_id}/buildings", response_model=BuildingList)
def list_buildings_by_phase(
    phase_id: str,
    service: Annotated[BuildingService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> BuildingList:
    """List all buildings for a specific phase."""
    return service.list_buildings_by_phase(phase_id=phase_id, skip=skip, limit=limit)


@router.post("/phases/{phase_id}/buildings", response_model=BuildingResponse, status_code=201)
def create_building_for_phase(
    phase_id: str,
    data: BuildingCreateForPhase,
    service: Annotated[BuildingService, Depends(get_service)],
) -> BuildingResponse:
    """Create a new building within a specific phase."""
    return service.create_building_for_phase(phase_id, data)


# ── Individual building endpoints ────────────────────────────────────────────

@router.get("/buildings/{building_id}", response_model=BuildingResponse)
def get_building(
    building_id: str,
    service: Annotated[BuildingService, Depends(get_service)],
) -> BuildingResponse:
    """Get a building by ID."""
    return service.get_building(building_id)


@router.patch("/buildings/{building_id}", response_model=BuildingResponse)
def update_building(
    building_id: str,
    data: BuildingUpdate,
    service: Annotated[BuildingService, Depends(get_service)],
) -> BuildingResponse:
    """Update a building."""
    return service.update_building(building_id, data)


@router.delete("/buildings/{building_id}", status_code=204)
def delete_building(
    building_id: str,
    service: Annotated[BuildingService, Depends(get_service)],
) -> Response:
    """Delete a building."""
    service.delete_building(building_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
