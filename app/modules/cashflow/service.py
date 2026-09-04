"""Cashflow: the governed forecast, the cash this module owns, and escrow.

Everything here holds one line: **cashflow consolidates cash it does not own.**
Not a single receipt, refund, construction payment or buyer instalment is
written by this module. They are read through the named contracts each source
module publishes, and the only rows written here are the ones nothing else in
the platform records — a consultant's fee, an equity drawdown, the escrow that
makes received cash unusable — plus the governed statement of when Finance
expects the rest of it to move.

Three disciplines run through the whole file.

**Recording is not paying.** A development or financing movement is a claim
until a second person confirms it, and the confirmer is never the recorder,
compared by user identifier. This is the same rule collections applies to buyer
cash and construction applies to contractor cash, and it is here for the same
reason: a single person who can both instruct and confirm a payment is not a
control.

**A governed forecast is history and stays reproducible.** Its cutoff decides
which transactions existed when it was approved; the business date decides which
month they land in. Those are different questions and this module never lets one
answer the other. A receipt confirmed after the cutoff is not in the forecast at
all; once a later forecast picks it up, it belongs to the month it is dated.

**Cash arrives once.** The subtlest rule in the module, and the one worth
reading twice. A confirmed receipt is already counted as cash that arrived. If
the instalments it will eventually be applied to also stay in the forward
collection forecast at full value, the same money is counted twice — once as
received and once as expected. The forecast therefore offsets confirmed
unapplied cash against the remaining schedule, deterministically, for forecast
purposes only. Nothing is written, and no allocation is created: the operator's
filing backlog is theirs to clear and a forecast is not permitted to clear it
for them.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.standing import CONFIRMED as STANDING_CONFIRMED
from app.core.standing import standing_conditions
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.cashflow import calculator, permissions
from app.modules.cashflow.calculator import ZERO, money
from app.modules.cashflow.models import (
    CATEGORY_CONSTRUCTION,
    CATEGORY_CUSTOMER_COLLECTION,
    DEVELOPMENT_CATEGORIES,
    EQUITY_CONTRIBUTION,
    EQUITY_DISTRIBUTION,
    FINANCING_INFLOW_TYPES,
    FINANCING_TYPES,
    FLOW_INFLOW,
    FLOW_OUTFLOW,
    FORECAST_ACTIVE,
    FORECAST_APPROVED,
    FORECAST_DRAFT,
    FORECAST_OPEN,
    FORECAST_REFRESHABLE,
    FORECAST_REJECTED,
    FORECAST_SOURCE_KINDS,
    FORECAST_SUBMITTED,
    FORECAST_SUPERSEDED,
    MOVEMENT_CONFIRMED,
    MOVEMENT_RECORDED,
    MOVEMENT_REVERSED,
    SOURCE_CONSTRUCTION,
    SOURCE_DEVELOPMENT,
    SOURCE_FINANCING,
    SOURCE_UNSOLD_CUSTOMER,
    CashflowCustomerScheduleSnapshot,
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
from app.modules.inventory.custom_fields import business_today
from app.modules.payment_plans import service as payment_plans_service
from app.modules.payment_plans.models import TRIGGER_AWAITING, TRIGGER_TRIGGERED
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.settings.models import Currency

#: The four tables in this module that follow one lifecycle: recorded, then
#: confirmed by a second person, then reversible without being erased. They do
#: not share a base class — each has its own columns and its own meaning — so
#: the helpers below take the union rather than a mixin invented to unify them.
CashMovement = (
    CashflowDevelopmentMovement
    | CashflowFinancingMovement
    | CashflowReceiptRestriction
    | CashflowRestrictionRelease
)

ENTITY_FORECAST = "cashflow_forecast_version"
ENTITY_DEVELOPMENT = "cashflow_development_movement"
ENTITY_FINANCING = "cashflow_financing_movement"
ENTITY_RESTRICTION = "cashflow_receipt_restriction"
ENTITY_RELEASE = "cashflow_restriction_release"

_FORECAST_FIELDS = (
    "id",
    "version_number",
    "status",
    "as_of_date",
    "forecast_start_month",
    "forecast_end_month",
    "opening_unrestricted_cash",
    "opening_restricted_cash",
    "discount_rate_per_period",
    "construction_forecast_version_id",
    "change_reason",
)
_MOVEMENT_FIELDS = (
    "id",
    "movement_reference",
    "amount",
    "movement_date",
    "value_date",
    "status",
)
_DEVELOPMENT_FIELDS = (*_MOVEMENT_FIELDS, "category", "phase_id")
_FINANCING_FIELDS = (*_MOVEMENT_FIELDS, "movement_type", "flow_direction")
_RESTRICTION_FIELDS = ("id", "receipt_id", "restricted_amount", "reason", "status")
_RELEASE_FIELDS = ("id", "restriction_id", "amount", "release_date", "status")


def _flush(session: Session) -> None:
    """Push pending changes so the database's own constraints answer first."""
    session.flush()


def _now() -> datetime:
    return datetime.now(UTC)


def _snapshot(row: object, fields: tuple[str, ...]) -> dict[str, Any]:
    """The audit trail's before/after picture of a row, as plain values."""
    out: dict[str, Any] = {}
    for field in fields:
        value = getattr(row, field, None)
        if isinstance(value, uuid.UUID | Decimal):
            out[field] = str(value)
        elif isinstance(value, date | datetime):
            out[field] = value.isoformat()
        else:
            out[field] = value
    return out


# --------------------------------------------------------------------------- #
# Months
# --------------------------------------------------------------------------- #


def month_of(day: date) -> date:
    """The first of the month a date falls in.

    Every period column in this module holds a canonical first-of-month, so a
    March receipt and a March forecast line group together instead of becoming
    two rows nothing will ever add up.
    """
    return day.replace(day=1)


def next_month(month: date) -> date:
    """The first of the month after ``month``."""
    if month.month == 12:
        return date(month.year + 1, 1, 1)
    return date(month.year, month.month + 1, 1)


def months_between(start: date, end: date) -> list[date]:
    """Every month from ``start`` to ``end`` inclusive, with no gaps.

    A month in which nothing happened still appears, carrying zeros. Omitting it
    would make a chart's horizontal axis lie about elapsed time and would let a
    quiet quarter read as three weeks.
    """
    if end < start:
        raise ValidationError("A forecast horizon cannot end before it starts.")
    months: list[date] = []
    current = month_of(start)
    last = month_of(end)
    while current <= last:
        months.append(current)
        current = next_month(current)
    return months


def resolve_as_of(as_of: date | None) -> date:
    """The date a read is answered for, refused if it is in the future.

    A cash position asked for next quarter would have to invent either
    transactions or the absence of them, and both inventions arrive in the same
    shape as fact. The forecast is where the future lives, and it is labelled.
    """
    today = business_today()
    if as_of is None:
        return today
    if as_of > today:
        raise ValidationError(
            f"A cash position cannot be taken as at {as_of}, which has not happened "
            "yet. The forecast answers questions about the future and says so."
        )
    return as_of


# --------------------------------------------------------------------------- #
# Forecast version
# --------------------------------------------------------------------------- #


def list_forecasts(session: Session, *, project: Project) -> list[CashflowForecastVersion]:
    """Every cashflow forecast this project has had, newest first."""
    return list(
        session.scalars(
            select(CashflowForecastVersion)
            .where(CashflowForecastVersion.project_id == project.id)
            .order_by(CashflowForecastVersion.version_number.desc())
        )
    )


def get_forecast(
    session: Session, *, project: Project, version_id: uuid.UUID
) -> CashflowForecastVersion:
    """Load one forecast of this project, or refuse as if it did not exist."""
    version = session.scalars(
        select(CashflowForecastVersion).where(
            CashflowForecastVersion.id == version_id,
            CashflowForecastVersion.project_id == project.id,
        )
    ).first()
    if version is None:
        raise permissions.forecast_not_found()
    return version


def active_forecast(session: Session, *, project_id: uuid.UUID) -> CashflowForecastVersion | None:
    """The forecast currently in force, or ``None`` where none has been activated."""
    return session.scalars(
        select(CashflowForecastVersion).where(
            CashflowForecastVersion.project_id == project_id,
            CashflowForecastVersion.status == FORECAST_ACTIVE,
        )
    ).first()


def _open_forecast(session: Session, *, project_id: uuid.UUID) -> CashflowForecastVersion | None:
    """The forecast being drafted, checked or waiting to be activated."""
    return session.scalars(
        select(CashflowForecastVersion).where(
            CashflowForecastVersion.project_id == project_id,
            CashflowForecastVersion.status.in_(tuple(FORECAST_OPEN)),
        )
    ).first()


