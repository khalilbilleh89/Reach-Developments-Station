import uuid
from datetime import date, datetime
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.projects.schemas import StrictRequest

ReportKind = Literal["site_report", "architect_certificate", "client_charter"]


class ReportFields(StrictRequest):
    title: str = Field(min_length=1, max_length=320)
    report_date: date | None = None
    kind: ReportKind = "site_report"
    building_id: uuid.UUID | None = None
    unit_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def valid_scope(self) -> Self:
        if len(set(self.unit_ids)) != len(self.unit_ids):
            raise ValueError("Select each unit only once.")
        if self.kind == "site_report":
            if self.report_date is None:
                raise ValueError("Enter the report date.")
            if self.building_id or self.unit_ids:
                raise ValueError("Site reports apply to the project.")
        elif self.kind == "client_charter":
            if self.building_id or len(self.unit_ids) != 1:
                raise ValueError("Select one unit for the client charter.")
        elif bool(self.building_id) == bool(self.unit_ids):
            raise ValueError("Select a building or one or more units for the certificate.")
        return self

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
    building_label: str | None
    unit_labels: list[str]
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
