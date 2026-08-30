"""Public contracts for sales and legal.

Every request model refuses a key it does not declare. A misspelled
``contarct_date`` answering 200 would tell somebody a contract was dated when it
was not, and this is the register a development's revenue is read from.

Money and rates are ``Decimal`` end to end and leave the API as JSON strings. A
JSON number is a float, and a float is not an acceptable carrier for a contract
price, a buyer's share or a tax rate.

Personal data is not a field on a read model that is sometimes blank. A caller
who may not see a buyer's identity document gets a response that does not carry
the field at all — the restriction is applied before the object exists, in
``permissions.visible_party_fields``, and the two party read models below are
the shape that decision produces.

No status field is writable anywhere in this module. Every transition is a named
route with its own preconditions, so there is no ``PATCH {"status": "active"}``
that could put a unit under contract without passing them.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.modules.projects.schemas import StrictRequest
from app.modules.sales.models import (
    ADJUSTMENT_TREATMENTS,
    ADJUSTMENT_TYPES,
    CANCELLATION_INITIATORS,
    CANCELLATION_STATUSES,
    CLEARANCE_STATUSES,
    CLEARANCE_TYPES,
    EXCEPTION_STATUSES,
    GATE_STATUSES,
    HANDOVER_STATUSES,
    KYC_STATUSES,
    LEGAL_EVENT_TYPES,
    PARTY_ROLES,
    RESERVATION_STATUSES,
    SALE_STATUSES,
    WITHDRAWAL_STATUSES,
)

#: Decimals leave the API as strings, for the reason stated at the top of the
#: module and repeated wherever money is defined in this codebase.
DecimalStr = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]

# ``max_digits`` mirrors the column, not a preference: without it a value like
# ``1e400`` satisfies every other rule and then overflows NUMERIC(18,2) inside
# the transaction, which reaches the caller as a 500 with nothing useful in it.
Money = Annotated[DecimalStr, Field(ge=0, max_digits=18, decimal_places=2)]
Fraction = Annotated[DecimalStr, Field(ge=0, le=1, max_digits=9, decimal_places=6)]
#: A buyer's share. Strictly above zero: a purchaser who owns none of the unit
#: is not a purchaser.
Share = Annotated[DecimalStr, Field(gt=0, le=1, max_digits=9, decimal_places=6)]

KycStatus = Literal[KYC_STATUSES]  # type: ignore[valid-type]
PartyRole = Literal[PARTY_ROLES]  # type: ignore[valid-type]
ReservationStatus = Literal[RESERVATION_STATUSES]  # type: ignore[valid-type]
AdjustmentType = Literal[ADJUSTMENT_TYPES]  # type: ignore[valid-type]
AdjustmentTreatment = Literal[ADJUSTMENT_TREATMENTS]  # type: ignore[valid-type]
GateStatus = Literal[GATE_STATUSES]  # type: ignore[valid-type]
ExceptionStatus = Literal[EXCEPTION_STATUSES]  # type: ignore[valid-type]
SaleStatus = Literal[SALE_STATUSES]  # type: ignore[valid-type]
LegalEventType = Literal[LEGAL_EVENT_TYPES]  # type: ignore[valid-type]
CancellationInitiator = Literal[CANCELLATION_INITIATORS]  # type: ignore[valid-type]
CancellationStatus = Literal[CANCELLATION_STATUSES]  # type: ignore[valid-type]
WithdrawalStatus = Literal[WITHDRAWAL_STATUSES]  # type: ignore[valid-type]
HandoverStatus = Literal[HANDOVER_STATUSES]  # type: ignore[valid-type]
ClearanceType = Literal[CLEARANCE_TYPES]  # type: ignore[valid-type]
ClearanceStatus = Literal[CLEARANCE_STATUSES]  # type: ignore[valid-type]

#: A response built from an ORM row. Only requests are strict.
_READ = ConfigDict(from_attributes=True, extra="ignore")

Name = Annotated[str, Field(min_length=1, max_length=200)]
Code = Annotated[str, Field(min_length=1, max_length=64)]
Reference = Annotated[str, Field(min_length=1, max_length=200)]
Reason = Annotated[str, Field(min_length=1, max_length=1000)]
LongReason = Annotated[str, Field(min_length=1, max_length=2000)]
ShortReason = Annotated[str, Field(min_length=1, max_length=500)]
Notes = Annotated[str, Field(max_length=2000)]


class ReasonRequest(StrictRequest):
    """A decision that has to be explicable to whoever reads it later."""

    reason: Reason


class EvidenceRequest(StrictRequest):
    """An attestation that evidence exists, and the reference to find it by.

    Deliberately not called a payment. What this records is that a named person
    saw something; PR-MVP-07 introduces the record that says money arrived.
    """

    evidence_reference: Reference


# --------------------------------------------------------------------------- #
# Project policy
# --------------------------------------------------------------------------- #


class SalesPolicyRead(BaseModel):
    """The gates one project puts in front of title transfer and handover."""

    model_config = _READ

    project_id: uuid.UUID
    handover_requires_collection_clearance: bool
    handover_requires_legal_clearance: bool
    handover_requires_delivery_clearance: bool
    handover_requires_title_transfer: bool
    title_transfer_requires_collection_clearance: bool
    reservation_requires_deposit_confirmation: bool


class SalesPolicyWriteRequest(StrictRequest):
    """Six named booleans. Not a condition language, and never becoming one."""

    handover_requires_collection_clearance: bool
    handover_requires_legal_clearance: bool
    handover_requires_delivery_clearance: bool
    handover_requires_title_transfer: bool
    title_transfer_requires_collection_clearance: bool
    reservation_requires_deposit_confirmation: bool


# --------------------------------------------------------------------------- #
# Clients and buyer parties
# --------------------------------------------------------------------------- #


class ClientCreateRequest(StrictRequest):
    """``client_number`` is absent: the server issues it under the project lock."""

    display_name: Name
    email: Annotated[str, Field(max_length=320)] | None = None
    phone: Annotated[str, Field(max_length=64)] | None = None
    address: Annotated[str, Field(max_length=500)] | None = None
    preferred_language_code: Code | None = None
    kyc_status: KycStatus = "not_started"
    privacy_consent_at: datetime | None = None
    privacy_consent_reference: Reference | None = None
    owner_advisor_user_id: uuid.UUID | None = None
    notes: Notes | None = None


class ClientUpdateRequest(StrictRequest):
    """Correction, not replacement. ``client_number`` is not writable."""

    display_name: Name | None = None
    email: Annotated[str, Field(max_length=320)] | None = None
    phone: Annotated[str, Field(max_length=64)] | None = None
    address: Annotated[str, Field(max_length=500)] | None = None
    preferred_language_code: Code | None = None
    kyc_status: KycStatus | None = None
    privacy_consent_at: datetime | None = None
    privacy_consent_reference: Reference | None = None
    owner_advisor_user_id: uuid.UUID | None = None
    notes: Notes | None = None
    is_active: bool | None = None


class ClientSummaryRead(BaseModel):
    """A buyer without their personal data.

    What a Project Manager, Finance or an Executive Viewer legitimately needs to
    run a development: who the buyer is on the register, whether their identity
    checks are done, and which advisor owns them. No contact details, no
    address, no identity documents — those are on the full read model, and the
    route chooses between the two before serialising anything.
    """

    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    client_number: str
    display_name: str
    kyc_status: str
    preferred_language_code: str | None
    owner_advisor_user_id: uuid.UUID | None
    is_active: bool
    created_at: datetime


class ClientRead(ClientSummaryRead):
    """A buyer including their contact details, for the roles whose work needs them."""

    email: str | None
    phone: str | None
    address: str | None
    privacy_consent_at: datetime | None
    privacy_consent_reference: str | None
    notes: str | None


class PartyCreateRequest(StrictRequest):
    """One named buyer and the share they take."""

    name_as_identification: Name
    share_fraction: Share
    party_role: PartyRole = "purchaser"
    nationality_code: Code | None = None
    residency_code: Code | None = None
    tax_id: Annotated[str, Field(max_length=64)] | None = None
    identity_document_type: Code | None = None
    identity_document_number: Annotated[str, Field(max_length=64)] | None = None
    representative_name: Name | None = None
    poa_reference: Reference | None = None
    is_primary: bool = False


class PartyUpdateRequest(StrictRequest):
    """Corrects the client master. A party frozen onto a contract is untouched."""

    name_as_identification: Name | None = None
    share_fraction: Share | None = None
    party_role: PartyRole | None = None
    nationality_code: Code | None = None
    residency_code: Code | None = None
    tax_id: Annotated[str, Field(max_length=64)] | None = None
    identity_document_type: Code | None = None
    identity_document_number: Annotated[str, Field(max_length=64)] | None = None
    representative_name: Name | None = None
    poa_reference: Reference | None = None
    is_primary: bool | None = None
    is_active: bool | None = None


class PartySummaryRead(BaseModel):
    """A named buyer without their identity documents."""

    model_config = _READ

    id: uuid.UUID
    client_id: uuid.UUID
    party_role: str
    name_as_identification: str
    nationality_code: str | None
    residency_code: str | None
    share_fraction: DecimalStr
    is_primary: bool
    is_active: bool


class PartyRead(PartySummaryRead):
    """A named buyer including identity documents and power of attorney."""

    tax_id: str | None
    identity_document_type: str | None
    identity_document_number: str | None
    representative_name: str | None
    poa_reference: str | None


class ShareReconciliationRead(BaseModel):
    """Whether a client's buyers add up to a whole unit yet."""

    total_share_fraction: DecimalStr
    reconciled: bool


