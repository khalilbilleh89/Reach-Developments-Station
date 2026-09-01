"""Collections behaviour: record cash, confirm it, apply it, and chase the rest.

The rules this file exists to hold, stated once.

**Only a confirmed receipt is cash.** A recorded one is a claim. Every balance
in this module counts confirmed receipts and nothing else, so a receipt sitting
in Finance's queue moves no figure on any screen — which is the honest answer,
because until somebody has looked at the bank we do not know the money came.

**Applying cash is a separate decision from receiving it.** Allocations are
their own rows, made by a person, reversible without pretending the money never
arrived. Cash that has arrived and not been applied is *unapplied*, it is
reported, and nothing here ever quietly absorbs it into a balance.

**Nothing is stored that can be derived.** Outstanding, unapplied, days
overdue, aging bucket, collection status: all computed from rows at read time,
for a supplied ``as_of``. There is no balance column in this module and no
nightly job, because a stored total is a second source of truth and it becomes
the wrong one the first time a write path forgets it.

**No unit of cash may vanish or appear twice.** The restructure is where that
is really tested: it moves every active allocation onto a replacement schedule
inside one transaction, and if a single unit cannot be placed it raises rather
than activating a schedule the money no longer fits.

Locking. Every mutating function takes the project row first, exactly as
payment plans and sales do, so no two writers in a project can interleave.
Below that the order is fixed and never varies::

    project → plan → version → sale → instalment → receipt → allocation

The invariants live on the rows that own them: "this instalment is not
over-allocated" is owned by the instalment, "this receipt is not
over-allocated" by the receipt, so both are taken for update before either is
read for a decision. Two collections officers filling the same instalment take
turns and the second is told what is actually left.

Cross-domain writes always go through a contract, never a column::

    → inventory.apply_collection_status          the unit's collection dimension
    → sales.apply_collection_clearance           the handover gate
    → sales.revoke_collection_clearance          when the ledger reopens
    → payment_plans.mark_collections_started     the boundary marker
    → payment_plans.activate_restructured_version the carried-forward schedule

Reading another domain's rows is ordinary and done directly. Writing them is
not, and there is no path in this file that does.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.base import MONEY_EXPONENT
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.collections import ledger, permissions
from app.modules.collections.models import (
    ACTION_PROMISE,
    ALLOCATION_ACTIVE,
    ALLOCATION_REVERSED,
    ALLOCATION_SUPERSEDED,
    DISPUTE_OPEN,
    DISPUTE_RESOLVED,
    DISPUTE_WITHDRAWN,
    RECEIPT_CONFIRMED,
    RECEIPT_RECORDED,
    RECEIPT_REVERSED,
    REFUND_CONFIRMED,
    REFUND_RECORDED,
    REFUND_REVERSED,
    RESTRUCTURE_ABANDONED,
    RESTRUCTURE_APPLIED,
    RESTRUCTURE_OPEN,
    WAIVER_APPROVED,
    WAIVER_LIVE,
    WAIVER_REJECTED,
    WAIVER_REVOKED,
    WAIVER_SUBMITTED,
    CollectionAction,
    CollectionDispute,
    CollectionReceipt,
    CollectionReceiptAllocation,
    CollectionRefund,
    CollectionRestructure,
    CollectionWaiver,
)
from app.modules.inventory import service as inventory_service
from app.modules.inventory.custom_fields import business_today
from app.modules.inventory.models import Unit
from app.modules.payment_plans import service as payment_plans_service
from app.modules.payment_plans.models import (
    TRIGGER_DATE_BASED,
    TRIGGER_TRIGGERED,
    VERSION_APPROVED,
    PaymentPlan,
    PaymentPlanInstallment,
    PaymentPlanVersion,
)
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import service as sales_service
from app.modules.sales.models import (
    CANCELLATION_COMPLETED,
    SALE_ACTIVE,
    Client,
    SaleCancellation,
    SaleContract,
)

ZERO = ledger.ZERO

_RECEIPT_PREFIX = "RCT"
_RESTRUCTURE_PREFIX = "RST"
_REFUND_PREFIX = "RFD"

#: One refusal each for a nested resource that is missing, hidden, or claimed by
#: the wrong parent. Identical in all three cases, because a message that
#: distinguishes them confirms that a guessed identifier names something real.
_NO_RECEIPT = "Receipt not found."
_NO_ALLOCATION = "Allocation not found."
_NO_INSTALLMENT = "Instalment not found."
_NO_DISPUTE = "Dispute not found."
_NO_WAIVER = "Waiver not found."
_NO_RESTRUCTURE = "Restructure not found."
_NO_REFUND = "Refund not found."

#: The sale states against which cash may still be recorded. A cancelled
#: contract keeps its history and stops taking new receipts; a draft one has no
#: agreed figures to receive against.
SALE_COLLECTABLE = frozenset({SALE_ACTIVE, "signature_pending", "termination_pending"})


def _now() -> datetime:
    return datetime.now(UTC)


def _money(value: object) -> Decimal:
    """Bring a figure back to the monetary scale every money column carries.

    ``SUM`` over no rows coalesces to the integer ``0``, which becomes the
    string ``"0"`` on the wire while every other money field is ``"0.00"``. A
    caller comparing the two — or a spreadsheet parsing a column of them —
    should not have to know which query produced which, so everything that can
    come back unscaled is quantised here.
    """
    return Decimal(value or 0).quantize(MONEY_EXPONENT)


# --------------------------------------------------------------------------- #
# Reading a position as it stood on a date
# --------------------------------------------------------------------------- #
#
# Every collections figure is derived, so "what did this account look like on
# 31 March?" is answerable without a single stored snapshot — but only if the
# read reconstructs the *cash* as well as the arithmetic. Aging an as-of-March
# schedule against the receipts confirmed in June is worse than not offering
# the question at all, because the answer looks authoritative and is wrong.
#
# Every row Collections owns is append-only and carries the moments it changed
# state, so the reconstruction is a filter rather than a replay. There is no
# event log here and none is needed.
#
# What this reconstructs is the *business-effective* position: what was true of
# the account on that date, judged by when things actually happened. It is not
# a claim about what a screen showed somebody at the time — a receipt confirmed
# on the 2nd of April for cash that arrived on the 30th of March moves the
# March position, and no report printed on the 31st could have known it. That
# is the right answer for month-end and for an auditor, and the wrong one for
# "what did I see?", which would need event sourcing this MVP deliberately does
# not have.


def _bound(as_of: date) -> datetime:
    """The first instant after ``as_of``.

    A single exclusive upper bound, compared against the ``timestamptz`` columns
    that record when each row changed state. Exclusive rather than end-of-day
    inclusive so there is no last-microsecond gap to argue about, and one
    function so the same boundary is used by the sale-level read and the
    project-level register.

    Asked for today, every clause below collapses to exactly the status filter
    it replaces — a confirmed receipt is one confirmed before tomorrow and not
    yet reversed — so the ordinary path keeps its behaviour and its query count,
    and the historical path is the same code with a different bound.
    """
    return datetime.combine(as_of + timedelta(days=1), time.min, tzinfo=UTC)


def _receipt_effective_on(as_of: date) -> ColumnElement[bool]:
    """Cash that had arrived, been confirmed, and not been reversed, by ``as_of``.

    ``receipt_date`` is the day the money arrived and ``confirmed_at`` the
    moment Finance accepted it; both must be behind us. A receipt confirmed
    today for cash that arrives tomorrow cannot exist — recording refuses a
    future receipt date — so the two clauses never contradict each other.
    """
    bound = _bound(as_of)
    return (
        (CollectionReceipt.receipt_date <= as_of)
        & CollectionReceipt.confirmed_at.is_not(None)
        & (CollectionReceipt.confirmed_at < bound)
        & (CollectionReceipt.reversed_at.is_(None) | (CollectionReceipt.reversed_at >= bound))
    )


def _allocation_effective_on(as_of: date) -> ColumnElement[bool]:
    """Cash that was sitting on an instalment on ``as_of``.

    Superseded counts the same as reversed here: a restructure that moved this
    allocation onto a replacement schedule in June did not move it in March, so
    the March position is the one it had then.
    """
    bound = _bound(as_of)
    return (
        (CollectionReceiptAllocation.created_at < bound)
        & (
            CollectionReceiptAllocation.reversed_at.is_(None)
            | (CollectionReceiptAllocation.reversed_at >= bound)
        )
        & (
            CollectionReceiptAllocation.superseded_at.is_(None)
            | (CollectionReceiptAllocation.superseded_at >= bound)
        )
    )


def _dispute_open_on(as_of: date) -> ColumnElement[bool]:
    """A dispute that had been raised and not yet closed on ``as_of``."""
    bound = _bound(as_of)
    return (CollectionDispute.opened_at < bound) & (
        CollectionDispute.resolved_at.is_(None) | (CollectionDispute.resolved_at >= bound)
    )


def _waiver_live_on(as_of: date) -> ColumnElement[bool]:
    """A waiver that had been approved and not withdrawn on ``as_of``."""
    bound = _bound(as_of)
    return (
        CollectionWaiver.approved_at.is_not(None)
        & (CollectionWaiver.approved_at < bound)
        & (CollectionWaiver.revoked_at.is_(None) | (CollectionWaiver.revoked_at >= bound))
        & (CollectionWaiver.rejected_at.is_(None) | (CollectionWaiver.rejected_at >= bound))
    )


def _refund_effective_on(as_of: date) -> ColumnElement[bool]:
    """Cash that had actually left the company by ``as_of``.

    The same shape as :func:`_receipt_effective_on`, and deliberately so: a
    refund is cash moving the other way, and money out obeys the rules money in
    obeys. A refund confirmed in July is not a payment made in June, and one
    reversed in September was still a payment made in August.
    """
    bound = _bound(as_of)
    return (
        (CollectionRefund.refund_date <= as_of)
        & CollectionRefund.confirmed_at.is_not(None)
        & (CollectionRefund.confirmed_at < bound)
        & (CollectionRefund.reversed_at.is_(None) | (CollectionRefund.reversed_at >= bound))
    )


def _refund_due_on(as_of: date) -> ColumnElement[bool]:
    """A cancellation whose refund had been *sanctioned* by ``as_of``.

    ``refund_due_amount`` is captured when the cancellation case is opened,
    which is a proposal rather than a debt: PR-MVP-05 makes the money on the way
    out something a financial approver has to sign, and until they have, nothing
    is owed. So the amount counts from the moment of approval, and a refund
    approved in June is not a liability the March account was carrying.

    This is a single rule applied at every date, today included — which is the
    point of one ``as_of``. It does change one of today's answers: a cancellation
    with a proposed refund still awaiting its approver now reports zero due
    rather than the proposal. That is the more honest of the two figures, and it
    is the one the historical read has to give anyway.
    """
    bound = _bound(as_of)
    return SaleCancellation.financial_approved_at.is_not(None) & (
        SaleCancellation.financial_approved_at < bound
    )


def _cancelled_on(as_of: date) -> ColumnElement[bool]:
    """A completed cancellation whose unit return had taken effect by ``as_of``.

    ``sale.status`` is today's answer and only today's. The date the unwind
    became effective is ``unit_return_date`` — the operator's statement of when
    the unit actually came back — and completion is the only route to
    ``cancelled``, so the two agree on the current date and disagree only where
    they should: before the cancellation happened.
    """
    return (SaleCancellation.status == CANCELLATION_COMPLETED) & (
        SaleCancellation.unit_return_date.is_not(None)
        & (SaleCancellation.unit_return_date <= as_of)
    )


def _action_recorded_on(as_of: date) -> ColumnElement[bool]:
    """A follow-up that had been written down by ``as_of``.

    A chase logged in June was not on the March account, and an operator
    reconstructing March to ask why nobody had called should not find a call
    they had not yet made.
    """
    return CollectionAction.created_at < _bound(as_of)


def sale_cancelled_as_of(session: Session, *, sale: SaleContract, as_of: date) -> bool:
    """Was this contract cancelled, as at ``as_of``? One answer, used twice.

    The instalment rows and the unit's collection status both need it, and they
    must not each work it out: two derivations of the same fact is how a row
    reading ``cancelled`` ends up beside an account that is not.
    """
    return (
        session.scalar(
            select(func.count())
            .select_from(SaleCancellation)
            .where(
                SaleCancellation.sale_contract_id == sale.id,
                _cancelled_on(as_of),
            )
        )
        or 0
    ) > 0


def _version_governing_on(as_of: date) -> ColumnElement[bool]:
    """The schedule that was governing the sale on ``as_of``.

    A version governs from the moment it is activated until the moment it is
    superseded. Reading a March position against the schedule a June
    restructure put in place would report instalments the buyer had never been
    given, so the version is reconstructed exactly like the cash.
    """
    bound = _bound(as_of)
    return (
        PaymentPlanVersion.activated_at.is_not(None)
        & (PaymentPlanVersion.activated_at < bound)
        & (PaymentPlanVersion.superseded_at.is_(None) | (PaymentPlanVersion.superseded_at >= bound))
    )


def resolve_as_of(as_of: date | None) -> date:
    """The date a read is answered for, refused if it is in the future.

    PR-MVP-10 owns forecasting. A collections read asked for next quarter would
    have to invent either receipts or the absence of them, and either invention
    would be reported in the same shape as fact.
    """
    today = business_today()
    if as_of is None:
        return today
    if as_of > today:
        raise ValidationError(
            "Collections reports what has happened, not what is expected. "
            f"The latest date this can be read for is {today.isoformat()}."
        )
    return as_of


def _require_text(value: str | None, *, detail: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError(detail)
    return cleaned


# --------------------------------------------------------------------------- #
# Loading and locking
#
# Order, everywhere: project → plan → version → sale → instalment → receipt →
# allocation. The project row is taken first by every mutating path in this
# module, in payment plans and in sales, so two writers in one project queue
# rather than interleave; the rest of the order exists so a path that needs
# three of these never takes them in a sequence some other path reverses.
# --------------------------------------------------------------------------- #


def _lock_receipt(
    session: Session, *, project_id: uuid.UUID, receipt_id: uuid.UUID
) -> CollectionReceipt:
    """Take the receipt row for update; it owns 'this receipt is not over-applied'."""
    receipt = session.scalars(
        select(CollectionReceipt)
        .where(CollectionReceipt.id == receipt_id, CollectionReceipt.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if receipt is None:
        raise NotFoundError(_NO_RECEIPT)
    return receipt


def _lock_installment(
    session: Session, *, project_id: uuid.UUID, installment_id: uuid.UUID
) -> PaymentPlanInstallment:
    """Take the instalment row for update; it owns 'this instalment is not over-filled'."""
    row = session.scalars(
        select(PaymentPlanInstallment)
        .where(
            PaymentPlanInstallment.id == installment_id,
            PaymentPlanInstallment.project_id == project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError(_NO_INSTALLMENT)
    return row


def _lock_refund(
    session: Session, *, project_id: uuid.UUID, refund_id: uuid.UUID
) -> CollectionRefund:
    refund = session.scalars(
        select(CollectionRefund)
        .where(CollectionRefund.id == refund_id, CollectionRefund.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if refund is None:
        raise NotFoundError(_NO_REFUND)
    return refund


def _lock_cancellation(
    session: Session, *, project_id: uuid.UUID, cancellation_id: uuid.UUID
) -> SaleCancellation:
    """Take the cancellation row; it owns 'refunds do not exceed what is due'."""
    row = session.scalars(
        select(SaleCancellation)
        .where(
            SaleCancellation.id == cancellation_id,
            SaleCancellation.project_id == project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError("Cancellation not found.")
    return row


def _lock_restructure(
    session: Session, *, project_id: uuid.UUID, restructure_id: uuid.UUID
) -> CollectionRestructure:
    row = session.scalars(
        select(CollectionRestructure)
        .where(
            CollectionRestructure.id == restructure_id,
            CollectionRestructure.project_id == project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError(_NO_RESTRUCTURE)
    return row


# --------------------------------------------------------------------------- #
# Parentage
#
# A nested path is a claim about parentage. ``/sales/S1/receipts/R2`` asserts
# that R2 is one of S1's receipts, and every loader below proves the whole chain
#
#     project → sale → receipt → allocation
#     project → sale → plan → version → instalment → dispute / waiver
#
# before returning anything, rather than validating each identifier alone and
# trusting the caller paired them honestly. Two independently valid identifiers
# are not a valid pair, and the refusal never says "belongs to another sale".
# --------------------------------------------------------------------------- #


def _visible_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> SaleContract:
    return permissions.require_visible_sale(session, project=project, sale_id=sale_id, actor=actor)


def _receipt_for_sale(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    receipt_id: uuid.UUID,
    actor: ActorContext,
) -> tuple[CollectionReceipt, SaleContract]:
    """Load a receipt proved to belong to ``sale_id``, or raise 404."""
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    receipt = session.scalars(
        select(CollectionReceipt).where(
            CollectionReceipt.id == receipt_id,
            CollectionReceipt.project_id == project.id,
            CollectionReceipt.sale_contract_id == sale.id,
        )
    ).first()
    if receipt is None:
        raise NotFoundError(_NO_RECEIPT)
    return receipt, sale


def visible_receipt(
    session: Session, *, project: Project, receipt_id: uuid.UUID, actor: ActorContext
) -> tuple[CollectionReceipt, SaleContract]:
    """Load a receipt the caller may see, narrowed through its sale in SQL."""
    statement = select(CollectionReceipt).where(
        CollectionReceipt.id == receipt_id, CollectionReceipt.project_id == project.id
    )
    allowed = permissions.visible_sales(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(CollectionReceipt.sale_contract_id.in_(allowed))
    receipt = session.scalars(statement).first()
    if receipt is None:
        raise NotFoundError(_NO_RECEIPT)
    sale = _visible_sale(session, project=project, sale_id=receipt.sale_contract_id, actor=actor)
    return receipt, sale


def _visible_installment(
    session: Session, *, project: Project, installment_id: uuid.UUID, actor: ActorContext
) -> tuple[PaymentPlanInstallment, PaymentPlan, SaleContract]:
    """Prove project → sale → plan → version → instalment for a bare instalment id."""
    row = session.scalars(
        select(PaymentPlanInstallment).where(
            PaymentPlanInstallment.id == installment_id,
            PaymentPlanInstallment.project_id == project.id,
        )
    ).first()
    if row is None:
        raise NotFoundError(_NO_INSTALLMENT)
    version = session.get(PaymentPlanVersion, row.payment_plan_version_id)
    if version is None:  # pragma: no cover - composite FK makes this unreachable
        raise NotFoundError(_NO_INSTALLMENT)
    plan = session.get(PaymentPlan, version.payment_plan_id)
    if plan is None:  # pragma: no cover - composite FK makes this unreachable
        raise NotFoundError(_NO_INSTALLMENT)
    try:
        sale = _visible_sale(session, project=project, sale_id=plan.sale_contract_id, actor=actor)
    except NotFoundError:
        # The instalment is real but sits behind a phase this caller was never
        # granted. Answer exactly as for an instalment that does not exist.
        raise NotFoundError(_NO_INSTALLMENT) from None
    return row, plan, sale


# --------------------------------------------------------------------------- #
# Human numbering
# --------------------------------------------------------------------------- #


def _next_number(
    session: Session,
    *,
    project: Project,
    prefix: str,
    column: object,
    table: object,
) -> str:
    """Assign the next project-scoped reference under the project lock.

    ``MAX + 1`` is safe only because the caller already holds the project row,
    so two requests arriving together take turns rather than both claiming
    RCT-000004. The unique index stays as the backstop for a caller that
    forgets the lock.
    """
    highest = session.scalar(
        select(func.max(func.substr(column, len(prefix) + 2))).where(
            table.project_id == project.id,  # type: ignore[attr-defined]
            column.like(f"{prefix}-%"),  # type: ignore[attr-defined]
        )
    )
    number = int(highest) + 1 if highest and highest.isdigit() else 1
    return f"{prefix}-{number:06d}"


def _require_governing_installment(
    session: Session, *, plan: PaymentPlan, installment: PaymentPlanInstallment
) -> None:
    """Refuse to raise a new operational decision against a schedule nobody is on.

    A dispute or a waiver is a statement about what the buyer is being asked for
    *now*. Attached to an instalment of a draft, a submitted, an approved-but-
    inactive or a superseded version, it would describe a demand that was never
    made or is no longer being made — and it would sit there invisible, because
    every screen reads the governing schedule.

    Reading is untouched: the historical rows stay on the account, and
    :func:`disputes_of_sale` and :func:`waivers_of_sale` still return them. This
    is only about creating new ones.
    """
    governing = payment_plans_service.active_version(session, plan_id=plan.id)
    if governing is not None and installment.payment_plan_version_id == governing.id:
        return
    if governing is None:
        raise ConflictError(
            "This sale has no active payment plan schedule. Activate one before "
            "raising a dispute or a waiver against its instalments."
        )
    raise ConflictError(
        "This instalment does not belong to the schedule currently governing the "
        "sale. Raise it against the active schedule instead."
    )


# --------------------------------------------------------------------------- #
# The ledger position of one sale
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SaleLedger:
    """Everything one sale's collections position is derived from, read once.

    Assembled by :func:`load_ledger` in a fixed handful of queries and then used
    by every caller that needs a figure — the account screen, the aging report,
    the clearance check, the status recalculation. One read, one answer.
    """

    sale: SaleContract
    as_of: date
    #: Whether the contract was cancelled *on* ``as_of``, not whether it is now.
    #: Worked out once and read by both the instalment rows and the unit status,
    #: because two derivations of one fact is how a row reading "cancelled" ends
    #: up beside an account that is not.
    sale_cancelled: bool
    plan: PaymentPlan | None
    version: PaymentPlanVersion | None
    installments: list[PaymentPlanInstallment]
    confirmed_receipts: list[CollectionReceipt]
    allocations: list[CollectionReceiptAllocation]
    open_disputes: list[CollectionDispute]
    live_waivers: list[CollectionWaiver]


def _plan_of(session: Session, *, sale_id: uuid.UUID) -> PaymentPlan | None:
    return session.scalars(
        select(PaymentPlan).where(PaymentPlan.sale_contract_id == sale_id)
    ).first()


def load_ledger(session: Session, *, sale: SaleContract, as_of: date | None = None) -> SaleLedger:
    """Read one sale's whole collections position, as it stood on ``as_of``.

    The governing version is the one that was *active* then, never the one being
    prepared. A revision under construction changes nothing about what the buyer
    owes, and a receivables report that switched to the draft the moment
    somebody opened it would be reporting a negotiation as though it were a
    contract.

    Every clause is a lifecycle clause rather than a status one, so the same
    code answers today and answers March — see :func:`_bound`. Asked for today
    the two are identical, which is why there is one path and not two.

    Disputes and waivers are narrowed to the governing schedule's own
    instalments. One raised against a schedule a restructure has since replaced
    is history, readable through :func:`disputes_of_sale`, and has no business
    colouring the position of a schedule it was never about.
    """
    as_of = as_of or business_today()
    cancelled = sale_cancelled_as_of(session, sale=sale, as_of=as_of)
    plan = _plan_of(session, sale_id=sale.id)
    version = (
        session.scalars(
            select(PaymentPlanVersion).where(
                PaymentPlanVersion.payment_plan_id == plan.id,
                _version_governing_on(as_of),
            )
        ).first()
        if plan
        else None
    )
    installments = (
        payment_plans_service.installments_of(session, version_id=version.id) if version else []
    )
    governing_ids = {row.id for row in installments}
    confirmed = list(
        session.scalars(
            select(CollectionReceipt)
            .where(
                CollectionReceipt.sale_contract_id == sale.id,
                _receipt_effective_on(as_of),
            )
            .order_by(CollectionReceipt.receipt_date, CollectionReceipt.receipt_number)
        )
    )
    allocations = list(
        session.scalars(
            select(CollectionReceiptAllocation).where(
                CollectionReceiptAllocation.sale_contract_id == sale.id,
                _allocation_effective_on(as_of),
            )
        )
    )
    disputes = [
        row
        for row in session.scalars(
            select(CollectionDispute).where(
                CollectionDispute.sale_contract_id == sale.id,
                _dispute_open_on(as_of),
            )
        )
        if row.installment_id in governing_ids
    ]
    waivers = [
        row
        for row in session.scalars(
            select(CollectionWaiver).where(
                CollectionWaiver.sale_contract_id == sale.id,
                _waiver_live_on(as_of),
            )
        )
        if row.installment_id in governing_ids
    ]
    return SaleLedger(
        sale=sale,
        as_of=as_of,
        sale_cancelled=cancelled,
        plan=plan,
        version=version,
        installments=installments,
        confirmed_receipts=confirmed,
        allocations=allocations,
        open_disputes=disputes,
        live_waivers=waivers,
    )


def _paid_by_installment(
    allocations: list[CollectionReceiptAllocation], confirmed_ids: set[uuid.UUID]
) -> dict[uuid.UUID, Decimal]:
    """How much confirmed cash sits on each instalment.

    Allocations whose receipt is only *recorded* are deliberately excluded. They
    are a proposal Finance has not accepted, and counting them would put money
    on a balance sheet on the strength of somebody having typed it in.
    """
    paid: dict[uuid.UUID, Decimal] = {}
    for allocation in allocations:
        if allocation.receipt_id not in confirmed_ids:
            continue
        paid[allocation.installment_id] = (
            paid.get(allocation.installment_id, ZERO) + allocation.amount
        )
    return paid


@dataclass(frozen=True, slots=True)
class SaleSummary:
    """One sale's collections position on an ``as_of`` date. Every field derived."""

    sale_id: uuid.UUID
    currency_id: uuid.UUID
    as_of: date
    active_payment_plan_id: uuid.UUID | None
    active_payment_plan_version_id: uuid.UUID | None
    scheduled_total: Decimal
    confirmed_receipts_total: Decimal
    allocated_total: Decimal
    unapplied_cash: Decimal
    outstanding_total: Decimal
    due_total: Decimal
    overdue_total: Decimal
    oldest_overdue_days: int
    installments_total: int
    installments_paid: int
    installments_partial: int
    installments_overdue: int
    installments_awaiting_trigger: int
    open_disputes: int
    active_waivers: int
    next_action_date: date | None
    derived_collection_status: str
    rows: list[ledger.InstallmentView]
    refund_due_total: Decimal
    refund_confirmed_total: Decimal
    refund_outstanding: Decimal
    collection_clearance_status: str | None


