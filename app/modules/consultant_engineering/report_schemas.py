import uuid
from datetime import date, datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.projects.schemas import StrictRequest


class ReportFields(StrictRequest):
    title: str = Field(min_length=1, max_length=320)
    report_date: date
    notes: str = Field(default="", max_length=2000)

    @field_validator("title", "notes")
    @classmethod
    def clean_text(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Text must not contain NUL characters.")
        return value.strip()

    @field_validator("title")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value:
            raise ValueError("Enter a report title.")
        return value


class ReportRead(ReportFields):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str | None
    source_url: str | None
    version: int
    created_at: datetime


class ReportUpdate(ReportFields):
    expected_version: int = Field(ge=1)


class ReportUpload(ReportFields):
    filename: str = Field(min_length=1, max_length=255)


class ReportRemoval(StrictRequest):
    reason: str = Field(min_length=1, max_length=500)
    expected_version: int = Field(ge=1)


class ReportPreview(BaseModel):
    page_count: int
    image: str


class ReportLink(ReportFields):
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
