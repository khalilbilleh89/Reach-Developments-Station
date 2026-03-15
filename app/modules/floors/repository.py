"""
floors.repository

Data access layer for the Floor entity.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.floors.models import Floor
from app.modules.floors.schemas import FloorCreate, FloorUpdate


class FloorRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: FloorCreate) -> Floor:
        floor = Floor(**data.model_dump())
        self.db.add(floor)
        self.db.commit()
        self.db.refresh(floor)
        return floor

    def get_by_id(self, floor_id: str) -> Optional[Floor]:
        return self.db.query(Floor).filter(Floor.id == floor_id).first()

    def get_by_building_and_code(self, building_id: str, code: str) -> Optional[Floor]:
        return (
            self.db.query(Floor)
            .filter(Floor.building_id == building_id, Floor.code == code)
            .first()
        )

    def get_by_building_and_sequence(
        self, building_id: str, sequence_number: int
    ) -> Optional[Floor]:
        return (
            self.db.query(Floor)
            .filter(
                Floor.building_id == building_id,
                Floor.sequence_number == sequence_number,
            )
            .first()
        )

    def list(
        self, building_id: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[Floor]:
        query = self.db.query(Floor)
        if building_id:
            query = query.filter(Floor.building_id == building_id)
        return query.order_by(Floor.sequence_number).offset(skip).limit(limit).all()

    def count(self, building_id: Optional[str] = None) -> int:
        query = self.db.query(Floor)
        if building_id:
            query = query.filter(Floor.building_id == building_id)
        return query.count()

    def update(self, floor: Floor, data: FloorUpdate) -> Floor:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(floor, field, value)
        self.db.commit()
        self.db.refresh(floor)
        return floor

    def delete(self, floor: Floor) -> None:
        self.db.delete(floor)
        self.db.commit()
