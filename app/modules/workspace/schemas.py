"""Request and response shapes for saved views and preferences."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.projects.schemas import StrictRequest

Density = Literal["comfortable", "compact"]

#: A filter value is a string, number, boolean or null — what a register's
#: controls hold. Nested structures are refused: a view is a form state, not a
#: document.
FilterValue = str | int | float | bool | None


class SavedViewCreate(StrictRequest):
    screen: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=80)
    filters: dict[str, FilterValue] = Field(default_factory=dict, max_length=40)
    sort: str | None = Field(default=None, max_length=80, pattern=r"^-?[a-z][a-z0-9_.]*$")
    pinned: bool = False


class SavedViewUpdate(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    filters: dict[str, FilterValue] | None = Field(default=None, max_length=40)
    sort: str | None = Field(default=None, max_length=80, pattern=r"^-?[a-z][a-z0-9_.]*$")
    pinned: bool | None = None


class SavedViewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    screen: str
    name: str
    filters: dict[str, Any]
    sort: str | None
    pinned: bool
    created_at: datetime
    updated_at: datetime


class PreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    register_density: Density


class PreferencesUpdate(StrictRequest):
    register_density: Density


class ProjectHit(BaseModel):
    """A development the caller may open, found by code or name."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    status: str
    city: str | None = None


class UnitHit(BaseModel):
    """A unit the caller may see, found by its reference or number."""

    id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    unit_reference: str
    unit_number: str
    commercial_status: str


class ClientHit(BaseModel):
    """A buyer on the register, by number and display name only; no contact detail."""

    id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    client_number: str
    display_name: str


class SearchRead(BaseModel):
    """What the command palette shows for a query, each list already scoped to the caller."""

    query: str
    projects: list[ProjectHit]
    units: list[UnitHit]
    clients: list[ClientHit]
