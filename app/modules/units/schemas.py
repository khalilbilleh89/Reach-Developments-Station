"""
units.schemas

Pydantic request/response schemas for the Unit CRUD API.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.enums.project import UnitStatus, UnitType


class UnitCreateForFloor(BaseModel):
    """Payload for creating a unit when floor_id comes from the URL path."""

    unit_number: str = Field(..., min_length=1, max_length=50)
    unit_type: UnitType
    status: UnitStatus = UnitStatus.AVAILABLE
    internal_area: float = Field(..., gt=0)
    balcony_area: Optional[float] = Field(None, ge=0)
    terrace_area: Optional[float] = Field(None, ge=0)
    roof_garden_area: Optional[float] = Field(None, ge=0)
    front_garden_area: Optional[float] = Field(None, ge=0)
    gross_area: Optional[float] = Field(None, gt=0)
    # Apartment-specific master attributes (Layer A)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
    floor_level: Optional[str] = Field(None, max_length=50)
    livable_area: Optional[float] = Field(None, ge=0)
    has_roof_garden: Optional[bool] = None


class UnitCreate(UnitCreateForFloor):
    """Payload for creating a unit when floor_id is provided in the body."""

    floor_id: str


class UnitUpdate(BaseModel):
    unit_type: Optional[UnitType] = None
    status: Optional[UnitStatus] = None
    internal_area: Optional[float] = Field(None, gt=0)
    balcony_area: Optional[float] = Field(None, ge=0)
    terrace_area: Optional[float] = Field(None, ge=0)
    roof_garden_area: Optional[float] = Field(None, ge=0)
    front_garden_area: Optional[float] = Field(None, ge=0)
    gross_area: Optional[float] = Field(None, gt=0)
    # Apartment-specific master attributes (Layer A)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
    floor_level: Optional[str] = Field(None, max_length=50)
    livable_area: Optional[float] = Field(None, ge=0)
    has_roof_garden: Optional[bool] = None


class UnitResponse(BaseModel):
    id: str
    floor_id: str
    unit_number: str
    unit_type: UnitType
    status: UnitStatus
    internal_area: float
    balcony_area: Optional[float]
    terrace_area: Optional[float]
    roof_garden_area: Optional[float]
    front_garden_area: Optional[float]
    gross_area: Optional[float]
    # Apartment-specific master attributes (Layer A)
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    floor_level: Optional[str]
    livable_area: Optional[float]
    has_roof_garden: Optional[bool]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UnitList(BaseModel):
    items: List[UnitResponse]
    total: int
