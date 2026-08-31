"""Payment plan behaviour: prepare, reconcile, sanction, activate, trigger.

The rules this file exists to hold, stated once:

**A schedule that does not reconcile cannot leave draft.** Not with a warning,
not at 99.99%, not a penny short. Every gate — submit, approve, activate —
recomputes the totals from the stored rows and refuses with the specific
shortfall rather than "invalid plan".

**A forecast is not an event.** A construction milestone expected in March does
not fall due in March. It falls due when PR-MVP-09 certifies it, which does not
exist yet, so the amount stays awaiting its trigger and the actual due date
stays empty. This is the one control most likely to be quietly softened by a
future change, and it is enforced in the database as well as here.

**Approval is independent.** The submitter cannot approve, the administrator
cannot approve, and approval re-reads and re-checks everything rather than
trusting what submission concluded — a sale can change between the two, and an
approval of stale figures is worse than no approval.

Everything that mutates takes the project lock first, then the plan, then the
version, in that order, and writes its audit row inside the same transaction as
the change it describes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import Role, User, UserRole
from app.modules.audit.service import record_event
from app.modules.inventory.custom_fields import business_today
from app.modules.inventory.models import Unit
from app.modules.payment_plans import permissions, schedule
from app.modules.payment_plans.models import (
    ALLOCATION_PERCENTAGE,
    CHARGE_PRO_RATA,
    ORIGIN_COPIED,
    ORIGIN_CUSTOM,
    RECURRENCE_MONTHS,
    TRIGGER_AWAITING,
    TRIGGER_CONSTRUCTION_MILESTONE,
    TRIGGER_DATE_BASED,
    TRIGGER_DAYS_AFTER_SPA,
    TRIGGER_EVENT_APPROVED,
    TRIGGER_EVENT_REVERSED,
    TRIGGER_EVENT_SUBMITTED,
    TRIGGER_FIXED_DATE,
    TRIGGER_HANDOVER,
    TRIGGER_MANUAL_EVENT,
    TRIGGER_RECURRING_MONTHLY,
    TRIGGER_RECURRING_QUARTERLY,
    TRIGGER_SCHEDULED,
    TRIGGER_TITLE_TRANSFER,
    TRIGGER_TRIGGERED,
    VERSION_ACTIVE,
    VERSION_APPROVED,
    VERSION_COPYABLE,
    VERSION_DRAFT,
    VERSION_OPEN,
    VERSION_REJECTED,
    VERSION_SUBMITTED,
    VERSION_SUPERSEDED,
    InstallmentTriggerEvent,
    PaymentPlan,
    PaymentPlanInstallment,
    PaymentPlanVersion,
)
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import service as sales_service
from app.modules.sales.models import (
    EVENT_TRANSFERRED,
    HANDOVER_HANDED_OVER,
    SALE_ACTIVE,
    SALE_SIGNATURE_PENDING,
    Client,
    HandoverRecord,
    SaleContract,
)

#: The sale states a plan may be prepared against. A draft contract's price,
#: tax and fees can still move, and a schedule written over figures that then
#: change is a schedule nobody agreed to.
SALE_PLANNABLE = frozenset({SALE_SIGNATURE_PENDING, SALE_ACTIVE})

_PLAN_PREFIX = "PLN"

_NOT_DRAFT = "Only a draft schedule can be changed. Create a new version to alter the terms."

#: One refusal each for a nested resource that is missing, hidden, or claimed by
#: the wrong parent. Deliberately identical in all three cases.
_NO_VERSION = "Payment plan version not found."
_NO_INSTALLMENT = "Instalment not found."
_NO_EVENT = "Trigger event not found."
_NO_COPY_SOURCE = "The plan being copied was not found in this project."


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Loading and locking
# --------------------------------------------------------------------------- #


def _lock_plan(session: Session, *, project_id: uuid.UUID, plan_id: uuid.UUID) -> PaymentPlan:
    """Take the plan row for update and return its committed state."""
    plan = session.scalars(
        select(PaymentPlan)
        .where(PaymentPlan.id == plan_id, PaymentPlan.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if plan is None:
        raise permissions.plan_not_found()
    return plan


def _lock_version(
    session: Session, *, project_id: uuid.UUID, version_id: uuid.UUID
) -> PaymentPlanVersion:
    """Take the version row for update and return its committed state."""
    version = session.scalars(
        select(PaymentPlanVersion)
        .where(
            PaymentPlanVersion.id == version_id,
            PaymentPlanVersion.project_id == project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if version is None:
        raise NotFoundError("Payment plan version not found.")
    return version


def _lock_trigger_event(
    session: Session, *, project_id: uuid.UUID, event_id: uuid.UUID
) -> InstallmentTriggerEvent:
    """Take the attestation row for update and return its committed state."""
    event = session.scalars(
        select(InstallmentTriggerEvent)
        .where(
            InstallmentTriggerEvent.id == event_id,
            InstallmentTriggerEvent.project_id == project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if event is None:
        raise NotFoundError(_NO_EVENT)
    return event


def _visible_plan_or_none(
    session: Session, *, project: Project, plan_id: uuid.UUID, actor: ActorContext
) -> PaymentPlan | None:
    """The plan if this caller may see it, otherwise nothing.

    Narrowed through the sale, so a plan on a unit in a phase the caller was
    never granted answers exactly as a plan that does not exist.
    """
    statement = select(PaymentPlan).where(
        PaymentPlan.id == plan_id, PaymentPlan.project_id == project.id
    )
    allowed = permissions.visible_sale_ids(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(PaymentPlan.sale_contract_id.in_(allowed))
    return session.scalars(statement).first()


def _visible_plan(
    session: Session, *, project: Project, plan_id: uuid.UUID, actor: ActorContext
) -> PaymentPlan:
    """Load a plan the caller may see, or raise 404."""
    plan = _visible_plan_or_none(session, project=project, plan_id=plan_id, actor=actor)
    if plan is None:
        raise permissions.plan_not_found()
    return plan


# --------------------------------------------------------------------------- #
# Nested resources
#
# A nested path is a claim about parentage: ``/plan-A/versions/version-B``
# asserts that B is one of A's versions, and ``/plan-A/installments/row-C``
# that C is scheduled by one of them. Every loader below proves the whole chain
#
#     project -> plan -> version -> instalment -> attestation
#
# before returning anything, rather than validating each identifier on its own
# and trusting that the caller paired them honestly. Two independently valid
# identifiers are not a valid pair.
#
# The refusal is always the same 404, and never says "belongs to another plan":
# that phrasing confirms the hidden identifier exists, which is exactly what a
# caller guessing at identifiers is trying to learn.
# --------------------------------------------------------------------------- #


def _visible_version_for_plan(
    session: Session,
    *,
    project: Project,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    actor: ActorContext,
) -> tuple[PaymentPlanVersion, PaymentPlan]:
    """Load a version proved to belong to ``plan_id``, or raise 404."""
    plan = _visible_plan(session, project=project, plan_id=plan_id, actor=actor)
    version = session.scalars(
        select(PaymentPlanVersion).where(
            PaymentPlanVersion.id == version_id,
            PaymentPlanVersion.project_id == project.id,
            PaymentPlanVersion.payment_plan_id == plan.id,
        )
    ).first()
    if version is None:
        raise NotFoundError(_NO_VERSION)
    return version, plan


def _visible_installment_for_plan(
    session: Session,
    *,
    project: Project,
    plan_id: uuid.UUID,
    installment_id: uuid.UUID,
    actor: ActorContext,
) -> tuple[PaymentPlanInstallment, PaymentPlanVersion, PaymentPlan]:
    """Load an instalment proved to be scheduled by ``plan_id``, or raise 404."""
    plan = _visible_plan(session, project=project, plan_id=plan_id, actor=actor)
    found = session.execute(
        select(PaymentPlanInstallment, PaymentPlanVersion)
        .join(
            PaymentPlanVersion,
            PaymentPlanVersion.id == PaymentPlanInstallment.payment_plan_version_id,
        )
        .where(
            PaymentPlanInstallment.id == installment_id,
            PaymentPlanInstallment.project_id == project.id,
            PaymentPlanVersion.payment_plan_id == plan.id,
        )
    ).first()
    if found is None:
        raise NotFoundError(_NO_INSTALLMENT)
    installment, version = found
    return installment, version, plan


def _visible_trigger_event_for_plan(
    session: Session,
    *,
    project: Project,
    plan_id: uuid.UUID,
    event_id: uuid.UUID,
    actor: ActorContext,
) -> tuple[InstallmentTriggerEvent, PaymentPlanInstallment, PaymentPlanVersion, PaymentPlan]:
    """Load an attestation proved to belong to ``plan_id``, or raise 404."""
    plan = _visible_plan(session, project=project, plan_id=plan_id, actor=actor)
    found = session.execute(
        select(InstallmentTriggerEvent, PaymentPlanInstallment, PaymentPlanVersion)
        .join(
            PaymentPlanInstallment,
            PaymentPlanInstallment.id == InstallmentTriggerEvent.installment_id,
        )
        .join(
            PaymentPlanVersion,
            PaymentPlanVersion.id == PaymentPlanInstallment.payment_plan_version_id,
        )
        .where(
            InstallmentTriggerEvent.id == event_id,
            InstallmentTriggerEvent.project_id == project.id,
            PaymentPlanVersion.payment_plan_id == plan.id,
        )
    ).first()
    if found is None:
        raise NotFoundError(_NO_EVENT)
    event, installment, version = found
    return event, installment, version, plan


def installments_of(session: Session, *, version_id: uuid.UUID) -> list[PaymentPlanInstallment]:
    """The schedule's rows, in contractual order."""
    return list(
        session.scalars(
            select(PaymentPlanInstallment)
            .where(PaymentPlanInstallment.payment_plan_version_id == version_id)
            .order_by(PaymentPlanInstallment.sequence)
        )
    )


