"""
settings.schemas

Pydantic request/response schemas for the Settings domain.

Schema families
---------------
PricingPolicy     — PricingPolicyCreate / PricingPolicyUpdate / PricingPolicyResponse
CommissionPolicy  — CommissionPolicyCreate / CommissionPolicyUpdate /
                    CommissionPolicyResponse
ProjectTemplate   — ProjectTemplateCreate / ProjectTemplateUpdate /
                    ProjectTemplateResponse

Each family has a paired list-response schema with a total count.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.constants.currency import DEFAULT_CURRENCY
from app.shared.enums.settings import CommissionCalculationMode, PricingPriceMode


# ---------------------------------------------------------------------------
# PricingPolicy schemas
# ---------------------------------------------------------------------------


class PricingPolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    is_default: bool = False
    currency: str = Field(default=DEFAULT_CURRENCY, max_length=10)
    base_markup_percent: Decimal = Field(default=Decimal("0"), ge=0, le=9999)
    balcony_price_factor: Decimal = Field(default=Decimal("0"), ge=0, le=9999)
    parking_price_mode: PricingPriceMode = PricingPriceMode.EXCLUDED
    storage_price_mode: PricingPriceMode = PricingPriceMode.EXCLUDED
    is_active: bool = True


class PricingPolicyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_default: Optional[bool] = None
    currency: Optional[str] = Field(default=None, max_length=10)
    base_markup_percent: Optional[Decimal] = Field(default=None, ge=0, le=9999)
    balcony_price_factor: Optional[Decimal] = Field(default=None, ge=0, le=9999)
    parking_price_mode: Optional[PricingPriceMode] = None
    storage_price_mode: Optional[PricingPriceMode] = None
    is_active: Optional[bool] = None


class PricingPolicyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_default: bool
    currency: str
    base_markup_percent: Decimal
    balcony_price_factor: Decimal
    parking_price_mode: PricingPriceMode
    storage_price_mode: PricingPriceMode
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PricingPolicyList(BaseModel):
    total: int
    items: List[PricingPolicyResponse]


# ---------------------------------------------------------------------------
# CommissionPolicy schemas
# ---------------------------------------------------------------------------


class CommissionPolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    is_default: bool = False
    pool_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    calculation_mode: CommissionCalculationMode = CommissionCalculationMode.MARGINAL
    is_active: bool = True


class CommissionPolicyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_default: Optional[bool] = None
    pool_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)
    calculation_mode: Optional[CommissionCalculationMode] = None
    is_active: Optional[bool] = None


class CommissionPolicyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_default: bool
    pool_percent: Decimal
    calculation_mode: CommissionCalculationMode
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommissionPolicyList(BaseModel):
    total: int
    items: List[CommissionPolicyResponse]


# ---------------------------------------------------------------------------
# ProjectTemplate schemas
# ---------------------------------------------------------------------------


class ProjectTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    default_pricing_policy_id: Optional[str] = None
    default_commission_policy_id: Optional[str] = None
    default_currency: str = Field(default=DEFAULT_CURRENCY, max_length=10)
    is_active: bool = True


class ProjectTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    default_pricing_policy_id: Optional[str] = None
    default_commission_policy_id: Optional[str] = None
    default_currency: Optional[str] = Field(default=None, max_length=10)
    is_active: Optional[bool] = None


class ProjectTemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    default_pricing_policy_id: Optional[str]
    default_commission_policy_id: Optional[str]
    default_currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectTemplateList(BaseModel):
    total: int
    items: List[ProjectTemplateResponse]
