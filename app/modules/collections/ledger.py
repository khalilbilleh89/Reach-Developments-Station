"""The arithmetic of a receivable, with no database in it.

Separated from :mod:`app.modules.collections.service` for the same reason
PR-MVP-06 separated ``schedule.py``: these are the rules a finance director
would argue about, and they should be readable and testable without building a
project, a unit, a contract and a plan first.

Everything here is a pure function over ``Decimal`` and ``date``. No session,
no ORM, no clock — ``as_of`` is always passed in, because "what did this look
like on 31 August?" is a question month-end reporting and an auditor both ask,
and a function that reaches for today cannot answer it.

Three rules are worth stating before the code.

**A forecast never makes money due.** :func:`effective_due_date` returns the
contractual date for a dated instalment and the *actual* date for a contingent
one that has genuinely triggered. It has no branch that reads
``forecast_due_date``, which is why a construction milestone whose expected date
passed three months ago reads as awaiting its trigger rather than ninety days
overdue.

**Grace is part of the date, not a discount.** An amount is overdue when
``as_of`` is strictly past ``due date + grace days`` — not on the boundary. The
off-by-one here is a financial reporting error, so the boundary is tested
explicitly rather than assumed.

**A label never destroys a fact.** :func:`installment_view` returns a primary
status *and* the flags beside it, so an instalment can be disputed, forty-seven
days overdue and eight thousand short all at once. Collapsing that into one
badge is how a receivables report stops reconciling to its own rows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

ZERO = Decimal("0.00")

# --------------------------------------------------------------------------- #
# Aging buckets
# --------------------------------------------------------------------------- #

#: The fixed MVP aging bands. Deliberately not configurable: a configurable
#: bucket expression is a rules engine, and the first thing a rules engine does
#: is make two reports disagree about what "60 days" means.
AGING_BUCKETS = ("awaiting_trigger", "current", "1_30", "31_60", "61_90", "91_plus")
BUCKET_AWAITING = "awaiting_trigger"
BUCKET_CURRENT = "current"
BUCKET_1_30 = "1_30"
BUCKET_31_60 = "31_60"
BUCKET_61_90 = "61_90"
BUCKET_91_PLUS = "91_plus"

# --------------------------------------------------------------------------- #
# Derived statuses
# --------------------------------------------------------------------------- #

#: Where one instalment stands, once cash is taken into account. Derived at
#: read time and stored nowhere: PR-MVP-06 already persists ``trigger_status``,
#: and a second status column would be a copy of a calculation that goes stale
#: the moment a receipt is confirmed.
INSTALLMENT_STATUSES = (
    "awaiting_trigger",
    "scheduled",
    "due",
    "partially_paid",
    "paid",
    "overdue",
    "disputed",
    "cancelled",
)
INSTALLMENT_AWAITING = "awaiting_trigger"
INSTALLMENT_SCHEDULED = "scheduled"
INSTALLMENT_DUE = "due"
INSTALLMENT_PARTIAL = "partially_paid"
INSTALLMENT_PAID = "paid"
INSTALLMENT_OVERDUE = "overdue"
INSTALLMENT_DISPUTED = "disputed"
INSTALLMENT_CANCELLED = "cancelled"

#: The unit's collection dimension, owned by inventory and decided here.
#: Same seven values PR-MVP-03 declared and left for this PR to drive.
UNIT_NOT_STARTED = "not_started"
UNIT_CURRENT = "current"
UNIT_PARTIALLY_PAID = "partially_paid"
UNIT_OVERDUE = "overdue"
UNIT_DISPUTED = "disputed"
UNIT_CLEARED = "cleared"
UNIT_CANCELLED = "cancelled"


def scheduled_amount(principal: Decimal, tax: Decimal, fee: Decimal) -> Decimal:
    """What one instalment asks the buyer for, in total.

    The single definition. The register, the account screen, Unit 360, the aging
    report and the restructure preview all call this rather than adding three
    columns each in their own way — three call sites adding the same three
    numbers is three chances for one of them to forget the buyer fee.
    """
    return principal + tax + fee


def effective_due_date(
    *,
    trigger_type: str,
    date_based: bool,
    contractual_due_date: date | None,
    actual_due_date: date | None,
    triggered: bool,
) -> date | None:
    """The date this instalment actually falls due, or ``None`` if it cannot yet.

    ``trigger_type`` is accepted for the caller's readability at the call site;
    ``date_based`` is the decision, taken from PR-MVP-06's own classification so
    this module never has to keep a second copy of which triggers are which.

    Deliberately three cases and no fourth:

    * a dated instalment is due on its contractual date;
    * a contingent instalment that has triggered is due on the date the trigger
      actually happened;
    * a contingent instalment still waiting has **no** due date, whatever its
      forecast says.
    """
    del trigger_type  # named for the reader; ``date_based`` carries the rule
    if date_based:
        return contractual_due_date or actual_due_date
    if triggered and actual_due_date is not None:
        return actual_due_date
    return None


def grace_end(due: date | None, grace_days: int) -> date | None:
    """The last day an amount can arrive without being late."""
    if due is None:
        return None
    from datetime import timedelta

    return due + timedelta(days=grace_days)


def days_overdue(
    *,
    due: date | None,
    grace_days: int,
    as_of: date,
    outstanding: Decimal,
) -> int:
    """How many days past the grace boundary this amount has been outstanding.

    Zero unless there is something still owed *and* ``as_of`` is strictly past
    the boundary. An instalment settled in full is never overdue however long
    ago it fell due, and one sitting on its grace boundary is not yet late.
    """
    if outstanding <= ZERO:
        return 0
    end = grace_end(due, grace_days)
    if end is None or as_of <= end:
        return 0
    return (as_of - end).days


def aging_bucket(*, due: date | None, overdue_days: int) -> str:
    """Which band this amount falls into on the report."""
    if due is None:
        return BUCKET_AWAITING
    if overdue_days <= 0:
        return BUCKET_CURRENT
    if overdue_days <= 30:
        return BUCKET_1_30
    if overdue_days <= 60:
        return BUCKET_31_60
    if overdue_days <= 90:
        return BUCKET_61_90
    return BUCKET_91_PLUS


@dataclass(frozen=True, slots=True)
class InstallmentView:
    """One instalment as Collections reads it, cash included.

    Both a ``status`` and the flags behind it, because the flags are facts and
    the status is a summary. Anything that needs to reconcile uses the numbers;
    anything that needs a badge uses the status; neither has to guess what the
    other meant.
    """

    installment_id: uuid.UUID
    sequence: int
    label: str
    trigger_type: str
    trigger_status: str
    due_date: date | None
    grace_days: int
    scheduled: Decimal
    paid: Decimal
    outstanding: Decimal
    overdue_days: int
    bucket: str
    status: str
    is_disputed: bool
    has_active_waiver: bool
    waived_until: date | None
    owner_user_id: uuid.UUID | None

    @property
    def overdue_amount(self) -> Decimal:
        """The part of this instalment that is actually late."""
        return self.outstanding if self.overdue_days > 0 else ZERO

    @property
    def due_amount(self) -> Decimal:
        """What is payable now — reached its date, still outstanding."""
        return self.outstanding if self.due_date is not None else ZERO


def installment_view(
    *,
    installment_id: uuid.UUID,
    sequence: int,
    label: str,
    trigger_type: str,
    trigger_status: str,
    date_based: bool,
    contractual_due_date: date | None,
    actual_due_date: date | None,
    triggered: bool,
    grace_days: int,
    principal: Decimal,
    tax: Decimal,
    fee: Decimal,
    paid: Decimal,
    as_of: date,
    disputed: bool,
    waived_until: date | None,
    owner_user_id: uuid.UUID | None,
    sale_cancelled: bool,
) -> InstallmentView:
    """Assemble everything derivable about one instalment on ``as_of``.

    The priority order for ``status`` reads downward and stops at the first
    match. ``disputed`` sits above ``overdue`` because a contested amount is the
    more urgent thing for a collections officer to see — and ``overdue_days``,
    ``outstanding`` and ``bucket`` are still on the row underneath it, so
    nothing is lost by the ordering.
    """
    scheduled = scheduled_amount(principal, tax, fee)
    outstanding = scheduled - paid
    due = effective_due_date(
        trigger_type=trigger_type,
        date_based=date_based,
        contractual_due_date=contractual_due_date,
        actual_due_date=actual_due_date,
        triggered=triggered,
    )
    overdue_days = days_overdue(
        due=due, grace_days=grace_days, as_of=as_of, outstanding=outstanding
    )
    bucket = aging_bucket(due=due, overdue_days=overdue_days)
    waiver_active = waived_until is not None and waived_until >= as_of

    if sale_cancelled:
        status = INSTALLMENT_CANCELLED
    elif due is None:
        status = INSTALLMENT_AWAITING
    elif outstanding <= ZERO:
        status = INSTALLMENT_PAID
    elif disputed:
        status = INSTALLMENT_DISPUTED
    elif overdue_days > 0:
        status = INSTALLMENT_OVERDUE
    elif paid > ZERO:
        status = INSTALLMENT_PARTIAL
    elif due <= as_of:
        status = INSTALLMENT_DUE
    else:
        status = INSTALLMENT_SCHEDULED

    return InstallmentView(
        installment_id=installment_id,
        sequence=sequence,
        label=label,
        trigger_type=trigger_type,
        trigger_status=trigger_status,
        due_date=due,
        grace_days=grace_days,
        scheduled=scheduled,
        paid=paid,
        outstanding=outstanding,
        overdue_days=overdue_days,
        bucket=bucket,
        status=status,
        is_disputed=disputed,
        has_active_waiver=waiver_active,
        waived_until=waived_until if waiver_active else None,
        owner_user_id=owner_user_id,
    )


def unit_collection_status(
    *,
    sale_cancelled: bool,
    has_active_schedule: bool,
    rows: list[InstallmentView],
    unapplied_cash: Decimal,
    allocated_cash: Decimal,
    open_disputes: int,
) -> str:
    """Which of inventory's seven collection values this account is in.

    Read top to bottom; the first true one wins.

    ``cleared`` is the strict one, and deliberately. A buyer who owes nothing
    but has an unresolved five-thousand overpayment sitting unapplied is not a
    file anybody should be closing, and letting that read as cleared is how the
    overpayment is discovered a year later by the buyer rather than by us.
    """
    if sale_cancelled:
        return UNIT_CANCELLED
    if not has_active_schedule:
        return UNIT_NOT_STARTED
    if open_disputes > 0:
        return UNIT_DISPUTED
    if any(row.overdue_days > 0 for row in rows):
        return UNIT_OVERDUE

    outstanding = sum((row.outstanding for row in rows), ZERO)
    if outstanding <= ZERO and unapplied_cash <= ZERO:
        return UNIT_CLEARED
    if allocated_cash > ZERO:
        return UNIT_PARTIALLY_PAID
    if unapplied_cash > ZERO:
        return UNIT_PARTIALLY_PAID
    return UNIT_CURRENT


# --------------------------------------------------------------------------- #
# Restructure carry-forward
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CarryLine:
    """One receipt's cash landing on one instalment of the replacement schedule."""

    receipt_id: uuid.UUID
    installment_id: uuid.UUID
    amount: Decimal