def versions_of(session: Session, *, plan_id: uuid.UUID) -> list[PaymentPlanVersion]:
    """Every version of a plan, newest first."""
    return list(
        session.scalars(
            select(PaymentPlanVersion)
            .where(PaymentPlanVersion.payment_plan_id == plan_id)
            .order_by(PaymentPlanVersion.version_number.desc())
        )
    )


def active_version(session: Session, *, plan_id: uuid.UUID) -> PaymentPlanVersion | None:
    """The schedule currently governing the sale, if one has been activated."""
    return session.scalars(
        select(PaymentPlanVersion).where(
            PaymentPlanVersion.payment_plan_id == plan_id,
            PaymentPlanVersion.status == VERSION_ACTIVE,
        )
    ).first()


def open_version(session: Session, *, plan_id: uuid.UUID) -> PaymentPlanVersion | None:
    """The version in preparation, if one is open."""
    return session.scalars(
        select(PaymentPlanVersion).where(
            PaymentPlanVersion.payment_plan_id == plan_id,
            PaymentPlanVersion.status.in_(tuple(VERSION_OPEN)),
        )
    ).first()


def current_version(session: Session, *, plan_id: uuid.UUID) -> PaymentPlanVersion | None:
    """The version a reader should be shown by default.

    The open one if a revision is being prepared, otherwise the standing one,
    otherwise the most recent history. A plan always shows something.
    """
    return _current_version_of(versions_of(session, plan_id=plan_id))


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #


def reconcile_rows(
    version: PaymentPlanVersion, rows: list[PaymentPlanInstallment]
) -> schedule.Reconciliation:
    """Total instalments already in hand against their version's frozen basis.

    Separated from the loading so a caller that has read a schedule for another
    reason — the register reads every plan's rows in one query — can total it
    without reading it again, and still get the answer from the same function
    the plan screen uses. Two totalling routines are two answers waiting to
    disagree.
    """
    lines = [
        schedule.Line(
            principal_amount=row.principal_amount,
            principal_fraction=row.principal_fraction,
            tax_amount=row.tax_amount,
            fee_amount=row.fee_amount,
        )
        for row in rows
    ]
    return schedule.reconcile(
        lines,
        contract_value_covered=version.contract_value_covered,
        tax_total_snapshot=version.tax_total_snapshot,
        buyer_fee_total_snapshot=version.buyer_fee_total_snapshot,
        total_buyer_payable_snapshot=version.total_buyer_payable_snapshot,
    )


def reconcile_version(session: Session, *, version: PaymentPlanVersion) -> schedule.Reconciliation:
    """Total the stored schedule against the version's frozen sale basis.

    Derived live from immutable rows rather than cached on the version: a
    stored total is a second source of truth that drifts the first time
    somebody writes a row without updating it.
    """
    return reconcile_rows(version, installments_of(session, version_id=version.id))


def _require_reconciled(session: Session, *, version: PaymentPlanVersion) -> None:
    """Refuse to advance a schedule that does not add up, and say why.

    The reasons name the figure and the amount. An operator who is told the
    principal is short by 5,000.00 knows which line to look at; one told the
    plan is invalid has to check all forty.
    """
    reconciliation = reconcile_version(session, version=version)
    if reconciliation.is_reconciled:
        return
    reasons = schedule.shortfall_reasons(reconciliation)
    raise ConflictError(" ".join(reasons))


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #


def _next_plan_number(session: Session, *, project: Project) -> str:
    """Assign the next project-scoped plan reference under the project lock.

    ``MAX + 1`` is only safe because the caller already took the project row
    for update; two requests arriving together take turns and produce
    PLN-000004 and PLN-000005 rather than both claiming the same number. The
    unique index remains as the backstop for a caller that forgot the lock.
    """
    highest = session.scalar(
        select(func.max(func.substr(PaymentPlan.plan_number, len(_PLAN_PREFIX) + 2))).where(
            PaymentPlan.project_id == project.id,
            PaymentPlan.plan_number.like(f"{_PLAN_PREFIX}-%"),
        )
    )
    number = int(highest) + 1 if highest and highest.isdigit() else 1
    return f"{_PLAN_PREFIX}-{number:06d}"


def _require_plannable_sale(sale: SaleContract) -> None:
    """Refuse a plan against a contract whose terms are not yet settled."""
    if sale.status not in SALE_PLANNABLE:
        raise ConflictError(
            "A payment plan can only be prepared for a contract that is awaiting "
            f"signature or active. This one is {sale.status.replace('_', ' ')}."
        )


def list_plans(session: Session, *, project: Project, actor: ActorContext) -> list[PaymentPlan]:
    """The plans this caller may see, narrowed in SQL."""
    permissions.require_plan_reader(actor)
    statement = select(PaymentPlan).where(PaymentPlan.project_id == project.id)
    allowed = permissions.visible_sale_ids(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(PaymentPlan.sale_contract_id.in_(allowed))
    return list(session.scalars(statement.order_by(PaymentPlan.plan_number.desc())))


def get_plan(
    session: Session, *, project: Project, plan_id: uuid.UUID, actor: ActorContext
) -> PaymentPlan:
    """One plan the caller may see."""
    permissions.require_plan_reader(actor)
    return _visible_plan(session, project=project, plan_id=plan_id, actor=actor)


def create_plan(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    sale_contract_id: uuid.UUID,
    name: str,
    reservation_treatment: str,
    origin_type: str,
    source_version_id: uuid.UUID | None,
    effective_date: date | None,
    notes: str | None,
    correlation_id: uuid.UUID,
) -> tuple[PaymentPlan, PaymentPlanVersion]:
    """Open a plan for a sale, with its first draft version.

    The version's basis is copied from the contract here and never recomputed:
    pricing is not consulted, tax is not recalculated. The contract already
    says what the buyer owes, and a schedule that re-derived it would sooner or
    later disagree with the document the parties signed.
    """
    permissions.require_plan_writer(actor)
    project = lock_project(session, project.id)
    sale = permissions.require_visible_sale(
        session, project=project, sale_id=sale_contract_id, actor=actor
    )
    _require_plannable_sale(sale)

    # The request's own shape is judged before the sale's state: a source
    # version that contradicts the origin, or one nobody has agreed to, is
    # wrong however many plans the sale already has.
    source = _resolve_copy_source(
        session,
        project=project,
        actor=actor,
        origin_type=origin_type,
        source_version_id=source_version_id,
    )

    existing = session.scalars(
        select(PaymentPlan).where(PaymentPlan.sale_contract_id == sale.id)
    ).first()
    if existing is not None:
        raise ConflictError(
            f"{sale.sale_number} already has payment plan {existing.plan_number}. "
            "Create a new version of it rather than a second plan."
        )

    plan = PaymentPlan(
        project_id=project.id,
        sale_contract_id=sale.id,
        plan_number=_next_plan_number(session, project=project),
        name=name,
        notes=notes,
        created_by_user_id=actor.user_id,
    )
    session.add(plan)
    session.flush()

    version = _new_version(
        session,
        plan=plan,
        sale=sale,
        actor=actor,
        version_number=1,
        reservation_treatment=reservation_treatment,
        origin_type=origin_type,
        source=source,
        change_reason=None,
        effective_date=effective_date,
    )
    record_event(
        session,
        action="payment_plan.created",
        entity_type="payment_plan",
        entity_id=plan.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "plan_number": plan.plan_number,
            "sale_contract_id": sale.id,
            "sale_number": sale.sale_number,
            "reservation_treatment": reservation_treatment,
            "origin_type": origin_type,
            "source_version_id": source.id if source else None,
            "effective_date": version.effective_date,
        },
    )
    return plan, version


def _resolve_copy_source(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    origin_type: str,
    source_version_id: uuid.UUID | None,
) -> PaymentPlanVersion | None:
    """Load the version a new schedule is being started from, if any.

    Only a settled schedule of the same project may be copied. A draft is not a
    pattern anybody has agreed to, and a rejected one is a pattern somebody
    explicitly refused.

    Copying reads: the fractions, the trigger definitions, the labels and the
    timing of somebody else's negotiated schedule all cross over. So the source
    must pass exactly the visibility a plan read passes. Otherwise a
    phase-scoped preparer who guessed a version identifier could lift the
    commercial shape of a deal in a phase they were never granted — and would
    not even have to read the plan to do it, because the copy hands them the
    structure directly.
    """
    if origin_type != ORIGIN_COPIED:
        if source_version_id is not None:
            raise ValidationError(
                "A source version only applies when the plan is copied from another."
            )
        return None
    if source_version_id is None:
        raise ValidationError("Copying a plan needs the version it is copied from.")
    source = session.scalars(
        select(PaymentPlanVersion).where(
            PaymentPlanVersion.id == source_version_id,
            PaymentPlanVersion.project_id == project.id,
        )
    ).first()
    if source is None:
        raise NotFoundError(_NO_COPY_SOURCE)
    # Same refusal for a source that is not there and one the caller may not
    # see, so a hidden phase is not confirmed by the difference.
    visible = _visible_plan_or_none(
        session, project=project, plan_id=source.payment_plan_id, actor=actor
    )
    if visible is None:
        raise NotFoundError(_NO_COPY_SOURCE)
    if source.status not in VERSION_COPYABLE:
        raise ConflictError(
            "Only an approved, active or superseded schedule can be copied. "
            f"That one is {source.status}."
        )
    return source


