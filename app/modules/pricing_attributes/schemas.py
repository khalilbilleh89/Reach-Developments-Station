"""
pricing_attributes.schemas

Pydantic request/response schemas for the Unit Qualitative Attributes API.

Enum-validated categorical fields:
  view_type: city | sea | park | interior
  floor_premium_category: standard | premium | penthouse
  orientation: N | S | E | W | NE | NW | SE | SW
  outdoor_area_premium: none | balcony | terrace | roof_garden
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UnitQualitativeAttributesCreate(BaseModel):
    """Payload for creating or updating qualitative pricing attributes for a unit."""

    view_type: Optional[str] = Field(
        default=None,
        pattern=r"^(city|sea|park|interior)$",
        description="View classification: city | sea | park | interior",
    )
    corner_unit: Optional[bool] = Field(
        default=None,
        description="Whether the unit is on a building corner.",
    )
    floor_premium_category: Optional[str] = Field(
        default=None,
        pattern=r"^(standard|premium|penthouse)$",
        description="Floor value classification: standard | premium | penthouse",
    )
    orientation: Optional[str] = Field(
        default=None,
        pattern=r"^(N|S|E|W|NE|NW|SE|SW)$",
        description="Cardinal orientation: N | S | E | W | NE | NW | SE | SW",
    )
    outdoor_area_premium: Optional[str] = Field(
        default=None,
        pattern=r"^(none|balcony|terrace|roof_garden)$",
        description="Outdoor premium treatment: none | balcony | terrace | roof_garden",
    )
    upgrade_flag: Optional[bool] = Field(
        default=None,
        description="Whether the unit has finish upgrades or premium interior.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional analyst commentary.",
    )


class UnitQualitativeAttributesResponse(BaseModel):
    """Response schema for qualitative pricing attributes."""

    id: str
    unit_id: str
    view_type: Optional[str]
    corner_unit: Optional[bool]
    floor_premium_category: Optional[str]
    orientation: Optional[str]
    outdoor_area_premium: Optional[str]
    upgrade_flag: Optional[bool]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
