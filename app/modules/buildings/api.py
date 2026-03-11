"""
buildings.api

CRUD API router for the Building entity.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.buildings.schemas import BuildingCreate, BuildingList, BuildingResponse, BuildingUpdate
from app.modules.buildings.service import BuildingService

router = APIRouter(prefix="/buildings", tags=["buildings"])


def get_service(db: Session = Depends(get_db)) -> BuildingService:
    return BuildingService(db)


@router.post("", response_model=BuildingResponse, status_code=201)
def create_building(
    data: BuildingCreate,
    service: Annotated[BuildingService, Depends(get_service)],
) -> BuildingResponse:
    """Create a new building."""
    return service.create_building(data)


@router.get("", response_model=BuildingList)
def list_buildings(
    service: Annotated[BuildingService, Depends(get_service)],
    phase_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> BuildingList:
    """List buildings, optionally filtered by phase."""
    return service.list_buildings(phase_id=phase_id, skip=skip, limit=limit)


@router.get("/{building_id}", response_model=BuildingResponse)
def get_building(
    building_id: str,
    service: Annotated[BuildingService, Depends(get_service)],
) -> BuildingResponse:
    """Get a building by ID."""
    return service.get_building(building_id)


@router.patch("/{building_id}", response_model=BuildingResponse)
def update_building(
    building_id: str,
    data: BuildingUpdate,
    service: Annotated[BuildingService, Depends(get_service)],
) -> BuildingResponse:
    """Update a building."""
    return service.update_building(building_id, data)
