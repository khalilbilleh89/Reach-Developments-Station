"""Plain-text directory details; no fixed number of contacts or unique-email rule."""

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.projects.schemas import StrictRequest

Team = Literal["operations", "engineering"]


class TeamFields(StrictRequest):
    team: Team
    name: str
    title: str | None = None
    scope_of_work: str | None = None
    email: str | None = None

    @field_validator("name")
    @classmethod
    def name_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter the person's name.")
        return value.strip()

    @field_validator("title", "scope_of_work", "email")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[^\s@<>?,;:]+@[^\s@<>?,;:]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class TeamUpdate(TeamFields):
    # Defaults permit PATCH omission; explicit null for required fields is still refused.
    team: Team = "operations"
    name: str = ""
    version: int = Field(ge=1)


class TeamRemoval(StrictRequest):
    version: int = Field(ge=1)
    reason: str = Field(min_length=1)


class TeamMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    team: Team
    name: str
    title: str | None
    scope_of_work: str | None
    email: str | None
    version: int


class TeamDirectory(BaseModel):
    members: list[TeamMemberRead]
    can_manage: bool
