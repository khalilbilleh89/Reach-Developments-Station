"""Public contracts for construction control.

Money and rates are ``Decimal`` end to end and leave the API as JSON strings,
for the reason stated wherever money is defined in this codebase: a JSON number
is a float, and a float is not an acceptable carrier for what a developer owes a
contractor.

Every request model refuses a key it does not declare. A misspelled ``ammount``
answering 200 would put a figure into an approved budget that nobody entered.

Four shapes are deliberately absent from every request model here.

**No status field is writable.** Submitting, approving, rejecting, activating,
certifying, confirming and reversing are separate acts with separate rights and
separate preconditions, so each has its own route. A ``PATCH {"status":
"certified"}`` would be somebody's signature available to whoever could reach the
endpoint.

**No derived total is writable.** Revised commitment, cumulative certified, net
due, outstanding, EAC and VAC are computed on every read. A client that could
send them could disagree with the rows they claim to summarise, and the
disagreement would be invisible.

**No cost-basis figure shares a model with a cash-basis one without saying so.**
Every response that carries both names the basis in the field group, because a
strip that puts certified work ex tax beside cash paid including tax and implies
the difference is a variance is the specific mistake this module exists to
prevent.

**Nothing writes another module's column.** There is no delivery status, no
instalment date and no cost pool in any request model here. Those belong to
inventory, payment plans and unit economics, and construction reaches them
through named service contracts or not at all.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.modules.construction.models import (
    CONTRACT_TYPES,
    COST_CATEGORIES,
    INVOICE_TYPES,
    MILESTONE_TYPES,
)
from app.modules.projects.schemas import StrictRequest

DecimalStr = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]

#: ``max_digits`` mirrors the column rather than a preference: without it a value
#: like ``1e400`` passes every other rule and then overflows NUMERIC(18,2) inside
#: the transaction, reaching the caller as a 500 with nothing useful in it.
Money = Annotated[DecimalStr, Field(ge=0, max_digits=18, decimal_places=2)]
#: A payment. Zero money does not leave a bank account.
PositiveMoney = Annotated[DecimalStr, Field(gt=0, max_digits=18, decimal_places=2)]
#: A figure that may legitimately be negative: a variation line, a variance at
#: completion, a headroom that has been exceeded.
SignedMoney = Annotated[DecimalStr, Field(max_digits=18, decimal_places=2)]
#: A fraction of one: 0.100000 means 10%. Mirrors the RATE column.
Fraction = Annotated[DecimalStr, Field(ge=0, le=1, max_digits=9, decimal_places=6)]

CostCategory = Literal[COST_CATEGORIES]  # type: ignore[valid-type]
ContractType = Literal[CONTRACT_TYPES]  # type: ignore[valid-type]
InvoiceType = Literal[INVOICE_TYPES]  # type: ignore[valid-type]
MilestoneType = Literal[MILESTONE_TYPES]  # type: ignore[valid-type]


class Response(BaseModel):
    """Every response model in this module reads from ORM rows."""

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Cost codes
# --------------------------------------------------------------------------- #


class CostCodeCreate(StrictRequest):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    cost_category: CostCategory
    package: str | None = Field(default=None, max_length=120)
    parent_cost_code_id: uuid.UUID | None = None
    phase_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CostCodeUpdate(StrictRequest):
    """``code`` and ``cost_category`` are here but the service refuses them once
    a governed record names the code — including a forecast line, because a
    forecast is what a historical estimate was about."""

    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    cost_category: CostCategory | None = None
    package: str | None = Field(default=None, max_length=120)
    parent_cost_code_id: uuid.UUID | None = None
    phase_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CostCodeRetire(StrictRequest):
    reason: str = Field(min_length=1, max_length=1000)


class CostCodeOut(Response):
    id: uuid.UUID
    code: str
    name: str
    cost_category: str
    package: str | None
    parent_cost_code_id: uuid.UUID | None
    phase_id: uuid.UUID | None
    building_id: uuid.UUID | None
    notes: str | None
    is_active: bool


# --------------------------------------------------------------------------- #
# Budget
# --------------------------------------------------------------------------- #


class BudgetCreate(StrictRequest):
    effective_date: date
    change_reason: str = Field(min_length=1, max_length=1000)
    source_version_id: uuid.UUID | None = None


class BudgetLineWrite(StrictRequest):
    cost_code_id: uuid.UUID
    approved_budget_amount: Money
    contingency_amount: Money = Decimal("0.00")
    #: Accepted only where the line does not yet exist — an opening baseline for
    #: a project that was building before this module existed. On an existing
    #: line the service refuses it, because a revision that could restate the
    #: original authorisation could make an overrun disappear.
    baseline_amount: Money | None = None
    funding_source: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)


class ReasonRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=1000)


class BudgetLineOut(Response):
    cost_code_id: uuid.UUID
    cost_code: str
    cost_code_name: str
    cost_category: str
    baseline_amount: Money
    approved_budget_amount: Money
    contingency_amount: Money
    #: Derived: approved plus contingency. Never a stored fourth amount.
    control_budget: Money
    #: What this code has committed, from contracts and approved variations.
    revised_commitment: SignedMoney
    #: Control budget less commitment. Negative where the code is over.
    headroom: SignedMoney
    funding_source: str | None
    notes: str | None


class BudgetOut(Response):
    id: uuid.UUID
    version_number: int
    status: str
    effective_date: date
    change_reason: str
    source_version_id: uuid.UUID | None
    currency_code: str | None
    created_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    activated_at: datetime | None
    superseded_at: datetime | None


class BudgetDetailOut(BudgetOut):
    lines: list[BudgetLineOut]
    total_baseline: Money
    total_approved_budget: Money
    total_contingency: Money
    total_control_budget: Money


# --------------------------------------------------------------------------- #
# Contracts
# --------------------------------------------------------------------------- #


class ContractCreate(StrictRequest):
    contract_number: str = Field(min_length=1, max_length=64)
    contract_type: ContractType
    vendor_name: str = Field(min_length=1, max_length=200)
    original_contract_value_ex_tax: Money
    currency_id: uuid.UUID
    advance_entitlement_amount: Money = Decimal("0.00")
    retention_rate_fraction: Fraction = Decimal("0.000000")
    tax_rate_fraction: Fraction | None = None
    vendor_registration_reference: str | None = Field(default=None, max_length=120)
    vendor_tax_reference: str | None = Field(default=None, max_length=120)
    vendor_contact_reference: str | None = Field(default=None, max_length=200)
    payment_terms: str | None = Field(default=None, max_length=500)
    planned_start_date: date | None = None
    planned_completion_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ContractLineWrite(StrictRequest):
    sequence: int = Field(ge=1)
    description: str = Field(min_length=1, max_length=500)
    cost_code_id: uuid.UUID
    original_amount_ex_tax: Money
    notes: str | None = Field(default=None, max_length=2000)


class ContractLineOut(Response):
    id: uuid.UUID
    sequence: int
    description: str
    cost_code_id: uuid.UUID
    cost_code: str
    original_amount_ex_tax: Money
    #: This line's cost code as it now stands, original plus approved changes.
    revised_commitment: SignedMoney
    certified_to_date: Money
    notes: str | None


class ContractOut(Response):
    id: uuid.UUID
    contract_number: str
    contract_type: str
    vendor_name: str
    status: str
    currency_code: str | None
    original_contract_value_ex_tax: Money
    approved_variation_delta: SignedMoney
    #: Derived on every read. There is no revised value column, so a terminated
    #: contract still carries what it committed.
    revised_commitment: SignedMoney
    certified_to_date: Money
    advance_entitlement_amount: Money
    retention_rate_fraction: Fraction
    planned_start_date: date | None
    planned_completion_date: date | None
    actual_start_date: date | None
    actual_completion_date: date | None


class ContractDetailOut(ContractOut):
    """The contract file: one record, on both bases, each labelled."""

    vendor_registration_reference: str | None
    vendor_tax_reference: str | None
    vendor_contact_reference: str | None
    payment_terms: str | None
    tax_rate_fraction: Fraction | None
    notes: str | None
    lines: list[ContractLineOut]
    # Cash basis. Never added to the figures above.
    approved_invoice_payable: Money
    disputed_invoice_payable: Money
    confirmed_paid: Money
    invoice_outstanding: SignedMoney
    retention_held: Money
    retention_released: Money
    retention_outstanding: Money
    advance_paid: Money
    advance_recovered: Money
    advance_outstanding: SignedMoney


# --------------------------------------------------------------------------- #
# Variations
# --------------------------------------------------------------------------- #


class VariationCreate(StrictRequest):
    variation_number: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1000)
    requested_date: date
    instruction_reference: str | None = Field(default=None, max_length=200)
    cause: str | None = Field(default=None, max_length=1000)
    #: Signed: +14 extends the contract's duration, -7 accelerates it. Recorded
    #: because it was agreed; it moves no date on its own.
    time_impact_days: int = 0
    funding_source: str | None = Field(default=None, max_length=120)


class VariationLineWrite(StrictRequest):
    sequence: int = Field(ge=1)
    cost_code_id: uuid.UUID
    description: str = Field(min_length=1, max_length=500)
    #: Signed and non-zero. An omission is a negative line, not a second record
    #: type, so every total over the table reads one way.
    value_delta_ex_tax: SignedMoney


class VariationLineOut(Response):
    id: uuid.UUID
    sequence: int
    cost_code_id: uuid.UUID
    cost_code: str
    description: str
    value_delta_ex_tax: SignedMoney


class VariationOut(Response):
    id: uuid.UUID
    contract_id: uuid.UUID
    contract_number: str
    variation_number: str
    description: str
    cause: str | None
    instruction_reference: str | None
    requested_date: date
    time_impact_days: int
    funding_source: str | None
    status: str
    total_value_ex_tax: SignedMoney
    #: Whether an Approver / CFO is required, decided on the server from the
    #: country pack's review amount against the absolute value of the change.
    #: Returned so the browser can state the rule rather than re-derive it — a
    #: threshold recomputed on the client can disagree with the one enforced.
    requires_escalation: bool
    review_amount: Money | None
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    withdrawn_at: datetime | None
    withdrawal_reason: str | None


class VariationDetailOut(VariationOut):
    lines: list[VariationLineOut]


# --------------------------------------------------------------------------- #
# Certificates
# --------------------------------------------------------------------------- #


class CertificateCreate(StrictRequest):
    certificate_number: str = Field(min_length=1, max_length=64)
    period_start: date
    period_end: date
    certificate_date: date
    retention_release_amount: Money = Decimal("0.00")
    advance_recovery_amount: Money = Decimal("0.00")
    other_deductions_amount: Money = Decimal("0.00")
    #: Stated, not derived. Nothing here reads a country pack's sales tax: those
    #: rules answer what a buyer pays, and applying them to a vendor valuation
    #: would invent a liability nobody agreed.
    tax_amount: Money = Decimal("0.00")
    certifier_name: str | None = Field(default=None, max_length=200)
    evidence_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class CertificateLineWrite(StrictRequest):
    cost_code_id: uuid.UUID
    current_work_value_ex_tax: Money
    notes: str | None = Field(default=None, max_length=2000)


class CertificateLineOut(Response):
    cost_code_id: uuid.UUID
    cost_code: str
    current_work_value_ex_tax: Money
    #: Everything certified on this contract and code before this certificate.
    previously_certified: Money
    cumulative_certified: Money
    #: What the contract and its approved variations commit for this code.
    revised_commitment: SignedMoney
    notes: str | None


class CertificateOut(Response):
    id: uuid.UUID
    contract_id: uuid.UUID
    contract_number: str
    certificate_number: str
    period_start: date
    period_end: date
    certificate_date: date
    status: str
    certifier_name: str | None
    evidence_reference: str | None
    # The waterfall, in the one order a payment certificate has. Every figure
    # server-derived; the browser renders it and calculates nothing.
    current_work_value_ex_tax: Money
    tax_amount: Money
    retention_release_amount: Money
    retention_held_amount: Money
    advance_recovery_amount: Money
    other_deductions_amount: Money
    net_due: SignedMoney
    #: What of this certificate's authorisation is not yet claimed by an invoice.
    uninvoiced_net_due: SignedMoney
    certified_at: datetime | None
    rejection_reason: str | None
    reversal_reason: str | None


class CertificateDetailOut(CertificateOut):
    lines: list[CertificateLineOut]


# --------------------------------------------------------------------------- #
# Invoices and payments
# --------------------------------------------------------------------------- #


class InvoiceRecord(StrictRequest):
    invoice_number: str = Field(min_length=1, max_length=64)
    invoice_type: InvoiceType
    invoice_date: date
    amount_ex_tax: Money
    tax_amount: Money = Decimal("0.00")
    #: Required for everything but an advance. An invoice type with no ceiling
    #: is a way to approve a liability nothing authorised.
    certificate_id: uuid.UUID | None = None
    due_date: date | None = None
    accounting_reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)


class InvoiceOut(Response):
    id: uuid.UUID
    contract_id: uuid.UUID
    contract_number: str
    certificate_id: uuid.UUID | None
    invoice_number: str
    invoice_type: str
    invoice_date: date
    due_date: date | None
    status: str
    amount_ex_tax: Money
    tax_amount: Money
    net_payable: Money
    allocated: Money
    outstanding: SignedMoney
    dispute_reason: str | None
    void_reason: str | None
    approved_at: datetime | None


class PaymentRecord(StrictRequest):
    payment_reference: str = Field(min_length=1, max_length=64)
    payment_date: date
    amount: PositiveMoney
    currency_id: uuid.UUID
    value_date: date | None = None
    bank_reference: str | None = Field(default=None, max_length=200)
    proof_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class AllocationWrite(StrictRequest):
    invoice_id: uuid.UUID
    amount: PositiveMoney


class AllocationOut(Response):
    invoice_id: uuid.UUID
    invoice_number: str
    amount: Money


class PaymentOut(Response):
    id: uuid.UUID
    contract_id: uuid.UUID
    contract_number: str
    payment_reference: str
    payment_date: date
    value_date: date | None
    amount: Money
    status: str
    currency_code: str | None
    bank_reference: str | None
    proof_reference: str | None
    #: What of this payment names an obligation. Confirmation refuses until it
    #: equals the amount exactly: cash leaving with nothing named is a
    #: disbursement nobody can explain.
    allocated: Money
    unallocated: SignedMoney
    confirmed_at: datetime | None
    reversed_at: datetime | None
    reversal_reason: str | None
    allocations: list[AllocationOut]


# --------------------------------------------------------------------------- #
# Milestones
# --------------------------------------------------------------------------- #


class MilestoneCreate(StrictRequest):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    milestone_type: MilestoneType
    phase_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    planned_date: date | None = None
    forecast_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class MilestoneUpdate(StrictRequest):
    """``code`` is absent on purpose: a payment plan points at it by that code,
    and renaming it would detach a live schedule from its trigger."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    milestone_type: MilestoneType | None = None
    phase_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    planned_date: date | None = None
    forecast_date: date | None = None
    progress_fraction: Fraction | None = None
    notes: str | None = Field(default=None, max_length=2000)


