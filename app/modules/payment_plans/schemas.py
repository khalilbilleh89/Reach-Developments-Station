"""Public contracts for payment plans.

Every request model refuses a key it does not declare. A misspelled
``principal_fracton`` answering 200 would report a schedule saved that was not,
and this is the register a development's receivables are read from.

Money and fractions are ``Decimal`` end to end and leave the API as JSON
strings, for the reason stated wherever money is defined in this codebase: a
JSON number is a float, and a float is not an acceptable carrier for a
contractual instalment.

No status field is writable. Submitting, approving, rejecting and activating a
schedule are four different acts with four different rights, so each has its
own route — there is no ``PATCH {"status": "active"}`` that could put a sale
under a schedule nobody sanctioned.

There is deliberately no ``paid_amount``, ``balance_due``, ``receipt_id`` or
``days_overdue`` on any model here. Those are PR-MVP-07's to define, and a
nullable column carrying one now would be read as cash truth this system cannot
yet state.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.modules.payment_plans.models import (
    ALLOCATION_MODES,
    CHARGE_ALLOCATION_MODES,
    ORIGIN_TYPES,
    RESERVATION_TREATMENTS,
    TRIGGER_EVENT_STATUSES,
    TRIGGER_STATUSES,
    TRIGGER_TYPES,
    VERSION_STATUSES,
)
from app.modules.projects.schemas import StrictRequest

DecimalStr = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]

#: ``max_digits`` mirrors the column rather than a preference: without it a
#: value like ``1e400`` passes every other rule and then overflows NUMERIC(18,2)
#: inside the transaction, reaching the caller as a 500 with nothing useful in it.
Money = Annotated[DecimalStr, Field(ge=0, max_digits=18, decimal_places=2)]
#: A share of the contract principal. Never above the whole.
Fraction = Annotated[DecimalStr, Field(ge=0, le=1, max_digits=9, decimal_places=6)]

VersionStatus = Literal[VERSION_STATUSES]  # type: ignore[valid-type]
TriggerType = Literal[TRIGGER_TYPES]  # type: ignore[valid-type]
TriggerStatus = Literal[TRIGGER_STATUSES]  # type: ignore[valid-type]
AllocationMode = Literal[ALLOCATION_MODES]  # type: ignore[valid-type]
ChargeAllocationMode = Literal[CHARGE_ALLOCATION_MODES]  # type: ignore[valid-type]
ReservationTreatment = Literal[RESERVATION_TREATMENTS]  # type: ignore[valid-type]
OriginType = Literal[ORIGIN_TYPES]  # type: ignore[valid-type]
TriggerEventStatus = Literal[TRIGGER_EVENT_STATUSES]  # type: ignore[valid-type]


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #


class PlanCreateRequest(StrictRequest):
    """Open a payment plan for a contract, with its first draft version."""

    sale_contract_id: uuid.UUID
    name: Annotated[str, Field(min_length=1, max_length=200)]
    reservation_treatment: ReservationTreatment = "reference_only"
    origin_type: OriginType = "custom"
    #: The approved, active or superseded version this schedule is copied from.
    #: Its shape travels; its amounts are re-derived against this sale.
    source_version_id: uuid.UUID | None = None
    #: The contractual date this schedule starts governing from. Omitted means
    #: today; a future date produces an approved schedule that cannot be
    #: activated until it arrives.
    effective_date: date | None = None
    notes: Annotated[str, Field(max_length=2000)] | None = None


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    sale_contract_id: uuid.UUID
    plan_number: str
    name: str
    notes: str | None
    #: When the first receipt against this plan was confirmed, or ``None``.
    #:
    #: Exposed because it changes what the plan screen may offer: once cash has
    #: arrived, the ordinary activation of a replacement schedule refuses, and a
    #: disabled button with no explanation is worse than no button. The builder
    #: reads this to say *why* — the revision has to go through a Collections
    #: restructure so the allocations are carried across.
    collections_started_at: datetime | None = None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Versions
# --------------------------------------------------------------------------- #


class VersionCreateRequest(StrictRequest):
    """Open a revision. The standing schedule keeps governing until it is replaced."""

    change_reason: Annotated[str, Field(min_length=1, max_length=500)]
    reservation_treatment: ReservationTreatment | None = None
    #: When the revised terms take effect. Omitted means today.
    effective_date: date | None = None


class VersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    payment_plan_id: uuid.UUID
    version_number: int
    status: VersionStatus
    effective_date: date

    currency_id: uuid.UUID
    contract_value_covered: DecimalStr
    tax_total_snapshot: DecimalStr
    buyer_fee_total_snapshot: DecimalStr
    total_buyer_payable_snapshot: DecimalStr

    allocation_mode: AllocationMode
    charge_allocation_mode: ChargeAllocationMode
    reservation_treatment: ReservationTreatment
    origin_type: OriginType
    source_version_id: uuid.UUID | None
    change_reason: str | None

    created_by_user_id: uuid.UUID
    created_at: datetime
    submitted_by_user_id: uuid.UUID | None
    submitted_at: datetime | None
    approved_by_user_id: uuid.UUID | None
    approved_at: datetime | None
    rejected_by_user_id: uuid.UUID | None
    rejected_at: datetime | None
    rejection_reason: str | None
    activated_by_user_id: uuid.UUID | None
    activated_at: datetime | None
    superseded_at: datetime | None


class DecisionRequest(StrictRequest):
    """Why a schedule was sanctioned or refused. Never optional."""

    reason: Annotated[str, Field(min_length=1, max_length=500)]


# --------------------------------------------------------------------------- #
# Instalments
# --------------------------------------------------------------------------- #


class InstallmentWrite(StrictRequest):
    """One row of a draft schedule.

    Exactly one of ``principal_fraction`` and ``principal_amount`` is read,
    chosen by the version's allocation mode; the other is derived by the server.
    Sending both is accepted and the unused one ignored, because a builder that
    keeps the derived value on screen should not have to strip it before saving.
    """

    sequence: Annotated[int, Field(ge=1, le=1000)]
    label: Annotated[str, Field(min_length=1, max_length=200)]
    trigger_type: TriggerType
    trigger_reference: Annotated[str, Field(max_length=200)] | None = None
    offset_days: Annotated[int, Field(ge=0, le=36500)] | None = None
    recurrence_index: Annotated[int, Field(ge=1, le=1000)] | None = None
    contractual_due_date: date | None = None
    forecast_due_date: date | None = None
    grace_days: Annotated[int, Field(ge=0, le=365)] = 0
    principal_amount: Money | None = None
    principal_fraction: Fraction | None = None
    #: Only read when the version allocates charges manually.
    tax_amount: Money | None = None
    fee_amount: Money | None = None
    owner_user_id: uuid.UUID | None = None


class ScheduleWriteRequest(StrictRequest):
    """Replace a draft version's whole schedule, atomically.

    Whole-schedule replacement rather than row-by-row editing, because adding a
    row changes what every other row is worth: six separate requests would
    leave the plan reconciling only at the end of a sequence nobody can
    guarantee completes.
    """

    allocation_mode: AllocationMode
    charge_allocation_mode: ChargeAllocationMode
    installments: Annotated[list[InstallmentWrite], Field(min_length=1, max_length=600)]


class TriggerEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    installment_id: uuid.UUID
    event_date: date
    evidence_reference: str
    reason: str
    status: TriggerEventStatus
    submitted_by_user_id: uuid.UUID
    submitted_at: datetime
    approved_by_user_id: uuid.UUID | None
    approved_at: datetime | None
    reversed_by_user_id: uuid.UUID | None
    reversed_at: datetime | None
    reversal_reason: str | None


class InstallmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_plan_version_id: uuid.UUID
    sequence: int
    label: str
    trigger_type: TriggerType
    trigger_reference: str | None
    offset_days: int | None
    recurrence_index: int | None
    #: What the contract says. Set for date-based triggers.
    contractual_due_date: date | None
    #: What somebody expects, for a contingent trigger. Never makes it due.
    forecast_due_date: date | None
    #: Set only once the trigger has genuinely occurred.
    actual_due_date: date | None
    grace_days: int
    principal_amount: DecimalStr
    principal_fraction: DecimalStr
    tax_amount: DecimalStr
    fee_amount: DecimalStr
    #: Principal + tax + fee, derived by the server.
    total_scheduled_amount: DecimalStr
    trigger_status: TriggerStatus
    owner_user_id: uuid.UUID | None
    #: Every attestation ever made about this instalment, newest first. Carried
    #: on the row rather than fetched per instalment, so an approver opening a
    #: hundred-row schedule makes one request and not a hundred.
    trigger_events: list[TriggerEventRead] = []


class ForecastRequest(StrictRequest):
    """Move a contingent instalment's expected date. Not a contractual change."""

    forecast_due_date: date | None = None
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class OwnerRequest(StrictRequest):
    """Assign who chases an instalment."""

    owner_user_id: uuid.UUID | None = None


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #


