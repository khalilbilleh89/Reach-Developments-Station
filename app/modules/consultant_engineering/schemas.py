"""Strict Consultant Engineer request and response contracts."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Strict = ConfigDict(extra="forbid")
Read = ConfigDict(from_attributes=True)


class EngagementCreate(BaseModel):
    model_config = Strict
    consultant_name: str = Field(min_length=1, max_length=200)
    agreement_reference: str = Field(min_length=1, max_length=120)
    agreement_date: date | None = None
    planned_start_date: date | None = None
    planned_completion_date: date | None = None
    scope_summary: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)


class EngagementUpdate(EngagementCreate):
    expected_updated_at: datetime


class EngagementOut(EngagementCreate):
    model_config = Read
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DisciplineWrite(BaseModel):
    model_config = Strict
    name: str = Field(min_length=1, max_length=160)
    lead_name: str | None = Field(default=None, max_length=200)
    status: Literal["not_started", "active", "completed", "on_hold"] = "not_started"
    notes: str | None = Field(default=None, max_length=2000)


class DisciplineOut(DisciplineWrite):
    model_config = Read
    id: uuid.UUID
    engagement_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class StageWrite(BaseModel):
    model_config = Strict
    name: str = Field(min_length=1, max_length=200)
    planned_date: date | None = None
    forecast_date: date | None = None
    actual_completion_date: date | None = None
    status: Literal["not_started", "in_progress", "completed", "on_hold", "cancelled"] = (
        "not_started"
    )
    notes: str | None = Field(default=None, max_length=2000)


class StageUpdate(StageWrite):
    sequence: int = Field(ge=1)
    expected_updated_at: datetime
    expected_order: list[uuid.UUID]


class StageOut(StageWrite):
    model_config = Read
    id: uuid.UUID
    engagement_id: uuid.UUID
    sequence: int
    created_at: datetime
    updated_at: datetime


class DeliverableWrite(BaseModel):
    model_config = Strict
    stage_id: uuid.UUID
    discipline_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=240)
    category: str | None = Field(default=None, max_length=120)
    revision_reference: str | None = Field(default=None, max_length=120)
    document_reference: str | None = Field(default=None, max_length=500)
    due_date: date | None = None
    submitted_date: date | None = None
    accepted_date: date | None = None
    status: Literal[
        "not_started", "in_progress", "submitted", "accepted", "superseded", "cancelled"
    ] = "not_started"
    notes: str | None = Field(default=None, max_length=2000)


class DeliverableUpdate(DeliverableWrite):
    expected_updated_at: datetime


class DeliverableOut(DeliverableWrite):
    model_config = Read
    id: uuid.UUID
    engagement_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class WorkspaceOut(BaseModel):
    active_engagement: EngagementOut | None
    engagements: list[EngagementOut]
    disciplines: list[DisciplineOut]
    stages: list[StageOut]
    deliverables: list[DeliverableOut]
    total_disciplines: int
    completed_disciplines: int
    current_design_stage: StageOut | None
    completed_stages: int
    total_stages: int
    outstanding_deliverables: int
    accepted_deliverables: int
