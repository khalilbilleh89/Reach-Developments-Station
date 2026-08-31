"""Deterministic schedule arithmetic: allocation, calendars, reconciliation.

Pure functions over values. Nothing here opens a session, reads a request,
checks a permission or writes an audit row — which is what makes every rule in
it testable on its own, and what keeps the one place that divides money by a
percentage from also being the place that decides who may do so.

Two disciplines run through the file.

**Decimal, never float.** Every amount arrives as a ``Decimal`` and leaves as
one, quantised to the platform's monetary scale. ``0.1 + 0.2`` is a wrong
answer about money, and a schedule that reconciles to 199,999.99 is a schedule
that cannot be activated.

**Residual is allocated, never absorbed.** Splitting 200,000 three ways leaves
a remainder that the individual lines cannot carry. It is given to a named
instalment rather than dropped, so the stored rows add up to the contract
exactly and nobody has to be told the difference is "just rounding".
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.db.base import MONEY_EXPONENT

#: The scale a stored fraction carries, matching the RATE column. A fraction is
#: quantised here so the total of the stored values is the total that gets
#: compared against 1, rather than a more precise number that only reconciles
#: before it is written down.
FRACTION_EXPONENT = Decimal("0.000001")

#: Exactly the whole. The comparison every percentage schedule must satisfy.
ONE = Decimal("1.000000")

ZERO_MONEY = Decimal("0.00")


def money(value: Decimal) -> Decimal:
    """Quantise an amount to the platform's monetary scale, half up."""
    return value.quantize(MONEY_EXPONENT, rounding=ROUND_HALF_UP)


def fraction(value: Decimal) -> Decimal:
    """Quantise a fraction to the stored rate scale, half up."""
    return value.quantize(FRACTION_EXPONENT, rounding=ROUND_HALF_UP)


def allocate(total: Decimal, fractions: list[Decimal]) -> list[Decimal]:
    """Split ``total`` across ``fractions``, giving the residual to the last line.

    Each line is rounded to the monetary scale on its own, which is what a
    person reading the schedule would do, and the rounding differences are then
    collected and handed to the final line. The alternative — leaving a penny
    unallocated — produces a schedule that can never be activated and an
    operator who cannot see why.

    The target is what the fractions ACTUALLY cover, not ``total``. This
    distinction is the whole point: a schedule whose percentages come to 0.95
    must allocate 95% of the contract and report a shortfall, not quietly round
    itself up to the full amount and reconcile. The residual absorbed here is
    only ever sub-unit rounding.

    An empty list allocates nothing. A total of zero allocates zeroes, which is
    the correct answer for a sale with no tax rather than a special case.
    """
    if not fractions:
        return []
    lines = [money(total * value) for value in fractions]
    covered = money(total * sum(fractions))
    residual = covered - sum(lines)
    if residual != ZERO_MONEY:
        lines[-1] = money(lines[-1] + residual)
    return lines


def derive_fractions(total: Decimal, amounts: list[Decimal]) -> list[Decimal]:
    """Express each amount as a fraction of ``total``, residual on the last line.

    The mirror of :func:`allocate`, used when the preparer typed amounts. A
    complete schedule's stored fractions must total exactly one, so the same
    residual discipline applies: rounding each division independently would
    leave a schedule whose percentages sum to 0.999999 while its money is
    exact, and both totals are checked at activation.

    A zero contract value yields zero fractions — there is nothing to be a
    proportion of, and inventing one would divide by zero.
    """
    if not amounts:
        return []
    if total == 0:
        return [Decimal("0.000000") for _ in amounts]
    values = [fraction(amount / total) for amount in amounts]
    # As in :func:`allocate`, the target is what the amounts actually come to.
    # A schedule that is 10,000 short must produce fractions that are short
    # too, rather than being rounded up to a whole that was never scheduled.
    covered = fraction(sum(amounts) / total)
    residual = covered - sum(values)
    if residual != Decimal("0"):
        values[-1] = fraction(values[-1] + residual)
    return values


