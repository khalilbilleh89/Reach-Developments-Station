import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.projects.schemas import StrictRequest


class DrawingFields(StrictRequest):
    name: str = Field(min_length=1, max_length=320)
    category: Literal["general", "architecture", "structure", "mep", "landscape", "interiors"] = (
        "general"
    )
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
    filename: str
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
