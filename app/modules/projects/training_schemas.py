"""Closed metadata contracts for project training files and external references."""

import uuid
from datetime import date, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

Kind = Literal["video", "document"]


class AssetMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    execution_date: date
    title: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=4000)

    @field_validator("title", "category", "description")
    @classmethod
    def safe_text(cls, value: str) -> str:
        if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError("Control characters are not allowed.")
        return value


class AssetCreate(AssetMetadata):
    kind: Kind
    external_url: str | None = Field(default=None, max_length=2000)

    @field_validator("external_url")
    @classmethod
    def safe_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme == "https"
                and parsed.hostname
                and not parsed.username
                and not parsed.password
            )
            valid = valid and parsed.port in (None, 443)
        except ValueError:
            valid = False
        if not valid or "\\" in value or any(c.isspace() or ord(c) < 32 for c in value):
            raise ValueError("Enter a valid HTTPS Drive or reference link without credentials.")
        return value


class AssetUpdate(AssetMetadata):
    expected_version: int = Field(ge=1)


class AssetRead(AssetCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    filename: str | None
    media_type: str | None
    byte_count: int
    created_at: datetime


class AssetRegister(BaseModel):
    total: int
    items: list[AssetRead]
    categories: list[str]


class Removal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)
