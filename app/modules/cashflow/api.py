"""The cashflow HTTP surface.

Every route hangs off ``CashflowProject``, which resolves the project, checks
the reading list and refuses a phase-scoped caller in one place. Doing those
three separately per route is three chances to forget one, and the one that gets
forgotten is the scope check — which is the only one whose absence is silent.

No DELETE anywhere. A confirmed movement, a restriction, a release and a
governed forecast are all records of decisions; they are reversed, rejected or
superseded, each with a reason, and never removed.

Exports are the same responses the screens read, rendered as CSV by the same
module. A route that re-queried for its export would eventually disagree with
the screen it is exporting.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.cashflow import models, permissions, read, schemas, service
from app.modules.cashflow.permissions import CashflowProject

router = APIRouter(prefix="/projects/{project_id}/cashflow", tags=["cashflow"])


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


@router.get("/summary", response_model=schemas.SummaryOut)
def read_summary(
    project: CashflowProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
) -> schemas.SummaryOut:
    """Where cash stands, when it runs short, and what the project earns."""
    del actor
    return read.summary_out(session, project=project, as_of=service.resolve_as_of(as_of))


@router.get("/monthly", response_model=schemas.MonthlyOut)
def read_monthly(
    project: CashflowProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
    from_month: Annotated[date | None, Query()] = None,
    to_month: Annotated[date | None, Query()] = None,
) -> schemas.MonthlyOut:
    """The cash bridge, month by month, with every month present."""
    del actor
    return read.monthly_out(
        session,
        project=project,
        as_of=service.resolve_as_of(as_of),
        from_month=from_month,
        to_month=to_month,
    )


@router.get("/monthly.csv", response_class=Response)
def export_monthly(
    project: CashflowProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
    from_month: Annotated[date | None, Query()] = None,
    to_month: Annotated[date | None, Query()] = None,
) -> Response:
    """The monthly table as CSV, from the response the screen renders."""
    del actor
    monthly = read.monthly_out(
        session,
        project=project,
        as_of=service.resolve_as_of(as_of),
        from_month=from_month,
        to_month=to_month,
    )
    return Response(
        content=read.monthly_csv(monthly),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="cashflow-monthly-{project.code}.csv"'
        },
    )


@router.get("/drilldown", response_model=schemas.DrilldownOut)
def read_drilldown(
    project: CashflowProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
    period_month: Annotated[date | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    basis: Annotated[str | None, Query()] = None,
    source_type: Annotated[str | None, Query()] = None,
    flow_direction: Annotated[str | None, Query()] = None,
) -> schemas.DrilldownOut:
    """The transactions behind a figure, named by the module that owns each."""
    del actor
    return read.drilldown_out(
        session,
        project=project,
        as_of=service.resolve_as_of(as_of),
        period_month=period_month,
        category=category,
        basis=basis,
        source_type=source_type,
        flow_direction=flow_direction,
    )


@router.get("/drilldown.csv", response_class=Response)
def export_drilldown(
    project: CashflowProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
    period_month: Annotated[date | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    basis: Annotated[str | None, Query()] = None,
    source_type: Annotated[str | None, Query()] = None,
    flow_direction: Annotated[str | None, Query()] = None,
) -> Response:
    """The drill-down as CSV, from the same rows the screen lists."""
    del actor
    drilldown = read.drilldown_out(
        session,
        project=project,
        as_of=service.resolve_as_of(as_of),
        period_month=period_month,
        category=category,
        basis=basis,
        source_type=source_type,
        flow_direction=flow_direction,
    )
    return Response(
        content=read.drilldown_csv(drilldown),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="cashflow-drilldown-{project.code}.csv"'
        },
    )


@router.get("/reconciliation", response_model=schemas.ReconciliationOut)
def read_reconciliation(
    project: CashflowProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
) -> schemas.ReconciliationOut:
    """Every structural check, answered on its own. No health score."""
    del actor
    return read.reconciliation_out(session, project=project, as_of=service.resolve_as_of(as_of))


@router.get("/management", response_model=schemas.ManagementOut)
def read_management(
    project: CashflowProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
) -> schemas.ManagementOut:
    """One management view, each figure named with the module that owns it."""
    return read.management_out(
        session, project=project, actor=actor, as_of=service.resolve_as_of(as_of)
    )


@router.get("/forecast-accuracy", response_model=schemas.ForecastAccuracyOut)
def read_forecast_accuracy(
    project: CashflowProject,
    session: DbSession,
    actor: ActiveActor,
    forecast_version_id: Annotated[uuid.UUID | None, Query()] = None,
    as_of: Annotated[date | None, Query()] = None,
) -> schemas.ForecastAccuracyOut:
    """A prior forecast against what actually happened, by month and group."""
    del actor
    version = (
        service.get_forecast(session, project=project, version_id=forecast_version_id)
        if forecast_version_id is not None
        else service.active_forecast(session, project_id=project.id)
    )
    if version is None:
        raise permissions.forecast_not_found()
    return read.forecast_accuracy_out(
        session,
        project=project,
        version=version,
        as_of=service.resolve_as_of(as_of),
    )


# --------------------------------------------------------------------------- #
# Forecast versions
# --------------------------------------------------------------------------- #


@router.get("/forecasts", response_model=list[schemas.ForecastOut])
def list_forecasts(
    project: CashflowProject, session: DbSession, actor: ActiveActor
) -> list[schemas.ForecastOut]:
    del actor
    return [
        read.forecast_out(session, project=project, version=version)
        for version in service.list_forecasts(session, project=project)
    ]


@router.post("/forecasts", response_model=schemas.ForecastOut, status_code=status.HTTP_201_CREATED)
def create_forecast(
    project: CashflowProject,
    payload: schemas.ForecastCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastOut:
    """Open a forecast, pinning the construction forecast and freezing the schedule."""
    permissions.require_cashflow_preparer(actor)
    version = service.create_forecast(
        session,
        project=project,
        actor=actor,
        as_of_date=payload.as_of_date,
        forecast_start_month=payload.forecast_start_month,
        forecast_end_month=payload.forecast_end_month,
        opening_unrestricted_cash=payload.opening_unrestricted_cash,
        opening_restricted_cash=payload.opening_restricted_cash,
        discount_rate_per_period=payload.discount_rate_per_period,
        change_reason=payload.change_reason,
        construction_forecast_version_id=payload.construction_forecast_version_id,
        source_version_id=payload.source_version_id,
    )
    session.commit()
    return read.forecast_out(session, project=project, version=version)


@router.get("/forecasts/{version_id}", response_model=schemas.ForecastDetailOut)
def read_forecast(
    project: CashflowProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastDetailOut:
    """The forecast file, including whether its sources have moved under it."""
    del actor
    version = service.get_forecast(session, project=project, version_id=version_id)
    return read.forecast_detail(session, project=project, version=version)


@router.put("/forecasts/{version_id}/lines", response_model=schemas.ForecastLineOut)
def set_forecast_line(
    project: CashflowProject,
    version_id: uuid.UUID,
    payload: schemas.ForecastLineWrite,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastLineOut:
    """Write one month's expected movement, replacing the cell rather than adding."""
    permissions.require_cashflow_preparer(actor)
    line = service.set_forecast_line(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        period_month=payload.period_month,
        source_kind=payload.source_kind,
        category=payload.category,
        amount=payload.amount,
        flow_direction=payload.flow_direction,
        phase_id=payload.phase_id,
        construction_cost_code_id=payload.construction_cost_code_id,
        note=payload.note,
    )
    session.commit()
    labels = read._cost_code_labels(session, project_id=project.id)
    return read.line_out(line, labels)