def add_months(start: date, months: int) -> date:
    """Add calendar months, clamping to the last valid day of the target month.

    31 January plus one month is 28 February — or 29 in a leap year — because
    31 February does not exist and the instalment still falls due. Written with
    the standard library on purpose: a date package is a dependency, and this is
    nine lines of arithmetic whose edge cases are all testable.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass(frozen=True)
class SeriesRow:
    """One proposed row of a recurring series. A date and a label, no money."""

    recurrence_index: int
    label: str
    due_date: date


def recurring_series(
    *, first_due_date: date, count: int, months_between: int, label_prefix: str
) -> list[SeriesRow]:
    """Propose the dates of a recurring series.

    Structure only: the caller decides what each row is worth, because the
    version's allocation mode owns the money and this function must not have
    two ways to answer the same question. Each date is computed from the FIRST
    due date rather than from its predecessor, so a February clamp does not
    drag every later month back to the 28th.
    """
    return [
        SeriesRow(
            recurrence_index=index + 1,
            label=f"{label_prefix} {index + 1}",
            due_date=add_months(first_due_date, months_between * index),
        )
        for index in range(count)
    ]


@dataclass(frozen=True)
class Reconciliation:
    """What the stored schedule adds up to, against what it must cover.

    Every field is derived from the instalment rows and the version's frozen
    basis. The browser is given this object and renders it; it never sums a
    column itself, because two implementations of the same total are one
    implementation and one bug waiting to be discovered by an operator.
    """

    installment_count: int

    scheduled_principal_total: Decimal
    contract_value_covered: Decimal
    principal_delta: Decimal

    scheduled_fraction_total: Decimal
    fraction_delta: Decimal

    scheduled_tax_total: Decimal
    tax_total_snapshot: Decimal
    tax_delta: Decimal

    scheduled_fee_total: Decimal
    buyer_fee_total_snapshot: Decimal
    fee_delta: Decimal

    scheduled_buyer_total: Decimal
    total_buyer_payable_snapshot: Decimal
    buyer_total_delta: Decimal

    @property
    def is_reconciled(self) -> bool:
        """Whether this schedule may be submitted, approved or activated.

        Every delta exactly zero, and at least one instalment. There is no
        tolerance: "close enough" on a contract of two hundred thousand is a
        difference somebody eventually has to explain to a buyer.
        """
        return (
            self.installment_count >= 1
            and self.principal_delta == ZERO_MONEY
            and self.fraction_delta == Decimal("0")
            and self.tax_delta == ZERO_MONEY
            and self.fee_delta == ZERO_MONEY
            and self.buyer_total_delta == ZERO_MONEY
        )


@dataclass(frozen=True)
class Line:
    """The money on one instalment, as the reconciliation reads it."""

    principal_amount: Decimal
    principal_fraction: Decimal
    tax_amount: Decimal
    fee_amount: Decimal


def reconcile(
    lines: list[Line],
    *,
    contract_value_covered: Decimal,
    tax_total_snapshot: Decimal,
    buyer_fee_total_snapshot: Decimal,
    total_buyer_payable_snapshot: Decimal,
) -> Reconciliation:
    """Total the schedule and compare it against the sale's frozen basis.

    Deltas are stored as scheduled-minus-required, so a shortfall is negative
    and an excess positive. The screen says which it is in words; the sign is
    here so it does not have to guess.
    """
    principal = money(sum((line.principal_amount for line in lines), ZERO_MONEY))
    fractions = fraction(sum((line.principal_fraction for line in lines), Decimal("0")))
    tax = money(sum((line.tax_amount for line in lines), ZERO_MONEY))
    fee = money(sum((line.fee_amount for line in lines), ZERO_MONEY))
    buyer_total = money(principal + tax + fee)
    return Reconciliation(
        installment_count=len(lines),
        scheduled_principal_total=principal,
        contract_value_covered=money(contract_value_covered),
        principal_delta=money(principal - contract_value_covered),
        scheduled_fraction_total=fractions,
        fraction_delta=fraction(fractions - ONE),
        scheduled_tax_total=tax,
        tax_total_snapshot=money(tax_total_snapshot),
        tax_delta=money(tax - tax_total_snapshot),
        scheduled_fee_total=fee,
        buyer_fee_total_snapshot=money(buyer_fee_total_snapshot),
        fee_delta=money(fee - buyer_fee_total_snapshot),
        scheduled_buyer_total=buyer_total,
        total_buyer_payable_snapshot=money(total_buyer_payable_snapshot),
        buyer_total_delta=money(buyer_total - total_buyer_payable_snapshot),
    )


def shortfall_reasons(reconciliation: Reconciliation) -> list[str]:
    """Say, in words, exactly what stops this schedule being put forward.

    An operator told "invalid plan" has to find the discrepancy themselves
    across forty rows. An operator told the principal is short by 5,000.00 goes
    to the line that is wrong.
    """
    reasons: list[str] = []
    if reconciliation.installment_count < 1:
        reasons.append("The schedule has no instalments.")
    if reconciliation.principal_delta != ZERO_MONEY:
        reasons.append(_delta_phrase("Principal", reconciliation.principal_delta))
    if reconciliation.fraction_delta != Decimal("0"):
        scheduled = reconciliation.scheduled_fraction_total
        reasons.append(f"The instalment percentages total {scheduled}, not 1.000000.")
    if reconciliation.tax_delta != ZERO_MONEY:
        reasons.append(_delta_phrase("Tax", reconciliation.tax_delta))
    if reconciliation.fee_delta != ZERO_MONEY:
        reasons.append(_delta_phrase("Buyer fees", reconciliation.fee_delta))
    if reconciliation.buyer_total_delta != ZERO_MONEY:
        reasons.append(_delta_phrase("The buyer total", reconciliation.buyer_total_delta))
    return reasons


def _delta_phrase(subject: str, delta: Decimal) -> str:
    if delta < ZERO_MONEY:
        return f"{subject} is short by {-delta}."
    return f"{subject} exceeds the contract by {delta}."
