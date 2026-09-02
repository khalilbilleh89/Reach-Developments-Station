"""Public contracts for collections.

Every request model refuses a key it does not declare. A misspelled ``ammount``
answering 200 would report cash recorded that was not, and this is the ledger a
development's receivables are read from.

Money is ``Decimal`` end to end and leaves the API as a JSON string, for the
reason stated wherever money is defined in this codebase: a JSON number is a
float, and a float is not an acceptable carrier for a buyer's balance.

No status field is writable anywhere here. Recording, confirming and reversing a
receipt are three acts with three different rights and three sets of
preconditions, so each has its own route — a ``PATCH {"status": "confirmed"}``
would be Finance's signature available to whoever could reach the endpoint.

There is deliberately no ``unapplied_amount`` input, no ``outstanding`` input
and no ``days_overdue`` input. Those are derived server-side and appear on
responses only. A client that could send them could disagree with the ledger.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.modules.collections.ledger import AGING_BUCKETS, INSTALLMENT_STATUSES
from app.modules.collections.models import (
    ACTION_TYPES,
    ALLOCATION_STATUSES,
    DISPUTE_STATUSES,
    RECEIPT_STATUSES,
    REFUND_STATUSES,
    RESTRUCTURE_STATUSES,
    WAIVER_STATUSES,
    WAIVER_TYPES,
)
from app.modules.projects.schemas import StrictRequest

DecimalStr = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]

#: ``max_digits`` mirrors the column rather than a preference: without it a
#: value like ``1e400`` passes every other rule and then overflows NUMERIC(18,2)
#: inside the transaction, reaching the caller as a 500 with nothing useful in it.
Money = Annotated[DecimalStr, Field(ge=0, max_digits=18, decimal_places=2)]
#: An amount of cash actually moving. Zero is not a transaction.
PositiveMoney = Annotated[DecimalStr, Field(gt=0, max_digits=18, decimal_places=2)]

ReceiptStatus = Literal[RECEIPT_STATUSES]  # type: ignore[valid-type]
AllocationStatus = Literal[ALLOCATION_STATUSES]  # type: ignore[valid-type]
ActionType = Literal[ACTION_TYPES]  # type: ignore[valid-type]
DisputeStatus = Literal[DISPUTE_STATUSES]  # type: ignore[valid-type]
WaiverType = Literal[WAIVER_TYPES]  # type: ignore[valid-type]
WaiverStatus = Literal[WAIVER_STATUSES]  # type: ignore[valid-type]
RestructureStatus = Literal[RESTRUCTURE_STATUSES]  # type: ignore[valid-type]
RefundStatus = Literal[REFUND_STATUSES]  # type: ignore[valid-type]
AgingBucket = Literal[AGING_BUCKETS]  # type: ignore[valid-type]
InstallmentCollectionStatus = Literal[INSTALLMENT_STATUSES]  # type: ignore[valid-type]

_REASON = Field(min_length=1, max_length=500)
_NOTES = Field(min_length=1, max_length=2000)


class _Read(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Receipts
# --------------------------------------------------------------------------- #


class ReceiptCreate(StrictRequest):
    """Record a claim that money arrived.

    ``currency_id`` is optional because the contract already settles it. When
    supplied it is checked rather than obeyed: a client sending a different
    currency is told so, instead of having its intent silently overwritten.
    """

    amount: PositiveMoney
    receipt_date: date
    currency_id: uuid.UUID | None = None
    bank_reference: str | None = Field(default=None, max_length=200)
    external_reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class ReversalRequest(StrictRequest):
    """Undo something that was confirmed. The reason is not optional."""

    reason: str = _REASON


class AllocationRead(_Read):
    """One application of receipt cash to one instalment."""

    id: uuid.UUID
    receipt_id: uuid.UUID
    installment_id: uuid.UUID
    payment_plan_version_id: uuid.UUID
    amount: Money
    status: AllocationStatus
    created_at: datetime
    reversal_reason: str | None = None
    superseded_by_restructure_id: uuid.UUID | None = None


class ReceiptRead(_Read):
    """One receipt, with what is left of it derived on the server."""

    id: uuid.UUID
    sale_contract_id: uuid.UUID
    receipt_number: str
    currency_id: uuid.UUID
    amount: Money
    receipt_date: date
    status: ReceiptStatus
    bank_reference: str | None = None
    external_reference: str | None = None
    notes: str | None = None
    recorded_at: datetime
    recorded_by_user_id: uuid.UUID
    confirmed_at: datetime | None = None
    confirmed_by_user_id: uuid.UUID | None = None
    reversed_at: datetime | None = None
    reversal_reason: str | None = None
    #: ``amount`` less every active allocation. Never stored.
    unapplied_amount: Money
    #: Whether this receipt's cash counts anywhere. Only ``confirmed`` does.
    counts_as_cash: bool
    allocations: list[AllocationRead] = []


class AllocationCreate(StrictRequest):
    """Apply part of a receipt to one instalment of the governing schedule."""

    installment_id: uuid.UUID
    amount: PositiveMoney


class SuggestedAllocationRead(BaseModel):
    """Where this receipt's unapplied cash would go. A proposal, never a posting."""

    installment_id: uuid.UUID
    sequence: int
    label: str
    due_date: date | None
    outstanding: Money
    amount: Money


