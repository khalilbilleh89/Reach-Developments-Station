"""
Unit pricing adapter.

Reads the active price from the Pricing module for a given unit.
Returns None when no pricing record has been configured for the unit.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from app.modules.pricing.repository import UnitPricingRepository

if TYPE_CHECKING:
    from app.modules.pricing.models import UnitPricing


class UnitPricingAdapter:
    """Thin read-only bridge from the Units domain to the Pricing domain.

    Reads the stored ``final_price`` and ``pricing_status`` from the
    ``unit_pricing`` table without embedding any pricing calculation logic —
    all computation lives in the Pricing module.
    """

    def __init__(self, db: Session) -> None:
        self._repo = UnitPricingRepository(db)

    def _get_record(self, unit_id: str) -> Optional["UnitPricing"]:
        """Fetch the pricing record for *unit_id*, or return None.

        Centralises the repository call so callers that need both
        ``final_price`` and ``pricing_status`` only issue one DB query.
        """
        return self._repo.get_by_unit_id(unit_id)

    def get_active_price(self, unit_id: str) -> Optional[Decimal]:
        """Return the ``final_price`` for *unit_id*, or None if no record exists.

        The returned value is the server-computed
        ``base_price + manual_adjustment`` stored in the ``unit_pricing``
        table.  This adapter never calculates — it only retrieves.
        """
        record = self._get_record(unit_id)
        if record is None:
            return None
        return Decimal(str(record.final_price))

    def get_pricing_status(self, unit_id: str) -> Optional[str]:
        """Return the ``pricing_status`` for *unit_id*, or None if no record exists.

        Possible values: ``draft`` | ``reviewed`` | ``approved``.
        """
        record = self._get_record(unit_id)
        if record is None:
            return None
        return record.pricing_status
