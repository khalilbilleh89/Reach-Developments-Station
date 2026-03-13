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
