"""
floors.schemas

Pydantic request/response schemas for the Floor CRUD API.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.enums.project import FloorStatus


class FloorCreate(BaseModel):
    building_id: str
    level: int
    name: Optional[str] = Field(None, max_length=255)
    status: FloorStatus = FloorStatus.PLANNED


class FloorUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    status: Optional[FloorStatus] = None


class FloorResponse(BaseModel):
    id: str
    building_id: str
    level: int
    name: Optional[str]
    status: FloorStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FloorList(BaseModel):
    items: List[FloorResponse]
    total: int
