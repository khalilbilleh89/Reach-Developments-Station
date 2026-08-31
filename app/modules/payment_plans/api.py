"""Payment plan routes: prepare a schedule, sanction it, and let it fall due.

Handlers validate, authorise and orchestrate. Every rule about what may happen
lives in the service; every rule about who may reach it lives in
``permissions.py``.

Status is never a PATCH. Submitting, approving, refusing and activating a
schedule are four acts with four different rights and four different sets of
preconditions, so each has its own route — a status column a client could set
would be an approval a client could grant itself.

There are no DELETE routes. A draft schedule is replaced atomically while it is
still a draft; once submitted, a schedule is refused, superseded or reversed,
and every one of those keeps the record of what was previously believed.

Triggers are resolved only when somebody asks. There is no scheduler, no
background worker and no GET that quietly writes: money falling due is an event
an operator must be able to point at in an audit trail.

Every nested route passes its ``plan_id`` down to the service rather than
letting the child identifier stand on its own. ``/plan-A/installments/row-B``
is a claim that B belongs to A, and the service refuses the pair — with the
same 404 it gives for a row that does not exist — when it does not.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.errors import NotFoundError
from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.inventory.models import Unit
from app.modules.payment_plans import service
from app.modules.payment_plans.models import (
    InstallmentTriggerEvent,
    PaymentPlanInstallment,
    PaymentPlanVersion,
)
from app.modules.payment_plans.permissions import PlanProject
from app.modules.payment_plans.schedule import Reconciliation, shortfall_reasons
from app.modules.payment_plans.schemas import (
    DecisionRequest,
    ForecastRequest,
    InstallmentRead,
    ManualTriggerRequest,
    OwnerRequest,
    PlanCreateRequest,
    PlanDetailRead,
    PlanRead,
    PlanRegisterRead,
    ReconciliationRead,
    RefreshResultRead,
    RegisterRowRead,
    ReversalRequest,
    ScheduleWriteRequest,
    SeriesPreviewRead,
    SeriesPreviewRequest,
    SeriesRowRead,
    TriggerEventRead,
    VersionCreateRequest,
    VersionDetailRead,
    VersionRead,
)
from app.modules.sales.models import Client, SaleContract

router = APIRouter(prefix="/projects/{project_id}/payment-plans", tags=["payment plans"])


def _installment_read(
    row: PaymentPlanInstallment,
    events: list[InstallmentTriggerEvent] | None = None,
) -> InstallmentRead:
    """Serialise one instalment, with its buyer total derived on the server."""
    return InstallmentRead(
        id=row.id,
        payment_plan_version_id=row.payment_plan_version_id,
        sequence=row.sequence,
        label=row.label,
        trigger_type=row.trigger_type,
        trigger_reference=row.trigger_reference,
        offset_days=row.offset_days,
        recurrence_index=row.recurrence_index,
        contractual_due_date=row.contractual_due_date,
        forecast_due_date=row.forecast_due_date,
        actual_due_date=row.actual_due_date,
        grace_days=row.grace_days,
        principal_amount=row.principal_amount,
        principal_fraction=row.principal_fraction,
        tax_amount=row.tax_amount,
        fee_amount=row.fee_amount,
        total_scheduled_amount=row.principal_amount + row.tax_amount + row.fee_amount,
        trigger_status=row.trigger_status,
        owner_user_id=row.owner_user_id,
        trigger_events=[TriggerEventRead.model_validate(event) for event in events or []],
    )


def _reconciliation_read(reconciliation: Reconciliation) -> ReconciliationRead:
    return ReconciliationRead(
        installment_count=reconciliation.installment_count,
        scheduled_principal_total=reconciliation.scheduled_principal_total,
        contract_value_covered=reconciliation.contract_value_covered,
        principal_delta=reconciliation.principal_delta,
        scheduled_fraction_total=reconciliation.scheduled_fraction_total,
        fraction_delta=reconciliation.fraction_delta,
        scheduled_tax_total=reconciliation.scheduled_tax_total,
        tax_total_snapshot=reconciliation.tax_total_snapshot,
        tax_delta=reconciliation.tax_delta,
        scheduled_fee_total=reconciliation.scheduled_fee_total,
        buyer_fee_total_snapshot=reconciliation.buyer_fee_total_snapshot,
        fee_delta=reconciliation.fee_delta,
        scheduled_buyer_total=reconciliation.scheduled_buyer_total,
        total_buyer_payable_snapshot=reconciliation.total_buyer_payable_snapshot,
        buyer_total_delta=reconciliation.buyer_total_delta,
        is_reconciled=reconciliation.is_reconciled,
        blocking_reasons=shortfall_reasons(reconciliation),
    )


def _version_detail(session: DbSession, version: PaymentPlanVersion) -> VersionDetailRead:
    """One version with its schedule, its attestations and its reconciliation.

    The attestations arrive grouped from a single query rather than a request
    per manual instalment: an approver opens this screen precisely because
    there is something on it to decide, and a schedule should not get slower
    the more of those it has.
    """
    rows = service.installments_of(session, version_id=version.id)
    events = service.trigger_events_by_installment(session, version_id=version.id)
    next_scheduled, next_forecast = service.forward_dates(rows)
    return VersionDetailRead(
        version=VersionRead.model_validate(version),
        installments=[_installment_read(row, events.get(row.id)) for row in rows],
        reconciliation=_reconciliation_read(service.reconcile_rows(version, rows)),
        next_scheduled_date=next_scheduled,
        next_forecast_date=next_forecast,
    )


# --------------------------------------------------------------------------- #
# Register and plans
# --------------------------------------------------------------------------- #


@router.get("", response_model=PlanRegisterRead, summary="The project's payment plans")
def list_plans(project: PlanProject, session: DbSession, actor: ActiveActor) -> PlanRegisterRead:
    rows = service.plan_register(session, project=project, actor=actor)
    return PlanRegisterRead(
        rows=[
            RegisterRowRead(**{name: getattr(row, name) for name in row.__slots__}) for row in rows
        ],
        total=len(rows),
    )


@router.post(
    "",
    response_model=PlanDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open a payment plan for a contract",
)
def create_plan(
    body: PlanCreateRequest,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> PlanDetailRead:
    plan, _version = service.create_plan(
        session,
        project=project,
        actor=actor,
        sale_contract_id=body.sale_contract_id,
        name=body.name,
        reservation_treatment=body.reservation_treatment,
        origin_type=body.origin_type,
        source_version_id=body.source_version_id,
        effective_date=body.effective_date,
        notes=body.notes,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    return _plan_detail(session, project=project, plan_id=plan.id, actor=actor)


@router.post(
    "/series-preview",
    response_model=SeriesPreviewRead,
    summary="Propose the dates of a recurring series",
)
def series_preview(
    body: SeriesPreviewRequest,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> SeriesPreviewRead:
    """Structure only — dates and labels, no money. Writes nothing."""
    service.permissions.require_plan_writer(actor)
    rows = service.series_preview(
        frequency=body.frequency,
        first_due_date=body.first_due_date,
        count=body.count,
        label_prefix=body.label_prefix,
    )
    return SeriesPreviewRead(
        rows=[
            SeriesRowRead(
                recurrence_index=row.recurrence_index, label=row.label, due_date=row.due_date
            )
            for row in rows
        ]
    )


def _plan_detail(
    session: DbSession, *, project: object, plan_id: uuid.UUID, actor: ActiveActor
) -> PlanDetailRead:
    """Everything a plan screen needs, in one response rather than per row."""
    plan = service.get_plan(session, project=project, plan_id=plan_id, actor=actor)  # type: ignore[arg-type]
    sale = session.get(SaleContract, plan.sale_contract_id)
    if sale is None:
        raise NotFoundError("Sale contract not found.")
    unit = session.get(Unit, sale.unit_id)
    client = session.get(Client, sale.client_id)
    # Two questions, two answers. Which version is being prepared, and which
    # one the buyer is actually being held to — these are the same version
    # most of the time and emphatically not the same during a revision, which
    # can run for weeks while the standing schedule keeps falling due.
    current = service.current_version(session, plan_id=plan.id)
    active = service.active_version(session, plan_id=plan.id)
    current_detail = _version_detail(session, current) if current else None
    if active is None:
        active_detail = None
    elif current is not None and active.id == current.id:
        # The ordinary case. Serialised twice, read once: no second pass over
        # the same instalments, attestations or arithmetic.
        active_detail = current_detail
    else:
        active_detail = _version_detail(session, active)
    return PlanDetailRead(
        plan=PlanRead.model_validate(plan),
        sale_id=sale.id,
        sale_number=sale.sale_number,
        spa_number=sale.spa_number,
        sale_status=sale.status,
        unit_id=sale.unit_id,
        unit_reference=unit.unit_reference if unit else "",
        # The buyer's display name only. A payment schedule never needs a
        # passport number, so this module never asks for one.
        client_display_name=client.display_name if client else "",
        currency_id=sale.currency_id,
        current=current_detail,
        active=active_detail,
        active_version_id=active.id if active else None,
        versions=[
            VersionRead.model_validate(version)
            for version in service.versions_of(session, plan_id=plan.id)
        ],
    )


@router.get("/for-sale/{sale_id}", response_model=PlanDetailRead | None, summary="A sale's plan")
def plan_for_sale(
    sale_id: uuid.UUID,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> PlanDetailRead | None:
    """The plan governing one sale, for the deal file and Unit 360.

    Answers ``null`` rather than 404 when a sale has no plan: not yet scheduled
    is an ordinary state, and the screens that ask say so in words.
    """
    plan = service.plan_for_sale(session, project=project, sale_id=sale_id, actor=actor)
    if plan is None:
        return None
    return _plan_detail(session, project=project, plan_id=plan.id, actor=actor)


@router.get("/{plan_id}", response_model=PlanDetailRead, summary="One payment plan")
def read_plan(
    plan_id: uuid.UUID,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> PlanDetailRead:
    return _plan_detail(session, project=project, plan_id=plan_id, actor=actor)


# --------------------------------------------------------------------------- #
# Versions
# --------------------------------------------------------------------------- #


@router.get(
    "/{plan_id}/versions", response_model=list[VersionRead], summary="A plan's version history"
)
def list_versions(
    plan_id: uuid.UUID,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> list[PaymentPlanVersion]:
    plan = service.get_plan(session, project=project, plan_id=plan_id, actor=actor)
    return service.versions_of(session, plan_id=plan.id)


@router.post(
    "/{plan_id}/versions",
    response_model=VersionDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open a revision of a plan",
)
def create_version(
    plan_id: uuid.UUID,
    body: VersionCreateRequest,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> VersionDetailRead:
    version = service.create_version(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        change_reason=body.change_reason,
        reservation_treatment=body.reservation_treatment,
        effective_date=body.effective_date,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_detail(session, version)


@router.get(
    "/{plan_id}/versions/{version_id}",
    response_model=VersionDetailRead,
    summary="One version, its schedule and its reconciliation",
)
def read_version(
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> VersionDetailRead:
    version, _plan = service.get_version(
        session, project=project, plan_id=plan_id, version_id=version_id, actor=actor
    )
    return _version_detail(session, version)


@router.put(
    "/{plan_id}/versions/{version_id}/installments",
    response_model=VersionDetailRead,
    summary="Replace a draft version's whole schedule",
)
def write_schedule(
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    body: ScheduleWriteRequest,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> VersionDetailRead:
    rows = [
        service.InstallmentDraft(
            sequence=row.sequence,
            label=row.label,
            trigger_type=row.trigger_type,
            trigger_reference=row.trigger_reference,
            offset_days=row.offset_days,
            recurrence_index=row.recurrence_index,
            contractual_due_date=row.contractual_due_date,
            forecast_due_date=row.forecast_due_date,
            grace_days=row.grace_days,
            principal_amount=row.principal_amount,
            principal_fraction=row.principal_fraction,
            tax_amount=row.tax_amount,
            fee_amount=row.fee_amount,
            owner_user_id=row.owner_user_id,
        )
        for row in body.installments
    ]
    version = service.replace_schedule(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        version_id=version_id,
        rows=rows,
        allocation_mode=body.allocation_mode,
        charge_allocation_mode=body.charge_allocation_mode,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_detail(session, version)


@router.post(
    "/{plan_id}/versions/{version_id}/submit",
    response_model=VersionDetailRead,
    summary="Put a reconciled schedule forward for sanction",
)
def submit_version(
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> VersionDetailRead:
    version = service.submit_version(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        version_id=version_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_detail(session, version)


@router.post(
    "/{plan_id}/versions/{version_id}/approve",
    response_model=VersionDetailRead,
    summary="Sanction a submitted schedule",
)
def approve_version(
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    body: DecisionRequest,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> VersionDetailRead:
    version = service.approve_version(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        version_id=version_id,
        reason=body.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_detail(session, version)


@router.post(
    "/{plan_id}/versions/{version_id}/reject",
    response_model=VersionDetailRead,
    summary="Refuse a submitted schedule",
)
def reject_version(
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    body: DecisionRequest,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> VersionDetailRead:
    version = service.reject_version(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        version_id=version_id,
        reason=body.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_detail(session, version)


@router.post(
    "/{plan_id}/versions/{version_id}/activate",
    response_model=VersionDetailRead,
    summary="Make an approved schedule the one governing the sale",
)
def activate_version(
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> VersionDetailRead:
    version = service.activate_version(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        version_id=version_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(version)
    return _version_detail(session, version)


# --------------------------------------------------------------------------- #
# Triggers
# --------------------------------------------------------------------------- #


@router.post(
    "/{plan_id}/refresh-triggers",
    response_model=RefreshResultRead,
    summary="Resolve contingent instalments against events that have happened",
)
def refresh_triggers(
    plan_id: uuid.UUID,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> RefreshResultRead:
    """Explicit, never scheduled.

    Resolves handover and title transfer from records that already exist. A
    construction milestone is never resolved here: PR-MVP-09 certifies those,
    and a forecast date is not a certificate.
    """
    triggered, waiting = service.refresh_triggers(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    return RefreshResultRead(
        triggered=[_installment_read(row) for row in triggered],
        still_awaiting=[_installment_read(row) for row in waiting],
    )


@router.patch(
    "/{plan_id}/installments/{installment_id}/forecast",
    response_model=InstallmentRead,
    summary="Move a contingent instalment's expected date",
)
def set_forecast(
    plan_id: uuid.UUID,
    installment_id: uuid.UUID,
    body: ForecastRequest,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> InstallmentRead:
    row = service.set_forecast(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        installment_id=installment_id,
        forecast_due_date=body.forecast_due_date,
        reason=body.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(row)
    return _installment_read(row)


@router.patch(
    "/{plan_id}/installments/{installment_id}/owner",
    response_model=InstallmentRead,
    summary="Assign who chases an instalment",
)
def set_owner(
    plan_id: uuid.UUID,
    installment_id: uuid.UUID,
    body: OwnerRequest,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> InstallmentRead:
    row = service.set_owner(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        installment_id=installment_id,
        owner_user_id=body.owner_user_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(row)
    return _installment_read(row)


@router.get(
    "/{plan_id}/installments/{installment_id}/trigger-events",
    response_model=list[TriggerEventRead],
    summary="Every attestation made about one instalment",
)
def list_trigger_events(
    plan_id: uuid.UUID,
    installment_id: uuid.UUID,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> list[TriggerEventRead]:
    return [
        TriggerEventRead.model_validate(event)
        for event in service.trigger_events_for_installment(
            session,
            project=project,
            plan_id=plan_id,
            installment_id=installment_id,
            actor=actor,
        )
    ]


@router.post(
    "/{plan_id}/installments/{installment_id}/manual-trigger",
    response_model=TriggerEventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Attest that a manually triggered instalment's event occurred",
)
def submit_manual_trigger(
    plan_id: uuid.UUID,
    installment_id: uuid.UUID,
    body: ManualTriggerRequest,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> TriggerEventRead:
    event = service.submit_manual_trigger(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        installment_id=installment_id,
        event_date=body.event_date,
        evidence_reference=body.evidence_reference,
        reason=body.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(event)
    return TriggerEventRead.model_validate(event)


@router.post(
    "/{plan_id}/trigger-events/{event_id}/approve",
    response_model=TriggerEventRead,
    summary="Sanction an attestation and make the instalment due",
)
def approve_manual_trigger(
    plan_id: uuid.UUID,
    event_id: uuid.UUID,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> TriggerEventRead:
    event = service.approve_manual_trigger(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        event_id=event_id,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(event)
    return TriggerEventRead.model_validate(event)


@router.post(
    "/{plan_id}/trigger-events/{event_id}/reverse",
    response_model=TriggerEventRead,
    summary="Withdraw an attestation that should not have been made",
)
def reverse_manual_trigger(
    plan_id: uuid.UUID,
    event_id: uuid.UUID,
    body: ReversalRequest,
    project: PlanProject,
    session: DbSession,
    actor: ActiveActor,
) -> TriggerEventRead:
    event = service.reverse_manual_trigger(
        session,
        project=project,
        actor=actor,
        plan_id=plan_id,
        event_id=event_id,
        reason=body.reason,
        correlation_id=actor.correlation_id,
    )
    session.commit()
    session.refresh(event)
    return TriggerEventRead.model_validate(event)
