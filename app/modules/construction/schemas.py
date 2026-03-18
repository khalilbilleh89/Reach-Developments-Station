"""
construction.schemas

Pydantic request/response contracts for the Construction domain.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.shared.enums.construction import ConstructionStatus, MilestoneStatus


# ── ConstructionScope ────────────────────────────────────────────────────────


class ConstructionScopeCreate(BaseModel):
    project_id: Optional[str] = None
    phase_id: Optional[str] = None
    building_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: ConstructionStatus = ConstructionStatus.PLANNED
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None

    @model_validator(mode="after")
    def require_at_least_one_link(self) -> "ConstructionScopeCreate":
        if not any([self.project_id, self.phase_id, self.building_id]):
            raise ValueError(
                "At least one of project_id, phase_id, or building_id must be provided."
            )
        return self


class ConstructionScopeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[ConstructionStatus] = None
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None


class ConstructionScopeResponse(BaseModel):
    id: str
    project_id: Optional[str]
    phase_id: Optional[str]
    building_id: Optional[str]
    name: str
    description: Optional[str]
    status: ConstructionStatus
    start_date: Optional[date]
    target_end_date: Optional[date]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConstructionScopeList(BaseModel):
    items: List[ConstructionScopeResponse]
    total: int


# ── ConstructionMilestone ────────────────────────────────────────────────────


class ConstructionMilestoneCreate(BaseModel):
    scope_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    sequence: int = Field(..., ge=1)
    status: MilestoneStatus = MilestoneStatus.PENDING
    target_date: Optional[date] = None
    completion_date: Optional[date] = None
    notes: Optional[str] = None


class ConstructionMilestoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    sequence: Optional[int] = Field(None, ge=1)
    status: Optional[MilestoneStatus] = None
    target_date: Optional[date] = None
    completion_date: Optional[date] = None
    notes: Optional[str] = None


class ConstructionMilestoneResponse(BaseModel):
    id: str
    scope_id: str
    name: str
    description: Optional[str]
    sequence: int
    status: MilestoneStatus
    target_date: Optional[date]
    completion_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConstructionMilestoneList(BaseModel):
    items: List[ConstructionMilestoneResponse]
    total: int