# --------------------------------------------------------------------------- #
# Reservations
# --------------------------------------------------------------------------- #


class ReservationCreateRequest(StrictRequest):
    """What a person chooses. Every money figure on the reservation is derived.

    There is no price field here and there never will be. The quote is produced
    by pricing from the unit's live approved price and the recorded adjustments,
    and a client that could post a net contract price would be a client that
    could sell a flat for a number nobody approved.
    """

    unit_id: uuid.UUID
    client_id: uuid.UUID
    reservation_date: date | None = None
    expires_on: date | None = None
    price_locked_until: date | None = None
    sales_channel_code: Code | None = None
    sales_branch_code: Code | None = None
    advisor_user_id: uuid.UUID | None = None
    deposit_required_amount: Money | None = None
    buyer_fee_total: Money | None = None


class ReservationUpdateRequest(StrictRequest):
    """Preparation only, and never a price. ``status`` is absent by design."""

    expires_on: date | None = None
    sales_channel_code: Code | None = None
    sales_branch_code: Code | None = None
    advisor_user_id: uuid.UUID | None = None
    deposit_required_amount: Money | None = None


class ReservationRecalculateRequest(StrictRequest):
    """Re-run the quote. Any standing exception approval is withdrawn with it."""

    buyer_fee_total: Money | None = None