# --------------------------------------------------------------------------- #
# Versions
# --------------------------------------------------------------------------- #


def _new_version(
    session: Session,
    *,
    plan: PaymentPlan,
    sale: SaleContract,
    actor: ActorContext,
    version_number: int,
    reservation_treatment: str,
    origin_type: str,
    source: PaymentPlanVersion | None,
    change_reason: str | None,
    effective_date: date | None,
) -> PaymentPlanVersion:
    """Create a draft version on the sale's frozen basis, copying rows if asked.

    ``effective_date`` is the contractual date the schedule starts governing
    from, not the date it was typed. Omitted means today; supplied means the
    parties agreed a date, and it is taken as given. A future one is honoured
    by refusing activation until it arrives — the control already in
    :func:`activate_version` — which is what makes an approved-but-not-yet-in-
    force schedule expressible at all.
    """
    version = PaymentPlanVersion(
        project_id=plan.project_id,
        payment_plan_id=plan.id,
        version_number=version_number,
        status=VERSION_DRAFT,
        effective_date=effective_date or business_today(),
        currency_id=sale.currency_id,
        contract_value_covered=sale.net_contract_price_ex_tax,
        tax_total_snapshot=sale.tax_total,
        buyer_fee_total_snapshot=sale.buyer_fee_total,
        total_buyer_payable_snapshot=sale.total_contract_price,
        allocation_mode=source.allocation_mode if source else ALLOCATION_PERCENTAGE,
        charge_allocation_mode=source.charge_allocation_mode if source else CHARGE_PRO_RATA,
        reservation_treatment=reservation_treatment,
        origin_type=origin_type,
        source_version_id=source.id if source else None,
        change_reason=change_reason,
        created_by_user_id=actor.user_id,
    )
    session.add(version)
    session.flush()
    if source is not None:
        _copy_installments(session, source=source, target=version, sale=sale)
    return version


def _copy_installments(
    session: Session,
    *,
    source: PaymentPlanVersion,
    target: PaymentPlanVersion,
    sale: SaleContract,
) -> None:
    """Copy a schedule's SHAPE onto a new version, re-deriving every amount.

    The structure travels — sequence, labels, triggers, offsets, grace — and the
    money does not. The target sale may be worth a different amount in a
    different currency, so copying its predecessor's figures would produce a
    schedule that reconciles against the wrong contract. The fractions are what
    the parties actually agreed to in shape; the amounts are recomputed from
    them against this sale's frozen basis.
    """
    rows = installments_of(session, version_id=source.id)
    if not rows:
        return
    fractions = [row.principal_fraction for row in rows]
    principals = schedule.allocate(target.contract_value_covered, fractions)
    taxes = _charge_lines(target, fractions, target.tax_total_snapshot)
    fees = _charge_lines(target, fractions, target.buyer_fee_total_snapshot)
    for index, row in enumerate(rows):
        session.add(
            PaymentPlanInstallment(
                project_id=target.project_id,
                payment_plan_version_id=target.id,
                sequence=row.sequence,
                label=row.label,
                trigger_type=row.trigger_type,
                trigger_reference=row.trigger_reference,
                offset_days=row.offset_days,
                recurrence_index=row.recurrence_index,
                contractual_due_date=_contractual_date_for(
                    trigger_type=row.trigger_type,
                    supplied=row.contractual_due_date,
                    offset_days=row.offset_days,
                    sale=sale,
                ),
                forecast_due_date=None,
                actual_due_date=None,
                grace_days=row.grace_days,
                principal_amount=principals[index],
                principal_fraction=fractions[index],
                tax_amount=taxes[index],
                fee_amount=fees[index],
                trigger_status=_initial_trigger_status(row.trigger_type),
                owner_user_id=None,
            )
        )
    session.flush()


def _charge_lines(
    version: PaymentPlanVersion, fractions: list[Decimal], total: Decimal
) -> list[Decimal]:
    """Spread a frozen charge across the schedule, or leave it to be typed."""
    if version.charge_allocation_mode == CHARGE_PRO_RATA:
        return schedule.allocate(total, fractions)
    return [schedule.ZERO_MONEY for _ in fractions]


def create_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    change_reason: str,
    reservation_treatment: str | None,
    effective_date: date | None,
    correlation_id: uuid.UUID,
) -> PaymentPlanVersion:
    """Open a revision, copying the standing schedule as its starting point.

    The active version keeps governing the sale throughout. There is never a
    window in which a contracted buyer has no schedule merely because somebody
    is drafting its replacement.
    """
    permissions.require_plan_writer(actor)
    project = lock_project(session, project.id)
    plan = _visible_plan(session, project=project, plan_id=plan_id, actor=actor)
    plan = _lock_plan(session, project_id=project.id, plan_id=plan.id)

    if open_version(session, plan_id=plan.id) is not None:
        raise ConflictError(
            "This plan already has a version in preparation. Finish or reject it first."
        )
    sale = session.get(SaleContract, plan.sale_contract_id)
    if sale is None:
        raise NotFoundError("Sale contract not found.")
    _require_plannable_sale(sale)

    standing = active_version(session, plan_id=plan.id)
    highest = session.scalar(
        select(func.max(PaymentPlanVersion.version_number)).where(
            PaymentPlanVersion.payment_plan_id == plan.id
        )
    )
    version = _new_version(
        session,
        plan=plan,
        sale=sale,
        actor=actor,
        version_number=(highest or 0) + 1,
        reservation_treatment=(
            reservation_treatment
            if reservation_treatment is not None
            else (standing.reservation_treatment if standing else "reference_only")
        ),
        origin_type=ORIGIN_COPIED if standing else ORIGIN_CUSTOM,
        source=standing,
        change_reason=change_reason,
        effective_date=effective_date,
    )
    record_event(
        session,
        action="payment_plan.version_created",
        entity_type="payment_plan_version",
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=change_reason,
        after={
            "plan_number": plan.plan_number,
            "version_number": version.version_number,
            "copied_from": standing.id if standing else None,
            "effective_date": version.effective_date,
        },
    )
    return version


def get_version(
    session: Session,
    *,
    project: Project,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    actor: ActorContext,
) -> tuple[PaymentPlanVersion, PaymentPlan]:
    """One version of one plan the caller may see."""
    permissions.require_plan_reader(actor)
    return _visible_version_for_plan(
        session, project=project, plan_id=plan_id, version_id=version_id, actor=actor
    )


# --------------------------------------------------------------------------- #
# The draft schedule
# --------------------------------------------------------------------------- #


def _contractual_date_for(
    *,
    trigger_type: str,
    supplied: date | None,
    offset_days: int | None,
    sale: SaleContract,
) -> date | None:
    """The contractual due date a trigger implies, resolved once and stored.

    A relative trigger is resolved against the contract date here rather than
    left for collections to recompute later: the SPA date does not move, so the
    answer does not change, and storing it means one reading of the contract
    instead of one per report.
    """
    if trigger_type == TRIGGER_DAYS_AFTER_SPA:
        return sale.contract_date + timedelta(days=offset_days or 0)
    if trigger_type in {
        TRIGGER_FIXED_DATE,
        TRIGGER_RECURRING_MONTHLY,
        TRIGGER_RECURRING_QUARTERLY,
    }:
        return supplied
    return None


def _initial_trigger_status(trigger_type: str) -> str:
    """Where an instalment starts: known by the calendar, or waiting on an event."""
    return TRIGGER_SCHEDULED if trigger_type in TRIGGER_DATE_BASED else TRIGGER_AWAITING


def _validate_row(row: InstallmentDraft, *, sale: SaleContract) -> None:
    """Refuse a trigger configuration that cannot describe a due date."""
    if row.trigger_type == TRIGGER_DAYS_AFTER_SPA and row.offset_days is None:
        raise ValidationError(
            f"Instalment {row.sequence} is dated from the SPA but has no number of days."
        )
    dated = {TRIGGER_FIXED_DATE, TRIGGER_RECURRING_MONTHLY, TRIGGER_RECURRING_QUARTERLY}
    if row.trigger_type in dated and row.contractual_due_date is None:
        raise ValidationError(f"Instalment {row.sequence} has no due date.")
    if row.trigger_type == TRIGGER_CONSTRUCTION_MILESTONE and not row.trigger_reference:
        raise ValidationError(
            f"Instalment {row.sequence} is triggered by a construction milestone "
            "but does not say which one."
        )
    if row.trigger_type == TRIGGER_MANUAL_EVENT and not row.trigger_reference:
        raise ValidationError(
            f"Instalment {row.sequence} needs a description of the event that makes it due."
        )


