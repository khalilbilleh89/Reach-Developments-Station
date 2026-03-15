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


# ---------------------------------------------------------------------------
# UnitPricing (formal per-unit pricing record) schemas
# ---------------------------------------------------------------------------

class UnitPricingCreate(BaseModel):
    """Payload for creating or updating a formal per-unit pricing record."""

    base_price: float = Field(..., ge=0, description="Base price of the unit. Must be non-negative.")
    manual_adjustment: float = Field(
        default=0.0,
        description="Manual upward or downward price adjustment.",
    )
    currency: str = Field(default="AED", min_length=1, max_length=10)
    pricing_status: str = Field(
        default="draft",
        pattern=r"^(draft|reviewed|approved)$",
        description="Pricing review status: draft | reviewed | approved.",
    )
    notes: Optional[str] = Field(default=None, description="Optional free-text notes.")


class UnitPricingUpdate(BaseModel):
    """Payload for partially updating a formal per-unit pricing record."""

    base_price: Optional[float] = Field(default=None, ge=0)
    manual_adjustment: Optional[float] = Field(default=None)
    currency: Optional[str] = Field(default=None, min_length=1, max_length=10)
    pricing_status: Optional[str] = Field(
        default=None,
        pattern=r"^(draft|reviewed|approved)$",
    )
    notes: Optional[str] = Field(default=None)


class UnitPricingResponse(BaseModel):
    """Response schema for a formal per-unit pricing record."""

    id: str
    unit_id: str
    base_price: float
    manual_adjustment: float
    final_price: float
    currency: str
    pricing_status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
