"""
collections.schemas

Pydantic request/response schemas for payment receipts and receivables views.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.constants.currency import DEFAULT_CURRENCY
from app.shared.enums.finance import PaymentMethod, ReceiptStatus, ReceivableStatus


# ---------------------------------------------------------------------------
# Receipt schemas
# ---------------------------------------------------------------------------


class PaymentReceiptCreate(BaseModel):
    """Payload for recording a new payment receipt."""

    contract_id: str = Field(..., min_length=1)
    payment_schedule_id: str = Field(..., min_length=1)
    receipt_date: date
    amount_received: float = Field(..., gt=0)
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=3)
    payment_method: Optional[PaymentMethod] = None
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=1000)


class PaymentReceiptResponse(BaseModel):
    """Response shape for a single payment receipt."""

    id: str
    contract_id: str
    payment_schedule_id: str
    receipt_date: date
    amount_received: float
    currency: str
    payment_method: Optional[PaymentMethod]
    reference_number: Optional[str]
    notes: Optional[str]
    status: ReceiptStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaymentReceiptListResponse(BaseModel):
    """Paginated list of payment receipts for a contract."""

    contract_id: str
    items: List[PaymentReceiptResponse]
    total: int
    total_received: float


# ---------------------------------------------------------------------------
# Receivables schemas
# ---------------------------------------------------------------------------


class ReceivableLineResponse(BaseModel):
    """Receivable view for a single payment schedule line."""

    schedule_id: str
    installment_number: int
    due_date: date
    due_amount: float
    total_received: float
    outstanding_amount: float
    receivable_status: ReceivableStatus


class ContractReceivablesResponse(BaseModel):
    """Full receivables summary for a contract."""

    contract_id: str
    items: List[ReceivableLineResponse]
    total_due: float
    total_received: float
    total_outstanding: float