class MilestoneAchieve(StrictRequest):
    """Site reporting work done. This triggers nothing."""

    achieved_date: date
    evidence_reference: str | None = Field(default=None, max_length=500)


class MilestoneCertify(StrictRequest):
    """Formal certification. This is what makes a buyer's instalment due."""

    certified_date: date
    evidence_reference: str | None = Field(default=None, max_length=500)
    linked_certificate_id: uuid.UUID | None = None


class MilestoneOut(Response):
    id: uuid.UUID
    code: str
    name: str
    milestone_type: str
    phase_id: uuid.UUID | None
    building_id: uuid.UUID | None
    scope_label: str | None
    planned_date: date | None
    forecast_date: date | None
    actual_achieved_date: date | None
    certified_date: date | None
    progress_fraction: Fraction
    status: str
    #: Derived server-side from one stated precedence. Never computed in the
    #: browser, so every screen says the same number.
    delay_days: int | None
    evidence_reference: str | None
    linked_certificate_id: uuid.UUID | None
    depends_on: list[uuid.UUID]


class MilestoneCertifiedOut(Response):
    """What a certification did, including to the schedules waiting on it."""

    milestone: MilestoneOut
    triggered_installment_count: int
    triggered_plan_count: int


class MilestoneTriggerOption(Response):
    """What a payment plan builder may see, and nothing more.

    Sales Operations writes payment plans and cannot read this module. So this
    model carries a code, a name, a scope and dates — no budget, no contract
    value, no estimate at completion, no margin, no cost of any kind.
    """

    code: str
    name: str
    scope_label: str | None
    planned_date: date | None
    forecast_date: date | None
    is_certified: bool
    certified_date: date | None