class ReservationExtendRequest(StrictRequest):
    """A later expiry and the reason for it. The quote does not move."""

    expires_on: date
    reason: Reason
    effective_date: date | None = None


class ReservationActivateRequest(StrictRequest):
    """Commit the unit. Everything else about the decision is already recorded."""

    effective_date: date | None = None


class ReservationCloseRequest(StrictRequest):
    """End a reservation on a recorded reason. Nothing is deleted."""

    reason: Reason
    effective_date: date | None = None


class ExceptionDecisionRequest(StrictRequest):
    """A sanction or a refusal, and why. Both are decisions somebody signed."""

    approved: bool
    reason: Reason


class AdjustmentCreateRequest(StrictRequest):
    """One commercial input. ``treatment`` is absent: the type determines it.

    Letting a user choose whether a package is a concession or a seller cost
    would be letting them decide whether the contract price falls, which is the
    single distinction this module exists to keep.
    """

    adjustment_type: AdjustmentType
    rate_fraction: Fraction | None = None
    amount: Money | None = None
    reason: Reason | None = None


class AdjustmentUpdateRequest(StrictRequest):
    """Revise the figure. The type cannot change — that is a different decision."""

    rate_fraction: Fraction | None = None
    amount: Money | None = None
    reason: Reason | None = None


