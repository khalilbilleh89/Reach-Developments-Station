"""
phases.schemas

Pydantic request/response schemas for the Phase CRUD API.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.shared.enums.project import PhaseStatus, PhaseType


class PhaseCreate(BaseModel):
    project_id: str
    name: str = Field(..., min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=100)
    sequence: int = Field(..., ge=1)
    phase_type: Optional[PhaseType] = None
    status: PhaseStatus = PhaseStatus.PLANNED
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def end_not_before_start(self) -> "PhaseCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class PhaseCreateForProject(BaseModel):
    """Schema for creating a phase within a project (project_id comes from URL)."""

    name: str = Field(..., min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=100)
    sequence: int = Field(..., ge=1)
    phase_type: Optional[PhaseType] = None
    status: PhaseStatus = PhaseStatus.PLANNED
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def end_not_before_start(self) -> "PhaseCreateForProject":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class PhaseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=100)
    sequence: Optional[int] = Field(None, ge=1)
    phase_type: Optional[PhaseType] = None
    status: Optional[PhaseStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def end_not_before_start(self) -> "PhaseUpdate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class PhaseResponse(BaseModel):
    id: str
    project_id: str
    name: str
    code: Optional[str]
    sequence: int
    phase_type: Optional[PhaseType]
    status: PhaseStatus
    start_date: Optional[date]
    end_date: Optional[date]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PhaseList(BaseModel):
    items: List[PhaseResponse]
    total: int


class LifecyclePhaseItem(BaseModel):
    """A phase as part of the project lifecycle view."""

    id: str
    project_id: str
    name: str
    code: Optional[str]
    sequence: int
    phase_type: Optional[PhaseType]
    status: PhaseStatus
    start_date: Optional[date]
    end_date: Optional[date]
    description: Optional[str]
    is_current: bool

    model_config = {"from_attributes": True}


class ProjectLifecycle(BaseModel):
    """Ordered lifecycle view for a project showing progression state."""

    project_id: str
    phases: List[LifecyclePhaseItem]
    current_phase_type: Optional[PhaseType]
    current_sequence: Optional[int]
