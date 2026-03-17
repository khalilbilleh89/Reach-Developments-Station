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

    def _validate_apartment_attributes(self, data: UnitCreate | UnitUpdate) -> None:
        """Validate cross-field apartment attribute rules.

        Per-field non-negative constraints (bedrooms >= 0, bathrooms >= 0, etc.)
        are already enforced by Pydantic schema-level Field(ge=0) definitions.
        Only cross-field business rules belong here.
        """
        # If has_roof_garden is explicitly False, roof_garden_area must be null or 0
        has_roof_garden = getattr(data, "has_roof_garden", None)
        roof_garden_area = getattr(data, "roof_garden_area", None)
        if (
            has_roof_garden is False
            and roof_garden_area is not None
            and roof_garden_area > 0
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="roof_garden_area must be null or 0 when has_roof_garden is false.",
            )

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
        self._validate_apartment_attributes(data)
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

    def list_units(
        self, floor_id: str | None = None, skip: int = 0, limit: int = 100
    ) -> UnitList:
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
        self._validate_apartment_attributes(data)
        updated = self.repo.update(unit, data)
        return UnitResponse.model_validate(updated)

    def delete_unit(self, unit_id: str) -> None:
        unit = self.repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        self.repo.delete(unit)
