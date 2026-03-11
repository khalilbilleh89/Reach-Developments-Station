"""
floors.service

Business logic for the Floor entity.
Enforces: floor must belong to a valid building; level must be unique per building.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.buildings.repository import BuildingRepository
from app.modules.floors.repository import FloorRepository
from app.modules.floors.schemas import FloorCreate, FloorList, FloorResponse, FloorUpdate


class FloorService:
    def __init__(self, db: Session) -> None:
        self.repo = FloorRepository(db)
        self.building_repo = BuildingRepository(db)

    def create_floor(self, data: FloorCreate) -> FloorResponse:
        building = self.building_repo.get_by_id(data.building_id)
        if not building:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Building '{data.building_id}' not found.",
            )
        existing = self.repo.get_by_building_and_level(data.building_id, data.level)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Floor at level {data.level} already exists in building '{data.building_id}'.",
            )
        floor = self.repo.create(data)
        return FloorResponse.model_validate(floor)

    def get_floor(self, floor_id: str) -> FloorResponse:
        floor = self.repo.get_by_id(floor_id)
        if not floor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Floor '{floor_id}' not found.",
            )
        return FloorResponse.model_validate(floor)

    def list_floors(self, building_id: str | None = None, skip: int = 0, limit: int = 100) -> FloorList:
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
