"""Narrow read contracts over Collections-owned cash truth.

This module deliberately imports no Sales service.  Sales may ask one bounded
question about cash held for a contract without learning receipt/refund row
semantics or creating the ``sales.service <-> collections.service`` cycle that
the domain stack forbids.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.core.standing import standing_conditions
from app.db.base import MONEY_EXPONENT
from app.modules.collections.models import CollectionReceipt, CollectionRefund


@dataclass(frozen=True, slots=True)
class EligibleCancellationCash:
    """Cash still held for one sale and therefore eligible for cancellation."""

    currency_id: uuid.UUID
    confirmed_receipts: Decimal
    confirmed_refunds: Decimal
    eligible_collected_amount: Decimal


def _money(value: object) -> Decimal:
    return Decimal(value or 0).quantize(MONEY_EXPONENT)


def _standing_total(
    session: Session,
    *,
    model: type[CollectionReceipt] | type[CollectionRefund],
    project_id: uuid.UUID,
    sale_contract_id: uuid.UUID,
    currency_id: uuid.UUID,
) -> Decimal:
    mismatched = session.scalar(
        select(model.id).where(
            model.project_id == project_id,
            model.sale_contract_id == sale_contract_id,
            model.currency_id != currency_id,
            *standing_conditions(
                status=model.status,
                confirmed_at=model.confirmed_at,
                reversed_at=model.reversed_at,
                as_of=None,
            ),
        )
    )
    if mismatched is not None:
        raise ConflictError(
            "Confirmed cancellation cash is not all in the contract currency. "
            "Correct the cash records before calculating refund terms."
        )
    return _money(
        session.scalar(
            select(func.coalesce(func.sum(model.amount), 0)).where(
                model.project_id == project_id,
                model.sale_contract_id == sale_contract_id,
                model.currency_id == currency_id,
                *standing_conditions(
                    status=model.status,
                    confirmed_at=model.confirmed_at,
                    reversed_at=model.reversed_at,
                    as_of=None,
                ),
            )
        )
    )


def eligible_cancellation_cash(
    session: Session,
    *,
    project_id: uuid.UUID,
    sale_contract_id: uuid.UUID,
    currency_id: uuid.UUID,
) -> EligibleCancellationCash:
    """Return gross confirmed receipts less standing confirmed refunds.

    Receipt allocations are intentionally absent.  Unapplied confirmed cash is
    still held for the buyer.  Reversed receipts/refunds follow the platform's
    canonical current-standing predicate, and subtracting prior confirmed
    refunds prevents the same cash becoming refundable twice.
    """
    receipts = _standing_total(
        session,
        model=CollectionReceipt,
        project_id=project_id,
        sale_contract_id=sale_contract_id,
        currency_id=currency_id,
    )
    refunds = _standing_total(
        session,
        model=CollectionRefund,
        project_id=project_id,
        sale_contract_id=sale_contract_id,
        currency_id=currency_id,
    )
    eligible = _money(receipts - refunds)
    if eligible < 0:
        raise ConflictError(
            "Confirmed refunds exceed confirmed buyer cash. Correct the Collections "
            "account before calculating cancellation terms."
        )
    return EligibleCancellationCash(
        currency_id=currency_id,
        confirmed_receipts=receipts,
        confirmed_refunds=refunds,
        eligible_collected_amount=eligible,
    )
