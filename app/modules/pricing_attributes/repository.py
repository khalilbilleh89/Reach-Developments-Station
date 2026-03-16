"""
pricing_attributes.repository

Data access layer for UnitQualitativeAttributes entities.

Provides idempotent upsert — one attribute record per unit guaranteed.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.modules.pricing_attributes.models import UnitQualitativeAttributes
from app.modules.pricing_attributes.schemas import UnitQualitativeAttributesCreate


class UnitQualitativeAttributesRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_unit_id(self, unit_id: str) -> Optional[UnitQualitativeAttributes]:
        """Return the qualitative attributes record for a unit, or None."""
        return (
            self.db.query(UnitQualitativeAttributes)
            .filter(UnitQualitativeAttributes.unit_id == unit_id)
            .first()
        )

    def upsert_for_unit(
        self, unit_id: str, data: UnitQualitativeAttributesCreate
    ) -> UnitQualitativeAttributes:
        """Create or update qualitative attributes for a unit (one record per unit).

        Uses exclude_unset=True so that omitted fields are left unchanged on update.
        Clients must send explicit null to clear a field.
        """
        existing = self.get_by_unit_id(unit_id)
        payload = data.model_dump(exclude_unset=True)
        if existing:
            for field, value in payload.items():
                setattr(existing, field, value)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        record = UnitQualitativeAttributes(unit_id=unit_id, **payload)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
