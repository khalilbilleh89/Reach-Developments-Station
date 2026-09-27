"""Sales-owned participation in a project denomination correction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.sales.models import Reservation, SaleContract, SaleContractTaxLine


@dataclass(frozen=True)
class SalesCurrencyCorrection:
    counts: dict[str, int]
    sale_contract_ids: frozenset[uuid.UUID]


def _correct_snapshot(
    value: object, old_currency_id: uuid.UUID, new_currency_id: uuid.UUID
) -> object:
    """Replace denomination identifiers inside Sales-owned quote evidence only."""
    if isinstance(value, dict):
        return {
            key: (
                str(new_currency_id)
                if "currency_id" in key and item == str(old_currency_id)
                else _correct_snapshot(item, old_currency_id, new_currency_id)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_correct_snapshot(item, old_currency_id, new_currency_id) for item in value]
    return value


def correct_project_base_currency(
    session: Session,
    *,
    project_id: uuid.UUID,
    old_currency_id: uuid.UUID,
    new_currency_id: uuid.UUID,
    direct_price_version_ids: frozenset[uuid.UUID],
) -> SalesCurrencyCorrection:
    """Relabel sales descended from corrected direct project-base prices."""
    counts: dict[str, int] = {}
    if not direct_price_version_ids:
        return SalesCurrencyCorrection(counts=counts, sale_contract_ids=frozenset())

    reservations = list(
        session.scalars(
            select(Reservation)
            .where(
                Reservation.project_id == project_id,
                Reservation.unit_price_version_id.in_(direct_price_version_ids),
                Reservation.currency_id == old_currency_id,
            )
            .with_for_update()
        )
    )
    deposit_count = 0
    for reservation in reservations:
        reservation.currency_id = new_currency_id
        if reservation.deposit_currency_id == old_currency_id:
            reservation.deposit_currency_id = new_currency_id
            deposit_count += 1
        reservation.quote_snapshot_json = cast(
            dict[str, object],
            _correct_snapshot(reservation.quote_snapshot_json, old_currency_id, new_currency_id),
        )
    if reservations:
        counts["reservations.currency_id"] = len(reservations)
        if deposit_count:
            counts["reservations.deposit_currency_id"] = deposit_count

    reservation_ids = {row.id for row in reservations}
    if not reservation_ids:
        return SalesCurrencyCorrection(counts=counts, sale_contract_ids=frozenset())
    sales = list(
        session.scalars(
            select(SaleContract)
            .where(
                SaleContract.project_id == project_id,
                SaleContract.reservation_id.in_(reservation_ids),
                SaleContract.currency_id == old_currency_id,
            )
            .with_for_update()
        )
    )
    for sale in sales:
        sale.currency_id = new_currency_id
        sale.reservation_quote_snapshot_json = cast(
            dict[str, object],
            _correct_snapshot(
                sale.reservation_quote_snapshot_json, old_currency_id, new_currency_id
            ),
        )
    sale_ids = frozenset(row.id for row in sales)
    if sales:
        counts["sale_contracts.currency_id"] = len(sales)
    if sale_ids:
        tax = session.execute(
            update(SaleContractTaxLine)
            .where(
                SaleContractTaxLine.project_id == project_id,
                SaleContractTaxLine.sale_contract_id.in_(sale_ids),
                SaleContractTaxLine.currency_id == old_currency_id,
            )
            .values(currency_id=new_currency_id)
        )
        if tax.rowcount:
            counts["sale_contract_tax_lines.currency_id"] = tax.rowcount
    return SalesCurrencyCorrection(counts=counts, sale_contract_ids=sale_ids)
