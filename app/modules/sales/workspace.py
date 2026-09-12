"""Sales-owned selection, price intent and transaction reads. No Inventory writes."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import exists, func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ServiceError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory.models import Building, Floor, Phase, Unit
from app.modules.inventory.physical import gross_measurement
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import permissions, service
from app.modules.sales.models import (
    RESERVATION_COMMITTED,
    RESERVATION_PREPARING,
    SALE_COMMITTED,
    Client,
    Reservation,
    SaleContract,
)
from app.modules.sales.price_facts import variance_amount, variance_fraction, variance_percentage


def price_facts(reference: Decimal, agreed: Decimal) -> dict[str, Any]:
    return {
        "reference_price_ex_tax": reference,
        "sales_price_ex_tax": agreed,
        "price_variance_amount": variance_amount(reference, agreed),
        "price_variance_fraction": variance_fraction(reference, agreed),
        "price_variance_percentage": variance_percentage(reference, agreed),
    }


def price_edit_blocker(actor: ActorContext, reservation: Reservation) -> str | None:
    try:
        permissions.require_reservation_writer(actor)
        service._require_preparing(reservation)
    except ServiceError as exc:
        return str(exc)
    return None


def reservation_preview(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    reservation_id: uuid.UUID,
    sales_price_ex_tax: Decimal,
) -> dict[str, Any]:
    permissions.require_reservation_writer(actor)
    reservation = service.get_reservation(
        session, project=project, actor=actor, reservation_id=reservation_id
    )
    service._require_preparing(reservation)
    unit = permissions.require_sellable_unit(
        session, project=project, actor=actor, unit_id=reservation.unit_id
    )
    inputs = service._quote_inputs(
        session, reservation_id=reservation.id, buyer_fee_total=reservation.buyer_fee_total
    )
    inputs["sales_price_ex_tax"] = sales_price_ex_tax
    quote = service.pricing_service.quote_preview(
        session,
        project=project,
        unit=unit,
        inputs=inputs,
        frozen_version_id=reservation.unit_price_version_id,
    )
    if quote["currency_id"] != reservation.currency_id:
        raise ConflictError("The price currency differs from the reservation.")
    return {
        **price_facts(quote["approved_reference_price_ex_tax"], quote["net_contract_price_ex_tax"]),
        "currency_id": quote["currency_id"],
        "unit_price_version_id": quote["unit_price_version_id"],
        "exception_approval_required": quote["approval_required"],
        "exception_reason": quote["approval_reason"],
        "tax_total": quote["tax_total"],
        "total_buyer_payable": quote["total_buyer_payable_preview"],
    }


def preview(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    unit_id: uuid.UUID,
    sales_price_ex_tax: Decimal,
    expected_price_version_id: uuid.UUID,
) -> dict[str, Any]:
    permissions.require_reservation_writer(actor)
    permissions.require_operational_project(project)
    unit = permissions.require_sellable_unit(session, project=project, unit_id=unit_id, actor=actor)
    service.require_available_reservation_unit(session, unit=unit)
    quote = service.pricing_service.quote_preview(
        session, project=project, unit=unit, inputs={"sales_price_ex_tax": sales_price_ex_tax}
    )
    if quote["unit_price_version_id"] != expected_price_version_id:
        raise ConflictError(
            "The unit list price changed. Refresh and review the price before saving."
        )
    return {
        **price_facts(quote["approved_reference_price_ex_tax"], quote["net_contract_price_ex_tax"]),
        "currency_id": quote["currency_id"],
        "unit_price_version_id": quote["unit_price_version_id"],
        "exception_approval_required": quote["approval_required"],
        "exception_reason": quote["approval_reason"],
        "tax_total": quote["tax_total"],
        "total_buyer_payable": quote["total_buyer_payable_preview"],
    }


def change_price(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    reservation_id: uuid.UUID,
    sales_price_ex_tax: Decimal,
) -> Reservation:
    permissions.require_reservation_writer(actor)
    permissions.require_operational_project(project)
    reservation = service.get_reservation(
        session, project=project, actor=actor, reservation_id=reservation_id
    )
    project = lock_project(session, project.id)
    unit = service.inventory_service.lock_unit(
        session, project_id=project.id, unit_id=reservation.unit_id
    )
    reservation = service._lock_reservation(
        session, project_id=project.id, reservation_id=reservation.id
    )
    service._require_preparing(reservation)
    before = service._snapshot(reservation, service._RESERVATION_FIELDS)
    reservation.agreed_price_target_ex_tax = service.money(sales_price_ex_tax)
    service._freeze_quote(
        session,
        project=project,
        unit=unit,
        reservation=reservation,
        buyer_fee_total=reservation.buyer_fee_total,
        actor=actor,
    )
    service._flush(session)
    record_event(
        session,
        action="reservation.sales_price_set",
        entity_type="reservation",
        entity_id=reservation.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=service._snapshot(reservation, service._RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


def unit_options(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    search: str = "",
    phase_id: uuid.UUID | None = None,
    building_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 30,
) -> dict[str, Any]:
    """Bounded candidate pages; next_offset advances past examined candidates.

    Release and current-price-basis rules are canonical service checks, not a
    second SQL implementation. A candidate page may contain no eligible options;
    the cursor still progresses without claiming a fabricated eligible total.
    """
    permissions.require_sales_reader(actor)
    permissions.require_operational_project(project)
    query = (
        select(Unit, Floor, Building, Phase)
        .join(Floor, Floor.id == Unit.floor_id)
        .join(Building, Building.id == Floor.building_id)
        .join(Phase, Phase.id == Building.phase_id)
        .where(
            Unit.project_id == project.id,
            Unit.is_active.is_(True),
            Unit.commercial_status == "available",
        )
    )
    allowed = permissions.visible_unit_ids(session, project_id=project.id, actor=actor)
    if allowed is not None:
        query = query.where(Unit.id.in_(allowed))
    for model, statuses in ((Reservation, RESERVATION_COMMITTED), (SaleContract, SALE_COMMITTED)):
        query = query.where(
            ~exists(select(model.id).where(model.unit_id == Unit.id, model.status.in_(statuses)))
        )
    if search.strip():
        query = query.where(
            or_(
                Unit.unit_reference.icontains(search.strip(), autoescape=True),
                Unit.unit_number.icontains(search.strip(), autoescape=True),
                Building.code.icontains(search.strip(), autoescape=True),
                Building.name.icontains(search.strip(), autoescape=True),
                Phase.code.icontains(search.strip(), autoescape=True),
                Phase.name.icontains(search.strip(), autoescape=True),
            )
        )
    if phase_id:
        query = query.where(Phase.id == phase_id)
    if building_id:
        query = query.where(Building.id == building_id)
    candidates = list(
        session.execute(
            query.order_by(Unit.unit_reference, Unit.id).offset(offset).limit(limit + 1)
        )
    )
    items = []
    for unit, floor, building, phase in candidates[:limit]:
        try:
            service.require_available_reservation_unit(session, unit=unit)
            quote = service.pricing_service.quote_preview(
                session, project=project, unit=unit, inputs={}
            )
        except ServiceError:
            continue
        schedule = service.inventory_service.approved_schedule(session, unit_id=unit.id)
        measurement = gross_measurement(
            service.inventory_service.area_lines(session, project_id=project.id, schedule=schedule)
            if schedule
            else []
        )
        items.append(
            {
                "unit_id": unit.id,
                "unit_reference": unit.unit_reference,
                "building_name": building.name,
                "floor_name": floor.label,
                "phase_name": phase.name,
                "unit_type": unit.unit_type_code,
                "commercial_availability": unit.commercial_status,
                "gross_area": measurement["gross_area"],
                "area_unit": measurement["gross_area_unit"],
                "unit_price_version_id": quote["unit_price_version_id"],
                "reference_price_ex_tax": quote["approved_reference_price_ex_tax"],
                "currency_id": quote["currency_id"],
            }
        )
    return {"items": items, "next_offset": offset + limit if len(candidates) > limit else None}


def transactions(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    search: str = "",
    history: bool = False,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    permissions.require_sales_reader(actor)
    allowed = permissions.visible_unit_ids(session, project_id=project.id, actor=actor)
    queries = []
    for model, kind, reference in (
        (Reservation, "reservation", Reservation.reservation_number),
        (SaleContract, "sale", SaleContract.sale_number),
    ):
        query = (
            select(
                model.id,
                literal(kind).label("kind"),
                reference.label("reference"),
                model.status,
                model.created_at,
                model.currency_id,
                model.reference_price_ex_tax,
                model.net_contract_price_ex_tax.label("sales_price_ex_tax"),
                Unit.id.label("unit_id"),
                Unit.unit_reference,
                Client.display_name.label("client_display_name"),
                Unit.legal_status,
                Unit.collection_status,
                (SaleContract.spa_number if kind == "sale" else literal(None)).label("spa_number"),
            )
            .join(Unit, Unit.id == model.unit_id)
            .join(Client, Client.id == model.client_id)
            .where(
                model.project_id == project.id,
                Unit.project_id == project.id,
                Client.project_id == project.id,
            )
        )
        if allowed is not None:
            query = query.where(model.unit_id.in_(allowed))
        if permissions.restricts_clients_to_own(actor):
            query = query.where(Client.owner_advisor_user_id == actor.user_id)
        if not history:
            if kind == "reservation":
                query = query.where(
                    model.status.in_(RESERVATION_PREPARING | RESERVATION_COMMITTED),
                    ~exists(
                        select(SaleContract.id).where(
                            SaleContract.reservation_id == Reservation.id,
                            SaleContract.status.in_({"draft", *SALE_COMMITTED}),
                        )
                    ),
                )
            else:
                query = query.where(model.status.in_({"draft", *SALE_COMMITTED}))
        if status:
            query = query.where(model.status == status)
        if search.strip():
            fields = [reference, Unit.unit_reference, Unit.unit_number, Client.display_name]
            if kind == "sale":
                fields.append(SaleContract.spa_number)
            query = query.where(
                or_(*(field.icontains(search.strip(), autoescape=True) for field in fields))
            )
        queries.append(query)
    combined = union_all(*queries).subquery()
    total = session.scalar(select(func.count()).select_from(combined)) or 0
    rows = session.execute(
        select(combined)
        .order_by(combined.c.created_at.desc(), combined.c.id.desc(), combined.c.kind)
        .offset(offset)
        .limit(limit)
    ).mappings()
    return {
        "items": [
            {**row, **price_facts(row["reference_price_ex_tax"], row["sales_price_ex_tax"])}
            for row in rows
        ],
        "total": total,
    }
