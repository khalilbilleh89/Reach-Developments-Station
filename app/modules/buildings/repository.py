"""
buildings.repository

Data access layer for the Building entity.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.buildings.schemas import BuildingCreate, BuildingUpdate


class BuildingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: BuildingCreate) -> Building:
        building = Building(**data.model_dump())
        self.db.add(building)
        self.db.commit()
        self.db.refresh(building)
        return building

    def get_by_id(self, building_id: str) -> Optional[Building]:
        return self.db.query(Building).filter(Building.id == building_id).first()

    def get_by_phase_and_code(self, phase_id: str, code: str) -> Optional[Building]:
        return (
            self.db.query(Building)
            .filter(Building.phase_id == phase_id, Building.code == code)
            .first()
        )

    def list(self, phase_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Building]:
        query = self.db.query(Building)
        if phase_id:
            query = query.filter(Building.phase_id == phase_id)
        return query.offset(skip).limit(limit).all()

    def count(self, phase_id: Optional[str] = None) -> int:
        query = self.db.query(Building)
        if phase_id:
            query = query.filter(Building.phase_id == phase_id)
        return query.count()

    def update(self, building: Building, data: BuildingUpdate) -> Building:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(building, field, value)
        self.db.commit()
        self.db.refresh(building)
        return building

    def delete(self, building: Building) -> None:
        self.db.delete(building)
        self.db.commit()
