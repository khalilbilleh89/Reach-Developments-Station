"""Strict commission contracts; authoritative provenance and totals are response-only."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

Strict = ConfigDict(extra="forbid")
Read = ConfigDict(from_attributes=True)
DecimalStr = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]


class GrantCreate(BaseModel):
    model_config = Strict
    sale_contract_id: uuid.UUID
    commissionable_base_amount: DecimalStr
    granted_rate_fraction: DecimalStr
    notes: str | None = Field(default=None, max_length=2000)


class GrantUpdate(BaseModel):
    model_config = Strict
    commissionable_base_amount: DecimalStr
    granted_rate_fraction: DecimalStr
    notes: str | None = Field(default=None, max_length=2000)
    expected_updated_at: datetime


class AllocationWrite(BaseModel):
    model_config = Strict
    beneficiary_name: str = Field(min_length=1, max_length=200)
    rate_fraction: DecimalStr
    notes: str | None = Field(default=None, max_length=1000)


class AllocationUpdate(AllocationWrite):
    expected_updated_at: datetime


class ReasonRequest(BaseModel):
    model_config = Strict
    reason: str = Field(min_length=1, max_length=1000)


class AllocationOut(BaseModel):
    model_config = Read
    id: uuid.UUID
    beneficiary_name: str
    rate_fraction: DecimalStr
    calculated_amount: DecimalStr
    sequence: int
    notes: str | None
    updated_at: datetime


class GrantOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    sale_contract_id: uuid.UUID
    sale_reference: str
    sale_status: str
    unit_id: uuid.UUID
    unit_reference: str
    buyer_display: str
    currency_id: uuid.UUID
    sold_price_snapshot: DecimalStr
    commissionable_base_amount: DecimalStr
    granted_rate_fraction: DecimalStr
    commission_total: DecimalStr
    status: str
    notes: str | None
    prepared_by_user_id: uuid.UUID
    released_by_user_id: uuid.UUID | None
    released_at: datetime | None
    reversed_by_user_id: uuid.UUID | None
    reversed_at: datetime | None
    reversal_reason: str | None
    created_at: datetime
    updated_at: datetime
    allocations: list[AllocationOut]
    allocation_rate_total: DecimalStr
    allocation_amount_total: DecimalStr
    is_reconciled: bool


class EligibleSaleOut(BaseModel):
    id: uuid.UUID
    sale_reference: str
    unit_reference: str
    buyer_display: str
    sold_price: DecimalStr
    currency_id: uuid.UUID
