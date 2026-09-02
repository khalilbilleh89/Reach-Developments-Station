"""Public contracts for unit economics.

Money, rates and areas are ``Decimal`` end to end and leave the API as JSON
strings, for the reason stated wherever money is defined in this codebase: a
JSON number is a float, and a float is not an acceptable carrier for a
developer's margin.

Every request model refuses a key it does not declare. A misspelled ``ammount``
answering 200 would put a cost pool in an approved basis that nobody entered.

Two shapes are deliberately absent from every request model here.

**No profit, margin or cost total is writable.** They are derived server-side on
every read. A client that could send them could disagree with the allocation
they claim to summarise, and the disagreement would be invisible.

**No status field is writable.** Submitting, approving, rejecting and activating
a cost basis are four acts with four different rights and four sets of
preconditions, so each has its own route. A ``PATCH {"status": "approved"}``
would be a second person's signature available to whoever could reach the
endpoint.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.modules.projects.schemas import StrictRequest
from app.modules.unit_economics.models import (
    ALLOCATION_METHODS,
    COST_BASES,
    ECONOMIC_BASES,
    FINANCE_TREATMENTS,
    POOL_CATEGORIES,
    POOL_SCOPES,
    POOL_SOURCE_KINDS,
    PROFITABILITY_STATUSES,
    REVENUE_SOURCES,
    UNIT_COST_STATUSES,
    UNIT_COST_TYPES,
    VERSION_STATUSES,
)

DecimalStr = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]

#: ``max_digits`` mirrors the column rather than a preference: without it a value
#: like ``1e400`` passes every other rule and then overflows NUMERIC(18,2) inside
#: the transaction, reaching the caller as a 500 with nothing useful in it.
Money = Annotated[DecimalStr, Field(ge=0, max_digits=18, decimal_places=2)]
#: A cost actually incurred. Zero is not a cost.
PositiveMoney = Annotated[DecimalStr, Field(gt=0, max_digits=18, decimal_places=2)]
#: Profit is money that may legitimately be negative. A loss is a fact.
SignedMoney = Annotated[DecimalStr, Field(max_digits=18, decimal_places=2)]
#: A fraction of one: 0.184000 means 18.4%. Signed, because margins go negative.
#: Mirrors the RATE column, and is used only where the value came from one.
Fraction = Annotated[DecimalStr, Field(max_digits=9, decimal_places=6)]
#: A ratio computed at read time and stored nowhere — margin, return on cost.
#: Deliberately *not* the RATE column's bound: nothing here is going into that
#: column, and three integer digits is a limit these can genuinely exceed. A
#: cost basis holding a placeholder amount produces a return on cost in the
#: thousands, which is a number worth showing somebody; answering it with a 500
#: because the response model would not carry it is the worst of both.
DerivedRatio = Annotated[DecimalStr, Field(max_digits=18, decimal_places=6)]
#: A driver value: an area, a count, a revenue or a surveyor's factor.
Driver = Annotated[DecimalStr, Field(ge=0, max_digits=18, decimal_places=4)]

VersionStatus = Literal[VERSION_STATUSES]  # type: ignore[valid-type]
FinanceTreatment = Literal[FINANCE_TREATMENTS]  # type: ignore[valid-type]
PoolCategory = Literal[POOL_CATEGORIES]  # type: ignore[valid-type]
PoolSourceKind = Literal[POOL_SOURCE_KINDS]  # type: ignore[valid-type]
PoolScope = Literal[POOL_SCOPES]  # type: ignore[valid-type]
AllocationMethod = Literal[ALLOCATION_METHODS]  # type: ignore[valid-type]
UnitCostType = Literal[UNIT_COST_TYPES]  # type: ignore[valid-type]
CostBasis = Literal[COST_BASES]  # type: ignore[valid-type]
UnitCostStatus = Literal[UNIT_COST_STATUSES]  # type: ignore[valid-type]
ProfitabilityStatus = Literal[PROFITABILITY_STATUSES]  # type: ignore[valid-type]
RevenueSource = Literal[REVENUE_SOURCES]  # type: ignore[valid-type]
EconomicBasis = Literal[ECONOMIC_BASES]  # type: ignore[valid-type]


# --------------------------------------------------------------------------- #
# Allocation versions
# --------------------------------------------------------------------------- #


class VersionCreate(StrictRequest):
    """Open a draft cost basis.

    No currency: it is the project's base currency and is not a choice. A
    project accounts in one currency, and allocating its cost in another would
    need an exchange rate this platform deliberately does not have.
    """

    effective_from: date
    change_reason: str = Field(min_length=1, max_length=1000)
    finance_treatment: FinanceTreatment = "excluded"


class VersionClone(StrictRequest):
    """Copy an existing basis into a new draft, to be recalculated."""

    effective_from: date
    change_reason: str = Field(min_length=1, max_length=1000)


class VersionDecision(StrictRequest):
    """Approve or reject a submitted basis. A rejection must say why."""

    reason: str | None = Field(default=None, max_length=1000)


class VersionRejection(StrictRequest):
    """Refuse a submitted basis."""

    reason: str = Field(min_length=1, max_length=1000)


class AllocationVersionRead(BaseModel):
    """One governed cost basis, as the API reports it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    version_number: int
    currency_id: uuid.UUID
    status: VersionStatus
    finance_treatment: FinanceTreatment
    effective_from: date
    effective_to: date | None
    change_reason: str
    source_version_id: uuid.UUID | None
    calculated_at: datetime | None
    created_at: datetime
    created_by_user_id: uuid.UUID
    submitted_at: datetime | None
    submitted_by_user_id: uuid.UUID | None
    approved_at: datetime | None
    approved_by_user_id: uuid.UUID | None
    rejected_at: datetime | None
    rejected_by_user_id: uuid.UUID | None
    rejection_reason: str | None
    activated_at: datetime | None
    activated_by_user_id: uuid.UUID | None
    superseded_at: datetime | None