def _installment_views(position: SaleLedger, *, as_of: date) -> list[ledger.InstallmentView]:
    """Turn the governing schedule plus the cash against it into readable rows."""
    confirmed_ids = {receipt.id for receipt in position.confirmed_receipts}
    paid = _paid_by_installment(position.allocations, confirmed_ids)
    disputed = {dispute.installment_id for dispute in position.open_disputes}
    waived: dict[uuid.UUID, date] = {}
    for waiver in position.live_waivers:
        current = waived.get(waiver.installment_id)
        if current is None or waiver.waived_until > current:
            waived[waiver.installment_id] = waiver.waived_until
    cancelled = position.sale_cancelled

    return [
        ledger.installment_view(
            installment_id=row.id,
            sequence=row.sequence,
            label=row.label,
            trigger_type=row.trigger_type,
            trigger_status=row.trigger_status,
            date_based=row.trigger_type in TRIGGER_DATE_BASED,
            contractual_due_date=row.contractual_due_date,
            actual_due_date=row.actual_due_date,
            triggered=row.trigger_status == TRIGGER_TRIGGERED,
            grace_days=row.grace_days,
            principal=row.principal_amount,
            tax=row.tax_amount,
            fee=row.fee_amount,
            paid=paid.get(row.id, ZERO),
            as_of=as_of,
            disputed=row.id in disputed,
            waived_until=waived.get(row.id),
            owner_user_id=row.owner_user_id,
            sale_cancelled=cancelled,
        )
        for row in position.installments
    ]