def _lock_forecast(
    session: Session, *, project_id: uuid.UUID, version_id: uuid.UUID
) -> CashflowForecastVersion:
    """Take one forecast row for update, having already locked the project."""
    version = session.scalars(
        select(CashflowForecastVersion)
        .where(
            CashflowForecastVersion.id == version_id,
            CashflowForecastVersion.project_id == project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if version is None:
        raise permissions.forecast_not_found()
    return version


def create_forecast(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    as_of_date: date,
    forecast_start_month: date,
    forecast_end_month: date,
    opening_unrestricted_cash: Decimal,
    opening_restricted_cash: Decimal,
    discount_rate_per_period: Decimal,
    change_reason: str,
    construction_forecast_version_id: uuid.UUID | None = None,
    source_version_id: uuid.UUID | None = None,
) -> CashflowForecastVersion:
    """Open a cashflow forecast, pinning what it is measured against.

    Two pins are taken here rather than at activation, because both are part of
    what the preparer is deciding. The construction forecast supplies the
    *amount* of remaining build cost this version will schedule month by month;
    the customer schedule snapshot, written immediately below, freezes which
    buyer instalments it was built on. A version that re-read either at approval
    time would not be the version anybody reviewed.

    The as-of date may not be in the future. A forecast taken as at a date that
    has not happened would have to guess which transactions had been confirmed
    by then, and the guess would be indistinguishable from a fact in every
    report that consumed it.
    """
    lock_project(session, project.id)
    if as_of_date > business_today():
        raise ValidationError(
            f"This forecast is taken as at {as_of_date}, which has not happened yet. "
            "A cutoff in the future would have to assume which transactions will "
            "have been confirmed by then."
        )
    if _open_forecast(session, project_id=project.id) is not None:
        raise ConflictError(
            "A cashflow forecast is already being prepared for this project. Finish "
            "or reject it before starting another — two open forecasts are two "
            "answers to one question."
        )
    start = month_of(forecast_start_month)
    end = month_of(forecast_end_month)
    if end < start:
        raise ValidationError("A forecast horizon cannot end before it starts.")
    # One temporal meaning for the opening balance, and only one. The figures
    # entered here are cash held at the start of the horizon; every report then
    # rolls that balance forward through what has moved since. If the horizon
    # opened in a *later* month, that balance would be a statement about a month
    # that has not happened, and the current cash position — which is the
    # opening balance plus this month's movement — would be quoting it as money
    # in the bank today. If it opened in an *earlier* month, the balance would be
    # a figure from before the cutoff with a month of unexamined history between
    # it and the report.
    #
    # Tying it to the cutoff's own month removes both without a second date
    # field to keep in step: the balance is cash at the start of the month the
    # forecast was taken in, and the days since are actual transactions.
    if start != month_of(as_of_date):
        raise ValidationError(
            f"A cashflow forecast opens in the month of its as-of date. This one "
            f"is taken as at {as_of_date} and opens in {start}, so its opening "
            f"balance would describe a different month from the cash it is "
            f"measured against. Set the start month to "
            f"{month_of(as_of_date)}, or take the forecast as at a date inside "
            f"{start}."
        )

    construction = construction_service.cashflow_forecast_position(
        session,
        project_id=project.id,
        version_id=construction_forecast_version_id,
    )
    if construction is None:
        raise ConflictError(
            "This project has no construction forecast in force, so there is no "
            "remaining build cost to schedule. Activate a construction forecast "
            "first — scheduling nothing would let a cashflow forecast reconcile "
            "perfectly against a project that has not costed its build."
        )

    source: CashflowForecastVersion | None = None
    if source_version_id is not None:
        source = get_forecast(session, project=project, version_id=source_version_id)

    highest = session.scalars(
        select(func.max(CashflowForecastVersion.version_number)).where(
            CashflowForecastVersion.project_id == project.id
        )
    ).first()
    version = CashflowForecastVersion(
        project_id=project.id,
        version_number=(highest or 0) + 1,
        currency_id=project.base_currency_id,
        as_of_date=as_of_date,
        forecast_start_month=start,
        forecast_end_month=end,
        opening_unrestricted_cash=money(opening_unrestricted_cash),
        opening_restricted_cash=money(opening_restricted_cash),
        discount_rate_per_period=discount_rate_per_period,
        source_version_id=source.id if source is not None else None,
        construction_forecast_version_id=construction.version_id,
        change_reason=change_reason.strip(),
        status=FORECAST_DRAFT,
        created_by_user_id=actor.user_id,
    )
    session.add(version)
    _flush(session)
    _write_customer_snapshot(session, project=project, version=version)
    record_event(
        session,
        action="cashflow.forecast_created",
        entity_type=ENTITY_FORECAST,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(version, _FORECAST_FIELDS),
    )
    return version


# --------------------------------------------------------------------------- #
# The customer schedule snapshot
# --------------------------------------------------------------------------- #


def chosen_forecast_date(row: payment_plans_service.CashflowScheduleRow) -> date | None:
    """Which of an instalment's three dates this forecast places it on.

    Payment plans keeps three dates because they mean three different things,
    and the choice between them is a forecasting judgement — which is why it is
    made here and never there.

    A **triggered** instalment has an ``actual_due_date``: the event happened and
    the money is contractually due, so that is when it is expected.

    An instalment **awaiting** a trigger has only somebody's expectation of when
    the event will occur. Its ``forecast_due_date`` is used for *timing only*,
    and using it here does not make the instalment due — the whole reason
    PR-MVP-06 kept the columns apart is that a construction forecast slipping by
    a month must not silently move a buyer's contractual obligation.

    Everything else falls back to the contractual date, then to the forecast one.
    An instalment with no date at all cannot be placed in a month and is reported
    as unplaced rather than dropped into the first period to make a total tidy.
    """
    if row.trigger_status == TRIGGER_TRIGGERED and row.actual_due_date is not None:
        return row.actual_due_date
    if row.trigger_status == TRIGGER_AWAITING and row.forecast_due_date is not None:
        return row.forecast_due_date
    return row.contractual_due_date or row.forecast_due_date or row.actual_due_date


def _write_customer_snapshot(
    session: Session, *, project: Project, version: CashflowForecastVersion
) -> int:
    """Freeze the buyer schedule this version was built on. Provenance, not a plan.

    Only instalments that can be placed in a month are recorded. One with no date
    of any kind is genuinely unplaceable — it has no contractual date and nobody
    has forecast its trigger — and inventing a month for it would put money in a
    period on no evidence at all. The reconciliation reports the count instead.
    """
    session.query(CashflowCustomerScheduleSnapshot).filter(
        CashflowCustomerScheduleSnapshot.forecast_version_id == version.id
    ).delete(synchronize_session=False)

    rows = payment_plans_service.cashflow_schedule_rows(
        session, project_id=project.id, as_of=version.as_of_date
    )
    written = 0
    for row in rows:
        placed = chosen_forecast_date(row)
        if placed is None:
            continue
        session.add(
            CashflowCustomerScheduleSnapshot(
                project_id=project.id,
                forecast_version_id=version.id,
                payment_plan_version_id=row.payment_plan_version_id,
                installment_id=row.installment_id,
                sale_contract_id=row.sale_contract_id,
                unit_id=row.unit_id,
                amount=money(row.amount),
                contractual_due_date=row.contractual_due_date,
                forecast_due_date=row.forecast_due_date,
                actual_due_date=row.actual_due_date,
                chosen_forecast_date=placed,
                trigger_type=row.trigger_type,
                trigger_status=row.trigger_status,
            )
        )
        written += 1
    _flush(session)
    return written


def refresh_customer_snapshot(
    session: Session, *, project: Project, actor: ActorContext, version_id: uuid.UUID
) -> int:
    """Re-freeze the buyer schedule under an open forecast, deliberately.

    The explicit act a stale-source refusal asks for. Refreshing is never
    automatic: a schedule quietly re-read underneath a version somebody is
    approving changes what they are approving, and the whole reason the snapshot
    exists is that a governed forecast must not move on its own.
    """
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    if version.status == FORECAST_APPROVED:
        # Not "only an open forecast can be refreshed": an approved one *is*
        # open, and a reader told that would go looking for the wrong problem.
        # The reason is governance, not structure, so the refusal says so and
        # names the way out.
        raise ConflictError(
            "This forecast has already been approved. Its buyer schedule cannot be "
            "changed under that approval — the months the CFO signed for are the "
            "months that schedule produced. Withdraw the approval and prepare or "
            "review the updated forecast instead."
        )
    if version.status not in FORECAST_REFRESHABLE:
        raise ConflictError(
            "Only a draft or submitted cashflow forecast's customer schedule can be "
            "refreshed. An active, superseded or rejected version is a statement "
            "about what the company expected at the time, and re-reading its "
            "sources now would rewrite that."
        )
    written = _write_customer_snapshot(session, project=project, version=version)
    record_event(
        session,
        action="cashflow.forecast_customer_snapshot_refreshed",
        entity_type=ENTITY_FORECAST,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after={"installments": written},
    )
    return written


def snapshot_rows(
    session: Session, *, version_id: uuid.UUID
) -> list[CashflowCustomerScheduleSnapshot]:
    """The frozen buyer schedule of one forecast version."""
    return list(
        session.scalars(
            select(CashflowCustomerScheduleSnapshot)
            .where(CashflowCustomerScheduleSnapshot.forecast_version_id == version_id)
            .order_by(CashflowCustomerScheduleSnapshot.chosen_forecast_date)
        )
    )


# --------------------------------------------------------------------------- #
# Staleness and reconciliation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SourceStaleness:
    """Whether a forecast's frozen sources still match what governs the project.

    Two independent ways a version can go stale while it is being prepared, and
    both are refusals rather than silent refreshes. A source that moved under an
    approver changes what they are approving, and the fact that the new source is
    more current does not make substituting it honest.
    """

    construction_is_stale: bool
    pinned_construction_version_number: int | None
    active_construction_version_number: int | None
    customer_schedule_is_stale: bool
    snapshot_plan_version_count: int
    governing_plan_version_count: int

    @property
    def is_stale(self) -> bool:
        return self.construction_is_stale or self.customer_schedule_is_stale


def source_staleness(
    session: Session, *, project: Project, version: CashflowForecastVersion
) -> SourceStaleness:
    """Compare a forecast's pinned sources with what governs the project now."""
    pinned = construction_service.cashflow_forecast_position(
        session, project_id=project.id, version_id=version.construction_forecast_version_id
    )
    current = construction_service.cashflow_forecast_position(session, project_id=project.id)
    construction_stale = (
        current is not None and pinned is not None and current.version_id != pinned.version_id
    )

    snapshot_versions = set(
        session.scalars(
            select(CashflowCustomerScheduleSnapshot.payment_plan_version_id)
            .where(CashflowCustomerScheduleSnapshot.forecast_version_id == version.id)
            .distinct()
        ).all()
    )
    governing = payment_plans_service.cashflow_governing_version_ids(
        session, project_id=project.id, as_of=version.as_of_date
    )
    return SourceStaleness(
        construction_is_stale=construction_stale,
        pinned_construction_version_number=pinned.version_number if pinned else None,
        active_construction_version_number=current.version_number if current else None,
        customer_schedule_is_stale=snapshot_versions != governing,
        snapshot_plan_version_count=len(snapshot_versions),
        governing_plan_version_count=len(governing),
    )


def construction_schedule_by_cost_code(
    session: Session, *, version_id: uuid.UUID
) -> dict[uuid.UUID, Decimal]:
    """What this forecast schedules for each construction cost code, in total."""
    return {
        cost_code_id: money(amount or ZERO)
        for cost_code_id, amount in session.execute(
            select(
                CashflowForecastLine.construction_cost_code_id,
                func.sum(CashflowForecastLine.amount),
            )
            .where(
                CashflowForecastLine.forecast_version_id == version_id,
                CashflowForecastLine.source_kind == SOURCE_CONSTRUCTION,
            )
            .group_by(CashflowForecastLine.construction_cost_code_id)
        ).all()
    }


def construction_reconciliation(
    session: Session, *, project: Project, version: CashflowForecastVersion
) -> list[calculator.Check]:
    """Every cost code's monthly schedule against the construction forecast it pins.

    Exactly, with no tolerance. Construction says 5,000,000 is left to spend on a
    cost code; this forecast says when. If the months add to 4,600,000 the two
    documents disagree about the project by 400,000, and the disagreement is not
    a rounding artefact — it is either a month somebody forgot or a cost nobody
    has scheduled. A tolerance here would be a decision to stop noticing which.

    An explicit zero is a valid schedule: a preparer looked at the code and said
    nothing is expected to be paid on it inside the horizon. A *missing* code is
    not that — it is a code nobody looked at — and the two are indistinguishable
    to any check that reads an absent code as zero, which is what comparing
    ``scheduled.get(code, 0)`` against a remaining cost of ``0.00`` does. It
    passes. Silently. On the one code the preparer never opened.

    So coverage and amount are asked separately, and both are asked of every
    code. Coverage asks whether the code appears in this forecast at all; the
    amount check then asks whether what it schedules adds up. A code with
    ``0.00`` left to spend passes the amount check either way and fails coverage
    until somebody writes the zero down.
    """
    pinned = construction_service.cashflow_forecast_position(
        session, project_id=project.id, version_id=version.construction_forecast_version_id
    )
    if pinned is None:
        return [
            calculator.count_check(
                name="construction_forecast_pinned",
                actual=1,
                detail="This forecast names a construction forecast that no longer exists.",
            )
        ]
    scheduled = construction_schedule_by_cost_code(session, version_id=version.id)
    checks: list[calculator.Check] = []
    for cost_code_id, remaining in sorted(
        pinned.remaining_by_cost_code.items(),
        key=lambda item: pinned.cost_code_labels.get(item[0], ""),
    ):
        label = pinned.cost_code_labels.get(cost_code_id, str(cost_code_id))
        checks.append(
            calculator.count_check(
                name=f"construction_schedule_covers_{label}",
                actual=0 if cost_code_id in scheduled else 1,
                detail=(
                    f"Construction forecast version {pinned.version_number} carries "
                    f"{label}, and this cashflow forecast has no line for it at all. "
                    "Schedule its months, or write an explicit zero to record that "
                    "nothing is expected on it inside the horizon — an absent code "
                    "is not a decision, it is an omission."
                ),
            )
        )
        checks.append(
            calculator.equality_check(
                name=f"construction_schedule_{label}",
                expected=remaining,
                actual=scheduled.get(cost_code_id, ZERO),
                detail=(
                    f"Construction forecast version {pinned.version_number} has "
                    f"{remaining} left to spend on {label}; this cashflow forecast "
                    f"schedules {scheduled.get(cost_code_id, ZERO)} across its months."
                ),
            )
        )
    # A schedule for a code the construction forecast does not carry is money
    # nobody has costed, and it would never be caught by the loop above.
    for cost_code_id, amount in scheduled.items():
        if cost_code_id not in pinned.remaining_by_cost_code:
            checks.append(
                calculator.equality_check(
                    name=f"construction_schedule_unknown_{cost_code_id}",
                    expected=ZERO,
                    actual=amount,
                    detail=(
                        "This forecast schedules cash for a cost code the pinned "
                        "construction forecast has no remaining cost on."
                    ),
                )
            )
    return checks


def _require_ready_for_governance(
    session: Session, *, project: Project, version: CashflowForecastVersion
) -> None:
    """Refuse to advance a forecast whose sources moved or whose maths disagrees.

    Re-proved at submission and again at activation rather than trusted from
    preparation, because both sources can move underneath an open version: a new
    construction forecast can be activated and a payment plan can be
    restructured while this one sits waiting for a signature.
    """
    # What to do about a moved source depends on where the version stands. A
    # draft or submitted one can be re-pinned in place; an approved one cannot,
    # because its schedule is what the CFO signed for — so telling an approver
    # to refresh it would send them at a refusal. Say the right thing for the
    # state the version is actually in.
    approved = version.status == FORECAST_APPROVED
    staleness = source_staleness(session, project=project, version=version)
    if staleness.construction_is_stale:
        remedy = (
            "Withdraw the approval and prepare a forecast on the current one."
            if approved
            else "Rebase this forecast on the current one."
        )
        raise ConflictError(
            f"This forecast schedules construction forecast version "
            f"{staleness.pinned_construction_version_number}, but version "
            f"{staleness.active_construction_version_number} is now in force. Its "
            "monthly build schedule no longer matches what construction expects to "
            f"spend. {remedy}"
        )
    if staleness.customer_schedule_is_stale:
        remedy = (
            "Withdraw the approval and review the updated forecast — an approved "
            "version's schedule cannot be re-pinned under the signature it carries."
            if approved
            else "Refresh the customer snapshot and re-check the months."
        )
        raise ConflictError(
            "The buyer schedules governing this project have changed since this "
            f"forecast froze them. {remedy} A schedule silently re-read underneath "
            "an approver changes what they are approving."
        )
    unplaced = _unplaced_installments(session, project=project, version=version)
    if unplaced:
        detail = "; ".join(
            f"sale {row.sale_contract_id} instalment {row.sequence} ({row.label})"
            for row in unplaced[:5]
        )
        more = "" if len(unplaced) <= 5 else f" and {len(unplaced) - 5} more"
        raise ConflictError(
            f"{len(unplaced)} governing buyer instalment(s) carry cash this forecast "
            f"could not place in any month, because they have no date of any kind — "
            f"{detail}{more}. An instalment with no timing is not an instalment worth "
            "nothing: the money is contractually owed and the forecast is silently "
            "short of it, so every funding figure taken from this version would "
            "understate what the project is owed and overstate what it needs to "
            "raise. Give each one a contractual or forecast date, refresh the "
            "customer snapshot, and submit again."
        )
    failed = [
        check
        for check in construction_reconciliation(session, project=project, version=version)
        if not check.passed
    ]
    if failed:
        # The check's own words, not its two numbers: a coverage failure counts
        # cost codes and an amount failure compares money, and one format that
        # served both reported a missing code as "expected 0, scheduled 1".
        detail = " ".join(check.detail for check in failed[:3])
        more = "" if len(failed) <= 3 else f" ({len(failed) - 3} further failures.)"
        raise ConflictError(
            "This forecast's monthly construction schedule does not reconcile to the "
            f"construction forecast it is measured against. {detail}{more} Every cost "
            "code the construction forecast carries must appear here, and its months "
            "must total its remaining cost exactly."
        )


# --------------------------------------------------------------------------- #
# Forecast governance
# --------------------------------------------------------------------------- #


def submit_forecast(
    session: Session, *, project: Project, actor: ActorContext, version_id: uuid.UUID
) -> CashflowForecastVersion:
    """Put a draft forecast up for approval, having proved it still holds."""
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    if version.status != FORECAST_DRAFT:
        raise ConflictError("Only a draft cashflow forecast can be submitted.")
    _require_ready_for_governance(session, project=project, version=version)

    before = _snapshot(version, _FORECAST_FIELDS)
    version.status = FORECAST_SUBMITTED
    version.submitted_at = _now()
    version.submitted_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="cashflow.forecast_submitted",
        entity_type=ENTITY_FORECAST,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(version, _FORECAST_FIELDS),
    )
    return version


def approve_forecast(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    reason: str,
) -> CashflowForecastVersion:
    """Approve a submitted forecast. Never by the person who submitted it.

    The sources are re-proved here as well, and this is the gate that was
    missing. They were checked at submission and again at activation, so a
    construction forecast replaced in between could be signed for and only
    discovered at activation — the approval already recorded against a version
    everybody then had to withdraw. An approver should not be able to put their
    name to a basis that is known to have moved, and the cheapest place to say
    so is before the signature rather than after it.
    """
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    if version.status != FORECAST_SUBMITTED:
        raise ConflictError("Only a submitted cashflow forecast can be approved.")
    permissions.require_different_approver(actor, submitted_by_user_id=version.submitted_by_user_id)
    _require_ready_for_governance(session, project=project, version=version)

    before = _snapshot(version, _FORECAST_FIELDS)
    version.status = FORECAST_APPROVED
    version.approved_at = _now()
    version.approved_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="cashflow.forecast_approved",
        entity_type=ENTITY_FORECAST,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(version, _FORECAST_FIELDS),
    )
    return version


#: A version that was never signed for, and one whose signature was taken back.
#: An auditor reading the history has to be able to tell those apart.
_REJECTED = "cashflow.forecast_rejected"
_WITHDRAWN = "cashflow.forecast_approval_withdrawn"


