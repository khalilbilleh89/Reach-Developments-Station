"""The cashflow arithmetic, and nothing else.

No session, no actor, no query, no audit write — the same discipline as
``construction/calculator.py``, ``pricing/calculator.py`` and
``unit_economics/calculator.py``. A funding requirement somebody took to a bank
must be reproducible from its recorded inputs, and a calculation that can also
read a row is one whose answer depends on when it was asked.

Five families of figure live here.

**The monthly bridge.** Opening plus inflows minus outflows is closing, and next
month's opening is this month's closing. Nothing is stored: a running balance
column is a number that can disagree with the transactions beneath it, and the
first time it does nobody knows which one is wrong.

**Restricted and usable cash.** Received and usable are different numbers.
Restricted cash moves on its own bridge — opening plus newly restricted minus
released — and unrestricted cash is what is left of total cash after it. A
release transfers availability; it never creates cash. Restricted cash may never
go negative, and it may never fund an unrestricted obligation.

**Funding.** The gap is measured against *unrestricted* cash, because escrowed
customer money cannot pay a contractor. The signed closing position and the
positive shortfall are both returned: a report that shows only the shortfall
cannot distinguish comfortable from exactly zero, and one that shows only the
signed balance makes every reader do the ``max(0, -x)`` in their head.

**Return.** NPV at the forecast's own per-period rate, and equity IRR under the
investor sign convention. Decimal throughout, no float anywhere, and no library:
the two formulas are eight lines, and a dependency that computes them in binary
floating point would give a different answer than the ledger it is quoting.

**Variance.** Actual against a prior forecast, as an amount always and as a rate
only where the denominator permits one.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise

from app.db.base import MONEY_EXPONENT, RATE

ZERO = Decimal("0.00")

#: The scale rates are stored at, for quantising a derived rate back to it.
RATE_EXPONENT = Decimal(1).scaleb(-RATE.scale)


def money(amount: Decimal) -> Decimal:
    """Quantise to the scale the money column stores. Half-up, once per figure."""
    return amount.quantize(MONEY_EXPONENT, rounding=ROUND_HALF_UP)


def rate(value: Decimal) -> Decimal:
    """Quantise to the scale the rate column stores."""
    return value.quantize(RATE_EXPONENT, rounding=ROUND_HALF_UP)


def total(amounts: Iterable[Decimal]) -> Decimal:
    """Sum a column of money at the stored scale."""
    return money(sum(amounts, ZERO))


# --------------------------------------------------------------------------- #
# The monthly bridge
# --------------------------------------------------------------------------- #


def net_cashflow(*, total_inflows: Decimal, total_outflows: Decimal) -> Decimal:
    """Signed. Negative is a month that consumed cash."""
    return money(total_inflows - total_outflows)


def closing_cash(*, opening_cash: Decimal, net_movement: Decimal) -> Decimal:
    """Signed, and allowed to be negative.

    A closing position below zero is the answer to "when do we run short?" and
    clamping it at zero would delete the question. The overdraft is reported,
    not hidden.
    """
    return money(opening_cash + net_movement)


def closing_restricted_cash(
    *, opening_restricted: Decimal, newly_restricted: Decimal, released: Decimal
) -> Decimal:
    """Restricted cash's own bridge, which may never close below zero.

    Releasing more than was ever restricted is not a small overdraft on an
    escrow account; it is a claim that money nobody set aside has been freed for
    use. The service holds the invariant under lock at write time and this
    refuses to state the impossible figure if it ever gets through.
    """
    closing = money(opening_restricted + newly_restricted - released)
    if closing < ZERO:
        raise ValueError(
            f"Restricted cash would close at {closing}. Releases cannot exceed what "
            "was restricted, and a negative escrow balance is not a position that "
            "can be reported."
        )
    return closing


def closing_unrestricted_cash(*, closing_total: Decimal, closing_restricted: Decimal) -> Decimal:
    """What is left of the bank once the restricted portion is set aside.

    Signed: unrestricted cash genuinely can be negative while restricted cash is
    healthy, and that project is short of money however comfortable the total
    looks.
    """
    return money(closing_total - closing_restricted)


def funding_gap(*, closing_unrestricted: Decimal) -> Decimal:
    """The positive shortfall, or zero. Never negative.

    Measured on unrestricted cash by definition. A project holding 4,000,000 of
    escrowed buyer money and 200,000 of its own, facing a 500,000 payment, has a
    300,000 funding gap — and a system that netted the escrow against it would
    report no problem right up until the bank refused the transfer.
    """
    return money(max(ZERO, -closing_unrestricted))


# --------------------------------------------------------------------------- #
# Funding across a horizon
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PeakDeficit:
    """The worst unrestricted position across a horizon, and when it happens.

    Both numbers, deliberately. ``minimum_unrestricted_cash`` is signed and is
    the position; ``peak_funding_deficit`` is the positive amount somebody has
    to raise. They are the same fact stated for two different readers, and a
    report carrying only one of them makes the other reader do arithmetic.
    """

    minimum_unrestricted_cash: Decimal
    peak_funding_deficit: Decimal
    peak_deficit_month: object | None


def peak_deficit(periods: Sequence[tuple[object, Decimal]]) -> PeakDeficit:
    """Scan closing unrestricted positions for the worst one.

    ``periods`` is ``(month, closing_unrestricted)`` in chronological order. The
    first month reaching the minimum wins a tie: the earliest date a shortfall
    of that size appears is the one funding has to be in place for.
    """
    if not periods:
        return PeakDeficit(
            minimum_unrestricted_cash=ZERO, peak_funding_deficit=ZERO, peak_deficit_month=None
        )
    worst_month, worst_value = periods[0]
    for month, value in periods[1:]:
        if value < worst_value:
            worst_month, worst_value = month, value
    gap = funding_gap(closing_unrestricted=worst_value)
    return PeakDeficit(
        minimum_unrestricted_cash=money(worst_value),
        peak_funding_deficit=gap,
        # A horizon that never goes short has no deficit month to name, and
        # naming the least comfortable one anyway would read as a warning.
        peak_deficit_month=worst_month if gap > ZERO else None,
    )


def forecast_collection_coverage(
    *, usable_customer_inflows: Decimal, project_outflows: Decimal
) -> Decimal | None:
    """How far expected usable collections go towards expected spend.

    ``None`` where nothing is expected to be spent. Dividing by zero to reach
    "infinite coverage" states a certainty the data does not support, and a
    screen showing ∞ has told the reader nothing except that the denominator was
    empty.
    """
    if project_outflows == ZERO:
        return None
    return rate(usable_customer_inflows / project_outflows)


# --------------------------------------------------------------------------- #
# Return
# --------------------------------------------------------------------------- #


def discount_factor(*, rate_per_period: Decimal, period_index: int) -> Decimal:
    """``(1 + r) ** t``, exactly, for an integer period index.

    Integer exponentiation of a Decimal is exact, so the factor carries no
    rounding of its own and every approximation in the NPV below is confined to
    the single division that uses it.
    """
    if period_index < 0:
        raise ValueError("A discount period index cannot be negative.")
    return (Decimal(1) + rate_per_period) ** period_index


def net_present_value(*, net_flows: Sequence[Decimal], rate_per_period: Decimal) -> Decimal:
    """Discount a series of periodic net flows at the forecast's own rate.

    ``t = 0`` is the first forecast period, which is therefore undiscounted. The
    rate is per *period* — the forecast stores it that way and no annual figure
    is converted here, because a service that silently turned 12% a year into
    something monthly would be making a compounding assumption nobody wrote
    down.

    Each period's discounted flow is quantised to the money scale before the
    sum, so the total equals the column of figures a reader can print beside it.
    """
    if rate_per_period <= Decimal(-1):
        raise ValueError(
            "A discount rate of -100% or lower has no discount factor: it divides by zero."
        )
    discounted = [
        money(flow / discount_factor(rate_per_period=rate_per_period, period_index=index))
        for index, flow in enumerate(net_flows)
    ]
    return total(discounted)


#: Why an IRR could not be produced. A closed set, because "unavailable" with no
#: reason is indistinguishable from a bug and invites somebody to print 0%.
IRR_NO_INVESTMENT = "no_negative_equity_cashflow"
IRR_NO_RETURN = "no_positive_equity_cashflow"
IRR_AMBIGUOUS = "multiple_sign_changes"
IRR_NOT_BRACKETED = "no_root_in_searched_range"

#: The range searched for a root: from just above -100% to 1,000% per period.
#: A periodic return outside that is not a number anybody should act on.
IRR_LOWER_BOUND = Decimal("-0.999999")
IRR_UPPER_BOUND = Decimal("10")

#: How finely the bisection narrows before it reports the rate. One order below
#: the stored rate scale, so the quantised answer is stable.
IRR_TOLERANCE = Decimal("0.0000001")

#: A hard cap on halvings. The interval shrinks by half each pass, so this is
#: far more than the tolerance needs and exists only so no input can loop.
IRR_MAX_ITERATIONS = 200


@dataclass(frozen=True)
class InternalRateOfReturn:
    """A periodic IRR, or an explicit reason there is none.

    Never both empty: either ``rate_per_period`` is a number or
    ``unavailable_reason`` says why it is not. Returning 0%, 999% or NaN for an
    unanswerable series is worse than returning nothing, because each of those
    is a number somebody will put in a board pack.
    """

    rate_per_period: Decimal | None
    unavailable_reason: str | None


def _sign_changes(flows: Sequence[Decimal]) -> int:
    """How many times the series crosses zero, ignoring zero periods."""
    signs = [1 if flow > ZERO else -1 for flow in flows if flow != ZERO]
    return sum(1 for first, second in pairwise(signs) if first != second)


def internal_rate_of_return(*, equity_flows: Sequence[Decimal]) -> InternalRateOfReturn:
    """Periodic IRR of an equity series, by bounded bisection on Decimal.

    The series is the **investor's**, not the project's: an equity contribution
    is money the investor paid out and enters negative; a distribution is money
    they received and enters positive. Feeding project-direction cash in here
    produces the right magnitude with the sign reversed, which is the single
    easiest way to report a disastrous investment as a good one.

    Bisection rather than Newton's method because it cannot diverge and needs no
    derivative, and because a conventional series — one sign change — makes NPV
    strictly decreasing in the rate, so a bracketed root is the root.

    Refused rather than guessed in four cases: nothing invested, nothing
    returned, more than one sign change (where several rates can satisfy the
    equation and none of them is *the* return), and a root outside the searched
    range.
    """
    flows = list(equity_flows)
    if not any(flow < ZERO for flow in flows):
        return InternalRateOfReturn(rate_per_period=None, unavailable_reason=IRR_NO_INVESTMENT)
    if not any(flow > ZERO for flow in flows):
        return InternalRateOfReturn(rate_per_period=None, unavailable_reason=IRR_NO_RETURN)
    if _sign_changes(flows) > 1:
        return InternalRateOfReturn(rate_per_period=None, unavailable_reason=IRR_AMBIGUOUS)

    def value_at(candidate: Decimal) -> Decimal:
        return sum(
            (
                flow / discount_factor(rate_per_period=candidate, period_index=index)
                for index, flow in enumerate(flows)
            ),
            Decimal(0),
        )

    low, high = IRR_LOWER_BOUND, IRR_UPPER_BOUND
    low_value, high_value = value_at(low), value_at(high)
    if low_value == Decimal(0):
        return InternalRateOfReturn(rate_per_period=rate(low), unavailable_reason=None)
    if high_value == Decimal(0):
        return InternalRateOfReturn(rate_per_period=rate(high), unavailable_reason=None)
    if (low_value > Decimal(0)) == (high_value > Decimal(0)):
        return InternalRateOfReturn(rate_per_period=None, unavailable_reason=IRR_NOT_BRACKETED)

    for _ in range(IRR_MAX_ITERATIONS):
        if high - low <= IRR_TOLERANCE:
            break
        middle = (low + high) / Decimal(2)
        middle_value = value_at(middle)
        if middle_value == Decimal(0):
            low = high = middle
            break
        if (middle_value > Decimal(0)) == (low_value > Decimal(0)):
            low, low_value = middle, middle_value
        else:
            high = middle
    return InternalRateOfReturn(
        rate_per_period=rate((low + high) / Decimal(2)), unavailable_reason=None
    )


# --------------------------------------------------------------------------- #
# Variance
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Variance:
    """Actual against a prior forecast: always an amount, sometimes a rate."""

    forecast_amount: Decimal
    actual_amount: Decimal
    variance_amount: Decimal
    variance_rate: Decimal | None


def forecast_variance(*, forecast_amount: Decimal, actual_amount: Decimal) -> Variance:
    """Signed against the forecast: positive means more happened than expected.

    The rate is ``None`` when nothing was forecast. A percentage against zero is
    undefined, and the alternatives — infinity, or quietly reporting 100% — both
    describe a forecast miss that cannot be sized. The amount is always there,
    and "we forecast nothing and spent 40,000" is a complete sentence without a
    percentage.
    """
    difference = money(actual_amount - forecast_amount)
    if forecast_amount == ZERO:
        return Variance(
            forecast_amount=money(forecast_amount),
            actual_amount=money(actual_amount),
            variance_amount=difference,
            variance_rate=None,
        )
    return Variance(
        forecast_amount=money(forecast_amount),
        actual_amount=money(actual_amount),
        variance_amount=difference,
        variance_rate=rate(difference / forecast_amount),
    )


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Check:
    """One reconciliation answer: what was compared, and whether it agreed."""

    name: str
    passed: bool
    expected: Decimal | None
    actual: Decimal | None
    detail: str


def equality_check(*, name: str, expected: Decimal, actual: Decimal, detail: str = "") -> Check:
    """Exact equality at the money scale. No tolerance, anywhere.

    A tolerance is a rounding error somebody decided to stop noticing, and the
    amount it hides grows with the project.
    """
    return Check(
        name=name,
        passed=money(expected) == money(actual),
        expected=money(expected),
        actual=money(actual),
        detail=detail,
    )


def limit_check(*, name: str, ceiling: Decimal, actual: Decimal, detail: str = "") -> Check:
    """``actual <= ceiling`` at the money scale."""
    return Check(
        name=name,
        passed=money(actual) <= money(ceiling),
        expected=money(ceiling),
        actual=money(actual),
        detail=detail,
    )


def count_check(*, name: str, actual: int, detail: str = "") -> Check:
    """A structural count that must be zero."""
    return Check(
        name=name,
        passed=actual == 0,
        expected=Decimal(0),
        actual=Decimal(actual),
        detail=detail,
    )