@router.post(
    "/forecasts/{version_id}/refresh-customer-snapshot",
    response_model=schemas.ForecastDetailOut,
)
def refresh_customer_snapshot(
    project: CashflowProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastDetailOut:
    """Re-freeze the buyer schedule. Deliberately an act, never automatic."""
    permissions.require_cashflow_preparer(actor)
    service.refresh_customer_snapshot(session, project=project, actor=actor, version_id=version_id)
    session.commit()
    version = service.get_forecast(session, project=project, version_id=version_id)
    return read.forecast_detail(session, project=project, version=version)


@router.post("/forecasts/{version_id}/submit", response_model=schemas.ForecastOut)
def submit_forecast(
    project: CashflowProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastOut:
    """Put a draft up for approval, having re-proved its sources and its maths."""
    permissions.require_cashflow_preparer(actor)
    version = service.submit_forecast(session, project=project, actor=actor, version_id=version_id)
    session.commit()
    return read.forecast_out(session, project=project, version=version)


@router.post("/forecasts/{version_id}/approve", response_model=schemas.ForecastOut)
def approve_forecast(
    project: CashflowProject,
    version_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastOut:
    """Approve a submitted forecast. Never the person who submitted it."""
    permissions.require_cashflow_approver(actor)
    version = service.approve_forecast(
        session, project=project, actor=actor, version_id=version_id, reason=payload.reason
    )
    session.commit()
    return read.forecast_out(session, project=project, version=version)


@router.post("/forecasts/{version_id}/reject", response_model=schemas.ForecastOut)
def reject_forecast(
    project: CashflowProject,
    version_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastOut:
    """Refuse a submitted forecast, or withdraw an approval, with the reason recorded.

    One endpoint because it is one authority taking one kind of decision: this
    version will not proceed. Withdrawing is the governed way out of an approved
    forecast that can no longer be activated — its sources moved while it waited
    — and without it the project's one open slot would stay occupied by a version
    nobody can activate, edit or replace.
    """
    permissions.require_cashflow_approver(actor)
    version = service.reject_forecast(
        session, project=project, actor=actor, version_id=version_id, reason=payload.reason
    )
    session.commit()
    return read.forecast_out(session, project=project, version=version)


@router.post("/forecasts/{version_id}/discard", response_model=schemas.ForecastOut)
def discard_forecast(
    project: CashflowProject,
    version_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastOut:
    """Close a draft its preparer no longer wants, with the reason recorded.

    The preparer's own act, not the approver's: a draft has not been put to
    anybody, and it frees the project's one open forecast slot so a replacement
    can be prepared against the sources now in force.
    """
    permissions.require_cashflow_preparer(actor)
    version = service.discard_forecast(
        session, project=project, actor=actor, version_id=version_id, reason=payload.reason
    )
    session.commit()
    return read.forecast_out(session, project=project, version=version)


@router.post("/forecasts/{version_id}/activate", response_model=schemas.ForecastOut)
def activate_forecast(
    project: CashflowProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastOut:
    """Put an approved forecast in force, re-proving its sources one last time."""
    permissions.require_cashflow_activator(actor)
    version = service.activate_forecast(
        session, project=project, actor=actor, version_id=version_id
    )
    session.commit()
    return read.forecast_out(session, project=project, version=version)


# --------------------------------------------------------------------------- #
# Development movements
# --------------------------------------------------------------------------- #


@router.get("/development-movements", response_model=list[schemas.DevelopmentMovementOut])
def list_development_movements(
    project: CashflowProject, session: DbSession, actor: ActiveActor
) -> list[schemas.DevelopmentMovementOut]:
    del actor
    return [
        read.development_movement_out(session, movement=movement)
        for movement in service.list_development_movements(session, project=project)
    ]


@router.post(
    "/development-movements",
    response_model=schemas.DevelopmentMovementOut,
    status_code=status.HTTP_201_CREATED,
)
def record_development_movement(
    project: CashflowProject,
    payload: schemas.DevelopmentMovementCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.DevelopmentMovementOut:
    """Record project cash nothing else in the platform holds. Not yet paid."""
    permissions.require_cashflow_recorder(actor)
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
    return read.development_movement_out(session, movement=movement)


@router.post(
    "/development-movements/{movement_id}/confirm",
    response_model=schemas.DevelopmentMovementOut,
)
def confirm_development_movement(
    project: CashflowProject,
    movement_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.DevelopmentMovementOut:
    """The moment it becomes cash, and never by the person who recorded it."""
    permissions.require_cashflow_confirmer(actor)
    movement = service.confirm_development_movement(
        session, project=project, actor=actor, movement_id=movement_id
    )
    session.commit()
    return read.development_movement_out(session, movement=movement)


@router.post(
    "/development-movements/{movement_id}/reverse",
    response_model=schemas.DevelopmentMovementOut,
)
def reverse_development_movement(
    project: CashflowProject,
    movement_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.DevelopmentMovementOut:
    """Withdraw it from the current position. Historical forecasts keep it."""
    permissions.require_cashflow_confirmer(actor)
    movement = service.reverse_development_movement(
        session,
        project=project,
        actor=actor,
        movement_id=movement_id,
        reason=payload.reason,
    )
    session.commit()
    return read.development_movement_out(session, movement=movement)


# --------------------------------------------------------------------------- #
# Financing movements
# --------------------------------------------------------------------------- #


@router.get("/financing-movements", response_model=list[schemas.FinancingMovementOut])
def list_financing_movements(
    project: CashflowProject, session: DbSession, actor: ActiveActor
) -> list[schemas.FinancingMovementOut]:
    del actor
    return [
        read.financing_movement_out(session, movement=movement)
        for movement in service.list_financing_movements(session, project=project)
    ]


@router.post(
    "/financing-movements",
    response_model=schemas.FinancingMovementOut,
    status_code=status.HTTP_201_CREATED,
)
def record_financing_movement(
    project: CashflowProject,
    payload: schemas.FinancingMovementCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.FinancingMovementOut:
    """Record equity or debt cash. Only where cash genuinely moves."""
    permissions.require_cashflow_recorder(actor)
    movement = service.record_financing_movement(
        session,
        project=project,
        actor=actor,
        movement_type=payload.movement_type,
        amount=payload.amount,
        movement_date=payload.movement_date,
        currency_id=payload.currency_id,
        value_date=payload.value_date,
        counterparty_reference=payload.counterparty_reference,
        facility_reference=payload.facility_reference,
        bank_reference=payload.bank_reference,
        evidence_reference=payload.evidence_reference,
        notes=payload.notes,
    )
    session.commit()
    return read.financing_movement_out(session, movement=movement)


@router.post(
    "/financing-movements/{movement_id}/confirm",
    response_model=schemas.FinancingMovementOut,
)
def confirm_financing_movement(
    project: CashflowProject,
    movement_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.FinancingMovementOut:
    permissions.require_cashflow_confirmer(actor)
    movement = service.confirm_financing_movement(
        session, project=project, actor=actor, movement_id=movement_id
    )
    session.commit()
    return read.financing_movement_out(session, movement=movement)


@router.post(
    "/financing-movements/{movement_id}/reverse",
    response_model=schemas.FinancingMovementOut,
)
def reverse_financing_movement(
    project: CashflowProject,
    movement_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.FinancingMovementOut:
    permissions.require_cashflow_confirmer(actor)
    movement = service.reverse_financing_movement(
        session,
        project=project,
        actor=actor,
        movement_id=movement_id,
        reason=payload.reason,
    )
    session.commit()
    return read.financing_movement_out(session, movement=movement)


# --------------------------------------------------------------------------- #
# Restricted cash
# --------------------------------------------------------------------------- #


@router.get("/restrictions", response_model=list[schemas.RestrictionOut])
def list_restrictions(
    project: CashflowProject, session: DbSession, actor: ActiveActor
) -> list[schemas.RestrictionOut]:
    del actor
    return [
        read.restriction_out(session, restriction=restriction)
        for restriction in service.list_restrictions(session, project=project)
    ]


@router.post(
    "/receipts/{receipt_id}/restriction",
    response_model=schemas.RestrictionOut,
    status_code=status.HTTP_201_CREATED,
)
def record_restriction(
    project: CashflowProject,
    receipt_id: uuid.UUID,
    payload: schemas.RestrictionCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.RestrictionOut:
    """Hold back part of a confirmed receipt. Total cash does not move."""
    permissions.require_cashflow_recorder(actor)
    restriction = service.record_restriction(
        session,
        project=project,
        actor=actor,
        receipt_id=receipt_id,
        restricted_amount=payload.restricted_amount,
        reason=payload.reason,
        source_reference=payload.source_reference,
        notes=payload.notes,
    )
    session.commit()
    return read.restriction_out(session, restriction=restriction)


@router.post("/restrictions/{restriction_id}/confirm", response_model=schemas.RestrictionOut)
def confirm_restriction(
    project: CashflowProject,
    restriction_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.RestrictionOut:
    permissions.require_cashflow_confirmer(actor)
    restriction = service.confirm_restriction(
        session, project=project, actor=actor, restriction_id=restriction_id
    )
    session.commit()
    return read.restriction_out(session, restriction=restriction)


@router.post("/restrictions/{restriction_id}/reverse", response_model=schemas.RestrictionOut)
def reverse_restriction(
    project: CashflowProject,
    restriction_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.RestrictionOut:
    """Refused while releases still stand against it."""
    permissions.require_cashflow_confirmer(actor)
    restriction = service.reverse_restriction(
        session,
        project=project,
        actor=actor,
        restriction_id=restriction_id,
        reason=payload.reason,
    )
    session.commit()
    return read.restriction_out(session, restriction=restriction)


@router.post(
    "/restrictions/{restriction_id}/releases",
    response_model=schemas.RestrictionOut,
    status_code=status.HTTP_201_CREATED,
)
def record_release(
    project: CashflowProject,
    restriction_id: uuid.UUID,
    payload: schemas.ReleaseCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.RestrictionOut:
    """Free part of an escrow. Availability moves; the bank balance does not."""
    permissions.require_cashflow_recorder(actor)
    service.record_release(
        session,
        project=project,
        actor=actor,
        restriction_id=restriction_id,
        release_date=payload.release_date,
        amount=payload.amount,
        certification_reference=payload.certification_reference,
        evidence_reference=payload.evidence_reference,
        notes=payload.notes,
    )
    session.commit()
    restriction = service._lock_row(
        session,
        model=service.CashflowReceiptRestriction,
        project_id=project.id,
        row_id=restriction_id,
        missing=permissions.restriction_not_found,
    )
    return read.restriction_out(session, restriction=restriction)


def _release_backing(session: DbSession, release: models.CashflowRestrictionRelease) -> bool:
    """Whether the escrow this release frees is still holding project cash.

    A release answers for itself and for the chain above it, so the record and
    the cash report cannot say different things about the same money.
    """
    restriction = session.get(models.CashflowReceiptRestriction, release.restriction_id)
    if restriction is None:
        return False
    return read.restriction_stands(session, restriction=restriction)


@router.post("/releases/{release_id}/confirm", response_model=schemas.ReleaseOut)
def confirm_release(
    project: CashflowProject,
    release_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ReleaseOut:
    """Re-proves the ceiling under lock: another release may have landed first."""
    permissions.require_cashflow_confirmer(actor)
    release = service.confirm_release(session, project=project, actor=actor, release_id=release_id)
    session.commit()
    return read.release_out(release, restriction_counts=_release_backing(session, release))


@router.post("/releases/{release_id}/reverse", response_model=schemas.ReleaseOut)
def reverse_release(
    project: CashflowProject,
    release_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ReleaseOut:
    permissions.require_cashflow_confirmer(actor)
    release = service.reverse_release(
        session,
        project=project,
        actor=actor,
        release_id=release_id,
        reason=payload.reason,
    )
    session.commit()
    return read.release_out(release, restriction_counts=_release_backing(session, release))
