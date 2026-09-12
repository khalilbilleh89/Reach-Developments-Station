"""One owner action to register a buyer and commit a unit, with no fictional legal events.

The existing reservation/contract records remain the only sales ledger. Every
step runs without committing; this boundary commits the buyer, frozen contract,
unit status and audit together or rolls all of them back.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory import custom_fields
from app.modules.inventory import service as inventory
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import permissions, service
from app.modules.sales.models import SaleContract


def register_buyer(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    unit_id: uuid.UUID,
    sales_price_ex_tax: Decimal | None = None,
    expected_price_version_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None,
    buyer: dict[str, Any] | None,
    reason: str,
    sale_date: date | None = None,
) -> SaleContract:
    if not actor.is_master_admin:
        raise PermissionDeniedError(
            "Only Master Administrator may register a sale without a separate approval."
        )
    if (client_id is None) == (buyer is None):
        raise ValidationError("Choose an existing buyer or enter a new buyer, not both.")
    if not reason.strip():
        raise ValidationError("Record why this unit is being sold to this buyer.")
    permissions.require_operational_project(project)
    today = custom_fields.business_today()
    effective = sale_date or today
    if effective > today:
        raise ValidationError("A sale cannot be dated in the future.")
    try:
        project = lock_project(session, project.id)
        unit = permissions.require_sellable_unit(
            session, project=project, unit_id=unit_id, actor=actor
        )
        unit = inventory.lock_unit(session, project_id=project.id, unit_id=unit.id)
        if not unit.is_active or unit.commercial_status not in {
            "unreleased",
            "available",
            "held",
            "reserved",
        }:
            raise ConflictError(
                "This unit is inactive or already sold. Open its existing Sale record."
            )
        reservations = service.list_reservations(
            session, project=project, actor=actor, unit_id=unit.id
        )
        reservation = next(
            (row for row in reservations if row.status in {"active", "extended"}), None
        )
        if reservation is not None and reservation.client_id != client_id:
            raise ConflictError(
                "This unit is reserved for another buyer. "
                "Resolve that reservation before changing the buyer."
            )
        if (
            reservation is not None
            and sales_price_ex_tax is not None
            and sales_price_ex_tax != reservation.net_contract_price_ex_tax
        ):
            raise ConflictError(
                "The existing reservation price is frozen. "
                "Use its governed lifecycle to change terms."
            )
        if buyer is not None:
            client = service.create_client(
                session, project=project, actor=actor, commit=False, **buyer
            )
            client_id = client.id
        if unit.commercial_status in {"unreleased", "held"}:
            inventory.transition_commercial_status(
                session,
                project=project,
                unit=unit,
                actor=actor,
                to_status="available",
                effective_date=effective,
                actor_user_id=actor.user_id,
                correlation_id=actor.correlation_id,
                reason=reason,
                owner_override_reason=reason,
                commit=False,
            )
        if reservation is None:
            reservation = service.create_reservation(
                session,
                project=project,
                actor=actor,
                unit_id=unit.id,
                sales_price_ex_tax=sales_price_ex_tax,
                expected_price_version_id=expected_price_version_id,
                client_id=client_id,
                reservation_date=effective,
                expires_on=today,
                price_locked_until=today,
                commit=False,
            )
            if reservation.deposit_gate_status == "pending":
                service.waive_deposit(
                    session,
                    project=project,
                    actor=actor,
                    reservation_id=reservation.id,
                    reason=reason,
                    commit=False,
                )
            if reservation.exception_approval_required:
                service.submit_exception(
                    session,
                    project=project,
                    actor=actor,
                    reservation_id=reservation.id,
                    reason=reason,
                    commit=False,
                )
                service.decide_exception(
                    session,
                    project=project,
                    actor=actor,
                    reservation_id=reservation.id,
                    approved=True,
                    reason=reason,
                    commit=False,
                )
            service.activate_reservation(
                session,
                project=project,
                actor=actor,
                reservation_id=reservation.id,
                effective_date=effective,
                owner_override_reason=reason,
                commit=False,
            )
        sale = service.create_sale(
            session,
            project=project,
            actor=actor,
            reservation_id=reservation.id,
            contract_date=effective,
            commit=False,
        )
        service.submit_sale(
            session,
            project=project,
            actor=actor,
            sale_id=sale.id,
            effective_date=effective,
            commit=False,
        )
        record_event(
            session,
            action="sale_contract.buyer_registered",
            entity_type="sale_contract",
            entity_id=sale.id,
            actor_user_id=actor.user_id,
            correlation_id=actor.correlation_id,
            reason=reason.strip(),
            after={
                "unit_id": str(unit.id),
                "client_id": str(client_id),
                "commercial_status": unit.commercial_status,
                "legal_signatures_recorded": False,
                "owner_override": True,
            },
        )
        session.commit()
        session.refresh(sale)
        return sale
    except Exception:
        session.rollback()
        raise
