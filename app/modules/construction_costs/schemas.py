"""
construction_costs.schemas

Pydantic request/response schemas for the Construction Cost Records domain.

Schema families
---------------
ConstructionCostRecordCreate        — fields required to create a new record.
ConstructionCostRecordUpdate        — partial update (all fields optional).
ConstructionCostRecordResponse      — full response shape returned by the API.
ConstructionCostRecordList          — paginated list response.
ConstructionCostSummaryResponse     — typed summary aggregate response.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.shared.enums.construction_costs import CostCategory, CostSource, CostStage


class ConstructionCostRecordCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    cost_category: CostCategory = CostCategory.HARD_COST
    cost_source: CostSource = CostSource.ESTIMATE
    cost_stage: CostStage = CostStage.CONSTRUCTION
    amount: Decimal = Field(..., description="Cost amount (may be negative for adjustments)")
    currency: str = Field(default="AED", max_length=10)
    effective_date: Optional[date] = None
    reference_number: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None
    is_active: bool = True


class ConstructionCostRecordUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    cost_category: Optional[CostCategory] = None
    cost_source: Optional[CostSource] = None
    cost_stage: Optional[CostStage] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = Field(default=None, max_length=10)
    effective_date: Optional[date] = None
    reference_number: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ConstructionCostRecordResponse(BaseModel):
    id: str
    project_id: str
    title: str
    cost_category: CostCategory
    cost_source: CostSource
    cost_stage: CostStage
    amount: Decimal
    currency: str
    effective_date: Optional[date]
    reference_number: Optional[str]
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConstructionCostRecordList(BaseModel):
    total: int
    items: List[ConstructionCostRecordResponse]


class ConstructionCostSummaryResponse(BaseModel):
    """Typed summary aggregate response for a project's construction cost records.

    All monetary totals are Decimal values serialised as strings by FastAPI,
    consistent with the rest of the platform's Decimal field convention.
    """

    project_id: str
    active_record_count: int
    grand_total: Decimal
    by_category: Dict[str, Decimal]
    by_stage: Dict[str, Decimal]

