"""
pricing_attributes.service

Application-layer orchestration for unit qualitative pricing attributes.

Validates unit existence before reading or writing attributes.
Coordinates with the repository for persistence.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.pricing_attributes.repository import UnitQualitativeAttributesRepository
from app.modules.pricing_attributes.schemas import (
    UnitQualitativeAttributesCreate,
    UnitQualitativeAttributesResponse,
)
from app.modules.units.repository import UnitRepository


class UnitPricingAttributesService:
    """Service for managing qualitative pricing attributes per unit."""

    def __init__(self, db: Session) -> None:
        self._repo = UnitQualitativeAttributesRepository(db)
        self._unit_repo = UnitRepository(db)

    def get_attributes(self, unit_id: str) -> UnitQualitativeAttributesResponse:
        """Return the qualitative attributes for a unit.

        Raises 404 if the unit does not exist or has no attributes record yet.
        """
        unit = self._unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        record = self._repo.get_by_unit_id(unit_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No pricing attributes found for unit '{unit_id}'.",
            )
        return UnitQualitativeAttributesResponse.model_validate(record)

    def save_attributes(
        self, unit_id: str, data: UnitQualitativeAttributesCreate
    ) -> tuple[UnitQualitativeAttributesResponse, bool]:
        """Create or update qualitative attributes for a unit.

        Returns a tuple of (response, created) where created is True when a
        new record was inserted and False when an existing record was updated.
        """
        unit = self._unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        existing = self._repo.get_by_unit_id(unit_id)
        created = existing is None
        record = self._repo.upsert_for_unit(unit_id, data)
        return UnitQualitativeAttributesResponse.model_validate(record), created
