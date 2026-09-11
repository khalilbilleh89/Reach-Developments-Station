"""Recorded acquisition costs and explicitly user-entered market assumptions.

No market data, tax advice, GDV inference or FX conversion. Calculations are
Decimal-only and estimates never feed the acquisition-cost ledger.
"""

from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.modules.audit.service import record_event
from app.modules.projects.models import LandMarketAssumption, LandParcel, PlanningControl, Project
from app.modules.projects.service import get_parcel, lock_project

CENT = Decimal("0.01")
ZERO = Decimal("0")
SQFT_TO_SQM = Decimal("0.09290304")
MAX_MONEY = Decimal("9999999999999999.99")


def amount(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return (numerator / denominator).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def cost_breakdown(parcel: LandParcel) -> dict[str, Any]:
    price = parcel.purchase_price
    rate = parcel.acquisition_tax_rate_fraction
    tax = amount(price * rate) if price is not None and rate is not None else None
    parts = [
        tax,
        parcel.acquisition_fees,
        parcel.agent_fee_amount,
        parcel.legal_fee_amount,
        parcel.registration_fee_amount,
    ]
    fees = amount(sum(parts, ZERO)) if all(p is not None for p in parts) else None
    total = amount(price + fees) if price is not None and fees is not None else None
    return {
        "acquisition_tax_amount": tax,
        "total_acquisition_fees": fees,
        "total_acquisition_cost": total,
        "total_acquisition_cost_basis": "complete" if total is not None else "incomplete_inputs",
        "agent_fee_rate_fraction": ratio(parcel.agent_fee_amount, price),
        "legal_fee_rate_fraction": ratio(parcel.legal_fee_amount, price),
        "registration_fee_rate_fraction": ratio(parcel.registration_fee_amount, price),
    }


def project_acquisition_total(session: Session, *, project_id: uuid.UUID) -> Decimal:
    """Known recorded costs for the existing allocation contract, including itemized fees.

    Preserve its historical partial-input semantics; completeness is exposed
    separately by cost_breakdown/management reporting, never inferred here.
    """
    total = ZERO
    for parcel in session.scalars(
        select(LandParcel).where(
            LandParcel.project_id == project_id, LandParcel.is_active.is_(True)
        )
    ):
        tax = cost_breakdown(parcel)["acquisition_tax_amount"]
        total += sum(
            (
                p or ZERO
                for p in [
                    parcel.purchase_price,
                    parcel.acquisition_fees,
                    tax,
                    parcel.agent_fee_amount,
                    parcel.legal_fee_amount,
                    parcel.registration_fee_amount,
                ]
            ),
            ZERO,
        )
    return amount(total)


def derive_analytics(
    parcel: LandParcel,
    planning: PlanningControl | None,
    assumptions: list[LandMarketAssumption],
) -> dict[str, Any]:
    costs = cost_breakdown(parcel)
    factor = SQFT_TO_SQM if parcel.area_unit == "sqft" else Decimal("1")
    area = parcel.land_area * factor
    buildable = (
        planning.maximum_gfa * factor if planning and planning.maximum_gfa is not None else None
    )
    total = costs["total_acquisition_cost"]
    years = []
    opening = parcel.purchase_price
    for row in sorted(assumptions, key=lambda item: item.year):
        # No inferred rates for omitted years, and no acquisition fee appreciation.
        with localcontext() as ctx:
            ctx.prec = 40
            value = (
                opening * (Decimal("1") + row.change_rate_fraction) if opening is not None else None
            )
            closing = amount(value) if value is not None and value <= MAX_MONEY else None
        years.append(
            {
                "year": row.year,
                "change_rate_fraction": row.change_rate_fraction,
                "opening_value": opening,
                "estimated_value": closing,
                "value_basis": "calculated"
                if closing is not None
                else "missing_price_or_out_of_range",
            }
        )
        opening = closing
    return {
        "land_area_sqm": area,
        "max_buildable_area_sqm": buildable,
        "purchase_cost_per_sqm": amount(parcel.purchase_price / area)
        if parcel.purchase_price is not None and area > 0
        else None,
        "purchase_cost_per_buildable_sqm": amount(parcel.purchase_price / buildable)
        if parcel.purchase_price is not None and buildable is not None and buildable > 0
        else None,
        "acquisition_cost_per_sqm": amount(total / area)
        if total is not None and area > 0
        else None,
        "acquisition_cost_per_buildable_sqm": amount(total / buildable)
        if total is not None and buildable is not None and buildable > 0
        else None,
        "purchase_cost_to_gdv_fraction": ratio(parcel.purchase_price, parcel.expected_gdv_amount),
        "acquisition_cost_to_gdv_fraction": ratio(total, parcel.expected_gdv_amount),
        "market_years": years,
    }


def read_analytics(session: Session, *, parcel: LandParcel) -> dict[str, Any]:
    planning = session.scalar(
        select(PlanningControl).where(
            PlanningControl.parcel_id == parcel.id, PlanningControl.project_id == parcel.project_id
        )
    )
    assumptions = list(
        session.scalars(
            select(LandMarketAssumption)
            .where(LandMarketAssumption.parcel_id == parcel.id)
            .order_by(LandMarketAssumption.year)
        )
    )
    return derive_analytics(parcel, planning, assumptions)


def write_market_assumption(
    session: Session,
    *,
    project: Project,
    parcel_id: uuid.UUID,
    year: int,
    change_rate_fraction: Decimal,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> None:
    lock_project(session, project.id)
    parcel = get_parcel(session, project_id=project.id, parcel_id=parcel_id)
    session.refresh(parcel)
    if parcel.acquisition_date and year < parcel.acquisition_date.year:
        raise ValidationError("The market year cannot precede the acquisition year.")
    row = session.scalar(
        select(LandMarketAssumption)
        .where(LandMarketAssumption.parcel_id == parcel.id, LandMarketAssumption.year == year)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    before = {"change_rate_fraction": str(row.change_rate_fraction)} if row else None
    if row is None:
        row = LandMarketAssumption(
            parcel_id=parcel.id, year=year, change_rate_fraction=change_rate_fraction
        )
        session.add(row)
    else:
        row.change_rate_fraction = change_rate_fraction
    session.flush()
    record_event(
        session,
        action="land_market_assumption.recorded",
        entity_type="land_market_assumption",
        entity_id=row.id,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
        before=before,
        after={
            "parcel_id": str(parcel.id),
            "year": year,
            "change_rate_fraction": str(change_rate_fraction),
        },
    )
    session.commit()
