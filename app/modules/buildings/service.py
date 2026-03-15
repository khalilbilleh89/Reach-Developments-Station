"""
buildings.service

Business logic for the Building entity.
Enforces: building must belong to a valid phase; code must be unique per phase.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.buildings.repository import BuildingRepository
from app.modules.buildings.schemas import BuildingCreate, BuildingCreateForPhase, BuildingList, BuildingResponse, BuildingUpdate
from app.modules.phases.repository import PhaseRepository


class BuildingService:
    def __init__(self, db: Session) -> None:
        self.repo = BuildingRepository(db)
        self.phase_repo = PhaseRepository(db)

    def create_building(self, data: BuildingCreate) -> BuildingResponse:
        phase = self.phase_repo.get_by_id(data.phase_id)
        if not phase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phase '{data.phase_id}' not found.",
            )
        existing = self.repo.get_by_phase_and_code(data.phase_id, data.code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Building with code '{data.code}' already exists in phase '{data.phase_id}'.",
            )
        building = self.repo.create(data)
        return BuildingResponse.model_validate(building)

    def create_building_for_phase(self, phase_id: str, data: BuildingCreateForPhase) -> BuildingResponse:
        phase = self.phase_repo.get_by_id(phase_id)
        if not phase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phase '{phase_id}' not found.",
            )
        existing = self.repo.get_by_phase_and_code(phase_id, data.code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Building with code '{data.code}' already exists in phase '{phase_id}'.",
            )
        full_data = BuildingCreate(phase_id=phase_id, **data.model_dump())
        building = self.repo.create(full_data)
        return BuildingResponse.model_validate(building)

    def list_buildings_by_phase(self, phase_id: str, skip: int = 0, limit: int = 100) -> BuildingList:
        phase = self.phase_repo.get_by_id(phase_id)
        if not phase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phase '{phase_id}' not found.",
            )
        return self.list_buildings(phase_id=phase_id, skip=skip, limit=limit)

    def get_building(self, building_id: str) -> BuildingResponse:
        building = self.repo.get_by_id(building_id)
        if not building:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Building '{building_id}' not found.",
            )
        return BuildingResponse.model_validate(building)

    def list_buildings(self, phase_id: str | None = None, skip: int = 0, limit: int = 100) -> BuildingList:
        buildings = self.repo.list(phase_id=phase_id, skip=skip, limit=limit)
        total = self.repo.count(phase_id=phase_id)
        return BuildingList(
            items=[BuildingResponse.model_validate(b) for b in buildings],
            total=total,
        )

    def update_building(self, building_id: str, data: BuildingUpdate) -> BuildingResponse:
        building = self.repo.get_by_id(building_id)
        if not building:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Building '{building_id}' not found.",
            )
        updated = self.repo.update(building, data)
        return BuildingResponse.model_validate(updated)

    def delete_building(self, building_id: str) -> None:
        building = self.repo.get_by_id(building_id)
        if not building:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Building '{building_id}' not found.",
            )
        self.repo.delete(building)
