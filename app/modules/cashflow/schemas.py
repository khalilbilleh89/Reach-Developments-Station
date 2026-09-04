"""The shape of every cashflow answer, and the basis stated with each of them.

Money and rates are ``Decimal`` end to end and leave the API as JSON strings.
Serialising a monetary amount as a JSON number hands it to a browser as a double
and 1234567.89 comes back subtly different; every figure in this module is a
string on the wire and a Decimal on both sides of it.

One rule shapes the response models more than any other: **a total without its
basis is not an answer.** Every reporting response carries the project, the
as-of date, the currency and the forecast version it was derived from, because
"unrestricted cash: 2,140,000" is a different number depending on when it was
asked and which forecast was in force, and a dashboard that omits that invites
two people to quote incompatible figures from the same screen.

The separations the brief insists on are carried in the field names rather than
in documentation. Scheduled due, forecast collection and actual receipt are
three fields and never one; total cash and usable cash are two; actual and
forecast series are labelled in words and not only by colour.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.modules.cashflow.models import (
    DEVELOPMENT_CATEGORIES,
    FINANCING_TYPES,
    FLOW_DIRECTIONS,
    FORECAST_LINE_CATEGORIES,
    FORECAST_SOURCE_KINDS,
)
from app.modules.projects.schemas import StrictRequest

DecimalStr = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]

Money = Annotated[DecimalStr, Field(ge=0, max_digits=18, decimal_places=2)]
PositiveMoney = Annotated[DecimalStr, Field(gt=0, max_digits=18, decimal_places=2)]
#: Cash positions are genuinely signed. A closing balance below zero is the
#: answer to "when do we run short?", and clamping it would delete the question.
SignedMoney = Annotated[DecimalStr, Field(max_digits=18, decimal_places=2)]
Fraction = Annotated[DecimalStr, Field(ge=0, max_digits=9, decimal_places=6)]
#: A return can be negative, and a coverage ratio can exceed one.
SignedFraction = Annotated[DecimalStr, Field(max_digits=9, decimal_places=6)]

DevelopmentCategory = Literal[DEVELOPMENT_CATEGORIES]  # type: ignore[valid-type]
FinancingType = Literal[FINANCING_TYPES]  # type: ignore[valid-type]
FlowDirection = Literal[FLOW_DIRECTIONS]  # type: ignore[valid-type]
ForecastSourceKind = Literal[FORECAST_SOURCE_KINDS]  # type: ignore[valid-type]
ForecastLineCategory = Literal[FORECAST_LINE_CATEGORIES]  # type: ignore[valid-type]


class Response(BaseModel):
    """Every response model in this module reads from ORM rows or dataclasses."""

    model_config = ConfigDict(from_attributes=True)


class ReasonRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=1000)


# --------------------------------------------------------------------------- #
# Forecast version
# --------------------------------------------------------------------------- #


class ForecastCreate(StrictRequest):
    as_of_date: date
    forecast_start_month: date
    forecast_end_month: date
    opening_unrestricted_cash: Money
    opening_restricted_cash: Money
    #: Per period, never per annum. The service does no conversion, because
    #: turning 12% a year into something monthly is a compounding assumption
    #: nobody wrote down.
    discount_rate_per_period: Fraction
    change_reason: str = Field(min_length=1, max_length=1000)
    construction_forecast_version_id: uuid.UUID | None = None
    source_version_id: uuid.UUID | None = None


class ForecastOut(Response):
    id: uuid.UUID
    version_number: int
    status: str
    currency_code: str | None
    as_of_date: date
    forecast_start_month: date
    forecast_end_month: date
    opening_unrestricted_cash: Money
    opening_restricted_cash: Money
    opening_total_cash: Money
    discount_rate_per_period: Fraction
    construction_forecast_version_id: uuid.UUID | None
    construction_forecast_version_number: int | None
    source_version_id: uuid.UUID | None
    change_reason: str
    installments_in_snapshot: int


class ForecastLineWrite(StrictRequest):
    period_month: date
    source_kind: ForecastSourceKind
    category: ForecastLineCategory
    amount: Money
    flow_direction: FlowDirection | None = None
    phase_id: uuid.UUID | None = None
    construction_cost_code_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)


class ForecastLineOut(Response):
    id: uuid.UUID
    period_month: date
    flow_direction: str
    category: str
    source_kind: str
    amount: Money
    phase_id: uuid.UUID | None
    construction_cost_code_id: uuid.UUID | None
    construction_cost_code: str | None
    note: str | None


class ScheduleSnapshotOut(Response):
    """One frozen buyer instalment. Provenance, and deliberately no buyer.

    A cash forecast needs the amount, the dates and which schedule they came
    from. It does not need who is paying, and putting a name here would widen
    the disclosure of every role that can read a cash report.
    """

    installment_id: uuid.UUID
    payment_plan_version_id: uuid.UUID
    sale_contract_id: uuid.UUID
    unit_id: uuid.UUID | None
    amount: Money
    contractual_due_date: date | None
    forecast_due_date: date | None
    actual_due_date: date | None
    chosen_forecast_date: date
    trigger_type: str
    trigger_status: str


class StalenessOut(Response):
    """Whether a forecast's frozen sources still match what governs the project."""

    is_stale: bool
    construction_is_stale: bool
    pinned_construction_version_number: int | None
    active_construction_version_number: int | None
    customer_schedule_is_stale: bool
    snapshot_plan_version_count: int
    governing_plan_version_count: int


