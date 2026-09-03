"""The construction control arithmetic, and nothing else.

No session, no actor, no query, no audit write. Inputs in, figures out — the
same discipline as ``pricing/calculator.py``, ``collections/ledger.py`` and
``unit_economics/calculator.py``, and for the same reason: a certificate
somebody signed must be reproducible from its recorded inputs, and a calculation
that can also read a row is one whose answer depends on when it was asked.

Four families of figure live here.

**Commitment.** What a contract obliges the developer to pay is its original
value plus every approved variation, positive and negative. Nothing about a
contract's *status* enters that sum: a terminated contract still committed the
money, and removing it takes a signed negative variation rather than a state
change.

**A certificate's net due.** One fixed sequence, because the order is what the
industry means by a payment certificate and a system that let each project
reorder it would let two projects disagree about what a valuation is:

```text
  Current work certified, ex tax
+ Tax
+ Retention released back
- Retention held on this work
- Advance recovered on this work
- Other deductions
  ------------------------------------------------------
= Net due
```

Retention and advance recovery move *when* money is paid, never *what* the work
cost. They are absent from every cost figure below and present in every payable
one, which is why the two are reported side by side and never added.

**Estimate and variance at completion.** ``EAC`` is certified work plus what
Finance says is left; ``VAC`` is that against the control budget the forecast
names. The sign convention is fixed once here: **positive VAC is over budget**.
Reversing it on one screen and not another is how two people read the same
project and disagree about whether it is in trouble.

**Reconciliation.** Exact equality checks, at the scale the money column stores,
with no tolerance anywhere. A tolerance is a rounding error somebody decided to
stop noticing.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.db.base import MONEY_EXPONENT

ZERO = Decimal("0.00")


def money(amount: Decimal) -> Decimal:
    """Quantise to the scale the money column stores. Half-up, once per figure."""
    return amount.quantize(MONEY_EXPONENT, rounding=ROUND_HALF_UP)


def total(amounts: Iterable[Decimal]) -> Decimal:
    """Sum a column of money at the stored scale.

    Quantised once at the end rather than per addend: every input is already at
    the column's scale, so the sum is exact and this only fixes the type.
    """
    return money(sum(amounts, ZERO))


# --------------------------------------------------------------------------- #
# Commitment
# --------------------------------------------------------------------------- #


def revised_commitment(*, original_amount: Decimal, approved_variation_delta: Decimal) -> Decimal:
    """What a contract now commits: its original value plus approved changes.

    Signed, so an omission reduces it. Never stored — a column holding this
    would have to be rewritten by every variation approval, and the first one
    that failed halfway would leave a contract worth two different amounts.
    """
    return money(original_amount + approved_variation_delta)


def headroom(*, approved_budget: Decimal, contingency: Decimal, committed: Decimal) -> Decimal:
    """What a cost code can still commit before it exceeds its authorisation.

    Contingency is inside the control budget rather than beside it: an approved
    reserve is money the business has already authorised, and requiring a budget
    revision to touch it would make the reserve decorative. Approving a
    variation does not move money from contingency into budget — the two stay
    separately visible, and only the total constrains commitment.
    """
    return money(approved_budget + contingency - committed)


def control_budget(*, approved_budget: Decimal, contingency: Decimal) -> Decimal:
    """The authorisation a cost code is measured against."""
    return money(approved_budget + contingency)


# --------------------------------------------------------------------------- #
# Certificates
# --------------------------------------------------------------------------- #


def retention_held(*, current_work_ex_tax: Decimal, retention_rate_fraction: Decimal) -> Decimal:
    """Retention withheld from this certificate's work.

    Decimal throughout and quantised once. The rate is an exact fraction of one,
    so ``200000.00 * 0.100000`` is exactly ``20000.00`` and not a float that
    happens to print that way.
    """
    return money(current_work_ex_tax * retention_rate_fraction)


@dataclass(frozen=True)
class CertificateAmounts:
    """Every figure a payment certificate states, derived from its inputs."""

    current_work_ex_tax: Decimal
    retention_held: Decimal
    retention_release: Decimal
    advance_recovery: Decimal
    other_deductions: Decimal
    tax: Decimal
    net_due: Decimal


def certificate_amounts(
    *,
    current_work_ex_tax: Decimal,
    retention_rate_fraction: Decimal,
    retention_release: Decimal,
    advance_recovery: Decimal,
    other_deductions: Decimal,
    tax: Decimal,
) -> CertificateAmounts:
    """Lay out a certificate, in the one order a payment certificate has.

    The caller has already proven the caps that make this meaningful — that the
    release does not exceed retention actually held, that the recovery does not
    exceed advance cash actually paid — because those are facts about other
    rows and this function may not read a row.
    """
    held = retention_held(
        current_work_ex_tax=current_work_ex_tax,
        retention_rate_fraction=retention_rate_fraction,
    )
    net = money(
        current_work_ex_tax + tax + retention_release - held - advance_recovery - other_deductions
    )
    return CertificateAmounts(
        current_work_ex_tax=money(current_work_ex_tax),
        retention_held=held,
        retention_release=money(retention_release),
        advance_recovery=money(advance_recovery),
        other_deductions=money(other_deductions),
        tax=money(tax),
        net_due=net,
    )


def invoice_payable(*, amount_ex_tax: Decimal, tax: Decimal) -> Decimal:
    """What an invoice claims in total, tax included. A cash-basis figure."""
    return money(amount_ex_tax + tax)


def outstanding(*, payable: Decimal, allocated: Decimal) -> Decimal:
    """What is still owed on an invoice after confirmed cash is applied."""
    return money(payable - allocated)


# --------------------------------------------------------------------------- #
# Forecast
# --------------------------------------------------------------------------- #


def estimate_at_completion(*, certified_to_date: Decimal, forecast_remaining: Decimal) -> Decimal:
    """What the work is now expected to cost in total, ex tax.

    Certified work is history and forecast remaining is judgement. Adding them
    is the only place the two meet, and the forecast half is always an explicit
    input: deriving it as budget minus certified would make the forecast a
    restatement of the budget, and a forecast that cannot disagree with the
    budget cannot warn anybody about it.
    """
    return money(certified_to_date + forecast_remaining)


def variance_at_completion(*, estimate_at_completion: Decimal, control_budget: Decimal) -> Decimal:
    """Expected final cost against authorisation. **Positive is over budget.**

    Stated once, here, and never inverted anywhere else. A screen that shows a
    favourable variance as positive while another shows it as negative is two
    screens that disagree about whether the project is in trouble.
    """
    return money(estimate_at_completion - control_budget)


@dataclass(frozen=True)
class CostCodePosition:
    """One cost code's whole control position, on one basis: ex tax."""

    control_budget: Decimal
    revised_commitment: Decimal
    certified_to_date: Decimal
    forecast_remaining: Decimal
    estimate_at_completion: Decimal
    variance_at_completion: Decimal
    headroom: Decimal
    #: True when the forecast expects to spend less than the developer has
    #: already contractually committed. Reported rather than corrected: either
    #: the forecast is wrong or a contract reduction is expected, and only
    #: Finance can say which. Silently raising the estimate to the commitment
    #: would hide the question.
    forecast_below_commitment: bool
    uncovered_commitment: Decimal


