"""
sales.schemas

Pydantic request/response schemas for buyers, reservations, and sales contracts.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.shared.enums.sales import ContractPaymentStatus, ContractStatus, ReservationStatus


# ---------------------------------------------------------------------------
# Buyer schemas
# ---------------------------------------------------------------------------

class BuyerCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=3, max_length=254)
    phone: str = Field(..., min_length=1, max_length=50)
    nationality: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)


class BuyerUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, min_length=3, max_length=254)
    phone: Optional[str] = Field(default=None, min_length=1, max_length=50)
    nationality: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)


class BuyerResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone: str
    nationality: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BuyerListResponse(BaseModel):
    total: int
    items: list[BuyerResponse]


# ---------------------------------------------------------------------------
# Reservation schemas
# ---------------------------------------------------------------------------

class ReservationCreate(BaseModel):
    unit_id: str
    buyer_id: str
    reservation_date: date
    expiry_date: date
    notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def expiry_not_before_reservation(self) -> "ReservationCreate":
        if self.expiry_date < self.reservation_date:
            raise ValueError("expiry_date must be on or after reservation_date")
        return self


class ReservationUpdate(BaseModel):
    expiry_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class ReservationResponse(BaseModel):
    id: str
    unit_id: str
    buyer_id: str
    reservation_date: date
    expiry_date: date
    status: ReservationStatus
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReservationListResponse(BaseModel):
    total: int
    items: list[ReservationResponse]


# ---------------------------------------------------------------------------
# SalesContract schemas
# ---------------------------------------------------------------------------

class SalesContractCreate(BaseModel):
    unit_id: str
    buyer_id: str
    reservation_id: Optional[str] = None
    contract_number: str = Field(..., min_length=1, max_length=100)
    contract_date: date
    contract_price: float = Field(..., gt=0)
    notes: Optional[str] = Field(default=None, max_length=1000)


class SalesContractUpdate(BaseModel):
    contract_date: Optional[date] = None
    contract_price: Optional[float] = Field(default=None, gt=0)
    notes: Optional[str] = Field(default=None, max_length=1000)


class SalesContractResponse(BaseModel):
    id: str
    unit_id: str
    buyer_id: str
    reservation_id: Optional[str]
    contract_number: str
    contract_date: date
    contract_price: float
    status: ContractStatus
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SalesContractListResponse(BaseModel):
    total: int
    items: list[SalesContractResponse]


# ---------------------------------------------------------------------------
# ContractPaymentSchedule schemas
# ---------------------------------------------------------------------------

class ContractPaymentScheduleResponse(BaseModel):
    id: str
    contract_id: str
    installment_number: int
    due_date: date
    amount: float
    currency: str
    status: ContractPaymentStatus
    paid_at: Optional[datetime]
    payment_reference: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContractPaymentScheduleListResponse(BaseModel):
    total: int
    items: list[ContractPaymentScheduleResponse]


class ContractPaymentRecordRequest(BaseModel):
    installment_number: int = Field(..., ge=1)
    paid_at: Optional[datetime] = None
    payment_reference: Optional[str] = Field(default=None, max_length=255)
