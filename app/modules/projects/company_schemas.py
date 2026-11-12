"""Every descriptive field is optional; omitted PATCH keys remain unchanged."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, computed_field, field_validator

from app.modules.projects.schemas import StrictRequest


class CompanyWrite(StrictRequest):
    legal_name: str | None = Field(default=None, max_length=320)
    trading_name: str | None = Field(default=None, max_length=320)
    registration_number: str | None = Field(default=None, max_length=320)
    tax_number: str | None = Field(default=None, max_length=320)
    legal_form: str | None = Field(default=None, max_length=320)
    country: str | None = Field(default=None, max_length=320)
    registered_address: str | None = Field(default=None, max_length=2000)
    contact_name: str | None = Field(default=None, max_length=320)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=320)
    website: str | None = Field(default=None, max_length=320)
    authorized_signatory: str | None = Field(default=None, max_length=320)
    project_role: (
        Literal["developer", "landowner", "investor", "project_company_spv", "contractor", "other"]
        | None
    ) = None
    other_role: str | None = Field(default=None, max_length=320)
    relationship: (
        Literal["independent", "parent_company", "subsidiary", "joint_venture", "project_entity"]
        | None
    ) = None
    related_company_id: uuid.UUID | None = None
    no_related_company: bool = False
    ownership_percentage: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=4)
    incorporation_date: date | None = None
    status: Literal["active", "inactive", "under_review"] | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CompanyRead(CompanyWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class BankAccountWrite(StrictRequest):
    beneficiary_name: str | None = Field(default=None, max_length=320)
    beneficiary_bank: str | None = Field(default=None, max_length=320)
    account_number: str | None = Field(default=None, max_length=320)
    iban: str | None = Field(default=None, max_length=320)
    swift_code: str | None = Field(default=None, max_length=320)
    bank_address: str | None = Field(default=None, max_length=2000)
    correspondent_bank: str | None = Field(default=None, max_length=320)
    correspondent_swift_code: str | None = Field(default=None, max_length=320)

    account_purpose: Literal["project", "operating", "escrow", "other"] | None = None
    currency_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    default_for_payments: bool | None = None
    last_verified_date: date | None = None
    status: Literal["active", "inactive"] | None = None
    bank_country: str | None = Field(default=None, max_length=320)


class BankAccountRead(BankAccountWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class CompanyDetail(CompanyRead):
    bank_accounts: list[BankAccountRead]
    logo_id: uuid.UUID | None = None


class RemovalRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=2000)


DOCUMENT_CATEGORIES = (
    "Company registration certificate",
    "Registered office/address certificate",
    "Directors & Secretary certificate",
    "Tax/VAT certificate",
    "Title deed/property document",
    "Other",
)


class DocumentMetadata(StrictRequest):
    category: str | None = Field(default=None, max_length=320)
    other_category: str | None = Field(default=None, max_length=320)
    linked_record: str | None = Field(default=None, max_length=500)
    issue_date: date | None = None
    issue_date_not_stated: bool = False
    expiry_date: date | None = None
    expiry_note: Literal["not_stated", "to_verify"] | None = None
    reminder_date: date | None = None
    reminder_days: int | None = None
    verification_status: Literal["needs_review", "verified", "expired", "superseded"] | None = None

    @field_validator("reminder_days")
    @classmethod
    def allowed_reminder_days(cls, value: int | None) -> int | None:
        if value not in {None, 30, 60, 90}:
            raise ValueError("Select a reminder of 30, 60 or 90 days before expiry.")
        return value


class DocumentFields(DocumentMetadata):
    label: str = Field(min_length=1, max_length=320)

    @field_validator("label")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a document label.")
        return value.strip()


class DocumentUpload(DocumentFields):
    filename: str = Field(min_length=1, max_length=255)


class DocumentUpdate(DocumentFields):
    expected_version: int = Field(ge=1)


class DocumentRemoval(RemovalRequest):
    expected_version: int = Field(ge=1)


class DocumentLink(DocumentFields):
    source_url: str = Field(min_length=1, max_length=2000)

    @field_validator("source_url")
    @classmethod
    def drive_link(cls, value: str) -> str:
        value = value.strip()
        if any(ord(char) <= 32 or ord(char) == 127 for char in value) or "\\" in value:
            raise ValueError("Enter a valid Google Drive HTTPS sharing link.")
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.netloc not in {"drive.google.com", "docs.google.com"}
            or not url.path.strip("/")
        ):
            raise ValueError("Use a Google Drive or Google Docs HTTPS sharing link.")
        return value


class DocumentRead(DocumentMetadata):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    label: str
    filename: str | None
    source_url: str | None = None
    version: int

    @computed_field
    @property
    def reminder_status(self) -> str | None:
        if self.verification_status == "superseded":
            return None
        today = datetime.now(UTC).date()
        if self.expiry_date and self.expiry_date < today:
            return "expired"
        if self.reminder_date and self.reminder_date <= today:
            return "renewal_due"
        return None
