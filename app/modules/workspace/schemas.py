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
