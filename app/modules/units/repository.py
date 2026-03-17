"""
units.repository

Data access layer for the Unit entity.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.units.models import Unit, UnitDynamicAttributeValue
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


class UnitDynamicAttributeRepository:
    """Persistence helpers for unit dynamic attribute values."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_unit(self, unit_id: str) -> List[UnitDynamicAttributeValue]:
        return (
            self.db.query(UnitDynamicAttributeValue)
            .filter(UnitDynamicAttributeValue.unit_id == unit_id)
            .all()
        )

    def get_by_unit_and_definition(
        self, unit_id: str, definition_id: str
    ) -> Optional[UnitDynamicAttributeValue]:
        return (
            self.db.query(UnitDynamicAttributeValue)
            .filter(
                UnitDynamicAttributeValue.unit_id == unit_id,
                UnitDynamicAttributeValue.definition_id == definition_id,
            )
            .first()
        )

    def upsert(
        self, unit_id: str, definition_id: str, option_id: str
    ) -> UnitDynamicAttributeValue:
        """Create or replace the selected option for a given unit + definition pair."""
        existing = self.get_by_unit_and_definition(unit_id, definition_id)
        if existing:
            existing.option_id = option_id
            self.db.commit()
            self.db.refresh(existing)
            return existing
        value = UnitDynamicAttributeValue(
            unit_id=unit_id,
            definition_id=definition_id,
            option_id=option_id,
        )
        self.db.add(value)
        self.db.commit()
        self.db.refresh(value)
        return value