class InstallmentDraft:
    """One row a preparer typed, before it is money.

    A plain carrier so the service can validate and derive without the API's
    request model reaching this far in, and without a dataclass import that
    would only ever be used here.
    """

    __slots__ = (
        "contractual_due_date",
        "fee_amount",
        "forecast_due_date",
        "grace_days",
        "label",
        "offset_days",
        "owner_user_id",
        "principal_amount",
        "principal_fraction",
        "recurrence_index",
        "sequence",
        "tax_amount",
        "trigger_reference",
        "trigger_type",
    )

    def __init__(self, **values: object) -> None:
        for name in self.__slots__:
            setattr(self, name, values.get(name))


def replace_schedule(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    rows: list[InstallmentDraft],
    allocation_mode: str,
    charge_allocation_mode: str,
    correlation_id: uuid.UUID,
) -> PaymentPlanVersion:
    """Replace a draft version's whole schedule, atomically.

    Whole-schedule replacement rather than per-row editing, because a payment
    schedule is one negotiated object: inserting a row changes what every other
    row is worth, and six separate requests would leave the plan reconciling
    only at the end of a sequence nobody can guarantee completes.

    Only a draft may be replaced. Once submitted there is an approved or
    pending financial schedule, and the way to change it is a new version.
    """
    permissions.require_plan_writer(actor)
    project = lock_project(session, project.id)
    version, plan = _visible_version_for_plan(
        session, project=project, plan_id=plan_id, version_id=version_id, actor=actor
    )
    _lock_plan(session, project_id=project.id, plan_id=plan.id)
    version = _lock_version(session, project_id=project.id, version_id=version.id)
    if version.status != VERSION_DRAFT:
        raise ConflictError(_NOT_DRAFT)

    sale = session.get(SaleContract, plan.sale_contract_id)
    if sale is None:
        raise NotFoundError("Sale contract not found.")

    if not rows:
        raise ValidationError("A payment plan needs at least one instalment.")
    sequences = [row.sequence for row in rows]
    if len(set(sequences)) != len(sequences):
        raise ValidationError("Two instalments share a sequence number.")
    for row in rows:
        _validate_row(row, sale=sale)
        _require_owner_eligible(session, user_id=row.owner_user_id)

    version.allocation_mode = allocation_mode
    version.charge_allocation_mode = charge_allocation_mode

    ordered = sorted(rows, key=lambda row: row.sequence)
    principals, fractions = _derive_money(version, ordered)
    taxes, fees = _derive_charges(version, ordered, fractions)

    session.query(PaymentPlanInstallment).filter(
        PaymentPlanInstallment.payment_plan_version_id == version.id
    ).delete(synchronize_session=False)

    for index, row in enumerate(ordered):
        session.add(
            PaymentPlanInstallment(
                project_id=project.id,
                payment_plan_version_id=version.id,
                sequence=row.sequence,
                label=row.label,
                trigger_type=row.trigger_type,
                trigger_reference=row.trigger_reference,
                offset_days=row.offset_days,
                recurrence_index=row.recurrence_index,
                contractual_due_date=_contractual_date_for(
                    trigger_type=row.trigger_type,
                    supplied=row.contractual_due_date,
                    offset_days=row.offset_days,
                    sale=sale,
                ),
                forecast_due_date=row.forecast_due_date,
                actual_due_date=None,
                grace_days=row.grace_days or 0,
                principal_amount=principals[index],
                principal_fraction=fractions[index],
                tax_amount=taxes[index],
                fee_amount=fees[index],
                trigger_status=_initial_trigger_status(row.trigger_type),
                owner_user_id=row.owner_user_id,
            )
        )
    session.flush()

    reconciliation = reconcile_version(session, version=version)
    record_event(
        session,
        action="payment_plan.schedule_saved",
        entity_type="payment_plan_version",
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "plan_number": plan.plan_number,
            "version_number": version.version_number,
            "installment_count": reconciliation.installment_count,
            "scheduled_principal_total": reconciliation.scheduled_principal_total,
            "is_reconciled": reconciliation.is_reconciled,
        },
    )
    return version


def _derive_money(
    version: PaymentPlanVersion, rows: list[InstallmentDraft]
) -> tuple[list[Decimal], list[Decimal]]:
    """Turn whichever figure the preparer typed into the pair that gets stored.

    The allocation mode decides which column is authoritative; the other is
    derived here so a stored amount and its percentage can never disagree.
    """
    if version.allocation_mode == ALLOCATION_PERCENTAGE:
        fractions = [
            schedule.fraction(_required(row.principal_fraction, row, "a percentage"))
            for row in rows
        ]
        principals = schedule.allocate(version.contract_value_covered, fractions)
        return principals, fractions
    principals = [schedule.money(_required(row.principal_amount, row, "an amount")) for row in rows]
    fractions = schedule.derive_fractions(version.contract_value_covered, principals)
    return principals, fractions


def _required(value: Decimal | None, row: InstallmentDraft, what: str) -> Decimal:
    if value is None:
        raise ValidationError(f"Instalment {row.sequence} needs {what}.")
    return value


def _derive_charges(
    version: PaymentPlanVersion, rows: list[InstallmentDraft], fractions: list[Decimal]
) -> tuple[list[Decimal], list[Decimal]]:
    """Spread the frozen tax and fees, or take what the preparer typed.

    Pro rata follows the principal split and gives the rounding residual to the
    last line, so the schedule reconciles by construction. Manual is taken
    verbatim and checked at submission — a manual schedule that is a penny out
    is shown the penny rather than being silently corrected, because somebody
    chose those numbers for a reason.
    """
    if version.charge_allocation_mode == CHARGE_PRO_RATA:
        return (
            schedule.allocate(version.tax_total_snapshot, fractions),
            schedule.allocate(version.buyer_fee_total_snapshot, fractions),
        )
    taxes = [schedule.money(row.tax_amount or schedule.ZERO_MONEY) for row in rows]
    fees = [schedule.money(row.fee_amount or schedule.ZERO_MONEY) for row in rows]
    return taxes, fees


