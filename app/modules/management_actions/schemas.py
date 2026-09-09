"""Strict commands; identities and business dates without private user fields."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["open", "in_progress", "completed", "cancelled"]
Source = Literal["manual", "portfolio_risk", "portfolio_outlook"]
DueState = Literal["overdue", "due_soon", "future", "closed"]


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Create(Command):
    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    owner_user_id: uuid.UUID
    due_date: date
    source_type: Source = "manual"
    source_code: str | None = Field(default=None, min_length=1, max_length=80)
    source_key: str | None = Field(default=None, min_length=1, max_length=300)
    source_observation_date: date | None = None


class Patch(Command):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    owner_user_id: uuid.UUID | None = None
    due_date: date | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=2000)


class Transition(Command):
    expected_version: int = Field(ge=1)
    status: Status
    reason: str | None = Field(default=None, min_length=1, max_length=2000)


class Identity(BaseModel):
    user_id: uuid.UUID
    display_name: str


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    project_name: str
    title: str
    description: str | None
    owner: Identity
    due_date: date
    due_state: DueState
    status: Status
    source_type: Source
    source_code: str | None
    source_key: str | None
    source_observation_date: date | None
    created_by: Identity
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None
    version: int


class ActionPage(BaseModel):
    as_of: date
    due_soon_days: int = 7
    items: list[ActionOut]
    total: int
    offset: int
    limit: int


class HistoryOut(BaseModel):
    id: uuid.UUID
    version: int
    actor: Identity
    occurred_at: datetime
    event_type: str
    reason: str | None
    changes: dict


class HistoryPage(BaseModel):
    items: list[HistoryOut]
    total: int
    offset: int
    limit: int