def reject_forecast(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    reason: str,
) -> CashflowForecastVersion:
    """Refuse a submitted forecast, or withdraw an approval that cannot be acted on.

    Both close a version that will not proceed, and both are the CFO's to take,
    so they are one act with two meanings rather than two code paths.

    Withdrawal exists because approval is not the last gate. Activation re-proves
    the sources, and a construction forecast activated while this one waited for
    a signature makes it unactivatable — while the one-open-forecast rule counts
    it as the project's open version, and only a draft may be edited. Without a
    way out of *approved*, a project in that state could neither activate what it
    had nor prepare anything else: the version would sit in the open slot forever
    and cashflow forecasting would stop for that development.

    The approval itself is not erased. ``approved_at`` and ``approved_by_user_id``
    stay exactly as they were, because the CFO did approve it and the record of
    that is not ours to revise; the withdrawal is a later event recorded on top,
    so the audit reads submitted → approved → withdrawn rather than pretending
    the middle step never happened.
    """
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    withdrawing = version.status == FORECAST_APPROVED
    if version.status not in (FORECAST_SUBMITTED, FORECAST_APPROVED):
        raise ConflictError(
            "Only a submitted or approved cashflow forecast can be rejected. An "
            "active or superseded version is in the record as something the "
            "company reported, and a rejected one is already closed."
        )
    permissions.require_different_approver(actor, submitted_by_user_id=version.submitted_by_user_id)

    before = _snapshot(version, _FORECAST_FIELDS)
    version.status = FORECAST_REJECTED
    version.rejected_at = _now()
    version.rejected_by_user_id = actor.user_id
    version.rejection_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        # Named apart on purpose: an auditor reading the history needs to see
        # that a signature was given and later taken back, which is a different
        # event from a version that was never approved at all.
        action=_WITHDRAWN if withdrawing else _REJECTED,
        entity_type=ENTITY_FORECAST,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(version, _FORECAST_FIELDS),
    )
    return version


def activate_forecast(
    session: Session, *, project: Project, actor: ActorContext, version_id: uuid.UUID
) -> CashflowForecastVersion:
    """Put an approved forecast in force, superseding the one before it.

    The sources are re-proved here as well as at submission. A construction
    forecast activated while this one waited for a signature would leave the
    company funding itself against a build schedule nobody currently expects.
    """
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    if version.status != FORECAST_APPROVED:
        raise ConflictError("Only an approved cashflow forecast can be activated.")
    if version.currency_id != project.base_currency_id:
        raise ConflictError(
            "This forecast was prepared in a currency the project no longer accounts "
            "in. Prepare a revision in the project's base currency."
        )
    _require_ready_for_governance(session, project=project, version=version)

    standing = active_forecast(session, project_id=project.id)
    if standing is not None:
        superseded_before = _snapshot(standing, _FORECAST_FIELDS)
        standing.status = FORECAST_SUPERSEDED
        standing.superseded_at = _now()
        _flush(session)
        record_event(
            session,
            action="cashflow.forecast_superseded",
            entity_type=ENTITY_FORECAST,
            entity_id=standing.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            before=superseded_before,
            after=_snapshot(standing, _FORECAST_FIELDS),
        )

    before = _snapshot(version, _FORECAST_FIELDS)
    version.status = FORECAST_ACTIVE
    version.activated_at = _now()
    version.activated_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="cashflow.forecast_activated",
        entity_type=ENTITY_FORECAST,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(version, _FORECAST_FIELDS),
    )
    return version


# --------------------------------------------------------------------------- #
# Forecast lines
# --------------------------------------------------------------------------- #


def _require_editable(version: CashflowForecastVersion) -> None:
    if version.status != FORECAST_DRAFT:
        raise ConflictError(
            "Only a draft cashflow forecast can be edited. A submitted or governed "
            "forecast is what somebody reviewed, and editing it in place would make "
            "the review meaningless."
        )


def set_forecast_line(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    period_month: date,
    source_kind: str,
    category: str,
    amount: Decimal,
    flow_direction: str | None = None,
    phase_id: uuid.UUID | None = None,
    construction_cost_code_id: uuid.UUID | None = None,
    note: str | None = None,
) -> CashflowForecastLine:
    """Write one month's expected movement, replacing any line with the same key.

    The natural key is the version, the month, the source kind, the category and
    the cost code — one figure per cell. Upsert rather than append, because a
    preparer correcting April's construction spend means "April is this now", and
    an append would silently double it.

    ``flow_direction`` is derived where the source kind fixes it, and only a
    financing line has to state it — and even then the database checks it against
    the movement type, because an equity contribution being cash in is a fact
    rather than a choice on a form.
    """
    del actor
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    _require_editable(version)

    if source_kind not in FORECAST_SOURCE_KINDS:
        raise ValidationError(f"{source_kind} is not a cashflow forecast source kind.")
    month = month_of(period_month)
    if not (version.forecast_start_month <= month <= version.forecast_end_month):
        raise ValidationError(
            f"{month} falls outside this forecast's horizon of "
            f"{version.forecast_start_month} to {version.forecast_end_month}. Extend "
            "the horizon, or the month would be invisible in every monthly report."
        )
    direction = _direction_for(source_kind=source_kind, category=category, stated=flow_direction)
    # The database holds this too, but a CHECK violation reaches the caller as a
    # 500 naming a constraint. The rule is worth stating in words at the boundary
    # that can still explain what to do about it.
    if source_kind == SOURCE_CONSTRUCTION and construction_cost_code_id is None:
        raise ValidationError(
            "A construction forecast line has to name the cost code it schedules. "
            "Without one there is nothing to reconcile against the construction "
            "forecast's remaining cost, and the month would be unattributable."
        )
    if source_kind != SOURCE_CONSTRUCTION and construction_cost_code_id is not None:
        raise ValidationError(
            f"A {source_kind} line does not belong to a construction cost code. "
            "Only the construction schedule is reconciled code by code."
        )

    existing = session.scalars(
        select(CashflowForecastLine).where(
            CashflowForecastLine.forecast_version_id == version.id,
            CashflowForecastLine.period_month == month,
            CashflowForecastLine.source_kind == source_kind,
            CashflowForecastLine.category == category,
            CashflowForecastLine.construction_cost_code_id.is_not_distinct_from(
                construction_cost_code_id
            ),
            CashflowForecastLine.phase_id.is_not_distinct_from(phase_id),
        )
    ).first()
    if existing is None:
        existing = CashflowForecastLine(
            project_id=project.id,
            forecast_version_id=version.id,
            period_month=month,
            flow_direction=direction,
            category=category,
            source_kind=source_kind,
            amount=money(amount),
            phase_id=phase_id,
            construction_cost_code_id=construction_cost_code_id,
            note=(note or "").strip() or None,
        )
        session.add(existing)
    else:
        existing.flow_direction = direction
        existing.amount = money(amount)
        existing.note = (note or "").strip() or None
    _flush(session)
    return existing


def _direction_for(*, source_kind: str, category: str, stated: str | None) -> str:
    """Which way a forecast line's cash moves, decided by what it is.

    Only financing can go either way, and even there the type decides. Letting a
    preparer state the direction on a construction line would allow a build cost
    to be typed as an inflow, which no report would catch because the total would
    still balance.
    """
    if source_kind in (SOURCE_CONSTRUCTION, SOURCE_DEVELOPMENT):
        return FLOW_OUTFLOW
    if source_kind == SOURCE_UNSOLD_CUSTOMER:
        return FLOW_INFLOW
    if category not in FINANCING_TYPES:
        raise ValidationError(f"{category} is not a financing movement type.")
    derived = FLOW_INFLOW if category in FINANCING_INFLOW_TYPES else FLOW_OUTFLOW
    if stated is not None and stated != derived:
        raise ValidationError(
            f"A {category} is cash {derived[:-4]}, not {stated[:-4]}. The direction "
            "follows from the movement type."
        )
    return derived


def remove_forecast_line(
    session: Session, *, project: Project, version_id: uuid.UUID, line_id: uuid.UUID
) -> None:
    """Drop a line from a draft forecast."""
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    _require_editable(version)
    line = session.scalars(
        select(CashflowForecastLine).where(
            CashflowForecastLine.id == line_id,
            CashflowForecastLine.forecast_version_id == version.id,
        )
    ).first()
    if line is None:
        raise NotFoundError("Forecast line not found.")
    session.delete(line)
    _flush(session)


def forecast_lines(session: Session, *, version_id: uuid.UUID) -> list[CashflowForecastLine]:
    """One forecast version's lines, in month then category order."""
    return list(
        session.scalars(
            select(CashflowForecastLine)
            .where(CashflowForecastLine.forecast_version_id == version_id)
            .order_by(
                CashflowForecastLine.period_month,
                CashflowForecastLine.source_kind,
                CashflowForecastLine.category,
            )
        )
    )


# --------------------------------------------------------------------------- #
# Cash this module owns
# --------------------------------------------------------------------------- #


def _next_reference(
    session: Session,
    *,
    project_id: uuid.UUID,
    model: type[CashflowDevelopmentMovement] | type[CashflowFinancingMovement],
    prefix: str,
) -> str:
    """The next project-scoped human reference, ``DEV-000001``.

    A label for people to quote on a bank instruction, never identity. Derived
    under the project lock every caller already holds, so two concurrent records
    cannot take the same number.
    """
    highest = session.scalars(
        select(func.count()).select_from(model).where(model.project_id == project_id)
    ).first()
    return f"{prefix}-{(highest or 0) + 1:06d}"


def _confirm_movement(
    session: Session,
    *,
    row: CashMovement,
    actor: ActorContext,
    fields: tuple[str, ...],
    entity_type: str,
    action: str,
    noun: str,
) -> None:
    """Turn a recorded claim into cash, by somebody other than the recorder.

    The identifier comparison is the control. A role check would let one user
    holding Finance and Approver / CFO instruct a payment and confirm it, which
    is one person moving the company's money and calling it two.
    """
    if row.status != MOVEMENT_RECORDED:
        raise ConflictError(f"Only a recorded {noun} can be confirmed.")
    permissions.require_different_confirmer(actor, recorded_by_user_id=row.recorded_by_user_id)
    before = _snapshot(row, fields)
    row.status = MOVEMENT_CONFIRMED
    row.confirmed_at = _now()
    row.confirmed_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action=action,
        entity_type=entity_type,
        entity_id=row.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(row, fields),
    )
    return row


def _reverse_movement(
    session: Session,
    *,
    row: CashMovement,
    actor: ActorContext,
    reason: str,
    fields: tuple[str, ...],
    entity_type: str,
    action: str,
    noun: str,
) -> None:
    """Withdraw a movement from the current position without erasing it.

    A reversal is not a delete and not an edit. The row stays, carrying who
    withdrew it and why, and every historical read taken before the reversal
    still counts it — because it was standing then, and a forecast approved with
    it inside must go on saying what it said.
    """
    if row.status not in (MOVEMENT_RECORDED, MOVEMENT_CONFIRMED):
        raise ConflictError(f"This {noun} has already been reversed.")
    before = _snapshot(row, fields)
    row.status = MOVEMENT_REVERSED
    row.reversed_at = _now()
    row.reversed_by_user_id = actor.user_id
    row.reversal_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action=action,
        entity_type=entity_type,
        entity_id=row.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(row, fields),
    )
    return row


