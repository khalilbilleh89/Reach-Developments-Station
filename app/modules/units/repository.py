"""
units.repository

Data access layer for the Unit entity.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.units.models import Unit
from app.modules.units.schemas import UnitCreate, UnitUpdate


class UnitRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: UnitCreate) -> Unit:
        unit = Unit(**data.model_dump())
        self.db.add(unit)
        self.db.commit()
        self.db.refresh(unit)
        return unit

    def get_by_id(self, unit_id: str) -> Optional[Unit]:
        return self.db.query(Unit).filter(Unit.id == unit_id).first()

    def get_by_floor_and_number(
        self, floor_id: str, unit_number: str
    ) -> Optional[Unit]:
        return (
            self.db.query(Unit)
            .filter(Unit.floor_id == floor_id, Unit.unit_number == unit_number)
            .first()
        )

    def list(
        self, floor_id: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[Unit]:
        query = self.db.query(Unit)
        if floor_id:
            query = query.filter(Unit.floor_id == floor_id)
        return query.offset(skip).limit(limit).all()

    def count(self, floor_id: Optional[str] = None) -> int:
        query = self.db.query(Unit)
        if floor_id:
            query = query.filter(Unit.floor_id == floor_id)
        return query.count()

    def update(self, unit: Unit, data: UnitUpdate) -> Unit:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(unit, field, value)
        self.db.commit()
        self.db.refresh(unit)
        return unit

    def delete(self, unit: Unit) -> None:
        self.db.delete(unit)
        self.db.commit()
