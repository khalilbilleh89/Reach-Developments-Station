"""
pricing.repository

Data access layer for UnitPricingAttributes entities.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.pricing.models import UnitPricingAttributes
from app.modules.pricing.schemas import UnitPricingAttributesCreate


class UnitPricingAttributesRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(self, unit_id: str, data: UnitPricingAttributesCreate) -> UnitPricingAttributes:
        """Create or replace pricing attributes for a unit (one set per unit)."""
        existing = self.get_by_unit(unit_id)
        if existing:
            for field, value in data.model_dump().items():
                setattr(existing, field, value)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        attrs = UnitPricingAttributes(unit_id=unit_id, **data.model_dump())
        self.db.add(attrs)
        self.db.commit()
        self.db.refresh(attrs)
        return attrs

    def get_by_unit(self, unit_id: str) -> Optional[UnitPricingAttributes]:
        return (
            self.db.query(UnitPricingAttributes)
            .filter(UnitPricingAttributes.unit_id == unit_id)
            .first()
        )

    def list_by_unit_ids(self, unit_ids: List[str]) -> List[UnitPricingAttributes]:
        """Return all pricing attributes for the given unit IDs."""
        if not unit_ids:
            return []
        return (
            self.db.query(UnitPricingAttributes)
            .filter(UnitPricingAttributes.unit_id.in_(unit_ids))
            .all()
        )


class UnitPricingRepository:
    """Data access layer for the formal UnitPricing record."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_unit_id(self, unit_id: str) -> Optional["UnitPricing"]:
        from app.modules.pricing.models import UnitPricing
        return (
            self.db.query(UnitPricing)
            .filter(UnitPricing.unit_id == unit_id)
            .first()
        )

    def create_for_unit(self, unit_id: str, **kwargs) -> "UnitPricing":
        from app.modules.pricing.models import UnitPricing
        record = UnitPricing(unit_id=unit_id, **kwargs)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_for_unit(self, record: "UnitPricing", **kwargs) -> "UnitPricing":
        for field, value in kwargs.items():
            setattr(record, field, value)
        self.db.commit()
        self.db.refresh(record)
        return record

    def upsert_for_unit(self, unit_id: str, **kwargs) -> "UnitPricing":
        """Create or update the pricing record for a unit (one record per unit)."""
        existing = self.get_by_unit_id(unit_id)
        if existing:
            return self.update_for_unit(existing, **kwargs)
        return self.create_for_unit(unit_id, **kwargs)

    def list_by_project(self, project_id: str) -> list["UnitPricing"]:
        """Return all pricing records for units belonging to the given project."""
        from app.modules.pricing.models import UnitPricing
        from app.modules.units.models import Unit
        from app.modules.floors.models import Floor
        from app.modules.buildings.models import Building
        from app.modules.phases.models import Phase

        return (
            self.db.query(UnitPricing)
            .join(Unit, UnitPricing.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .all()
        )
