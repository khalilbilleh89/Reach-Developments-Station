"""Public contracts for pricing.

Every request model refuses a key it does not declare. A misspelled
``curreny_id`` answering 200 would tell somebody a price changed when it did
not, and for the register a development sells from that is the wrong default by
a wide margin.

Money, rates and areas are ``Decimal`` end to end and leave the API as JSON
strings. A JSON number is a float, and a float is not an acceptable carrier for
a price, a discount fraction or the area a price was computed from.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.modules.pricing.models import (
    ADJUSTMENT_METHODS,
    AREA_PRICING_METHODS,
    BENCHMARK_AREA_BASES,
    COMPONENT_TYPES,
    ELIGIBLE_BASES,
    ESCALATION_SCOPES,
    ESCALATION_TRIGGERS,
    MARKET_FLAGS,
    PREMIUM_METHODS,
    PREMIUM_SOURCE_KINDS,
    PRICING_STATUSES,
    STACKING_METHODS,
    TAX_TREATMENTS,
)
from app.modules.projects.schemas import StrictRequest

#: Decimals leave the API as strings, for the reason stated at the top of the
#: module and repeated wherever money is defined in this codebase.
DecimalStr = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]

# ``max_digits`` mirrors the column, not a preference. Without it a value like
# ``1e400`` satisfies every other rule and then overflows NUMERIC(18,2) inside
# the transaction, which reaches the caller as a 500 with nothing useful in it.
Money = Annotated[DecimalStr, Field(ge=0, max_digits=18, decimal_places=2)]
SignedMoney = Annotated[DecimalStr, Field(max_digits=18, decimal_places=2)]
Measure = Annotated[DecimalStr, Field(ge=0, max_digits=18, decimal_places=4)]
Fraction = Annotated[DecimalStr, Field(ge=0, le=1, max_digits=9, decimal_places=6)]
SignedFraction = Annotated[DecimalStr, Field(ge=-1, le=1, max_digits=9, decimal_places=6)]

PricingStatus = Literal[PRICING_STATUSES]  # type: ignore[valid-type]
AreaPricingMethod = Literal[AREA_PRICING_METHODS]  # type: ignore[valid-type]
PremiumSourceKind = Literal[PREMIUM_SOURCE_KINDS]  # type: ignore[valid-type]
PremiumMethod = Literal[PREMIUM_METHODS]  # type: ignore[valid-type]
EligibleBase = Literal[ELIGIBLE_BASES]  # type: ignore[valid-type]
StackingMethod = Literal[STACKING_METHODS]  # type: ignore[valid-type]
EscalationTrigger = Literal[ESCALATION_TRIGGERS]  # type: ignore[valid-type]
EscalationScope = Literal[ESCALATION_SCOPES]  # type: ignore[valid-type]
AdjustmentMethod = Literal[ADJUSTMENT_METHODS]  # type: ignore[valid-type]
BenchmarkAreaBasis = Literal[BENCHMARK_AREA_BASES]  # type: ignore[valid-type]
MarketFlag = Literal[MARKET_FLAGS]  # type: ignore[valid-type]
ComponentType = Literal[COMPONENT_TYPES]  # type: ignore[valid-type]
TaxTreatment = Literal[TAX_TREATMENTS]  # type: ignore[valid-type]

#: A response built from an ORM row. Only requests are strict.
_READ = ConfigDict(from_attributes=True, extra="ignore")

Code = Annotated[str, Field(min_length=1, max_length=32)]
Label = Annotated[str, Field(min_length=1, max_length=200)]
MatchCode = Annotated[str, Field(min_length=1, max_length=64)]
Reason = Annotated[str, Field(min_length=1, max_length=500)]
Notes = Annotated[str, Field(max_length=2000)]


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


class PricingConfigurationCreateRequest(StrictRequest):
    """``version_number`` is absent: the server issues it under the project lock."""

    name: Label
    pricing_currency_id: uuid.UUID
    base_internal_rate: Money
    valid_from: date
    valid_to: date | None = None
    premium_stacking_default: StackingMethod = "additive"
    maximum_premium_fraction: Fraction | None = None
    offer_valid_days: int | None = Field(default=None, gt=0)
    price_lock_days: int | None = Field(default=None, gt=0)
    reservation_expiry_days: int | None = Field(default=None, gt=0)
    default_payment_plan_adjustment_fraction: SignedFraction | None = None
    tax_treatment_code: TaxTreatment = "exclusive"


class PricingConfigurationUpdateRequest(StrictRequest):
    """Draft only. ``status`` is deliberately absent — see the explicit routes."""

    name: Label | None = None
    pricing_currency_id: uuid.UUID | None = None
    base_internal_rate: Money | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    premium_stacking_default: StackingMethod | None = None
    maximum_premium_fraction: Fraction | None = None
    offer_valid_days: int | None = Field(default=None, gt=0)
    price_lock_days: int | None = Field(default=None, gt=0)
    reservation_expiry_days: int | None = Field(default=None, gt=0)
    default_payment_plan_adjustment_fraction: SignedFraction | None = None
    tax_treatment_code: TaxTreatment | None = None


class ReasonRequest(StrictRequest):
    """A decision that has to be explicable to whoever reads it later."""

    reason: Reason


class OptionalReasonRequest(StrictRequest):
    reason: Reason | None = None


class PricingConfigurationRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    version_number: int
    name: str
    status: str
    pricing_currency_id: uuid.UUID
    base_internal_rate: DecimalStr
    premium_stacking_default: str
    maximum_premium_fraction: DecimalStr | None
    offer_valid_days: int | None
    price_lock_days: int | None
    reservation_expiry_days: int | None
    default_payment_plan_adjustment_fraction: DecimalStr | None
    tax_treatment_code: str
    valid_from: date
    valid_to: date | None
    submitted_at: datetime | None
    submitted_by_user_id: uuid.UUID | None
    approved_at: datetime | None
    approved_by_user_id: uuid.UUID | None
    activated_at: datetime | None
    activated_by_user_id: uuid.UUID | None
    superseded_at: datetime | None
    change_reason: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Area rules
# --------------------------------------------------------------------------- #


class AreaRuleCreateRequest(StrictRequest):
    area_type_id: uuid.UUID
    pricing_method: AreaPricingMethod
    rate_per_area: Money | None = None
    internal_rate_factor: Fraction | None = None
    sort_order: int = Field(default=0, ge=0)


class AreaRuleUpdateRequest(StrictRequest):
    pricing_method: AreaPricingMethod | None = None
    rate_per_area: Money | None = None
    internal_rate_factor: Fraction | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class AreaRuleRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    pricing_configuration_id: uuid.UUID
    area_type_id: uuid.UUID
    pricing_method: str
    rate_per_area: DecimalStr | None
    internal_rate_factor: DecimalStr | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Premium rules
# --------------------------------------------------------------------------- #


class PremiumRuleCreateRequest(StrictRequest):
    """``source_kind`` is a closed list. There is no field name and no operator."""

    code: Code
    label: Label
    source_kind: PremiumSourceKind
    match_code: MatchCode | None = None
    custom_field_definition_id: uuid.UUID | None = None
    custom_option_code: MatchCode | None = None
    method: PremiumMethod
    percentage_fraction: SignedFraction | None = None
    amount: Money | None = None
    eligible_base: EligibleBase = "base_with_adjustments"
    stacking_method: StackingMethod | None = None
    sequence: int = Field(default=0, ge=0)


class PremiumRuleUpdateRequest(StrictRequest):
    label: Label | None = None
    match_code: MatchCode | None = None
    custom_option_code: MatchCode | None = None
    method: PremiumMethod | None = None
    percentage_fraction: SignedFraction | None = None
    amount: Money | None = None
    eligible_base: EligibleBase | None = None
    stacking_method: StackingMethod | None = None
    sequence: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class PremiumRuleRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    pricing_configuration_id: uuid.UUID
    code: str
    label: str
    source_kind: str
    match_code: str | None
    custom_field_definition_id: uuid.UUID | None
    custom_option_code: str | None
    method: str
    percentage_fraction: DecimalStr | None
    amount: DecimalStr | None
    eligible_base: str
    stacking_method: str | None
    sequence: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Escalation
# --------------------------------------------------------------------------- #


class EscalationRuleCreateRequest(StrictRequest):
    code: Code
    label: Label
    trigger_type: EscalationTrigger
    scope_type: EscalationScope = "project"
    phase_id: uuid.UUID | None = None
    unit_type_code: MatchCode | None = None
    threshold_date: date | None = None
    threshold_fraction: Fraction | None = None
    milestone_reference: Label | None = None
    market_index_reference: Label | None = None
    adjustment_method: AdjustmentMethod
    adjustment_percentage_fraction: SignedFraction | None = None
    adjustment_amount: SignedMoney | None = None
    cumulative: bool = False
    sequence: int = Field(default=0, ge=0)


class EscalationRuleUpdateRequest(StrictRequest):
    label: Label | None = None
    threshold_date: date | None = None
    threshold_fraction: Fraction | None = None
    milestone_reference: Label | None = None
    market_index_reference: Label | None = None
    adjustment_method: AdjustmentMethod | None = None
    adjustment_percentage_fraction: SignedFraction | None = None
    adjustment_amount: SignedMoney | None = None
    cumulative: bool | None = None
    sequence: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class EscalationRuleRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    pricing_configuration_id: uuid.UUID
    code: str
    label: str
    trigger_type: str
    scope_type: str
    phase_id: uuid.UUID | None
    unit_type_code: str | None
    threshold_date: date | None
    threshold_fraction: DecimalStr | None
    milestone_reference: str | None
    market_index_reference: str | None
    adjustment_method: str
    adjustment_percentage_fraction: DecimalStr | None
    adjustment_amount: DecimalStr | None
    cumulative: bool
    sequence: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EscalationActivateRequest(StrictRequest):
    """Evidence and a reason are both required, for every trigger type.

    A date trigger the system could evaluate itself is still activated by a
    person: activation is the moment a policy starts moving money, and one that
    starts because a clock ticked has nobody's name on it.
    """

    effective_date: date
    evidence_reference: Reason
    reason: Reason
    evidence_value: Measure | None = None
    evidence_date: date | None = None


class EscalationActivationRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    pricing_escalation_rule_id: uuid.UUID
    effective_date: date
    evidence_value: DecimalStr | None
    evidence_date: date | None
    evidence_reference: str
    reason: str
    approved_by_user_id: uuid.UUID
    approved_at: datetime
    is_active: bool
    reversed_at: datetime | None
    reversal_reason: str | None


# --------------------------------------------------------------------------- #
# Market benchmarks
# --------------------------------------------------------------------------- #


class BenchmarkCreateRequest(StrictRequest):
    phase_id: uuid.UUID | None = None
    unit_type_code: MatchCode | None = None
    area_basis: BenchmarkAreaBasis
    benchmark_price_per_area: Money
    currency_id: uuid.UUID
    comparison_date: date
    source_name: Label
    source_reference: Reason | None = None
    tolerance_fraction: Fraction
    notes: Notes | None = None


class BenchmarkUpdateRequest(StrictRequest):
    benchmark_price_per_area: Money | None = None
    comparison_date: date | None = None
    source_name: Label | None = None
    source_reference: Reason | None = None
    tolerance_fraction: Fraction | None = None
    notes: Notes | None = None
    is_active: bool | None = None


class BenchmarkRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    phase_id: uuid.UUID | None
    unit_type_code: str | None
    area_basis: str
    benchmark_price_per_area: DecimalStr
    currency_id: uuid.UUID
    comparison_date: date
    source_name: str
    source_reference: str | None
    tolerance_fraction: DecimalStr
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Price versions
# --------------------------------------------------------------------------- #


class PaidUpgradeRequest(StrictRequest):
    code: Code
    label: Label
    amount: Money


class PriceVersionCreateRequest(StrictRequest):
    """Inputs for one draft. Nothing here approves or activates anything."""

    valid_from: date | None = None
    change_reason: Reason | None = None
    internal_rate_override: Money | None = None
    override_reason: Reason | None = None
    paid_upgrades: list[PaidUpgradeRequest] = Field(default_factory=list, max_length=50)


class ComponentOverrideRequest(StrictRequest):
    """Replace one calculated line with a stated amount and a stated reason.

    ``override_amount: null`` removes an override and restores the calculation,
    which is why it is a separate meaning from omitting the key entirely.
    """

    sequence: int = Field(ge=1)
    override_amount: SignedMoney | None = None
    override_reason: Reason | None = None


class PriceVersionUpdateRequest(StrictRequest):
    """Draft only. ``status`` is absent: transitions have their own routes."""

    valid_from: date | None = None
    change_reason: Reason | None = None
    overrides: list[ComponentOverrideRequest] = Field(default_factory=list, max_length=200)


class BulkGenerateRequest(StrictRequest):
    """Which units to price. Filters narrow; they never widen what a caller sees.

    At least one criterion is required. A request with none would select every
    unit in the development, which is a big enough action that it should be
    asked for rather than arrived at by leaving a field out.
    """

    unit_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5000)
    phase_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    unit_type_code: MatchCode | None = None
    commercial_status: MatchCode | None = None
    valid_from: date | None = None
    change_reason: Reason | None = None


class BulkVersionRequest(StrictRequest):
    version_ids: list[uuid.UUID] = Field(min_length=1, max_length=5000)
    reason: Reason | None = None
    valid_from: date | None = None


class PriceComponentRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    sequence: int
    component_type: str
    code: str
    label: str
    quantity: DecimalStr | None
    unit_of_measure: str | None
    basis_amount: DecimalStr | None
    rate: DecimalStr | None
    factor: DecimalStr | None
    calculated_amount: DecimalStr
    override_amount: DecimalStr | None
    final_amount: DecimalStr
    override_reason: str | None
    area_rule_id: uuid.UUID | None
    premium_rule_id: uuid.UUID | None
    escalation_activation_id: uuid.UUID | None


class PriceVersionRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    unit_id: uuid.UUID
    version_number: int
    pricing_configuration_id: uuid.UUID
    unit_area_schedule_id: uuid.UUID
    status: str
    currency_id: uuid.UUID
    valid_from: date | None
    valid_to: date | None
    base_area_value: DecimalStr
    scope_adjustment_total: DecimalStr
    premium_total: DecimalStr
    premium_cap_adjustment: DecimalStr
    escalation_total: DecimalStr
    paid_upgrade_total: DecimalStr
    reference_price_ex_tax: DecimalStr
    internal_area_snapshot: DecimalStr | None
    weighted_area_snapshot: DecimalStr | None
    price_per_internal_area: DecimalStr | None
    price_per_weighted_area: DecimalStr | None
    market_benchmark_id: uuid.UUID | None
    market_benchmark_price_snapshot: DecimalStr | None
    market_deviation_fraction: DecimalStr | None
    market_flag: str
    submitted_at: datetime | None
    submitted_by_user_id: uuid.UUID | None
    approved_at: datetime | None
    approved_by_user_id: uuid.UUID | None
    activated_at: datetime | None
    activated_by_user_id: uuid.UUID | None
    superseded_at: datetime | None
    change_reason: str | None
    created_at: datetime
    updated_at: datetime


class PriceVersionDetail(PriceVersionRead):
    """A price version with the lines that produced it, and what it was based on."""

    components: list[PriceComponentRead]
    basis_snapshot_json: dict[str, Any]


class UnitPricingRead(BaseModel):
    """Everything the Unit 360 pricing tab needs, in one response."""

    model_config = ConfigDict(extra="forbid")

    unit_id: uuid.UUID
    unit_reference: str
    unit_type_code: str | None
    pricing_approved: bool
    repricing_required: bool
    has_active_configuration: bool
    active_price: PriceVersionDetail | None
    history: list[PriceVersionRead]


class PriceRegisterRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: uuid.UUID
    unit_reference: str
    unit_number: str
    unit_type_code: str | None
    commercial_status: str
    pricing_approved: bool
    repricing_required: bool
    version_id: uuid.UUID | None
    version_number: int | None
    status: str | None
    currency_id: uuid.UUID | None
    reference_price_ex_tax: DecimalStr | None
    internal_area_snapshot: DecimalStr | None
    weighted_area_snapshot: DecimalStr | None
    price_per_internal_area: DecimalStr | None
    price_per_weighted_area: DecimalStr | None
    market_flag: str | None
    market_deviation_fraction: DecimalStr | None


class PriceRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[PriceRegisterRow]
    total: int
    priced: int
    not_priced: int
    repricing_required: int


# --------------------------------------------------------------------------- #
# Quote preview
# --------------------------------------------------------------------------- #


class QuotePreviewRequest(StrictRequest):
    """Proposed commercial terms. Nothing here is stored.

    The two groups are kept apart on purpose. A **price concession** — a
    discount or a seller credit — reduces what the buyer contracts to pay. A
    **seller cost** — a furniture package, commission support, a financing
    subsidy — does not: the contract stays where it is and the seller's net
    revenue falls. Merging them produces a contract price nobody agreed to.
    """

    # Price concessions.
    discount_fraction: Fraction | None = None
    discount_amount: Money | None = None
    seller_credit: Money | None = None
    # Price additions.
    paid_upgrade_amount: Money | None = None
    payment_plan_adjustment_fraction: SignedFraction | None = None
    # Seller-borne costs.
    package_cost: Money | None = None
    upgrade_allowance_cost: Money | None = None
    commission_support: Money | None = None
    financing_subsidy: Money | None = None
    extended_terms_npv_cost: Money | None = None
    # Buyer-borne additions.
    buyer_paid_fees: Money | None = None


class QuoteTaxLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tax_code: str
    label: str
    rate_fraction: DecimalStr
    calculation_basis: str
    amount: DecimalStr


class QuotePreviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: uuid.UUID
    unit_reference: str
    unit_price_version_id: uuid.UUID
    version_number: int
    currency_id: uuid.UUID

    approved_reference_price_ex_tax: DecimalStr
    paid_upgrade_price: DecimalStr
    payment_plan_price_adjustment: DecimalStr
    payment_plan_adjustment_fraction: DecimalStr
    gross_quoted_price_ex_tax: DecimalStr

    cash_discount: DecimalStr
    seller_credit: DecimalStr
    net_contract_price_ex_tax: DecimalStr

    seller_package_cost: DecimalStr
    upgrade_allowance_cost: DecimalStr
    commission_support: DecimalStr
    financing_subsidy: DecimalStr
    extended_terms_npv_cost: DecimalStr
    seller_cost_total: DecimalStr
    effective_net_revenue_preview: DecimalStr

    tax_status: str
    tax_treatment_code: str
    taxes: list[QuoteTaxLine]
    tax_total: DecimalStr
    buyer_paid_fees: DecimalStr
    total_buyer_payable_preview: DecimalStr

    offer_valid_days: int | None
    price_lock_days: int | None
    reservation_expiry_days: int | None

    approval_required: bool
    approval_reason: str | None
    threshold_rate_fraction: DecimalStr | None
    threshold_amount: DecimalStr | None
    required_role: str | None


class PricingOverview(BaseModel):
    """The Pricing Studio header: what the project prices at, and what is outstanding."""

    model_config = ConfigDict(extra="forbid")

    configuration: PricingConfigurationRead | None
    currency_id: uuid.UUID | None
    base_internal_rate: DecimalStr | None
    active_escalations: int
    units_total: int
    units_priced: int
    units_not_priced: int
    units_repricing_required: int