class DependencyWrite(StrictRequest):
    depends_on_milestone_id: uuid.UUID


# --------------------------------------------------------------------------- #
# Forecast
# --------------------------------------------------------------------------- #


class ForecastCreate(StrictRequest):
    as_of_date: date
    change_reason: str = Field(min_length=1, max_length=1000)
    budget_version_id: uuid.UUID | None = None
    source_version_id: uuid.UUID | None = None


class ForecastLineWrite(StrictRequest):
    cost_code_id: uuid.UUID
    #: Finance's explicit judgement of what is left to spend. Never derived as
    #: budget minus certified: a forecast that cannot disagree with the budget
    #: cannot warn anybody about it.
    forecast_remaining_amount_ex_tax: Money
    note: str | None = Field(default=None, max_length=2000)


class ForecastLineOut(Response):
    cost_code_id: uuid.UUID
    cost_code: str
    cost_code_name: str
    control_budget: Money
    revised_commitment: SignedMoney
    #: Certified as at the forecast's own cutoff, not as at today. This is what
    #: makes a superseded forecast still reproducible.
    certified_to_date: Money
    forecast_remaining_amount_ex_tax: Money
    estimate_at_completion: Money
    variance_at_completion: SignedMoney
    #: Reported, never corrected. Either the forecast is wrong or a contract
    #: reduction is expected, and only Finance can say which.
    forecast_below_commitment: bool
    uncovered_commitment: Money
    note: str | None


