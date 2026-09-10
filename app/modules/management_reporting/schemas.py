"""Version-one reporting contracts: exact decimals and explicit coverage."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.management_actions.schemas import ReportingAction, ReportingFrontier
from app.modules.portfolio.outlook_schemas import Outlook
from app.modules.portfolio.schemas import Overview, ProjectSummary, Risk

Scope = Literal["portfolio", "project"]


class Create(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    scope: Scope
    project_id: uuid.UUID | None = None
    label: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def scope_matches(self) -> "Create":
        if (self.scope == "project") != (self.project_id is not None):
            raise ValueError("Project scope requires one project; portfolio scope takes none.")
        return self


class ActionCounts(BaseModel):
    open: int = 0
    in_progress: int = 0
    completed: int = 0
    cancelled: int = 0
    overdue: int = 0


class DevelopmentFact(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    project_id: uuid.UUID
    source_id: uuid.UUID
    kind: Literal["permit", "consultant_stage", "consultant_deliverable"] = "permit"
    label: str
    status: str
    due_date: date | None
    blocking: bool | None = None
    planned_date: date | None = None
    forecast_date: date | None = None
    actual_date: date | None = None


class Payload(BaseModel):
    overview: Overview
    projects: list[ProjectSummary]
    outlooks: list[Outlook]
    actions: list[ReportingAction]
    action_frontier: list[ReportingFrontier]
    action_counts: ActionCounts
    development: list[DevelopmentFact]


class SnapshotHeader(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    scope_type: Scope
    project_id: uuid.UUID | None
    label: str | None
    as_of_date: date
    captured_at: datetime
    created_by_user_id: uuid.UUID
    creator_display_name: str
    schema_version: int
    project_count: int
    incomplete_project_count: int
    content_hash: str

    @field_validator("captured_at")
    @classmethod
    def utc_capture(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class SnapshotOut(SnapshotHeader):
    payload: Payload


class SnapshotPage(BaseModel):
    items: list[SnapshotHeader]
    total: int
    limit: int
    offset: int


class Movement(BaseModel):
    section: str
    metric: str
    project_id: uuid.UUID | None = None
    project_code: str | None = None
    currency: str | None = None
    prior_currency: str | None = None
    current_currency: str | None = None
    unit: str
    prior: Decimal | None
    current: Decimal | None
    delta: Decimal | None = None
    prior_availability: str
    current_availability: str
    comparable: bool
    reason: str | None = None
    basis: str


class FactChange(BaseModel):
    section: str
    project_id: uuid.UUID
    project_code: str
    fact: str
    prior: str | None
    current: str | None


class ProjectIdentity(BaseModel):
    project_id: uuid.UUID
    code: str
    name: str


class RiskChange(BaseModel):
    classification: Literal["new", "resolved", "continuing", "coverage_changed"]
    prior: Risk | None = None
    current: Risk | None = None
    reason: str | None = None


class Execution(BaseModel):
    created: int = 0
    started: int = 0
    completed: int = 0
    reopened: int = 0
    cancelled: int = 0
    prior_overdue: int = 0
    current_overdue: int = 0
    basis: str = (
        "Immutable events: prior capture < occurred_at <= current capture, limited to "
        "versions visible in the current snapshot and projects common to both. "
        "Counts are events, not an effectiveness score."
    )


class Comparison(BaseModel):
    prior: SnapshotHeader
    current: SnapshotHeader
    added_projects: list[ProjectIdentity]
    removed_projects: list[ProjectIdentity]
    common_projects: list[ProjectIdentity]
    movements: list[Movement]
    facts: list[FactChange]
    risks: list[RiskChange]
    execution: Execution
    composition_changed: bool


class BoardPack(BaseModel):
    snapshot: SnapshotOut
    comparison: Comparison | None = None
    historical_notice: str
    section_order: list[str]
