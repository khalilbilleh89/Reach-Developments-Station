"""
units.service

Business logic for the Unit entity.
Enforces: unit must belong to a valid floor; unit number must be unique per floor.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.floors.repository import FloorRepository
from app.modules.units.repository import UnitRepository
from app.modules.units.schemas import UnitCreate, UnitList, UnitResponse, UnitUpdate


class UnitService:
    def __init__(self, db: Session) -> None:
        self.repo = UnitRepository(db)
        self.floor_repo = FloorRepository(db)

    def create_unit(self, data: UnitCreate) -> UnitResponse:
        floor = self.floor_repo.get_by_id(data.floor_id)
        if not floor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Floor '{data.floor_id}' not found.",
            )
        existing = self.repo.get_by_floor_and_number(data.floor_id, data.unit_number)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unit '{data.unit_number}' already exists on floor '{data.floor_id}'.",
            )
        unit = self.repo.create(data)
        return UnitResponse.model_validate(unit)

    def get_unit(self, unit_id: str) -> UnitResponse:
        unit = self.repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        return UnitResponse.model_validate(unit)

    def list_units(self, floor_id: str | None = None, skip: int = 0, limit: int = 100) -> UnitList:
        units = self.repo.list(floor_id=floor_id, skip=skip, limit=limit)
        total = self.repo.count(floor_id=floor_id)
        return UnitList(
            items=[UnitResponse.model_validate(u) for u in units],
            total=total,
        )

    def update_unit(self, unit_id: str, data: UnitUpdate) -> UnitResponse:
        unit = self.repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        updated = self.repo.update(unit, data)
        return UnitResponse.model_validate(updated)
