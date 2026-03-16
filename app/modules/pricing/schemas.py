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
# Pricing readiness inspection schema
# ---------------------------------------------------------------------------

class PricingReadinessResponse(BaseModel):
    """Explicit readiness state for the pricing engine inputs of a unit.

    Returned by GET /pricing/unit/{unit_id}/readiness so the frontend can
    distinguish between:
      - a unit that is fully configured for pricing (is_ready_for_pricing=True)
      - a unit that is missing specific numerical engine attributes (False)

    missing_required_fields lists only the fields that are absent from the
    stored UnitPricingAttributes record (e.g. base_price_per_sqm, floor_premium).
    This is separate from the qualitative attributes managed by the
    EditAttributesModal (view_type, corner_unit, etc.), which do not block
    the pricing engine.
    """

    unit_id: str
    is_ready_for_pricing: bool
    missing_required_fields: list[str]
    readiness_reason: Optional[str]


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


# ---------------------------------------------------------------------------
# Assembled pricing detail schema (three-layer model)
# ---------------------------------------------------------------------------

class UnitPricingDetailResponse(BaseModel):
    """Assembled pricing detail for a single unit — all pricing layers in one response.

    Separates the three conceptually distinct pricing concepts so that the
    frontend can render a coherent inspection view without stitching together
    multiple unrelated responses:

    Layer 2 — engine_inputs (UnitPricingAttributesResponse | None):
        Numerical inputs consumed by the pricing calculation engine:
        base_price_per_sqm, floor_premium, view_premium, corner_premium,
        size_adjustment, and custom_adjustment.  Missing when the unit has
        not yet been configured for pricing.  Managed via POST
        /pricing/unit/{id}/attributes.

    Layer 3a — pricing_readiness (PricingReadinessResponse):
        Authoritative readiness summary that lists exactly which engine-input
        fields are still missing.  Always present (even when engine_inputs is
        None) so the frontend can display actionable missing-field details.

    Layer 3b — pricing_record (UnitPricingResponse | None):
        Formal commercial pricing record: approved price, currency, status,
        and analyst notes.  Missing when no record has been created yet.
        Managed via PUT /units/{id}/pricing.

    Note: Layer 1 (qualitative attributes — view type, corner unit, etc.) is
    managed by the separate pricing_attributes module and is returned by
    GET /units/{id}/pricing-attributes.  It is not included here to keep
    the module boundary clean.
    """

    unit_id: str
    engine_inputs: Optional[UnitPricingAttributesResponse]
    pricing_readiness: PricingReadinessResponse
    pricing_record: Optional[UnitPricingResponse]
