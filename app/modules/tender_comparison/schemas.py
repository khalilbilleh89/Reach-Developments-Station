"""
tender_comparison.schemas

Pydantic request/response schemas for the Tender Comparison domain.

Schema families
---------------
ConstructionCostComparisonSetCreate     — create a new comparison set.
ConstructionCostComparisonSetUpdate     — partial update of a set.
ConstructionCostComparisonLineCreate    — add a line to a set.
ConstructionCostComparisonLineUpdate    — partial update of a line.
ConstructionCostComparisonLineResponse  — full line response.
ConstructionCostComparisonSetResponse   — full set response including lines.
ConstructionCostComparisonSummaryResponse — set-level variance summary totals.

PR-V6-13 additions:
ConstructionCostComparisonSetResponse and ConstructionCostComparisonSetListItem
  now include is_approved_baseline / approved_at / approved_by_user_id.
ActiveTenderBaselineResponse — lightweight response for the project active-baseline
  query endpoint.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.constants.currency import DEFAULT_CURRENCY
from app.shared.enums.construction_costs import CostCategory
from app.shared.enums.tender_comparison import ComparisonStage, VarianceReason


# ---------------------------------------------------------------------------
# Comparison Line schemas
# ---------------------------------------------------------------------------


class ConstructionCostComparisonLineCreate(BaseModel):
    cost_category: CostCategory = CostCategory.HARD_COST
    baseline_amount: Decimal = Field(
        default=Decimal("0.00"),
        description="Baseline cost amount for this category.",
    )
    comparison_amount: Decimal = Field(
        default=Decimal("0.00"),
        description="Comparison (tender/contract/variation) cost amount.",
    )
    variance_reason: VarianceReason = VarianceReason.OTHER
    notes: Optional[str] = None


class ConstructionCostComparisonLineUpdate(BaseModel):
    cost_category: Optional[CostCategory] = None
    baseline_amount: Optional[Decimal] = None
    comparison_amount: Optional[Decimal] = None
    variance_reason: Optional[VarianceReason] = None
    notes: Optional[str] = None


class ConstructionCostComparisonLineResponse(BaseModel):
    id: str
    comparison_set_id: str
    cost_category: CostCategory
    baseline_amount: Decimal
    comparison_amount: Decimal
    variance_amount: Decimal
    variance_pct: Optional[Decimal]
    variance_reason: VarianceReason
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Comparison Set schemas
# ---------------------------------------------------------------------------


class ConstructionCostComparisonSetCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    comparison_stage: ComparisonStage = ComparisonStage.BASELINE_VS_TENDER
    baseline_label: str = Field(default="Baseline", min_length=1, max_length=255)
    comparison_label: str = Field(default="Tender", min_length=1, max_length=255)
    notes: Optional[str] = None
    is_active: bool = True
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=3)


class ConstructionCostComparisonSetUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    comparison_stage: Optional[ComparisonStage] = None
    baseline_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    comparison_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)


class ConstructionCostComparisonSetResponse(BaseModel):
    id: str
    project_id: str
    title: str
    comparison_stage: ComparisonStage
    baseline_label: str
    comparison_label: str
    notes: Optional[str]
    is_active: bool
    currency: str
    is_approved_baseline: bool
    approved_at: Optional[datetime]
    approved_by_user_id: Optional[str]
    lines: List[ConstructionCostComparisonLineResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConstructionCostComparisonSetListItem(BaseModel):
    """Lightweight set entry for list responses (no lines)."""

    id: str
    project_id: str
    title: str
    comparison_stage: ComparisonStage
    baseline_label: str
    comparison_label: str
    notes: Optional[str]
    is_active: bool
    currency: str
    is_approved_baseline: bool
    approved_at: Optional[datetime]
    approved_by_user_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConstructionCostComparisonSetList(BaseModel):
    total: int
    items: List[ConstructionCostComparisonSetListItem]


class ConstructionCostComparisonSummaryResponse(BaseModel):
    """Set-level variance summary derived live from its lines.

    All monetary totals are Decimal values serialised as strings by FastAPI,
    consistent with the platform's Decimal field convention.
    """

    comparison_set_id: str
    project_id: str
    line_count: int
    total_baseline: Decimal
    total_comparison: Decimal
    total_variance: Decimal
    total_variance_pct: Optional[Decimal]


class ActiveTenderBaselineResponse(BaseModel):
    """Response for the project active-baseline query endpoint.

    Returns the currently approved baseline set for a project, or null fields
    when no baseline has been approved.
    """

    project_id: str
    has_approved_baseline: bool
    baseline: Optional[ConstructionCostComparisonSetListItem]
