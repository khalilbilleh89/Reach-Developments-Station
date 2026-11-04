"""Closed metadata contracts for project marketing files and external references."""

import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Placement = Literal["logo", "material"]
Kind = Literal["image", "video", "document"]


class AssetMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    notes: str = Field(default="", max_length=500)

    @field_validator("title", "category", "notes")
    @classmethod
    def safe_text(cls, value: str) -> str:
        if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError("Control characters are not allowed.")
        return value


class AssetCreate(AssetMetadata):
    placement: Placement = "material"
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

    @model_validator(mode="after")
    def logo_type(self) -> "AssetCreate":
        if self.placement == "logo" and (self.kind != "image" or self.external_url):
            raise ValueError("Logos must be uploaded PNG or JPEG images.")
        return self


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
