"""
Tests for the payment plan template engine.

Validates deterministic schedule generation, allocation math, and date sequencing.
All tests are pure Python — no database required.
"""

import pytest
from datetime import date

from app.modules.payment_plans.template_engine import (
    ScheduleLine,
    calculate_down_payment_amount,
    calculate_handover_amount,
    calculate_remaining_balance,
    generate_due_dates,
    generate_schedule,
    split_installments,
)
from app.shared.enums.finance import InstallmentFrequency


# ---------------------------------------------------------------------------
# calculate_down_payment_amount
# ---------------------------------------------------------------------------


def test_calculate_down_payment_amount_basic():
    assert calculate_down_payment_amount(500_000.0, 10.0) == pytest.approx(50_000.0)


def test_calculate_down_payment_amount_zero_percent():
    assert calculate_down_payment_amount(500_000.0, 0.0) == pytest.approx(0.0)


def test_calculate_down_payment_amount_100_percent():
    assert calculate_down_payment_amount(500_000.0, 100.0) == pytest.approx(500_000.0)


# ---------------------------------------------------------------------------
# calculate_handover_amount
# ---------------------------------------------------------------------------


def test_calculate_handover_amount_basic():
    assert calculate_handover_amount(500_000.0, 5.0) == pytest.approx(25_000.0)


def test_calculate_handover_amount_none():
    assert calculate_handover_amount(500_000.0, None) == pytest.approx(0.0)


