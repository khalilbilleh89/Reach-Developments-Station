"""
units.repository

Data access layer for the Unit entity.
"""

from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.modules.buildings.models import Building
from app.modules.floors.models import Floor
from app.modules.phases.models import Phase
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

    def _apply_filters(self, query, floor_id: Optional[str], project_id: Optional[str]):
        """Apply floor_id and/or project_id filters to a Unit query.

        project_id filter joins through the canonical hierarchy:
        Unit → Floor → Building → Phase to scope by project.
        """
        if floor_id:
            query = query.filter(Unit.floor_id == floor_id)
        if project_id:
            query = (
                query
                .join(Floor, Floor.id == Unit.floor_id)
                .join(Building, Building.id == Floor.building_id)
                .join(Phase, Phase.id == Building.phase_id)
                .filter(Phase.project_id == project_id)
            )
        return query

    def list(
        self,
        floor_id: Optional[str] = None,
        project_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Unit]:
        query = self._apply_filters(self.db.query(Unit), floor_id, project_id)
        return query.offset(skip).limit(limit).all()

    def count(
        self,
        floor_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> int:
        query = self._apply_filters(self.db.query(Unit), floor_id, project_id)
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
            .options(
                joinedload(UnitDynamicAttributeValue.definition),
                joinedload(UnitDynamicAttributeValue.option),
            )
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
        """Create or replace the selected option for a given unit + definition pair.

        Uses a read-then-write pattern with IntegrityError recovery to handle
        concurrent requests that may race on the (unit_id, definition_id) unique
        constraint. On constraint violation the transaction is rolled back and the
        existing row is re-fetched and updated deterministically.
        """
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
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            # A concurrent request inserted the row first — fetch and update it.
            existing = self.get_by_unit_and_definition(unit_id, definition_id)
            if existing:
                existing.option_id = option_id
                self.db.commit()
                self.db.refresh(existing)
                return existing
            raise
        self.db.refresh(value)
        return value
