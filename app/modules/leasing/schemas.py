"""Exact decimal inputs and explicit, bounded leasing responses."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Stage = Literal["draft", "marketing", "negotiating", "leased", "closed"]
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]


class Terms(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    owner_client_id: uuid.UUID | None = None
    status: Stage = "draft"
    mandate_date: date | None = None
    mandate_reference: str = Field(default="", max_length=200)
    asking_rent_monthly: Money | None = None
    available_from: date | None = None
    tenant_name: str = Field(default="", max_length=200)
    agreed_rent_monthly: Money | None = None
    security_deposit: Money | None = None
    lease_start: date | None = None
    lease_end: date | None = None
    agreement_reference: str = Field(default="", max_length=200)
    next_action: str = Field(default="", max_length=300)
    follow_up_date: date | None = None
    notes: str = Field(default="", max_length=4000)


class Create(Terms):
    unit_id: uuid.UUID


class Update(Terms):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


class Removal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


class Instruction(Terms):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    unit_id: uuid.UUID
    currency_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class ProjectChoice(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    currency_code: str


class ClientChoice(BaseModel):
    id: uuid.UUID
    display_name: str
    client_number: str
    is_active: bool


class UnitChoice(BaseModel):
    id: uuid.UUID
    unit_reference: str
    building: str | None
    floor: str | None
    is_active: bool


class UnitChoices(BaseModel):
    items: list[UnitChoice]
    total: int


class Source(BaseModel):
    unit: UnitChoice
    project_name: str
    location: str | None
    currency_code: str
    asset_class: str
    bedrooms: int | None
    bathrooms: int | None
    furnishing: str | None
    delivery_status: str
    internal_area: Decimal | None
    area_unit: str | None
    sale_client: ClientChoice | None
    sale_reference: str | None


class Row(Instruction):
    project_name: str
    unit_reference: str
    owner_name: str | None
    currency_code: str
    attention: list[str]


class Detail(Row):
    source: Source
    owner: ClientChoice | None
    owner_matches_sale: bool | None


class Register(BaseModel):
    items: list[Row]
    total: int
    as_at: date
    counts: dict[str, int]
