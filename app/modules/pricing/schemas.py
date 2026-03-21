"""
pricing.schemas

Pydantic request/response schemas for the Pricing Engine API.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# Authoritative default currency for the platform.  All pricing values inherit
# this when no explicit currency is available from the pricing record.
DEFAULT_CURRENCY = "AED"

# Valid pricing status values.  The canonical lifecycle is:
#   draft → submitted → approved → archived
# The ``reviewed`` status is retained for backward compatibility.
_PRICING_STATUS_PATTERN = r"^(draft|submitted|reviewed|approved|archived)$"


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
    currency: str = Field(default=DEFAULT_CURRENCY)


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
    """Payload for creating or updating a formal per-unit pricing record.

    ``pricing_status`` is intentionally limited to non-terminal values here.
    Approval must go through POST /pricing/{id}/approve (which stamps
    ``approved_by`` and ``approval_date``).  Archival is handled automatically
    by the supersede workflow.
    """

    base_price: float = Field(..., ge=0, description="Base price of the unit. Must be non-negative.")
    manual_adjustment: float = Field(
        default=0.0,
        description="Manual upward or downward price adjustment.",
    )
    currency: str = Field(default="AED", min_length=1, max_length=10)
    pricing_status: str = Field(
        default="draft",
        pattern=r"^(draft|submitted|reviewed)$",
        description="Pricing lifecycle status for create/update: draft | submitted | reviewed.",
    )
    notes: Optional[str] = Field(default=None, description="Optional free-text notes.")


class UnitPricingUpdate(BaseModel):
    """Payload for partially updating a formal per-unit pricing record.

    ``pricing_status`` is intentionally excluded.  Status progression must
    occur through dedicated lifecycle endpoints only:
    - POST /pricing/{id}/approve  — transitions to ``approved``
    - POST /units/{id}/pricing    — archives existing and creates new ``draft``

    ``manual_adjustment`` is intentionally excluded.  All pricing overrides
    must use POST /pricing/{id}/override, which enforces role-based authority
    thresholds and records a full audit trail.

    Only base_price/currency/notes fields are writable here.
    """

    base_price: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=1, max_length=10)
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
    approved_by: Optional[str]
    approval_date: Optional[datetime]
    override_reason: Optional[str]
    override_requested_by: Optional[str]
    override_approved_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PricingApprovalRequest(BaseModel):
    """Payload for approving a pricing record."""

    approved_by: str = Field(..., min_length=1, max_length=255, description="Identifier of the approver.")


class PricingHistoryResponse(BaseModel):
    """Paginated list of all pricing records for a unit (including archived)."""

    unit_id: str
    total: int
    items: List[UnitPricingResponse]


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


# ---------------------------------------------------------------------------
# Premium breakdown schemas
# ---------------------------------------------------------------------------

class PremiumBreakdownResponse(BaseModel):
    """Detailed premium breakdown for a pricing record.

    Shows how the engine-calculated price is composed from the base price
    per sqm and each individual premium component.

    ``has_engine_breakdown`` is False when no UnitPricingAttributes record
    exists for the unit; in that case all engine-derived fields are None.
    The formal pricing record values (base_price, manual_adjustment,
    final_price) are always present.
    """

    pricing_id: str
    unit_id: str
    # Formal pricing record values.
    base_price: float
    manual_adjustment: float
    final_price: float
    currency: str
    # Engine-based breakdown (present only when pricing attributes exist).
    has_engine_breakdown: bool
    base_price_per_sqm: Optional[float]
    unit_area: Optional[float]
    engine_base_unit_price: Optional[float]
    floor_premium: Optional[float]
    view_premium: Optional[float]
    corner_premium: Optional[float]
    size_adjustment: Optional[float]
    custom_adjustment: Optional[float]
    premium_total: Optional[float]
    engine_final_unit_price: Optional[float]


# ---------------------------------------------------------------------------
# Pricing override schemas
# ---------------------------------------------------------------------------

class PricingOverrideRequest(BaseModel):
    """Payload for applying a governed price override to a pricing record.

    The ``override_amount`` replaces the current ``manual_adjustment``.
    The override percentage is computed as abs(override_amount) / base_price × 100
    and validated against the authority threshold for ``role``.

    All three text fields are mandatory to ensure an auditable paper trail.
    """

    override_amount: float = Field(
        ...,
        description="New manual_adjustment value to apply as the price override.",
    )
    override_reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Mandatory justification for the price override.",
    )
    requested_by: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Identifier of the user requesting the override.",
    )
    role: Literal["sales_manager", "development_director", "ceo"] = Field(
        ...,
        description=(
            "Role of the requester used for authority threshold validation. "
            "Accepted values: sales_manager, development_director, ceo."
        ),
    )
