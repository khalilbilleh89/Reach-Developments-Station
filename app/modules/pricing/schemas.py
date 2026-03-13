"""
pricing.schemas

Pydantic request/response schemas for the Pricing Engine API.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# UnitPricingAttributes schemas
# ---------------------------------------------------------------------------

class UnitPricingAttributesCreate(BaseModel):
    base_price_per_sqm: float = Field(..., gt=0)
    floor_premium: float = Field(default=0.0, ge=0)
    view_premium: float = Field(default=0.0, ge=0)
    corner_premium: float = Field(default=0.0, ge=0)
    size_adjustment: float = Field(default=0.0)
    custom_adjustment: float = Field(default=0.0)


class UnitPricingAttributesResponse(BaseModel):
    id: str
    unit_id: str
    base_price_per_sqm: Optional[float]
    floor_premium: Optional[float]
    view_premium: Optional[float]
    corner_premium: Optional[float]
    size_adjustment: Optional[float]
    custom_adjustment: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pricing calculation response schemas
# ---------------------------------------------------------------------------

class UnitPriceResponse(BaseModel):
    unit_id: str
    unit_area: float
    base_unit_price: float
    premium_total: float
    final_unit_price: float


class ProjectPriceSummaryItem(BaseModel):
    unit_id: str
    unit_area: float
    base_unit_price: float
    premium_total: float
    final_unit_price: float


class ProjectPriceSummaryResponse(BaseModel):
    project_id: str
    total_units_priced: int
    total_value: float
    items: list[ProjectPriceSummaryItem]
