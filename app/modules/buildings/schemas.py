"""
buildings.schemas

Pydantic request/response schemas for the Building CRUD API.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.enums.project import BuildingStatus


class BuildingCreate(BaseModel):
    phase_id: str
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=100)
    floors_count: Optional[int] = Field(None, ge=1)
    status: BuildingStatus = BuildingStatus.PLANNED


class BuildingCreateForPhase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=100)
    floors_count: Optional[int] = Field(None, ge=1)
    status: BuildingStatus = BuildingStatus.PLANNED


class BuildingUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    floors_count: Optional[int] = Field(None, ge=1)
    status: Optional[BuildingStatus] = None


class BuildingResponse(BaseModel):
    id: str
    phase_id: str
    name: str
    code: str
    floors_count: Optional[int]
    status: BuildingStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BuildingList(BaseModel):
    items: List[BuildingResponse]
    total: int