class ForecastOut(Response):
    id: uuid.UUID
    version_number: int
    status: str
    as_of_date: date
    budget_version_id: uuid.UUID
    budget_version_number: int | None
    change_reason: str
    source_version_id: uuid.UUID | None
    currency_code: str | None
    created_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    activated_at: datetime | None
    superseded_at: datetime | None


class ForecastDetailOut(ForecastOut):
    lines: list[ForecastLineOut]
    total_control_budget: Money
    total_certified: Money
    total_forecast_remaining: Money
    total_estimate_at_completion: Money
    total_variance_at_completion: SignedMoney


# --------------------------------------------------------------------------- #
# Summary and reconciliation
# --------------------------------------------------------------------------- #


class CostControlPosition(Response):
    """The cost side. Every figure here is **ex tax**, without exception."""

    original_baseline: Money
    current_approved_budget: Money
    approved_contingency: Money
    control_budget: Money
    original_commitment: Money
    approved_variation_delta: SignedMoney
    revised_commitment: SignedMoney
    certified_to_date: Money
    forecast_remaining: Money | None
    estimate_at_completion: Money | None
    variance_at_completion: SignedMoney | None


class PayablePosition(Response):
    """The cash side. These carry tax, retention and deductions.

    Kept in its own model so no response can put a figure from here beside one
    from :class:`CostControlPosition` without the basis being visible. The
    difference between the two is not a variance and must never be presented as
    one.
    """

    approved_invoice_payable: Money
    disputed_invoice_payable: Money
    confirmed_paid: Money
    invoice_outstanding: SignedMoney
    retention_outstanding: Money
    advance_paid: Money
    advance_recovered: Money
    advance_outstanding: SignedMoney


