"""Stage payment attribution and optional immutable PDF evidence.

Cashflow owns all amounts and cash transitions; Design owns only the attribution.
"""

import hashlib
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.cashflow import permissions, read
from app.modules.cashflow import schemas as cash_schemas
from app.modules.cashflow import service as cash
from app.modules.cashflow.models import CashflowDevelopmentMovement
from app.modules.consultant_engineering import models, schemas
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.settings.models import Currency

MAX_PROOF_BYTES = 10 * 1024 * 1024
ZERO = Decimal("0.00")


def stage(session: Session, project: Project, stage_id: uuid.UUID) -> models.ConsultantDesignStage:
    row = session.scalar(
        select(models.ConsultantDesignStage)
        .where(
            models.ConsultantDesignStage.id == stage_id,
            models.ConsultantDesignStage.project_id == project.id,
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Design stage not found.")
    return row


def payment(
    session: Session, project: Project, payment_id: uuid.UUID
) -> models.ConsultantStagePayment:
    row = session.scalar(
        select(models.ConsultantStagePayment).where(
            models.ConsultantStagePayment.id == payment_id,
            models.ConsultantStagePayment.project_id == project.id,
        )
    )
    if row is None:
        raise NotFoundError("Stage payment not found.")
    return row


def _completed(row: models.ConsultantDesignStage) -> None:
    if row.status != "completed" or row.actual_completion_date is None:
        raise ConflictError(
            "Complete the design stage and record its completion date before payment."
        )


def guard_stage_change(
    session: Session,
    project: Project,
    row: models.ConsultantDesignStage,
    payload: schemas.StageUpdate,
) -> None:
    if (
        payload.status == "completed"
        and payload.actual_completion_date == row.actual_completion_date
    ):
        return
    standing = session.scalar(
        select(models.ConsultantStagePayment.id)
        .join(
            CashflowDevelopmentMovement,
            CashflowDevelopmentMovement.id == models.ConsultantStagePayment.movement_id,
        )
        .where(
            models.ConsultantStagePayment.project_id == project.id,
            models.ConsultantStagePayment.stage_id == row.id,
            CashflowDevelopmentMovement.status.in_(("recorded", "confirmed")),
        )
        .limit(1)
    )
    if standing is not None:
        raise ConflictError("Remove or reverse standing stage payments before changing completion.")


def create_payment(
    session: Session,
    project: Project,
    actor: ActorContext,
    stage_id: uuid.UUID,
    payload: schemas.StagePaymentCreate,
) -> models.ConsultantStagePayment:
    permissions.require_prelaunch_recorder(actor)
    lock_project(session, project.id)
    fingerprint = hashlib.sha256(
        payload.model_dump_json(exclude={"request_id", "expected_stage_updated_at"}).encode()
    ).hexdigest()
    existing = session.scalar(
        select(models.ConsultantStagePayment).where(
            models.ConsultantStagePayment.project_id == project.id,
            models.ConsultantStagePayment.request_id == payload.request_id,
        )
    )
    if existing is not None:
        if existing.stage_id != stage_id or existing.request_fingerprint != fingerprint:
            raise ConflictError("This payment request was already saved with different details.")
        return existing
    target = stage(session, project, stage_id)
    _completed(target)
    if target.updated_at != payload.expected_stage_updated_at:
        raise ConflictError("The stage changed. Reload its programme before recording payment.")
    agreement = session.scalar(
        select(models.ConsultantEngagement).where(
            models.ConsultantEngagement.id == target.engagement_id,
            models.ConsultantEngagement.project_id == project.id,
        )
    )
    if agreement.status == "draft":
        raise ConflictError("Activate the consultant agreement before recording a payment.")
    if payload.movement_date < target.actual_completion_date:
        raise ValidationError("Stage payment date cannot precede stage completion.")
    movement = cash.record_development_movement(
        session,
        project=project,
        actor=actor,
        counterparty_reference=agreement.consultant_name,
        **payload.model_dump(
            exclude={"request_id", "expected_stage_updated_at", "counterparty_reference"}
        ),
    )
    row = models.ConsultantStagePayment(
        project_id=project.id,
        stage_id=target.id,
        movement_id=movement.id,
        request_id=payload.request_id,
        request_fingerprint=fingerprint,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="design.stage_payment_recorded",
        entity_type="consultant_stage_payment",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        after={"stage_id": target.id, "movement_id": movement.id, "project_id": project.id},
    )
    return row


def payment_out(
    session: Session, project: Project, actor: ActorContext, row: models.ConsultantStagePayment
) -> schemas.StagePaymentOut:
    movement = session.scalar(
        select(CashflowDevelopmentMovement).where(
            CashflowDevelopmentMovement.id == row.movement_id,
            CashflowDevelopmentMovement.project_id == project.id,
        )
    )
    proofs = session.scalars(
        select(models.ConsultantPaymentProof)
        .where(
            models.ConsultantPaymentProof.payment_id == row.id,
            models.ConsultantPaymentProof.project_id == project.id,
            models.ConsultantPaymentProof.is_deleted.is_(False),
        )
        .order_by(models.ConsultantPaymentProof.created_at, models.ConsultantPaymentProof.id)
    ).all()
    return schemas.StagePaymentOut(
        id=row.id,
        stage_id=row.stage_id,
        expense=read.prelaunch_expense_out(session, movement=movement, actor=actor),
        proofs=[schemas.PaymentProofOut.model_validate(proof) for proof in proofs],
    )


def workspace(
    session: Session, project: Project, actor: ActorContext
) -> schemas.PaymentsWorkspaceOut:
    permissions.require_cashflow_reader(actor)
    rows = session.scalars(
        select(models.ConsultantStagePayment)
        .where(
            models.ConsultantStagePayment.project_id == project.id,
        )
        .order_by(models.ConsultantStagePayment.created_at.desc(), models.ConsultantStagePayment.id)
    ).all()
    outputs = [payment_out(session, project, actor, row) for row in rows]
    positions = []
    for target in session.scalars(
        select(models.ConsultantDesignStage).where(
            models.ConsultantDesignStage.project_id == project.id
        )
    ):
        expenses = [row.expense for row in outputs if row.stage_id == target.id]
        paid = sum((row.amount for row in expenses if row.status == "confirmed"), ZERO)
        positions.append(
            schemas.StagePaymentPosition(
                stage_id=target.id,
                agreed_payment_amount=target.agreed_payment_amount,
                recorded_amount=sum(
                    (row.amount for row in expenses if row.status == "recorded"), ZERO
                ),
                confirmed_paid_amount=paid,
                remaining_amount=target.agreed_payment_amount - paid
                if target.agreed_payment_amount is not None
                else None,
            )
        )
    currency = session.get(Currency, project.base_currency_id)
    return schemas.PaymentsWorkspaceOut(
        currency_id=project.base_currency_id,
        currency_code=currency.code if currency else None,
        payments=outputs,
        stages=positions,
    )


def change_payment(
    session: Session,
    project: Project,
    actor: ActorContext,
    payment_id: uuid.UUID,
    body: cash_schemas.PreLaunchExpenseUpdate,
) -> models.ConsultantStagePayment:
    lock_project(session, project.id)
    row = payment(session, project, payment_id)
    target = stage(session, project, row.stage_id)
    _completed(target)
    if body.changes.category != "consultants":
        raise ValidationError("A design payment must keep the Consultants category.")
    if body.changes.movement_date < target.actual_completion_date:
        raise ValidationError("Stage payment date cannot precede stage completion.")
    cash.correct_prelaunch_expense(
        session,
        project=project,
        actor=actor,
        movement_id=row.movement_id,
        expected=body.expected,
        changes=body.changes,
    )
    return row


def confirm_payment(
    session: Session,
    project: Project,
    actor: ActorContext,
    payment_id: uuid.UUID,
    body: cash_schemas.PreLaunchExpenseConfirm,
) -> models.ConsultantStagePayment:
    permissions.require_cashflow_confirmer(actor)
    lock_project(session, project.id)
    row = payment(session, project, payment_id)
    _completed(stage(session, project, row.stage_id))
    cash.confirm_development_movement(
        session, project=project, actor=actor, movement_id=row.movement_id, expected=body.expected
    )
    return row


def remove_payment(
    session: Session,
    project: Project,
    actor: ActorContext,
    payment_id: uuid.UUID,
    body: cash_schemas.PreLaunchExpenseRemove,
) -> models.ConsultantStagePayment:
    lock_project(session, project.id)
    row = payment(session, project, payment_id)
    cash.correct_prelaunch_expense(
        session,
        project=project,
        actor=actor,
        movement_id=row.movement_id,
        expected=body.expected,
        removal_reason=body.reason,
    )
    return row


def reverse_payment(
    session: Session, project: Project, actor: ActorContext, payment_id: uuid.UUID, reason: str
) -> models.ConsultantStagePayment:
    permissions.require_cashflow_confirmer(actor)
    lock_project(session, project.id)
    row = payment(session, project, payment_id)
    cash.reverse_development_movement(
        session, project=project, actor=actor, movement_id=row.movement_id, reason=reason
    )
    return row


def authorize_upload(
    session: Session, project: Project, actor: ActorContext, payment_id: uuid.UUID
) -> None:
    try:
        permissions.require_prelaunch_recorder(actor)
        payment(session, project, payment_id)
    finally:
        session.rollback()


def create_proof(
    session: Session,
    project: Project,
    actor: ActorContext,
    payment_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> models.ConsultantPaymentProof:
    permissions.require_prelaunch_recorder(actor)
    lock_project(session, project.id)
    payment(session, project, payment_id)
    filename = filename.strip()
    if (
        not filename
        or len(filename) > 255
        or any(c in filename for c in "/\\")
        or any(ord(c) < 32 or ord(c) == 127 for c in filename)
    ):
        raise ValidationError("Enter a valid PDF filename.")
    if (
        not 0 < len(data) <= MAX_PROOF_BYTES
        or not filename.lower().endswith(".pdf")
        or not data.startswith(b"%PDF-")
    ):
        raise ValidationError("Upload a non-empty PDF up to 10 MB matching its .pdf file type.")
    digest = hashlib.sha256(data).hexdigest()
    existing = session.scalar(
        select(models.ConsultantPaymentProof).where(
            models.ConsultantPaymentProof.project_id == project.id,
            models.ConsultantPaymentProof.payment_id == payment_id,
            models.ConsultantPaymentProof.sha256 == digest,
            models.ConsultantPaymentProof.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing
    row = models.ConsultantPaymentProof(
        project_id=project.id,
        payment_id=payment_id,
        filename=filename,
        document=data,
        sha256=digest,
        created_by_user_id=actor.user_id,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="design.payment_proof_added",
        entity_type="consultant_payment_proof",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        after={
            "payment_id": payment_id,
            "project_id": project.id,
            "filename": filename,
            "sha256": digest,
        },
    )
    return row


def proof(
    session: Session, project: Project, payment_id: uuid.UUID, proof_id: uuid.UUID
) -> models.ConsultantPaymentProof:
    payment(session, project, payment_id)
    row = session.scalar(
        select(models.ConsultantPaymentProof).where(
            models.ConsultantPaymentProof.id == proof_id,
            models.ConsultantPaymentProof.payment_id == payment_id,
            models.ConsultantPaymentProof.project_id == project.id,
            models.ConsultantPaymentProof.is_deleted.is_(False),
        )
    )
    if row is None:
        raise NotFoundError("Payment proof not found.")
    return row


def delete_proof(
    session: Session,
    project: Project,
    actor: ActorContext,
    payment_id: uuid.UUID,
    proof_id: uuid.UUID,
    reason: str,
) -> None:
    permissions.require_prelaunch_recorder(actor)
    lock_project(session, project.id)
    row = proof(session, project, payment_id, proof_id)
    row.is_deleted = True
    record_event(
        session,
        action="design.payment_proof_removed",
        entity_type="consultant_payment_proof",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason,
        before={"filename": row.filename, "sha256": row.sha256, "payment_id": row.payment_id},
        after={"is_deleted": True, "project_id": project.id},
    )
