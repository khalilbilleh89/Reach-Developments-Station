"""
Payment plan template engine.

Pure, deterministic business logic for generating payment schedule lines.
No database access.  No side effects.

Generation algorithm (standard installments)
--------------------------------------------
1. down_payment_amount  = contract_price * down_payment_percent / 100
2. handover_amount      = contract_price * handover_percent / 100   (0 if absent)
3. remaining_balance    = contract_price - down_payment_amount - handover_amount
4. installment_amounts  = split evenly across number_of_installments
   (last installment absorbs rounding remainder)
5. due_dates            = start_date + (n * period) for n in 0..N-1

Installment numbering
---------------------
- Down payment:       installment_number = 0
- Regular intervals:  installment_number = 1 … N
- Handover:           installment_number = N + 1  (after last regular installment)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import List, Optional


@dataclass(frozen=True)
class ScheduleLine:
    """A single generated payment schedule line (not yet persisted)."""

    installment_number: int
    due_date: date
    due_amount: float
    notes: Optional[str] = None


def calculate_down_payment_amount(contract_price: float, down_payment_percent: float) -> float:
    """Down payment amount from contract price and percentage."""
    return round(contract_price * down_payment_percent / 100.0, 2)


def calculate_handover_amount(contract_price: float, handover_percent: Optional[float]) -> float:
    """Handover amount from contract price and percentage (0.0 if absent)."""
    if handover_percent is None or handover_percent == 0.0:
        return 0.0
    return round(contract_price * handover_percent / 100.0, 2)


def calculate_remaining_balance(
    contract_price: float,
    down_payment_amount: float,
    handover_amount: float,
) -> float:
    """Remaining balance after removing down payment and handover from contract price."""
    return round(contract_price - down_payment_amount - handover_amount, 2)


def split_installments(remaining_balance: float, number_of_installments: int) -> List[float]:
    """
    Split remaining_balance evenly over number_of_installments.

    The last installment absorbs any rounding remainder so the sum is exact.
    """
    if number_of_installments <= 0:
        raise ValueError("number_of_installments must be positive.")
    base_amount = round(remaining_balance / number_of_installments, 2)
    amounts = [base_amount] * number_of_installments
    # Adjust last installment to absorb rounding difference
    total_allocated = round(base_amount * number_of_installments, 2)
    remainder = round(remaining_balance - total_allocated, 2)
    amounts[-1] = round(amounts[-1] + remainder, 2)
    return amounts


def generate_due_dates(
    start_date: date,
    number_of_installments: int,
    frequency: str,
) -> List[date]:
    """
    Generate a sequence of due dates starting from start_date.

    Supports 'monthly' (+1 month each) and 'quarterly' (+3 months each).
    'custom' uses monthly as default period; callers may override post-generation.
    """
    from app.shared.enums.finance import InstallmentFrequency

    if frequency == InstallmentFrequency.QUARTERLY.value:
        delta = relativedelta(months=3)
    else:
        # monthly and custom both default to monthly
        delta = relativedelta(months=1)

    dates = []
    current = start_date
    for _ in range(number_of_installments):
        dates.append(current)
        current = current + delta
    return dates


def generate_schedule(
    contract_id: str,
    template_id: Optional[str],
    contract_price: float,
    number_of_installments: int,
    down_payment_percent: float,
    installment_frequency: str,
    start_date: date,
    handover_percent: Optional[float] = None,
) -> List[ScheduleLine]:
    """
    Generate the full list of ScheduleLine objects for a contract.

    Lines are in order:
      - installment 0  : down payment (due on start_date)
      - installments 1…N: regular installments
      - installment N+1 : handover (due after last regular installment)
    """
    lines: List[ScheduleLine] = []

    down_amount = calculate_down_payment_amount(contract_price, down_payment_percent)
    handover_amount = calculate_handover_amount(contract_price, handover_percent)
    remaining = calculate_remaining_balance(contract_price, down_amount, handover_amount)

    installment_amounts = split_installments(remaining, number_of_installments)
    due_dates = generate_due_dates(start_date, number_of_installments, installment_frequency)

    # Down payment (installment 0) — due on start_date
    if down_amount > 0.0:
        lines.append(
            ScheduleLine(
                installment_number=0,
                due_date=start_date,
                due_amount=down_amount,
                notes="Down payment",
            )
        )

    # Regular installments
    for idx, (amount, due_date) in enumerate(zip(installment_amounts, due_dates), start=1):
        lines.append(
            ScheduleLine(
                installment_number=idx,
                due_date=due_date,
                due_amount=amount,
            )
        )

    # Handover installment (after last regular installment)
    if handover_amount > 0.0:
        last_due_date = due_dates[-1] if due_dates else start_date
        from app.shared.enums.finance import InstallmentFrequency
        if installment_frequency == InstallmentFrequency.QUARTERLY.value:
            handover_due = last_due_date + relativedelta(months=3)
        else:
            handover_due = last_due_date + relativedelta(months=1)
        lines.append(
            ScheduleLine(
                installment_number=number_of_installments + 1,
                due_date=handover_due,
                due_amount=handover_amount,
                notes="Handover",
            )
        )

    return lines
