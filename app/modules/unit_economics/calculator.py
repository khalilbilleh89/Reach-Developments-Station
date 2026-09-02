"""The unit economics arithmetic, and nothing else.

No session, no actor, no query, no audit write. Inputs in, figures out — the
same discipline as ``pricing/calculator.py`` and ``collections/ledger.py``, and
for the same reason: a cost allocation somebody signed must be reproducible from
its recorded inputs, and a calculation that can also read a row is one whose
answer depends on when it was asked.

Two things are computed here.

**Dividing a pool.** :func:`allocate` turns one amount and a list of drivers
into a list of amounts that sum to the original *exactly*. Not to within a cent
— exactly, at the scale the money column stores, because a pool that does not
reconcile is a pool whose total nobody can trace to its parts. Rounding leaves a
residual and the residual goes somewhere deterministic rather than nowhere.

**Layering profit.** :func:`profitability` applies one fixed sequence of
subtractions. There is no formula engine and no configurable ordering: the
layers below are what a development appraisal means by gross, contribution and
post-finance profit, and a system that let each project reorder them would let
two projects disagree about what "margin" is.

```text
  Revenue
- Direct + Land + Hard + Soft           = Development cost
  ------------------------------------------------------
= Gross profit
- Variable selling + Commercial seller cost   = Commercial cost
  ------------------------------------------------------
= Contribution profit
- Allocated finance + Deal finance cost       = Finance cost
  ------------------------------------------------------
= Profit after finance
```

A ratio whose denominator is zero is ``None``, never zero. Zero margin and
undefined margin are different facts, and the screen that prints ``0.0%`` for
both is the screen that gets believed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.db.base import MONEY_EXPONENT, RATE

ZERO = Decimal("0.00")

#: The scale rates are stored at, for quantising a derived share or margin back
#: to it. A ratio the column cannot hold is a ratio that changes when read back.
RATE_EXPONENT = Decimal(1).scaleb(-RATE.scale)


def money(amount: Decimal) -> Decimal:
    """Quantise to the scale the money column stores. Half-up, once per figure."""
    return amount.quantize(MONEY_EXPONENT, rounding=ROUND_HALF_UP)


def rate(value: Decimal) -> Decimal:
    """Quantise a fraction to the scale the rate column stores."""
    return value.quantize(RATE_EXPONENT, rounding=ROUND_HALF_UP)


class AllocationError(ValueError):
    """A pool that cannot be divided, with a message an operator can act on."""


# --------------------------------------------------------------------------- #
# Dividing a pool
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DriverLine:
    """One eligible unit's contribution to a pool's denominator."""

    unit_id: uuid.UUID
    driver_value: Decimal


@dataclass(frozen=True, slots=True)
class AllocationLine:
    """One unit's share of one pool, and how it was arrived at."""

    unit_id: uuid.UUID
    driver_value: Decimal
    driver_share: Decimal
    allocated_amount: Decimal
    is_rounding_recipient: bool


def allocate(*, pool_amount: Decimal, drivers: list[DriverLine]) -> list[AllocationLine]:
    """Divide ``pool_amount`` across ``drivers`` so the parts sum to the whole.

    Every share is computed against the *unrounded* total and quantised once.
    The residual — what rounding lost or gained, at most a few cents on any real
    pool — is given to one deterministic recipient rather than spread, dropped,
    or absorbed into whichever line happened to be last.

    The recipient is the largest driver, ties broken by unit id, so the same
    inputs always produce the same allocation. Largest rather than smallest
    because a cent is least visible against the biggest share, and stable rather
    than random because an allocation that changes on recalculation is one
    nobody can re-approve.

    Refuses an empty population and a zero denominator. A pool nobody is
    eligible for, or one whose drivers are all zero, has no allocation — and
    writing zeros for it would report a shared cost as having been absorbed by
    nobody while still counting in the project total.
    """
    if not drivers:
        raise AllocationError("No eligible units, so this pool cannot be allocated.")
    total_driver = sum((line.driver_value for line in drivers), Decimal("0"))
    if total_driver <= 0:
        raise AllocationError(
            "Every eligible unit has a driver of zero, so there is nothing to divide this pool by."
        )

    amount = money(pool_amount)
    shares = [line.driver_value / total_driver for line in drivers]
    amounts = [money(amount * share) for share in shares]
    residual = amount - sum(amounts, ZERO)

    recipient = max(
        range(len(drivers)),
        key=lambda index: (drivers[index].driver_value, str(drivers[index].unit_id)),
    )
    amounts[recipient] = amounts[recipient] + residual

    return [
        AllocationLine(
            unit_id=line.unit_id,
            driver_value=line.driver_value,
            driver_share=rate(share),
            allocated_amount=allocated,
            is_rounding_recipient=index == recipient,
        )
        for index, (line, share, allocated) in enumerate(zip(drivers, shares, amounts, strict=True))
    ]


def reconciles(*, pool_amount: Decimal, allocated: list[Decimal]) -> Decimal:
    """The variance between a pool and what was allocated from it. Normally zero.

    Returned rather than asserted so the caller can name the pool in its own
    refusal, and so the reconciliation view can show a variance rather than
    merely failing.
    """
    return money(pool_amount) - money(sum(allocated, ZERO))