def _next_action_date(session: Session, *, sale_id: uuid.UUID, as_of: date) -> date | None:
    """The soonest planned follow-up still ahead of us."""
    return session.scalar(
        select(func.min(CollectionAction.next_action_date)).where(
            CollectionAction.sale_contract_id == sale_id,
            CollectionAction.next_action_date >= as_of,
            _action_recorded_on(as_of),
        )
    )


def _refund_position(
    session: Session, *, sale_id: uuid.UUID, as_of: date
) -> tuple[Decimal, Decimal]:
    """What this contract's cancellations had made due by ``as_of``, and what had left.

    Both sides obey the same cutoff as the receivable beside them, because a
    March balance shown next to a June refund is two reporting dates in one
    answer — and the reader has no way of telling which figure belongs to which.
    """
    due = session.scalar(
        select(func.coalesce(func.sum(SaleCancellation.refund_due_amount), 0)).where(
            SaleCancellation.sale_contract_id == sale_id,
            _refund_due_on(as_of),
        )
    )
    paid = session.scalar(
        select(func.coalesce(func.sum(CollectionRefund.amount), 0)).where(
            CollectionRefund.sale_contract_id == sale_id,
            _refund_effective_on(as_of),
        )
    )
    return _money(due), _money(paid)


@dataclass(frozen=True, slots=True)
class SaleExtras:
    """The four per-sale facts that live outside the ledger tables.

    Passed in by the register, which reads them for every sale at once, and
    looked up individually when a single account is being shown. The point is
    that :func:`summarise` stays the one place a collections figure is
    computed: a register that totalled its own rows would be a second answer,
    and the way that disagreement surfaces is a deal file and an aging report
    disagreeing about one buyer's balance.
    """

    next_action_date: date | None
    refund_due_total: Decimal
    refund_confirmed_total: Decimal
    collection_clearance_status: str | None


def summarise(
    session: Session,
    *,
    position: SaleLedger,
    as_of: date | None = None,
    extras: SaleExtras | None = None,
) -> SaleSummary:
    """The whole read model for one sale, from one already-loaded position.

    Every screen that shows a collections figure calls this, and so does the
    register — batched, through ``extras``. One totalling routine, one answer.
    """
    as_of = as_of or position.as_of
    if extras is None:
        refund_due, refund_paid = _refund_position(session, sale_id=position.sale.id, as_of=as_of)
        extras = SaleExtras(
            next_action_date=_next_action_date(session, sale_id=position.sale.id, as_of=as_of),
            refund_due_total=refund_due,
            refund_confirmed_total=refund_paid,
            collection_clearance_status=sales_service.collection_clearance_status_as_of(
                session, sale_id=position.sale.id, as_of=as_of
            ),
        )
    rows = _installment_views(position, as_of=as_of)
    confirmed_total = sum((r.amount for r in position.confirmed_receipts), ZERO)
    confirmed_ids = {receipt.id for receipt in position.confirmed_receipts}
    allocated_total = sum(
        (a.amount for a in position.allocations if a.receipt_id in confirmed_ids), ZERO
    )
    unapplied = confirmed_total - allocated_total
    outstanding = sum((r.outstanding for r in rows), ZERO)
    due_total = sum((r.due_amount for r in rows), ZERO)
    overdue_total = sum((r.overdue_amount for r in rows), ZERO)
    oldest = max((r.overdue_days for r in rows), default=0)

    status = ledger.unit_collection_status(
        sale_cancelled=position.sale_cancelled,
        has_active_schedule=position.version is not None,
        rows=rows,
        unapplied_cash=unapplied,
        allocated_cash=allocated_total,
        confirmed_cash=confirmed_total,
        open_disputes=len(position.open_disputes),
    )
    return SaleSummary(
        sale_id=position.sale.id,
        currency_id=position.sale.currency_id,
        as_of=as_of,
        active_payment_plan_id=position.plan.id if position.plan else None,
        active_payment_plan_version_id=position.version.id if position.version else None,
        scheduled_total=sum((r.scheduled for r in rows), ZERO),
        confirmed_receipts_total=confirmed_total,
        allocated_total=allocated_total,
        unapplied_cash=unapplied,
        outstanding_total=outstanding,
        due_total=due_total,
        overdue_total=overdue_total,
        oldest_overdue_days=oldest,
        installments_total=len(rows),
        installments_paid=sum(1 for r in rows if r.status == ledger.INSTALLMENT_PAID),
        installments_partial=sum(1 for r in rows if r.paid > ZERO and r.outstanding > ZERO),
        installments_overdue=sum(1 for r in rows if r.overdue_days > 0),
        installments_awaiting_trigger=sum(1 for r in rows if r.due_date is None),
        open_disputes=len(position.open_disputes),
        active_waivers=sum(1 for r in rows if r.has_active_waiver),
        next_action_date=extras.next_action_date,
        derived_collection_status=status,
        rows=rows,
        refund_due_total=extras.refund_due_total,
        refund_confirmed_total=extras.refund_confirmed_total,
        refund_outstanding=extras.refund_due_total - extras.refund_confirmed_total,
        collection_clearance_status=extras.collection_clearance_status,
    )


def sale_summary(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor: ActorContext,
    as_of: date | None = None,
) -> SaleSummary:
    """One sale's collections account, for the workspace and the deal file."""
    permissions.require_collection_reader(actor)
    as_of = resolve_as_of(as_of)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    position = load_ledger(session, sale=sale, as_of=as_of)
    return summarise(session, position=position, as_of=as_of)


# --------------------------------------------------------------------------- #
# Status recalculation and the clearance interlock
# --------------------------------------------------------------------------- #


def _unit_of(session: Session, *, sale: SaleContract) -> Unit | None:
    return session.get(Unit, sale.unit_id)


def clearance_blockers_of(summary: SaleSummary) -> list[str]:
    """The reasons this account may not be signed off, in the operator's words.

    Returned as a list rather than a boolean because a disabled button with no
    explanation is the thing this replaces. An officer told "4,250 remains
    outstanding and 500 is unapplied" knows what to do next; one told the action
    is unavailable opens a support ticket.
    """
    blockers: list[str] = []
    if summary.active_payment_plan_version_id is None:
        blockers.append("this sale has no active payment schedule")
    if summary.outstanding_total > ZERO:
        blockers.append(f"{summary.outstanding_total} remains outstanding")
    if summary.unapplied_cash > ZERO:
        blockers.append(f"{summary.unapplied_cash} of confirmed cash is unapplied")
    if summary.open_disputes:
        plural = "s" if summary.open_disputes != 1 else ""
        blockers.append(f"{summary.open_disputes} dispute{plural} remains open")
    return blockers


def recalculate_collection_status(
    session: Session,
    *,
    project: Project,
    sale: SaleContract,
    actor: ActorContext,
    correlation_id: uuid.UUID,
    reason: str,
) -> str:
    """Re-derive this account's position and push it to the domains that own it.

    Called after every write that could move a figure — receipt confirmed or
    reversed, allocation created or reversed, dispute opened or closed, waiver
    decided, restructure applied, refund confirmed. Cheap, and cheaper than the
    alternative: a unit reading ``cleared`` beside a ledger showing forty
    thousand outstanding is the contradiction this integration exists to make
    impossible.

    Two things happen, both inside the caller's transaction:

    * inventory is asked to apply the derived collection status, which it
      ignores when nothing changed rather than writing an event per receipt;
    * a collection clearance that has been given is withdrawn if the financial
      position has reopened underneath it.
    """
    position = load_ledger(session, sale=sale)
    summary = summarise(session, position=position, as_of=business_today())

    unit = _unit_of(session, sale=sale)
    if unit is not None:
        inventory_service.apply_collection_status(
            session,
            project=project,
            unit=unit,
            to_status=summary.derived_collection_status,
            effective_date=business_today(),
            actor_user_id=actor.user_id,
            correlation_id=correlation_id,
            reason=reason,
        )

    if summary.collection_clearance_status == "cleared" and clearance_blockers_of(summary):
        blockers = "; ".join(clearance_blockers_of(summary))
        revoked = sales_service.revoke_collection_clearance(
            session,
            project=project,
            sale_id=sale.id,
            actor_user_id=actor.user_id,
            correlation_id=correlation_id,
            reason=f"The collections ledger reopened: {blockers}.",
        )
        if revoked is not None:
            record_event(
                session,
                action="collections.clearance_auto_revoked",
                entity_type="sale_contract",
                entity_id=sale.id,
                correlation_id=correlation_id,
                actor_user_id=actor.user_id,
                reason=reason,
                after={"sale_number": sale.sale_number, "blockers": blockers},
            )
    return summary.derived_collection_status


# --------------------------------------------------------------------------- #
# Receipts
# --------------------------------------------------------------------------- #


def _require_collectable(sale: SaleContract) -> None:
    if sale.status not in SALE_COLLECTABLE:
        raise ConflictError(
            "Cash can only be recorded against a live contract. This sale is "
            f"{sale.status.replace('_', ' ')}."
        )


def record_receipt(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    sale_id: uuid.UUID,
    amount: Decimal,
    receipt_date: date,
    currency_id: uuid.UUID | None,
    bank_reference: str | None,
    external_reference: str | None,
    notes: str | None,
    correlation_id: uuid.UUID,
) -> CollectionReceipt:
    """Record a claim that money arrived. Not yet cash.

    The receipt is ``recorded``, which moves no balance anywhere. Finance turns
    it into cash by confirming it, and until then it appears on the account
    marked as awaiting confirmation — visible, because a collections officer
    chasing a buyer who has already paid needs to know a transfer is in the
    queue, and not counted, because we have not yet looked at the bank.
    """
    permissions.require_collection_writer(actor)
    project = lock_project(session, project.id)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    _require_collectable(sale)

    if amount <= ZERO:
        raise ValidationError("A receipt must be for a positive amount.")
    today = business_today()
    if receipt_date > today:
        raise ValidationError(
            "A receipt records money that has arrived. It cannot be dated in the future."
        )
    if currency_id is not None and currency_id != sale.currency_id:
        raise ValidationError(
            "A receipt must be in the contract's currency. This MVP settles in the "
            "currency the contract froze and has no exchange-rate model to convert one "
            "into another."
        )

    receipt = CollectionReceipt(
        project_id=project.id,
        sale_contract_id=sale.id,
        receipt_number=_next_number(
            session,
            project=project,
            prefix=_RECEIPT_PREFIX,
            column=CollectionReceipt.receipt_number,
            table=CollectionReceipt,
        ),
        currency_id=sale.currency_id,
        amount=amount,
        receipt_date=receipt_date,
        bank_reference=(bank_reference or "").strip() or None,
        external_reference=(external_reference or "").strip() or None,
        notes=notes,
        status=RECEIPT_RECORDED,
        recorded_by_user_id=actor.user_id,
    )
    session.add(receipt)
    session.flush()
    record_event(
        session,
        action="collections.receipt_recorded",
        entity_type="collection_receipt",
        entity_id=receipt.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "receipt_number": receipt.receipt_number,
            "sale_number": sale.sale_number,
            "amount": receipt.amount,
            "receipt_date": receipt.receipt_date,
        },
    )
    return receipt


def _active_allocations_of_receipt(
    session: Session, *, receipt_id: uuid.UUID
) -> list[CollectionReceiptAllocation]:
    return list(
        session.scalars(
            select(CollectionReceiptAllocation).where(
                CollectionReceiptAllocation.receipt_id == receipt_id,
                CollectionReceiptAllocation.status == ALLOCATION_ACTIVE,
            )
        )
    )


