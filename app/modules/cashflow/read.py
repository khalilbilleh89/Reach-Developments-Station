"""Every cashflow response, assembled in exactly one place.

The API layer calls these and nothing else. A dozen routes each totalling their
own months is a dozen chances for two screens to disagree about what "usable
cash" means, and the disagreement surfaces as a board pack that does not match
the export somebody attached to it.

The export is the same function. ``monthly_csv`` renders the rows
``monthly_out`` returns rather than re-querying, because a dashboard saying
5,420,000 and a CSV saying 5,419,999 is a failed control however small the
difference — and the only way to be certain they agree is for them to be the
same list.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.standing import CONFIRMED as STANDING_CONFIRMED
from app.modules.access.dependencies import ActorContext
from app.modules.cashflow import calculator, schemas, service
from app.modules.cashflow.calculator import ZERO, money
from app.modules.cashflow.models import (
    MOVEMENT_CONFIRMED,
    CashflowDevelopmentMovement,
    CashflowFinancingMovement,
    CashflowForecastLine,
    CashflowForecastVersion,
    CashflowReceiptRestriction,
    CashflowRestrictionRelease,
)
from app.modules.collections import service as collections_service
from app.modules.collections.models import CollectionReceipt
from app.modules.construction import service as construction_service
from app.modules.construction.models import CostCode
from app.modules.projects.models import Project
from app.modules.settings.models import Currency
from app.modules.unit_economics import service as economics_service


def _currency_code(session: Session, currency_id: uuid.UUID | None) -> str | None:
    if currency_id is None:
        return None
    currency = session.get(Currency, currency_id)
    return currency.code if currency is not None else None


# --------------------------------------------------------------------------- #
# Forecast
# --------------------------------------------------------------------------- #


def forecast_out(
    session: Session, *, project: Project, version: CashflowForecastVersion
) -> schemas.ForecastOut:
    """A forecast header, with its currency and pinned construction version resolved.

    Built field by field rather than validated straight off the ORM row: the row
    carries a ``currency_id`` and not a code, and the construction pin is a
    version identifier rather than the number a person reads.
    """
    pinned = construction_service.cashflow_forecast_position(
        session, project_id=project.id, version_id=version.construction_forecast_version_id
    )
    snapshot_count = len(service.snapshot_rows(session, version_id=version.id))
    return schemas.ForecastOut(
        id=version.id,
        version_number=version.version_number,
        status=version.status,
        currency_code=_currency_code(session, version.currency_id),
        as_of_date=version.as_of_date,
        forecast_start_month=version.forecast_start_month,
        forecast_end_month=version.forecast_end_month,
        opening_unrestricted_cash=version.opening_unrestricted_cash,
        opening_restricted_cash=version.opening_restricted_cash,
        opening_total_cash=money(
            version.opening_unrestricted_cash + version.opening_restricted_cash
        ),
        discount_rate_per_period=version.discount_rate_per_period,
        construction_forecast_version_id=version.construction_forecast_version_id,
        construction_forecast_version_number=pinned.version_number if pinned else None,
        source_version_id=version.source_version_id,
        change_reason=version.change_reason,
        installments_in_snapshot=snapshot_count,
    )


def _cost_code_labels(session: Session, *, project_id: uuid.UUID) -> dict[uuid.UUID, str]:
    return {
        code.id: code.code
        for code in session.scalars(select(CostCode).where(CostCode.project_id == project_id))
    }


def line_out(line: CashflowForecastLine, labels: dict[uuid.UUID, str]) -> schemas.ForecastLineOut:
    return schemas.ForecastLineOut(
        id=line.id,
        period_month=line.period_month,
        flow_direction=line.flow_direction,
        category=line.category,
        source_kind=line.source_kind,
        amount=line.amount,
        phase_id=line.phase_id,
        construction_cost_code_id=line.construction_cost_code_id,
        construction_cost_code=labels.get(line.construction_cost_code_id)
        if line.construction_cost_code_id
        else None,
        note=line.note,
    )


def staleness_out(staleness: service.SourceStaleness) -> schemas.StalenessOut:
    return schemas.StalenessOut(
        is_stale=staleness.is_stale,
        construction_is_stale=staleness.construction_is_stale,
        pinned_construction_version_number=staleness.pinned_construction_version_number,
        active_construction_version_number=staleness.active_construction_version_number,
        customer_schedule_is_stale=staleness.customer_schedule_is_stale,
        snapshot_plan_version_count=staleness.snapshot_plan_version_count,
        governing_plan_version_count=staleness.governing_plan_version_count,
    )


def check_out(check: calculator.Check) -> schemas.CheckOut:
    return schemas.CheckOut(
        name=check.name,
        passed=check.passed,
        expected=check.expected,
        actual=check.actual,
        detail=check.detail,
    )


def forecast_detail(
    session: Session, *, project: Project, version: CashflowForecastVersion
) -> schemas.ForecastDetailOut:
    """The forecast file: what it schedules, what it froze, and whether it holds.

    The staleness block and the construction reconciliation are part of the
    detail rather than a separate call, because the submission screen has to
    show them before it offers the button. Somebody approving a forecast whose
    sources have moved should be told on the screen where they are approving it.
    """
    labels = _cost_code_labels(session, project_id=project.id)
    return schemas.ForecastDetailOut(
        **forecast_out(session, project=project, version=version).model_dump(),
        lines=[
            line_out(line, labels)
            for line in service.forecast_lines(session, version_id=version.id)
        ],
        customer_schedule=[
            schemas.ScheduleSnapshotOut(
                installment_id=row.installment_id,
                payment_plan_version_id=row.payment_plan_version_id,
                sale_contract_id=row.sale_contract_id,
                unit_id=row.unit_id,
                amount=row.amount,
                contractual_due_date=row.contractual_due_date,
                forecast_due_date=row.forecast_due_date,
                actual_due_date=row.actual_due_date,
                chosen_forecast_date=row.chosen_forecast_date,
                trigger_type=row.trigger_type,
                trigger_status=row.trigger_status,
            )
            for row in service.snapshot_rows(session, version_id=version.id)
        ],
        staleness=staleness_out(
            service.source_staleness(session, project=project, version=version)
        ),
        construction_reconciliation=[
            check_out(check)
            for check in service.construction_reconciliation(
                session, project=project, version=version
            )
        ],
    )


# --------------------------------------------------------------------------- #
# Cash this module owns
# --------------------------------------------------------------------------- #


def development_movement_out(
    session: Session, *, movement: CashflowDevelopmentMovement
) -> schemas.DevelopmentMovementOut:
    return schemas.DevelopmentMovementOut(
        id=movement.id,
        movement_reference=movement.movement_reference,
        category=movement.category,
        amount=movement.amount,
        currency_code=_currency_code(session, movement.currency_id),
        movement_date=movement.movement_date,
        value_date=movement.value_date,
        phase_id=movement.phase_id,
        status=movement.status,
        counterparty_reference=movement.counterparty_reference,
        invoice_reference=movement.invoice_reference,
        bank_reference=movement.bank_reference,
        evidence_reference=movement.evidence_reference,
        notes=movement.notes,
        counts_as_cash=movement.status == MOVEMENT_CONFIRMED,
    )


def financing_movement_out(
    session: Session, *, movement: CashflowFinancingMovement
) -> schemas.FinancingMovementOut:
    return schemas.FinancingMovementOut(
        id=movement.id,
        movement_reference=movement.movement_reference,
        movement_type=movement.movement_type,
        flow_direction=movement.flow_direction,
        amount=movement.amount,
        currency_code=_currency_code(session, movement.currency_id),
        movement_date=movement.movement_date,
        value_date=movement.value_date,
        status=movement.status,
        counterparty_reference=movement.counterparty_reference,
        facility_reference=movement.facility_reference,
        bank_reference=movement.bank_reference,
        evidence_reference=movement.evidence_reference,
        notes=movement.notes,
        counts_as_cash=movement.status == MOVEMENT_CONFIRMED,
    )


def restriction_stands(session: Session, *, restriction: CashflowReceiptRestriction) -> bool:
    """Whether this escrow is holding project cash **now**.

    Its own confirmation is half the question. A restriction is a claim over one
    receipt, so it can only hold money that receipt still put in the bank: once
    the transfer is reversed there is nothing left for the escrow to hold, and
    saying otherwise subtracts an amount from a balance that no longer exists.

    The same rule the reports use, asked here so the record and the report
    cannot disagree. The persisted status is untouched — the restriction really
    was confirmed, and rewriting that to tidy a screen would destroy the audit
    trail — which is why the reconciliation goes on naming it as a correction
    somebody owes.
    """
    if restriction.status != MOVEMENT_CONFIRMED:
        return False
    receipt = session.get(CollectionReceipt, restriction.receipt_id)
    return receipt is not None and receipt.status == STANDING_CONFIRMED


def release_out(
    release: CashflowRestrictionRelease, *, restriction_counts: bool
) -> schemas.ReleaseOut:
    """One release, and whether it is currently freeing anything.

    ``counts_as_released`` needs the parent chain and not only this row's own
    status: a release frees an escrow, and an escrow whose receipt was reversed
    is holding nothing to free. Passed in rather than looked up, so every caller
    has to have decided.
    """
    return schemas.ReleaseOut(
        id=release.id,
        restriction_id=release.restriction_id,
        release_date=release.release_date,
        amount=release.amount,
        certification_reference=release.certification_reference,
        evidence_reference=release.evidence_reference,
        status=release.status,
        counts_as_released=release.status == MOVEMENT_CONFIRMED and restriction_counts,
        restriction_counts=restriction_counts,
    )


def restriction_out(
    session: Session, *, restriction: CashflowReceiptRestriction
) -> schemas.RestrictionOut:
    """An escrow record with its releases and what is still held.

    ``outstanding_restricted`` is derived on every read rather than stored,
    which is what stops it disagreeing with the releases printed underneath it.
    """
    receipt = session.get(CollectionReceipt, restriction.receipt_id)
    releases = list(
        session.scalars(
            select(CashflowRestrictionRelease)
            .where(CashflowRestrictionRelease.restriction_id == restriction.id)
            .order_by(CashflowRestrictionRelease.release_date)
        )
    )
    released = service.released_against(session, restriction_id=restriction.id)
    standing = restriction_stands(session, restriction=restriction)
    return schemas.RestrictionOut(
        id=restriction.id,
        receipt_id=restriction.receipt_id,
        receipt_number=receipt.receipt_number if receipt else None,
        receipt_amount=receipt.amount if receipt else None,
        restricted_amount=restriction.restricted_amount,
        released_amount=released,
        outstanding_restricted=money(restriction.restricted_amount - released)
        if standing
        else ZERO,
        reason=restriction.reason,
        source_reference=restriction.source_reference,
        status=restriction.status,
        counts_as_restricted=standing,
        receipt_stands=receipt is not None and receipt.status == STANDING_CONFIRMED,
        releases=[release_out(release, restriction_counts=standing) for release in releases],
    )


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def report_basis(
    session: Session,
    *,
    project: Project,
    as_of: date,
    version: CashflowForecastVersion | None,
    from_month: date | None = None,
    to_month: date | None = None,
) -> schemas.ReportBasis:
    """What every reporting response says about itself before its figures."""
    return schemas.ReportBasis(
        project_id=project.id,
        as_of_date=as_of,
        currency_code=_currency_code(session, project.base_currency_id),
        forecast_version_id=version.id if version else None,
        forecast_version_number=version.version_number if version else None,
        forecast_as_of_date=version.as_of_date if version else None,
        from_month=from_month,
        to_month=to_month,
    )


def position_out(position: service.MonthlyPosition) -> schemas.MonthlyPositionOut:
    return schemas.MonthlyPositionOut(
        period_month=position.period_month,
        basis=service.month_basis(position.period_state),
        opening_total_cash=position.opening_total_cash,
        customer_scheduled_due=position.customer_scheduled_due,
        customer_actual_receipts=position.customer_actual_receipts,
        customer_forecast_receipts=position.customer_forecast_receipts,
        financing_actual_inflows=position.financing_actual_inflows,
        financing_forecast_inflows=position.financing_forecast_inflows,
        development_actual_outflows=position.development_actual_outflows,
        development_forecast_outflows=position.development_forecast_outflows,
        construction_actual_payments=position.construction_actual_payments,
        construction_forecast_payments=position.construction_forecast_payments,
        customer_refunds=position.customer_refunds,
        financing_actual_outflows=position.financing_actual_outflows,
        financing_forecast_outflows=position.financing_forecast_outflows,
        total_inflows=position.total_inflows,
        total_outflows=position.total_outflows,
        net_cashflow=position.net_cashflow,
        closing_total_cash=position.closing_total_cash,
        opening_restricted_cash=position.opening_restricted_cash,
        newly_restricted_customer_cash=position.newly_restricted_customer_cash,
        escrow_releases=position.escrow_releases,
        closing_restricted_cash=position.closing_restricted_cash,
        opening_unrestricted_cash=position.opening_unrestricted_cash,
        usable_inflows=position.usable_inflows,
        unrestricted_outflows=position.unrestricted_outflows,
        closing_unrestricted_cash=position.closing_unrestricted_cash,
        funding_gap=position.funding_gap,
    )


def monthly_out(
    session: Session,
    *,
    project: Project,
    as_of: date,
    from_month: date | None = None,
    to_month: date | None = None,
) -> schemas.MonthlyOut:
    """The cash bridge, month by month, with the basis stated."""
    version = service.active_forecast(session, project_id=project.id)
    positions = service.monthly_positions(
        session,
        project=project,
        version=version,
        as_of=as_of,
        start_month=service.month_of(from_month) if from_month else None,
        end_month=service.month_of(to_month) if to_month else None,
    )
    return schemas.MonthlyOut(
        basis=report_basis(
            session,
            project=project,
            as_of=as_of,
            version=version,
            from_month=positions[0].period_month if positions else None,
            to_month=positions[-1].period_month if positions else None,
        ),
        months=[position_out(position) for position in positions],
    )


#: The monthly export's columns, in the order the cash bridge reads.
MONTHLY_CSV_COLUMNS: tuple[tuple[str, str], ...] = (
    ("period_month", "Month"),
    ("basis", "Basis"),
    ("opening_total_cash", "Opening total cash"),
    ("customer_scheduled_due", "Customer scheduled due"),
    ("customer_actual_receipts", "Customer actual receipts"),
    ("customer_forecast_receipts", "Customer forecast receipts"),
    ("financing_actual_inflows", "Financing in (actual)"),
    ("financing_forecast_inflows", "Financing in (forecast)"),
    ("construction_actual_payments", "Construction paid"),
    ("construction_forecast_payments", "Construction forecast"),
    ("development_actual_outflows", "Development paid"),
    ("development_forecast_outflows", "Development forecast"),
    ("customer_refunds", "Refunds"),
    ("financing_actual_outflows", "Financing out (actual)"),
    ("financing_forecast_outflows", "Financing out (forecast)"),
    ("total_inflows", "Total inflows"),
    ("total_outflows", "Total outflows"),
    ("net_cashflow", "Net cashflow"),
    ("closing_total_cash", "Closing total cash"),
    ("opening_restricted_cash", "Opening restricted"),
    ("newly_restricted_customer_cash", "Newly restricted"),
    ("escrow_releases", "Escrow released"),
    ("closing_restricted_cash", "Closing restricted"),
    ("closing_unrestricted_cash", "Closing unrestricted"),
    ("funding_gap", "Funding gap"),
)


def monthly_csv(monthly: schemas.MonthlyOut) -> str:
    """Render the same response the screen shows. Never a second query.

    Taking the assembled response rather than re-deriving it is the whole point.
    Two paths to one figure eventually disagree, and the disagreement is
    discovered by somebody comparing a board pack against the spreadsheet
    attached to it.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _, label in MONTHLY_CSV_COLUMNS])
    for month in monthly.months:
        writer.writerow([str(getattr(month, field)) for field, _ in MONTHLY_CSV_COLUMNS])
    return buffer.getvalue()