class ConstructionControls(Response):
    """Counts a screen may act on, each from a stored fact."""

    open_variations: int
    escalated_variations: int
    over_budget_cost_codes: int
    forecast_below_commitment_cost_codes: int
    late_milestones: int
    achieved_uncertified_milestones: int
    overdue_approved_invoices: int
    has_active_budget: bool
    has_active_forecast: bool


class ConstructionSummaryOut(Response):
    currency_code: str | None
    budget_version_number: int | None
    forecast_version_number: int | None
    forecast_as_of: date | None
    cost_control: CostControlPosition
    payable: PayablePosition
    controls: ConstructionControls


class ReconciliationCheckOut(Response):
    key: str
    label: str
    ok: bool
    amount: SignedMoney | None
    expected: SignedMoney | None
    variance: SignedMoney | None
    detail: str | None


class ReconciliationOut(Response):
    """Explicit checks, and no overall score.

    A health percentage over a set of pass/fail questions is a number that
    cannot be acted on: it tells a reader something is wrong without saying
    what, and it goes green while one check is still failing.
    """

    ok: bool
    checks: list[ReconciliationCheckOut]


# --------------------------------------------------------------------------- #
# Delivery
# --------------------------------------------------------------------------- #


class DeliveryAction(StrictRequest):
    """Move units through the build states construction owns.

    Exactly one scope is named. The states available are construction's own —
    handover belongs to sales, and this request cannot express one.
    """

    unit_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    phase_id: uuid.UUID | None = None
    effective_date: date
    reason: str | None = Field(default=None, max_length=1000)


class DeliveryResultOut(Response):
    """What a delivery action did, all of it or none of it."""

    to_status: str
    unit_count: int
    unit_ids: list[uuid.UUID]
