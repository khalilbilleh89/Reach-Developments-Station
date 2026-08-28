"""Public contracts for country configuration.

Every rate is named ``*_rate_fraction`` and carries an explicit fraction:
``0.160000`` is 16 per cent. Monetary values are ``Decimal`` end to end and are
serialised as JSON strings so no client can silently reinterpret them as floats.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.modules.settings.models import AREA_UNITS, TAX_APPLIES_TO, TAX_CALCULATION_BASIS

AreaUnit = Literal[AREA_UNITS]  # type: ignore[valid-type]
TaxAppliesTo = Literal[TAX_APPLIES_TO]  # type: ignore[valid-type]
TaxCalculationBasis = Literal[TAX_CALCULATION_BASIS]  # type: ignore[valid-type]

#: Decimals leave the API as strings. A JSON number is a float, and a float is
#: never an acceptable carrier for money or a rate.
DecimalStr = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]

#: A rate expressed as a fraction of one.
RateFraction = Annotated[DecimalStr, Field(ge=0, le=1, decimal_places=6)]
Money = Annotated[DecimalStr, Field(ge=0, decimal_places=2)]


class CurrencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    symbol: str | None
    minor_units: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CurrencyCreateRequest(BaseModel):
    code: str = Field(min_length=3, max_length=3)
    name: str = Field(min_length=1, max_length=120)
    symbol: str | None = Field(default=None, max_length=8)
    minor_units: int = Field(default=2, ge=0, le=6)


class CurrencyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    symbol: str | None = Field(default=None, max_length=8)
    minor_units: int | None = Field(default=None, ge=0, le=6)
    is_active: bool | None = None


class CountryPackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: str
    name: str
    locale: str
    timezone: str
    default_currency_id: uuid.UUID
    area_unit: str
    fiscal_year_start_month: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CountryPackCreateRequest(BaseModel):
    country_code: str = Field(min_length=2, max_length=2)
    name: str = Field(min_length=1, max_length=120)
    locale: str = Field(min_length=2, max_length=35)
    timezone: str = Field(min_length=1, max_length=64)
    default_currency_id: uuid.UUID
    area_unit: AreaUnit = "sqm"
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)


class CountryPackUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    locale: str | None = Field(default=None, min_length=2, max_length=35)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    default_currency_id: uuid.UUID | None = None
    area_unit: AreaUnit | None = None
    fiscal_year_start_month: int | None = Field(default=None, ge=1, le=12)
    is_active: bool | None = None


class TaxRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_pack_id: uuid.UUID
    tax_code: str
    label: str
    applies_to: str
    calculation_basis: str
    #: Explicit fraction of one. 0.160000 is 16 per cent.
    rate_fraction: RateFraction
    valid_from: date
    valid_to: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TaxRuleCreateRequest(BaseModel):
    tax_code: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=120)
    applies_to: TaxAppliesTo
    calculation_basis: TaxCalculationBasis
    rate_fraction: RateFraction
    valid_from: date
    valid_to: date | None = None


class TaxRuleUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    applies_to: TaxAppliesTo | None = None
    calculation_basis: TaxCalculationBasis | None = None
    rate_fraction: RateFraction | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool | None = None
    reason: str | None = Field(default=None, max_length=500)


class ReferenceValueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_pack_id: uuid.UUID | None
    category: str
    code: str
    label: str
    description: str | None
    sort_order: int
    is_active: bool
    valid_from: date | None
    valid_to: date | None
    created_at: datetime
    updated_at: datetime


class ReferenceValueCreateRequest(BaseModel):
    #: Omit for a value that applies to every country.
    country_pack_id: uuid.UUID | None = None
    category: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0, le=100000)
    valid_from: date | None = None
    valid_to: date | None = None


class ReferenceValueUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    sort_order: int | None = Field(default=None, ge=0, le=100000)
    is_active: bool | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class ApprovalThresholdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_pack_id: uuid.UUID
    discount_review_rate_fraction: RateFraction | None
    discount_review_amount: Money | None
    pricing_requires_finance_approval: bool
    pricing_requires_commercial_approval: bool
    minimum_margin_rate_fraction: RateFraction | None
    custom_plan_min_down_payment_rate_fraction: RateFraction | None
    custom_plan_max_duration_months: int | None
    custom_plan_max_post_handover_rate_fraction: RateFraction | None
    custom_plan_max_npv_cost_rate_fraction: RateFraction | None
    receipt_reversal_requires_dual_control: bool
    refund_requires_dual_control: bool
    construction_variation_review_amount: Money | None
    forecast_reset_variance_rate_fraction: RateFraction | None
    updated_at: datetime


class ApprovalThresholdWriteRequest(BaseModel):
    """Full replacement of a country pack's control limits."""

    discount_review_rate_fraction: RateFraction | None = None
    discount_review_amount: Money | None = None
    pricing_requires_finance_approval: bool = False
    pricing_requires_commercial_approval: bool = False
    minimum_margin_rate_fraction: RateFraction | None = None
    custom_plan_min_down_payment_rate_fraction: RateFraction | None = None
    custom_plan_max_duration_months: int | None = Field(default=None, ge=1, le=600)
    custom_plan_max_post_handover_rate_fraction: RateFraction | None = None
    custom_plan_max_npv_cost_rate_fraction: RateFraction | None = None
    receipt_reversal_requires_dual_control: bool = True
    refund_requires_dual_control: bool = True
    construction_variation_review_amount: Money | None = None
    forecast_reset_variance_rate_fraction: RateFraction | None = None
    reason: str | None = Field(default=None, max_length=500)