def source_row_out(row: service.SourceRow) -> schemas.SourceRowOut:
    return schemas.SourceRowOut(
        source_type=row.source_type,
        source_id=row.source_id,
        period_month=row.period_month,
        business_date=row.business_date,
        amount=row.amount,
        flow_direction=row.flow_direction,
        category=row.category,
        basis=row.basis,
        status=row.status,
        display_reference=row.display_reference,
    )


def drilldown_out(
    session: Session,
    *,
    project: Project,
    as_of: date,
    period_month: date | None = None,
    category: str | None = None,
    basis: str | None = None,
    source_type: str | None = None,
    flow_direction: str | None = None,
) -> schemas.DrilldownOut:
    """The transactions behind a figure, filtered the way the figure was.

    Every management number has to open into the rows that made it, and the rows
    are references to records the owning modules already hold — never a second
    copy written for reporting, which would be one more thing to keep in step.
    """
    version = service.active_forecast(session, project_id=project.id)
    rows = service.collect_source_rows(session, project=project, version=version, as_of=as_of)
    # A drill-down that does not add up to the figure it opened from is worse
    # than no drill-down, so it shows exactly the rows the bridge counted — plus
    # the contractual schedule, which is a memo series and is labelled one.
    filtered = [
        row
        for row in rows
        if (row.basis == service.BASIS_SCHEDULED or service.counts_as_cash(row, as_of=as_of))
        and (period_month is None or row.period_month == service.month_of(period_month))
        and (category is None or row.category == category)
        and (basis is None or row.basis == basis)
        and (source_type is None or row.source_type == source_type)
        and (flow_direction is None or row.flow_direction == flow_direction)
    ]
    return schemas.DrilldownOut(
        basis=report_basis(
            session,
            project=project,
            as_of=as_of,
            version=version,
            from_month=period_month,
            to_month=period_month,
        ),
        total=calculator.total(row.amount for row in filtered),
        rows=[source_row_out(row) for row in filtered],
    )