def test_calculate_handover_amount_zero():
    assert calculate_handover_amount(500_000.0, 0.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# calculate_remaining_balance
# ---------------------------------------------------------------------------


def test_calculate_remaining_balance():
    remaining = calculate_remaining_balance(500_000.0, 50_000.0, 25_000.0)
    assert remaining == pytest.approx(425_000.0)


def test_calculate_remaining_balance_no_handover():
    remaining = calculate_remaining_balance(500_000.0, 50_000.0, 0.0)
    assert remaining == pytest.approx(450_000.0)


# ---------------------------------------------------------------------------
# split_installments
# ---------------------------------------------------------------------------


def test_split_installments_even_division():
    amounts = split_installments(120_000.0, 12)
    assert len(amounts) == 12
    assert all(a == pytest.approx(10_000.0) for a in amounts)
    assert sum(amounts) == pytest.approx(120_000.0)


def test_split_installments_rounding_absorbed_by_last():
    # 100_000 / 3 = 33_333.33... — remainder absorbed by last
    amounts = split_installments(100_000.0, 3)
    assert len(amounts) == 3
    assert sum(amounts) == pytest.approx(100_000.0)
    # Last installment takes any rounding difference
    assert amounts[0] == amounts[1]


def test_split_installments_single():
    amounts = split_installments(500_000.0, 1)
    assert amounts == [pytest.approx(500_000.0)]


def test_split_installments_invalid_count():
    with pytest.raises(ValueError):
        split_installments(100_000.0, 0)


# ---------------------------------------------------------------------------
# generate_due_dates
# ---------------------------------------------------------------------------


def test_generate_due_dates_monthly():
    dates = generate_due_dates(date(2026, 1, 1), 3, InstallmentFrequency.MONTHLY.value)
    assert dates == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_generate_due_dates_quarterly():
    dates = generate_due_dates(date(2026, 1, 1), 4, InstallmentFrequency.QUARTERLY.value)
    assert dates == [
        date(2026, 1, 1),
        date(2026, 4, 1),
        date(2026, 7, 1),
        date(2026, 10, 1),
    ]


def test_generate_due_dates_custom_defaults_to_monthly():
    dates = generate_due_dates(date(2026, 1, 1), 2, InstallmentFrequency.CUSTOM.value)
    assert dates == [date(2026, 1, 1), date(2026, 2, 1)]


def test_generate_due_dates_single():
    dates = generate_due_dates(date(2026, 6, 15), 1, InstallmentFrequency.MONTHLY.value)
    assert dates == [date(2026, 6, 15)]


# ---------------------------------------------------------------------------
# generate_schedule — end-to-end
# ---------------------------------------------------------------------------


_START = date(2026, 1, 1)


def _standard_schedule(
    contract_price: float = 500_000.0,
    down_pct: float = 10.0,
    n_installments: int = 12,
    handover_pct: float | None = None,
    frequency: str = InstallmentFrequency.MONTHLY.value,
) -> list[ScheduleLine]:
    return generate_schedule(
        contract_id="cid",
        template_id="tid",
        contract_price=contract_price,
        number_of_installments=n_installments,
        down_payment_percent=down_pct,
        installment_frequency=frequency,
        start_date=_START,
        handover_percent=handover_pct,
    )


def test_generate_schedule_total_equals_contract_price():
    lines = _standard_schedule()
    assert sum(l.due_amount for l in lines) == pytest.approx(500_000.0)


def test_generate_schedule_includes_down_payment():
    lines = _standard_schedule()
    assert lines[0].installment_number == 0
    assert lines[0].due_amount == pytest.approx(50_000.0)
    assert lines[0].notes == "Down payment"


def test_generate_schedule_down_payment_due_on_start_date():
    lines = _standard_schedule()
    assert lines[0].due_date == _START


def test_generate_schedule_installment_count_with_down_payment():
    lines = _standard_schedule(n_installments=12)
    # 1 down payment + 12 regular = 13 lines
    assert len(lines) == 13


def test_generate_schedule_installment_count_with_handover():
    lines = _standard_schedule(n_installments=12, handover_pct=5.0)
    # 1 down payment + 12 regular + 1 handover = 14 lines
    assert len(lines) == 14


def test_generate_schedule_handover_last():
    lines = _standard_schedule(n_installments=12, handover_pct=5.0)
    assert lines[-1].notes == "Handover"
    assert lines[-1].installment_number == 13


def test_generate_schedule_handover_amount():
    lines = _standard_schedule(contract_price=500_000.0, handover_pct=5.0, n_installments=12)
    handover = lines[-1]
    assert handover.due_amount == pytest.approx(25_000.0)


def test_generate_schedule_handover_date_after_last_installment():
    lines = _standard_schedule(n_installments=3, handover_pct=5.0)
    last_regular = lines[-2]
    handover = lines[-1]
    # Handover must be after last regular installment
    assert handover.due_date > last_regular.due_date


def test_generate_schedule_dates_are_sequential():
    lines = _standard_schedule(n_installments=6)
    regular_dates = [l.due_date for l in lines[1:]]  # skip down payment
    assert regular_dates == sorted(regular_dates)


def test_generate_schedule_zero_down_payment_omits_down_line():
    lines = _standard_schedule(down_pct=0.0, n_installments=12)
    assert all(l.installment_number != 0 for l in lines)
    assert len(lines) == 12


def test_generate_schedule_total_exact_for_awkward_price():
    # 333_333.33 is not evenly divisible — rounding logic must hold
    lines = _standard_schedule(contract_price=333_333.33, n_installments=7, down_pct=10.0)
    total = sum(l.due_amount for l in lines)
    assert abs(total - 333_333.33) < 0.02


def test_generate_schedule_returns_schedule_line_objects():
    lines = _standard_schedule()
    assert all(isinstance(l, ScheduleLine) for l in lines)


def test_generate_schedule_is_deterministic():
    lines1 = _standard_schedule()
    lines2 = _standard_schedule()
    assert lines1 == lines2


def test_generate_schedule_quarterly_frequency():
    lines = _standard_schedule(n_installments=4, frequency=InstallmentFrequency.QUARTERLY.value)
    regular = [l for l in lines if l.installment_number > 0]
    # Quarterly: 3-month gaps
    from dateutil.relativedelta import relativedelta
    for i in range(1, len(regular)):
        expected = regular[i - 1].due_date + relativedelta(months=3)
        assert regular[i].due_date == expected
