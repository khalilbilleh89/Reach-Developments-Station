"""Original-currency collections, with the existing owner receivable calculation."""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.collections import service
from app.modules.collections.models import CollectionRefund
from app.modules.sales.models import SaleContract


@dataclass
class CollectionsPosition:
    confirmed: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    refunds: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    unapplied: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    overdue: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    unavailable_overdue_currencies: set[uuid.UUID] = field(default_factory=set)
    missing_schedules: int = 0
    scheduled: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID, str, date, uuid.UUID, Decimal]] = field(
        default_factory=list
    )
    undated_installments: int = 0


def positions(
    session: Session, project_ids: Select, as_of: date, *, risk_only: bool = False
) -> dict[uuid.UUID, CollectionsPosition]:
    sales = list(
        session.scalars(select(SaleContract).where(SaleContract.project_id.in_(project_ids)))
    )
    ledgers = service.load_ledgers(session, sales, as_of)
    result: dict[uuid.UUID, CollectionsPosition] = {}
    for sale in sales:
        target = result.setdefault(sale.project_id, CollectionsPosition())
        position, extras = ledgers[sale.id]
        allocations: dict[uuid.UUID, Decimal] = {}
        for allocation in position.allocations:
            allocations[allocation.receipt_id] = (
                allocations.get(allocation.receipt_id, Decimal(0)) + allocation.amount
            )
        unsafe = False
        for receipt in position.confirmed_receipts:
            code = receipt.currency_id
            if not risk_only:
                target.confirmed[code] = target.confirmed.get(code, Decimal(0)) + receipt.amount
            target.unapplied[code] = (
                target.unapplied.get(code, Decimal(0))
                + receipt.amount
                - allocations.get(receipt.id, Decimal(0))
            )
            if allocations.get(receipt.id, Decimal(0)) and code != sale.currency_id:
                unsafe = True
        if unsafe:
            target.unavailable_overdue_currencies.add(sale.currency_id)
        elif position.version is not None or position.sale_cancelled:
            summary = service.summarise(session, position=position, as_of=as_of, extras=extras)
            if not risk_only and position.version is not None and not position.sale_cancelled:
                for row in summary.rows:
                    if row.outstanding <= 0:
                        continue
                    if row.due_date is None:
                        target.undated_installments += 1
                    else:
                        target.scheduled.append(
                            (
                                row.installment_id,
                                sale.id,
                                position.version.id,
                                row.label,
                                row.due_date,
                                sale.currency_id,
                                row.outstanding,
                            )
                        )
            target.overdue[sale.currency_id] = (
                target.overdue.get(sale.currency_id, Decimal(0)) + summary.overdue_total
            )
        elif sale.activated_at is not None:
            target.missing_schedules += 1
            target.unavailable_overdue_currencies.add(sale.currency_id)
    if risk_only:
        return result
    for refund in session.scalars(
        select(CollectionRefund).where(
            CollectionRefund.project_id.in_(project_ids), service._refund_effective_on(as_of)
        )
    ):
        target = result.setdefault(refund.project_id, CollectionsPosition())
        target.refunds[refund.currency_id] = (
            target.refunds.get(refund.currency_id, Decimal(0)) + refund.amount
        )
    return result