DRILLDOWN_CSV_COLUMNS: tuple[tuple[str, str], ...] = (
    ("source_type", "Source"),
    ("source_id", "Source ID"),
    ("period_month", "Month"),
    ("business_date", "Date"),
    ("amount", "Amount"),
    ("flow_direction", "Direction"),
    ("category", "Category"),
    ("basis", "Basis"),
    ("status", "Status"),
    ("display_reference", "Reference"),
)


def drilldown_csv(drilldown: schemas.DrilldownOut) -> str:
    """The same rows the drill-down returned, in the same order."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _, label in DRILLDOWN_CSV_COLUMNS])
    for row in drilldown.rows:
        writer.writerow([str(getattr(row, field)) for field, _ in DRILLDOWN_CSV_COLUMNS])
    return buffer.getvalue()


def summary_out(session: Session, *, project: Project, as_of: date) -> schemas.SummaryOut:
    """The command surface: where cash stands, when it runs short, what it earns.

    Unrestricted cash leads, because it is the only one of the three balances a
    developer can actually spend. Total and restricted are stated beside it
    rather than instead of it, so nobody has to subtract two numbers on a screen
    to learn what the company can pay a contractor with.
    """
    version = service.active_forecast(session, project_id=project.id)
    positions = service.monthly_positions(session, project=project, version=version, as_of=as_of)
    rows = service.collect_source_rows(session, project=project, version=version, as_of=as_of)

    # What is in the bank, not where this month will end. The month the report
    # is taken in closes on a blended figure — cash that moved plus cash still
    # expected — and reporting that as the position would tell a developer they
    # can pay a contractor with money that has not arrived.
    held = service.actual_cash_position(rows, version=version, as_of=as_of)

    # Coverage is a forward question, so it is asked of forward cash only. The
    # current month contributes the part of itself that has not happened yet.
    ahead = [position for position in positions if position.period_state != service.PERIOD_CLOSED]
    coverage_numerator = calculator.total(
        money(position.customer_forecast_receipts + position.financing_forecast_inflows)
        for position in ahead
    )
    coverage_denominator = calculator.total(
        money(
            position.construction_forecast_payments
            + position.development_forecast_outflows
            + position.financing_forecast_outflows
        )
        for position in ahead
    )
    peak = calculator.peak_deficit(
        [(position.period_month, position.closing_unrestricted_cash) for position in positions]
    )
    returns = service.return_position(
        positions,
        rows,
        as_of=as_of,
        discount_rate_per_period=version.discount_rate_per_period if version else ZERO,
    )

    return schemas.SummaryOut(
        basis=report_basis(
            session,
            project=project,
            as_of=as_of,
            version=version,
            from_month=positions[0].period_month if positions else None,
            to_month=positions[-1].period_month if positions else None,
        ),
        position=schemas.CashPositionOut(
            total_cash=held.total_cash,
            restricted_cash=held.restricted_cash,
            unrestricted_cash=held.unrestricted_cash,
            forecast_collection_coverage=calculator.forecast_collection_coverage(
                usable_customer_inflows=coverage_numerator,
                project_outflows=coverage_denominator,
            ),
            coverage_numerator=coverage_numerator,
            coverage_denominator=coverage_denominator,
        ),
        peak_deficit=schemas.PeakDeficitOut(
            minimum_unrestricted_cash=peak.minimum_unrestricted_cash,
            peak_funding_deficit=peak.peak_funding_deficit,
            peak_deficit_month=peak.peak_deficit_month,
        ),
        funding_windows=[
            schemas.FundingWindowOut(
                days=window.days,
                from_date=window.from_date,
                to_date=window.to_date,
                opening_unrestricted_cash=window.opening_unrestricted_cash,
                usable_inflows=window.usable_inflows,
                outflows=window.outflows,
                net_movement=window.net_movement,
                minimum_projected_unrestricted_cash=(window.minimum_projected_unrestricted_cash),
                closing_projected_unrestricted_cash=(window.closing_projected_unrestricted_cash),
                funding_requirement=window.funding_requirement,
            )
            for window in service.funding_windows(
                session, project=project, version=version, as_of=as_of, rows=rows
            )
        ],
        returns=schemas.ReturnOut(
            npv_basis=returns.npv_basis,
            discount_rate_per_period=returns.discount_rate_per_period,
            net_present_value=returns.net_present_value,
            net_project_cashflow=returns.net_project_cashflow,
            equity_irr_basis=returns.equity_irr_basis,
            equity_irr_per_period=returns.equity_irr_per_period,
            equity_irr_unavailable_reason=returns.equity_irr_unavailable_reason,
            equity_contributed=returns.equity_contributed,
            equity_distributed=returns.equity_distributed,
            equity_net=returns.equity_net,
        ),
        has_active_forecast=version is not None,
        staleness=staleness_out(service.source_staleness(session, project=project, version=version))
        if version is not None
        else None,
    )


def reconciliation_out(
    session: Session, *, project: Project, as_of: date
) -> schemas.ReconciliationOut:
    """Every structural check, answered on its own. No health score."""
    version = service.active_forecast(session, project_id=project.id)
    checks = service.reconciliation(session, project=project, as_of=as_of)
    return schemas.ReconciliationOut(
        basis=report_basis(session, project=project, as_of=as_of, version=version),
        checks=[check_out(check) for check in checks],
        failed_count=sum(1 for check in checks if not check.passed),
    )


def forecast_accuracy_out(
    session: Session,
    *,
    project: Project,
    version: CashflowForecastVersion,
    as_of: date,
) -> schemas.ForecastAccuracyOut:
    """A prior forecast against what actually happened, by month and group."""
    return schemas.ForecastAccuracyOut(
        basis=report_basis(session, project=project, as_of=as_of, version=version),
        rows=[
            schemas.AccuracyRowOut(
                period_month=row.period_month,
                category_group=row.category_group,
                variance=schemas.VarianceOut(
                    forecast_amount=row.variance.forecast_amount,
                    actual_amount=row.variance.actual_amount,
                    variance_amount=row.variance.variance_amount,
                    variance_rate=row.variance.variance_rate,
                ),
            )
            for row in service.forecast_accuracy(
                session, project=project, version=version, as_of=as_of
            )
        ],
    )


# --------------------------------------------------------------------------- #
# Management reporting
# --------------------------------------------------------------------------- #

GROUP_COLLECTIONS = "Collections"
GROUP_CONSTRUCTION = "Construction"
GROUP_CASH = "Cash & Funding"
GROUP_RETURNS = "Returns"
GROUP_ECONOMICS = "Unit Economics"


def _metric(
    key: str,
    label: str,
    value: Decimal | str | None,
    *,
    unit: str,
    source_module: str,
    drilldown_source_type: str | None = None,
) -> schemas.ManagementMetricOut:
    return schemas.ManagementMetricOut(
        key=key,
        label=label,
        value=None if value is None else str(value),
        unit=unit,
        source_module=source_module,
        drilldown_source_type=drilldown_source_type,
    )


def management_out(
    session: Session, *, project: Project, actor: ActorContext, as_of: date
) -> schemas.ManagementOut:
    """One management view, assembled from the modules that own each fact.

    Nothing here is recalculated. Construction's control position comes from
    construction, collections' position from collections, unit economics'
    contribution from unit economics — each through the reader that module
    already publishes. Cashflow contributes only what it owns: the cross-module,
    time-based figures nothing else can answer.

    Restating another module's arithmetic here would produce a second definition
    of "certified to date" that agrees today and drifts the first time the
    original changes, and the drift would be discovered by an executive
    comparing two screens.
    """
    summary = summary_out(session, project=project, as_of=as_of)
    cost = construction_service.cost_control_position(session, project=project)
    payable = construction_service.payable_position(session, project=project)
    collections_summary = collections_service.project_summary(
        session, project=project, actor=actor, as_of=as_of
    )
    base_totals = next(
        (
            totals
            for totals in collections_summary.currencies
            if totals.currency_id == project.base_currency_id
        ),
        None,
    )
    economics, _units = economics_service.project_economics(session, project=project, actor=actor)

    groups = [
        schemas.ManagementGroupOut(
            group=GROUP_CASH,
            metrics=[
                _metric(
                    "unrestricted_cash",
                    "Unrestricted cash",
                    summary.position.unrestricted_cash,
                    unit="money",
                    source_module="cashflow",
                    drilldown_source_type=None,
                ),
                _metric(
                    "total_cash",
                    "Total cash",
                    summary.position.total_cash,
                    unit="money",
                    source_module="cashflow",
                ),
                _metric(
                    "restricted_cash",
                    "Restricted cash",
                    summary.position.restricted_cash,
                    unit="money",
                    source_module="cashflow",
                    drilldown_source_type=service.SOURCE_RESTRICTION,
                ),
                *[
                    _metric(
                        f"funding_requirement_{window.days}",
                        f"Next {window.days} days funding requirement",
                        window.funding_requirement,
                        unit="money",
                        source_module="cashflow",
                    )
                    for window in summary.funding_windows
                ],
                _metric(
                    "peak_funding_deficit",
                    "Peak funding deficit",
                    summary.peak_deficit.peak_funding_deficit,
                    unit="money",
                    source_module="cashflow",
                ),
                _metric(
                    "peak_deficit_month",
                    "Worst month",
                    summary.peak_deficit.peak_deficit_month.isoformat()
                    if summary.peak_deficit.peak_deficit_month
                    else None,
                    unit="month",
                    source_module="cashflow",
                ),
                _metric(
                    "forecast_collection_coverage",
                    "Forecast collection coverage",
                    summary.position.forecast_collection_coverage,
                    unit="fraction",
                    source_module="cashflow",
                ),
            ],
        ),
        schemas.ManagementGroupOut(
            group=GROUP_RETURNS,
            metrics=[
                _metric(
                    "net_present_value",
                    "Project NPV",
                    summary.returns.net_present_value,
                    unit="money",
                    source_module="cashflow",
                ),
                _metric(
                    "net_project_cashflow",
                    "Net project cashflow",
                    summary.returns.net_project_cashflow,
                    unit="money",
                    source_module="cashflow",
                ),
                # Never alone: IRR sits between two absolute figures so a reader
                # cannot take a percentage without the cash behind it.
                _metric(
                    "equity_irr_per_period",
                    "Equity IRR (per period)",
                    summary.returns.equity_irr_per_period,
                    unit="fraction",
                    source_module="cashflow",
                ),
                _metric(
                    "equity_irr_unavailable_reason",
                    "IRR unavailable because",
                    summary.returns.equity_irr_unavailable_reason,
                    unit="text",
                    source_module="cashflow",
                ),
                _metric(
                    "equity_net",
                    "Equity net",
                    summary.returns.equity_net,
                    unit="money",
                    source_module="cashflow",
                    drilldown_source_type=service.SOURCE_FINANCING_MOVEMENT,
                ),
            ],
        ),
        schemas.ManagementGroupOut(
            group=GROUP_COLLECTIONS,
            metrics=[
                _metric(
                    "due_to_date",
                    "Due to date",
                    base_totals.due_total if base_totals else None,
                    unit="money",
                    source_module="collections",
                ),
                _metric(
                    "confirmed_collected",
                    "Confirmed collected (lifetime)",
                    base_totals.confirmed_receipts_total if base_totals else None,
                    unit="money",
                    source_module="collections",
                    drilldown_source_type=service.SOURCE_RECEIPT,
                ),
                _metric(
                    "overdue",
                    "Overdue",
                    base_totals.overdue_total if base_totals else None,
                    unit="money",
                    source_module="collections",
                ),
                _metric(
                    "unapplied_cash",
                    "Confirmed unapplied cash",
                    base_totals.unapplied_cash if base_totals else None,
                    unit="money",
                    source_module="collections",
                ),
                _metric(
                    "accounts_overdue",
                    "Accounts overdue",
                    str(collections_summary.accounts_overdue),
                    unit="count",
                    source_module="collections",
                ),
            ],
        ),
        schemas.ManagementGroupOut(
            group=GROUP_CONSTRUCTION,
            metrics=[
                _metric(
                    "control_budget",
                    "Control budget",
                    cost.control_budget,
                    unit="money",
                    source_module="construction",
                ),
                _metric(
                    "revised_commitment",
                    "Revised commitment",
                    cost.revised_commitment,
                    unit="money",
                    source_module="construction",
                ),
                _metric(
                    "certified_to_date",
                    "Certified to date",
                    cost.certified_to_date,
                    unit="money",
                    source_module="construction",
                ),
                _metric(
                    "construction_paid",
                    "Construction cash paid",
                    payable.confirmed_paid,
                    unit="money",
                    source_module="construction",
                    drilldown_source_type=service.SOURCE_CONSTRUCTION_PAYMENT,
                ),
                _metric(
                    "estimate_at_completion",
                    "Estimate at completion",
                    cost.estimate_at_completion,
                    unit="money",
                    source_module="construction",
                ),
                _metric(
                    "variance_at_completion",
                    "Variance at completion",
                    cost.variance_at_completion,
                    unit="money",
                    source_module="construction",
                ),
            ],
        ),
        schemas.ManagementGroupOut(
            group=GROUP_ECONOMICS,
            metrics=[
                _metric(
                    "revenue_total",
                    "Contracted and expected revenue",
                    economics.totals.revenue_total,
                    unit="money",
                    source_module="unit_economics",
                ),
                _metric(
                    "contribution_profit_total",
                    "Contribution profit",
                    economics.totals.contribution_profit_total,
                    unit="money",
                    source_module="unit_economics",
                ),
                _metric(
                    "margin_fraction",
                    "Margin",
                    economics.totals.margin_fraction,
                    unit="fraction",
                    source_module="unit_economics",
                ),
                _metric(
                    "sold_count",
                    "Units sold",
                    str(economics.sold_count),
                    unit="count",
                    source_module="unit_economics",
                ),
                _metric(
                    "unsold_count",
                    "Units unsold",
                    str(economics.unsold_count),
                    unit="count",
                    source_module="unit_economics",
                ),
            ],
        ),
    ]
    return schemas.ManagementOut(basis=summary.basis, groups=groups)