def _require_owner_eligible(session: Session, *, user_id: uuid.UUID | None) -> None:
    """Refuse an instalment owner who does not do this work.

    An arbitrary user identifier is not somebody who chases a payment, and a
    schedule assigned to a departed administrator is a schedule nobody is
    chasing.
    """
    if user_id is None:
        return
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise ValidationError("The instalment owner is not an active user.")
    roles = set(
        session.scalars(
            select(Role.key)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
    )
    if not roles.intersection(permissions.INSTALLMENT_OWNER_ROLES):
        raise ValidationError("An instalment can only be owned by Collections or Sales Operations.")


def series_preview(
    *, frequency: str, first_due_date: date, count: int, label_prefix: str
) -> list[schedule.SeriesRow]:
    """Propose the dates of a recurring series. Writes nothing.

    Structure only — no amounts. The version's allocation mode owns the money,
    and a helper that also decided what each row was worth would be a second
    answer to a question that already has one.
    """
    months = RECURRENCE_MONTHS.get(frequency)
    if months is None:
        raise ValidationError("A recurring series is monthly or quarterly.")
    return schedule.recurring_series(
        first_due_date=first_due_date,
        count=count,
        months_between=months,
        label_prefix=label_prefix,
    )


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #


def submit_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> PaymentPlanVersion:
    """Put a reconciled draft forward for sanction."""
    permissions.require_plan_writer(actor)
    project = lock_project(session, project.id)
    version, plan = _visible_version_for_plan(
        session, project=project, plan_id=plan_id, version_id=version_id, actor=actor
    )
    _lock_plan(session, project_id=project.id, plan_id=plan.id)
    version = _lock_version(session, project_id=project.id, version_id=version.id)
    if version.status != VERSION_DRAFT:
        raise ConflictError("Only a draft schedule can be put forward.")
    _require_reconciled(session, version=version)

    version.status = VERSION_SUBMITTED
    version.submitted_at = _now()
    version.submitted_by_user_id = actor.user_id
    session.flush()
    record_event(
        session,
        action="payment_plan.submitted",
        entity_type="payment_plan_version",
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={"plan_number": plan.plan_number, "version_number": version.version_number},
    )
    return version


def approve_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> PaymentPlanVersion:
    """Sanction a submitted schedule, after re-proving it from the stored rows.

    Approval does not trust what submission concluded. The sale can be amended
    between the two, and the schedule is checked again against the contract's
    current figures as well as its own totals — an approval of stale numbers is
    worse than no approval, because it carries a signature.
    """
    permissions.require_plan_approver(actor)
    project = lock_project(session, project.id)
    version, plan = _visible_version_for_plan(
        session, project=project, plan_id=plan_id, version_id=version_id, actor=actor
    )
    _lock_plan(session, project_id=project.id, plan_id=plan.id)
    version = _lock_version(session, project_id=project.id, version_id=version.id)
    if version.status != VERSION_SUBMITTED:
        raise ConflictError("Only a submitted schedule can be approved.")
    permissions.require_different_checker(actor, maker_user_id=version.submitted_by_user_id)

    sale = _lock_sale(session, project_id=project.id, sale_id=plan.sale_contract_id)
    _require_basis_unchanged(version, sale=sale)
    _require_reconciled(session, version=version)

    version.status = VERSION_APPROVED
    version.approved_at = _now()
    version.approved_by_user_id = actor.user_id
    session.flush()
    record_event(
        session,
        action="payment_plan.approved",
        entity_type="payment_plan_version",
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={"plan_number": plan.plan_number, "version_number": version.version_number},
    )
    return version


def reject_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> PaymentPlanVersion:
    """Refuse a submitted schedule. It stays readable; the revision is new."""
    permissions.require_plan_approver(actor)
    project = lock_project(session, project.id)
    version, plan = _visible_version_for_plan(
        session, project=project, plan_id=plan_id, version_id=version_id, actor=actor
    )
    _lock_plan(session, project_id=project.id, plan_id=plan.id)
    version = _lock_version(session, project_id=project.id, version_id=version.id)
    if version.status != VERSION_SUBMITTED:
        raise ConflictError("Only a submitted schedule can be refused.")
    permissions.require_different_checker(actor, maker_user_id=version.submitted_by_user_id)

    version.status = VERSION_REJECTED
    version.rejected_at = _now()
    version.rejected_by_user_id = actor.user_id
    version.rejection_reason = reason
    session.flush()
    record_event(
        session,
        action="payment_plan.rejected",
        entity_type="payment_plan_version",
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={"plan_number": plan.plan_number, "version_number": version.version_number},
    )
    return version


def _lock_sale(session: Session, *, project_id: uuid.UUID, sale_id: uuid.UUID) -> SaleContract:
    sale = session.scalars(
        select(SaleContract)
        .where(SaleContract.id == sale_id, SaleContract.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if sale is None:
        raise NotFoundError("Sale contract not found.")
    return sale


def _require_basis_unchanged(version: PaymentPlanVersion, *, sale: SaleContract) -> None:
    """Refuse to sanction a schedule written against figures the sale has left.

    The version froze the contract's currency and totals when it was created. If
    the contract has since been amended, the schedule reconciles against
    something that is no longer true and must be rebuilt rather than blessed.
    """
    mismatches: list[str] = []
    if version.currency_id != sale.currency_id:
        mismatches.append("currency")
    if version.contract_value_covered != sale.net_contract_price_ex_tax:
        mismatches.append("contract value")
    if version.tax_total_snapshot != sale.tax_total:
        mismatches.append("tax")
    if version.buyer_fee_total_snapshot != sale.buyer_fee_total:
        mismatches.append("buyer fees")
    if version.total_buyer_payable_snapshot != sale.total_contract_price:
        mismatches.append("total payable")
    if mismatches:
        raise ConflictError(
            "The contract has changed since this schedule was written "
            f"({', '.join(mismatches)}). Create a new version against the current terms."
        )


def activate_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> PaymentPlanVersion:
    """Make an approved schedule the one governing the sale.

    Everything is re-read under lock and re-proved: the sale is still active,
    its figures still match the frozen basis, and the schedule still adds up.
    The previous standing version is superseded in the same transaction, so
    there is never a moment with two active schedules or none.

    Activation is also where date-based triggers materialise their actual due
    dates. Contingent ones do not: a construction milestone, a handover or a
    title transfer is still waiting for something to happen.
    """
    permissions.require_plan_approver(actor)
    project = lock_project(session, project.id)
    version, plan = _visible_version_for_plan(
        session, project=project, plan_id=plan_id, version_id=version_id, actor=actor
    )
    plan = _lock_plan(session, project_id=project.id, plan_id=plan.id)
    version = _lock_version(session, project_id=project.id, version_id=version.id)
    _require_no_collection_activity(plan, version=version)
    return _activate_locked(
        session,
        project=project,
        actor=actor,
        plan=plan,
        version=version,
        correlation_id=correlation_id,
    )


def _require_no_collection_activity(plan: PaymentPlan, *, version: PaymentPlanVersion) -> None:
    """Refuse the ordinary activation path once cash has arrived on this plan.

    Not bureaucracy, and not a rule about who may decide. Activating a
    replacement version swaps in instalments with new identifiers, and every
    receipt allocation already made points at the old ones — so a schedule that
    was half collected would come back on screen reading as entirely unpaid,
    with the cash still in the ledger and no longer visible against anything.

    The refusal names the way through, because there is one: PR-MVP-07's
    restructure carries the allocations across in the same transaction as the
    activation, and refuses outright if a single unit of cash cannot be placed.

    Activating the *first* version is untouched — there is nothing to carry.
    """
    if plan.collections_started_at is None:
        return
    if active_version_id_of(version) is None:
        return
    raise ConflictError(
        "This plan has confirmed collection activity. Activate the revision through "
        "a Collections restructure, so the cash already received is carried onto the "
        "new schedule in the same transaction."
    )


def active_version_id_of(version: PaymentPlanVersion) -> uuid.UUID | None:
    """The version this one would replace, read from the row being activated.

    A separate function only so the guard above reads as one sentence: a first
    activation has no predecessor and nothing to carry, and the value that says
    so is the source version the revision was copied from.
    """
    return version.source_version_id


def _activate_locked(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan: PaymentPlan,
    version: PaymentPlanVersion,
    correlation_id: uuid.UUID,
) -> PaymentPlanVersion:
    """Activate a version whose plan and version rows are already locked.

    Extracted so PR-MVP-07's restructure can reach exactly these checks — the
    sale is still active, the frozen basis still matches, the schedule still
    reconciles, the predecessor is superseded in the same transaction — without
    a second copy of them drifting out of step with this one. The only thing it
    does not apply is the collections guard, which is the whole reason the
    restructure exists.
    """
    if version.status != VERSION_APPROVED:
        raise ConflictError("Only an approved schedule can be activated.")

    today = business_today()
    if version.effective_date > today:
        raise ConflictError(
            f"This schedule takes effect on {version.effective_date.isoformat()}. "
            "It cannot be activated before then."
        )

    sale = _lock_sale(session, project_id=project.id, sale_id=plan.sale_contract_id)
    if sale.status != SALE_ACTIVE:
        raise ConflictError(
            f"A payment plan governs a live contract. This sale is {sale.status.replace('_', ' ')}."
        )
    _require_basis_unchanged(version, sale=sale)
    _require_reconciled(session, version=version)

    standing = active_version(session, plan_id=plan.id)
    if standing is not None and standing.id != version.id:
        standing = _lock_version(session, project_id=project.id, version_id=standing.id)
        standing.status = VERSION_SUPERSEDED
        standing.superseded_at = _now()
        session.flush()
        record_event(
            session,
            action="payment_plan.superseded",
            entity_type="payment_plan_version",
            entity_id=standing.id,
            correlation_id=correlation_id,
            actor_user_id=actor.user_id,
            after={
                "plan_number": plan.plan_number,
                "version_number": standing.version_number,
                "replaced_by": version.version_number,
            },
        )

    version.status = VERSION_ACTIVE
    version.activated_at = _now()
    version.activated_by_user_id = actor.user_id
    session.flush()

    materialised = _materialise_dated_triggers(session, version=version)
    record_event(
        session,
        action="payment_plan.activated",
        entity_type="payment_plan_version",
        entity_id=version.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "plan_number": plan.plan_number,
            "version_number": version.version_number,
            "dated_installments_materialised": materialised,
            "superseded_version": standing.version_number if standing else None,
        },
    )
    return version


def _materialise_dated_triggers(session: Session, *, version: PaymentPlanVersion) -> int:
    """Fill in the actual due date for every instalment the calendar settles.

    Fixed, SPA-relative and recurring instalments are due on their contractual
    date and nothing else has to happen. Contingent ones are deliberately left
    alone — that is the difference this module exists to keep.
    """
    count = 0
    for row in installments_of(session, version_id=version.id):
        if row.trigger_type in TRIGGER_DATE_BASED and row.contractual_due_date is not None:
            row.actual_due_date = row.contractual_due_date
            row.trigger_status = TRIGGER_SCHEDULED
            count += 1
    session.flush()
    return count


# --------------------------------------------------------------------------- #
# Triggers
# --------------------------------------------------------------------------- #


def refresh_triggers(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> tuple[list[PaymentPlanInstallment], list[PaymentPlanInstallment]]:
    """Resolve contingent instalments against events that have actually happened.

    An explicit action, never a background job and never a side effect of a GET.
    Somebody asks, and the answer is computed from records that already exist:
    a completed handover, an effective title transfer. Returns what changed and
    what is still waiting, so the screen can say both.

    Construction milestones are not resolved here at any cost. PR-MVP-09 owns
    certification; until it exists there is no record that could say a milestone
    was reached, and a forecast date is not one.
    """
    permissions.require_plan_operator(actor)
    project = lock_project(session, project.id)
    plan = _visible_plan(session, project=project, plan_id=plan_id, actor=actor)
    _lock_plan(session, project_id=project.id, plan_id=plan.id)
    version = active_version(session, plan_id=plan.id)
    if version is None:
        raise ConflictError("This plan has no active schedule to refresh.")

    handover_date = _completed_handover_date(session, sale_id=plan.sale_contract_id)
    transfer_date = _title_transfer_date(session, sale_id=plan.sale_contract_id)

    changed: list[PaymentPlanInstallment] = []
    waiting: list[PaymentPlanInstallment] = []
    for row in installments_of(session, version_id=version.id):
        if row.trigger_status == TRIGGER_TRIGGERED or row.trigger_type in TRIGGER_DATE_BASED:
            continue
        resolved = None
        if row.trigger_type == TRIGGER_HANDOVER:
            resolved = handover_date
        elif row.trigger_type == TRIGGER_TITLE_TRANSFER:
            resolved = transfer_date
        # Construction milestones and manual events are never resolved from
        # here: one needs PR-MVP-09, the other needs an approved attestation.
        if resolved is None:
            waiting.append(row)
            continue
        row.actual_due_date = resolved
        row.trigger_status = TRIGGER_TRIGGERED
        changed.append(row)
    session.flush()

    if changed:
        record_event(
            session,
            action="payment_plan.triggers_refreshed",
            entity_type="payment_plan_version",
            entity_id=version.id,
            correlation_id=correlation_id,
            actor_user_id=actor.user_id,
            after={
                "plan_number": plan.plan_number,
                "triggered": [
                    {"sequence": row.sequence, "actual_due_date": row.actual_due_date}
                    for row in changed
                ],
                "still_awaiting": len(waiting),
            },
        )
    return changed, waiting


def _completed_handover_date(session: Session, *, sale_id: uuid.UUID) -> date | None:
    """The date the unit was actually handed over, or nothing.

    A scheduled handover date is a plan, and a readiness date is an opinion.
    Only a completed handover makes a handover-triggered instalment due.
    """
    handover = session.scalars(
        select(HandoverRecord).where(HandoverRecord.sale_contract_id == sale_id)
    ).first()
    if handover is None or handover.status != HANDOVER_HANDED_OVER:
        return None
    return handover.handover_date


def _title_transfer_date(session: Session, *, sale_id: uuid.UUID) -> date | None:
    """The date title actually transferred, per the effective legal timeline.

    Read through the sales module's own contract, so a withdrawn registration
    is excluded exactly as it is everywhere else. ``transfer_pending`` and
    ``registered`` do not count: the contract's trigger is the transfer.
    """
    for event in sales_service.effective_legal_events(session, sale_id=sale_id):
        if event.event_type == EVENT_TRANSFERRED:
            return event.event_date
    return None


def submit_manual_trigger(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    installment_id: uuid.UUID,
    event_date: date,
    evidence_reference: str,
    reason: str,
    correlation_id: uuid.UUID,
) -> InstallmentTriggerEvent:
    """Attest that the event a manually triggered instalment waits on occurred.

    Only for ``manual_approved_event``. A construction milestone cannot be
    attested this way: certifying construction is PR-MVP-09's job, and letting
    an operator type one here would manufacture a certification this system has
    no basis for.

    The attestation is of something that *has happened*, so its date cannot be
    in the future. A future date is not an early attestation, it is a forecast,
    and instalments already carry a forecast date for exactly that. Accepting
    one here would make money contractually due for an event nobody has
    witnessed — and would need a scheduler to later decide it had occurred,
    which this module does not have and should not grow.
    """
    permissions.require_plan_operator(actor)
    today = business_today()
    if event_date > today:
        raise ValidationError(
            f"An attestation records an event that has happened, so it cannot be dated "
            f"{event_date.isoformat()}, which is after {today.isoformat()}. "
            "Use the forecast date for an event still expected."
        )
    project = lock_project(session, project.id)
    installment, version, plan = _visible_installment_for_plan(
        session, project=project, plan_id=plan_id, installment_id=installment_id, actor=actor
    )
    if version.status != VERSION_ACTIVE:
        raise ConflictError("Only an instalment on the active schedule can be triggered.")
    if installment.trigger_type != TRIGGER_MANUAL_EVENT:
        raise ConflictError(
            "Only an instalment that waits on a manually approved event can be triggered this way."
        )
    if installment.trigger_status == TRIGGER_TRIGGERED:
        raise ConflictError("This instalment has already been triggered.")
    standing = _standing_trigger_event(session, installment_id=installment.id)
    if standing is not None:
        raise ConflictError("An attestation for this instalment is already outstanding.")

    event = InstallmentTriggerEvent(
        project_id=project.id,
        installment_id=installment.id,
        event_date=event_date,
        evidence_reference=evidence_reference,
        reason=reason,
        status=TRIGGER_EVENT_SUBMITTED,
        submitted_by_user_id=actor.user_id,
    )
    session.add(event)
    session.flush()
    record_event(
        session,
        action="installment_trigger.submitted",
        entity_type="installment_trigger_event",
        entity_id=event.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={
            "plan_number": plan.plan_number,
            "sequence": installment.sequence,
            "event_date": event_date,
            "evidence_reference": evidence_reference,
        },
    )
    return event


def _standing_trigger_event(
    session: Session, *, installment_id: uuid.UUID
) -> InstallmentTriggerEvent | None:
    return session.scalars(
        select(InstallmentTriggerEvent).where(
            InstallmentTriggerEvent.installment_id == installment_id,
            InstallmentTriggerEvent.status.in_((TRIGGER_EVENT_SUBMITTED, TRIGGER_EVENT_APPROVED)),
        )
    ).first()


def approve_manual_trigger(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    event_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> InstallmentTriggerEvent:
    """Sanction an attestation, and make the instalment due, in one transaction.

    Maker and checker are different people. The System Administrator is not a
    checker: administering a platform is not authority to declare that a
    contractual event occurred.

    The version is re-read under lock and re-required to be active, because
    submission and approval are separated in time and a revision can be
    activated between them. Approving against a schedule that has since been
    superseded would make an instalment due on terms the sale no longer runs
    on — a date written into a schedule nobody is being held to.
    """
    permissions.require_plan_approver(actor)
    project = lock_project(session, project.id)
    event, installment, version, plan = _visible_trigger_event_for_plan(
        session, project=project, plan_id=plan_id, event_id=event_id, actor=actor
    )
    _lock_plan(session, project_id=project.id, plan_id=plan.id)
    version = _lock_version(session, project_id=project.id, version_id=version.id)
    event = _lock_trigger_event(session, project_id=project.id, event_id=event.id)
    installment = _relock_installment(session, installment_id=installment.id)
    if event.status != TRIGGER_EVENT_SUBMITTED:
        raise ConflictError("Only a submitted attestation can be approved.")
    if version.status != VERSION_ACTIVE:
        raise ConflictError(
            "This attestation belongs to a superseded payment-plan version and can no "
            "longer be approved."
        )
    permissions.require_different_checker(actor, maker_user_id=event.submitted_by_user_id)

    event.status = TRIGGER_EVENT_APPROVED
    event.approved_by_user_id = actor.user_id
    event.approved_at = _now()
    installment.actual_due_date = event.event_date
    installment.trigger_status = TRIGGER_TRIGGERED
    session.flush()
    record_event(
        session,
        action="installment_trigger.approved",
        entity_type="installment_trigger_event",
        entity_id=event.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "plan_number": plan.plan_number,
            "version_number": version.version_number,
            "sequence": installment.sequence,
            "actual_due_date": installment.actual_due_date,
        },
    )
    return event


def reverse_manual_trigger(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    event_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> InstallmentTriggerEvent:
    """Withdraw an attestation that should not have been made.

    The event is not deleted — somebody made that attestation and the record of
    it is the point. The instalment goes back to waiting and its actual due
    date is cleared, which is safe today because no receipt can yet have been
    allocated against it. PR-MVP-07 will need a stronger rule once cash exists.
    """
    permissions.require_plan_approver(actor)
    project = lock_project(session, project.id)
    event, installment, version, plan = _visible_trigger_event_for_plan(
        session, project=project, plan_id=plan_id, event_id=event_id, actor=actor
    )
    _lock_plan(session, project_id=project.id, plan_id=plan.id)
    _lock_version(session, project_id=project.id, version_id=version.id)
    event = _lock_trigger_event(session, project_id=project.id, event_id=event.id)
    installment = _relock_installment(session, installment_id=installment.id)
    if event.status != TRIGGER_EVENT_APPROVED:
        raise ConflictError("Only an approved attestation can be withdrawn.")

    event.status = TRIGGER_EVENT_REVERSED
    event.reversed_by_user_id = actor.user_id
    event.reversed_at = _now()
    event.reversal_reason = reason
    installment.actual_due_date = None
    installment.trigger_status = TRIGGER_AWAITING
    session.flush()
    record_event(
        session,
        action="installment_trigger.reversed",
        entity_type="installment_trigger_event",
        entity_id=event.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={"plan_number": plan.plan_number, "sequence": installment.sequence},
    )
    return event


def _relock_installment(session: Session, *, installment_id: uuid.UUID) -> PaymentPlanInstallment:
    """Re-read an instalment's committed state under the version lock already held."""
    row = session.scalars(
        select(PaymentPlanInstallment)
        .where(PaymentPlanInstallment.id == installment_id)
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError(_NO_INSTALLMENT)
    return row


def trigger_events_of(
    session: Session, *, installment_id: uuid.UUID
) -> list[InstallmentTriggerEvent]:
    """Every attestation ever made about one instalment, newest first.

    Takes no actor: callers reach it only through a loader that has already
    proved the instalment belongs to a plan this caller may see.
    """
    return list(
        session.scalars(
            select(InstallmentTriggerEvent)
            .where(InstallmentTriggerEvent.installment_id == installment_id)
            .order_by(InstallmentTriggerEvent.submitted_at.desc())
        )
    )


def trigger_events_by_installment(
    session: Session, *, version_id: uuid.UUID
) -> dict[uuid.UUID, list[InstallmentTriggerEvent]]:
    """Every attestation on a version's schedule, grouped by instalment.

    One query for the whole version rather than one per manual instalment. A
    hundred-row schedule drawn a request at a time is a screen that gets slower
    the more there is to decide on, which is exactly backwards: the plans with
    the most pending attestations are the ones an approver opens most.
    """
    grouped: dict[uuid.UUID, list[InstallmentTriggerEvent]] = {}
    for event in session.scalars(
        select(InstallmentTriggerEvent)
        .join(
            PaymentPlanInstallment,
            PaymentPlanInstallment.id == InstallmentTriggerEvent.installment_id,
        )
        .where(PaymentPlanInstallment.payment_plan_version_id == version_id)
        .order_by(InstallmentTriggerEvent.submitted_at.desc())
    ):
        grouped.setdefault(event.installment_id, []).append(event)
    return grouped


def trigger_events_for_installment(
    session: Session,
    *,
    project: Project,
    plan_id: uuid.UUID,
    installment_id: uuid.UUID,
    actor: ActorContext,
) -> list[InstallmentTriggerEvent]:
    """One instalment's attestation history, once its parentage is proved.

    The instalment is resolved *through* the plan in the path rather than by
    its own identifier, so pairing a visible plan with someone else's
    instalment identifier reads nothing.
    """
    permissions.require_plan_reader(actor)
    installment, _version, _plan = _visible_installment_for_plan(
        session, project=project, plan_id=plan_id, installment_id=installment_id, actor=actor
    )
    return trigger_events_of(session, installment_id=installment.id)


# --------------------------------------------------------------------------- #
# Operational maintenance on a live schedule
# --------------------------------------------------------------------------- #


def set_forecast(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    installment_id: uuid.UUID,
    forecast_due_date: date | None,
    reason: str,
    correlation_id: uuid.UUID,
) -> PaymentPlanInstallment:
    """Update when a contingent instalment is expected to fall due.

    Forecast is not contract. Changing it does not change what the buyer
    agreed, does not make anything due and does not require a new version — but
    it does require a reason, because somebody downstream will plan against it.
    """
    permissions.require_plan_operator(actor)
    project = lock_project(session, project.id)
    installment, version, plan = _visible_installment_for_plan(
        session, project=project, plan_id=plan_id, installment_id=installment_id, actor=actor
    )
    if version.status != VERSION_ACTIVE:
        raise ConflictError("Only the active schedule's forecast can be maintained.")
    if installment.trigger_type in TRIGGER_DATE_BASED:
        raise ConflictError(
            "This instalment falls due on a contractual date, so it has no forecast."
        )
    before = installment.forecast_due_date
    installment.forecast_due_date = forecast_due_date
    session.flush()
    record_event(
        session,
        action="payment_plan.forecast_changed",
        entity_type="payment_plan_installment",
        entity_id=installment.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before={"forecast_due_date": before},
        after={
            "plan_number": plan.plan_number,
            "sequence": installment.sequence,
            "forecast_due_date": forecast_due_date,
        },
    )
    return installment


def set_owner(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan_id: uuid.UUID,
    installment_id: uuid.UUID,
    owner_user_id: uuid.UUID | None,
    correlation_id: uuid.UUID,
) -> PaymentPlanInstallment:
    """Assign who chases an instalment. Operational, not contractual."""
    permissions.require_plan_operator(actor)
    project = lock_project(session, project.id)
    installment, version, plan = _visible_installment_for_plan(
        session, project=project, plan_id=plan_id, installment_id=installment_id, actor=actor
    )
    if version.status != VERSION_ACTIVE:
        raise ConflictError("Only the active schedule's assignments can be maintained.")
    _require_owner_eligible(session, user_id=owner_user_id)
    before = installment.owner_user_id
    installment.owner_user_id = owner_user_id
    session.flush()
    record_event(
        session,
        action="payment_plan.owner_changed",
        entity_type="payment_plan_installment",
        entity_id=installment.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        before={"owner_user_id": before},
        after={
            "plan_number": plan.plan_number,
            "sequence": installment.sequence,
            "owner_user_id": owner_user_id,
        },
    )
    return installment


# --------------------------------------------------------------------------- #
# The register
# --------------------------------------------------------------------------- #


class RegisterRow:
    """One line of the project's payment plan register.

    Assembled here rather than in the API so the reconciliation shown in a list
    is computed by exactly the same function as the one shown on the plan — a
    register that totalled its own way would eventually disagree with the
    screen an operator opens to fix it.

    Every figure describes the version named by ``version_id``: the governing
    one where a sale has one, and otherwise the one in preparation. A revision
    being drafted alongside is named by ``revision_*`` and contributes no
    figures, because it governs nothing.
    """

    __slots__ = (
        "approved_by_user_id",
        "awaiting_trigger_count",
        "client_display_name",
        "contract_value_covered",
        "copy_source_status",
        "copy_source_version_id",
        "copy_source_version_number",
        "currency_id",
        "effective_date",
        "installment_count",
        "is_reconciled",
        "next_forecast_date",
        "next_scheduled_date",
        "plan_id",
        "plan_number",
        "revision_status",
        "revision_version_id",
        "revision_version_number",
        "sale_id",
        "sale_number",
        "scheduled_principal_total",
        "spa_number",
        "unit_id",
        "unit_reference",
        "version_id",
        "version_number",
        "version_status",
    )

    def __init__(self, **values: object) -> None:
        for name in self.__slots__:
            setattr(self, name, values.get(name))


def _current_version_of(versions: list[PaymentPlanVersion]) -> PaymentPlanVersion | None:
    """The version a reader is shown, chosen from rows already in memory.

    Exactly the precedence :func:`current_version` applies in SQL — the open
    one, else the standing one, else the most recent history — restated over a
    list so the register can decide for five hundred plans without asking the
    database five hundred times. The two must agree, so the ordering rule lives
    here once and :func:`current_version` defers to it.
    """
    ordered = sorted(versions, key=lambda version: version.version_number, reverse=True)
    open_one = next((version for version in ordered if version.status in VERSION_OPEN), None)
    if open_one is not None:
        return open_one
    standing = next((version for version in ordered if version.status == VERSION_ACTIVE), None)
    if standing is not None:
        return standing
    return next(iter(ordered), None)


def _next_on_or_after(dates: list[date], today: date) -> date | None:
    """The soonest of these dates that has not already passed.

    "Next" means next, so a date in the past is not it. PR-MVP-06 cannot say
    whether a past instalment was paid, and answering with the oldest date in
    the schedule would read as an arrears figure — which is precisely the
    inference this module must not invite.
    """
    upcoming = [value for value in dates if value >= today]
    return min(upcoming) if upcoming else None


def open_version_of(versions: list[PaymentPlanVersion]) -> PaymentPlanVersion | None:
    """The version being prepared, if one is. The in-memory form of the SQL rule."""
    ordered = sorted(versions, key=lambda version: version.version_number, reverse=True)
    return next((version for version in ordered if version.status in VERSION_OPEN), None)


def governing_version_of(versions: list[PaymentPlanVersion]) -> PaymentPlanVersion | None:
    """The version the sale is actually running on, if any has been activated."""
    return next((version for version in versions if version.status == VERSION_ACTIVE), None)


def settled_source_of(versions: list[PaymentPlanVersion]) -> PaymentPlanVersion | None:
    """The best version of this plan that somebody has actually agreed to.

    A schedule is worth copying once it has been sanctioned; a draft is a
    proposal and a rejected one is a proposal that was refused. The standing
    version first, then one approved but not yet in force, then the most
    recent one it replaced.

    Chosen separately from :func:`_current_version_of` because the two answer
    different questions. Opening a draft revision changes which version is
    being *prepared*; it does not un-agree the schedule the parties signed,
    and a copy selector that lost the plan the moment somebody started
    revising it would be answering the wrong one.
    """
    ordered = sorted(versions, key=lambda version: version.version_number, reverse=True)
    for wanted in (VERSION_ACTIVE, VERSION_APPROVED, VERSION_SUPERSEDED):
        found = next((version for version in ordered if version.status == wanted), None)
        if found is not None:
            return found
    return None


def forward_dates(rows: list[PaymentPlanInstallment]) -> tuple[date | None, date | None]:
    """The soonest scheduled and forecast dates still to come, in that order.

    Forward-only, and the same answer on every surface. PR-MVP-06 cannot say
    whether a date already past was paid, so offering the oldest date in the
    schedule under a heading like "next" would read as arrears — a claim about
    money this module has no basis for.
    """
    today = business_today()
    return (
        _next_on_or_after([row.actual_due_date for row in rows if row.actual_due_date], today),
        _next_on_or_after([row.forecast_due_date for row in rows if row.forecast_due_date], today),
    )


def plan_register(session: Session, *, project: Project, actor: ActorContext) -> list[RegisterRow]:
    """Every payment plan this caller may see, described by what governs it.

    The register is an operational overview, and the question it answers is
    "what is each sale actually running on". So the figures on a row come from
    the *governing* version whenever there is one — not from whatever somebody
    happens to be drafting. The plan builder is where a revision is inspected;
    here it is named beside the row and nothing more.

    That distinction is the whole point of this function choosing its own
    version rather than reusing :func:`current_version`, which deliberately
    prefers the version in preparation because that is the one being edited.
    Applied to a register it produced management nonsense: opening a draft
    revision dropped a live plan out of the project's active count and replaced
    a reconciled twenty-instalment schedule with an empty draft's figures.

    Read in a fixed handful of queries rather than a few per plan. The obvious
    shape — loop the plans, ask each for its version, then its reconciliation,
    then its rows — costs about five round trips per plan and loads every
    schedule twice, because reconciling reads the same instalments the caller
    then reads again. At the few hundred to few thousand sales this roadmap
    expects, that is thousands of queries to draw one screen.

    So: plans in one query, their versions in a second, the primary versions'
    instalments in a third, and the grouping and totalling done in memory with
    the same pure function the plan screen uses. Three statements whether the
    project has one plan or five hundred, and each schedule read once.

    Deliberately carries no collected, outstanding or overdue figure. Those are
    PR-MVP-07's to state, and a column of zeroes labelled "paid" would be read
    as a fact about money rather than an absence of one.
    """
    permissions.require_plan_reader(actor)
    statement = (
        select(PaymentPlan, SaleContract, Unit, Client)
        .join(SaleContract, SaleContract.id == PaymentPlan.sale_contract_id)
        .join(Unit, Unit.id == SaleContract.unit_id)
        .join(Client, Client.id == SaleContract.client_id)
        .where(PaymentPlan.project_id == project.id)
    )
    allowed = permissions.visible_sale_ids(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(PaymentPlan.sale_contract_id.in_(allowed))
    listed = list(session.execute(statement.order_by(PaymentPlan.plan_number.desc())))
    if not listed:
        return []

    plan_ids = [plan.id for plan, _sale, _unit, _client in listed]
    by_plan: dict[uuid.UUID, list[PaymentPlanVersion]] = {plan_id: [] for plan_id in plan_ids}
    for version in session.scalars(
        select(PaymentPlanVersion).where(PaymentPlanVersion.payment_plan_id.in_(plan_ids))
    ):
        by_plan[version.payment_plan_id].append(version)

    # What governs, and — separately — what is being prepared. Before the first
    # activation nothing governs, and the version in preparation is all there is
    # to show; its status says plainly that it does not yet govern anything.
    governing = {plan_id: governing_version_of(rows) for plan_id, rows in by_plan.items()}
    preparing = {plan_id: open_version_of(rows) for plan_id, rows in by_plan.items()}
    chosen = {
        plan_id: governing[plan_id] or preparing[plan_id] or _current_version_of(rows)
        for plan_id, rows in by_plan.items()
    }
    revisions = {
        plan_id: (
            version
            if (version := preparing[plan_id]) is not None
            and chosen[plan_id] is not None
            and version.id != chosen[plan_id].id
            else None
        )
        for plan_id in by_plan
    }
    version_ids = [version.id for version in chosen.values() if version is not None]
    by_version: dict[uuid.UUID, list[PaymentPlanInstallment]] = {
        version_id: [] for version_id in version_ids
    }
    if version_ids:
        for row in session.scalars(
            select(PaymentPlanInstallment)
            .where(PaymentPlanInstallment.payment_plan_version_id.in_(version_ids))
            .order_by(PaymentPlanInstallment.sequence)
        ):
            by_version[row.payment_plan_version_id].append(row)

    rows: list[RegisterRow] = []
    for plan, sale, unit, client in listed:
        version = chosen.get(plan.id)
        installments = by_version.get(version.id, []) if version is not None else []
        reconciliation = reconcile_rows(version, installments) if version is not None else None
        next_scheduled, next_forecast = forward_dates(installments)
        # The settled schedule comes from the versions already in memory, so
        # naming a copy source costs no additional query.
        source = settled_source_of(by_plan.get(plan.id, []))
        revision = revisions.get(plan.id)
        rows.append(
            RegisterRow(
                plan_id=plan.id,
                plan_number=plan.plan_number,
                sale_id=sale.id,
                sale_number=sale.sale_number,
                spa_number=sale.spa_number,
                unit_id=unit.id,
                unit_reference=unit.unit_reference,
                client_display_name=client.display_name,
                version_id=version.id if version else None,
                version_number=version.version_number if version else None,
                version_status=version.status if version else None,
                effective_date=version.effective_date if version else None,
                currency_id=version.currency_id if version else sale.currency_id,
                contract_value_covered=(
                    version.contract_value_covered if version else sale.net_contract_price_ex_tax
                ),
                installment_count=reconciliation.installment_count if reconciliation else 0,
                scheduled_principal_total=(
                    reconciliation.scheduled_principal_total if reconciliation else None
                ),
                is_reconciled=reconciliation.is_reconciled if reconciliation else False,
                next_scheduled_date=next_scheduled,
                next_forecast_date=next_forecast,
                copy_source_version_id=source.id if source else None,
                copy_source_version_number=source.version_number if source else None,
                copy_source_status=source.status if source else None,
                revision_version_id=revision.id if revision else None,
                revision_version_number=revision.version_number if revision else None,
                revision_status=revision.status if revision else None,
                awaiting_trigger_count=sum(
                    1 for row in installments if row.trigger_status == TRIGGER_AWAITING
                ),
                approved_by_user_id=version.approved_by_user_id if version else None,
            )
        )
    return rows


def plan_for_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> PaymentPlan | None:
    """The plan governing one sale, for the deal file and Unit 360.

    Returns nothing rather than raising when a sale has no plan yet: "not
    scheduled" is an ordinary answer, and the screens that ask this question
    say so in words.
    """
    permissions.require_plan_reader(actor)
    sale = permissions.require_visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    return session.scalars(
        select(PaymentPlan).where(PaymentPlan.sale_contract_id == sale.id)
    ).first()


# --------------------------------------------------------------------------- #
# The collections boundary
#
# Two contracts, and neither is an HTTP route. PR-MVP-07 owns receipts and
# allocations; this module owns the contractual schedule and the rule that a
# schedule with cash against it cannot be swapped out from underneath it.
#
# The dependency points one way. Collections imports payment plans; payment
# plans imports nothing from collections and never will, because the moment it
# does the two modules can no longer be reasoned about — or tested — apart.
# There is no plugin registry, no event bus and no hook here: two named
# functions are enough for the one interaction that actually exists.
# --------------------------------------------------------------------------- #


def lock_plan(session: Session, *, project_id: uuid.UUID, plan_id: uuid.UUID) -> PaymentPlan:
    """Take a plan's row for update, for a caller in another domain.

    Collections needs this lock before it reads which version is governing, so
    that a restructure cannot activate a replacement between the read and the
    write. Public rather than reaching into the private helper, because the
    lock order is a property of the system and not of this module.
    """
    return _lock_plan(session, project_id=project_id, plan_id=plan_id)


def lock_version(
    session: Session, *, project_id: uuid.UUID, version_id: uuid.UUID
) -> PaymentPlanVersion:
    """Take a version's row for update, for a caller in another domain.

    Needed by the collections restructure, which must hold both the version it
    is replacing and the one replacing it while it moves the cash between their
    instalments.
    """
    return _lock_version(session, project_id=project_id, version_id=version_id)


def mark_collections_started(
    session: Session, *, project_id: uuid.UUID, plan_id: uuid.UUID
) -> PaymentPlan:
    """Record that cash has now been confirmed against this plan. Idempotent.

    Called by collections inside the transaction that confirms the first
    receipt, so the marker and the money it refers to commit together. The
    caller is expected to hold the project and plan locks already; the row is
    taken for update again here regardless, because a contract that quietly
    depends on its caller having remembered a lock is a contract that fails on
    the day somebody adds a second caller.

    Set once and never cleared. Reversing the last receipt does not undo it:
    the schedule has still been collected against, the allocations are still on
    the record, and the restructure path is still the honest way to replace it.
    """
    plan = _lock_plan(session, project_id=project_id, plan_id=plan_id)
    if plan.collections_started_at is None:
        plan.collections_started_at = _now()
        session.flush()
    return plan


def activate_restructured_version(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    plan: PaymentPlan,
    version: PaymentPlanVersion,
    correlation_id: uuid.UUID,
) -> PaymentPlanVersion:
    """Activate a replacement schedule on behalf of a collections restructure.

    Every check the ordinary path makes still runs — approved, effective today
    or earlier, sale still active, frozen basis still matching, schedule still
    reconciling, predecessor superseded in the same transaction. The single
    difference is that the collections guard does not apply, because the caller
    is the mechanism that guard exists to point at.

    Deliberately not exposed as a route. Reaching this without having carried
    the allocations forward first would produce exactly the silent loss the
    guard prevents, so the only way in is through
    ``collections.service.apply_restructure``, which does that carry-forward in
    the same transaction and refuses if a single unit of cash cannot be placed.

    The caller holds the project, plan and version locks. It also owns the
    transaction: nothing here commits.
    """
    return _activate_locked(
        session,
        project=project,
        actor=actor,
        plan=plan,
        version=version,
        correlation_id=correlation_id,
    )
