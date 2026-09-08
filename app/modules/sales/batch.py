"""Commercial facts in source currency; no receipt or allocation is a sale."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.sales.models import (
    RESERVATION_COMMITTED,
    SALE_COMMITTED,
    Reservation,
    SaleContract,
)


@dataclass
class SalesPosition:
    committed_ids: set[uuid.UUID] = field(default_factory=set)
    active_sold_ids: set[uuid.UUID] = field(default_factory=set)
    contracted: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    # UTC event dates remain separate, allowing Analysis to own its observation window.
    activations: list[date] = field(default_factory=list)
    cancellations: list[date] = field(default_factory=list)


def standing(sale: SaleContract, cutoff: date) -> bool:
    """Cancellation takes effect on its UTC day; termination pending still stands."""
    return sale.cancelled_at is None or sale.cancelled_at.astimezone(UTC).date() > cutoff


def positions(session: Session, project_ids: Select, as_of: date) -> dict[uuid.UUID, SalesPosition]:
    result: dict[uuid.UUID, SalesPosition] = {}
    for pid, uid in session.execute(
        select(Reservation.project_id, Reservation.unit_id).where(
            Reservation.project_id.in_(project_ids), Reservation.status.in_(RESERVATION_COMMITTED)
        )
    ):
        result.setdefault(pid, SalesPosition()).committed_ids.add(uid)
    bound = datetime.combine(as_of + timedelta(days=1), time(), UTC)
    for sale in session.scalars(
        select(SaleContract).where(SaleContract.project_id.in_(project_ids))
    ):
        position = result.setdefault(sale.project_id, SalesPosition())
        if sale.status in SALE_COMMITTED:
            position.committed_ids.add(sale.unit_id)
        if sale.activated_at is None or sale.activated_at >= bound:
            continue
        position.activations.append(sale.activated_at.astimezone(UTC).date())
        if sale.cancelled_at is not None:
            position.cancellations.append(sale.cancelled_at.astimezone(UTC).date())
        if standing(sale, as_of):
            position.contracted[sale.currency_id] = (
                position.contracted.get(sale.currency_id, Decimal(0)) + sale.total_contract_price
            )
            # Exactly the current Project Analysis active-sold definition.
            if sale.status == "active":
                position.active_sold_ids.add(sale.unit_id)
    return result
