"""A narrow Development-facing facade over authoritative cashflow movements.

There is intentionally no Pre-Launch model or repository. Every mutation below
delegates to Cashflow's locked, audited Development Movement service, so a
confirmed expense reaches project actual cash exactly once.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, status

from app.core.errors import ValidationError
from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.cashflow import permissions, read, schemas, service
from app.modules.cashflow.permissions import CashflowProject

router = APIRouter(prefix="/projects/{project_id}/pre-launch", tags=["pre-launch"])

# No construction, financing, escrow, commission distribution or handover can
# enter through this contextual surface. ``other`` remains for explicit costs
# whose business wording does not fit a narrow governed category.
PRELAUNCH_CATEGORIES = service.PRELAUNCH_CATEGORIES


def _register(
    session: DbSession, project: CashflowProject, actor: ActiveActor
) -> schemas.PreLaunchRegisterOut:
    movements = [
        movement
        for movement in service.list_development_movements(session, project=project)
        if movement.category in PRELAUNCH_CATEGORIES
    ]
    return schemas.PreLaunchRegisterOut(
        categories=service.prelaunch_category_summary(movements),
        expenses=[
            read.prelaunch_expense_out(session, movement=row, actor=actor) for row in movements
        ],
        recorded_amount=sum(
            (row.amount for row in movements if row.status == "recorded"), start=Decimal("0.00")
        ),
        confirmed_paid_amount=sum(
            (row.amount for row in movements if row.status == "confirmed"),
            start=Decimal("0.00"),
        ),
    )


@router.get("/expenses", response_model=schemas.PreLaunchRegisterOut)
def list_expenses(
    project: CashflowProject, session: DbSession, actor: ActiveActor
) -> schemas.PreLaunchRegisterOut:
    return _register(session, project, actor)


@router.post(
    "/expenses",
    response_model=schemas.PreLaunchExpenseOut,
    status_code=status.HTTP_201_CREATED,
)
def record_expense(
    project: CashflowProject,
    payload: schemas.DevelopmentMovementCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.PreLaunchExpenseOut:
    permissions.require_prelaunch_recorder(actor)
    if payload.category not in PRELAUNCH_CATEGORIES:
        raise ValidationError("That category cannot be recorded through Pre-Launch.")
    movement = service.record_development_movement(
        session,
        project=project,
        actor=actor,
        category=payload.category,
        amount=payload.amount,
        movement_date=payload.movement_date,
        currency_id=payload.currency_id,
        value_date=payload.value_date,
        phase_id=payload.phase_id,
        counterparty_reference=payload.counterparty_reference,
        invoice_reference=payload.invoice_reference,
        bank_reference=payload.bank_reference,
        evidence_reference=payload.evidence_reference,
        notes=payload.notes,
    )
    session.commit()
    return read.prelaunch_expense_out(session, movement=movement, actor=actor)


@router.patch("/expenses/{movement_id}", response_model=schemas.PreLaunchExpenseOut)
def update_expense(
    project: CashflowProject,
    movement_id: uuid.UUID,
    payload: schemas.PreLaunchExpenseUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.PreLaunchExpenseOut:
    movement = service.correct_prelaunch_expense(
        session,
        project=project,
        actor=actor,
        movement_id=movement_id,
        expected=payload.expected,
        changes=payload.changes,
    )
    session.commit()
    return read.prelaunch_expense_out(session, movement=movement, actor=actor)


@router.post("/expenses/{movement_id}/remove", response_model=schemas.PreLaunchExpenseOut)
def remove_expense(
    project: CashflowProject,
    movement_id: uuid.UUID,
    payload: schemas.PreLaunchExpenseRemove,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.PreLaunchExpenseOut:
    movement = service.correct_prelaunch_expense(
        session,
        project=project,
        actor=actor,
        movement_id=movement_id,
        expected=payload.expected,
        removal_reason=payload.reason,
    )
    session.commit()
    return read.prelaunch_expense_out(session, movement=movement, actor=actor)


@router.post("/expenses/{movement_id}/confirm", response_model=schemas.PreLaunchExpenseOut)
def confirm_expense(
    project: CashflowProject,
    movement_id: uuid.UUID,
    payload: schemas.PreLaunchExpenseConfirm,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.PreLaunchExpenseOut:
    permissions.require_cashflow_confirmer(actor)
    movement = service.confirm_development_movement(
        session, project=project, actor=actor, movement_id=movement_id, expected=payload.expected
    )
    if movement.category not in PRELAUNCH_CATEGORIES:
        session.rollback()
        raise ValidationError("That movement is not a Pre-Launch expense.")
    session.commit()
    return read.prelaunch_expense_out(session, movement=movement, actor=actor)


@router.post("/expenses/{movement_id}/reverse", response_model=schemas.PreLaunchExpenseOut)
def reverse_expense(
    project: CashflowProject,
    movement_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.PreLaunchExpenseOut:
    permissions.require_cashflow_confirmer(actor)
    movement = service.reverse_development_movement(
        session, project=project, actor=actor, movement_id=movement_id, reason=payload.reason
    )
    if movement.category not in PRELAUNCH_CATEGORIES:
        session.rollback()
        raise ValidationError("That movement is not a Pre-Launch expense.")
    session.commit()
    return read.prelaunch_expense_out(session, movement=movement, actor=actor)
