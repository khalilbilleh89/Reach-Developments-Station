"""
feasibility.schemas

Pydantic request/response schemas for the Feasibility Engine API.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.enums.finance import FeasibilityScenarioType


# ---------------------------------------------------------------------------
# FeasibilityRun schemas
# ---------------------------------------------------------------------------

class FeasibilityRunCreate(BaseModel):
    project_id: str
    scenario_name: str = Field(..., min_length=1, max_length=255)
    scenario_type: FeasibilityScenarioType = FeasibilityScenarioType.BASE
    notes: Optional[str] = None


class FeasibilityRunUpdate(BaseModel):
    scenario_name: Optional[str] = Field(None, min_length=1, max_length=255)
    scenario_type: Optional[FeasibilityScenarioType] = None
    notes: Optional[str] = None


class FeasibilityRunResponse(BaseModel):
    id: str
    project_id: str
    scenario_name: str
    scenario_type: FeasibilityScenarioType
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeasibilityRunList(BaseModel):
    items: List[FeasibilityRunResponse]
    total: int


# ---------------------------------------------------------------------------
# FeasibilityAssumptions schemas
# ---------------------------------------------------------------------------

class FeasibilityAssumptionsCreate(BaseModel):
    sellable_area_sqm: float = Field(..., gt=0)
    avg_sale_price_per_sqm: float = Field(..., gt=0)
    construction_cost_per_sqm: float = Field(..., gt=0)
    soft_cost_ratio: float = Field(..., ge=0, le=1)
    finance_cost_ratio: float = Field(..., ge=0, le=1)
    sales_cost_ratio: float = Field(..., ge=0, le=1)
    development_period_months: int = Field(..., ge=1)
    notes: Optional[str] = None


class FeasibilityAssumptionsUpdate(BaseModel):
    sellable_area_sqm: Optional[float] = Field(None, gt=0)
    avg_sale_price_per_sqm: Optional[float] = Field(None, gt=0)
    construction_cost_per_sqm: Optional[float] = Field(None, gt=0)
    soft_cost_ratio: Optional[float] = Field(None, ge=0, le=1)
    finance_cost_ratio: Optional[float] = Field(None, ge=0, le=1)
    sales_cost_ratio: Optional[float] = Field(None, ge=0, le=1)
    development_period_months: Optional[int] = Field(None, ge=1)
    notes: Optional[str] = None


class FeasibilityAssumptionsResponse(BaseModel):
    id: str
    run_id: str
    sellable_area_sqm: Optional[float]
    avg_sale_price_per_sqm: Optional[float]
    construction_cost_per_sqm: Optional[float]
    soft_cost_ratio: Optional[float]
    finance_cost_ratio: Optional[float]
    sales_cost_ratio: Optional[float]
    development_period_months: Optional[int]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# FeasibilityResult schemas
# ---------------------------------------------------------------------------

class FeasibilityResultResponse(BaseModel):
    id: str
    run_id: str
    gdv: Optional[float]
    construction_cost: Optional[float]
    soft_cost: Optional[float]
    finance_cost: Optional[float]
    sales_cost: Optional[float]
    total_cost: Optional[float]
    developer_profit: Optional[float]
    profit_margin: Optional[float]
    irr_estimate: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