# --------------------------------------------------------------------------- #
# Layering profit
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CostInputs:
    """Everything that reduces a unit's revenue, by the layer it belongs to.

    Eight figures rather than one total, because "which layer" is the whole
    question: a commission and a construction cost both reduce profit and a
    developer manages them in completely different meetings.
    """

    direct_cost: Decimal = ZERO
    land_cost: Decimal = ZERO
    hard_cost: Decimal = ZERO
    soft_cost: Decimal = ZERO
    variable_selling_cost: Decimal = ZERO
    commercial_seller_cost: Decimal = ZERO
    allocated_finance_cost: Decimal = ZERO
    deal_finance_cost: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class Profitability:
    """One unit's profit, layer by layer, with every subtotal a reader may ask for.

    Margins are ``None`` where the denominator is not positive. That is the one
    place this dataclass is opinionated, and it is opinionated on purpose.
    """

    revenue: Decimal
    development_cost: Decimal
    gross_profit: Decimal
    commercial_cost: Decimal
    contribution_profit: Decimal
    finance_cost: Decimal
    profit_after_finance: Decimal
    total_cost: Decimal
    gross_margin_fraction: Decimal | None
    contribution_margin_fraction: Decimal | None
    margin_fraction: Decimal | None
    return_on_cost_fraction: Decimal | None


def profitability(*, revenue: Decimal, costs: CostInputs) -> Profitability:
    """Apply the layers in their fixed order and return every subtotal.

    Revenue is the effective net revenue *before* seller costs: concessions have
    already reduced it, seller costs have not. That distinction is the one this
    module is most likely to get wrong, and getting it wrong subtracts a package
    the developer absorbed twice — once inside revenue and once as a cost — for
    a margin that is quietly too low and internally consistent.
    """
    revenue = money(revenue)
    development = money(costs.direct_cost + costs.land_cost + costs.hard_cost + costs.soft_cost)
    gross = money(revenue - development)
    commercial = money(costs.variable_selling_cost + costs.commercial_seller_cost)
    contribution = money(gross - commercial)
    finance = money(costs.allocated_finance_cost + costs.deal_finance_cost)
    after_finance = money(contribution - finance)
    total = money(development + commercial + finance)

    return Profitability(
        revenue=revenue,
        development_cost=development,
        gross_profit=gross,
        commercial_cost=commercial,
        contribution_profit=contribution,
        finance_cost=finance,
        profit_after_finance=after_finance,
        total_cost=total,
        gross_margin_fraction=_ratio(gross, revenue),
        contribution_margin_fraction=_ratio(contribution, revenue),
        margin_fraction=_ratio(after_finance, revenue),
        return_on_cost_fraction=_ratio(after_finance, total),
    )


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """A fraction, or ``None`` where the denominator cannot carry one.

    Negative numerators are returned as they are. A loss is a fact and clamping
    it to zero would hide the units the business most needs to look at.
    """
    if denominator <= 0:
        return None
    return rate(numerator / denominator)


# --------------------------------------------------------------------------- #
# Summing units into a project
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PortfolioTotals:
    """Every comparable unit added up, with weighted ratios rather than averages.

    A project margin is total profit over total revenue. The average of the unit
    margins is a different number, it is not the developer's margin, and the gap
    between the two grows with how unequal the units are — which is exactly the
    projects where somebody is relying on the figure.
    """

    unit_count: int
    revenue_total: Decimal
    development_cost_total: Decimal
    commercial_cost_total: Decimal
    finance_cost_total: Decimal
    total_cost_total: Decimal
    gross_profit_total: Decimal
    contribution_profit_total: Decimal
    profit_total: Decimal
    margin_fraction: Decimal | None
    return_on_cost_fraction: Decimal | None


def portfolio(rows: list[Profitability]) -> PortfolioTotals:
    """Add up the units whose profit could actually be calculated."""
    revenue = money(sum((row.revenue for row in rows), ZERO))
    development = money(sum((row.development_cost for row in rows), ZERO))
    commercial = money(sum((row.commercial_cost for row in rows), ZERO))
    finance = money(sum((row.finance_cost for row in rows), ZERO))
    total_cost = money(sum((row.total_cost for row in rows), ZERO))
    gross = money(sum((row.gross_profit for row in rows), ZERO))
    contribution = money(sum((row.contribution_profit for row in rows), ZERO))
    profit = money(sum((row.profit_after_finance for row in rows), ZERO))
    return PortfolioTotals(
        unit_count=len(rows),
        revenue_total=revenue,
        development_cost_total=development,
        commercial_cost_total=commercial,
        finance_cost_total=finance,
        total_cost_total=total_cost,
        gross_profit_total=gross,
        contribution_profit_total=contribution,
        profit_total=profit,
        margin_fraction=_ratio(profit, revenue),
        return_on_cost_fraction=_ratio(profit, total_cost),
    )


# --------------------------------------------------------------------------- #
# The waterfall
# --------------------------------------------------------------------------- #

#: The order a cost waterfall is read in, and the label each step carries. Here
#: rather than in the frontend because the sequence is the calculation: a UI
#: that owned the order could render a subtraction the backend never made.
WATERFALL_STEPS: tuple[tuple[str, str], ...] = (
    ("revenue", "Revenue"),
    ("land_cost", "Land"),
    ("hard_cost", "Hard"),
    ("soft_cost", "Soft"),
    ("direct_cost", "Direct"),
    ("gross_profit", "Gross profit"),
    ("variable_selling_cost", "Variable selling"),
    ("seller_cost", "Seller cost"),
    ("contribution_profit", "Contribution profit"),
    ("finance_cost", "Finance"),
    ("profit_after_finance", "Profit after finance"),
)

#: Which waterfall steps are subtotals rather than deductions.
WATERFALL_SUBTOTALS = frozenset(
    {"revenue", "gross_profit", "contribution_profit", "profit_after_finance"}
)
