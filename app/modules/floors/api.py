"""
floors.api

CRUD API router for the Floor entity.

Provides two route groups:
  /api/v1/buildings/{building_id}/floors  — building-scoped floor listing and creation
  /api/v1/floors/{floor_id}               — individual floor operations (get, update, delete)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.floors.schemas import (
    FloorCreateForBuilding,
    FloorList,
    FloorResponse,
    FloorUpdate,
)
from app.modules.floors.service import FloorService

router = APIRouter(tags=["floors"])


def get_service(db: Session = Depends(get_db)) -> FloorService:
    return FloorService(db)


# ── Building-scoped endpoints ─────────────────────────────────────────────────


@router.get("/buildings/{building_id}/floors", response_model=FloorList)
def list_floors_by_building(
    building_id: str,
    service: Annotated[FloorService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> FloorList:
    """List all floors for a specific building."""
    return service.list_floors_by_building(
        building_id=building_id, skip=skip, limit=limit
    )


@router.post(
    "/buildings/{building_id}/floors", response_model=FloorResponse, status_code=201
)
def create_floor_for_building(
    building_id: str,
    data: FloorCreateForBuilding,
    service: Annotated[FloorService, Depends(get_service)],
) -> FloorResponse:
    """Create a new floor within a specific building."""
    return service.create_floor_for_building(building_id, data)


# ── Individual floor endpoints ────────────────────────────────────────────────


@router.get("/floors/{floor_id}", response_model=FloorResponse)
def get_floor(
    floor_id: str,
    service: Annotated[FloorService, Depends(get_service)],
) -> FloorResponse:
    """Get a floor by ID."""
    return service.get_floor(floor_id)


@router.patch("/floors/{floor_id}", response_model=FloorResponse)
def update_floor(
    floor_id: str,
    data: FloorUpdate,
    service: Annotated[FloorService, Depends(get_service)],
) -> FloorResponse:
    """Update a floor."""
    return service.update_floor(floor_id, data)


@router.delete("/floors/{floor_id}", status_code=204)
def delete_floor(
    floor_id: str,
    service: Annotated[FloorService, Depends(get_service)],
) -> Response:
    """Delete a floor by ID."""
    service.delete_floor(floor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