class AdjustmentRead(BaseModel):
    """One recorded commercial input and what it does to the deal."""

    model_config = _READ

    id: uuid.UUID
    reservation_id: uuid.UUID
    adjustment_type: str
    treatment: str
    rate_fraction: DecimalStr | None
    amount: DecimalStr | None
    reason: str | None
    requested_by_user_id: uuid.UUID
    created_at: datetime


class ReservationStatusEventRead(BaseModel):
    """One movement in a reservation's life. Append-only."""

    model_config = _READ

    id: uuid.UUID
    reservation_id: uuid.UUID
    from_status: str
    to_status: str
    effective_date: date
    reason: str | None
    actor_user_id: uuid.UUID
    created_at: datetime


class ReservationRead(BaseModel):
    """A reservation and the quote it froze.

    The whole waterfall is here as separate figures rather than a single total:
    somebody will be asked what the buyer was quoted, what they were given, and
    what the seller absorbed, and a response carrying only the final number
    cannot answer any of the three.
    """

    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    reservation_number: str
    unit_id: uuid.UUID
    client_id: uuid.UUID
    unit_price_version_id: uuid.UUID
    status: str
    reservation_date: date
    expires_on: date
    price_locked_until: date
    sales_channel_code: str | None
    sales_branch_code: str | None
    advisor_user_id: uuid.UUID | None

    deposit_required_amount: DecimalStr | None
    deposit_currency_id: uuid.UUID | None
    deposit_gate_status: str
    deposit_confirmation_reference: str | None
    deposit_confirmed_by_user_id: uuid.UUID | None
    deposit_confirmed_at: datetime | None
    deposit_waiver_reason: str | None

    currency_id: uuid.UUID
    reference_price_ex_tax: DecimalStr
    paid_upgrade_amount: DecimalStr
    payment_plan_adjustment_amount: DecimalStr
    gross_quoted_price_ex_tax: DecimalStr
    cash_discount_amount: DecimalStr
    seller_credit_amount: DecimalStr
    net_contract_price_ex_tax: DecimalStr
    seller_cost_total: DecimalStr
    effective_net_revenue_preview: DecimalStr
    tax_total: DecimalStr
    buyer_fee_total: DecimalStr
    total_buyer_payable: DecimalStr

    exception_approval_required: bool
    exception_approval_status: str
    exception_reason: str | None
    exception_required_role: str | None
    exception_submitted_by_user_id: uuid.UUID | None
    exception_submitted_at: datetime | None
    exception_approved_by_user_id: uuid.UUID | None
    exception_approved_at: datetime | None
    exception_decision_reason: str | None

    activated_at: datetime | None
    converted_at: datetime | None
    closed_at: datetime | None
    closure_reason: str | None
    created_at: datetime


class ReservationDetailRead(BaseModel):
    """A reservation with its inputs, its history and the whole frozen calculation."""

    reservation: ReservationRead
    adjustments: list[AdjustmentRead]
    events: list[ReservationStatusEventRead]
    quote_snapshot: dict[str, Any]
    #: True when the reservation is past its expiry and still holding the unit.
    #: Displayed as "Expired — closure required": nothing in this system expires
    #: a reservation on its own, so the state is shown and not acted on.
    closure_required: bool


# --------------------------------------------------------------------------- #
# Sale contracts
# --------------------------------------------------------------------------- #


class SaleCreateRequest(StrictRequest):
    """Draw up a contract on a live reservation, at the price it froze."""

    reservation_id: uuid.UUID
    contract_date: date | None = None
    spa_number: Code | None = None
    first_payment_required_amount: Money | None = None


