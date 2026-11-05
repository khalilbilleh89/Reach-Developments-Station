import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.projects.schemas import StrictRequest


class DrawingFields(StrictRequest):
    name: str = Field(min_length=1, max_length=320)
    category: Literal[
        "general",
        "architecture",
        "structure",
        "mep",
        "landscape",
        "interiors",
        "electrical",
        "mechanical",
        "shop_drawing",
    ] = "general"
    drawing_number: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=200)
    revision: str = Field(default="", max_length=80)
    status: Literal["reference", "for_review", "issued", "superseded"] = "reference"
    notes: str = Field(default="", max_length=2000)

    @field_validator("name", "drawing_number", "location", "revision", "notes")
    @classmethod
    def clean_text(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Text must not contain NUL characters.")
        return value.strip()

    @field_validator("name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value:
            raise ValueError("Enter a drawing name.")
        return value


class DrawingRead(DrawingFields):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str | None
    source_url: str | None
    version: int
    created_at: datetime


class DrawingUpdate(DrawingFields):
    expected_version: int = Field(ge=1)


class DrawingUpload(DrawingFields):
    filename: str = Field(min_length=1, max_length=255)


class DrawingRemoval(StrictRequest):
    reason: str = Field(min_length=1, max_length=500)
    expected_version: int = Field(ge=1)


class DrawingPreview(BaseModel):
    page_count: int
    image: str


class DrawingLink(DrawingFields):
    source_url: str = Field(min_length=1, max_length=2000)

    @field_validator("source_url")
    @classmethod
    def google_drive_url(cls, value: str) -> str:
        value = value.strip()
        if any(ord(char) <= 32 or ord(char) == 127 for char in value) or "\\" in value:
            raise ValueError("Enter a valid Google Drive HTTPS link.")
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.netloc not in {"drive.google.com", "docs.google.com"}
            or not url.path.strip("/")
        ):
            raise ValueError("Use a Google Drive or Google Docs HTTPS sharing link.")
        return value