def _lock_row(
    session: Session,
    *,
    model: type[CashMovement],
    project_id: uuid.UUID,
    row_id: uuid.UUID,
    missing: Callable[[], NotFoundError],
) -> CashMovement:
    row = session.scalars(
        select(model)
        .where(model.id == row_id, model.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise missing()
    return row


# --------------------------------------------------------------------------- #
# Development movements
# --------------------------------------------------------------------------- #


def list_development_movements(
    session: Session, *, project: Project
) -> list[CashflowDevelopmentMovement]:
    """The project's own development cash, newest first."""
    return list(
        session.scalars(
            select(CashflowDevelopmentMovement)
            .where(CashflowDevelopmentMovement.project_id == project.id)
            .order_by(CashflowDevelopmentMovement.movement_date.desc())
        )
    )


def record_development_movement(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    category: str,
    amount: Decimal,
    movement_date: date,
    currency_id: uuid.UUID,
    value_date: date | None = None,
    phase_id: uuid.UUID | None = None,
    counterparty_reference: str | None = None,
    invoice_reference: str | None = None,
    bank_reference: str | None = None,
    evidence_reference: str | None = None,
    notes: str | None = None,
) -> CashflowDevelopmentMovement:
    """Record project cash the platform has no other record of. Not yet paid.

    The category set has no construction entry, deliberately. Construction cash
    is PR-MVP-09's and is read from there; a category here that could hold one
    would let the same disbursement be recorded twice with nothing to detect it,
    and the project would report a build that cost double.
    """
    lock_project(session, project.id)
    if category not in DEVELOPMENT_CATEGORIES:
        raise ValidationError(
            f"{category} is not a development category. Construction cash is not "
            "recorded here: it belongs to the contract it was paid against."
        )
    _require_project_currency(session, project=project, currency_id=currency_id)
    if movement_date > business_today():
        raise ValidationError(
            "A movement is a record of something that happened. It cannot be dated in the future."
        )
    movement = CashflowDevelopmentMovement(
        project_id=project.id,
        movement_reference=_next_reference(
            session, project_id=project.id, model=CashflowDevelopmentMovement, prefix="DEV"
        ),
        category=category,
        amount=money(amount),
        currency_id=currency_id,
        movement_date=movement_date,
        value_date=value_date,
        phase_id=phase_id,
        counterparty_reference=(counterparty_reference or "").strip() or None,
        invoice_reference=(invoice_reference or "").strip() or None,
        bank_reference=(bank_reference or "").strip() or None,
        evidence_reference=(evidence_reference or "").strip() or None,
        notes=(notes or "").strip() or None,
        status=MOVEMENT_RECORDED,
        recorded_by_user_id=actor.user_id,
    )
    session.add(movement)
    _flush(session)
    record_event(
        session,
        action="cashflow.development_movement_recorded",
        entity_type=ENTITY_DEVELOPMENT,
        entity_id=movement.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(movement, _DEVELOPMENT_FIELDS),
    )
    return movement


def confirm_development_movement(
    session: Session, *, project: Project, actor: ActorContext, movement_id: uuid.UUID
) -> CashflowDevelopmentMovement:
    """Confirm that development cash actually left. This is the moment it counts."""
    lock_project(session, project.id)
    movement = _lock_row(
        session,
        model=CashflowDevelopmentMovement,
        project_id=project.id,
        row_id=movement_id,
        missing=permissions.movement_not_found,
    )
    _confirm_movement(
        session,
        row=movement,
        actor=actor,
        fields=_DEVELOPMENT_FIELDS,
        entity_type=ENTITY_DEVELOPMENT,
        action="cashflow.development_movement_confirmed",
        noun="development movement",
    )
    return movement


def reverse_development_movement(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    movement_id: uuid.UUID,
    reason: str,
) -> CashflowDevelopmentMovement:
    """Withdraw a development movement from the current cash position."""
    lock_project(session, project.id)
    movement = _lock_row(
        session,
        model=CashflowDevelopmentMovement,
        project_id=project.id,
        row_id=movement_id,
        missing=permissions.movement_not_found,
    )
    _reverse_movement(
        session,
        row=movement,
        actor=actor,
        reason=reason,
        fields=_DEVELOPMENT_FIELDS,
        entity_type=ENTITY_DEVELOPMENT,
        action="cashflow.development_movement_reversed",
        noun="development movement",
    )
    return movement


# --------------------------------------------------------------------------- #
# Financing movements
# --------------------------------------------------------------------------- #


def list_financing_movements(
    session: Session, *, project: Project
) -> list[CashflowFinancingMovement]:
    """The project's equity and debt cash, newest first."""
    return list(
        session.scalars(
            select(CashflowFinancingMovement)
            .where(CashflowFinancingMovement.project_id == project.id)
            .order_by(CashflowFinancingMovement.movement_date.desc())
        )
    )


def record_financing_movement(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    movement_type: str,
    amount: Decimal,
    movement_date: date,
    currency_id: uuid.UUID,
    value_date: date | None = None,
    counterparty_reference: str | None = None,
    facility_reference: str | None = None,
    bank_reference: str | None = None,
    evidence_reference: str | None = None,
    notes: str | None = None,
) -> CashflowFinancingMovement:
    """Record equity or debt cash. Only where cash genuinely moves.

    A facility signed is not a drawdown and a guarantee issued is not cash
    posted. Instruments with no cash movement have no row here and appear in no
    position, which is the boundary that keeps this a cash ledger rather than
    the beginning of a treasury system.
    """
    lock_project(session, project.id)
    if movement_type not in FINANCING_TYPES:
        raise ValidationError(f"{movement_type} is not a financing movement type.")
    _require_project_currency(session, project=project, currency_id=currency_id)
    if movement_date > business_today():
        raise ValidationError(
            "A movement is a record of something that happened. It cannot be dated in the future."
        )
    movement = CashflowFinancingMovement(
        project_id=project.id,
        movement_reference=_next_reference(
            session, project_id=project.id, model=CashflowFinancingMovement, prefix="FIN"
        ),
        movement_type=movement_type,
        flow_direction=(FLOW_INFLOW if movement_type in FINANCING_INFLOW_TYPES else FLOW_OUTFLOW),
        amount=money(amount),
        currency_id=currency_id,
        movement_date=movement_date,
        value_date=value_date,
        counterparty_reference=(counterparty_reference or "").strip() or None,
        facility_reference=(facility_reference or "").strip() or None,
        bank_reference=(bank_reference or "").strip() or None,
        evidence_reference=(evidence_reference or "").strip() or None,
        notes=(notes or "").strip() or None,
        status=MOVEMENT_RECORDED,
        recorded_by_user_id=actor.user_id,
    )
    session.add(movement)
    _flush(session)
    record_event(
        session,
        action="cashflow.financing_movement_recorded",
        entity_type=ENTITY_FINANCING,
        entity_id=movement.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(movement, _FINANCING_FIELDS),
    )
    return movement


def confirm_financing_movement(
    session: Session, *, project: Project, actor: ActorContext, movement_id: uuid.UUID
) -> CashflowFinancingMovement:
    """Confirm that financing cash actually moved."""
    lock_project(session, project.id)
    movement = _lock_row(
        session,
        model=CashflowFinancingMovement,
        project_id=project.id,
        row_id=movement_id,
        missing=permissions.movement_not_found,
    )
    _confirm_movement(
        session,
        row=movement,
        actor=actor,
        fields=_FINANCING_FIELDS,
        entity_type=ENTITY_FINANCING,
        action="cashflow.financing_movement_confirmed",
        noun="financing movement",
    )
    return movement


def reverse_financing_movement(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    movement_id: uuid.UUID,
    reason: str,
) -> CashflowFinancingMovement:
    """Withdraw a financing movement from the current cash position."""
    lock_project(session, project.id)
    movement = _lock_row(
        session,
        model=CashflowFinancingMovement,
        project_id=project.id,
        row_id=movement_id,
        missing=permissions.movement_not_found,
    )
    _reverse_movement(
        session,
        row=movement,
        actor=actor,
        reason=reason,
        fields=_FINANCING_FIELDS,
        entity_type=ENTITY_FINANCING,
        action="cashflow.financing_movement_reversed",
        noun="financing movement",
    )
    return movement


def _require_project_currency(
    session: Session, *, project: Project, currency_id: uuid.UUID
) -> None:
    """One denomination throughout. The MVP has no exchange rate and says so.

    Refused at entry rather than converted, relabelled or quietly excluded. A
    conversion needs a rate this platform does not hold; a relabel is a lie; and
    an exclusion produces a cash position that is silently missing a
    transaction — the worst of the three, because nothing on the screen says so.
    """
    if currency_id != project.base_currency_id:
        base = session.get(Currency, project.base_currency_id)
        raise ValidationError(
            f"This project accounts in {base.code if base else 'its base currency'}. "
            "A movement in another currency cannot enter its cash position: there is "
            "no exchange rate in this MVP, and converting one without a governed rate "
            "would invent the amount."
        )


# --------------------------------------------------------------------------- #
# Restricted cash
# --------------------------------------------------------------------------- #


def list_restrictions(session: Session, *, project: Project) -> list[CashflowReceiptRestriction]:
    """Every escrow restriction this project has recorded, newest first."""
    return list(
        session.scalars(
            select(CashflowReceiptRestriction)
            .where(CashflowReceiptRestriction.project_id == project.id)
            .order_by(CashflowReceiptRestriction.recorded_at.desc())
        )
    )


def record_restriction(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    receipt_id: uuid.UUID,
    restricted_amount: Decimal,
    reason: str,
    source_reference: str | None = None,
    notes: str | None = None,
) -> CashflowReceiptRestriction:
    """Mark part of a confirmed buyer receipt as cash the developer may not spend.

    Attached to a **confirmed** receipt only. Restricting money that has not
    arrived would take it out of a usable balance it was never in, and the
    project would report itself short of cash it had never received.
    """
    lock_project(session, project.id)
    receipt = session.scalars(
        select(CollectionReceipt).where(
            CollectionReceipt.id == receipt_id, CollectionReceipt.project_id == project.id
        )
    ).first()
    if receipt is None:
        raise NotFoundError("Receipt not found.")
    if receipt.status != MOVEMENT_CONFIRMED:
        raise ConflictError(
            "Only confirmed buyer cash can be restricted. A receipt nobody has "
            "confirmed is not yet money in the bank, so there is nothing to hold "
            "back."
        )
    standing = session.scalars(
        select(CashflowReceiptRestriction).where(
            CashflowReceiptRestriction.receipt_id == receipt.id,
            CashflowReceiptRestriction.status.in_((MOVEMENT_RECORDED, MOVEMENT_CONFIRMED)),
        )
    ).first()
    if standing is not None:
        # A partial unique index enforces this, but a constraint violation
        # reaches the caller as a 500 naming an index. The rule is one a person
        # can act on — release or reverse what is already held — and it is worth
        # saying so at the boundary that can still explain it.
        raise ConflictError(
            f"{receipt.receipt_number} already has {standing.restricted_amount} held "
            "against it. One escrow per receipt: two would each be measured against "
            "the transfer on its own and could together hold back more than arrived. "
            "Release or reverse the standing one first."
        )
    amount = money(restricted_amount)
    if amount > receipt.amount:
        raise ValidationError(
            f"{amount} cannot be restricted out of a receipt of {receipt.amount}. "
            "An escrow cannot hold more than the transfer it was taken from."
        )
    restriction = CashflowReceiptRestriction(
        project_id=project.id,
        receipt_id=receipt.id,
        restricted_amount=amount,
        reason=reason.strip(),
        source_reference=(source_reference or "").strip() or None,
        notes=(notes or "").strip() or None,
        status=MOVEMENT_RECORDED,
        recorded_by_user_id=actor.user_id,
    )
    session.add(restriction)
    _flush(session)
    record_event(
        session,
        action="cashflow.restriction_recorded",
        entity_type=ENTITY_RESTRICTION,
        entity_id=restriction.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(restriction, _RESTRICTION_FIELDS),
    )
    return restriction


def confirm_restriction(
    session: Session, *, project: Project, actor: ActorContext, restriction_id: uuid.UUID
) -> CashflowReceiptRestriction:
    """Confirm that the cash really is held. Only then does it leave the usable pool."""
    lock_project(session, project.id)
    restriction = _lock_row(
        session,
        model=CashflowReceiptRestriction,
        project_id=project.id,
        row_id=restriction_id,
        missing=permissions.restriction_not_found,
    )
    _confirm_movement(
        session,
        row=restriction,
        actor=actor,
        fields=_RESTRICTION_FIELDS,
        entity_type=ENTITY_RESTRICTION,
        action="cashflow.restriction_confirmed",
        noun="restriction",
    )
    return restriction


def reverse_restriction(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    restriction_id: uuid.UUID,
    reason: str,
) -> CashflowReceiptRestriction:
    """Withdraw a restriction, refusing while releases still stand against it.

    Reversing the restriction under a standing release would leave the release
    freeing money nothing was holding, and the restricted balance would close
    below zero — a position the calculator refuses to state and the reporting
    could not explain.
    """
    lock_project(session, project.id)
    restriction = _lock_row(
        session,
        model=CashflowReceiptRestriction,
        project_id=project.id,
        row_id=restriction_id,
        missing=permissions.restriction_not_found,
    )
    standing = session.scalars(
        select(func.count())
        .select_from(CashflowRestrictionRelease)
        .where(
            CashflowRestrictionRelease.restriction_id == restriction.id,
            CashflowRestrictionRelease.status.in_((MOVEMENT_RECORDED, MOVEMENT_CONFIRMED)),
        )
    ).first()
    if standing:
        raise ConflictError(
            f"{standing} release(s) still stand against this restriction. Reverse "
            "them first: a release against a restriction that no longer exists would "
            "free money nothing was holding."
        )
    _reverse_movement(
        session,
        row=restriction,
        actor=actor,
        reason=reason,
        fields=_RESTRICTION_FIELDS,
        entity_type=ENTITY_RESTRICTION,
        action="cashflow.restriction_reversed",
        noun="restriction",
    )
    return restriction


def released_against(
    session: Session, *, restriction_id: uuid.UUID, exclude_release_id: uuid.UUID | None = None
) -> Decimal:
    """What standing releases have already freed from one restriction."""
    conditions = [
        CashflowRestrictionRelease.restriction_id == restriction_id,
        CashflowRestrictionRelease.status.in_((MOVEMENT_RECORDED, MOVEMENT_CONFIRMED)),
    ]
    if exclude_release_id is not None:
        conditions.append(CashflowRestrictionRelease.id != exclude_release_id)
    total = session.scalars(
        select(func.coalesce(func.sum(CashflowRestrictionRelease.amount), 0)).where(*conditions)
    ).first()
    return money(total or ZERO)


def record_release(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    restriction_id: uuid.UUID,
    release_date: date,
    amount: Decimal,
    certification_reference: str | None = None,
    evidence_reference: str | None = None,
    notes: str | None = None,
) -> CashflowRestrictionRelease:
    """Free part of a restriction, under the restriction's own lock.

    The lock is the control, and it is the reason this cannot be done with a
    validator. Two operators each releasing 80 from a restriction of 100 would
    both read 100 available, both pass their own check and both write — leaving
    160 released against 100 held. Taking the restriction row for update makes
    them decide in sequence against committed state, so the second sees the
    first's release and is refused.
    """
    lock_project(session, project.id)
    restriction = _lock_row(
        session,
        model=CashflowReceiptRestriction,
        project_id=project.id,
        row_id=restriction_id,
        missing=permissions.restriction_not_found,
    )
    if restriction.status != MOVEMENT_CONFIRMED:
        raise ConflictError(
            "Only a confirmed restriction can be released. Money nobody has "
            "confirmed as held cannot be freed."
        )
    requested = money(amount)
    already = released_against(session, restriction_id=restriction.id)
    if already + requested > restriction.restricted_amount:
        raise ConflictError(
            f"Releasing {requested} would take total releases to "
            f"{already + requested} against {restriction.restricted_amount} "
            "restricted. An escrow cannot release more than it holds."
        )
    release = CashflowRestrictionRelease(
        project_id=project.id,
        restriction_id=restriction.id,
        release_date=release_date,
        amount=requested,
        certification_reference=(certification_reference or "").strip() or None,
        evidence_reference=(evidence_reference or "").strip() or None,
        notes=(notes or "").strip() or None,
        status=MOVEMENT_RECORDED,
        recorded_by_user_id=actor.user_id,
    )
    session.add(release)
    _flush(session)
    record_event(
        session,
        action="cashflow.release_recorded",
        entity_type=ENTITY_RELEASE,
        entity_id=release.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(release, _RELEASE_FIELDS),
    )
    return release


def confirm_release(
    session: Session, *, project: Project, actor: ActorContext, release_id: uuid.UUID
) -> CashflowRestrictionRelease:
    """Confirm a release, re-proving the ceiling under lock.

    Re-proved rather than trusted from when the release was recorded: another
    release against the same restriction may have been confirmed in between, and
    two recorded releases that each fitted on their own can exceed the
    restriction together.
    """
    lock_project(session, project.id)
    release = _lock_row(
        session,
        model=CashflowRestrictionRelease,
        project_id=project.id,
        row_id=release_id,
        missing=permissions.release_not_found,
    )
    restriction = _lock_row(
        session,
        model=CashflowReceiptRestriction,
        project_id=project.id,
        row_id=release.restriction_id,
        missing=permissions.restriction_not_found,
    )
    already = released_against(
        session, restriction_id=restriction.id, exclude_release_id=release.id
    )
    if already + release.amount > restriction.restricted_amount:
        raise ConflictError(
            f"Confirming this release would take total releases to "
            f"{already + release.amount} against {restriction.restricted_amount} "
            "restricted. Another release was confirmed against this restriction "
            "first."
        )
    _confirm_movement(
        session,
        row=release,
        actor=actor,
        fields=_RELEASE_FIELDS,
        entity_type=ENTITY_RELEASE,
        action="cashflow.release_confirmed",
        noun="release",
    )
    return release


def reverse_release(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    release_id: uuid.UUID,
    reason: str,
) -> CashflowRestrictionRelease:
    """Withdraw a release, putting the cash back into the restricted balance."""
    lock_project(session, project.id)
    release = _lock_row(
        session,
        model=CashflowRestrictionRelease,
        project_id=project.id,
        row_id=release_id,
        missing=permissions.release_not_found,
    )
    _reverse_movement(
        session,
        row=release,
        actor=actor,
        reason=reason,
        fields=_RELEASE_FIELDS,
        entity_type=ENTITY_RELEASE,
        action="cashflow.release_reversed",
        noun="release",
    )
    return release


# --------------------------------------------------------------------------- #
# Deriving the monthly position
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SourceRow:
    """One transaction behind a management figure, for the drill-down.

    A reference to the row that already exists, never a copy of it. Building a
    second table of "reporting transactions" would mean two records of one
    payment, and the moment somebody corrected one the dashboard and the ledger
    would disagree about a number that has one correct value.
    """

    source_type: str
    source_id: uuid.UUID
    period_month: date
    business_date: date
    amount: Decimal
    flow_direction: str
    category: str
    basis: str
    status: str
    display_reference: str

    #: True when the row knows only which month it belongs to, not which day.
    #: A forecast line is the only such source, and the distinction matters:
    #: every rule that asks "has this happened yet?" has to ask it of a date,
    #: and a month-grained row has to be told which day to answer for.
    month_grain: bool = False


@dataclass(frozen=True)
class MonthlyPosition:
    """One month of the cash bridge, on both the total and the usable basis."""

    period_month: date
    #: ``PERIOD_CLOSED``, ``PERIOD_CURRENT`` or ``PERIOD_FUTURE``. The month the
    #: report was taken in is neither of the other two and must not be reported
    #: as either — see ``period_state``.
    period_state: str

    opening_total_cash: Decimal
    customer_scheduled_due: Decimal
    customer_actual_receipts: Decimal
    customer_forecast_receipts: Decimal
    financing_actual_inflows: Decimal
    financing_forecast_inflows: Decimal
    development_actual_outflows: Decimal
    development_forecast_outflows: Decimal
    construction_actual_payments: Decimal
    construction_forecast_payments: Decimal
    customer_refunds: Decimal
    financing_actual_outflows: Decimal
    financing_forecast_outflows: Decimal
    total_inflows: Decimal
    total_outflows: Decimal
    net_cashflow: Decimal
    closing_total_cash: Decimal

    opening_restricted_cash: Decimal
    newly_restricted_customer_cash: Decimal
    escrow_releases: Decimal
    closing_restricted_cash: Decimal

    opening_unrestricted_cash: Decimal
    usable_inflows: Decimal
    unrestricted_outflows: Decimal
    closing_unrestricted_cash: Decimal
    funding_gap: Decimal


#: The source types a drill-down row can name. Each is a row in the module that
#: governs it, and this module holds none of them.
SOURCE_RECEIPT = "collection_receipt"
SOURCE_REFUND = "collection_refund"
SOURCE_CONSTRUCTION_PAYMENT = "construction_payment"
SOURCE_DEVELOPMENT_MOVEMENT = "cashflow_development_movement"
SOURCE_FINANCING_MOVEMENT = "cashflow_financing_movement"
SOURCE_RESTRICTION = "cashflow_receipt_restriction"
SOURCE_RELEASE = "cashflow_restriction_release"
SOURCE_SCHEDULE = "payment_plan_installment"
SOURCE_FORECAST_LINE = "cashflow_forecast_line"

BASIS_ACTUAL = "actual"
BASIS_FORECAST = "forecast"
BASIS_SCHEDULED = "scheduled"

#: Availability moves rather than cash, so these two are never an inflow or an
#: outflow — they only decide how much of the cash already counted is spendable.
RESTRICTION_SOURCES = (SOURCE_RESTRICTION, SOURCE_RELEASE)

#: Where a month sits relative to the date the report was taken. There are three
#: of these and not two, which is the whole point of naming them.
PERIOD_CLOSED = "closed"
PERIOD_CURRENT = "current"
PERIOD_FUTURE = "future"

#: What a month's figures were assembled from, stated in the response. A closed
#: month is settled history and a future month is entirely expectation; the month
#: the report was taken in is both at once and needs a word of its own, because
#: calling it "actual" hides every payment still due before the month ends.
MONTH_BASIS_ACTUAL = "actual"
MONTH_BASIS_ACTUAL_AND_FORECAST = "actual_and_forecast"
MONTH_BASIS_FORECAST = "forecast"


def period_state(month: date, *, as_of: date) -> str:
    """Which of the three temporal states a month is in.

    The month the as-of date falls in is a **partial** month, and treating it as
    finished is the error this exists to prevent. A report taken on 3 April that
    calls April "actual" reports one working week of collections as the month's
    answer and drops every instalment due on the 15th — the figure is not merely
    incomplete, it is confidently wrong in the direction of a cash shortfall
    nobody will be able to reproduce a week later.
    """
    current = month_of(as_of)
    if month < current:
        return PERIOD_CLOSED
    if month == current:
        return PERIOD_CURRENT
    return PERIOD_FUTURE


def month_basis(state: str) -> str:
    """The word a month of the bridge reports itself under."""
    if state == PERIOD_CLOSED:
        return MONTH_BASIS_ACTUAL
    if state == PERIOD_CURRENT:
        return MONTH_BASIS_ACTUAL_AND_FORECAST
    return MONTH_BASIS_FORECAST


def counts_as_cash(row: SourceRow, *, as_of: date) -> bool:
    """**The** rule that decides whether a source row is cash in a report.

    One rule, used by the monthly bridge, the cash position, the funding windows,
    the drill-down, the NPV and the equity IRR. Every one of those answers the
    same question — *does this row belong in the cash this report is about?* — and
    the version of this platform that answered it in six places answered it two
    different ways: the bridge zeroed a month's whole forecast series the moment
    the month began, while Returns swept every equity row it could find whatever
    its basis. The two numbers on one screen described different projects.

    The rule itself:

    A **scheduled** row is the contractual memo series — what buyers owe and
    when it falls due — and is never cash. It is reported beside the cash so a
    reader can see collection running ahead of or behind the contract.

    An **actual** row is a confirmed movement and is always cash. It was already
    filtered for what was standing at the cutoff when it was collected.

    A **forecast** row is cash only while it is still ahead of the cutoff. A
    dated row — a buyer instalment out of the frozen schedule — answers on its
    own date, which is why an instalment due on the 20th survives a report taken
    on the 3rd of the same month. A **month-grained** row has no date to answer
    with, and the MVP rule is that a forecast line stated for the as-of month is
    *the remainder of that month*: whatever the preparer expected to move, minus
    nothing, because a preparer writing April's figure in April is writing what
    is still to come. Months already closed are answered by their actuals.
    """
    if row.basis == BASIS_SCHEDULED:
        return False
    if row.basis == BASIS_ACTUAL:
        return True
    if row.month_grain:
        return row.period_month >= month_of(as_of)
    return row.business_date > as_of


def window_date(row: SourceRow, *, as_of: date) -> date:
    """The day a row is projected on inside a literal date window.

    A month-grained forecast has no day, so it is placed on the earliest day it
    could still occur — the day after the cutoff for the current month, the first
    of the month for any later one. That is a placement, not a distribution: this
    MVP does not know how a month's figure is spread across its days, and
    pretending to would put a precision on the funding requirement that the input
    does not carry. Stated once here so the bridge, the windows and any future
    reader place it the same way.
    """
    if not row.month_grain:
        return row.business_date
    return max(row.period_month, as_of + timedelta(days=1))


def opening_anchor_month(version: CashflowForecastVersion | None) -> date | None:
    """The month a governed opening cash balance is stated as at, if there is one.

    An opening balance is a **statement about one moment**: on the first of this
    month the project held so much cash, so much of it restricted. Every figure
    downstream is that balance plus what moved since.

    Which makes running the bridge backwards from it incoherent. The transactions
    of the months before the anchor are not additional to the opening balance —
    they are what produced it. Replaying them through it counts each of them
    twice, and the error grows with how much history the project has, so the
    oldest and most valuable projects report the worst numbers. The earlier
    version of this module did exactly that: it quietly moved the series start
    back to the earliest transaction it could find while keeping the governed
    opening balance at its stated value.

    So the anchor is immutable and the bridge begins there. The pre-opening
    transactions are not lost — they stay in the drill-down and in the modules
    that own them — they are simply not replayed through a balance that already
    contains them.

    A project with no forecast in force has no governed opening balance at all
    (it opens at zero), so there is nothing to anchor and the series may begin
    wherever its history does.
    """
    return version.forecast_start_month if version is not None else None


def _standing_rows(
    session: Session,
    *,
    model: type[CashMovement],
    project_id: uuid.UUID,
    as_of: date | None,
) -> list[ColumnElement[bool]]:
    """Conditions for cash this module owns, now or at a historical cutoff."""
    return [
        model.project_id == project_id,
        *standing_conditions(
            status=model.status,
            confirmed_at=model.confirmed_at,
            reversed_at=model.reversed_at,
            as_of=as_of,
        ),
    ]


def offset_unapplied_cash(
    rows: Sequence[CashflowCustomerScheduleSnapshot], unapplied: dict[uuid.UUID, Decimal]
) -> dict[uuid.UUID, Decimal]:
    """Reduce a forward schedule by cash already received against the same sale.

    The double-count this exists to prevent is easy to miss and expensive. A
    confirmed receipt of 80 is already reported as cash that arrived. If the
    three 100 instalments it will eventually be applied to also stay in the
    forward forecast at 300, the forecast says 380 will have been collected when
    the true figure is 300.

    The offset is deterministic — earliest expected date first, then sequence —
    so two readers of the same version get the same months. Nothing is written:
    the operator's allocations are theirs, and a forecast that quietly applied
    cash to instalments would be making an accounting entry to tidy a chart.
    """
    remaining = dict(unapplied)
    adjusted: dict[uuid.UUID, Decimal] = {}
    for row in sorted(rows, key=lambda item: (item.chosen_forecast_date, item.amount)):
        credit = remaining.get(row.sale_contract_id, ZERO)
        if credit <= ZERO:
            adjusted[row.installment_id] = money(row.amount)
            continue
        applied = min(credit, row.amount)
        remaining[row.sale_contract_id] = money(credit - applied)
        adjusted[row.installment_id] = money(row.amount - applied)
    return adjusted


#: What a forecast line and an actual movement have to agree on before the one
#: can be said to have happened as the other. Deliberately narrow: an offset at
#: the wrong grain quietly cancels an expectation nobody has met.
GRAIN_CONSTRUCTION = "construction_cost_code"
GRAIN_DEVELOPMENT = "development_category"
GRAIN_FINANCING = "financing_type"


def _forecast_grain(line: CashflowForecastLine) -> tuple[str, object, object] | None:
    """The key an actual movement must match to have met this line's expectation.

    ``None`` for an unsold-customer line, and that is the interesting case. Such
    a line is Finance's expectation of cash from units nobody has sold yet, and
    no receipt in the system carries a link back to it — a buyer who signs next
    month pays against a contract and a payment plan, and that cash reaches the
    forecast through the schedule snapshot, not through this line. Offsetting it
    against ordinary contracted receipts would cancel an expectation about
    unsold stock using cash from sold stock, which is two different questions
    answered with one number.
    """
    if line.source_kind == SOURCE_CONSTRUCTION:
        return (GRAIN_CONSTRUCTION, line.construction_cost_code_id, None)
    if line.source_kind == SOURCE_DEVELOPMENT:
        return (GRAIN_DEVELOPMENT, line.category, line.phase_id)
    if line.source_kind == SOURCE_FINANCING:
        return (GRAIN_FINANCING, line.category, line.flow_direction)
    return None


def _post_cutoff_actuals(
    session: Session,
    *,
    project: Project,
    version: CashflowForecastVersion,
    as_of: date,
) -> tuple[dict[tuple[date, str, object, object], Decimal], dict[date, Decimal]]:
    """Cash that has moved since the forecast was written, at the grain it was written on.

    Only movements **after** the version's own cutoff. A payment the preparer
    could already see when they wrote the figure is inside the figure: the
    remaining expectation they stated was what was left *after* it, and
    subtracting it again would halve a forecast that was already correct.

    Returns the matched pool and, separately, construction cash no cost code can
    be named for — an advance, or cash not yet allocated to an invoice. That
    money left the bank and has to reduce *something*, or the month reports it
    twice; it is kept apart here so the place that spreads it says so out loud.
    """
    cutoff = version.as_of_date
    matched: dict[tuple[date, str, object, object], Decimal] = {}
    unattributed: dict[date, Decimal] = {}

    def add(key: tuple[date, str, object, object], amount: Decimal) -> None:
        matched[key] = money(matched.get(key, ZERO) + amount)

    for payment in construction_service.cashflow_payment_rows(
        session, project_id=project.id, as_of=as_of
    ):
        if payment.business_date <= cutoff:
            continue
        month = month_of(payment.business_date)
        for cost_code_id, amount in payment.by_cost_code.items():
            add((month, GRAIN_CONSTRUCTION, cost_code_id, None), amount)
        if payment.unattributed_amount > ZERO:
            unattributed[month] = money(unattributed.get(month, ZERO) + payment.unattributed_amount)

    for movement in session.scalars(
        select(CashflowDevelopmentMovement).where(
            *_standing_rows(
                session, model=CashflowDevelopmentMovement, project_id=project.id, as_of=as_of
            ),
            CashflowDevelopmentMovement.movement_date > cutoff,
        )
    ):
        add(
            (
                month_of(movement.movement_date),
                GRAIN_DEVELOPMENT,
                movement.category,
                movement.phase_id,
            ),
            money(movement.amount),
        )

    for movement in session.scalars(
        select(CashflowFinancingMovement).where(
            *_standing_rows(
                session, model=CashflowFinancingMovement, project_id=project.id, as_of=as_of
            ),
            CashflowFinancingMovement.movement_date > cutoff,
        )
    ):
        add(
            (
                month_of(movement.movement_date),
                GRAIN_FINANCING,
                movement.movement_type,
                movement.flow_direction,
            ),
            money(movement.amount),
        )
    return matched, unattributed


def forecast_remainders(
    session: Session,
    *,
    project: Project,
    version: CashflowForecastVersion,
    as_of: date,
) -> dict[uuid.UUID, Decimal]:
    """What is still expected on each forecast line, after what has already happened.

    Cash happens once. The platform already enforces that for buyer receipts —
    a confirmed receipt leaves the forward schedule by exactly its amount — and
    this is the same rule for the figures Finance writes by hand.

    A September line of 1,000,000 is the spend expected **for September, at the
    moment the forecast was cut**. When 300,000 of it is paid on the 10th, a
    live report of September is 300,000 that has gone and 700,000 still to go.
    Reporting 300,000 actual *and* 1,000,000 forecast claims 1,300,000, and does
    it on no evidence at all: nobody forecast a further million after paying the
    first three hundred thousand. The governed figure is not touched — the
    forecast file still says 1,000,000, because that is what was approved — this
    is only how a projection reads it.

    Matching is by grain and never by anything looser. Construction offsets at
    the cost code the documents attribute the payment to; development at the
    category, and at the phase where the line names one; financing at the
    movement type and its direction. Cash that matches no line is not spread
    around looking for one — with the single exception below, which is spread
    deliberately and says so.

    A remainder never goes negative. Spending more than was forecast does not
    create expected cash; the overrun belongs to the variance and accuracy
    layer, which reports it as an overrun rather than quietly enlarging the
    forecast.
    """
    lines = forecast_lines(session, version_id=version.id)
    matched, unattributed = _post_cutoff_actuals(
        session, project=project, version=version, as_of=as_of
    )
    remaining = {line.id: money(line.amount) for line in lines}

    # A phase-scoped line consumes before an unscoped one of the same category,
    # so a payment attributable to a phase is not absorbed by the general line
    # and then counted against the phase's as well.
    for line in sorted(lines, key=lambda item: (item.phase_id is None, str(item.id))):
        grain = _forecast_grain(line)
        if grain is None:
            continue
        kind, first, second = grain
        keys = [(line.period_month, kind, first, second)]
        if kind == GRAIN_DEVELOPMENT and line.phase_id is None:
            # An unscoped development line stands for the category across the
            # whole project, so it answers for any phase's spend on it.
            keys = sorted(
                key
                for key in matched
                if key[0] == line.period_month and key[1] == kind and key[2] == first
            )
        for key in keys:
            available = matched.get(key, ZERO)
            if available <= ZERO:
                continue
            taken = min(available, remaining[line.id])
            matched[key] = money(available - taken)
            remaining[line.id] = money(remaining[line.id] - taken)

    # Construction cash with no cost code — an advance, or cash not yet
    # allocated — still left the bank. Spreading it across what the month still
    # expects, in proportion to what each code has left, is the only reading
    # that keeps the month's total honest: leaving it out would report the
    # advance and the whole original forecast, which is the double count this
    # function exists to prevent.
    for month, pool in unattributed.items():
        codes = [
            line
            for line in lines
            if line.source_kind == SOURCE_CONSTRUCTION
            and line.period_month == month
            and remaining[line.id] > ZERO
        ]
        total = calculator.total(remaining[line.id] for line in codes)
        if not codes or total <= ZERO:
            continue
        spread = min(pool, total)
        running = ZERO
        for index, line in enumerate(sorted(codes, key=lambda item: str(item.id))):
            share = (
                money(spread - running)
                if index == len(codes) - 1
                else money(spread * remaining[line.id] / total)
            )
            running = money(running + share)
            remaining[line.id] = money(max(ZERO, remaining[line.id] - share))
    return remaining


def collect_source_rows(
    session: Session,
    *,
    project: Project,
    version: CashflowForecastVersion | None,
    as_of: date,
) -> list[SourceRow]:
    """Every transaction and forecast line that could contribute to a figure.

    Assembled once and reused by the monthly bridge, the drill-down, the
    reconciliation and the export, so the four cannot disagree. A dashboard
    saying 5,420,000 and an export saying 5,419,999 is a failed control, and the
    only way to be sure they match is for them to be the same list.

    This is the **register**: everything that was standing at the cutoff, on
    whichever basis it carries. Which of these rows is cash *in a given report*
    is not decided here — it is decided once, by ``counts_as_cash``, at every
    place that adds them up. Deciding it here as well is how the two answers
    started to differ.
    """
    rows: list[SourceRow] = []

    for receipt in collections_service.cashflow_receipt_rows(
        session, project_id=project.id, as_of=as_of
    ):
        rows.append(
            SourceRow(
                source_type=SOURCE_RECEIPT,
                source_id=receipt.id,
                period_month=month_of(receipt.business_date),
                business_date=receipt.business_date,
                amount=money(receipt.amount),
                flow_direction=FLOW_INFLOW,
                category=CATEGORY_CUSTOMER_COLLECTION,
                basis=BASIS_ACTUAL,
                status=MOVEMENT_CONFIRMED,
                display_reference=receipt.reference,
            )
        )
    for refund in collections_service.cashflow_refund_rows(
        session, project_id=project.id, as_of=as_of
    ):
        rows.append(
            SourceRow(
                source_type=SOURCE_REFUND,
                source_id=refund.id,
                period_month=month_of(refund.business_date),
                business_date=refund.business_date,
                amount=money(refund.amount),
                flow_direction=FLOW_OUTFLOW,
                category=CATEGORY_CUSTOMER_COLLECTION,
                basis=BASIS_ACTUAL,
                status=MOVEMENT_CONFIRMED,
                display_reference=refund.reference,
            )
        )
    for payment in construction_service.cashflow_payment_rows(
        session, project_id=project.id, as_of=as_of
    ):
        rows.append(
            SourceRow(
                source_type=SOURCE_CONSTRUCTION_PAYMENT,
                source_id=payment.id,
                period_month=month_of(payment.business_date),
                business_date=payment.business_date,
                amount=money(payment.amount),
                flow_direction=FLOW_OUTFLOW,
                category=CATEGORY_CONSTRUCTION,
                basis=BASIS_ACTUAL,
                status=MOVEMENT_CONFIRMED,
                display_reference=f"{payment.reference} · {payment.vendor_name}",
            )
        )
    for movement in session.scalars(
        select(CashflowDevelopmentMovement).where(
            *_standing_rows(
                session, model=CashflowDevelopmentMovement, project_id=project.id, as_of=as_of
            )
        )
    ):
        rows.append(
            SourceRow(
                source_type=SOURCE_DEVELOPMENT_MOVEMENT,
                source_id=movement.id,
                period_month=month_of(movement.movement_date),
                business_date=movement.movement_date,
                amount=money(movement.amount),
                flow_direction=FLOW_OUTFLOW,
                category=movement.category,
                basis=BASIS_ACTUAL,
                status=MOVEMENT_CONFIRMED,
                display_reference=movement.movement_reference,
            )
        )
    for movement in session.scalars(
        select(CashflowFinancingMovement).where(
            *_standing_rows(
                session, model=CashflowFinancingMovement, project_id=project.id, as_of=as_of
            )
        )
    ):
        rows.append(
            SourceRow(
                source_type=SOURCE_FINANCING_MOVEMENT,
                source_id=movement.id,
                period_month=month_of(movement.movement_date),
                business_date=movement.movement_date,
                amount=money(movement.amount),
                flow_direction=movement.flow_direction,
                category=movement.movement_type,
                basis=BASIS_ACTUAL,
                status=MOVEMENT_CONFIRMED,
                display_reference=movement.movement_reference,
            )
        )

    # Restrictions and releases move availability rather than cash, so they
    # carry their own basis and are never added to an inflow or an outflow.
    #
    # A restriction is standing only while the receipt it holds is: an escrow
    # over a transfer that was reversed is holding money the project never had,
    # and reporting it would take the reversal out of unrestricted cash twice —
    # once because the receipt no longer counts, and again because the escrow
    # still claims a share of what is left. At a historical cutoff both are asked
    # of that cutoff, so an August report keeps an escrow over an August receipt
    # that a September reversal later withdrew.
    for restriction, receipt_date, receipt_number in session.execute(
        select(
            CashflowReceiptRestriction,
            CollectionReceipt.receipt_date,
            CollectionReceipt.receipt_number,
        )
        .join(CollectionReceipt, CollectionReceipt.id == CashflowReceiptRestriction.receipt_id)
        .where(
            *_standing_rows(
                session, model=CashflowReceiptRestriction, project_id=project.id, as_of=as_of
            ),
            *standing_conditions(
                status=CollectionReceipt.status,
                confirmed_at=CollectionReceipt.confirmed_at,
                reversed_at=CollectionReceipt.reversed_at,
                as_of=as_of,
            ),
        )
    ).all():
        rows.append(
            SourceRow(
                source_type=SOURCE_RESTRICTION,
                source_id=restriction.id,
                # The month the money arrived, not the month somebody filed the
                # escrow paperwork: restricted cash has to rise in the same
                # period the receipt raised total cash, or unrestricted cash
                # briefly reports money the bank never released.
                period_month=month_of(receipt_date),
                business_date=receipt_date,
                amount=money(restriction.restricted_amount),
                flow_direction=FLOW_INFLOW,
                category="restriction",
                basis=BASIS_ACTUAL,
                status=MOVEMENT_CONFIRMED,
                display_reference=receipt_number,
            )
        )
    # A release frees a restriction, so it is standing only while that
    # restriction — and the receipt behind it — is. Freeing an escrow that no
    # longer exists would raise unrestricted cash against nothing.
    for release in session.scalars(
        select(CashflowRestrictionRelease)
        .join(
            CashflowReceiptRestriction,
            CashflowReceiptRestriction.id == CashflowRestrictionRelease.restriction_id,
        )
        .join(CollectionReceipt, CollectionReceipt.id == CashflowReceiptRestriction.receipt_id)
        .where(
            *_standing_rows(
                session, model=CashflowRestrictionRelease, project_id=project.id, as_of=as_of
            ),
            *standing_conditions(
                status=CashflowReceiptRestriction.status,
                confirmed_at=CashflowReceiptRestriction.confirmed_at,
                reversed_at=CashflowReceiptRestriction.reversed_at,
                as_of=as_of,
            ),
            *standing_conditions(
                status=CollectionReceipt.status,
                confirmed_at=CollectionReceipt.confirmed_at,
                reversed_at=CollectionReceipt.reversed_at,
                as_of=as_of,
            ),
        )
    ):
        rows.append(
            SourceRow(
                source_type=SOURCE_RELEASE,
                source_id=release.id,
                period_month=month_of(release.release_date),
                business_date=release.release_date,
                amount=money(release.amount),
                flow_direction=FLOW_OUTFLOW,
                category="release",
                basis=BASIS_ACTUAL,
                status=MOVEMENT_CONFIRMED,
                display_reference=str(release.id),
            )
        )

    if version is None:
        return rows

    snapshot = snapshot_rows(session, version_id=version.id)
    unapplied = collections_service.cashflow_unapplied_cash(
        session, project_id=project.id, as_of=as_of
    )
    adjusted = offset_unapplied_cash(snapshot, unapplied)
    for row in snapshot:
        month = month_of(row.chosen_forecast_date)
        rows.append(
            SourceRow(
                source_type=SOURCE_SCHEDULE,
                source_id=row.installment_id,
                period_month=month,
                business_date=row.chosen_forecast_date,
                amount=money(row.amount),
                flow_direction=FLOW_INFLOW,
                category=CATEGORY_CUSTOMER_COLLECTION,
                basis=BASIS_SCHEDULED,
                status=row.trigger_status,
                display_reference=str(row.installment_id),
            )
        )
        expected = adjusted.get(row.installment_id, money(row.amount))
        # No month test here. An instalment due on the 20th is still ahead of a
        # report taken on the 3rd of the same month, and dropping it because its
        # month has begun deletes three weeks of collections from the forecast.
        # ``counts_as_cash`` asks the instalment's own date instead.
        if expected > ZERO:
            rows.append(
                SourceRow(
                    source_type=SOURCE_SCHEDULE,
                    source_id=row.installment_id,
                    period_month=month,
                    business_date=row.chosen_forecast_date,
                    amount=expected,
                    flow_direction=FLOW_INFLOW,
                    category=CATEGORY_CUSTOMER_COLLECTION,
                    basis=BASIS_FORECAST,
                    status=row.trigger_status,
                    display_reference=str(row.installment_id),
                )
            )
    # The governed figure less what has already happened against it. The line
    # itself is untouched — a forecast that quietly shrank would not be the one
    # anybody approved — so the forecast file still reports the original amount
    # and only the projection reads the remainder.
    remainders = forecast_remainders(session, project=project, version=version, as_of=as_of)
    for line in forecast_lines(session, version_id=version.id):
        remaining = remainders.get(line.id, money(line.amount))
        if remaining <= ZERO:
            continue
        rows.append(
            SourceRow(
                source_type=SOURCE_FORECAST_LINE,
                source_id=line.id,
                period_month=line.period_month,
                business_date=line.period_month,
                amount=remaining,
                flow_direction=line.flow_direction,
                category=line.category,
                basis=BASIS_FORECAST,
                status=line.source_kind,
                display_reference=f"{line.source_kind}:{line.category}",
                month_grain=True,
            )
        )
    return rows


def _sum(rows: Sequence[SourceRow], predicate: Callable[[SourceRow], bool]) -> Decimal:
    return calculator.total(row.amount for row in rows if predicate(row))


@dataclass(frozen=True)
class ActualCashPosition:
    """Cash confirmed in hand at the as-of date, with no expectation in it."""

    as_of: date
    total_cash: Decimal
    restricted_cash: Decimal
    unrestricted_cash: Decimal


def actual_cash_position(
    rows: Sequence[SourceRow],
    *,
    version: CashflowForecastVersion | None,
    as_of: date,
) -> ActualCashPosition:
    """The governed opening balance plus every confirmed movement since it.

    Distinct from the current month's closing position, and deliberately so. The
    month the report is taken in closes on a **blended** figure — cash that moved
    plus cash still expected before the month ends — which is the right answer to
    "where will this month end" and the wrong answer to "what can we pay a
    contractor with today". Two different questions that a single "current cash"
    number had been answering with one figure.

    Built from the same row list and the same ``counts_as_cash`` rule as the
    bridge, restricted to what had actually happened by the cutoff, so this
    figure and the bridge cannot describe different projects.
    """
    anchor = opening_anchor_month(version)
    opening_total = money(
        (version.opening_unrestricted_cash + version.opening_restricted_cash)
        if version is not None
        else ZERO
    )
    opening_restricted = money(version.opening_restricted_cash if version is not None else ZERO)

    def counted(row: SourceRow) -> bool:
        if row.basis != BASIS_ACTUAL or not counts_as_cash(row, as_of=as_of):
            return False
        if anchor is not None and row.period_month < anchor:
            return False
        # A confirmed movement dated ahead of the cutoff is real cash in the
        # month it is dated, and it is not in the bank today.
        return row.business_date <= as_of

    moved = [row for row in rows if counted(row)]
    inflows = _sum(
        moved,
        lambda row: (
            row.flow_direction == FLOW_INFLOW and row.source_type not in RESTRICTION_SOURCES
        ),
    )
    outflows = _sum(
        moved,
        lambda row: (
            row.flow_direction == FLOW_OUTFLOW and row.source_type not in RESTRICTION_SOURCES
        ),
    )
    newly_restricted = _sum(moved, lambda row: row.source_type == SOURCE_RESTRICTION)
    released = _sum(moved, lambda row: row.source_type == SOURCE_RELEASE)

    total = calculator.closing_cash(
        opening_cash=opening_total,
        net_movement=calculator.net_cashflow(total_inflows=inflows, total_outflows=outflows),
    )
    restricted = calculator.closing_restricted_cash(
        opening_restricted=opening_restricted,
        newly_restricted=newly_restricted,
        released=released,
    )
    return ActualCashPosition(
        as_of=as_of,
        total_cash=total,
        restricted_cash=restricted,
        unrestricted_cash=calculator.closing_unrestricted_cash(
            closing_total=total, closing_restricted=restricted
        ),
    )


def monthly_positions(
    session: Session,
    *,
    project: Project,
    version: CashflowForecastVersion | None,
    as_of: date,
    start_month: date | None = None,
    end_month: date | None = None,
) -> list[MonthlyPosition]:
    """The cash bridge, month by month, with no gaps and nothing stored.

    A month is in one of **three** states, not two. A **closed** month is
    finished and its figures are its actuals. A **future** month has not started
    and its figures are its forecast. The month the report was taken in is
    **both**: the cash that has already moved, plus what is still expected before
    the month ends. Reporting that month as actual-only is the error worth
    naming, because it does not look like an error — the figure is a real number
    made of real transactions, and it silently omits every instalment due later
    in the month. A project reported on the 3rd would show a funding cliff that
    disappears on the 4th.

    The two series are never added to each other for the same cash. Which rows
    belong is settled once by ``counts_as_cash``: an actual row is cash that
    moved, a forecast row is cash still ahead of the cutoff, and no row can be
    both.

    Every month between the bounds appears, including the empty ones. A quiet
    quarter that vanished from the series would make a chart's axis lie about
    elapsed time, and a reader would see three months of work compressed into
    three weeks.

    The series may not begin before the governed opening balance is stated —
    see ``opening_anchor_month``.
    """
    rows = collect_source_rows(session, project=project, version=version, as_of=as_of)
    anchor = opening_anchor_month(version)

    if start_month is None:
        start_month = (
            anchor
            if anchor is not None
            else min((row.period_month for row in rows), default=month_of(as_of))
        )
    else:
        start_month = month_of(start_month)
        if anchor is not None and start_month < anchor:
            raise ValidationError(
                f"This project's cash bridge opens in {anchor}, the month the "
                f"forecast in force states its opening balance for. {start_month} "
                "is before that. The months before an opening balance cannot be "
                "rebuilt by replaying transactions through it — those transactions "
                "are already inside it, and running them again would count them "
                "twice. They remain in the transaction drill-down."
            )
    if end_month is None:
        end_month = version.forecast_end_month if version else month_of(as_of)
        latest = max((row.period_month for row in rows), default=end_month)
        end_month = max(end_month, latest, start_month)
    else:
        end_month = month_of(end_month)

    # Anything before the anchor is inside the opening balance already.
    rows = [row for row in rows if row.period_month >= start_month]

    by_month: dict[date, list[SourceRow]] = {}
    for row in rows:
        by_month.setdefault(row.period_month, []).append(row)

    opening_total = money(
        (version.opening_unrestricted_cash + version.opening_restricted_cash) if version else ZERO
    )
    opening_restricted = money(version.opening_restricted_cash if version else ZERO)

    positions: list[MonthlyPosition] = []
    for month in months_between(start_month, end_month):
        all_rows = by_month.get(month, [])
        # The one rule, asked once per month. Everything below sums what it
        # returned, so no figure here can be built on a second reading of what
        # "actual" and "forecast" mean.
        month_rows = [row for row in all_rows if counts_as_cash(row, as_of=as_of)]
        state = period_state(month, as_of=as_of)

        # Bound as a default rather than closed over: a closure inside this loop
        # would read whichever month the loop finished on, and every month would
        # silently report the last one's figures.
        def summed(
            source_type: str,
            row_basis: str,
            direction: str | None = None,
            categories: tuple[str, ...] | None = None,
            *,
            rows_of_month: Sequence[SourceRow] = month_rows,
        ) -> Decimal:
            return calculator.total(
                row.amount
                for row in rows_of_month
                if row.source_type == source_type
                and row.basis == row_basis
                and (direction is None or row.flow_direction == direction)
                and (categories is None or row.category in categories)
            )

        customer_scheduled = _sum(
            all_rows,
            lambda row: row.source_type == SOURCE_SCHEDULE and row.basis == BASIS_SCHEDULED,
        )
        customer_actual = summed(SOURCE_RECEIPT, BASIS_ACTUAL)
        customer_forecast = _sum(
            month_rows,
            lambda row: (
                row.basis == BASIS_FORECAST
                and (
                    row.source_type == SOURCE_SCHEDULE
                    or (
                        row.source_type == SOURCE_FORECAST_LINE
                        and row.category == CATEGORY_CUSTOMER_COLLECTION
                    )
                )
            ),
        )
        refunds = summed(SOURCE_REFUND, BASIS_ACTUAL)
        construction_actual = summed(SOURCE_CONSTRUCTION_PAYMENT, BASIS_ACTUAL)
        construction_forecast = summed(
            SOURCE_FORECAST_LINE, BASIS_FORECAST, FLOW_OUTFLOW, (CATEGORY_CONSTRUCTION,)
        )
        development_actual = summed(SOURCE_DEVELOPMENT_MOVEMENT, BASIS_ACTUAL)
        development_forecast = summed(
            SOURCE_FORECAST_LINE, BASIS_FORECAST, FLOW_OUTFLOW, DEVELOPMENT_CATEGORIES
        )
        financing_in_actual = summed(SOURCE_FINANCING_MOVEMENT, BASIS_ACTUAL, FLOW_INFLOW)
        financing_out_actual = summed(SOURCE_FINANCING_MOVEMENT, BASIS_ACTUAL, FLOW_OUTFLOW)
        financing_in_forecast = summed(
            SOURCE_FORECAST_LINE, BASIS_FORECAST, FLOW_INFLOW, FINANCING_TYPES
        )
        financing_out_forecast = summed(
            SOURCE_FORECAST_LINE, BASIS_FORECAST, FLOW_OUTFLOW, FINANCING_TYPES
        )

        total_inflows = calculator.total(
            [customer_actual, customer_forecast, financing_in_actual, financing_in_forecast]
        )
        total_outflows = calculator.total(
            [
                refunds,
                construction_actual,
                construction_forecast,
                development_actual,
                development_forecast,
                financing_out_actual,
                financing_out_forecast,
            ]
        )
        net = calculator.net_cashflow(total_inflows=total_inflows, total_outflows=total_outflows)
        closing_total = calculator.closing_cash(opening_cash=opening_total, net_movement=net)

        newly_restricted = _sum(month_rows, lambda row: row.source_type == SOURCE_RESTRICTION)
        releases = _sum(month_rows, lambda row: row.source_type == SOURCE_RELEASE)
        closing_restricted = calculator.closing_restricted_cash(
            opening_restricted=opening_restricted,
            newly_restricted=newly_restricted,
            released=releases,
        )
        opening_unrestricted = money(opening_total - opening_restricted)
        closing_unrestricted = calculator.closing_unrestricted_cash(
            closing_total=closing_total, closing_restricted=closing_restricted
        )

        positions.append(
            MonthlyPosition(
                period_month=month,
                period_state=state,
                opening_total_cash=opening_total,
                customer_scheduled_due=customer_scheduled,
                customer_actual_receipts=customer_actual,
                customer_forecast_receipts=customer_forecast,
                financing_actual_inflows=financing_in_actual,
                financing_forecast_inflows=financing_in_forecast,
                development_actual_outflows=development_actual,
                development_forecast_outflows=development_forecast,
                construction_actual_payments=construction_actual,
                construction_forecast_payments=construction_forecast,
                customer_refunds=refunds,
                financing_actual_outflows=financing_out_actual,
                financing_forecast_outflows=financing_out_forecast,
                total_inflows=total_inflows,
                total_outflows=total_outflows,
                net_cashflow=net,
                closing_total_cash=closing_total,
                opening_restricted_cash=opening_restricted,
                newly_restricted_customer_cash=newly_restricted,
                escrow_releases=releases,
                closing_restricted_cash=closing_restricted,
                opening_unrestricted_cash=opening_unrestricted,
                usable_inflows=money(total_inflows - newly_restricted + releases),
                unrestricted_outflows=total_outflows,
                closing_unrestricted_cash=closing_unrestricted,
                funding_gap=calculator.funding_gap(closing_unrestricted=closing_unrestricted),
            )
        )
        opening_total = closing_total
        opening_restricted = closing_restricted
    return positions


# --------------------------------------------------------------------------- #
# Funding windows and return
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FundingWindow:
    """A literal date window, not a count of months.

    "The next 90 days" asked on 20 March means to 18 June, which is most of
    March, all of April and May and half of June. Answering with three calendar
    months would quietly include the twenty days of March that have already been
    paid for, and the number would be wrong in the direction that makes a project
    look better funded than it is.
    """

    days: int
    from_date: date
    to_date: date
    opening_unrestricted_cash: Decimal
    usable_inflows: Decimal
    outflows: Decimal
    net_movement: Decimal
    minimum_projected_unrestricted_cash: Decimal
    closing_projected_unrestricted_cash: Decimal
    funding_requirement: Decimal


def funding_windows(
    session: Session,
    *,
    project: Project,
    version: CashflowForecastVersion | None,
    as_of: date,
    windows: Sequence[int] = (30, 60, 90),
    rows: Sequence[SourceRow] | None = None,
) -> list[FundingWindow]:
    """How much cash the project must raise to get through the next N days.

    Three things this answers that the arithmetic it replaces did not.

    **It starts from the money already in the bank.** A window that netted
    expected inflows against expected outflows and called the shortfall a
    funding requirement told a project sitting on ten million that it needed to
    raise five, which is not a conservative error — it is an instruction to
    raise debt against cash the company already holds, and somebody would have
    paid arrangement fees for it. Only *unrestricted* cash opens the window:
    escrowed buyer money is on the balance sheet and cannot pay a contractor.

    **It walks the window in date order.** Cash is not fungible across time. A
    two-million payment on day ten funded by a two-million receipt on day twenty
    closes the window level and is insolvent in between, and the closing balance
    — the figure this used to report — is exactly the one number that cannot see
    it.

    **It reports the worst point, not the last one.** The requirement is what it
    takes to never go below zero, so it is driven by the deepest trough inside
    the window. Movements are applied a day at a time and the position is read at
    each day's end: within one day the order of two payments is not a fact this
    system holds, and inventing one would make the answer depend on the order
    rows happened to be written in.
    """
    if rows is None:
        rows = collect_source_rows(session, project=project, version=version, as_of=as_of)
    opening = actual_cash_position(rows, version=version, as_of=as_of).unrestricted_cash
    live = [row for row in rows if counts_as_cash(row, as_of=as_of)]

    out: list[FundingWindow] = []
    for days in windows:
        end = as_of + timedelta(days=days)
        by_day: dict[date, list[SourceRow]] = {}
        for row in live:
            when = window_date(row, as_of=as_of)
            if as_of < when <= end:
                by_day.setdefault(when, []).append(row)

        running = opening
        minimum = opening
        inflows = ZERO
        outflows = ZERO
        restricted = ZERO
        released = ZERO
        for day in sorted(by_day):
            for row in by_day[day]:
                if row.source_type == SOURCE_RESTRICTION:
                    restricted = money(restricted + row.amount)
                    running = money(running - row.amount)
                elif row.source_type == SOURCE_RELEASE:
                    released = money(released + row.amount)
                    running = money(running + row.amount)
                elif row.flow_direction == FLOW_INFLOW:
                    inflows = money(inflows + row.amount)
                    running = money(running + row.amount)
                else:
                    outflows = money(outflows + row.amount)
                    running = money(running - row.amount)
            minimum = min(minimum, running)

        usable = money(inflows - restricted + released)
        out.append(
            FundingWindow(
                days=days,
                from_date=as_of,
                to_date=end,
                opening_unrestricted_cash=opening,
                usable_inflows=usable,
                outflows=outflows,
                net_movement=money(usable - outflows),
                minimum_projected_unrestricted_cash=minimum,
                closing_projected_unrestricted_cash=running,
                funding_requirement=calculator.funding_gap(closing_unrestricted=minimum),
            )
        )
    return out


@dataclass(frozen=True)
class ReturnPosition:
    """NPV and equity IRR, each with the basis it was computed on stated.

    The basis is part of the number. A project NPV and a levered one differ by
    every financing flow, and a figure labelled only "NPV" invites the reader to
    assume whichever they were expecting.
    """

    npv_basis: str
    discount_rate_per_period: Decimal
    net_present_value: Decimal
    net_project_cashflow: Decimal
    equity_irr_basis: str
    equity_irr_per_period: Decimal | None
    equity_irr_unavailable_reason: str | None
    equity_contributed: Decimal
    equity_distributed: Decimal
    equity_net: Decimal


#: What the NPV is computed on, stated in the response rather than assumed.
NPV_BASIS = "project_operating_and_development"
IRR_BASIS = "equity_investor_sign_convention"


def equity_rows(
    positions: Sequence[MonthlyPosition],
    rows: Sequence[SourceRow],
    *,
    as_of: date,
) -> list[SourceRow]:
    """The equity movements the bridge is reporting, and no others.

    Gated by ``counts_as_cash`` and confined to the bridge's own months, because
    a return computed on a wider set than the cash bridge is a return on a
    different project. The version this replaces swept every equity row in the
    register regardless of basis, so a contribution that was both forecast and
    then actually received counted twice in the IRR while the bridge counted it
    once, and the two disagreed by exactly the amount that mattered most.
    """
    months = {position.period_month for position in positions}
    return [
        row
        for row in rows
        if row.period_month in months
        and counts_as_cash(row, as_of=as_of)
        and (
            (row.category == EQUITY_CONTRIBUTION and row.flow_direction == FLOW_INFLOW)
            or (row.category == EQUITY_DISTRIBUTION and row.flow_direction == FLOW_OUTFLOW)
        )
    ]


def equity_flows_for(
    positions: Sequence[MonthlyPosition],
    rows: Sequence[SourceRow],
    *,
    as_of: date,
) -> list[Decimal]:
    """The investor-sign equity series an IRR is computed on, one per period.

    Public because it is the thing that has to be provable. An IRR is a single
    number derived from a series nobody can see, and "the IRR looks wrong" is not
    a defect anyone can act on. Exposing the series lets a reader — and a test —
    put the bridge's equity cash for a month beside the figure the IRR was given
    for that month and check that they are the same cash with the sign turned
    round.
    """
    by_month: dict[date, Decimal] = {}
    for row in equity_rows(positions, rows, as_of=as_of):
        # The signs are the investor's, not the project's. An equity
        # contribution is cash the project received and the investor paid.
        signed = -row.amount if row.category == EQUITY_CONTRIBUTION else row.amount
        by_month[row.period_month] = money(by_month.get(row.period_month, ZERO) + signed)
    return [by_month.get(position.period_month, ZERO) for position in positions]


def return_position(
    positions: Sequence[MonthlyPosition],
    rows: Sequence[SourceRow],
    *,
    as_of: date,
    discount_rate_per_period: Decimal,
) -> ReturnPosition:
    """Discounted return on the project, and the periodic return on equity.

    **NPV is the project's, not the investor's.** It discounts operating and
    development cash — customer cash in, refunds, development spend and
    construction spend — and excludes every financing flow. Equity contributions
    are how the project was funded, not what it earned, and including them would
    make a project look better the more expensively it was financed.

    **IRR is the investor's**, and the signs are reversed for it deliberately. An
    equity contribution is cash the project received and the investor paid out;
    feeding project-direction cash into an IRR produces the right magnitude with
    the wrong sign, which is the single easiest way to report a loss as a return.

    Both are computed on the **same basis as the cash bridge**. The NPV reads the
    bridge's own monthly figures; the equity series is gated by the same
    ``counts_as_cash`` rule over the same months. Returns applies no second
    interpretation of what is actual and what is forecast, because a project
    whose bridge and whose IRR disagree about that has two answers and no way to
    tell which one a decision was made on.
    """
    project_flows = [
        money(
            position.customer_actual_receipts
            + position.customer_forecast_receipts
            - position.customer_refunds
            - position.development_actual_outflows
            - position.development_forecast_outflows
            - position.construction_actual_payments
            - position.construction_forecast_payments
        )
        for position in positions
    ]

    equity = equity_rows(positions, rows, as_of=as_of)
    contributed = _sum(equity, lambda row: row.category == EQUITY_CONTRIBUTION)
    distributed = _sum(equity, lambda row: row.category == EQUITY_DISTRIBUTION)
    equity_flows = equity_flows_for(positions, rows, as_of=as_of)
    irr = calculator.internal_rate_of_return(equity_flows=equity_flows)

    return ReturnPosition(
        npv_basis=NPV_BASIS,
        discount_rate_per_period=discount_rate_per_period,
        net_present_value=calculator.net_present_value(
            net_flows=project_flows, rate_per_period=discount_rate_per_period
        ),
        net_project_cashflow=calculator.total(project_flows),
        equity_irr_basis=IRR_BASIS,
        equity_irr_per_period=irr.rate_per_period,
        equity_irr_unavailable_reason=irr.unavailable_reason,
        equity_contributed=contributed,
        equity_distributed=distributed,
        equity_net=money(distributed - contributed),
    )


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #


def reconciliation(session: Session, *, project: Project, as_of: date) -> list[calculator.Check]:
    """Structural checks with no tolerance, each answered on its own.

    No health score. A single blended number would let a failed escrow ceiling
    and a passing currency check average into "mostly fine", and nobody would
    know which half was which.
    """
    version = active_forecast(session, project_id=project.id)
    checks: list[calculator.Check] = []

    if version is not None:
        checks.append(
            calculator.equality_check(
                name="opening_total_splits_into_restricted_and_unrestricted",
                expected=money(version.opening_unrestricted_cash + version.opening_restricted_cash),
                actual=money(version.opening_unrestricted_cash + version.opening_restricted_cash),
                detail="Opening total cash is stated as its two components, never separately.",
            )
        )
        checks.extend(construction_reconciliation(session, project=project, version=version))
        staleness = source_staleness(session, project=project, version=version)
        checks.append(
            calculator.count_check(
                name="construction_source_current",
                actual=1 if staleness.construction_is_stale else 0,
                detail=(
                    f"The forecast in force pins construction forecast version "
                    f"{staleness.pinned_construction_version_number}; version "
                    f"{staleness.active_construction_version_number} is now active."
                ),
            )
        )
        unplaced = _unplaced_installment_count(session, project=project, version=version)
        checks.append(
            calculator.count_check(
                name="customer_schedule_snapshot_complete",
                actual=unplaced,
                detail=(
                    f"{unplaced} governing instalment(s) have no date of any kind and "
                    "could not be placed in a month."
                ),
            )
        )

    # Every restriction against the receipt it was taken from, and every release
    # against the restriction it frees. Both are ceilings the service holds under
    # lock; this is the independent read that proves it held.
    for restriction, receipt_amount in session.execute(
        select(CashflowReceiptRestriction, CollectionReceipt.amount)
        .join(CollectionReceipt, CollectionReceipt.id == CashflowReceiptRestriction.receipt_id)
        .where(
            CashflowReceiptRestriction.project_id == project.id,
            CashflowReceiptRestriction.status.in_((MOVEMENT_RECORDED, MOVEMENT_CONFIRMED)),
        )
    ).all():
        checks.append(
            calculator.limit_check(
                name=f"restriction_within_receipt_{restriction.id}",
                ceiling=receipt_amount,
                actual=restriction.restricted_amount,
                detail="An escrow cannot hold more than the transfer it was taken from.",
            )
        )
        checks.append(
            calculator.limit_check(
                name=f"releases_within_restriction_{restriction.id}",
                ceiling=restriction.restricted_amount,
                actual=released_against(session, restriction_id=restriction.id),
                detail="An escrow cannot release more than it holds.",
            )
        )

    # An escrow over a transfer that no longer stands is holding money the
    # project does not have. The reads that build a report already exclude it;
    # this is the independent count that says somebody has a correction to make.
    unbacked = session.scalars(
        select(func.count())
        .select_from(CashflowReceiptRestriction)
        .join(CollectionReceipt, CollectionReceipt.id == CashflowReceiptRestriction.receipt_id)
        .where(
            CashflowReceiptRestriction.project_id == project.id,
            CashflowReceiptRestriction.status.in_((MOVEMENT_RECORDED, MOVEMENT_CONFIRMED)),
            CollectionReceipt.status != STANDING_CONFIRMED,
        )
    ).first()
    checks.append(
        calculator.count_check(
            name="restrictions_backed_by_standing_customer_cash",
            actual=int(unbacked or 0),
            detail=(
                "A restriction can only hold customer cash that is still standing. "
                "Reverse the restriction when the receipt behind it is withdrawn."
            ),
        )
    )

    # Confirmed cash that has not been confirmed by a second person is cash one
    # person moved alone. The database refuses it; this proves none slipped past
    # an earlier revision of the constraint.
    for model, label in (
        (CashflowDevelopmentMovement, "development"),
        (CashflowFinancingMovement, "financing"),
        (CashflowRestrictionRelease, "release"),
    ):
        unchecked = session.scalars(
            select(func.count())
            .select_from(model)
            .where(
                model.project_id == project.id,
                model.status == MOVEMENT_CONFIRMED,
                model.confirmed_by_user_id == model.recorded_by_user_id,
            )
        ).first()
        checks.append(
            calculator.count_check(
                name=f"{label}_maker_is_not_checker",
                actual=int(unchecked or 0),
                detail="A confirmation by the person who recorded it is not a second pair of eyes.",
            )
        )

    checks.append(
        calculator.count_check(
            name="one_denomination_throughout",
            actual=_foreign_currency_count(session, project=project),
            detail=(
                "Every movement consolidated into the project's cash must be in its "
                "base currency. This MVP has no exchange rate."
            ),
        )
    )

    # The bridge itself: opening plus inflows minus outflows is closing, and each
    # month opens where the last one closed.
    positions = monthly_positions(session, project=project, version=version, as_of=as_of)
    for position in positions:
        checks.append(
            calculator.equality_check(
                name=f"bridge_{position.period_month.isoformat()}",
                expected=position.closing_total_cash,
                actual=money(
                    position.opening_total_cash + position.total_inflows - position.total_outflows
                ),
                detail="Opening plus inflows less outflows is closing.",
            )
        )
        checks.append(
            calculator.equality_check(
                name=f"usable_split_{position.period_month.isoformat()}",
                expected=position.closing_unrestricted_cash,
                actual=money(position.closing_total_cash - position.closing_restricted_cash),
                detail="Unrestricted cash is total cash less what is restricted.",
            )
        )
    for earlier, later in pairwise(positions):
        checks.append(
            calculator.equality_check(
                name=f"carry_{later.period_month.isoformat()}",
                expected=earlier.closing_total_cash,
                actual=later.opening_total_cash,
                detail="A month opens exactly where the one before it closed.",
            )
        )
    return checks


def _unplaced_installments(
    session: Session, *, project: Project, version: CashflowForecastVersion
) -> list[payment_plans_service.CashflowScheduleRow]:
    """Governing instalments the snapshot could not place in any month.

    Named rather than counted, because the count alone tells a preparer that
    something is wrong and nothing about where to go and fix it.
    """
    governing = payment_plans_service.cashflow_schedule_rows(
        session, project_id=project.id, as_of=version.as_of_date
    )
    return [row for row in governing if chosen_forecast_date(row) is None]


def _unplaced_installment_count(
    session: Session, *, project: Project, version: CashflowForecastVersion
) -> int:
    """How many governing instalments have no date to be placed on."""
    return len(_unplaced_installments(session, project=project, version=version))


def _foreign_currency_count(session: Session, *, project: Project) -> int:
    """Movements consolidated here that are not in the project's base currency."""
    total = 0
    for model in (CashflowDevelopmentMovement, CashflowFinancingMovement):
        total += int(
            session.scalars(
                select(func.count())
                .select_from(model)
                .where(
                    model.project_id == project.id,
                    model.currency_id != project.base_currency_id,
                )
            ).first()
            or 0
        )
    return total


# --------------------------------------------------------------------------- #
# Forecast accuracy
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AccuracyRow:
    """One month and category, forecast against what actually happened."""

    period_month: date
    category_group: str
    variance: calculator.Variance


#: The groups accuracy is reported on. Deliberately several rather than one: a
#: blended "accuracy score" would let customer collections running 20% ahead
#: cancel construction running 20% behind and report a project on plan.
ACCURACY_CUSTOMER_INFLOW = "customer_inflow"
ACCURACY_CONSTRUCTION_OUTFLOW = "construction_outflow"
ACCURACY_DEVELOPMENT_OUTFLOW = "development_outflow"
ACCURACY_FINANCING = "financing"


def forecast_accuracy(
    session: Session,
    *,
    project: Project,
    version: CashflowForecastVersion,
    as_of: date,
) -> list[AccuracyRow]:
    """A prior forecast's months against the actuals that landed in them.

    Compared only up to the as-of date, and only from the version's own cutoff.
    A month before the version existed was never forecast — a line written for it
    is hindsight, and measuring hindsight tells a reader nothing about how well
    this company plans. A month that has not finished has no actual to be
    measured against, and reporting one would call a project behind plan for the
    entirely ordinary reason that the month is still running.

    The one partial period is the version's own as-of month, and both sides are
    trimmed to it: ``counts_as_cash`` gives the forecast the version actually
    made for the rest of that month, and ``measurable`` gives the actuals that
    landed in the same stretch of it.
    """
    limit = month_of(as_of)
    cutoff_month = month_of(version.as_of_date)
    forecast_rows = collect_source_rows(
        session, project=project, version=version, as_of=version.as_of_date
    )
    actual_rows = collect_source_rows(session, project=project, version=None, as_of=as_of)

    def group_of(row: SourceRow) -> str | None:
        if row.category == CATEGORY_CUSTOMER_COLLECTION and row.flow_direction == FLOW_INFLOW:
            return ACCURACY_CUSTOMER_INFLOW
        if row.category == CATEGORY_CONSTRUCTION:
            return ACCURACY_CONSTRUCTION_OUTFLOW
        if row.category in DEVELOPMENT_CATEGORIES:
            return ACCURACY_DEVELOPMENT_OUTFLOW
        if row.category in FINANCING_TYPES:
            return ACCURACY_FINANCING
        return None

    def in_scope(row: SourceRow) -> bool:
        return cutoff_month <= row.period_month <= limit and group_of(row) is not None

    def measurable(row: SourceRow) -> bool:
        """Actual cash this version was in a position to have forecast.

        Its own as-of month was already part spent when it was prepared, so it
        only ever forecast the remainder of that month. Putting that remainder
        beside the whole month's actuals would report every forecast as wildly
        under, for the one reason that has nothing to do with how good the
        forecast was — and the earlier in the month a forecast is taken, the
        worse it would appear to have been.
        """
        if row.period_month != cutoff_month:
            return True
        return row.business_date > version.as_of_date

    forecast_totals: dict[tuple[date, str], Decimal] = {}
    for row in forecast_rows:
        if not in_scope(row) or row.basis != BASIS_FORECAST:
            continue
        # The same rule the bridge used when this version was the live one, so
        # what is measured is what the version actually reported at the time.
        if not counts_as_cash(row, as_of=version.as_of_date):
            continue
        key = (row.period_month, str(group_of(row)))
        forecast_totals[key] = money(forecast_totals.get(key, ZERO) + row.amount)

    actual_totals: dict[tuple[date, str], Decimal] = {}
    for row in actual_rows:
        if not in_scope(row) or row.basis != BASIS_ACTUAL or not measurable(row):
            continue
        if row.source_type in RESTRICTION_SOURCES:
            continue
        key = (row.period_month, str(group_of(row)))
        actual_totals[key] = money(actual_totals.get(key, ZERO) + row.amount)

    return [
        AccuracyRow(
            period_month=month,
            category_group=group,
            variance=calculator.forecast_variance(
                forecast_amount=forecast_totals.get((month, group), ZERO),
                actual_amount=actual_totals.get((month, group), ZERO),
            ),
        )
        for month, group in sorted(set(forecast_totals) | set(actual_totals))
    ]
