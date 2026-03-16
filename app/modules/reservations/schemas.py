"""
reservations.schemas

Pydantic request/response schemas for the unit reservation API.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ReservationStatus(str, Enum):
    """Lifecycle states for a unit reservation."""

    active = "active"
    expired = "expired"
    cancelled = "cancelled"
    converted = "converted"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ReservationCreate(BaseModel):
    """Payload for creating a new unit reservation."""

    unit_id: str
    customer_name: str = Field(..., min_length=1, max_length=200)
    customer_phone: str = Field(..., min_length=1, max_length=50)
    customer_email: Optional[str] = Field(default=None, max_length=254)
    reservation_price: float = Field(..., gt=0)
    reservation_fee: Optional[float] = Field(default=None, ge=0)
    currency: str = Field(default="AED", max_length=10)
    expires_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class ReservationUpdate(BaseModel):
    """Payload for partially updating an active reservation.

    Status transitions are NOT permitted via PATCH; use the dedicated lifecycle
    endpoints (cancel, expire, convert) instead.
    """

    notes: Optional[str] = Field(default=None, max_length=2000)
    expires_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ReservationResponse(BaseModel):
    """Full reservation record returned by the API."""

    id: str
    unit_id: str
    customer_name: str
    customer_phone: str
    customer_email: Optional[str]
    reservation_price: float
    reservation_fee: Optional[float]
    currency: str
    status: ReservationStatus
    expires_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReservationListResponse(BaseModel):
    """Paginated list of reservations."""

    total: int
    items: list[ReservationResponse]
