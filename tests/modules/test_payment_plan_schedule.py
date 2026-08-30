"""The pure schedule arithmetic, on its own.

No database, no HTTP, no permissions — which is the point of keeping these
functions in a module that has none of those. Every rounding and calendar edge
case is checked here, where a failure names the arithmetic rather than a route.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.payment_plans import schedule

# --------------------------------------------------------------------------- #
# Allocation
# --------------------------------------------------------------------------- #


def test_a_clean_split_allocates_exactly() -> None:
    fractions = [Decimal("0.2"), Decimal("0.3"), Decimal("0.5")]
    lines = schedule.allocate(Decimal("200000.00"), fractions)
    assert lines == [Decimal("40000.00"), Decimal("60000.00"), Decimal("100000.00")]
    assert sum(lines) == Decimal("200000.00")


def test_the_rounding_residual_goes_to_the_last_line() -> None:
    """Three thirds cannot each be exact, but the column must still add up."""
    fractions = [Decimal("0.333333"), Decimal("0.333333"), Decimal("0.333334")]
    lines = schedule.allocate(Decimal("200000.00"), fractions)
    assert sum(lines) == Decimal("200000.00")
    # The difference lands on one line, not spread as false precision.
    assert lines[0] == lines[1]


def test_an_incomplete_split_allocates_only_what_it_covers() -> None:
    """A 95% schedule allocates 95%. It is never rounded up to reconcile."""
    lines = schedule.allocate(Decimal("200000.00"), [Decimal("0.2"), Decimal("0.75")])
    assert sum(lines) == Decimal("190000.00")


def test_an_excessive_split_allocates_more_than_the_contract() -> None:
    lines = schedule.allocate(Decimal("200000.00"), [Decimal("0.5"), Decimal("0.6")])
    assert sum(lines) == Decimal("220000.00")


def test_allocating_nothing_is_not_a_special_case() -> None:
    assert schedule.allocate(Decimal("0.00"), [Decimal("0.5"), Decimal("0.5")]) == [
        Decimal("0.00"),
        Decimal("0.00"),
    ]
    assert schedule.allocate(Decimal("100.00"), []) == []


def test_a_large_contract_still_reconciles_to_the_unit() -> None:
    fractions = [Decimal("0.076923") for _ in range(12)] + [Decimal("0.076924")]
    lines = schedule.allocate(Decimal("98765432.10"), fractions)
    assert sum(lines) == Decimal("98765432.10")


def test_twenty_equal_lines_reconcile() -> None:
    lines = schedule.allocate(Decimal("220000.00"), [Decimal("0.05")] * 20)
    assert sum(lines) == Decimal("220000.00")
    assert len(lines) == 20


# --------------------------------------------------------------------------- #
# Derived fractions
# --------------------------------------------------------------------------- #


def test_amounts_derive_fractions_that_total_one() -> None:
    amounts = [Decimal("66666.66"), Decimal("66666.67"), Decimal("66666.67")]
    fractions = schedule.derive_fractions(Decimal("200000.00"), amounts)
    assert sum(fractions) == Decimal("1.000000")


def test_short_amounts_derive_short_fractions() -> None:
    fractions = schedule.derive_fractions(Decimal("200000.00"), [Decimal("190000.00")])
    assert sum(fractions) == Decimal("0.950000")


def test_a_zero_contract_derives_zero_fractions() -> None:
    """There is nothing to be a proportion of; inventing one would divide by zero."""
    assert schedule.derive_fractions(Decimal("0.00"), [Decimal("0.00")]) == [Decimal("0.000000")]


# --------------------------------------------------------------------------- #
# Calendar
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2026, 1, 31), 3, date(2026, 4, 30)),
        (date(2026, 11, 30), 3, date(2027, 2, 28)),
        (date(2026, 12, 31), 1, date(2027, 1, 31)),
        (date(2026, 8, 31), 6, date(2027, 2, 28)),
        (date(2026, 3, 15), 12, date(2027, 3, 15)),
        (date(2026, 5, 31), 0, date(2026, 5, 31)),
    ],
)
def test_month_arithmetic_clamps_to_the_last_valid_day(
    start: date, months: int, expected: date
) -> None:
    assert schedule.add_months(start, months) == expected


def test_a_series_does_not_drag_after_a_month_end_clamp() -> None:
    """January 31 to February 28 must not pull March back to the 28th.

    Each date is computed from the first, not from its predecessor.
    """
    rows = schedule.recurring_series(
        first_due_date=date(2026, 1, 31), count=4, months_between=1, label_prefix="Monthly"
    )
    assert [row.due_date for row in rows] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
    ]
    assert [row.recurrence_index for row in rows] == [1, 2, 3, 4]
    assert rows[0].label == "Monthly 1"


def test_a_quarterly_series_steps_three_months() -> None:
    rows = schedule.recurring_series(
        first_due_date=date(2026, 2, 15), count=4, months_between=3, label_prefix="Q"
    )
    assert [row.due_date for row in rows] == [
        date(2026, 2, 15),
        date(2026, 5, 15),
        date(2026, 8, 15),
        date(2026, 11, 15),
    ]


def test_a_forty_eight_month_series_is_ordinary() -> None:
    rows = schedule.recurring_series(
        first_due_date=date(2026, 1, 15), count=48, months_between=1, label_prefix="M"
    )
    assert len(rows) == 48
    assert rows[-1].due_date == date(2029, 12, 15)


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #


def _line(principal: str, fraction: str, tax: str = "0.00", fee: str = "0.00") -> schedule.Line:
    return schedule.Line(
        principal_amount=Decimal(principal),
        principal_fraction=Decimal(fraction),
        tax_amount=Decimal(tax),
        fee_amount=Decimal(fee),
    )


def test_an_exact_schedule_reconciles() -> None:
    result = schedule.reconcile(
        [_line("40000.00", "0.200000", "6400.00"), _line("160000.00", "0.800000", "25600.00")],
        contract_value_covered=Decimal("200000.00"),
        tax_total_snapshot=Decimal("32000.00"),
        buyer_fee_total_snapshot=Decimal("0.00"),
        total_buyer_payable_snapshot=Decimal("232000.00"),
    )
    assert result.is_reconciled is True
    assert schedule.shortfall_reasons(result) == []


def test_an_empty_schedule_never_reconciles() -> None:
    result = schedule.reconcile(
        [],
        contract_value_covered=Decimal("0.00"),
        tax_total_snapshot=Decimal("0.00"),
        buyer_fee_total_snapshot=Decimal("0.00"),
        total_buyer_payable_snapshot=Decimal("0.00"),
    )
    assert result.is_reconciled is False
    assert "no instalments" in schedule.shortfall_reasons(result)[0]


def test_a_shortfall_is_named_and_quantified() -> None:
    result = schedule.reconcile(
        [_line("190000.00", "0.950000")],
        contract_value_covered=Decimal("200000.00"),
        tax_total_snapshot=Decimal("0.00"),
        buyer_fee_total_snapshot=Decimal("0.00"),
        total_buyer_payable_snapshot=Decimal("200000.00"),
    )
    assert result.is_reconciled is False
    assert result.principal_delta == Decimal("-10000.00")
    reasons = " ".join(schedule.shortfall_reasons(result))
    assert "Principal is short by 10000.00" in reasons
    assert "0.950000" in reasons


def test_an_excess_is_named_and_quantified() -> None:
    result = schedule.reconcile(
        [_line("210000.00", "1.050000")],
        contract_value_covered=Decimal("200000.00"),
        tax_total_snapshot=Decimal("0.00"),
        buyer_fee_total_snapshot=Decimal("0.00"),
        total_buyer_payable_snapshot=Decimal("200000.00"),
    )
    assert result.principal_delta == Decimal("10000.00")
    assert "exceeds the contract by 10000.00" in " ".join(schedule.shortfall_reasons(result))


def test_one_missing_unit_of_tax_blocks_the_whole_schedule() -> None:
    result = schedule.reconcile(
        [_line("200000.00", "1.000000", "31999.99")],
        contract_value_covered=Decimal("200000.00"),
        tax_total_snapshot=Decimal("32000.00"),
        buyer_fee_total_snapshot=Decimal("0.00"),
        total_buyer_payable_snapshot=Decimal("232000.00"),
    )
    assert result.is_reconciled is False
    assert result.tax_delta == Decimal("-0.01")


def test_the_buyer_total_is_the_sum_of_all_three_columns() -> None:
    result = schedule.reconcile(
        [_line("100.00", "1.000000", "16.00", "5.00")],
        contract_value_covered=Decimal("100.00"),
        tax_total_snapshot=Decimal("16.00"),
        buyer_fee_total_snapshot=Decimal("5.00"),
        total_buyer_payable_snapshot=Decimal("121.00"),
    )
    assert result.scheduled_buyer_total == Decimal("121.00")
    assert result.is_reconciled is True
