"""
projects.schemas

Pydantic request/response schemas for the Project CRUD API.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.shared.enums.project import ProjectStatus


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
