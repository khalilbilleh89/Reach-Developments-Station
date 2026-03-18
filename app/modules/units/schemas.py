"""
units.schemas

Pydantic request/response schemas for the Unit CRUD API.

Also contains schemas for the unit dynamic attribute values layer (PR-033):
  UnitDynamicAttributeValueResponse — one selected project-defined option for a unit
  UnitDynamicAttributesSaveItem     — one item in the save request
  UnitDynamicAttributesSaveRequest  — full save request payload
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


# ---------------------------------------------------------------------------
# Unit dynamic attribute value schemas (PR-033)
# ---------------------------------------------------------------------------


class UnitDynamicAttributeValueResponse(BaseModel):
    """One selected project-defined attribute option for a unit.

    Includes denormalised definition and option labels so the frontend can
    render values without additional round-trips.
    """

    id: str
    unit_id: str
    definition_id: str
    option_id: str
    # Denormalised read-only fields for frontend convenience
    definition_key: str
    definition_label: str
    option_value: str
    option_label: str

    model_config = {"from_attributes": True}


class UnitDynamicAttributesSaveItem(BaseModel):
    """One attribute selection in a save request."""

    definition_id: str = Field(..., min_length=1)
    option_id: str = Field(..., min_length=1)


class UnitDynamicAttributesSaveRequest(BaseModel):
    """Payload for PUT /units/{unit_id}/dynamic-attributes.

    Upserts the provided attribute selections for the unit.  Each item in
    ``attributes`` must reference a definition that belongs to the same project
    as the unit, and an option that belongs to that definition.
    """

    attributes: List[UnitDynamicAttributesSaveItem]
