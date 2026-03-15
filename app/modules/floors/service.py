"""
floors.service

Business logic for the Floor entity.
Enforces: floor must belong to a valid building; code and sequence_number must be unique per building.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.buildings.repository import BuildingRepository
from app.modules.floors.repository import FloorRepository
from app.modules.floors.schemas import (
    FloorCreate,
    FloorCreateForBuilding,
    FloorList,
    FloorResponse,
    FloorUpdate,
)


class FloorService:
    def __init__(self, db: Session) -> None:
        self.repo = FloorRepository(db)
        self.building_repo = BuildingRepository(db)

    def _validate_building_exists(self, building_id: str) -> None:
        building = self.building_repo.get_by_id(building_id)
        if not building:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Building '{building_id}' not found.",
            )

    def _validate_code_unique(self, building_id: str, code: str) -> None:
        existing = self.repo.get_by_building_and_code(building_id, code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Floor with code '{code}' already exists in building '{building_id}'.",
            )

    def _validate_sequence_unique(self, building_id: str, sequence_number: int) -> None:
        existing = self.repo.get_by_building_and_sequence(building_id, sequence_number)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Floor with sequence number {sequence_number} already exists in building '{building_id}'.",
            )

    def create_floor_for_building(
        self, building_id: str, data: FloorCreateForBuilding
    ) -> FloorResponse:
        self._validate_building_exists(building_id)
        self._validate_code_unique(building_id, data.code)
        self._validate_sequence_unique(building_id, data.sequence_number)
        full_data = FloorCreate(building_id=building_id, **data.model_dump())
        floor = self.repo.create(full_data)
        return FloorResponse.model_validate(floor)

    def list_floors_by_building(
        self, building_id: str, skip: int = 0, limit: int = 100
    ) -> FloorList:
        self._validate_building_exists(building_id)
        return self.list_floors(building_id=building_id, skip=skip, limit=limit)

    def get_floor(self, floor_id: str) -> FloorResponse:
        floor = self.repo.get_by_id(floor_id)
        if not floor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Floor '{floor_id}' not found.",
            )
        return FloorResponse.model_validate(floor)

    def list_floors(
        self, building_id: str | None = None, skip: int = 0, limit: int = 100
    ) -> FloorList:
        floors = self.repo.list(building_id=building_id, skip=skip, limit=limit)
        total = self.repo.count(building_id=building_id)
        return FloorList(
            items=[FloorResponse.model_validate(f) for f in floors],
            total=total,
        )

    def update_floor(self, floor_id: str, data: FloorUpdate) -> FloorResponse:
        floor = self.repo.get_by_id(floor_id)
        if not floor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Floor '{floor_id}' not found.",
            )
        updated = self.repo.update(floor, data)
        return FloorResponse.model_validate(updated)

    def delete_floor(self, floor_id: str) -> None:
        floor = self.repo.get_by_id(floor_id)
        if not floor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Floor '{floor_id}' not found.",
            )
        self.repo.delete(floor)