# --------------------------------------------------------------------------- #
# Cost pools
# --------------------------------------------------------------------------- #


class PoolCreate(StrictRequest):
    """Add one shared cost to a draft basis.

    ``amount`` is absent for a land pool sourced from the land register: that
    total is derived from the parcels and re-derived at activation, so typing it
    here would create a second land cost that could disagree with the first.
    """

    pool_number: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    category: PoolCategory
    source_kind: PoolSourceKind = "manual"
    amount: Money | None = None
    scope_kind: PoolScope = "project"
    phase_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    allocation_method: AllocationMethod
    area_type_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class PoolUpdate(StrictRequest):
    """Change one draft pool. Absent keys are left alone."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    amount: Money | None = None
    scope_kind: PoolScope | None = None
    phase_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    allocation_method: AllocationMethod | None = None
    area_type_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class DriverEntry(StrictRequest):
    """One unit's driver value for a custom-driver pool."""

    unit_id: uuid.UUID
    driver_value: Driver


class DriverSet(StrictRequest):
    """Every driver value for one custom-driver pool, in one request."""

    drivers: list[DriverEntry] = Field(min_length=1)


class CostPoolRead(BaseModel):
    """One shared cost, and the rule for dividing it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    allocation_version_id: uuid.UUID
    pool_number: str
    name: str
    category: PoolCategory
    source_kind: PoolSourceKind
    amount: Money
    scope_kind: PoolScope
    phase_id: uuid.UUID | None
    building_id: uuid.UUID | None
    allocation_method: AllocationMethod
    area_type_id: uuid.UUID | None
    notes: str | None


class AllocationRead(BaseModel):
    """One unit's share of one pool, with the evidence behind it."""

    model_config = ConfigDict(from_attributes=True)

    unit_id: uuid.UUID
    unit_reference: str
    driver_value: Driver
    driver_share: Fraction
    allocated_amount: Money
    source_area_schedule_id: uuid.UUID | None
    source_price_version_id: uuid.UUID | None
    is_rounding_recipient: bool


class PoolAllocationSummary(BaseModel):
    """What one pool's division came to, and whether it reconciles."""

    pool_id: uuid.UUID
    pool_number: str
    name: str
    category: PoolCategory
    allocation_method: AllocationMethod
    scope_kind: PoolScope
    pool_amount: Money
    eligible_units: int
    driver_total: Driver
    allocated_total: Money
    variance: SignedMoney


class CalculationPreview(BaseModel):
    """Everything Finance needs to see before signing a cost basis.

    Pool by pool, with the driver total, the allocated total and the variance —
    because approving a total nobody can decompose is approving a black box, and
    the whole point of this module is that a margin can be taken apart.
    """

    version: AllocationVersionRead
    pools: list[PoolAllocationSummary]
    source_cost_total: Money
    allocated_cost_total: Money
    variance: SignedMoney
    reconciled: bool
    stale_sources: list[str]


class ReconciliationRead(BaseModel):
    """Whether every pool in a version still equals the sum of its allocations."""

    reconciled: bool
    source_cost_total: Money
    allocated_cost_total: Money
    variance: SignedMoney
    pool_count: int
    allocation_count: int
    unreconciled_pools: list[str]