# --------------------------------------------------------------------------- #
# The receivable
# --------------------------------------------------------------------------- #


class CollectionInstallmentRow(BaseModel):
    """One instalment with the cash against it, aged as at ``as_of``.

    Both ``status`` and the flags beside it, because a badge that replaced the
    facts would make a disputed, overdue, part-paid instalment unreadable.
    """

    installment_id: uuid.UUID
    sequence: int
    label: str
    trigger_type: str
    trigger_status: str
    due_date: date | None
    grace_days: int
    scheduled: Money
    paid: Money
    outstanding: Money
    overdue_days: int
    bucket: AgingBucket
    status: InstallmentCollectionStatus
    is_disputed: bool
    has_active_waiver: bool
    waived_until: date | None
    owner_user_id: uuid.UUID | None


class CollectionSaleSummary(BaseModel):
    """One sale's whole collections position. Every figure derived at read time."""

    sale_id: uuid.UUID
    currency_id: uuid.UUID
    as_of: date
    active_payment_plan_id: uuid.UUID | None
    active_payment_plan_version_id: uuid.UUID | None
    scheduled_total: Money
    confirmed_receipts_total: Money
    allocated_total: Money
    unapplied_cash: Money
    outstanding_total: Money
    due_total: Money
    overdue_total: Money
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
    #: What the cancellations say is owed back, and what has actually left.
    #: Reported side by side and never netted into one "refund" figure.
    refund_due_total: Money
    refund_confirmed_total: Money
    refund_outstanding: Money
    collection_clearance_status: str | None
    clearance_blockers: list[str] = []
    installments: list[CollectionInstallmentRow] = []


class CollectionRegisterRow(BaseModel):
    """One account on the project register."""

    sale_id: uuid.UUID
    sale_number: str
    spa_number: str | None
    unit_id: uuid.UUID
    unit_number: str
    client_display_name: str
    currency_id: uuid.UUID
    summary: CollectionSaleSummary


class AgingRowRead(BaseModel):
    """One instalment on the aging report, with the account it belongs to."""

    sale_id: uuid.UUID
    sale_number: str
    unit_number: str
    client_display_name: str
    currency_id: uuid.UUID
    installment: CollectionInstallmentRow


class CollectionCurrencyTotals(BaseModel):
    """Every money figure for one denomination. Nothing here crosses currencies."""

    currency_id: uuid.UUID
    accounts: int
    outstanding_total: Money
    due_total: Money
    overdue_total: Money
    unapplied_cash: Money
    confirmed_receipts_total: Money
    buckets: dict[str, Money]


class CollectionProjectSummary(BaseModel):
    """The project strip. ``confirmed_receipts_total`` is lifetime and says so.

    Money is grouped by currency and there is deliberately no project-wide
    total: a project selling in two currencies has no single outstanding
    figure, and one produced by adding them would be wrong by the exchange
    rate while looking exactly like a fact. The counts are project-wide,
    because a count of accounts is not money.
    """

    as_of: date
    accounts: int
    accounts_overdue: int
    accounts_disputed: int
    accounts_cleared: int
    currencies: list[CollectionCurrencyTotals]


# --------------------------------------------------------------------------- #
# Operations
# --------------------------------------------------------------------------- #


class CollectionActionCreate(StrictRequest):
    """Append what Collections did. A promise here is not a payment anywhere."""

    action_type: ActionType
    action_at: date
    notes: str = _NOTES
    installment_id: uuid.UUID | None = None
    promised_amount: PositiveMoney | None = None
    promised_date: date | None = None
    next_action_date: date | None = None


class CollectionActionRead(_Read):
    """One recorded chase."""

    id: uuid.UUID
    sale_contract_id: uuid.UUID
    installment_id: uuid.UUID | None
    action_type: ActionType
    action_at: date
    notes: str
    promised_amount: Money | None
    promised_date: date | None
    next_action_date: date | None
    created_at: datetime
    created_by_user_id: uuid.UUID


class DisputeCreate(StrictRequest):
    """Contest an instalment. The instalment stays due and stays counted."""

    reason: str = Field(min_length=1, max_length=2000)