def confirm_receipt(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    receipt_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> CollectionReceipt:
    """Finance accepts that the money arrived. This is where cash becomes cash.

    Confirmation revalidates every proposed allocation under lock rather than
    trusting what was true when they were drafted. The plan can be restructured
    while a receipt sits in the queue, and applying cash to instalments that no
    longer govern the sale would put the money somewhere nobody would ever find
    it again. If the schedule has moved, this refuses and says so.

    This is also the moment the collections boundary closes on the plan: from
    here the ordinary payment-plan activation path will not swap the schedule
    out without carrying the allocations forward.
    """
    permissions.require_finance(actor)
    project = lock_project(session, project.id)
    receipt, sale = visible_receipt(session, project=project, receipt_id=receipt_id, actor=actor)
    plan = _plan_of(session, sale_id=sale.id)
    if plan is not None:
        payment_plans_service.lock_plan(session, project_id=project.id, plan_id=plan.id)
    receipt = _lock_receipt(session, project_id=project.id, receipt_id=receipt.id)

    if receipt.status == RECEIPT_CONFIRMED:
        raise ConflictError("This receipt has already been confirmed.")
    if receipt.status == RECEIPT_REVERSED:
        raise ConflictError("This receipt has been reversed and cannot be confirmed.")
    permissions.require_different_confirmer(actor, recorded_by_user_id=receipt.recorded_by_user_id)

    governing = payment_plans_service.active_version(session, plan_id=plan.id) if plan else None
    for allocation in _active_allocations_of_receipt(session, receipt_id=receipt.id):
        if governing is None or allocation.payment_plan_version_id != governing.id:
            raise ConflictError(
                "The payment plan changed while this receipt was being reviewed. "
                "Reallocate it against the current schedule before confirming."
            )
        installment = _lock_installment(
            session, project_id=project.id, installment_id=allocation.installment_id
        )
        _require_installment_capacity(session, installment=installment, adding=ZERO)

    receipt.status = RECEIPT_CONFIRMED
    receipt.confirmed_at = _now()
    receipt.confirmed_by_user_id = actor.user_id
    session.flush()

    if plan is not None:
        payment_plans_service.mark_collections_started(
            session, project_id=project.id, plan_id=plan.id
        )

    record_event(
        session,
        action="collections.receipt_confirmed",
        entity_type="collection_receipt",
        entity_id=receipt.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "receipt_number": receipt.receipt_number,
            "sale_number": sale.sale_number,
            "amount": receipt.amount,
        },
    )
    recalculate_collection_status(
        session,
        project=project,
        sale=sale,
        actor=actor,
        correlation_id=correlation_id,
        reason=f"Receipt {receipt.receipt_number} confirmed.",
    )
    return receipt


def reverse_receipt(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    receipt_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> CollectionReceipt:
    """Undo a confirmation, and every allocation that depended on it. Atomically.

    The receipt stays on the record, reversed, with the reason on it. Its
    allocations are reversed in the same transaction, so the receivable reopens
    from the ledger rather than from anybody adding an amount back to a stored
    balance — there is no stored balance to add it back to.

    A correction is a reversal plus a fresh receipt. Confirmed cash is never
    edited in place.
    """
    permissions.require_finance(actor)
    reason = _require_text(reason, detail="Say why this receipt is being reversed.")
    project = lock_project(session, project.id)
    receipt, sale = visible_receipt(session, project=project, receipt_id=receipt_id, actor=actor)
    receipt = _lock_receipt(session, project_id=project.id, receipt_id=receipt.id)
    if receipt.status != RECEIPT_CONFIRMED:
        raise ConflictError("Only a confirmed receipt can be reversed.")

    reversed_count = 0
    for allocation in _active_allocations_of_receipt(session, receipt_id=receipt.id):
        _lock_installment(session, project_id=project.id, installment_id=allocation.installment_id)
        allocation.status = ALLOCATION_REVERSED
        allocation.reversed_at = _now()
        allocation.reversed_by_user_id = actor.user_id
        allocation.reversal_reason = f"Receipt {receipt.receipt_number} reversed: {reason}"
        reversed_count += 1

    receipt.status = RECEIPT_REVERSED
    receipt.reversed_at = _now()
    receipt.reversed_by_user_id = actor.user_id
    receipt.reversal_reason = reason
    session.flush()
    record_event(
        session,
        action="collections.receipt_reversed",
        entity_type="collection_receipt",
        entity_id=receipt.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={
            "receipt_number": receipt.receipt_number,
            "sale_number": sale.sale_number,
            "amount": receipt.amount,
            "allocations_reversed": reversed_count,
        },
    )
    recalculate_collection_status(
        session,
        project=project,
        sale=sale,
        actor=actor,
        correlation_id=correlation_id,
        reason=f"Receipt {receipt.receipt_number} reversed.",
    )
    return receipt


def receipts_of_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> list[CollectionReceipt]:
    """Every receipt ever recorded against this sale, reversed ones included."""
    permissions.require_collection_reader(actor)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    return list(
        session.scalars(
            select(CollectionReceipt)
            .where(CollectionReceipt.sale_contract_id == sale.id)
            .order_by(
                CollectionReceipt.receipt_date.desc(),
                CollectionReceipt.receipt_number.desc(),
            )
        )
    )


def allocations_of_receipt(
    session: Session, *, receipt_id: uuid.UUID
) -> list[CollectionReceiptAllocation]:
    """Every allocation ever made from this receipt, in the order they happened."""
    return list(
        session.scalars(
            select(CollectionReceiptAllocation)
            .where(CollectionReceiptAllocation.receipt_id == receipt_id)
            .order_by(CollectionReceiptAllocation.created_at)
        )
    )


def receipt_unapplied(session: Session, *, receipt: CollectionReceipt) -> Decimal:
    """What is left of this receipt. Derived, never stored.

    A stored ``unapplied_amount`` would be a second source of truth that has to
    be updated by six different write paths, and the first one that forgets
    produces a receipt whose parts do not add up to its whole.
    """
    applied = session.scalar(
        select(func.coalesce(func.sum(CollectionReceiptAllocation.amount), 0)).where(
            CollectionReceiptAllocation.receipt_id == receipt.id,
            CollectionReceiptAllocation.status == ALLOCATION_ACTIVE,
        )
    )
    return receipt.amount - _money(applied)


# --------------------------------------------------------------------------- #
# Allocations
# --------------------------------------------------------------------------- #


def _installment_allocated(session: Session, *, installment_id: uuid.UUID) -> Decimal:
    """Active allocations sitting on one instalment, proposals included.

    Proposals count here — and nowhere else. They are excluded from every
    *balance*, because a receipt Finance has not accepted is not cash; but they
    are included in the capacity check, so two officers cannot each draft a
    proposal filling the same instalment and discover at confirmation that only
    one of them can ever be accepted. Reserving the room up front is stricter
    than the invariant requires and turns an unresolvable conflict later into a
    clear refusal now.
    """
    applied = session.scalar(
        select(func.coalesce(func.sum(CollectionReceiptAllocation.amount), 0)).where(
            CollectionReceiptAllocation.installment_id == installment_id,
            CollectionReceiptAllocation.status == ALLOCATION_ACTIVE,
        )
    )
    return _money(applied)


def _require_installment_capacity(
    session: Session, *, installment: PaymentPlanInstallment, adding: Decimal
) -> Decimal:
    """Refuse to put more on an instalment than the instalment asks for.

    Excess cash stays unapplied and visible. Pushing it into an instalment would
    hide an overpayment inside a negative balance, which is the shape in which
    overpayments are discovered years later by the buyer rather than by us.
    """
    scheduled = ledger.scheduled_amount(
        installment.principal_amount, installment.tax_amount, installment.fee_amount
    )
    allocated = _installment_allocated(session, installment_id=installment.id)
    remaining = scheduled - allocated
    if adding > remaining:
        raise ConflictError(
            f"This instalment has only {remaining} remaining. Allocate that or less, and "
            "leave the rest of the receipt unapplied."
        )
    return remaining


def _require_receipt_capacity(
    session: Session, *, receipt: CollectionReceipt, adding: Decimal
) -> Decimal:
    """Refuse to apply more of a receipt than the receipt contains."""
    remaining = receipt_unapplied(session, receipt=receipt)
    if adding > remaining:
        raise ConflictError(f"This receipt has only {remaining} unapplied. Allocate that or less.")
    return remaining


def create_allocation(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    receipt_id: uuid.UUID,
    installment_id: uuid.UUID,
    amount: Decimal,
    correlation_id: uuid.UUID,
) -> CollectionReceiptAllocation:
    """Apply part of a receipt to one instalment of the governing schedule.

    Two capacities are proved under lock: the receipt has this much unapplied,
    and the instalment has this much room. Both rows are taken for update first,
    so two officers filling the same instalment from different receipts take
    turns and the second is told what is actually left rather than writing a
    total that exceeds the amount owed.

    New cash may only be applied to the version currently governing the sale.
    Allocating against a draft, an approved-but-not-active or a superseded
    schedule would attach money to instalments that do not describe what the
    buyer owes, which is how cash becomes invisible.
    """
    permissions.require_collection_writer(actor)
    if amount <= ZERO:
        raise ValidationError("An allocation must be for a positive amount.")

    project = lock_project(session, project.id)
    receipt, sale = visible_receipt(session, project=project, receipt_id=receipt_id, actor=actor)
    plan = _plan_of(session, sale_id=sale.id)
    if plan is None:
        raise ConflictError("This sale has no payment plan to allocate against.")
    governing = payment_plans_service.active_version(session, plan_id=plan.id)
    if governing is None:
        raise ConflictError(
            "This sale has no active payment schedule. Activate one before applying cash."
        )

    installment = session.scalars(
        select(PaymentPlanInstallment).where(
            PaymentPlanInstallment.id == installment_id,
            PaymentPlanInstallment.project_id == project.id,
            PaymentPlanInstallment.payment_plan_version_id == governing.id,
        )
    ).first()
    if installment is None:
        # Missing, in another sale's plan, or on a version that is not the one
        # governing this sale. One refusal for all three.
        raise NotFoundError(_NO_INSTALLMENT)

    installment = _lock_installment(session, project_id=project.id, installment_id=installment.id)
    receipt = _lock_receipt(session, project_id=project.id, receipt_id=receipt.id)
    if receipt.status == RECEIPT_REVERSED:
        raise ConflictError("This receipt has been reversed. Its cash is no longer held.")

    _require_receipt_capacity(session, receipt=receipt, adding=amount)
    _require_installment_capacity(session, installment=installment, adding=amount)

    allocation = CollectionReceiptAllocation(
        project_id=project.id,
        sale_contract_id=sale.id,
        payment_plan_id=plan.id,
        payment_plan_version_id=governing.id,
        installment_id=installment.id,
        receipt_id=receipt.id,
        amount=amount,
        status=ALLOCATION_ACTIVE,
        created_by_user_id=actor.user_id,
    )
    session.add(allocation)
    session.flush()
    record_event(
        session,
        action="collections.allocation_created",
        entity_type="collection_receipt_allocation",
        entity_id=allocation.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "receipt_number": receipt.receipt_number,
            "sale_number": sale.sale_number,
            "installment_sequence": installment.sequence,
            "amount": allocation.amount,
            "receipt_status": receipt.status,
        },
    )
    if receipt.status == RECEIPT_CONFIRMED:
        recalculate_collection_status(
            session,
            project=project,
            sale=sale,
            actor=actor,
            correlation_id=correlation_id,
            reason=f"Receipt {receipt.receipt_number} allocated.",
        )
    return allocation