class VersionDetail(BaseModel):
    """One version with its pools and its reconciliation."""

    version: AllocationVersionRead
    pools: list[CostPoolRead]
    reconciliation: ReconciliationRead
    stale_sources: list[str]


# --------------------------------------------------------------------------- #
# Unit costs
# --------------------------------------------------------------------------- #


class UnitCostCreate(StrictRequest):
    """Record a cost attributable to one unit.

    ``cost_type`` decides whether this lands above or below gross profit. There
    is deliberately no field for that: letting a user choose both the type and
    its economic treatment would let them choose which margin it reduces.
    """

    cost_type: UnitCostType
    basis: CostBasis
    amount: PositiveMoney
    effective_date: date
    sale_contract_id: uuid.UUID | None = None
    reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class UnitCostReversal(StrictRequest):
    """Undo a recorded cost. The row stays; the reason is mandatory."""

    reason: str = Field(min_length=1, max_length=1000)


class UnitCostRead(BaseModel):
    """One recorded unit cost."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    unit_id: uuid.UUID
    sale_contract_id: uuid.UUID | None
    currency_id: uuid.UUID
    cost_type: UnitCostType
    cost_class: str
    basis: CostBasis
    amount: Money
    effective_date: date
    reference: str | None
    notes: str | None
    status: UnitCostStatus
    created_at: datetime
    reversed_at: datetime | None
    reversal_reason: str | None


# --------------------------------------------------------------------------- #
# Economics
# --------------------------------------------------------------------------- #


class WaterfallStep(BaseModel):
    """One labelled line of the cost waterfall, in the order it is subtracted."""

    key: str
    label: str
    amount: SignedMoney
    is_subtotal: bool


class UnitEconomicsRead(BaseModel):
    """One unit's whole economic position.

    Every figure is computed server-side. Nothing here is stored, and nothing
    here is recomputed in the browser: two implementations of a margin are two
    answers waiting to disagree in front of a finance director.
    """

    unit_id: uuid.UUID
    unit_reference: str
    unit_number: str
    commercial_status: str
    basis: EconomicBasis
    revenue_source: RevenueSource | None
    revenue_source_id: uuid.UUID | None
    revenue_currency_id: uuid.UUID | None
    cost_currency_id: uuid.UUID

    allocation_version_id: uuid.UUID | None
    allocation_version_number: int | None
    allocation_effective_from: date | None

    land_cost: Money
    hard_cost: Money
    soft_cost: Money
    direct_cost: Money
    variable_selling_cost: Money
    seller_cost: Money
    allocated_finance_cost: Money
    deal_finance_cost: Money

    revenue: Money | None
    development_cost: Money | None
    commercial_cost: Money | None
    finance_cost: Money | None
    total_cost: Money | None
    gross_profit: SignedMoney | None
    gross_margin_fraction: DerivedRatio | None
    contribution_profit: SignedMoney | None
    contribution_margin_fraction: DerivedRatio | None
    profit_after_finance: SignedMoney | None
    margin_fraction: DerivedRatio | None
    return_on_cost_fraction: DerivedRatio | None

    profitability_status: ProfitabilityStatus
    below_margin_threshold: bool | None
    threshold_fraction: Fraction | None


class UnitEconomicsDetail(BaseModel):
    """One unit's economics with its waterfall and its recorded unit costs."""

    economics: UnitEconomicsRead
    waterfall: list[WaterfallStep]
    unit_costs: list[UnitCostRead]


class ProjectEconomicsRead(BaseModel):
    """The project's current blended position.

    Ratios are weighted — total profit over total revenue — never the average of
    the unit ratios. The two are different numbers, and only the first is the
    developer's margin.

    ``currency_mismatch_count`` is reported rather than silently dropped. A
    summary that quietly excluded units would be a summary of an unstated
    subset, which is the failure this platform refuses everywhere money is
    added up.
    """

    currency_id: uuid.UUID
    unit_count: int
    comparable_unit_count: int
    sold_count: int
    unsold_count: int
    negative_profit_count: int
    below_threshold_count: int
    incomplete_count: int
    currency_mismatch_count: int
    threshold_fraction: Fraction | None

    revenue_total: Money
    development_cost_total: Money
    commercial_cost_total: Money
    finance_cost_total: Money
    total_cost_total: Money
    gross_profit_total: SignedMoney
    contribution_profit_total: SignedMoney
    profit_total: SignedMoney
    margin_fraction: DerivedRatio | None
    return_on_cost_fraction: DerivedRatio | None

    active_version: AllocationVersionRead | None
