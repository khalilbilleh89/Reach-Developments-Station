"""
units.api

CRUD API router for the Unit entity.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.units.schemas import UnitCreate, UnitList, UnitResponse, UnitUpdate
from app.modules.units.service import UnitService

router = APIRouter(prefix="/units", tags=["units"])


def get_service(db: Session = Depends(get_db)) -> UnitService:
    return UnitService(db)


@router.post("", response_model=UnitResponse, status_code=201)
def create_unit(
    data: UnitCreate,
    service: Annotated[UnitService, Depends(get_service)],
) -> UnitResponse:
    """Create a new unit."""
    return service.create_unit(data)


@router.get("", response_model=UnitList)
def list_units(
    service: Annotated[UnitService, Depends(get_service)],
    floor_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> UnitList:
    """List units, optionally filtered by floor."""
    return service.list_units(floor_id=floor_id, skip=skip, limit=limit)


@router.get("/{unit_id}", response_model=UnitResponse)
def get_unit(
    unit_id: str,
    service: Annotated[UnitService, Depends(get_service)],
) -> UnitResponse:
    """Get a unit by ID."""
    return service.get_unit(unit_id)


@router.patch("/{unit_id}", response_model=UnitResponse)
def update_unit(
    unit_id: str,
    data: UnitUpdate,
    service: Annotated[UnitService, Depends(get_service)],
) -> UnitResponse:
    """Update a unit."""
    return service.update_unit(unit_id, data)