class ReconciliationRead(BaseModel):
    """What the stored schedule adds up to, against what it must cover.

    Server-derived, every field. The browser renders this and never sums a
    column itself, because two implementations of one total are one
    implementation and one defect waiting to be found by an operator.
    """

    installment_count: int

    scheduled_principal_total: DecimalStr
    contract_value_covered: DecimalStr
    principal_delta: DecimalStr

    scheduled_fraction_total: DecimalStr
    fraction_delta: DecimalStr

    scheduled_tax_total: DecimalStr
    tax_total_snapshot: DecimalStr
    tax_delta: DecimalStr

    scheduled_fee_total: DecimalStr
    buyer_fee_total_snapshot: DecimalStr
    fee_delta: DecimalStr

    scheduled_buyer_total: DecimalStr
    total_buyer_payable_snapshot: DecimalStr
    buyer_total_delta: DecimalStr

    is_reconciled: bool
    #: Said in words, so an operator is told which figure is wrong and by how
    #: much rather than that the plan is invalid.
    blocking_reasons: list[str]


class VersionDetailRead(BaseModel):
    """A version, its schedule and its reconciliation, in one response."""

    version: VersionRead
    installments: list[InstallmentRead]
    reconciliation: ReconciliationRead
    #: The soonest scheduled and forecast dates still to come on this version.
    #: Derived on the server so every surface that summarises a schedule gives
    #: the same answer, and so no screen has to decide for itself what "next"
    #: means over a list of dates that includes the past.
    next_scheduled_date: date | None
    next_forecast_date: date | None


