"""Collections routes: record cash, confirm it, apply it, and chase the rest.

Handlers validate, authorise and orchestrate. Every rule about what may happen
lives in the service; every rule about who may reach it lives in
``permissions.py``.

Status is never a PATCH. Recording a receipt, confirming it and reversing it are
three acts with three different rights and three sets of preconditions, so each
has its own route: a status column a client could set would be Finance's
signature available to anybody who could reach the endpoint.

There are no DELETE routes. Financial records are reversed, superseded,
resolved or withdrawn, and every one of those keeps what was previously
believed on the record.

Nothing here computes a figure. Outstanding, unapplied, days overdue, aging
bucket and collection status all arrive from the service already decided, so
the browser and the API agree with the ledger by construction rather than by
two implementations happening to match.

Every nested route passes its parent identifier down to the service rather than
letting the child stand on its own. ``/sales/S1/receipts/R2`` is a claim that R2
belongs to S1, and the service refuses the pair — with the same 404 it gives for
a receipt that does not exist — when it does not.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy.orm import Session

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.collections import service
from app.modules.collections.models import (
    RECEIPT_CONFIRMED as _CONFIRMED,
)
from app.modules.collections.models import (
    CollectionReceipt,
)
from app.modules.collections.permissions import CollectionProject
from app.modules.collections.schemas import (
    AgingRowRead,
    AllocationCreate,
    AllocationRead,
    CarryLineRead,
    ClearanceRead,
    ClearanceRequest,
    CollectionActionCreate,
    CollectionActionRead,
    CollectionInstallmentRow,
    CollectionProjectSummary,
    CollectionRegisterRow,
    CollectionSaleSummary,
    DisputeClose,
    DisputeCreate,
    DisputeRead,
    ReceiptCreate,
    ReceiptRead,
    RefundCreate,
    RefundRead,
    RestructureApplyPreview,
    RestructureApplyResponse,
    RestructureCreate,
    RestructureRead,
    ReversalRequest,
    SuggestedAllocationRead,
    WaiverCreate,
    WaiverDecision,
    WaiverRead,
)
from app.modules.projects.models import Project

router = APIRouter(prefix="/projects/{project_id}/collections", tags=["collections"])


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #


def _installment_row(view: object) -> CollectionInstallmentRow:
    return CollectionInstallmentRow.model_validate(view, from_attributes=True)


def _summary_read(
    summary: service.SaleSummary, *, blockers: list[str] | None = None
) -> CollectionSaleSummary:
    return CollectionSaleSummary(
        sale_id=summary.sale_id,
        currency_id=summary.currency_id,
        as_of=summary.as_of,
        active_payment_plan_id=summary.active_payment_plan_id,
        active_payment_plan_version_id=summary.active_payment_plan_version_id,
        scheduled_total=summary.scheduled_total,
        confirmed_receipts_total=summary.confirmed_receipts_total,
        allocated_total=summary.allocated_total,
        unapplied_cash=summary.unapplied_cash,
        outstanding_total=summary.outstanding_total,
        due_total=summary.due_total,
        overdue_total=summary.overdue_total,
        oldest_overdue_days=summary.oldest_overdue_days,
        installments_total=summary.installments_total,
        installments_paid=summary.installments_paid,
        installments_partial=summary.installments_partial,
        installments_overdue=summary.installments_overdue,
        installments_awaiting_trigger=summary.installments_awaiting_trigger,
        open_disputes=summary.open_disputes,
        active_waivers=summary.active_waivers,
        next_action_date=summary.next_action_date,
        derived_collection_status=summary.derived_collection_status,
        refund_due_total=summary.refund_due_total,
        refund_confirmed_total=summary.refund_confirmed_total,
        refund_outstanding=summary.refund_outstanding,
        collection_clearance_status=summary.collection_clearance_status,
        clearance_blockers=blockers if blockers is not None else [],
        installments=[_installment_row(row) for row in summary.rows],
    )


def _receipt_read(
    session: Session, receipt: CollectionReceipt, *, with_allocations: bool = True
) -> ReceiptRead:
    """One receipt, with what is left of it derived rather than stored."""
    return ReceiptRead(
        id=receipt.id,
        sale_contract_id=receipt.sale_contract_id,
        receipt_number=receipt.receipt_number,
        currency_id=receipt.currency_id,
        amount=receipt.amount,
        receipt_date=receipt.receipt_date,
        status=receipt.status,
        bank_reference=receipt.bank_reference,
        external_reference=receipt.external_reference,
        notes=receipt.notes,
        recorded_at=receipt.recorded_at,
        recorded_by_user_id=receipt.recorded_by_user_id,
        confirmed_at=receipt.confirmed_at,
        confirmed_by_user_id=receipt.confirmed_by_user_id,
        reversed_at=receipt.reversed_at,
        reversal_reason=receipt.reversal_reason,
        unapplied_amount=service.receipt_unapplied(session, receipt=receipt),
        counts_as_cash=receipt.status == _CONFIRMED,
        allocations=(
            [
                AllocationRead.model_validate(row)
                for row in service.allocations_of_receipt(session, receipt_id=receipt.id)
            ]
            if with_allocations
            else []
        ),
    )


def _sale_summary(
    session: Session, project: Project, sale_id: uuid.UUID, actor: ActiveActor, as_of: date | None
) -> CollectionSaleSummary:
    summary = service.sale_summary(
        session, project=project, sale_id=sale_id, actor=actor, as_of=as_of
    )
    return _summary_read(summary, blockers=service.clearance_blockers_of(summary))


# --------------------------------------------------------------------------- #
# Project reads
# --------------------------------------------------------------------------- #


@router.get(
    "/summary",
    response_model=CollectionProjectSummary,
    summary="Project collections figures, as at a date",
)
def read_project_summary(
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
) -> CollectionProjectSummary:
    totals = service.project_summary(session, project=project, actor=actor, as_of=as_of)
    return CollectionProjectSummary.model_validate(totals, from_attributes=True)


@router.get(
    "/receivables",
    response_model=list[CollectionRegisterRow],
    summary="Every account this caller may see, with its collections position",
)
def read_receivables(
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
) -> list[CollectionRegisterRow]:
    return [
        CollectionRegisterRow(
            sale_id=row.sale_id,
            sale_number=row.sale_number,
            spa_number=row.spa_number,
            unit_id=row.unit_id,
            unit_number=row.unit_number,
            client_display_name=row.client_display_name,
            currency_id=row.currency_id,
            summary=_summary_read(row.summary),
        )
        for row in service.collection_register(session, project=project, actor=actor, as_of=as_of)
    ]


@router.get(
    "/aging",
    response_model=list[AgingRowRead],
    summary="Every live instalment, aged as at a date",
)
def read_aging(
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
    overdue_only: Annotated[bool, Query()] = False,
) -> list[AgingRowRead]:
    return [
        AgingRowRead(
            sale_id=row.sale_id,
            sale_number=row.sale_number,
            unit_number=row.unit_number,
            client_display_name=row.client_display_name,
            currency_id=row.currency_id,
            installment=_installment_row(row.installment),
        )
        for row in service.aging_report(
            session, project=project, actor=actor, as_of=as_of, overdue_only=overdue_only
        )
    ]


# --------------------------------------------------------------------------- #
# One account
# --------------------------------------------------------------------------- #


@router.get(
    "/sales/{sale_id}",
    response_model=CollectionSaleSummary,
    summary="One sale's collections account",
)
def read_sale_summary(
    sale_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
) -> CollectionSaleSummary:
    return _sale_summary(session, project, sale_id, actor, as_of)


@router.get(
    "/sales/{sale_id}/receipts",
    response_model=list[ReceiptRead],
    summary="Every receipt recorded against this sale",
)
def read_receipts(
    sale_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> list[ReceiptRead]:
    return [
        _receipt_read(session, receipt)
        for receipt in service.receipts_of_sale(
            session, project=project, sale_id=sale_id, actor=actor
        )
    ]


@router.get(
    "/sales/{sale_id}/actions",
    response_model=list[CollectionActionRead],
    summary="The chase history for this sale",
)
def read_actions(
    sale_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> list[CollectionActionRead]:
    return [
        CollectionActionRead.model_validate(row)
        for row in service.actions_of_sale(session, project=project, sale_id=sale_id, actor=actor)
    ]


@router.get(
    "/sales/{sale_id}/disputes",
    response_model=list[DisputeRead],
    summary="Every dispute raised on this sale",
)
def read_disputes(
    sale_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> list[DisputeRead]:
    return [
        DisputeRead.model_validate(row)
        for row in service.disputes_of_sale(session, project=project, sale_id=sale_id, actor=actor)
    ]


@router.get(
    "/sales/{sale_id}/waivers",
    response_model=list[WaiverRead],
    summary="Every waiver asked for on this sale",
)
def read_waivers(
    sale_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> list[WaiverRead]:
    return [
        WaiverRead.model_validate(row)
        for row in service.waivers_of_sale(session, project=project, sale_id=sale_id, actor=actor)
    ]


@router.get(
    "/sales/{sale_id}/restructures",
    response_model=list[RestructureRead],
    summary="Every restructure raised on this sale",
)
def read_restructures(
    sale_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> list[RestructureRead]:
    return [
        RestructureRead.model_validate(row)
        for row in service.restructures_of_sale(
            session, project=project, sale_id=sale_id, actor=actor
        )
    ]


@router.get(
    "/sales/{sale_id}/refunds",
    response_model=list[RefundRead],
    summary="Every refund recorded against this sale",
)
def read_refunds(
    sale_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> list[RefundRead]:
    return [
        RefundRead.model_validate(row)
        for row in service.refunds_of_sale(session, project=project, sale_id=sale_id, actor=actor)
    ]


@router.get(
    "/sales/{sale_id}/collection-clearance",
    response_model=ClearanceRead,
    summary="Whether this account can be signed off, and what stands in the way",
)
def read_clearance(
    sale_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> ClearanceRead:
    summary = service.sale_summary(session, project=project, sale_id=sale_id, actor=actor)
    return ClearanceRead(
        sale_id=sale_id,
        status=summary.collection_clearance_status,
        blockers=service.clearance_blockers_of(summary),
    )


# --------------------------------------------------------------------------- #
# Receipts
# --------------------------------------------------------------------------- #


@router.post(
    "/sales/{sale_id}/receipts",
    response_model=ReceiptRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a claim that money arrived",
)
def create_receipt(
    sale_id: uuid.UUID,
    payload: ReceiptCreate,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> ReceiptRead:
    receipt = service.record_receipt(
        session,
        project=project,
        actor=actor,
        sale_id=sale_id,
        amount=payload.amount,
        receipt_date=payload.receipt_date,
        currency_id=payload.currency_id,
        bank_reference=payload.bank_reference,
        external_reference=payload.external_reference,
        notes=payload.notes,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(receipt)
    return _receipt_read(session, receipt)


@router.get(
    "/receipts/{receipt_id}",
    response_model=ReceiptRead,
    summary="One receipt, with its allocations",
)
def read_receipt(
    receipt_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> ReceiptRead:
    service.permissions.require_collection_reader(actor)
    receipt, _ = service.visible_receipt(
        session, project=project, receipt_id=receipt_id, actor=actor
    )
    return _receipt_read(session, receipt)


@router.get(
    "/receipts/{receipt_id}/suggested-allocations",
    response_model=list[SuggestedAllocationRead],
    summary="Where this receipt's unapplied cash would go, oldest first",
)
def read_suggestions(
    receipt_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> list[SuggestedAllocationRead]:
    return [
        SuggestedAllocationRead.model_validate(row, from_attributes=True)
        for row in service.suggest_allocation(
            session, project=project, actor=actor, receipt_id=receipt_id
        )
    ]


@router.post(
    "/receipts/{receipt_id}/confirm",
    response_model=ReceiptRead,
    summary="Finance accepts that the money arrived",
)
def confirm_receipt(
    receipt_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> ReceiptRead:
    receipt = service.confirm_receipt(
        session,
        project=project,
        actor=actor,
        receipt_id=receipt_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(receipt)
    return _receipt_read(session, receipt)


@router.post(
    "/receipts/{receipt_id}/reverse",
    response_model=ReceiptRead,
    summary="Undo a confirmation, and every allocation that depended on it",
)
def reverse_receipt(
    receipt_id: uuid.UUID,
    payload: ReversalRequest,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> ReceiptRead:
    receipt = service.reverse_receipt(
        session,
        project=project,
        actor=actor,
        receipt_id=receipt_id,
        reason=payload.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(receipt)
    return _receipt_read(session, receipt)


# --------------------------------------------------------------------------- #
# Allocations
# --------------------------------------------------------------------------- #


@router.post(
    "/receipts/{receipt_id}/allocations",
    response_model=AllocationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Apply part of a receipt to one instalment",
)
def create_allocation(
    receipt_id: uuid.UUID,
    payload: AllocationCreate,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> AllocationRead:
    allocation = service.create_allocation(
        session,
        project=project,
        actor=actor,
        receipt_id=receipt_id,
        installment_id=payload.installment_id,
        amount=payload.amount,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(allocation)
    return AllocationRead.model_validate(allocation)


@router.post(
    "/allocations/{allocation_id}/reverse",
    response_model=AllocationRead,
    summary="Take cash back off an instalment; the receipt stays confirmed",
)
def reverse_allocation(
    allocation_id: uuid.UUID,
    payload: ReversalRequest,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> AllocationRead:
    allocation = service.reverse_allocation(
        session,
        project=project,
        actor=actor,
        allocation_id=allocation_id,
        reason=payload.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(allocation)
    return AllocationRead.model_validate(allocation)


# --------------------------------------------------------------------------- #
# Collection actions
# --------------------------------------------------------------------------- #


@router.post(
    "/sales/{sale_id}/actions",
    response_model=CollectionActionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Append what Collections did",
)
def create_action(
    sale_id: uuid.UUID,
    payload: CollectionActionCreate,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> CollectionActionRead:
    action = service.record_action(
        session,
        project=project,
        actor=actor,
        sale_id=sale_id,
        installment_id=payload.installment_id,
        action_type=payload.action_type,
        action_at=payload.action_at,
        notes=payload.notes,
        promised_amount=payload.promised_amount,
        promised_date=payload.promised_date,
        next_action_date=payload.next_action_date,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(action)
    return CollectionActionRead.model_validate(action)


# --------------------------------------------------------------------------- #
# Disputes
# --------------------------------------------------------------------------- #


@router.post(
    "/installments/{installment_id}/disputes",
    response_model=DisputeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Contest an instalment; it stays due and stays counted",
)
def open_dispute(
    installment_id: uuid.UUID,
    payload: DisputeCreate,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> DisputeRead:
    dispute = service.open_dispute(
        session,
        project=project,
        actor=actor,
        installment_id=installment_id,
        reason=payload.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(dispute)
    return DisputeRead.model_validate(dispute)


@router.post(
    "/disputes/{dispute_id}/resolve",
    response_model=DisputeRead,
    summary="Close a dispute with an outcome",
)
def resolve_dispute(
    dispute_id: uuid.UUID,
    payload: DisputeClose,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> DisputeRead:
    dispute = service.resolve_dispute(
        session,
        project=project,
        actor=actor,
        dispute_id=dispute_id,
        resolution=payload.resolution,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(dispute)
    return DisputeRead.model_validate(dispute)


@router.post(
    "/disputes/{dispute_id}/withdraw",
    response_model=DisputeRead,
    summary="Close a dispute that should not have been raised",
)
def withdraw_dispute(
    dispute_id: uuid.UUID,
    payload: DisputeClose,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> DisputeRead:
    dispute = service.withdraw_dispute(
        session,
        project=project,
        actor=actor,
        dispute_id=dispute_id,
        resolution=payload.resolution,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(dispute)
    return DisputeRead.model_validate(dispute)


# --------------------------------------------------------------------------- #
# Waivers
# --------------------------------------------------------------------------- #


@router.post(
    "/installments/{installment_id}/waivers",
    response_model=WaiverRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ask for an operational pause on chasing one instalment",
)
def submit_waiver(
    installment_id: uuid.UUID,
    payload: WaiverCreate,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> WaiverRead:
    waiver = service.submit_waiver(
        session,
        project=project,
        actor=actor,
        installment_id=installment_id,
        waiver_type=payload.waiver_type,
        waived_until=payload.waived_until,
        reason=payload.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(waiver)
    return WaiverRead.model_validate(waiver)


@router.post(
    "/waivers/{waiver_id}/approve",
    response_model=WaiverRead,
    summary="Sanction an operational hold; nothing about the debt changes",
)
def approve_waiver(
    waiver_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> WaiverRead:
    waiver = service.approve_waiver(
        session,
        project=project,
        actor=actor,
        waiver_id=waiver_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(waiver)
    return WaiverRead.model_validate(waiver)


@router.post(
    "/waivers/{waiver_id}/reject",
    response_model=WaiverRead,
    summary="Refuse a hold; the refused row stays readable",
)
def reject_waiver(
    waiver_id: uuid.UUID,
    payload: WaiverDecision,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> WaiverRead:
    waiver = service.reject_waiver(
        session,
        project=project,
        actor=actor,
        waiver_id=waiver_id,
        reason=payload.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(waiver)
    return WaiverRead.model_validate(waiver)


@router.post(
    "/waivers/{waiver_id}/revoke",
    response_model=WaiverRead,
    summary="Withdraw a hold in force and resume collection",
)
def revoke_waiver(
    waiver_id: uuid.UUID,
    payload: WaiverDecision,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> WaiverRead:
    waiver = service.revoke_waiver(
        session,
        project=project,
        actor=actor,
        waiver_id=waiver_id,
        reason=payload.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(waiver)
    return WaiverRead.model_validate(waiver)


# --------------------------------------------------------------------------- #
# Restructures
# --------------------------------------------------------------------------- #


@router.post(
    "/sales/{sale_id}/restructures",
    response_model=RestructureRead,
    status_code=status.HTTP_201_CREATED,
    summary="Raise a restructure and open the revision it will carry cash onto",
)
def create_restructure(
    sale_id: uuid.UUID,
    payload: RestructureCreate,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> RestructureRead:
    restructure, _ = service.create_restructure(
        session,
        project=project,
        actor=actor,
        sale_id=sale_id,
        reason=payload.reason,
        effective_date=payload.effective_date,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(restructure)
    return RestructureRead.model_validate(restructure)


@router.get(
    "/restructures/{restructure_id}/preview",
    response_model=RestructureApplyPreview,
    summary="Exactly where the cash would land, and what still blocks applying",
)
def preview_restructure(
    restructure_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> RestructureApplyPreview:
    preview = service.preview_restructure(
        session, project=project, actor=actor, restructure_id=restructure_id
    )
    return RestructureApplyPreview(
        restructure_id=preview.restructure_id,
        source_version_id=preview.source_version_id,
        replacement_version_id=preview.replacement_version_id,
        replacement_status=preview.replacement_status,
        ready_to_apply=preview.ready_to_apply,
        blockers=preview.blockers,
        carried_total=preview.carried_total,
        unapplied_total=preview.unapplied_total,
        confirmed_receipts_total=preview.confirmed_receipts_total,
        superseding=preview.superseding,
        lines=[
            CarryLineRead(
                receipt_id=line.receipt_id,
                installment_id=line.installment_id,
                amount=line.amount,
            )
            for line in preview.lines
        ],
    )


@router.post(
    "/restructures/{restructure_id}/apply",
    response_model=RestructureApplyResponse,
    summary="Carry the cash forward and activate the replacement, atomically",
)
def apply_restructure(
    restructure_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> RestructureApplyResponse:
    restructure = service.apply_restructure(
        session,
        project=project,
        actor=actor,
        restructure_id=restructure_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(restructure)
    return RestructureApplyResponse(
        restructure=RestructureRead.model_validate(restructure),
        summary=_sale_summary(session, project, restructure.sale_contract_id, actor, None),
    )


@router.post(
    "/restructures/{restructure_id}/abandon",
    response_model=RestructureRead,
    summary="Close a restructure that is not going to happen",
)
def abandon_restructure(
    restructure_id: uuid.UUID,
    payload: ReversalRequest,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> RestructureRead:
    restructure = service.abandon_restructure(
        session,
        project=project,
        actor=actor,
        restructure_id=restructure_id,
        reason=payload.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(restructure)
    return RestructureRead.model_validate(restructure)


# --------------------------------------------------------------------------- #
# Refunds
# --------------------------------------------------------------------------- #


@router.post(
    "/sales/{sale_id}/refunds",
    response_model=RefundRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a repayment being made against a cancellation",
)
def create_refund(
    sale_id: uuid.UUID,
    payload: RefundCreate,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> RefundRead:
    refund = service.record_refund(
        session,
        project=project,
        actor=actor,
        sale_id=sale_id,
        cancellation_id=payload.cancellation_id,
        amount=payload.amount,
        refund_date=payload.refund_date,
        currency_id=payload.currency_id,
        bank_reference=payload.bank_reference,
        notes=payload.notes,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(refund)
    return RefundRead.model_validate(refund)


@router.post(
    "/refunds/{refund_id}/confirm",
    response_model=RefundRead,
    summary="Finance confirms that the money actually left",
)
def confirm_refund(
    refund_id: uuid.UUID,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> RefundRead:
    refund = service.confirm_refund(
        session,
        project=project,
        actor=actor,
        refund_id=refund_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(refund)
    return RefundRead.model_validate(refund)


@router.post(
    "/refunds/{refund_id}/reverse",
    response_model=RefundRead,
    summary="Undo a confirmed refund; the row stays with its reason",
)
def reverse_refund(
    refund_id: uuid.UUID,
    payload: ReversalRequest,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> RefundRead:
    refund = service.reverse_refund(
        session,
        project=project,
        actor=actor,
        refund_id=refund_id,
        reason=payload.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(refund)
    return RefundRead.model_validate(refund)


# --------------------------------------------------------------------------- #
# Clearance
# --------------------------------------------------------------------------- #


@router.post(
    "/sales/{sale_id}/collection-clearance",
    response_model=ClearanceRead,
    summary="Sign off that this account is financially clear",
)
def grant_clearance(
    sale_id: uuid.UUID,
    payload: ClearanceRequest,
    project: CollectionProject,
    session: DbSession,
    actor: ActiveActor,
) -> ClearanceRead:
    granted = service.grant_collection_clearance(
        session,
        project=project,
        actor=actor,
        sale_id=sale_id,
        evidence_reference=payload.evidence_reference,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    return ClearanceRead(sale_id=sale_id, status=granted, blockers=[])
