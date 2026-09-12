"""Read-only dependency checks for project inventory choices owned by Inventory."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.pricing.models import (
    MarketBenchmark,
    PricingEscalationRule,
    PricingPremiumRule,
    UnitPriceVersion,
)


def unit_has_price_history(session: Session, *, project_id: uuid.UUID, unit_id: uuid.UUID) -> bool:
    """Whether a physical record already participates in a retained price snapshot."""
    return (
        session.scalar(
            select(UnitPriceVersion.id)
            .where(UnitPriceVersion.project_id == project_id, UnitPriceVersion.unit_id == unit_id)
            .limit(1)
        )
        is not None
    )


def inventory_option_in_use(
    session: Session, *, project_id: uuid.UUID, category: str, code: str
) -> bool:
    sources = ("parking", "storage") if category == "sub_asset_subtype" else (category,)
    if session.scalar(
        select(PricingPremiumRule.id)
        .where(
            PricingPremiumRule.project_id == project_id,
            PricingPremiumRule.source_kind.in_(sources),
            PricingPremiumRule.match_code == code,
        )
        .limit(1)
    ):
        return True
    if category == "unit_type":
        for model in (PricingEscalationRule, MarketBenchmark):
            if session.scalar(
                select(model.id)
                .where(model.project_id == project_id, model.unit_type_code == code)
                .limit(1)
            ):
                return True
    return False
