"""Every descriptive field is optional; omitted PATCH keys remain unchanged."""

import uuid

from pydantic import ConfigDict, Field

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


class BankAccountRead(BankAccountWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class CompanyDetail(CompanyRead):
    bank_accounts: list[BankAccountRead]


class RemovalRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=2000)
