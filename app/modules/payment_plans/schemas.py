"""
payment_plans.schemas

Pydantic request/response schemas for payment plan templates and schedules.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.shared.enums.finance import InstallmentFrequency, PaymentPlanType, PaymentScheduleStatus


# ---------------------------------------------------------------------------
# Template schemas
# ---------------------------------------------------------------------------


class PaymentPlanTemplateCreate(BaseModel):
    """Payload for creating a new payment plan template."""

    name: str = Field(..., min_length=1, max_length=255)
    plan_type: PaymentPlanType = PaymentPlanType.STANDARD_INSTALLMENTS
    description: Optional[str] = Field(None, max_length=1000)
    down_payment_percent: float = Field(..., ge=0.0, le=100.0)
    number_of_installments: int = Field(..., ge=1)
    installment_frequency: InstallmentFrequency = InstallmentFrequency.MONTHLY
    handover_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_allocation(self) -> "PaymentPlanTemplateCreate":
        """Down payment + handover must not exceed 100%."""
        handover = self.handover_percent or 0.0
        total = self.down_payment_percent + handover
        if total > 100.0:
            raise ValueError(
                f"down_payment_percent ({self.down_payment_percent}) + "
                f"handover_percent ({handover}) must not exceed 100. Got {total}."
            )
        return self


class PaymentPlanTemplateUpdate(BaseModel):
    """Payload for partially updating a payment plan template."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    plan_type: Optional[PaymentPlanType] = None
    description: Optional[str] = Field(None, max_length=1000)
    down_payment_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    number_of_installments: Optional[int] = Field(None, ge=1)
    installment_frequency: Optional[InstallmentFrequency] = None
    handover_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def validate_allocation_if_both_provided(self) -> "PaymentPlanTemplateUpdate":
        """When both percent fields are present in the payload, validate total ≤ 100.

        If only one is present the service must merge with the stored value and
        re-validate the effective total.
        """
        if self.down_payment_percent is not None and self.handover_percent is not None:
            total = self.down_payment_percent + self.handover_percent
            if total > 100.0:
                raise ValueError(
                    f"down_payment_percent ({self.down_payment_percent}) + "
                    f"handover_percent ({self.handover_percent}) must not exceed 100. "
                    f"Got {total}."
                )
        return self


class PaymentPlanTemplateResponse(BaseModel):
    """Response shape for a payment plan template."""

    id: str
    name: str
    plan_type: PaymentPlanType
    description: Optional[str]
    down_payment_percent: float
    number_of_installments: int
    installment_frequency: InstallmentFrequency
    handover_percent: Optional[float]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaymentPlanTemplateList(BaseModel):
    """Paginated list of payment plan templates."""

    items: List[PaymentPlanTemplateResponse]
    total: int


# ---------------------------------------------------------------------------
# Schedule schemas
# ---------------------------------------------------------------------------


class PaymentPlanGenerateRequest(BaseModel):
    """Request body for generating a payment schedule for a contract."""

    contract_id: str = Field(..., min_length=1)
    template_id: str = Field(..., min_length=1)
    start_date: Optional[date] = None


class PaymentScheduleResponse(BaseModel):
    """Response shape for a single payment schedule line."""

    id: str
    contract_id: str
    template_id: Optional[str]
    installment_number: int
    due_date: date
    due_amount: float
    status: PaymentScheduleStatus
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaymentScheduleListResponse(BaseModel):
    """List of payment schedule lines for a contract."""

    contract_id: str
    items: List[PaymentScheduleResponse]
    total: int
    total_due: float