class SaleUpdateRequest(StrictRequest):
    """Draft only, and never a money column. After submission this route refuses."""

    spa_number: Code | None = None
    contract_date: date | None = None
    sales_channel_code: Code | None = None
    sales_branch_code: Code | None = None
    advisor_user_id: uuid.UUID | None = None
    first_payment_required_amount: Money | None = None


class SaleSubmitRequest(StrictRequest):
    """Hand the unit's commitment from the reservation to the contract."""

    spa_number: Code | None = None
    effective_date: date | None = None


class SaleActivateRequest(StrictRequest):
    """Make the contract live, once both signatures are on the legal timeline."""

    effective_date: date | None = None


class SalePartyRead(BaseModel):
    """A buyer as the contract froze them, without identity documents."""

    model_config = _READ

    id: uuid.UUID
    sale_contract_id: uuid.UUID
    client_party_id: uuid.UUID | None
    party_role: str
    name_as_identification: str
    nationality_code: str | None
    residency_code: str | None
    share_fraction: DecimalStr


class SalePartyDetailRead(SalePartyRead):
    """A frozen buyer including identity documents and power of attorney."""

    tax_id: str | None
    identity_document_type: str | None
    identity_document_number: str | None
    representative_name: str | None
    poa_reference: str | None


class SaleTaxLineRead(BaseModel):
    """One tax line as the contract was signed under it. Immutable."""

    model_config = _READ

    id: uuid.UUID
    sale_contract_id: uuid.UUID
    tax_rule_id: uuid.UUID | None
    tax_code: str
    label: str
    rate_fraction: DecimalStr
    calculation_basis: str
    taxable_amount: DecimalStr
    tax_amount: DecimalStr
    currency_id: uuid.UUID
    valid_on: date


class SaleRead(BaseModel):
    """A contract and the commercial terms it was signed on."""

    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    sale_number: str
    spa_number: str | None
    reservation_id: uuid.UUID
    unit_id: uuid.UUID
    client_id: uuid.UUID
    unit_price_version_id: uuid.UUID
    currency_id: uuid.UUID
    contract_date: date
    status: str

    reference_price_ex_tax: DecimalStr
    gross_quoted_price_ex_tax: DecimalStr
    cash_discount_amount: DecimalStr
    seller_credit_amount: DecimalStr
    net_contract_price_ex_tax: DecimalStr
    seller_cost_total: DecimalStr
    effective_net_revenue_snapshot: DecimalStr
    tax_total: DecimalStr
    buyer_fee_total: DecimalStr
    total_contract_price: DecimalStr

    sales_channel_code: str | None
    sales_branch_code: str | None
    advisor_user_id: uuid.UUID | None

    first_payment_required_amount: DecimalStr | None
    first_payment_gate_status: str
    first_payment_evidence_reference: str | None
    first_payment_confirmed_by_user_id: uuid.UUID | None
    first_payment_confirmed_at: datetime | None
    first_payment_waiver_reason: str | None

    submitted_at: datetime | None
    submitted_by_user_id: uuid.UUID | None
    activated_at: datetime | None
    activated_by_user_id: uuid.UUID | None
    cancelled_at: datetime | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Legal timeline
# --------------------------------------------------------------------------- #


class LegalEventCreateRequest(StrictRequest):
    """One recorded legal fact. A fee here is what an authority charged.

    It is not a cash movement: PR-MVP-10 owns money leaving the company, and a
    stamp duty recorded on this timeline must never be summed into a payment
    ledger.
    """

    event_type: LegalEventType
    event_date: date
    authority_reference: Reference | None = None
    document_reference: Reference | None = None
    fee_amount: Money | None = None
    currency_id: uuid.UUID | None = None
    notes: Notes | None = None


class LegalEventReverseRequest(StrictRequest):
    """Withdraw an event by recording another that says so. No PATCH, no DELETE."""

    reason: Reason
    event_date: date | None = None