@dataclass(frozen=True, slots=True)
class CarryTarget:
    """One instalment of the replacement schedule, and what it can absorb."""

    installment_id: uuid.UUID
    capacity: Decimal


@dataclass(frozen=True, slots=True)
class CarrySource:
    """One receipt's currently active allocated total against the old schedule."""

    receipt_id: uuid.UUID
    amount: Decimal


class CarryForwardError(Exception):
    """The replacement schedule cannot hold the cash already received.

    Raised rather than returned so no caller can accidentally treat a partial
    plan as a complete one. The service turns it into a refusal and the
    restructure does not apply — leaving the old schedule governing, its
    allocations active, and not one unit of cash moved.
    """


def plan_carry_forward(sources: list[CarrySource], targets: list[CarryTarget]) -> list[CarryLine]:
    """Place each receipt's already-allocated cash onto the new schedule.

    Deterministic and boring on purpose. Receipts are consumed in the order
    given — the caller supplies them oldest first — and each is poured into the
    replacement instalments in the order given, which the caller sorts by due
    date and then by sequence. The same restructure planned twice produces the
    same rows, which is what makes the preview an honest promise about what
    applying will do.

    Nothing is invented and nothing is absorbed: every source amount is placed
    in full or :class:`CarryForwardError` is raised. A receipt's *unapplied*
    balance is never passed in as a source, so a restructure can never quietly
    become an auto-allocation of cash nobody chose to apply.
    """
    remaining = {target.installment_id: target.capacity for target in targets}
    order = [target.installment_id for target in targets]
    lines: list[CarryLine] = []

    for source in sources:
        left = source.amount
        if left <= ZERO:
            continue
        for installment_id in order:
            if left <= ZERO:
                break
            room = remaining[installment_id]
            if room <= ZERO:
                continue
            take = room if room < left else left
            lines.append(
                CarryLine(
                    receipt_id=source.receipt_id,
                    installment_id=installment_id,
                    amount=take,
                )
            )
            remaining[installment_id] = room - take
            left -= take
        if left > ZERO:
            raise CarryForwardError(
                "The replacement schedule cannot hold the cash already collected: "
                f"{left} would have nowhere to go."
            )
    return lines


def total_of(lines: list[CarryLine]) -> Decimal:
    """What a carry-forward plan moves, for the conservation check."""
    return sum((line.amount for line in lines), ZERO)
