"""
collections.receipt_matching_service

Pure-function receipt matching engine.

Matches an incoming payment amount against outstanding installment
obligations for a contract.

Matching strategies
-------------------
1. Exact match      — payment amount == installment amount (single line).
2. Partial payment  — payment amount < smallest outstanding installment.
3. Multi-installment — payment amount covers one or more installments exactly
                        or leaves a remainder that is itself a partial payment.
4. Unmatched        — payment cannot be associated with any obligation (e.g.
                       no outstanding installments, or amount is zero).

The engine is stateless: it accepts data snapshots and returns result objects.
No database writes are performed here; callers decide how to persist results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.shared.enums.finance import MatchStrategy


_CENT = 100  # cents per currency unit


def _to_cents(amount: float) -> int:
    """Convert to integer cents (round to 2 dp first)."""
    return round(round(amount, 2) * _CENT)


# ---------------------------------------------------------------------------
# Data models (input + output)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstallmentObligation:
    """Minimal outstanding installment data required for matching."""

    id: str
    installment_number: int
    outstanding_amount: float


@dataclass
class ReceiptMatchResult:
    """Outcome of attempting to match a payment to installment obligations.

    Attributes
    ----------
    strategy:
        Which matching strategy was applied.
    matched_installment_ids:
        IDs of installments that are fully or partially covered.
    allocated_amounts:
        ``{installment_id: amount_applied}`` for each matched installment.
    unallocated_amount:
        Portion of the payment that could not be matched.
    """

    strategy: MatchStrategy
    matched_installment_ids: list[str] = field(default_factory=list)
    allocated_amounts: dict[str, float] = field(default_factory=dict)
    unallocated_amount: float = 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def match_payment_to_installments(
    payment_amount: float,
    outstanding_installments: list[InstallmentObligation],
) -> ReceiptMatchResult:
    """Determine how a payment should be allocated across outstanding installments.

    The installments are evaluated in ascending ``installment_number`` order so
    earlier installments are satisfied first.

    Parameters
    ----------
    payment_amount:
        The incoming payment amount (must be > 0).
    outstanding_installments:
        All installments that still carry an outstanding balance (amount > 0).

    Returns
    -------
    ReceiptMatchResult
        Describes the matching strategy and per-installment allocations.
    """
    if payment_amount <= 0 or not outstanding_installments:
        return detect_unmatched_payment(payment_amount)

    sorted_installments = sorted(
        outstanding_installments, key=lambda i: i.installment_number
    )

    # Check for exact single-installment match first.
    for inst in sorted_installments:
        if _to_cents(payment_amount) == _to_cents(inst.outstanding_amount):
            return _exact_match(inst, payment_amount)

    # Check whether the payment is smaller than the first installment outstanding.
    first = sorted_installments[0]
    if _to_cents(payment_amount) < _to_cents(first.outstanding_amount):
        return apply_partial_payment(payment_amount, first)

    # Attempt to allocate across multiple installments.
    return allocate_multi_installment_payment(payment_amount, sorted_installments)


def _exact_match(
    installment: InstallmentObligation, amount: float
) -> ReceiptMatchResult:
    """Return an exact-match result for a single installment."""
    return ReceiptMatchResult(
        strategy=MatchStrategy.EXACT,
        matched_installment_ids=[installment.id],
        allocated_amounts={installment.id: round(amount, 2)},
        unallocated_amount=0.0,
    )


def apply_partial_payment(
    payment_amount: float,
    installment: InstallmentObligation,
) -> ReceiptMatchResult:
    """Apply a payment that is less than the installment's outstanding amount.

    The full payment is applied to the first (or only) installment.
    """
    allocated = round(payment_amount, 2)
    return ReceiptMatchResult(
        strategy=MatchStrategy.PARTIAL,
        matched_installment_ids=[installment.id],
        allocated_amounts={installment.id: allocated},
        unallocated_amount=0.0,
    )


def allocate_multi_installment_payment(
    payment_amount: float,
    installments: list[InstallmentObligation],
) -> ReceiptMatchResult:
    """Greedily allocate a payment across multiple installments in order.

    Each installment is fully satisfied before the next is touched.
    If the remaining amount is insufficient to fully cover the next
    installment, the remainder is applied as a partial allocation to that
    installment and no unallocated balance remains.

    If the payment exceeds all installment obligations, the surplus is
    returned as ``unallocated_amount`` and the strategy is labelled
    ``MULTI_INSTALLMENT`` (not ``PARTIAL``) to reflect overpayment.
    """
    remaining_cents = _to_cents(payment_amount)
    matched_ids: list[str] = []
    allocations: dict[str, float] = {}

    for inst in installments:
        if remaining_cents <= 0:
            break
        inst_cents = _to_cents(inst.outstanding_amount)
        if remaining_cents >= inst_cents:
            # Fully cover this installment.
            allocations[inst.id] = inst.outstanding_amount
            matched_ids.append(inst.id)
            remaining_cents -= inst_cents
        else:
            # Partial coverage of this installment with leftover.
            partial = round(remaining_cents / _CENT, 2)
            allocations[inst.id] = partial
            matched_ids.append(inst.id)
            remaining_cents = 0
            break

    unallocated = round(remaining_cents / _CENT, 2)
    strategy = (
        MatchStrategy.MULTI_INSTALLMENT
        if len(matched_ids) > 1 or unallocated > 0
        else MatchStrategy.PARTIAL
    )
    return ReceiptMatchResult(
        strategy=strategy,
        matched_installment_ids=matched_ids,
        allocated_amounts=allocations,
        unallocated_amount=unallocated,
    )


def detect_unmatched_payment(payment_amount: float) -> ReceiptMatchResult:
    """Return an unmatched result when no allocation is possible."""
    return ReceiptMatchResult(
        strategy=MatchStrategy.UNMATCHED,
        matched_installment_ids=[],
        allocated_amounts={},
        unallocated_amount=round(max(payment_amount, 0.0), 2),
    )
