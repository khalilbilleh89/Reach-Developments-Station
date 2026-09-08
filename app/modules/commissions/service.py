"""Sale-sourced, exactly reconciled commission distribution lifecycle."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.db.base import MONEY_EXPONENT
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.commissions import models, schemas
from app.modules.commissions.permissions import require_preparer, require_releaser
from app.modules.inventory.models import Unit
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales.models import SALE_ACTIVE, SaleContract, SaleContractParty


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_EXPONENT, rounding=ROUND_HALF_UP)


def _terms(base: Decimal, rate: Decimal, sold: Decimal) -> tuple[Decimal, Decimal]:
    if base <= 0 or base > sold:
        raise ValidationError(
            "Commissionable base must be above zero and no greater than the sold price."
        )
    if rate <= 0 or rate > 1:
        raise ValidationError("Granted commission rate must be above 0% and no greater than 100%.")
    return money(base), money(base * rate)


def _get(
    session: Session, project: Project, identifier: uuid.UUID, *, lock: bool = False
) -> models.CommissionGrant:
    statement = select(models.CommissionGrant).where(
        models.CommissionGrant.id == identifier, models.CommissionGrant.project_id == project.id
    )
    if lock:
        statement = statement.with_for_update()
    row = session.scalar(statement)
    if row is None:
        raise NotFoundError("Commission not found.")
    return row


def _allocations(session: Session, commission_id: uuid.UUID) -> list[models.CommissionAllocation]:
    return list(
        session.scalars(
            select(models.CommissionAllocation)
            .where(models.CommissionAllocation.commission_id == commission_id)
            .order_by(models.CommissionAllocation.sequence)
        )
    )


def _sale_context(session: Session, row: models.CommissionGrant) -> tuple[SaleContract, Unit, str]:
    sale = session.get(SaleContract, row.sale_contract_id)
    unit = session.get(Unit, row.unit_id)
    buyers = list(
        session.scalars(
            select(SaleContractParty.name_as_identification)
            .where(SaleContractParty.sale_contract_id == row.sale_contract_id)
            .order_by(SaleContractParty.created_at)
        )
    )
    return sale, unit, ", ".join(buyers) or "Buyer not named"


def out(session: Session, row: models.CommissionGrant) -> schemas.GrantOut:
    allocations = _allocations(session, row.id)
    sale, unit, buyer = _sale_context(session, row)
    rate_total = sum((item.rate_fraction for item in allocations), Decimal("0.000000"))
    amount_total = sum((item.calculated_amount for item in allocations), Decimal("0.00"))
    return schemas.GrantOut(
        id=row.id,
        project_id=row.project_id,
        sale_contract_id=row.sale_contract_id,
        sale_reference=sale.sale_number,
        sale_status=sale.status,
        unit_id=row.unit_id,
        unit_reference=unit.unit_reference,
        buyer_display=buyer,
        currency_id=row.currency_id,
        sold_price_snapshot=row.sold_price_snapshot,
        commissionable_base_amount=row.commissionable_base_amount,
        granted_rate_fraction=row.granted_rate_fraction,
        commission_total=row.commission_total,
        status=row.status,
        notes=row.notes,
        prepared_by_user_id=row.prepared_by_user_id,
        released_by_user_id=row.released_by_user_id,
        released_at=row.released_at,
        reversed_by_user_id=row.reversed_by_user_id,
        reversed_at=row.reversed_at,
        reversal_reason=row.reversal_reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
        allocations=allocations,
        allocation_rate_total=rate_total,
        allocation_amount_total=amount_total,
        is_reconciled=bool(allocations)
        and rate_total == row.granted_rate_fraction
        and amount_total == row.commission_total,
    )


def list_grants(session: Session, project: Project) -> list[schemas.GrantOut]:
    return [
        out(session, row)
        for row in session.scalars(
            select(models.CommissionGrant)
            .where(models.CommissionGrant.project_id == project.id)
            .order_by(models.CommissionGrant.created_at.desc())
        )
    ]


def eligible_sales(session: Session, project: Project) -> list[schemas.EligibleSaleOut]:
    live_sales = select(models.CommissionGrant.sale_contract_id).where(
        models.CommissionGrant.status.in_(("draft", "released"))
    )
    sales = list(
        session.scalars(
            select(SaleContract)
            .where(
                SaleContract.project_id == project.id,
                SaleContract.status == SALE_ACTIVE,
                SaleContract.id.not_in(live_sales),
            )
            .order_by(SaleContract.sale_number)
        )
    )
    result = []
    for sale in sales:
        unit = session.get(Unit, sale.unit_id)
        parties = list(
            session.scalars(
                select(SaleContractParty.name_as_identification).where(
                    SaleContractParty.sale_contract_id == sale.id
                )
            )
        )
        result.append(
            schemas.EligibleSaleOut(
                id=sale.id,
                sale_reference=sale.sale_number,
                unit_reference=unit.unit_reference,
                buyer_display=", ".join(parties) or "Buyer not named",
                sold_price=sale.total_contract_price,
                currency_id=sale.currency_id,
            )
        )
    return result


def create(
    session: Session, project: Project, actor: ActorContext, payload: schemas.GrantCreate
) -> schemas.GrantOut:
    require_preparer(actor)
    lock_project(session, project.id)
    sale = session.scalar(
        select(SaleContract)
        .where(SaleContract.id == payload.sale_contract_id, SaleContract.project_id == project.id)
        .with_for_update()
    )
    if sale is None:
        raise NotFoundError("Active sale contract not found.")
    if sale.status != SALE_ACTIVE:
        raise ConflictError("Only an active sale contract is eligible for commission distribution.")
    base, total = _terms(
        payload.commissionable_base_amount, payload.granted_rate_fraction, sale.total_contract_price
    )
    row = models.CommissionGrant(
        project_id=project.id,
        sale_contract_id=sale.id,
        unit_id=sale.unit_id,
        currency_id=sale.currency_id,
        sold_price_snapshot=sale.total_contract_price,
        commissionable_base_amount=base,
        granted_rate_fraction=payload.granted_rate_fraction,
        commission_total=total,
        notes=payload.notes,
        prepared_by_user_id=actor.user_id,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("This sale already has a live commission distribution.") from exc
    _audit(
        session,
        actor,
        "commission.draft_created",
        row,
        after={
            "sale_contract_id": sale.id,
            "sold_price_snapshot": sale.total_contract_price,
            "commissionable_base_amount": base,
            "granted_rate_fraction": payload.granted_rate_fraction,
            "commission_total": total,
        },
    )
    session.commit()
    session.refresh(row)
    return out(session, row)


def _audit(
    session: Session,
    actor: ActorContext,
    action: str,
    row: models.CommissionGrant | models.CommissionAllocation,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> None:
    record_event(
        session,
        action=action,
        entity_type=type(row).__name__,
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=after,
        reason=reason,
    )


def _draft(row: models.CommissionGrant) -> None:
    if row.status != "draft":
        raise ConflictError("Released and reversed commission terms are immutable.")


def _recalculate(session: Session, row: models.CommissionGrant) -> None:
    allocations = _allocations(session, row.id)
    for item in allocations:
        item.calculated_amount = money(row.commissionable_base_amount * item.rate_fraction)
    if (
        allocations
        and sum((item.rate_fraction for item in allocations), Decimal("0"))
        == row.granted_rate_fraction
    ):
        residual = row.commission_total - sum(
            (item.calculated_amount for item in allocations), Decimal("0")
        )
        allocations[-1].calculated_amount += residual
    session.flush()


def update(
    session: Session,
    project: Project,
    actor: ActorContext,
    identifier: uuid.UUID,
    payload: schemas.GrantUpdate,
) -> schemas.GrantOut:
    require_preparer(actor)
    lock_project(session, project.id)
    row = _get(session, project, identifier, lock=True)
    _draft(row)
    if row.updated_at != payload.expected_updated_at:
        raise ConflictError("Commission changed. Reload before saving.")
    base, total = _terms(
        payload.commissionable_base_amount, payload.granted_rate_fraction, row.sold_price_snapshot
    )
    before = {
        "commissionable_base_amount": row.commissionable_base_amount,
        "granted_rate_fraction": row.granted_rate_fraction,
        "commission_total": row.commission_total,
    }
    (
        row.commissionable_base_amount,
        row.granted_rate_fraction,
        row.commission_total,
        row.notes,
        row.prepared_by_user_id,
    ) = base, payload.granted_rate_fraction, total, payload.notes, actor.user_id
    _recalculate(session, row)
    _audit(
        session,
        actor,
        "commission.draft_updated",
        row,
        before,
        {
            "commissionable_base_amount": base,
            "granted_rate_fraction": payload.granted_rate_fraction,
            "commission_total": total,
        },
    )
    session.commit()
    session.refresh(row)
    return out(session, row)


def add_allocation(
    session: Session,
    project: Project,
    actor: ActorContext,
    identifier: uuid.UUID,
    payload: schemas.AllocationWrite,
) -> schemas.GrantOut:
    require_preparer(actor)
    lock_project(session, project.id)
    row = _get(session, project, identifier, lock=True)
    _draft(row)
    if payload.rate_fraction <= 0 or payload.rate_fraction > 1:
        raise ValidationError("Beneficiary percentage must be above 0% and no greater than 100%.")
    sequence = (
        session.scalar(
            select(func.max(models.CommissionAllocation.sequence)).where(
                models.CommissionAllocation.commission_id == row.id
            )
        )
        or 0
    ) + 1
    allocation = models.CommissionAllocation(
        project_id=project.id,
        commission_id=row.id,
        beneficiary_name=payload.beneficiary_name.strip(),
        rate_fraction=payload.rate_fraction,
        calculated_amount=money(row.commissionable_base_amount * payload.rate_fraction),
        sequence=sequence,
        notes=payload.notes,
    )
    session.add(allocation)
    session.flush()
    row.prepared_by_user_id = actor.user_id
    _recalculate(session, row)
    _audit(session, actor, "commission.allocation_added", allocation, after=payload.model_dump())
    session.commit()
    return out(session, row)


def update_allocation(
    session: Session,
    project: Project,
    actor: ActorContext,
    commission_id: uuid.UUID,
    allocation_id: uuid.UUID,
    payload: schemas.AllocationUpdate,
) -> schemas.GrantOut:
    require_preparer(actor)
    lock_project(session, project.id)
    row = _get(session, project, commission_id, lock=True)
    _draft(row)
    allocation = session.scalar(
        select(models.CommissionAllocation).where(
            models.CommissionAllocation.id == allocation_id,
            models.CommissionAllocation.commission_id == row.id,
            models.CommissionAllocation.project_id == project.id,
        )
    )
    if allocation is None:
        raise NotFoundError("Commission allocation not found.")
    if allocation.updated_at != payload.expected_updated_at:
        raise ConflictError("Allocation changed. Reload before saving.")
    if payload.rate_fraction <= 0 or payload.rate_fraction > 1:
        raise ValidationError("Beneficiary percentage must be above 0% and no greater than 100%.")
    before = {
        "beneficiary_name": allocation.beneficiary_name,
        "rate_fraction": allocation.rate_fraction,
    }
    allocation.beneficiary_name = payload.beneficiary_name.strip()
    allocation.rate_fraction = payload.rate_fraction
    allocation.notes = payload.notes
    row.prepared_by_user_id = actor.user_id
    _recalculate(session, row)
    _audit(
        session,
        actor,
        "commission.allocation_updated",
        allocation,
        before,
        payload.model_dump(exclude={"expected_updated_at"}),
    )
    session.commit()
    return out(session, row)


def remove_allocation(
    session: Session,
    project: Project,
    actor: ActorContext,
    commission_id: uuid.UUID,
    allocation_id: uuid.UUID,
) -> schemas.GrantOut:
    require_preparer(actor)
    lock_project(session, project.id)
    row = _get(session, project, commission_id, lock=True)
    _draft(row)
    allocation = session.scalar(
        select(models.CommissionAllocation).where(
            models.CommissionAllocation.id == allocation_id,
            models.CommissionAllocation.commission_id == row.id,
        )
    )
    if allocation is None:
        raise NotFoundError("Commission allocation not found.")
    _audit(
        session,
        actor,
        "commission.allocation_removed",
        allocation,
        before={
            "beneficiary_name": allocation.beneficiary_name,
            "rate_fraction": allocation.rate_fraction,
        },
    )
    session.delete(allocation)
    session.flush()
    row.prepared_by_user_id = actor.user_id
    _recalculate(session, row)
    session.commit()
    return out(session, row)


def release(
    session: Session, project: Project, actor: ActorContext, identifier: uuid.UUID
) -> schemas.GrantOut:
    require_releaser(actor)
    lock_project(session, project.id)
    row = _get(session, project, identifier, lock=True)
    _draft(row)
    if row.prepared_by_user_id == actor.user_id:
        raise PermissionDeniedError("The person who prepared this commission may not release it.")
    _recalculate(session, row)
    detail = out(session, row)
    if not detail.is_reconciled:
        raise ConflictError(
            "Beneficiary percentages and amounts must reconcile exactly before release."
        )
    now = datetime.now(UTC)
    row.status, row.released_by_user_id, row.released_at = "released", actor.user_id, now
    session.flush()
    _audit(session, actor, "commission.released", row, {"status": "draft"}, {"status": "released"})
    session.commit()
    session.refresh(row)
    return out(session, row)


def reverse(
    session: Session, project: Project, actor: ActorContext, identifier: uuid.UUID, reason: str
) -> schemas.GrantOut:
    require_releaser(actor)
    lock_project(session, project.id)
    row = _get(session, project, identifier, lock=True)
    if row.status != "released":
        raise ConflictError("Only a released commission may be reversed.")
    reason = reason.strip()
    if not reason:
        raise ValidationError("Reversal reason is required.")
    row.status, row.reversed_by_user_id, row.reversed_at, row.reversal_reason = (
        "reversed",
        actor.user_id,
        datetime.now(UTC),
        reason,
    )
    session.flush()
    _audit(
        session,
        actor,
        "commission.reversed",
        row,
        {"status": "released"},
        {"status": "reversed"},
        reason,
    )
    session.commit()
    session.refresh(row)
    return out(session, row)
