"""
commission.schemas

Pydantic request/response schemas for the Commission module.

Schema families are strictly separated:
  Plan definition   — CommissionPlanCreate / CommissionPlanResponse
  Slab definition   — CommissionSlabCreate / CommissionSlabResponse
  Payout results    — CommissionPayoutRequest / CommissionPayoutResponse /
                      CommissionPayoutLineResponse
  Summary           — CommissionSummaryResponse
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.shared.enums.commission import (
    CalculationMode,
    CommissionPartyType,
    CommissionPayoutStatus,
)


# ---------------------------------------------------------------------------
# Plan schemas
# ---------------------------------------------------------------------------


class CommissionPlanCreate(BaseModel):
    project_id: str
    name: str = Field(..., max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    pool_percentage: float = Field(..., gt=0, le=100)
    calculation_mode: CalculationMode = CalculationMode.MARGINAL
    is_active: bool = True
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None

    @model_validator(mode="after")
    def effective_dates_order(self) -> "CommissionPlanCreate":
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise ValueError("effective_to must be after effective_from")
        return self


class CommissionPlanResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str]
    pool_percentage: float
    calculation_mode: CalculationMode
    is_active: bool
    effective_from: Optional[datetime]
    effective_to: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Slab schemas
# ---------------------------------------------------------------------------


class CommissionSlabCreate(BaseModel):
    range_from: float = Field(..., ge=0)
    range_to: Optional[float] = Field(default=None, gt=0)
    sales_rep_pct: float = Field(..., ge=0, le=100)
    team_lead_pct: float = Field(..., ge=0, le=100)
    manager_pct: float = Field(..., ge=0, le=100)
    broker_pct: float = Field(..., ge=0, le=100)
    platform_pct: float = Field(..., ge=0, le=100)
    sequence: int = Field(..., ge=1)

    @model_validator(mode="after")
    def range_to_gt_range_from(self) -> "CommissionSlabCreate":
        if self.range_to is not None and self.range_to <= self.range_from:
            raise ValueError("range_to must be greater than range_from")
        return self

    @model_validator(mode="after")
    def allocation_sums_to_100(self) -> "CommissionSlabCreate":
        total = round(
            self.sales_rep_pct
            + self.team_lead_pct
            + self.manager_pct
            + self.broker_pct
            + self.platform_pct,
            4,
        )
        if abs(total - 100.0) > 0.01:
            raise ValueError(
                f"Slab allocation percentages must sum to 100 (got {total:.4f})"
            )
        return self


class CommissionSlabResponse(BaseModel):
    id: str
    commission_plan_id: str
    range_from: float
    range_to: Optional[float]
    sales_rep_pct: float
    team_lead_pct: float
    manager_pct: float
    broker_pct: float
    platform_pct: float
    sequence: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Payout schemas
# ---------------------------------------------------------------------------


class CommissionPayoutRequest(BaseModel):
    sale_contract_id: str
    commission_plan_id: str
    notes: Optional[str] = Field(default=None, max_length=2000)


class CommissionPayoutLineResponse(BaseModel):
    id: str
    commission_payout_id: str
    party_type: CommissionPartyType
    party_reference: Optional[str]
    slab_id: Optional[str]
    amount: float
    percentage: float
    value_covered: float
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommissionPayoutResponse(BaseModel):
    id: str
    project_id: str
    sale_contract_id: str
    commission_plan_id: str
    gross_sale_value: float
    commission_pool_value: float
    calculation_mode: CalculationMode
    status: CommissionPayoutStatus
    calculated_at: Optional[datetime]
    approved_at: Optional[datetime]
    notes: Optional[str]
    lines: List[CommissionPayoutLineResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommissionPayoutListResponse(BaseModel):
    total: int
    items: List["CommissionPayoutListItem"]


class CommissionPayoutListItem(BaseModel):
    """Lightweight payout representation for list endpoints (no per-line detail)."""

    id: str
    project_id: str
    sale_contract_id: str
    commission_plan_id: str
    gross_sale_value: float
    commission_pool_value: float
    calculation_mode: CalculationMode
    status: CommissionPayoutStatus
    calculated_at: Optional[datetime]
    approved_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Summary schema
# ---------------------------------------------------------------------------


class CommissionSummaryResponse(BaseModel):
    project_id: str
    total_payouts: int
    draft_payouts: int
    calculated_payouts: int
    approved_payouts: int
    cancelled_payouts: int
    total_gross_value: float
    total_commission_pool: float
