"""
phases.schemas

Pydantic request/response schemas for the Phase CRUD API.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.enums.project import PhaseStatus


class PhaseCreate(BaseModel):
    project_id: str
    name: str = Field(..., min_length=1, max_length=255)
    sequence: int = Field(..., ge=1)
    status: PhaseStatus = PhaseStatus.PLANNED
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class PhaseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    sequence: Optional[int] = Field(None, ge=1)
    status: Optional[PhaseStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class PhaseResponse(BaseModel):
    id: str
    project_id: str
    name: str
    sequence: int
    status: PhaseStatus
    start_date: Optional[date]
    end_date: Optional[date]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PhaseList(BaseModel):
    items: List[PhaseResponse]
    total: int
