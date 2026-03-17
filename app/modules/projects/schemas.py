"""
projects.schemas

Pydantic request/response schemas for the Project CRUD API,
and for project-level attribute definitions and options.
"""

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.shared.enums.project import ProjectStatus

# ---------------------------------------------------------------------------
# Supported attribute definition keys — extend here as new types are added.
# ---------------------------------------------------------------------------
SUPPORTED_DEFINITION_KEYS = Literal["view_type"]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=100)
    developer_name: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    status: ProjectStatus = ProjectStatus.PIPELINE
    description: Optional[str] = None

    @model_validator(mode="after")
    def target_end_not_before_start(self) -> "ProjectCreate":
        if self.start_date and self.target_end_date and self.target_end_date < self.start_date:
            raise ValueError("target_end_date must be on or after start_date")
        return self


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    developer_name: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    status: Optional[ProjectStatus] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def target_end_not_before_start(self) -> "ProjectUpdate":
        if self.start_date and self.target_end_date and self.target_end_date < self.start_date:
            raise ValueError("target_end_date must be on or after start_date")
        return self


class ProjectResponse(BaseModel):
    id: str
    name: str
    code: str
    developer_name: Optional[str]
    location: Optional[str]
    start_date: Optional[date]
    target_end_date: Optional[date]
    status: ProjectStatus
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectList(BaseModel):
    items: List[ProjectResponse]
    total: int


class ProjectSummary(BaseModel):
    """Aggregated KPI summary for a single project."""

    project_id: str
    total_phases: int
    active_phases: int
    planned_phases: int
    completed_phases: int
    earliest_start_date: Optional[date]
    latest_target_completion: Optional[date]


# ---------------------------------------------------------------------------
# Project Attribute Options
# ---------------------------------------------------------------------------

class AttributeOptionCreate(BaseModel):
    value: str = Field(..., min_length=1, max_length=255)
    label: str = Field(..., min_length=1, max_length=255)
    sort_order: int = Field(default=0, ge=0)


class AttributeOptionUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=255)
    sort_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class AttributeOptionResponse(BaseModel):
    id: str
    definition_id: str
    value: str
    label: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Project Attribute Definitions
# ---------------------------------------------------------------------------

class AttributeDefinitionCreate(BaseModel):
    key: SUPPORTED_DEFINITION_KEYS
    label: str = Field(..., min_length=1, max_length=255)
    input_type: str = Field(default="select", max_length=50)


class AttributeDefinitionUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None


class AttributeDefinitionResponse(BaseModel):
    id: str
    project_id: str
    key: str
    label: str
    input_type: str
    is_active: bool
    options: List[AttributeOptionResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AttributeDefinitionList(BaseModel):
    items: List[AttributeDefinitionResponse]
    total: int
