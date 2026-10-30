"""Plain-text titles and email templates; no executable or rich-text content."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.projects.schemas import StrictRequest


class EmailInput(StrictRequest):
    category: Literal["internal", "clients", "external"]
    subject: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20000)

    @field_validator("title", "subject", "body")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a title, subject and email body.")
        return value.strip()


class EmailUpdate(EmailInput):
    expected_version: int = Field(ge=1)


class EmailRead(BaseModel):
    category: Literal["internal", "clients", "external"]
    subject: str
    id: uuid.UUID
    title: str
    body: str
    version: int


class EmailList(BaseModel):
    items: list[EmailRead]
    can_edit: bool