def cost_code_position(
    *,
    approved_budget: Decimal,
    contingency: Decimal,
    revised_commitment_amount: Decimal,
    certified_to_date: Decimal,
    forecast_remaining: Decimal,
) -> CostCodePosition:
    """Assemble one cost code's control position from its five stored inputs."""
    budget = control_budget(approved_budget=approved_budget, contingency=contingency)
    eac = estimate_at_completion(
        certified_to_date=certified_to_date, forecast_remaining=forecast_remaining
    )
    below = eac < revised_commitment_amount
    return CostCodePosition(
        control_budget=budget,
        revised_commitment=money(revised_commitment_amount),
        certified_to_date=money(certified_to_date),
        forecast_remaining=money(forecast_remaining),
        estimate_at_completion=eac,
        variance_at_completion=variance_at_completion(
            estimate_at_completion=eac, control_budget=budget
        ),
        headroom=headroom(
            approved_budget=approved_budget,
            contingency=contingency,
            committed=revised_commitment_amount,
        ),
        forecast_below_commitment=below,
        uncovered_commitment=money(revised_commitment_amount - eac) if below else ZERO,
    )


# --------------------------------------------------------------------------- #
# Retention and advance
# --------------------------------------------------------------------------- #


def retention_outstanding(*, held: Decimal, released: Decimal) -> Decimal:
    """Retention still being held. Derived from certified rows, never stored."""
    return money(held - released)


def advance_outstanding(*, paid: Decimal, recovered: Decimal) -> Decimal:
    """Advance cash not yet recovered through certified valuations.

    ``paid`` is confirmed, unreversed cash against approved advance invoices —
    not the contract's entitlement. An entitlement nobody drew down is not money
    anybody has to recover.
    """
    return money(paid - recovered)


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Check:
    """One reconciliation question, and whether the rows answer it."""

    key: str
    label: str
    ok: bool
    amount: Decimal | None = None
    expected: Decimal | None = None
    detail: str | None = None

    @property
    def variance(self) -> Decimal | None:
        """How far out it is, where both sides are amounts."""
        if self.amount is None or self.expected is None:
            return None
        return money(self.amount - self.expected)


def equality_check(
    *, key: str, label: str, amount: Decimal, expected: Decimal, detail: str | None = None
) -> Check:
    """Two amounts that must be exactly equal at the stored scale.

    No tolerance. If a contract's lines and its header disagree by a cent, the
    contract is wrong by a cent and somebody should be told, not have it
    rounded away by the thing that was supposed to catch it.
    """
    left, right = money(amount), money(expected)
    return Check(key=key, label=label, ok=left == right, amount=left, expected=right, detail=detail)


def limit_check(
    *, key: str, label: str, amount: Decimal, limit: Decimal, detail: str | None = None
) -> Check:
    """An amount that must not exceed a ceiling — certified against commitment,
    paid against approved, released against held."""
    left, right = money(amount), money(limit)
    return Check(key=key, label=label, ok=left <= right, amount=left, expected=right, detail=detail)
