"""Launch list values for an already authorised inventory selection."""

from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.inventory.models import Unit
from app.modules.pricing.models import STATUS_ACTIVE, UnitPriceVersion


def launch_register(session: Session, *, selection: Select, limit: int, offset: int) -> dict:
    """Current launch prices only; stale prices are counted and excluded from totals.

    Inventory supplies the SQL scope. No contract amounts, draft prices or buyer
    information participate. Currency groups are never added together.
    """
    scoped = selection.subquery()
    version = UnitPriceVersion
    current = (version.id.is_not(None)) & Unit.pricing_approved.is_(True)
    query = (
        select(Unit, version)
        .join(scoped, scoped.c.id == Unit.id)
        .outerjoin(version, (version.unit_id == Unit.id) & (version.status == STATUS_ACTIVE))
    )
    rows = session.execute(
        query.order_by(Unit.sequence, Unit.unit_reference).limit(limit).offset(offset)
    ).all()
    counts = session.execute(
        select(
            func.count(Unit.id),
            func.count(Unit.id).filter(current),
            func.count(Unit.id).filter(version.id.is_not(None) & ~Unit.pricing_approved),
        )
        .join(scoped, scoped.c.id == Unit.id)
        .outerjoin(version, (version.unit_id == Unit.id) & (version.status == STATUS_ACTIVE))
    ).one()
    totals = session.execute(
        select(version.currency_id, func.sum(version.reference_price_ex_tax))
        .join(Unit, Unit.id == version.unit_id)
        .join(scoped, scoped.c.id == Unit.id)
        .where(version.status == STATUS_ACTIVE, Unit.pricing_approved.is_(True))
        .group_by(version.currency_id)
    ).all()
    return {
        "total": counts[0],
        "priced_count": counts[1],
        "repricing_count": counts[2],
        "unpriced_count": counts[0] - counts[1] - counts[2],
        "totals": [
            {"currency_id": currency, "amount": amount or Decimal("0")}
            for currency, amount in totals
        ],
        "rows": [
            {
                "unit_id": unit.id,
                "currency_id": price.currency_id if price else None,
                "price": price.reference_price_ex_tax if price and unit.pricing_approved else None,
                "repricing_required": price is not None and not unit.pricing_approved,
            }
            for unit, price in rows
        ],
    }
