"""
sales.schemas

Pydantic request/response schemas for buyers, reservations, and sales contracts.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.shared.enums.sales import ContractStatus, ReservationStatus


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
    reservation_date: str = Field(..., description="ISO date string, e.g. 2026-03-13")
    expiry_date: str = Field(..., description="ISO date string, e.g. 2026-04-13")
    notes: Optional[str] = Field(default=None, max_length=1000)


class ReservationUpdate(BaseModel):
    expiry_date: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class ReservationResponse(BaseModel):
    id: str
    unit_id: str
    buyer_id: str
    reservation_date: str
    expiry_date: str
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
    contract_date: str = Field(..., description="ISO date string, e.g. 2026-03-13")
    contract_price: float = Field(..., gt=0)
    notes: Optional[str] = Field(default=None, max_length=1000)


class SalesContractUpdate(BaseModel):
    contract_date: Optional[str] = None
    contract_price: Optional[float] = Field(default=None, gt=0)
    notes: Optional[str] = Field(default=None, max_length=1000)


class SalesContractResponse(BaseModel):
    id: str
    unit_id: str
    buyer_id: str
    reservation_id: Optional[str]
    contract_number: str
    contract_date: str
    contract_price: float
    status: ContractStatus
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SalesContractListResponse(BaseModel):
    total: int
    items: list[SalesContractResponse]