class CheckOut(Response):
    """One reconciliation answer. No score, ever."""

    name: str
    passed: bool
    expected: SignedMoney | None
    actual: SignedMoney | None
    detail: str


class ForecastDetailOut(ForecastOut):
    lines: list[ForecastLineOut]
    customer_schedule: list[ScheduleSnapshotOut]
    staleness: StalenessOut
    construction_reconciliation: list[CheckOut]


# --------------------------------------------------------------------------- #
# Cash this module owns
# --------------------------------------------------------------------------- #


class DevelopmentMovementCreate(StrictRequest):
    category: DevelopmentCategory
    amount: PositiveMoney
    movement_date: date
    currency_id: uuid.UUID
    value_date: date | None = None
    phase_id: uuid.UUID | None = None
    counterparty_reference: str | None = Field(default=None, max_length=200)
    invoice_reference: str | None = Field(default=None, max_length=200)
    bank_reference: str | None = Field(default=None, max_length=200)
    evidence_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class DevelopmentMovementOut(Response):
    id: uuid.UUID
    movement_reference: str
    category: str
    amount: Money
    currency_code: str | None
    movement_date: date
    value_date: date | None
    phase_id: uuid.UUID | None
    status: str
    counterparty_reference: str | None
    invoice_reference: str | None
    bank_reference: str | None
    evidence_reference: str | None
    notes: str | None
    #: Stated rather than inferred from the status, because "is this cash?" is
    #: the only question a reader of a cash report is actually asking.
    counts_as_cash: bool


class FinancingMovementCreate(StrictRequest):
    movement_type: FinancingType
    amount: PositiveMoney
    movement_date: date
    currency_id: uuid.UUID
    value_date: date | None = None
    counterparty_reference: str | None = Field(default=None, max_length=200)
    facility_reference: str | None = Field(default=None, max_length=200)
    bank_reference: str | None = Field(default=None, max_length=200)
    evidence_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class FinancingMovementOut(Response):
    id: uuid.UUID
    movement_reference: str
    movement_type: str
    flow_direction: str
    amount: Money
    currency_code: str | None
    movement_date: date
    value_date: date | None
    status: str
    counterparty_reference: str | None
    facility_reference: str | None
    bank_reference: str | None
    evidence_reference: str | None
    notes: str | None
    counts_as_cash: bool


# --------------------------------------------------------------------------- #
# Restricted cash
# --------------------------------------------------------------------------- #


class RestrictionCreate(StrictRequest):
    restricted_amount: Money
    reason: str = Field(min_length=1, max_length=500)
    source_reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class ReleaseCreate(StrictRequest):
    release_date: date
    amount: PositiveMoney
    certification_reference: str | None = Field(default=None, max_length=200)
    evidence_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class ReleaseOut(Response):
    id: uuid.UUID
    restriction_id: uuid.UUID
    release_date: date
    amount: Money
    certification_reference: str | None
    evidence_reference: str | None
    status: str
    #: True only when this release is confirmed **and** the escrow it frees is
    #: still holding cash. A release against a restriction whose receipt was
    #: reversed frees nothing, whatever its own status says.
    counts_as_released: bool
    #: Whether the escrow this release belongs to currently holds anything,
    #: stated separately so a screen can say *why* a confirmed release is not
    #: counting.
    restriction_counts: bool


class RestrictionOut(Response):
    id: uuid.UUID
    receipt_id: uuid.UUID
    receipt_number: str | None
    receipt_amount: Money | None
    restricted_amount: Money
    released_amount: Money
    outstanding_restricted: Money
    reason: str
    source_reference: str | None
    status: str
    #: True only when the restriction is confirmed **and** the receipt behind it
    #: still stands. One truth across the summary, the drill-down, the register
    #: and this record: an escrow over a reversed transfer holds nothing.
    counts_as_restricted: bool
    #: Whether the transfer this escrow was taken from is still standing. False
    #: is what a reader needs to see when a confirmed restriction stops counting.
    receipt_stands: bool
    releases: list[ReleaseOut]


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


class ReportBasis(Response):
    """What every reporting response states about itself before its figures.

    Not decoration. A cash total is meaningless without the date it was taken
    at, the currency it is in and the forecast version behind its future months,
    and a screen that omits them lets two people quote incompatible numbers and
    both be right.
    """

    project_id: uuid.UUID
    as_of_date: date
    currency_code: str | None
    forecast_version_id: uuid.UUID | None
    forecast_version_number: int | None
    forecast_as_of_date: date | None
    from_month: date | None
    to_month: date | None