class LegalEventRead(BaseModel):
    """One entry on a contract's legal timeline, correction or original."""

    model_config = _READ

    id: uuid.UUID
    sale_contract_id: uuid.UUID
    event_type: str
    event_date: date
    authority_reference: str | None
    document_reference: str | None
    fee_amount: DecimalStr | None
    currency_id: uuid.UUID | None
    notes: str | None
    reverses_event_id: uuid.UUID | None
    reversal_reason: str | None
    entered_by_user_id: uuid.UUID
    created_at: datetime


class LegalTimelineRead(BaseModel):
    """The whole timeline, plus the reading of it the unit's status comes from."""

    events: list[LegalEventRead]
    #: The identifiers of the events that still stand — neither reversals nor
    #: reversed. Sent rather than left to the browser to work out, because a
    #: second implementation of "which events count" is a second answer.
    effective_event_ids: list[uuid.UUID]
    legal_status: str


# --------------------------------------------------------------------------- #
# Cancellation
# --------------------------------------------------------------------------- #


class CancellationCreateRequest(StrictRequest):
    """Open the controlled process that ends a contract.

    ``refund_due_amount`` is what is owed. There is deliberately no
    ``refund_paid_amount``: a refund that was actually paid is a payment
    transaction, and PR-MVP-07 owns those.
    """

    initiated_by_party: CancellationInitiator
    reason: LongReason
    initiation_date: date | None = None
    notice_date: date | None = None
    cure_deadline: date | None = None
    reason_code: Code | None = None
    forfeiture_amount: Money | None = None
    refund_due_amount: Money | None = None


class CancellationAdvanceRequest(StrictRequest):
    """One named step along. ``completed`` has its own route and its own gates."""

    to_status: CancellationStatus
    reason: Reason | None = None
    notice_date: date | None = None
    cure_deadline: date | None = None


class CancellationCompleteRequest(StrictRequest):
    """Take the unit back. It returns as ``returned``, never as ``available``."""

    unit_return_date: date | None = None


class CancellationRead(BaseModel):
    """A cancellation case and where it has got to."""

    model_config = _READ

    id: uuid.UUID
    sale_contract_id: uuid.UUID
    initiated_by_party: str
    initiation_date: date
    notice_date: date | None
    cure_deadline: date | None
    reason_code: str | None
    reason: str
    status: str
    termination_date: date | None
    forfeiture_amount: DecimalStr | None
    refund_due_amount: DecimalStr | None
    financial_approval_required: bool
    financial_approved_by_user_id: uuid.UUID | None
    financial_approved_at: datetime | None
    legal_withdrawal_required: bool
    legal_withdrawal_status: str
    unit_return_date: date | None
    remarketing_required: bool
    created_by_user_id: uuid.UUID
    created_at: datetime


# --------------------------------------------------------------------------- #
# Handover
# --------------------------------------------------------------------------- #


class HandoverCreateRequest(StrictRequest):
    """Open the operational record for giving the buyer their keys."""

    readiness_date: date | None = None
    scheduled_handover_date: date | None = None
    notes: Notes | None = None


class HandoverUpdateRequest(StrictRequest):
    """Scheduling and snagging. ``handed_over`` is refused — it has its own gates."""

    status: HandoverStatus | None = None
    readiness_date: date | None = None
    inspection_date: date | None = None
    snag_status: Code | None = None
    snag_notes: Notes | None = None
    client_notice_date: date | None = None
    scheduled_handover_date: date | None = None
    handover_date: date | None = None
    keys_reference: Reference | None = None
    meter_readings_json: dict[str, Any] | None = None
    acceptance_document_reference: Reference | None = None
    notes: Notes | None = None


class HandoverCompleteRequest(StrictRequest):
    """Hand over, once every configured clearance is in place."""

    handover_date: date | None = None
    acceptance_document_reference: Reference | None = None
    keys_reference: Reference | None = None