class PlanDetailRead(BaseModel):
    """Everything a plan screen needs, without a request per instalment."""

    plan: PlanRead
    sale_id: uuid.UUID
    sale_number: str
    spa_number: str | None
    sale_status: str
    unit_id: uuid.UUID
    unit_reference: str
    client_display_name: str
    currency_id: uuid.UUID
    #: The version being worked on: the one in preparation if there is one,
    #: otherwise the standing one, otherwise the most recent history. This is
    #: the editing workspace, and it is not a claim about what governs.
    current: VersionDetailRead | None
    #: The version actually governing the sale, or nothing before the first
    #: activation. Carried in full rather than as an identifier because a
    #: revision can be in preparation for weeks while this schedule keeps
    #: falling due, and every surface that needs to say what the buyer owes
    #: needs its rows, not its id.
    active: VersionDetailRead | None
    active_version_id: uuid.UUID | None
    versions: list[VersionRead]


# --------------------------------------------------------------------------- #
# Triggers
# --------------------------------------------------------------------------- #


class SeriesPreviewRequest(StrictRequest):
    """Ask for the dates of a recurring series. Writes nothing.

    ``count`` carries a generous technical ceiling and no business limit: a
    forty-eight month plan is an ordinary commercial term, and a schema that
    stopped at six would be the six-column spreadsheet this product replaces.
    """

    frequency: Literal["recurring_monthly", "recurring_quarterly"]
    first_due_date: date
    count: Annotated[int, Field(ge=1, le=600)]
    label_prefix: Annotated[str, Field(min_length=1, max_length=120)] = "Instalment"


class SeriesRowRead(BaseModel):
    recurrence_index: int
    label: str
    due_date: date


class SeriesPreviewRead(BaseModel):
    rows: list[SeriesRowRead]


class ManualTriggerRequest(StrictRequest):
    """Attest that the event a manually triggered instalment waits on occurred."""

    event_date: date
    evidence_reference: Annotated[str, Field(min_length=1, max_length=200)]
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class ReversalRequest(StrictRequest):
    """Withdraw an attestation. The original stays on the record."""

    reason: Annotated[str, Field(min_length=1, max_length=500)]


class RefreshResultRead(BaseModel):
    """What an explicit trigger refresh resolved, and what is still waiting."""

    triggered: list[InstallmentRead]
    still_awaiting: list[InstallmentRead]


# --------------------------------------------------------------------------- #
# Register
# --------------------------------------------------------------------------- #


class RegisterRowRead(BaseModel):
    """One line of the project's payment plan register.

    Every figure here describes the version named by ``version_id`` — the one
    governing the sale where there is one, otherwise the one in preparation.
    A revision being drafted alongside appears only as ``revision_*``.

    Carries no collected, outstanding or overdue figure: those are PR-MVP-07's
    to state, and a column of zeroes labelled "paid" reads as a fact about
    money rather than the absence of one. For the same reason the forward-
    looking dates are named for the schedule rather than for collection: what
    is scheduled next, not what is owed next.
    """

    plan_id: uuid.UUID
    plan_number: str
    sale_id: uuid.UUID
    sale_number: str
    spa_number: str | None
    unit_id: uuid.UUID
    unit_reference: str
    client_display_name: str
    version_id: uuid.UUID | None
    version_number: int | None
    version_status: VersionStatus | None
    effective_date: date | None
    currency_id: uuid.UUID
    contract_value_covered: DecimalStr
    installment_count: int
    scheduled_principal_total: DecimalStr | None
    is_reconciled: bool
    #: The soonest scheduled date still to come, and the soonest forecast date
    #: still to come. Both look forward only: PR-MVP-06 cannot say whether a
    #: date already past was paid, so surfacing one would read as arrears.
    next_scheduled_date: date | None
    next_forecast_date: date | None
    awaiting_trigger_count: int
    approved_by_user_id: uuid.UUID | None
    #: The best settled version of this plan — standing, else approved, else
    #: the most recent superseded one. Named separately from the version the
    #: row describes because opening a draft revision must not withdraw the
    #: schedule the parties agreed from the list of plans worth copying.
    copy_source_version_id: uuid.UUID | None
    copy_source_version_number: int | None
    copy_source_status: VersionStatus | None
    #: A revision being prepared alongside the version this row describes.
    #: Named, not costed: it governs nothing, so it contributes no figure to
    #: the register and none of the project's operational counts.
    revision_version_id: uuid.UUID | None
    revision_version_number: int | None
    revision_status: VersionStatus | None


class PlanRegisterRead(BaseModel):
    rows: list[RegisterRowRead]
    total: int
