"""
pricing.repository

Data access layer for UnitPricingAttributes entities.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.pricing.models import UnitPricingAttributes
from app.modules.pricing.schemas import UnitPricingAttributesCreate
from app.modules.pricing.status_rules import ARCHIVED_STATUS


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
        """Return the active (non-archived) pricing record for *unit_id*, or None."""
        from app.modules.pricing.models import UnitPricing
        return (
            self.db.query(UnitPricing)
            .filter(
                UnitPricing.unit_id == unit_id,
                UnitPricing.pricing_status != ARCHIVED_STATUS,
            )
            .order_by(UnitPricing.created_at.desc())
            .first()
        )

    def get_by_id(self, pricing_id: str) -> Optional["UnitPricing"]:
        """Return a pricing record by its primary key, or None."""
        from app.modules.pricing.models import UnitPricing
        return self.db.query(UnitPricing).filter(UnitPricing.id == pricing_id).first()

    def get_all_by_unit_id(self, unit_id: str) -> List["UnitPricing"]:
        """Return all pricing records for *unit_id*, including archived, newest first."""
        from app.modules.pricing.models import UnitPricing
        return (
            self.db.query(UnitPricing)
            .filter(UnitPricing.unit_id == unit_id)
            .order_by(UnitPricing.created_at.desc())
            .all()
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
        """Create or update the active pricing record for a unit.

        Updates the existing active (non-archived) record in place when one
        exists, preserving pricing history for archived records.
        """
        existing = self.get_by_unit_id(unit_id)
        if existing:
            return self.update_for_unit(existing, **kwargs)
        return self.create_for_unit(unit_id, **kwargs)

    def archive_existing_pricing(self, unit_id: str) -> Optional["UnitPricing"]:
        """Set the active pricing record for *unit_id* to 'archived'.

        Returns the archived record, or None when no active record exists.
        """
        record = self.get_by_unit_id(unit_id)
        if record is None:
            return None
        return self.update_for_unit(record, pricing_status=ARCHIVED_STATUS)

    def list_by_project(self, project_id: str) -> list["UnitPricing"]:
        """Return all active (non-archived) pricing records for units in the given project."""
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
            .filter(
                Phase.project_id == project_id,
                UnitPricing.pricing_status != ARCHIVED_STATUS,
            )
            .all()
        )


class PricingHistoryRepository:
    """Data access layer for the PricingHistory audit log."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_change(
        self,
        pricing_id: str,
        unit_id: str,
        change_type: str,
        base_price: float,
        manual_adjustment: float,
        final_price: float,
        pricing_status: str,
        currency: str = "AED",
        override_reason: Optional[str] = None,
        override_requested_by: Optional[str] = None,
        override_approved_by: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> "PricingHistory":
        """Append an immutable audit entry for a pricing state change.

        Commits immediately after adding the entry, matching the single-record
        commit pattern used throughout the rest of the repository layer.  Each
        audit entry is written as its own transaction; callers should ensure the
        parent pricing operation has already been committed before calling this
        method so that the audit trail always reflects the persisted state.
        """
        from app.modules.pricing.models import PricingHistory
        entry = PricingHistory(
            pricing_id=pricing_id,
            unit_id=unit_id,
            change_type=change_type,
            base_price=base_price,
            manual_adjustment=manual_adjustment,
            final_price=final_price,
            pricing_status=pricing_status,
            currency=currency,
            override_reason=override_reason,
            override_requested_by=override_requested_by,
            override_approved_by=override_approved_by,
            actor=actor,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get_by_pricing_id(self, pricing_id: str) -> List["PricingHistory"]:
        """Return all audit entries for a pricing record, oldest first."""
        from app.modules.pricing.models import PricingHistory
        return (
            self.db.query(PricingHistory)
            .filter(PricingHistory.pricing_id == pricing_id)
            .order_by(PricingHistory.created_at.asc(), PricingHistory.id.asc())
            .all()
        )

    def get_by_unit_id(self, unit_id: str) -> List["PricingHistory"]:
        """Return all audit entries for all pricing records of a unit, oldest first."""
        from app.modules.pricing.models import PricingHistory
        return (
            self.db.query(PricingHistory)
            .filter(PricingHistory.unit_id == unit_id)
            .order_by(PricingHistory.created_at.asc(), PricingHistory.id.asc())
            .all()
        )