class ClearanceRead(BaseModel):
    """One department's answer about handing this unit over, current or historical."""

    model_config = _READ

    id: uuid.UUID
    handover_id: uuid.UUID
    clearance_type: str
    status: str
    evidence_reference: str | None
    reason: str | None
    cleared_by_user_id: uuid.UUID | None
    cleared_at: datetime | None
    revoked_by_user_id: uuid.UUID | None
    revoked_at: datetime | None
    revocation_reason: str | None
    created_at: datetime


class HandoverRead(BaseModel):
    """A handover record and its operational detail."""

    model_config = _READ

    id: uuid.UUID
    sale_contract_id: uuid.UUID
    readiness_date: date | None
    inspection_date: date | None
    snag_status: str | None
    snag_notes: str | None
    client_notice_date: date | None
    scheduled_handover_date: date | None
    handover_date: date | None
    keys_reference: str | None
    meter_readings_json: dict[str, Any] | None
    acceptance_document_reference: str | None
    notes: str | None
    status: str
    created_at: datetime


class HandoverDetailRead(BaseModel):
    """A handover, every clearance ever recorded on it, and what still blocks it."""

    handover: HandoverRead
    clearances: list[ClearanceRead]
    #: Everything standing between this handover and the buyer's keys, in plain
    #: words. Computed on the server: the browser is never told the rule and
    #: asked to reach the same conclusion.
    blockers: list[str]


# --------------------------------------------------------------------------- #
# Contract detail and the sales register
# --------------------------------------------------------------------------- #


class SaleDetailRead(BaseModel):
    """A contract with its frozen parties, taxes, legal timeline and case files."""

    sale: SaleRead
    parties: list[SalePartyRead] | list[SalePartyDetailRead]
    tax_lines: list[SaleTaxLineRead]
    legal: LegalTimelineRead
    cancellation: CancellationRead | None
    handover: HandoverDetailRead | None
    quote_snapshot: dict[str, Any]


class SalesRegisterRow(BaseModel):
    """One unit's commercial and legal position, on one line.

    Four statuses side by side and never collapsed into "sold": a unit can be
    contracted, lodged with the registry, overdue on collections and still under
    construction, and those are four teams' answers to four different questions.
    """

    unit_id: uuid.UUID
    unit_reference: str
    unit_number: str
    commercial_status: str
    legal_status: str
    delivery_status: str
    client_id: uuid.UUID | None
    client_display_name: str | None
    reservation_id: uuid.UUID | None
    reservation_number: str | None
    reservation_status: str | None
    reservation_expires_on: date | None
    closure_required: bool
    sale_id: uuid.UUID | None
    sale_number: str | None
    spa_number: str | None
    sale_status: str | None
    contract_date: date | None
    currency_id: uuid.UUID | None
    net_contract_price_ex_tax: DecimalStr | None
    cash_discount_amount: DecimalStr | None
    total_contract_price: DecimalStr | None
    sales_branch_code: str | None
    advisor_user_id: uuid.UUID | None
    #: The milestone the legal timeline is waiting for, or null when it is done
    #: or has not started. Derived on the server from the same transition map
    #: the recording route enforces, so the screen and the rule cannot diverge.
    next_legal_step: str | None
    handover_status: str | None


class SalesRegisterTotals(BaseModel):
    """Counts, and contracted value in the project's own currency.

    No conversion happens anywhere in this module. Where a project's contracts
    are denominated in more than one currency the value totals are withheld
    rather than added up, because a sum of two currencies is not a number.
    """

    units: int
    available: int
    reserved: int
    contract_pending: int
    contracted: int
    returned: int
    active_reservations: int
    active_contracts: int
    open_cancellations: int
    contracted_value: DecimalStr | None
    currency_id: uuid.UUID | None
    mixed_currency: bool


class SalesRegisterRead(BaseModel):
    """The project's sales register."""

    rows: list[SalesRegisterRow]
    totals: SalesRegisterTotals
    total: int
