"""Exact fixed-amount operations commission contracts."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

Amount = Annotated[
    Decimal,
    Field(gt=0, max_digits=18, decimal_places=2),
    PlainSerializer(str, return_type=str, when_used="json"),
]


class OperationsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    client_id: uuid.UUID
    beneficiary_name: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)
    amount: Amount


class OperationsUpdate(OperationsInput):
    expected_version: int = Field(ge=1)


class OperationsDelete(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


class OperationsOut(OperationsInput):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    client_display: str
    currency_id: uuid.UUID
    version: int
    created_at: datetime


class ClientOption(BaseModel):
    id: uuid.UUID
    display_name: str
    client_number: str


class OperationsRegister(BaseModel):
    items: list[OperationsOut]
    clients: list[ClientOption]
    currency_id: uuid.UUID
