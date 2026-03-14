"""
sales_exceptions.schemas

Pydantic request/response schemas for the SalesException resource.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.shared.enums.sales_exceptions import ApprovalStatus, ExceptionType


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------

class SalesExceptionCreate(BaseModel):
    project_id: str
    unit_id: str
    sale_contract_id: Optional[str] = None
    exception_type: ExceptionType
    base_price: float = Field(..., gt=0)
    requested_price: float = Field(..., gt=0)
    incentive_value: Optional[float] = Field(default=None, ge=0)
    incentive_description: Optional[str] = Field(default=None, max_length=500)
    requested_by: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def requested_price_not_above_base(self) -> "SalesExceptionCreate":
        if self.requested_price > self.base_price:
            raise ValueError("requested_price must not exceed base_price")
        return self


class SalesExceptionUpdate(BaseModel):
    """Fields that may be changed while the exception is still pending."""

    sale_contract_id: Optional[str] = None
    incentive_value: Optional[float] = Field(default=None, ge=0)
    incentive_description: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)


class SalesExceptionApproval(BaseModel):
    """Payload for approve/reject actions."""

    approved_by: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class SalesExceptionResponse(BaseModel):
    id: str
    project_id: str
    unit_id: str
    sale_contract_id: Optional[str]
    exception_type: ExceptionType
    base_price: float
    requested_price: float
    discount_amount: float
    discount_percentage: float
    incentive_value: Optional[float]
    incentive_description: Optional[str]
    approval_status: ApprovalStatus
    requested_by: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SalesExceptionListResponse(BaseModel):
    total: int
    items: list[SalesExceptionResponse]


# ---------------------------------------------------------------------------
# Project-level summary
# ---------------------------------------------------------------------------

class SalesExceptionSummary(BaseModel):
    project_id: str
    total_exceptions: int
    pending_exceptions: int
    approved_exceptions: int
    rejected_exceptions: int
    total_discount_amount: float
    total_incentive_value: float
