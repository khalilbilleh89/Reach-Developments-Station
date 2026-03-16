"""
receivables.schemas

Pydantic request/response schemas for the receivables module.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.enums.finance import ReceivableStatus


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ReceivableResponse(BaseModel):
    """Response shape for a single receivable."""

    id: str
    contract_id: str
    payment_plan_id: Optional[str]
    installment_id: str
    receivable_number: int
    due_date: date
    amount_due: float
    amount_paid: float
    balance_due: float
    currency: str
    status: ReceivableStatus
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReceivableListResponse(BaseModel):
    """List of receivables for a contract or project."""

    items: List[ReceivableResponse]
    total: int
    total_amount_due: float
    total_amount_paid: float
    total_balance_due: float


# ---------------------------------------------------------------------------
# Update schemas
# ---------------------------------------------------------------------------


class ReceivableStatusUpdate(BaseModel):
    """Payload for manually overriding the status of a receivable."""

    status: str = Field(..., min_length=1, max_length=50)
    notes: Optional[str] = Field(None, max_length=2000)


class ReceivablePaymentUpdate(BaseModel):
    """Payload for recording a manual payment against a receivable.

    amount_paid is the new cumulative amount paid (not an incremental delta).
    This lets the caller set the total paid without tracking prior payments.
    """

    amount_paid: float = Field(..., ge=0.0)
    notes: Optional[str] = Field(None, max_length=2000)


# ---------------------------------------------------------------------------
# Generation response
# ---------------------------------------------------------------------------


class GenerateReceivablesResponse(BaseModel):
    """Response returned after generating receivables for a contract."""

    contract_id: str
    generated: int
    items: List[ReceivableResponse]