class DisputeClose(StrictRequest):
    """Resolve or withdraw a dispute. The outcome is recorded either way."""

    resolution: str = Field(min_length=1, max_length=2000)


class DisputeRead(_Read):
    """One dispute."""

    id: uuid.UUID
    sale_contract_id: uuid.UUID
    installment_id: uuid.UUID
    status: DisputeStatus
    reason: str
    opened_at: datetime
    opened_by_user_id: uuid.UUID
    resolved_at: datetime | None
    resolved_by_user_id: uuid.UUID | None
    resolution: str | None


class WaiverCreate(StrictRequest):
    """Ask for an operational pause. Never a reduction of what is owed."""

    waiver_type: WaiverType
    waived_until: date
    reason: str = Field(min_length=1, max_length=2000)


class WaiverDecision(StrictRequest):
    """Refuse or withdraw a waiver, with the reason on the record."""

    reason: str = _REASON


class WaiverRead(_Read):
    """One waiver, at whatever point of its life it has reached."""

    id: uuid.UUID
    sale_contract_id: uuid.UUID
    installment_id: uuid.UUID
    waiver_type: WaiverType
    waived_until: date
    reason: str
    status: WaiverStatus
    submitted_at: datetime
    submitted_by_user_id: uuid.UUID
    approved_at: datetime | None
    approved_by_user_id: uuid.UUID | None
    rejected_at: datetime | None
    rejection_reason: str | None
    revoked_at: datetime | None
    revocation_reason: str | None


# --------------------------------------------------------------------------- #
# Restructures
# --------------------------------------------------------------------------- #


class RestructureCreate(StrictRequest):
    """Raise a restructure and open the revision it will carry the cash onto."""

    reason: str = Field(min_length=1, max_length=2000)
    effective_date: date | None = None


class RestructureRead(_Read):
    """One restructure."""

    id: uuid.UUID
    sale_contract_id: uuid.UUID
    payment_plan_id: uuid.UUID
    restructure_number: str
    source_version_id: uuid.UUID
    replacement_version_id: uuid.UUID
    status: RestructureStatus
    reason: str
    requested_at: datetime
    requested_by_user_id: uuid.UUID
    applied_at: datetime | None
    applied_by_user_id: uuid.UUID | None
    abandoned_at: datetime | None
    abandonment_reason: str | None


class CarryLineRead(BaseModel):
    """One receipt's cash landing on one instalment of the replacement schedule."""

    receipt_id: uuid.UUID
    installment_id: uuid.UUID
    amount: Money


class RestructureApplyPreview(BaseModel):
    """Exactly what applying would do, and what still stands in the way.

    ``carried_total`` must equal the cash currently allocated, and
    ``unapplied_total`` must be unchanged by the move. Both are shown so the
    person confirming can see conservation rather than take it on trust.
    """

    restructure_id: uuid.UUID
    source_version_id: uuid.UUID
    replacement_version_id: uuid.UUID
    replacement_status: str
    ready_to_apply: bool
    blockers: list[str]
    carried_total: Money
    unapplied_total: Money
    confirmed_receipts_total: Money
    superseding: int
    lines: list[CarryLineRead]


class RestructureApplyResponse(BaseModel):
    """The restructure after it was applied, with the account it left behind."""

    restructure: RestructureRead
    summary: CollectionSaleSummary


# --------------------------------------------------------------------------- #
# Refunds
# --------------------------------------------------------------------------- #


class RefundCreate(StrictRequest):
    """Record a repayment being made against a cancellation."""

    cancellation_id: uuid.UUID
    amount: PositiveMoney
    refund_date: date
    currency_id: uuid.UUID | None = None
    bank_reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class RefundRead(_Read):
    """One refund."""

    id: uuid.UUID
    sale_contract_id: uuid.UUID
    cancellation_id: uuid.UUID
    refund_number: str
    currency_id: uuid.UUID
    amount: Money
    refund_date: date
    status: RefundStatus
    bank_reference: str | None
    notes: str | None
    recorded_at: datetime
    recorded_by_user_id: uuid.UUID
    confirmed_at: datetime | None
    confirmed_by_user_id: uuid.UUID | None
    reversed_at: datetime | None
    reversal_reason: str | None


# --------------------------------------------------------------------------- #
# Clearance
# --------------------------------------------------------------------------- #


class ClearanceRequest(StrictRequest):
    """Sign off that the ledger is clear, with the evidence behind it."""

    evidence_reference: str = Field(min_length=1, max_length=200)


class ClearanceRead(BaseModel):
    """The clearance position, and what would have to change to grant it."""

    sale_id: uuid.UUID
    status: str | None
    blockers: list[str]
