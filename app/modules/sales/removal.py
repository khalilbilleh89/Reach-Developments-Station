"""Master Administrator closes a mistaken sale; all linked evidence is retained."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import service
from app.modules.sales.models import (
    RESERVATION_COMMITTED,
    SALE_COMMITTED,
    HandoverRecord,
    Reservation,
    SaleCancellation,
    SaleContract,
)


def remove_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext, reason: str
) -> None:
    if not actor.is_master_admin:
        raise PermissionDeniedError("Only Master Administrator may remove a sale.")
    if not reason.strip():
        raise ValidationError("Give a reason for removing this sale.")
    project = lock_project(session, project.id)
    sale = service.get_sale(session, project=project, sale_id=sale_id, actor=actor)
    unit = service.inventory_service.lock_unit(session, project_id=project.id, unit_id=sale.unit_id)
    sale = service._lock_sale(session, project_id=project.id, sale_id=sale.id)
    if sale.status == "cancelled":
        return
    # Completing a governed cancellation never invents a registry withdrawal,
    # refund decision, cure-period waiver or recovery of a handed-over property.
    cancellation = service._open_cancellation(session, sale_id=sale.id)
    if cancellation is not None:
        raise ConflictError(
            "This sale has a cancellation in progress. Complete its Cancellation tab."
        )
    events = service._recorded_event_types(session, sale_id=sale.id)
    if events & service.REGISTRY_ENGAGED_EVENTS:
        raise ConflictError(
            "Record the registry withdrawal through Cancellation before removing this sale."
        )
    handover = session.scalar(
        select(HandoverRecord).where(
            HandoverRecord.project_id == project.id, HandoverRecord.sale_contract_id == sale.id
        )
    )
    if handover is not None and handover.status == "handed_over":
        raise ConflictError(
            "This unit has been handed over. Resolve its handover before cancellation."
        )
    # A fully executed sale follows the existing money/legal cancellation flow.
    # The one-action removal is for draft and unsigned test entries.
    if events & {"buyer_signed", "seller_signed"} or (
        sale.status != "draft" and unit.collection_status != "not_started"
    ):
        raise ConflictError(
            "This sale has legal or collection activity. "
            "Use Start cancellation to resolve its terms."
        )
    reservation = service._lock_reservation(
        session, project_id=project.id, reservation_id=sale.reservation_id
    )
    other_sale = session.scalar(
        select(SaleContract.id).where(
            SaleContract.project_id == project.id,
            SaleContract.unit_id == unit.id,
            SaleContract.id != sale.id,
            SaleContract.status.in_(SALE_COMMITTED),
        )
    )
    other_reservation = session.scalar(
        select(Reservation.id).where(
            Reservation.project_id == project.id,
            Reservation.unit_id == unit.id,
            Reservation.id != reservation.id,
            Reservation.status.in_(RESERVATION_COMMITTED),
        )
    )
    today = service.inventory_fields.business_today()
    before = {"status": sale.status, "unit_id": str(unit.id), "client_id": str(sale.client_id)}
    sale.status = "cancelled"
    sale.cancelled_at = service._now()
    # An old draft may coexist with a newer commitment: never release its unit.
    if (
        other_sale is None
        and other_reservation is None
        and unit.commercial_status in {"reserved", "contract_pending"}
    ):
        service._release_or_hold(
            session,
            project=project,
            unit=unit,
            actor=actor,
            effective_date=today,
            reason=reason.strip(),
        )
    if reservation.status not in {"cancelled", "expired"}:
        previous = reservation.status
        reservation.status = "cancelled"
        reservation.closed_at = service._now()
        reservation.closure_reason = reason.strip()
        service._record_reservation_event(
            session,
            reservation=reservation,
            from_status=previous,
            to_status="cancelled",
            effective_date=today,
            actor=actor,
            reason=reason.strip(),
        )
    if handover is not None:
        handover.status = "cancelled"
    case = SaleCancellation(
        project_id=project.id,
        sale_contract_id=sale.id,
        initiated_by_party="seller",
        initiation_date=today,
        termination_date=today,
        unit_return_date=today,
        status="completed",
        reason=reason.strip(),
        reason_code="master_admin_removal",
        financial_approval_required=False,
        legal_withdrawal_required=False,
        legal_withdrawal_status="not_required",
        remarketing_required=False,
        created_by_user_id=actor.user_id,
    )
    session.add(case)
    session.flush()
    record_event(
        session,
        action="sale_contract.cancelled",
        entity_type="sale_contract",
        entity_id=sale.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before=before,
        after={
            "status": "cancelled",
            "master_admin_removal": True,
            "cancellation_id": str(case.id),
        },
    )
    record_event(
        session,
        action="sale_cancellation.completed",
        entity_type="sale_cancellation",
        entity_id=case.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        after={"status": "completed", "sale_contract_id": str(sale.id)},
    )
    session.commit()
