"""
floors.schemas

Pydantic request/response schemas for the Floor CRUD API.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.enums.project import FloorStatus


class FloorCreateForBuilding(BaseModel):
    """Payload for creating a floor within a specific building (building_id comes from URL)."""

    name: str = Field(..., max_length=255)
    code: str = Field(..., max_length=100)
    sequence_number: int = Field(..., ge=1)
    level_number: Optional[int] = None
    status: FloorStatus = FloorStatus.PLANNED
    description: Optional[str] = None


class FloorCreate(FloorCreateForBuilding):
    """Payload for creating a floor when building_id is provided in the body."""

    building_id: str


class FloorUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    level_number: Optional[int] = None
    status: Optional[FloorStatus] = None
    description: Optional[str] = None


class FloorResponse(BaseModel):
    id: str
    building_id: str
    name: str
    code: str
    sequence_number: int
    level_number: Optional[int]
    status: FloorStatus
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FloorList(BaseModel):
    items: List[FloorResponse]
    total: int
