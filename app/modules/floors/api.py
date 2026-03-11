"""
floors.api

CRUD API router for the Floor entity.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.floors.schemas import FloorCreate, FloorList, FloorResponse, FloorUpdate
from app.modules.floors.service import FloorService

router = APIRouter(prefix="/floors", tags=["floors"])


def get_service(db: Session = Depends(get_db)) -> FloorService:
    return FloorService(db)


@router.post("", response_model=FloorResponse, status_code=201)
def create_floor(
    data: FloorCreate,
    service: Annotated[FloorService, Depends(get_service)],
) -> FloorResponse:
    """Create a new floor."""
    return service.create_floor(data)


@router.get("", response_model=FloorList)
def list_floors(
    service: Annotated[FloorService, Depends(get_service)],
    building_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> FloorList:
    """List floors, optionally filtered by building."""
    return service.list_floors(building_id=building_id, skip=skip, limit=limit)


@router.get("/{floor_id}", response_model=FloorResponse)
def get_floor(
    floor_id: str,
    service: Annotated[FloorService, Depends(get_service)],
) -> FloorResponse:
    """Get a floor by ID."""
    return service.get_floor(floor_id)


@router.patch("/{floor_id}", response_model=FloorResponse)
def update_floor(
    floor_id: str,
    data: FloorUpdate,
    service: Annotated[FloorService, Depends(get_service)],
) -> FloorResponse:
    """Update a floor."""
    return service.update_floor(floor_id, data)
