"""Pricing-owned participation in a project denomination correction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.pricing.models import UnitPriceVersion


@dataclass(frozen=True)
class PricingCurrencyCorrection:
    counts: dict[str, int]
    direct_price_version_ids: frozenset[uuid.UUID]


def correct_project_base_currency(
    session: Session,
    *,
    project_id: uuid.UUID,
    old_currency_id: uuid.UUID,
    new_currency_id: uuid.UUID,
) -> PricingCurrencyCorrection:
    """Relabel direct prices; configured pricing and market observations stay explicit."""
    ids = frozenset(
        session.scalars(
            select(UnitPriceVersion.id).where(
                UnitPriceVersion.project_id == project_id,
                UnitPriceVersion.currency_id == old_currency_id,
                UnitPriceVersion.pricing_configuration_id.is_(None),
            )
        )
    )
    if not ids:
        return PricingCurrencyCorrection(counts={}, direct_price_version_ids=ids)
    result = session.execute(
        update(UnitPriceVersion)
        .where(UnitPriceVersion.id.in_(ids))
        .values(currency_id=new_currency_id)
    )
    return PricingCurrencyCorrection(
        counts={"unit_price_versions.currency_id": result.rowcount},
        direct_price_version_ids=ids,
    )