def reverse_allocation(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    allocation_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> CollectionReceiptAllocation:
    """Take cash back off an instalment. The receipt stays confirmed.

    No money is lost and none is created: the amount returns to the receipt's
    unapplied balance, where it is visible and can be applied somewhere else.
    The reversed row stays, because "this was applied here and then moved" is
    exactly what somebody reconciling the account needs to be able to read.
    """
    permissions.require_collection_writer(actor)
    reason = _require_text(reason, detail="Say why this allocation is being reversed.")
    project = lock_project(session, project.id)

    statement = select(CollectionReceiptAllocation).where(
        CollectionReceiptAllocation.id == allocation_id,
        CollectionReceiptAllocation.project_id == project.id,
    )
    allowed = permissions.visible_sales(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(CollectionReceiptAllocation.sale_contract_id.in_(allowed))
    allocation = session.scalars(statement).first()
    if allocation is None:
        raise NotFoundError(_NO_ALLOCATION)

    sale = _visible_sale(session, project=project, sale_id=allocation.sale_contract_id, actor=actor)
    _lock_installment(session, project_id=project.id, installment_id=allocation.installment_id)
    receipt = _lock_receipt(session, project_id=project.id, receipt_id=allocation.receipt_id)
    session.refresh(allocation)
    if allocation.status != ALLOCATION_ACTIVE:
        raise ConflictError("Only an active allocation can be reversed.")

    allocation.status = ALLOCATION_REVERSED
    allocation.reversed_at = _now()
    allocation.reversed_by_user_id = actor.user_id
    allocation.reversal_reason = reason
    session.flush()
    record_event(
        session,
        action="collections.allocation_reversed",
        entity_type="collection_receipt_allocation",
        entity_id=allocation.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={
            "receipt_number": receipt.receipt_number,
            "sale_number": sale.sale_number,
            "amount": allocation.amount,
        },
    )
    if receipt.status == RECEIPT_CONFIRMED:
        recalculate_collection_status(
            session,
            project=project,
            sale=sale,
            actor=actor,
            correlation_id=correlation_id,
            reason=f"Allocation from {receipt.receipt_number} reversed.",
        )
    return allocation


@dataclass(frozen=True, slots=True)
class SuggestedAllocation:
    """A proposal the operator confirms or changes. Never posted automatically."""

    installment_id: uuid.UUID
    sequence: int
    label: str
    due_date: date | None
    outstanding: Decimal
    amount: Decimal


def suggest_allocation(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    receipt_id: uuid.UUID,
) -> list[SuggestedAllocation]:
    """Where this receipt's unapplied cash would go, oldest actionable first.

    Convenience, not truth. Nothing is written; the allocation rows a person
    confirms are the only record of where money went. Deterministic and dull on
    purpose — oldest due date first, then schedule order — because an operator
    who cannot predict the suggestion stops trusting it and types every line by
    hand anyway.
    """
    permissions.require_collection_reader(actor)
    receipt, sale = visible_receipt(session, project=project, receipt_id=receipt_id, actor=actor)
    if receipt.status == RECEIPT_REVERSED:
        return []
    remaining = receipt_unapplied(session, receipt=receipt)
    if remaining <= ZERO:
        return []

    position = load_ledger(session, sale=sale)
    if position.version is None:
        return []
    rows = _installment_views(position, as_of=business_today())

    actionable = [row for row in rows if row.due_date is not None and row.outstanding > ZERO]
    actionable.sort(key=lambda row: (row.due_date or date.max, row.sequence))

    suggestions: list[SuggestedAllocation] = []
    for row in actionable:
        if remaining <= ZERO:
            break
        # Room already taken by a proposal on this instalment is not offered
        # twice, so a suggestion is always one the operator can actually post.
        room = row.scheduled - _installment_allocated(session, installment_id=row.installment_id)
        if room <= ZERO:
            continue
        take = room if room < remaining else remaining
        suggestions.append(
            SuggestedAllocation(
                installment_id=row.installment_id,
                sequence=row.sequence,
                label=row.label,
                due_date=row.due_date,
                outstanding=row.outstanding,
                amount=take,
            )
        )
        remaining -= take
    return suggestions


# --------------------------------------------------------------------------- #
# Collection actions
# --------------------------------------------------------------------------- #


def record_action(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    sale_id: uuid.UUID,
    installment_id: uuid.UUID | None,
    action_type: str,
    action_at: date,
    notes: str,
    promised_amount: Decimal | None,
    promised_date: date | None,
    next_action_date: date | None,
    correlation_id: uuid.UUID,
) -> CollectionAction:
    """Append what Collections did. There is no update and no delete.

    A promise to pay is recorded here and counted nowhere: a buyer undertaking
    to send ten thousand tomorrow moves no figure in this ledger, because only a
    confirmed receipt does. The promise sits beside the balance so the gap
    between what was said and what arrived is visible, which is the only reason
    to write it down.

    ``action_at`` is something that happened and cannot be in the future.
    ``promised_date`` and ``next_action_date`` are intentions and can be.
    """
    permissions.require_collection_writer(actor)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    notes = _require_text(notes, detail="Record what happened.")

    today = business_today()
    if action_at > today:
        raise ValidationError(
            "A collection action records something that has happened. Use the next "
            "action date to plan one."
        )
    if action_type == ACTION_PROMISE and promised_amount is None:
        raise ValidationError("A promise to pay needs the amount that was promised.")
    if promised_amount is not None and promised_amount <= ZERO:
        raise ValidationError("A promised amount must be positive.")

    if installment_id is not None:
        installment, _, installment_sale = _visible_installment(
            session, project=project, installment_id=installment_id, actor=actor
        )
        if installment_sale.id != sale.id:
            raise NotFoundError(_NO_INSTALLMENT)
        installment_id = installment.id

    action = CollectionAction(
        project_id=project.id,
        sale_contract_id=sale.id,
        installment_id=installment_id,
        action_type=action_type,
        action_at=action_at,
        notes=notes,
        promised_amount=promised_amount,
        promised_date=promised_date,
        next_action_date=next_action_date,
        created_by_user_id=actor.user_id,
    )
    session.add(action)
    session.flush()
    record_event(
        session,
        action="collections.action_recorded",
        entity_type="collection_action",
        entity_id=action.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "sale_number": sale.sale_number,
            "action_type": action_type,
            "action_at": action_at,
            "promised_amount": promised_amount,
            "next_action_date": next_action_date,
        },
    )
    return action


def actions_of_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> list[CollectionAction]:
    """The chase history, most recent first."""
    permissions.require_collection_reader(actor)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    return list(
        session.scalars(
            select(CollectionAction)
            .where(CollectionAction.sale_contract_id == sale.id)
            .order_by(CollectionAction.action_at.desc(), CollectionAction.created_at.desc())
        )
    )


# --------------------------------------------------------------------------- #
# Disputes
# --------------------------------------------------------------------------- #


def open_dispute(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    installment_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> CollectionDispute:
    """Mark an instalment as contested. It stays due, and it stays counted.

    Nothing about the money changes: not the scheduled amount, not what has been
    paid, not the contractual due date, not a single day of aging. A dispute is
    a fact about the conversation with the buyer, and a receivables report that
    quietly dropped disputed amounts would be a report of what we expect to
    collect rather than what we are owed.
    """
    permissions.require_collection_writer(actor)
    reason = _require_text(reason, detail="Say what is being disputed.")
    project = lock_project(session, project.id)
    installment, plan, sale = _visible_installment(
        session, project=project, installment_id=installment_id, actor=actor
    )
    _lock_installment(session, project_id=project.id, installment_id=installment.id)
    _require_governing_installment(session, plan=plan, installment=installment)

    standing = session.scalars(
        select(CollectionDispute).where(
            CollectionDispute.installment_id == installment.id,
            CollectionDispute.status == DISPUTE_OPEN,
        )
    ).first()
    if standing is not None:
        raise ConflictError("This instalment already has an open dispute.")

    dispute = CollectionDispute(
        project_id=project.id,
        sale_contract_id=sale.id,
        installment_id=installment.id,
        status=DISPUTE_OPEN,
        reason=reason,
        opened_by_user_id=actor.user_id,
    )
    session.add(dispute)
    session.flush()
    record_event(
        session,
        action="collections.dispute_opened",
        entity_type="collection_dispute",
        entity_id=dispute.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={
            "sale_number": sale.sale_number,
            "installment_sequence": installment.sequence,
        },
    )
    recalculate_collection_status(
        session,
        project=project,
        sale=sale,
        actor=actor,
        correlation_id=correlation_id,
        reason="Collection dispute opened.",
    )
    return dispute


def _close_dispute(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    dispute_id: uuid.UUID,
    to_status: str,
    resolution: str,
    action: str,
    correlation_id: uuid.UUID,
) -> CollectionDispute:
    permissions.require_collection_writer(actor)
    resolution = _require_text(resolution, detail="Say how this dispute was closed.")
    project = lock_project(session, project.id)

    statement = select(CollectionDispute).where(
        CollectionDispute.id == dispute_id, CollectionDispute.project_id == project.id
    )
    allowed = permissions.visible_sales(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(CollectionDispute.sale_contract_id.in_(allowed))
    dispute = session.scalars(statement.with_for_update()).first()
    if dispute is None:
        raise NotFoundError(_NO_DISPUTE)
    if dispute.status != DISPUTE_OPEN:
        raise ConflictError("This dispute is already closed.")

    sale = _visible_sale(session, project=project, sale_id=dispute.sale_contract_id, actor=actor)
    dispute.status = to_status
    dispute.resolved_at = _now()
    dispute.resolved_by_user_id = actor.user_id
    dispute.resolution = resolution
    session.flush()
    record_event(
        session,
        action=action,
        entity_type="collection_dispute",
        entity_id=dispute.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=resolution,
        after={"sale_number": sale.sale_number, "status": to_status},
    )
    recalculate_collection_status(
        session,
        project=project,
        sale=sale,
        actor=actor,
        correlation_id=correlation_id,
        reason="Collection dispute closed.",
    )
    return dispute


def resolve_dispute(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    dispute_id: uuid.UUID,
    resolution: str,
    correlation_id: uuid.UUID,
) -> CollectionDispute:
    """Close a dispute with an outcome. The balance is exactly where it was."""
    return _close_dispute(
        session,
        project=project,
        actor=actor,
        dispute_id=dispute_id,
        to_status=DISPUTE_RESOLVED,
        resolution=resolution,
        action="collections.dispute_resolved",
        correlation_id=correlation_id,
    )


def withdraw_dispute(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    dispute_id: uuid.UUID,
    resolution: str,
    correlation_id: uuid.UUID,
) -> CollectionDispute:
    """Close a dispute that should not have been raised. The row stays."""
    return _close_dispute(
        session,
        project=project,
        actor=actor,
        dispute_id=dispute_id,
        to_status=DISPUTE_WITHDRAWN,
        resolution=resolution,
        action="collections.dispute_withdrawn",
        correlation_id=correlation_id,
    )


def disputes_of_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> list[CollectionDispute]:
    """Every dispute ever raised on this sale, closed ones included."""
    permissions.require_collection_reader(actor)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    return list(
        session.scalars(
            select(CollectionDispute)
            .where(CollectionDispute.sale_contract_id == sale.id)
            .order_by(CollectionDispute.opened_at.desc())
        )
    )


# --------------------------------------------------------------------------- #
# Waivers
# --------------------------------------------------------------------------- #


def submit_waiver(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    installment_id: uuid.UUID,
    waiver_type: str,
    waived_until: date,
    reason: str,
    correlation_id: uuid.UUID,
) -> CollectionWaiver:
    """Ask the CFO to pause collection action on one instalment.

    What is being asked for is a concession about *chasing*, never about owing.
    The scheduled amount, the tax, the buyer fee and the contract value are
    untouched by anything in this function, and the account keeps reporting the
    balance as outstanding for the whole period of the hold.
    """
    permissions.require_collection_writer(actor)
    reason = _require_text(reason, detail="Say why collection should be paused.")
    project = lock_project(session, project.id)
    installment, plan, sale = _visible_installment(
        session, project=project, installment_id=installment_id, actor=actor
    )
    _lock_installment(session, project_id=project.id, installment_id=installment.id)
    _require_governing_installment(session, plan=plan, installment=installment)

    if waived_until <= business_today():
        raise ValidationError(
            "A waiver runs to a future date. One that has already expired concedes nothing."
        )
    standing = session.scalars(
        select(CollectionWaiver).where(
            CollectionWaiver.installment_id == installment.id,
            CollectionWaiver.status.in_(tuple(WAIVER_LIVE)),
        )
    ).first()
    if standing is not None:
        raise ConflictError("This instalment already has a waiver awaiting a decision or in force.")

    waiver = CollectionWaiver(
        project_id=project.id,
        sale_contract_id=sale.id,
        installment_id=installment.id,
        waiver_type=waiver_type,
        waived_until=waived_until,
        reason=reason,
        status=WAIVER_SUBMITTED,
        submitted_by_user_id=actor.user_id,
    )
    session.add(waiver)
    session.flush()
    record_event(
        session,
        action="collections.waiver_submitted",
        entity_type="collection_waiver",
        entity_id=waiver.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={
            "sale_number": sale.sale_number,
            "installment_sequence": installment.sequence,
            "waiver_type": waiver_type,
            "waived_until": waived_until,
        },
    )
    return waiver


def _decide_waiver(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    waiver_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> tuple[CollectionWaiver, SaleContract, Project]:
    permissions.require_waiver_approver(actor)
    project = lock_project(session, project.id)
    statement = select(CollectionWaiver).where(
        CollectionWaiver.id == waiver_id, CollectionWaiver.project_id == project.id
    )
    allowed = permissions.visible_sales(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(CollectionWaiver.sale_contract_id.in_(allowed))
    waiver = session.scalars(statement.with_for_update()).first()
    if waiver is None:
        raise NotFoundError(_NO_WAIVER)
    sale = _visible_sale(session, project=project, sale_id=waiver.sale_contract_id, actor=actor)
    return waiver, sale, project


def approve_waiver(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    waiver_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> CollectionWaiver:
    """Sanction an operational hold. Nothing about the debt changes."""
    waiver, sale, project = _decide_waiver(
        session,
        project=project,
        actor=actor,
        waiver_id=waiver_id,
        correlation_id=correlation_id,
    )
    if waiver.status != WAIVER_SUBMITTED:
        raise ConflictError("Only a submitted waiver can be approved.")
    permissions.require_different_waiver_approver(
        actor, submitted_by_user_id=waiver.submitted_by_user_id
    )
    waiver.status = WAIVER_APPROVED
    waiver.approved_at = _now()
    waiver.approved_by_user_id = actor.user_id
    session.flush()
    record_event(
        session,
        action="collections.waiver_approved",
        entity_type="collection_waiver",
        entity_id=waiver.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "sale_number": sale.sale_number,
            "waiver_type": waiver.waiver_type,
            "waived_until": waiver.waived_until,
        },
    )
    return waiver


def reject_waiver(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    waiver_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> CollectionWaiver:
    """Refuse a hold. The refused row stays readable."""
    reason = _require_text(reason, detail="Say why this waiver is refused.")
    waiver, sale, project = _decide_waiver(
        session,
        project=project,
        actor=actor,
        waiver_id=waiver_id,
        correlation_id=correlation_id,
    )
    if waiver.status != WAIVER_SUBMITTED:
        raise ConflictError("Only a submitted waiver can be refused.")
    permissions.require_different_waiver_approver(
        actor, submitted_by_user_id=waiver.submitted_by_user_id
    )
    waiver.status = WAIVER_REJECTED
    waiver.rejected_at = _now()
    waiver.rejected_by_user_id = actor.user_id
    waiver.rejection_reason = reason
    session.flush()
    record_event(
        session,
        action="collections.waiver_rejected",
        entity_type="collection_waiver",
        entity_id=waiver.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={"sale_number": sale.sale_number},
    )
    return waiver


def revoke_waiver(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    waiver_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> CollectionWaiver:
    """Withdraw a hold that is in force, and resume collection."""
    reason = _require_text(reason, detail="Say why this waiver is being withdrawn.")
    waiver, sale, project = _decide_waiver(
        session,
        project=project,
        actor=actor,
        waiver_id=waiver_id,
        correlation_id=correlation_id,
    )
    if waiver.status != WAIVER_APPROVED:
        raise ConflictError("Only an approved waiver can be withdrawn.")
    waiver.status = WAIVER_REVOKED
    waiver.revoked_at = _now()
    waiver.revoked_by_user_id = actor.user_id
    waiver.revocation_reason = reason
    session.flush()
    record_event(
        session,
        action="collections.waiver_revoked",
        entity_type="collection_waiver",
        entity_id=waiver.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={"sale_number": sale.sale_number},
    )
    return waiver


def waivers_of_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> list[CollectionWaiver]:
    """Every waiver ever asked for on this sale, refused and revoked included."""
    permissions.require_collection_reader(actor)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    return list(
        session.scalars(
            select(CollectionWaiver)
            .where(CollectionWaiver.sale_contract_id == sale.id)
            .order_by(CollectionWaiver.submitted_at.desc())
        )
    )


# --------------------------------------------------------------------------- #
# Restructures
#
# The contractual schedule is still edited in the Payment Plan Builder and still
# sanctioned by the CFO through PR-MVP-06's lifecycle. There is no second
# instalment editor here and no second approval: one financial decision, one
# approver, one place the schedule is written.
#
# What lives here is the part PR-MVP-06 cannot know: cash has already been
# received against the schedule being replaced, and every unit of it has to land
# on the new one in the same transaction that activates it.
# --------------------------------------------------------------------------- #


def _open_restructure(session: Session, *, plan_id: uuid.UUID) -> CollectionRestructure | None:
    return session.scalars(
        select(CollectionRestructure).where(
            CollectionRestructure.payment_plan_id == plan_id,
            CollectionRestructure.status == RESTRUCTURE_OPEN,
        )
    ).first()


def create_restructure(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    sale_id: uuid.UUID,
    reason: str,
    effective_date: date | None,
    correlation_id: uuid.UUID,
) -> tuple[CollectionRestructure, PaymentPlanVersion]:
    """Raise a restructure and open the revision it will carry the cash onto.

    The active schedule keeps governing the sale and its allocations stay
    active for the whole time the replacement is being drafted and reviewed.
    Nothing moves until :func:`apply_restructure`, so a revision abandoned
    halfway leaves the account exactly as it was.
    """
    permissions.require_collection_writer(actor)
    reason = _require_text(reason, detail="Say why this schedule is being restructured.")
    project = lock_project(session, project.id)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)

    plan = _plan_of(session, sale_id=sale.id)
    if plan is None:
        raise ConflictError("This sale has no payment plan to restructure.")
    plan = payment_plans_service.lock_plan(session, project_id=project.id, plan_id=plan.id)
    source = payment_plans_service.active_version(session, plan_id=plan.id)
    if source is None:
        raise ConflictError("This plan has no active schedule to replace.")
    if plan.collections_started_at is None:
        raise ConflictError(
            "No cash has been confirmed against this plan, so there is nothing to carry "
            "forward. Revise the schedule through the payment plan directly."
        )
    if _open_restructure(session, plan_id=plan.id) is not None:
        raise ConflictError(
            "This plan already has a restructure in progress. Finish or abandon it first."
        )
    if payment_plans_service.open_version(session, plan_id=plan.id) is not None:
        raise ConflictError(
            "This plan already has a version in preparation. Finish or reject it before "
            "raising a restructure."
        )

    number = _next_number(
        session,
        project=project,
        prefix=_RESTRUCTURE_PREFIX,
        column=CollectionRestructure.restructure_number,
        table=CollectionRestructure,
    )
    replacement = payment_plans_service.create_version(
        session,
        project=project,
        actor=actor,
        plan_id=plan.id,
        change_reason=f"Collections restructure {number}: {reason}",
        reservation_treatment=None,
        effective_date=effective_date,
        correlation_id=correlation_id,
    )
    restructure = CollectionRestructure(
        project_id=project.id,
        sale_contract_id=sale.id,
        payment_plan_id=plan.id,
        restructure_number=number,
        source_version_id=source.id,
        replacement_version_id=replacement.id,
        status=RESTRUCTURE_OPEN,
        reason=reason,
        requested_by_user_id=actor.user_id,
    )
    session.add(restructure)
    session.flush()
    record_event(
        session,
        action="collections.restructure_created",
        entity_type="collection_restructure",
        entity_id=restructure.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={
            "restructure_number": number,
            "sale_number": sale.sale_number,
            "source_version_number": source.version_number,
            "replacement_version_number": replacement.version_number,
        },
    )
    return restructure, replacement


@dataclass(frozen=True, slots=True)
class CarryPreview:
    """What applying a restructure would do, before anybody commits to it."""

    restructure_id: uuid.UUID
    source_version_id: uuid.UUID
    replacement_version_id: uuid.UUID
    replacement_status: str
    ready_to_apply: bool
    blockers: list[str]
    carried_total: Decimal
    unapplied_total: Decimal
    confirmed_receipts_total: Decimal
    lines: list[ledger.CarryLine]
    superseding: int


def _carry_sources(
    session: Session, *, version_id: uuid.UUID
) -> tuple[list[ledger.CarrySource], list[CollectionReceiptAllocation]]:
    """Each receipt's currently active allocated total against one version.

    Ordered oldest receipt first so the plan is reproducible: the same
    restructure previewed twice must place the same money on the same rows, or
    the preview is not a promise about what applying will do.

    A receipt's *unapplied* balance is deliberately not a source. A restructure
    moves cash that somebody already chose to apply; turning it into an
    opportunity to apply the rest would be an automatic allocation nobody asked
    for.
    """
    allocations = list(
        session.scalars(
            select(CollectionReceiptAllocation).where(
                CollectionReceiptAllocation.payment_plan_version_id == version_id,
                CollectionReceiptAllocation.status == ALLOCATION_ACTIVE,
            )
        )
    )
    totals: dict[uuid.UUID, Decimal] = {}
    for allocation in allocations:
        totals[allocation.receipt_id] = totals.get(allocation.receipt_id, ZERO) + allocation.amount
    if not totals:
        return [], allocations
    ordered = list(
        session.scalars(
            select(CollectionReceipt)
            .where(CollectionReceipt.id.in_(list(totals)))
            .order_by(
                CollectionReceipt.receipt_date,
                CollectionReceipt.receipt_number,
                CollectionReceipt.id,
            )
        )
    )
    sources = [
        ledger.CarrySource(receipt_id=receipt.id, amount=totals[receipt.id]) for receipt in ordered
    ]
    return sources, allocations


def _carry_targets(session: Session, *, version_id: uuid.UUID) -> list[ledger.CarryTarget]:
    """The replacement instalments, due date first and then schedule order."""
    rows = payment_plans_service.installments_of(session, version_id=version_id)
    rows.sort(key=lambda row: (row.contractual_due_date or date.max, row.sequence))
    return [
        ledger.CarryTarget(
            installment_id=row.id,
            capacity=ledger.scheduled_amount(row.principal_amount, row.tax_amount, row.fee_amount),
        )
        for row in rows
    ]


def preview_restructure(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    restructure_id: uuid.UUID,
) -> CarryPreview:
    """Show exactly where the cash would land, and what still blocks applying.

    Computed with the same functions the apply path uses, so the preview is not
    a separate estimate that can disagree with the thing it previews.
    """
    permissions.require_collection_reader(actor)
    statement = select(CollectionRestructure).where(
        CollectionRestructure.id == restructure_id,
        CollectionRestructure.project_id == project.id,
    )
    allowed = permissions.visible_sales(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(CollectionRestructure.sale_contract_id.in_(allowed))
    restructure = session.scalars(statement).first()
    if restructure is None:
        raise NotFoundError(_NO_RESTRUCTURE)

    replacement = session.get(PaymentPlanVersion, restructure.replacement_version_id)
    sale = session.get(SaleContract, restructure.sale_contract_id)
    position = load_ledger(session, sale=sale) if sale else None
    sources, existing = _carry_sources(session, version_id=restructure.source_version_id)
    targets = _carry_targets(session, version_id=restructure.replacement_version_id)

    blockers: list[str] = []
    if restructure.status != RESTRUCTURE_OPEN:
        blockers.append(f"this restructure is {restructure.status}")
    if replacement is None or replacement.status != VERSION_APPROVED:
        blockers.append("the replacement schedule has not been approved yet")
    elif replacement.effective_date > business_today():
        blockers.append(
            f"the replacement schedule takes effect on {replacement.effective_date.isoformat()}"
        )

    lines: list[ledger.CarryLine] = []
    try:
        lines = ledger.plan_carry_forward(sources, targets)
    except ledger.CarryForwardError as error:
        blockers.append(str(error))

    return CarryPreview(
        restructure_id=restructure.id,
        source_version_id=restructure.source_version_id,
        replacement_version_id=restructure.replacement_version_id,
        replacement_status=replacement.status if replacement else "missing",
        ready_to_apply=not blockers,
        blockers=blockers,
        carried_total=ledger.total_of(lines),
        unapplied_total=(
            summarise(session, position=position, as_of=business_today()).unapplied_cash
            if position
            else ZERO
        ),
        confirmed_receipts_total=(
            sum((r.amount for r in position.confirmed_receipts), ZERO) if position else ZERO
        ),
        lines=lines,
        superseding=len(existing),
    )


def _require_no_unresolved_exceptions(
    session: Session, *, sale_id: uuid.UUID, version_id: uuid.UUID
) -> None:
    """Refuse the restructure while the schedule it replaces is still contested.

    An open dispute and a live waiver are decisions somebody took about specific
    instalments of a specific schedule. The replacement's instalments are new
    rows with new identifiers, new amounts and new dates, so there is no honest
    automatic answer to "which of the new ones is the disputed one?" — the
    amount may have been split across three, or folded into one, or moved past
    the date the hold ran to.

    Migrating them anyway would be the system inventing a commercial decision
    nobody made. So it refuses and names what to close first. Cash is carried
    forward because a unit of cash is a unit of cash whatever schedule it lands
    on; a judgement is not.
    """
    installment_ids = select(PaymentPlanInstallment.id).where(
        PaymentPlanInstallment.payment_plan_version_id == version_id
    )
    disputes = session.scalar(
        select(func.count())
        .select_from(CollectionDispute)
        .where(
            CollectionDispute.sale_contract_id == sale_id,
            CollectionDispute.status == DISPUTE_OPEN,
            CollectionDispute.installment_id.in_(installment_ids),
        )
    )
    if disputes:
        raise ConflictError(
            "This schedule still has an open dispute. Resolve or withdraw it before "
            "restructuring, so the outcome is recorded against the instalment it was "
            "actually about."
        )
    waivers = session.scalar(
        select(func.count())
        .select_from(CollectionWaiver)
        .where(
            CollectionWaiver.sale_contract_id == sale_id,
            CollectionWaiver.status.in_(tuple(WAIVER_LIVE)),
            CollectionWaiver.installment_id.in_(installment_ids),
        )
    )
    if waivers:
        raise ConflictError(
            "This schedule still has a waiver awaiting a decision or in force. Decide "
            "or revoke it before restructuring — a hold on an instalment that is about "
            "to be replaced cannot be carried to a schedule it was never granted for."
        )


def apply_restructure(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    restructure_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> CollectionRestructure:
    """Carry the cash forward and activate the replacement. One transaction.

    The order matters and is not negotiable: the allocations move *first*, and
    only if every one of them lands does the replacement schedule become the one
    governing the sale. Activating first and moving the money afterwards would
    leave a window — and, if the move then failed, a live schedule with cash
    stranded against a superseded one.

    If a single unit of cash cannot be placed on the new schedule, this raises
    and nothing happens: the old version stays active, its allocations stay
    active, the replacement stays approved, and the restructure stays open. No
    penny vanishes and no penny appears twice.
    """
    permissions.require_collection_writer(actor)
    project = lock_project(session, project.id)
    restructure = _lock_restructure(session, project_id=project.id, restructure_id=restructure_id)
    sale = _visible_sale(
        session, project=project, sale_id=restructure.sale_contract_id, actor=actor
    )
    if restructure.status != RESTRUCTURE_OPEN:
        raise ConflictError(f"This restructure is already {restructure.status}.")

    plan = payment_plans_service.lock_plan(
        session, project_id=project.id, plan_id=restructure.payment_plan_id
    )
    source = payment_plans_service.lock_version(
        session, project_id=project.id, version_id=restructure.source_version_id
    )
    replacement = payment_plans_service.lock_version(
        session, project_id=project.id, version_id=restructure.replacement_version_id
    )

    governing = payment_plans_service.active_version(session, plan_id=plan.id)
    if governing is None or governing.id != source.id:
        raise ConflictError(
            "The schedule this restructure was raised against is no longer the one "
            "governing the sale. Raise a new restructure against the current schedule."
        )
    if replacement.status != VERSION_APPROVED:
        raise ConflictError(
            "The replacement schedule has not been approved. The CFO sanctions it in the "
            "payment plan, and the restructure applies it here."
        )
    _require_no_unresolved_exceptions(session, sale_id=sale.id, version_id=source.id)

    sources, existing = _carry_sources(session, version_id=source.id)
    targets = _carry_targets(session, version_id=replacement.id)
    for target in targets:
        _lock_installment(session, project_id=project.id, installment_id=target.installment_id)
    for allocation in existing:
        _lock_installment(session, project_id=project.id, installment_id=allocation.installment_id)

    before_total = sum((s.amount for s in sources), ZERO)
    lines = ledger.plan_carry_forward(sources, targets)
    carried = ledger.total_of(lines)
    if carried != before_total:  # pragma: no cover - the planner raises first
        raise ConflictError(
            "The cash already collected cannot be carried onto the replacement schedule "
            "exactly. The restructure has not been applied."
        )

    now = _now()
    for allocation in existing:
        allocation.status = ALLOCATION_SUPERSEDED
        allocation.superseded_at = now
        allocation.superseded_by_restructure_id = restructure.id
    session.flush()

    for line in lines:
        session.add(
            CollectionReceiptAllocation(
                project_id=project.id,
                sale_contract_id=sale.id,
                payment_plan_id=plan.id,
                payment_plan_version_id=replacement.id,
                installment_id=line.installment_id,
                receipt_id=line.receipt_id,
                amount=line.amount,
                status=ALLOCATION_ACTIVE,
                created_by_user_id=actor.user_id,
            )
        )
    session.flush()

    payment_plans_service.activate_restructured_version(
        session,
        project=project,
        actor=actor,
        plan=plan,
        version=replacement,
        correlation_id=correlation_id,
    )

    restructure.status = RESTRUCTURE_APPLIED
    restructure.applied_at = now
    restructure.applied_by_user_id = actor.user_id
    session.flush()
    record_event(
        session,
        action="collections.restructure_applied",
        entity_type="collection_restructure",
        entity_id=restructure.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=restructure.reason,
        after={
            "restructure_number": restructure.restructure_number,
            "sale_number": sale.sale_number,
            "cash_carried": carried,
            "allocations_superseded": len(existing),
            "allocations_created": len(lines),
            "replacement_version_number": replacement.version_number,
        },
    )
    recalculate_collection_status(
        session,
        project=project,
        sale=sale,
        actor=actor,
        correlation_id=correlation_id,
        reason=f"Restructure {restructure.restructure_number} applied.",
    )
    return restructure


def abandon_restructure(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    restructure_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> CollectionRestructure:
    """Close a restructure that is not going to happen.

    Needed because the CFO can refuse the replacement schedule, and PR-MVP-06
    makes a rejected version terminal. Without this the refusal would leave the
    restructure open for ever and the plan unable to be restructured again — one
    declined revision permanently blocking the only safe way to reschedule a
    collected plan.

    Nothing financial moves. No allocation is touched, and the active schedule
    was never replaced.
    """
    permissions.require_collection_writer(actor)
    reason = _require_text(reason, detail="Say why this restructure is being abandoned.")
    project = lock_project(session, project.id)
    restructure = _lock_restructure(session, project_id=project.id, restructure_id=restructure_id)
    sale = _visible_sale(
        session, project=project, sale_id=restructure.sale_contract_id, actor=actor
    )
    if restructure.status != RESTRUCTURE_OPEN:
        raise ConflictError(f"This restructure is already {restructure.status}.")

    restructure.status = RESTRUCTURE_ABANDONED
    restructure.abandoned_at = _now()
    restructure.abandoned_by_user_id = actor.user_id
    restructure.abandonment_reason = reason
    session.flush()
    record_event(
        session,
        action="collections.restructure_abandoned",
        entity_type="collection_restructure",
        entity_id=restructure.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={
            "restructure_number": restructure.restructure_number,
            "sale_number": sale.sale_number,
        },
    )
    return restructure


def restructures_of_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> list[CollectionRestructure]:
    """Every restructure ever raised on this sale."""
    permissions.require_collection_reader(actor)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    return list(
        session.scalars(
            select(CollectionRestructure)
            .where(CollectionRestructure.sale_contract_id == sale.id)
            .order_by(CollectionRestructure.requested_at.desc())
        )
    )


# --------------------------------------------------------------------------- #
# Refunds
#
# Money leaving, in its own table. PR-MVP-05 recorded what a cancellation makes
# *due* and was careful never to call it paid; this is the other half, and the
# two are reported side by side rather than netted, because "we owe them twelve
# thousand" and "we have paid them five" are different sentences.
# --------------------------------------------------------------------------- #


def _confirmed_refund_total(session: Session, *, cancellation_id: uuid.UUID) -> Decimal:
    total = session.scalar(
        select(func.coalesce(func.sum(CollectionRefund.amount), 0)).where(
            CollectionRefund.cancellation_id == cancellation_id,
            CollectionRefund.status == REFUND_CONFIRMED,
        )
    )
    return _money(total)


def _require_refund_headroom(
    session: Session,
    *,
    cancellation: SaleCancellation,
    adding: Decimal,
) -> Decimal:
    """Refuse to pay back more than the approved cancellation says is owed.

    The cancellation's own financial approval is the authority for *how much*;
    nothing here re-decides that. This only stops the sum of what actually left
    from exceeding it.
    """
    due = cancellation.refund_due_amount
    if due is None:
        raise ConflictError(
            "This cancellation has no approved refund amount, so there is nothing to "
            "repay. The amount due is settled on the cancellation."
        )
    already = _confirmed_refund_total(session, cancellation_id=cancellation.id)
    remaining = due - already
    if adding > remaining:
        raise ConflictError(
            f"This cancellation has {remaining} still due. A refund cannot exceed it."
        )
    return remaining


def record_refund(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    sale_id: uuid.UUID,
    cancellation_id: uuid.UUID,
    amount: Decimal,
    refund_date: date,
    currency_id: uuid.UUID | None,
    bank_reference: str | None,
    notes: str | None,
    correlation_id: uuid.UUID,
) -> CollectionRefund:
    """Record a repayment being made against a cancellation. Not yet cash out.

    Partial refunds are ordinary: several transfers against one cancellation is
    how this is usually settled, and requiring one transaction to equal the
    whole amount due would push operators into recording a payment that did not
    happen.
    """
    permissions.require_collection_writer(actor)
    project = lock_project(session, project.id)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)

    cancellation = session.scalars(
        select(SaleCancellation).where(
            SaleCancellation.id == cancellation_id,
            SaleCancellation.project_id == project.id,
            SaleCancellation.sale_contract_id == sale.id,
        )
    ).first()
    if cancellation is None:
        raise NotFoundError("Cancellation not found.")

    if amount <= ZERO:
        raise ValidationError("A refund must be for a positive amount.")
    if refund_date > business_today():
        raise ValidationError(
            "A refund records money that has left. It cannot be dated in the future."
        )
    if currency_id is not None and currency_id != sale.currency_id:
        raise ValidationError("A refund must be in the contract's currency.")
    _require_refund_headroom(session, cancellation=cancellation, adding=amount)

    refund = CollectionRefund(
        project_id=project.id,
        sale_contract_id=sale.id,
        cancellation_id=cancellation.id,
        refund_number=_next_number(
            session,
            project=project,
            prefix=_REFUND_PREFIX,
            column=CollectionRefund.refund_number,
            table=CollectionRefund,
        ),
        currency_id=sale.currency_id,
        amount=amount,
        refund_date=refund_date,
        bank_reference=(bank_reference or "").strip() or None,
        notes=notes,
        status=REFUND_RECORDED,
        recorded_by_user_id=actor.user_id,
    )
    session.add(refund)
    session.flush()
    record_event(
        session,
        action="collections.refund_recorded",
        entity_type="collection_refund",
        entity_id=refund.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "refund_number": refund.refund_number,
            "sale_number": sale.sale_number,
            "amount": refund.amount,
            "refund_date": refund.refund_date,
        },
    )
    return refund


def _visible_refund(
    session: Session, *, project: Project, refund_id: uuid.UUID, actor: ActorContext
) -> tuple[CollectionRefund, SaleContract]:
    statement = select(CollectionRefund).where(
        CollectionRefund.id == refund_id, CollectionRefund.project_id == project.id
    )
    allowed = permissions.visible_sales(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(CollectionRefund.sale_contract_id.in_(allowed))
    refund = session.scalars(statement).first()
    if refund is None:
        raise NotFoundError(_NO_REFUND)
    sale = _visible_sale(session, project=project, sale_id=refund.sale_contract_id, actor=actor)
    return refund, sale


def confirm_refund(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    refund_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> CollectionRefund:
    """Finance confirms that the money actually left.

    The cancellation row is taken for update first, because "confirmed refunds
    do not exceed the amount due" is an invariant that spans rows and belongs to
    the cancellation. Two Finance officers confirming two refunds at once take
    turns, and the second is told what is really left.
    """
    permissions.require_finance(actor)
    project = lock_project(session, project.id)
    refund, sale = _visible_refund(session, project=project, refund_id=refund_id, actor=actor)
    cancellation = _lock_cancellation(
        session, project_id=project.id, cancellation_id=refund.cancellation_id
    )
    refund = _lock_refund(session, project_id=project.id, refund_id=refund.id)

    if refund.status == REFUND_CONFIRMED:
        raise ConflictError("This refund has already been confirmed.")
    if refund.status == REFUND_REVERSED:
        raise ConflictError("This refund has been reversed and cannot be confirmed.")
    permissions.require_different_confirmer(actor, recorded_by_user_id=refund.recorded_by_user_id)
    _require_refund_headroom(session, cancellation=cancellation, adding=refund.amount)

    refund.status = REFUND_CONFIRMED
    refund.confirmed_at = _now()
    refund.confirmed_by_user_id = actor.user_id
    session.flush()
    record_event(
        session,
        action="collections.refund_confirmed",
        entity_type="collection_refund",
        entity_id=refund.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "refund_number": refund.refund_number,
            "sale_number": sale.sale_number,
            "amount": refund.amount,
        },
    )
    return refund


def reverse_refund(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    refund_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID,
) -> CollectionRefund:
    """Undo a confirmed refund. The row stays, reversed, with the reason on it."""
    permissions.require_finance(actor)
    reason = _require_text(reason, detail="Say why this refund is being reversed.")
    project = lock_project(session, project.id)
    refund, sale = _visible_refund(session, project=project, refund_id=refund_id, actor=actor)
    _lock_cancellation(session, project_id=project.id, cancellation_id=refund.cancellation_id)
    refund = _lock_refund(session, project_id=project.id, refund_id=refund.id)
    if refund.status != REFUND_CONFIRMED:
        raise ConflictError("Only a confirmed refund can be reversed.")

    refund.status = REFUND_REVERSED
    refund.reversed_at = _now()
    refund.reversed_by_user_id = actor.user_id
    refund.reversal_reason = reason
    session.flush()
    record_event(
        session,
        action="collections.refund_reversed",
        entity_type="collection_refund",
        entity_id=refund.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        after={
            "refund_number": refund.refund_number,
            "sale_number": sale.sale_number,
            "amount": refund.amount,
        },
    )
    return refund


def refunds_of_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> list[CollectionRefund]:
    """Every refund ever recorded against this sale, reversed ones included."""
    permissions.require_collection_reader(actor)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    return list(
        session.scalars(
            select(CollectionRefund)
            .where(CollectionRefund.sale_contract_id == sale.id)
            .order_by(CollectionRefund.refund_date.desc(), CollectionRefund.refund_number.desc())
        )
    )


# --------------------------------------------------------------------------- #
# The collection clearance
# --------------------------------------------------------------------------- #


def grant_collection_clearance(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    sale_id: uuid.UUID,
    evidence_reference: str,
    correlation_id: uuid.UUID,
) -> str:
    """Sign off that this account is financially clear, against the ledger.

    Not an approval and not a CFO decision: it is the Collections department
    attesting that its own books are clear, and it is checked against objective
    figures rather than taken on trust. Until PR-MVP-07 there was nothing to
    check against and the same signature was worth much less.

    The three conditions are the strict ones. Nothing outstanding, nothing
    unapplied, nothing disputed — a buyer who owes nothing but has an
    unresolved overpayment is not a file to close.
    """
    permissions.require_collection_writer(actor)
    evidence_reference = _require_text(
        evidence_reference, detail="Record the reference of the evidence for this clearance."
    )
    project = lock_project(session, project.id)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)

    position = load_ledger(session, sale=sale)
    summary = summarise(session, position=position, as_of=business_today())
    blockers = clearance_blockers_of(summary)
    if blockers:
        raise ConflictError("Collection clearance cannot be granted: " + "; ".join(blockers) + ".")

    sales_service.apply_collection_clearance(
        session,
        project=project,
        sale_id=sale.id,
        actor_user_id=actor.user_id,
        correlation_id=correlation_id,
        evidence_reference=evidence_reference,
    )
    record_event(
        session,
        action="collections.clearance_granted",
        entity_type="sale_contract",
        entity_id=sale.id,
        correlation_id=correlation_id,
        actor_user_id=actor.user_id,
        after={
            "sale_number": sale.sale_number,
            "evidence_reference": evidence_reference,
            "outstanding_total": summary.outstanding_total,
            "unapplied_cash": summary.unapplied_cash,
        },
    )
    return "cleared"


def clearance_blockers(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> list[str]:
    """Exactly what stands between this account and its clearance, in words."""
    permissions.require_collection_reader(actor)
    sale = _visible_sale(session, project=project, sale_id=sale_id, actor=actor)
    position = load_ledger(session, sale=sale)
    return clearance_blockers_of(summarise(session, position=position, as_of=business_today()))


# --------------------------------------------------------------------------- #
# The project registers
#
# Batched, deliberately. PR-MVP-06 learned this the expensive way: a register
# that asks one question per sale is fine on the twelve rows a developer tests
# with and unusable on the eight hundred a real development has. Everything
# below reads its tables in a fixed handful of queries whatever the row count,
# and assembles in memory.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RegisterRow:
    """One account as the collections workspace lists it."""

    sale_id: uuid.UUID
    sale_number: str
    spa_number: str | None
    unit_id: uuid.UUID
    unit_number: str
    client_display_name: str
    currency_id: uuid.UUID
    summary: SaleSummary


def _visible_sales_for_register(
    session: Session, *, project: Project, actor: ActorContext
) -> list[tuple[SaleContract, Unit, Client]]:
    """Every sale this caller may see, with the unit and buyer, in one query."""
    statement = (
        select(SaleContract, Unit, Client)
        .join(Unit, Unit.id == SaleContract.unit_id)
        .join(Client, Client.id == SaleContract.client_id)
        .where(SaleContract.project_id == project.id)
    )
    allowed = permissions.visible_sales(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(SaleContract.id.in_(allowed))
    return [
        (sale, unit, client)
        for sale, unit, client in session.execute(
            statement.order_by(SaleContract.sale_number)
        ).all()
    ]


def _group(rows: list, key: str) -> dict[uuid.UUID, list]:
    grouped: dict[uuid.UUID, list] = {}
    for row in rows:
        grouped.setdefault(getattr(row, key), []).append(row)
    return grouped


def collection_register(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    as_of: date | None = None,
) -> list[RegisterRow]:
    """Every account this caller may see, with its whole collections position.

    Eleven queries, whatever the number of sales. Each answers one question for
    every row at once — which sales, which plans, which schedules were governing
    on the date, which instalments, which receipts counted as cash then, which
    allocations were live then, which disputes were open, which waivers were in
    force, which follow-ups had been written down, which contracts had been
    unwound, and how the refunds stood — and the rows are then assembled without
    touching the database again.

    Every one of those is asked *as at* ``as_of``. A register that reconstructed
    the receivable historically and then read today's cancellations beside it
    would be two reporting dates in one table, and no column would say which.
    """
    permissions.require_collection_reader(actor)
    as_of = resolve_as_of(as_of)
    visible = _visible_sales_for_register(session, project=project, actor=actor)
    if not visible:
        return []

    sale_ids = [sale.id for sale, _, _ in visible]

    plans = list(
        session.scalars(select(PaymentPlan).where(PaymentPlan.sale_contract_id.in_(sale_ids)))
    )
    plan_by_sale = {plan.sale_contract_id: plan for plan in plans}
    plan_ids = [plan.id for plan in plans]

    versions = (
        list(
            session.scalars(
                select(PaymentPlanVersion).where(
                    PaymentPlanVersion.payment_plan_id.in_(plan_ids),
                    _version_governing_on(as_of),
                )
            )
        )
        if plan_ids
        else []
    )
    version_by_plan = {version.payment_plan_id: version for version in versions}
    version_ids = [version.id for version in versions]

    installments = (
        list(
            session.scalars(
                select(PaymentPlanInstallment)
                .where(PaymentPlanInstallment.payment_plan_version_id.in_(version_ids))
                .order_by(PaymentPlanInstallment.sequence)
            )
        )
        if version_ids
        else []
    )
    rows_by_version = _group(installments, "payment_plan_version_id")

    receipts = list(
        session.scalars(
            select(CollectionReceipt)
            .where(
                CollectionReceipt.sale_contract_id.in_(sale_ids),
                _receipt_effective_on(as_of),
            )
            .order_by(CollectionReceipt.receipt_date, CollectionReceipt.receipt_number)
        )
    )
    receipts_by_sale = _group(receipts, "sale_contract_id")

    allocations = list(
        session.scalars(
            select(CollectionReceiptAllocation).where(
                CollectionReceiptAllocation.sale_contract_id.in_(sale_ids),
                _allocation_effective_on(as_of),
            )
        )
    )
    allocations_by_sale = _group(allocations, "sale_contract_id")

    disputes = list(
        session.scalars(
            select(CollectionDispute).where(
                CollectionDispute.sale_contract_id.in_(sale_ids),
                _dispute_open_on(as_of),
            )
        )
    )
    disputes_by_sale = _group(disputes, "sale_contract_id")

    waivers = list(
        session.scalars(
            select(CollectionWaiver).where(
                CollectionWaiver.sale_contract_id.in_(sale_ids),
                _waiver_live_on(as_of),
            )
        )
    )
    waivers_by_sale = _group(waivers, "sale_contract_id")

    next_actions = dict(
        session.execute(
            select(
                CollectionAction.sale_contract_id,
                func.min(CollectionAction.next_action_date),
            )
            .where(
                CollectionAction.sale_contract_id.in_(sale_ids),
                CollectionAction.next_action_date >= as_of,
                _action_recorded_on(as_of),
            )
            .group_by(CollectionAction.sale_contract_id)
        ).all()
    )

    refunds_due = {
        sale_id: _money(total)
        for sale_id, total in session.execute(
            select(
                SaleCancellation.sale_contract_id,
                func.coalesce(func.sum(SaleCancellation.refund_due_amount), 0),
            )
            .where(
                SaleCancellation.sale_contract_id.in_(sale_ids),
                _refund_due_on(as_of),
            )
            .group_by(SaleCancellation.sale_contract_id)
        ).all()
    }
    refunds_paid = {
        sale_id: _money(total)
        for sale_id, total in session.execute(
            select(
                CollectionRefund.sale_contract_id,
                func.coalesce(func.sum(CollectionRefund.amount), 0),
            )
            .where(
                CollectionRefund.sale_contract_id.in_(sale_ids),
                _refund_effective_on(as_of),
            )
            .group_by(CollectionRefund.sale_contract_id)
        ).all()
    }

    # Which of these contracts had actually been unwound by the cutoff. One
    # query for the whole register, because "was this cancelled in March?" is a
    # question about a date and answering it per sale would put the register
    # back to a query per row — the thing its budget test exists to prevent.
    cancelled_ids = set(
        session.scalars(
            select(SaleCancellation.sale_contract_id).where(
                SaleCancellation.sale_contract_id.in_(sale_ids),
                _cancelled_on(as_of),
            )
        )
    )

    register: list[RegisterRow] = []
    for sale, unit, client in visible:
        plan = plan_by_sale.get(sale.id)
        version = version_by_plan.get(plan.id) if plan else None
        schedule = rows_by_version.get(version.id, []) if version else []
        governing_ids = {row.id for row in schedule}
        position = SaleLedger(
            sale=sale,
            as_of=as_of,
            sale_cancelled=sale.id in cancelled_ids,
            plan=plan,
            version=version,
            installments=schedule,
            confirmed_receipts=receipts_by_sale.get(sale.id, []),
            allocations=allocations_by_sale.get(sale.id, []),
            open_disputes=[
                row
                for row in disputes_by_sale.get(sale.id, [])
                if row.installment_id in governing_ids
            ],
            live_waivers=[
                row
                for row in waivers_by_sale.get(sale.id, [])
                if row.installment_id in governing_ids
            ],
        )
        extras = SaleExtras(
            next_action_date=next_actions.get(sale.id),
            refund_due_total=refunds_due.get(sale.id, ZERO),
            refund_confirmed_total=refunds_paid.get(sale.id, ZERO),
            # Not read per row: the clearance belongs on the account screen,
            # and joining every handover into the register would buy a column
            # nobody filters on at the cost of the query budget this exists to
            # protect.
            collection_clearance_status=None,
        )
        register.append(
            RegisterRow(
                sale_id=sale.id,
                sale_number=sale.sale_number,
                spa_number=sale.spa_number,
                unit_id=unit.id,
                unit_number=unit.unit_number,
                client_display_name=client.display_name,
                currency_id=sale.currency_id,
                summary=summarise(session, position=position, as_of=as_of, extras=extras),
            )
        )
    return register


@dataclass(frozen=True, slots=True)
class AgingRow:
    """One instalment on the aging report, with the account it belongs to."""

    sale_id: uuid.UUID
    sale_number: str
    unit_number: str
    client_display_name: str
    currency_id: uuid.UUID
    installment: ledger.InstallmentView


def aging_report(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    as_of: date | None = None,
    overdue_only: bool = False,
) -> list[AgingRow]:
    """Every live instalment, aged as at ``as_of``. Oldest debt first.

    ``as_of`` is a real parameter and not decoration: "what was the aging on 31
    August?" is a question month-end reporting and an auditor both ask, and it
    is answerable here because nothing is stored — there are no nightly
    snapshots to have missed a day, only rows and arithmetic.
    """
    as_of = resolve_as_of(as_of)
    rows: list[AgingRow] = []
    for entry in collection_register(session, project=project, actor=actor, as_of=as_of):
        for view in entry.summary.rows:
            if overdue_only and view.overdue_days <= 0:
                continue
            rows.append(
                AgingRow(
                    sale_id=entry.sale_id,
                    sale_number=entry.sale_number,
                    unit_number=entry.unit_number,
                    client_display_name=entry.client_display_name,
                    currency_id=entry.currency_id,
                    installment=view,
                )
            )
    rows.sort(key=lambda row: (-row.installment.overdue_days, row.sale_number))
    return rows


@dataclass(frozen=True, slots=True)
class CurrencyTotals:
    """Every money figure for one denomination. Nothing here crosses currencies."""

    currency_id: uuid.UUID
    accounts: int
    outstanding_total: Decimal
    due_total: Decimal
    overdue_total: Decimal
    unapplied_cash: Decimal
    confirmed_receipts_total: Decimal
    buckets: dict[str, Decimal]


@dataclass(frozen=True, slots=True)
class ProjectSummary:
    """The collections strip at the top of the workspace. Every figure derived.

    **There is no project-wide money total, and that is the design.** A project
    can sell in more than one currency, and 100 dinars plus 50 dollars is not
    150 of anything. A single ``outstanding_total`` could only be produced by
    adding unlike numbers and then labelling the result with whichever currency
    happened to come first, which is a figure that looks authoritative, appears
    on an executive screen, and is wrong by however much the exchange rate is.

    Converting to a reporting currency instead would need an FX model — rates,
    as-at dates, which rate for a receivable and which for cash received — and
    PR-MVP-07 is deliberately not the place that gets invented. So the money is
    grouped by ``currency_id`` and the screen shows each denomination on its own
    line.

    The counts are project-wide, because a count of accounts is not money: four
    overdue accounts are four overdue accounts whatever they are billed in.
    """

    as_of: date
    accounts: int
    accounts_overdue: int
    accounts_disputed: int
    accounts_cleared: int
    currencies: list[CurrencyTotals]


def project_summary(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    as_of: date | None = None,
) -> ProjectSummary:
    """Project-level collections figures, totalled from the same register rows.

    ``confirmed_receipts_total`` is lifetime and says so in its name, because an
    unlabelled "collected" beside a current outstanding invites exactly the
    wrong subtraction.

    Grouped by currency — see :class:`ProjectSummary`. Currencies come back in a
    stable order so the strip does not reshuffle itself between reads.
    """
    as_of = resolve_as_of(as_of)
    rows = collection_register(session, project=project, actor=actor, as_of=as_of)

    grouped: dict[uuid.UUID, list[RegisterRow]] = {}
    for entry in rows:
        grouped.setdefault(entry.currency_id, []).append(entry)

    currencies: list[CurrencyTotals] = []
    for currency_id in sorted(grouped, key=str):
        entries = grouped[currency_id]
        buckets: dict[str, Decimal] = dict.fromkeys(ledger.AGING_BUCKETS, ZERO)
        for entry in entries:
            for view in entry.summary.rows:
                buckets[view.bucket] = buckets[view.bucket] + view.outstanding
        currencies.append(
            CurrencyTotals(
                currency_id=currency_id,
                accounts=len(entries),
                outstanding_total=sum((r.summary.outstanding_total for r in entries), ZERO),
                due_total=sum((r.summary.due_total for r in entries), ZERO),
                overdue_total=sum((r.summary.overdue_total for r in entries), ZERO),
                unapplied_cash=sum((r.summary.unapplied_cash for r in entries), ZERO),
                confirmed_receipts_total=sum(
                    (r.summary.confirmed_receipts_total for r in entries), ZERO
                ),
                buckets=buckets,
            )
        )

    return ProjectSummary(
        as_of=as_of,
        accounts=len(rows),
        accounts_overdue=sum(1 for r in rows if r.summary.overdue_total > ZERO),
        accounts_disputed=sum(1 for r in rows if r.summary.open_disputes > 0),
        accounts_cleared=sum(
            1 for r in rows if r.summary.derived_collection_status == ledger.UNIT_CLEARED
        ),
        currencies=currencies,
    )
