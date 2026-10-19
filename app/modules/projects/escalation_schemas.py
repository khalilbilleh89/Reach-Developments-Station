"""Percent input at the API boundary; fractions stored using the shared RATE type."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.projects.schemas import StrictRequest


class EscalationFields(StrictRequest):
    effective_date: date
    escalation_percent: Decimal = Field(gt=0, lt=100000, decimal_places=4)
    project_status: str = Field(min_length=1, max_length=200)

    @field_validator("project_status")
    @classmethod
    def status_text(cls, value: str) -> str:
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("Enter a project status.")
        return value


class EscalationUpdate(EscalationFields):
    version: int = Field(ge=1)
    effective_date: date = date.min
    escalation_percent: Decimal = Field(default=Decimal("1"), gt=0, lt=100000, decimal_places=4)
    project_status: str = Field(default="", min_length=1, max_length=200)


class EscalationRemoval(StrictRequest):
    version: int = Field(ge=1)
    reason: str = Field(min_length=1)


class EscalationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    effective_date: date
    escalation_percent: Decimal
    project_status: str
    version: int


class EscalationRegister(BaseModel):
    entries: list[EscalationRead]
    can_manage: bool