class MonthlyPositionOut(Response):
    period_month: date
    #: In words, never only in colour. A reader who cannot distinguish two
    #: shades still has to be able to tell what happened from what is expected —
    #: and there are three answers, not two. The month the report was taken in
    #: is ``actual_and_forecast``: cash that has moved, plus what is still
    #: expected before it ends. Labelling it "actual" would present a part month
    #: as a finished one.
    basis: Literal["actual", "actual_and_forecast", "forecast"]

    opening_total_cash: SignedMoney
    customer_scheduled_due: Money
    customer_actual_receipts: Money
    customer_forecast_receipts: Money
    financing_actual_inflows: Money
    financing_forecast_inflows: Money
    development_actual_outflows: Money
    development_forecast_outflows: Money
    construction_actual_payments: Money
    construction_forecast_payments: Money
    customer_refunds: Money
    financing_actual_outflows: Money
    financing_forecast_outflows: Money
    total_inflows: Money
    total_outflows: Money
    net_cashflow: SignedMoney
    closing_total_cash: SignedMoney

    opening_restricted_cash: Money
    newly_restricted_customer_cash: Money
    escrow_releases: Money
    closing_restricted_cash: Money

    opening_unrestricted_cash: SignedMoney
    usable_inflows: SignedMoney
    unrestricted_outflows: Money
    closing_unrestricted_cash: SignedMoney
    funding_gap: Money


class MonthlyOut(Response):
    basis: ReportBasis
    months: list[MonthlyPositionOut]


class FundingWindowOut(Response):
    """A literal date window. Thirty days is thirty days, not one month."""

    days: int
    from_date: date
    to_date: date
    #: What the project can actually spend on the day the window opens. A
    #: funding requirement stated without it is a requirement to raise money
    #: the company already has.
    opening_unrestricted_cash: SignedMoney
    usable_inflows: Money
    outflows: Money
    net_movement: SignedMoney
    #: The deepest point inside the window, not the last one. A window that
    #: closes level can still be several million short in the middle of it, and
    #: that trough is what has to be funded.
    minimum_projected_unrestricted_cash: SignedMoney
    closing_projected_unrestricted_cash: SignedMoney
    funding_requirement: Money


class PeakDeficitOut(Response):
    """Both numbers: the signed position and the amount somebody must raise."""

    minimum_unrestricted_cash: SignedMoney
    peak_funding_deficit: Money
    peak_deficit_month: date | None


class ReturnOut(Response):
    """NPV and IRR, each carrying the basis it was computed on.

    ``equity_irr_per_period`` is null wherever the series cannot answer, and
    ``equity_irr_unavailable_reason`` says which of the four reasons applies.
    Never 0%, never 999%, never NaN — each of those is a number somebody will
    put in a board pack.
    """

    npv_basis: str
    discount_rate_per_period: Fraction
    net_present_value: SignedMoney
    net_project_cashflow: SignedMoney
    equity_irr_basis: str
    equity_irr_per_period: SignedFraction | None
    equity_irr_unavailable_reason: str | None
    equity_contributed: Money
    equity_distributed: Money
    equity_net: SignedMoney


class CashPositionOut(Response):
    """Where the project's cash stands right now, on both bases."""

    total_cash: SignedMoney
    restricted_cash: Money
    unrestricted_cash: SignedMoney
    #: Null when nothing is expected to be spent. Not infinity: a screen showing
    #: ∞ has told the reader only that the denominator was empty.
    forecast_collection_coverage: SignedFraction | None
    coverage_numerator: Money
    coverage_denominator: Money


class SummaryOut(Response):
    basis: ReportBasis
    position: CashPositionOut
    peak_deficit: PeakDeficitOut
    funding_windows: list[FundingWindowOut]
    returns: ReturnOut
    has_active_forecast: bool
    staleness: StalenessOut | None


class SourceRowOut(Response):
    """One transaction behind a figure. A reference, never a copy."""

    source_type: str
    source_id: uuid.UUID
    period_month: date
    business_date: date
    amount: SignedMoney
    flow_direction: str
    category: str
    basis: str
    status: str
    display_reference: str


class DrilldownOut(Response):
    basis: ReportBasis
    total: SignedMoney
    rows: list[SourceRowOut]


class VarianceOut(Response):
    forecast_amount: Money
    actual_amount: Money
    variance_amount: SignedMoney
    #: Null where nothing was forecast. A percentage against zero is undefined,
    #: and the amount is a complete sentence without one.
    variance_rate: SignedFraction | None


class AccuracyRowOut(Response):
    period_month: date
    category_group: str
    variance: VarianceOut


class ForecastAccuracyOut(Response):
    basis: ReportBasis
    rows: list[AccuracyRowOut]


class ReconciliationOut(Response):
    basis: ReportBasis
    checks: list[CheckOut]
    failed_count: int


class ManagementMetricOut(Response):
    """One management figure, with where it came from and how to open it.

    ``source_module`` is not decoration either: it is the answer to "who owns
    this number?", and a dashboard tile whose owner cannot be named is a tile
    nobody can check.
    """

    key: str
    label: str
    value: str | None
    unit: str
    source_module: str
    drilldown_source_type: str | None


class ManagementGroupOut(Response):
    group: str
    metrics: list[ManagementMetricOut]


class ManagementOut(Response):
    basis: ReportBasis
    groups: list[ManagementGroupOut]
