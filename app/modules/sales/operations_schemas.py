"""Explicit Operations requests and responses."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.projects.schemas import StrictRequest

Section = Literal["property_purchase", "golden_visa"]
Purpose = Literal["investment_only", "golden_visa"]


class StageInput(StrictRequest):
    id: uuid.UUID | None = None
    label: str = Field(min_length=1, max_length=160)
    section: Section
    is_active: bool = True

    @field_validator("label")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a stage name.")
        return value.strip()


class PipelineInput(StrictRequest):
    expected_version: int = Field(ge=0)
    stages: list[StageInput] = Field(max_length=100)


class StageRead(BaseModel):
    id: uuid.UUID
    label: str
    section: Section
    position: int
    source: Literal["manual", "buyer_signed_spa"]
    is_active: bool


class ProgressInput(StrictRequest):
    stage_id: uuid.UUID
    completed: bool | None
    completed_date: date | None

    @model_validator(mode="after")
    def date_requires_completion(self) -> "ProgressInput":
        if self.completed is not True and self.completed_date is not None:
            raise ValueError("A completion date requires Yes.")
        return self


class BuyerInput(StrictRequest):
    expected_version: int = Field(ge=0)
    pipeline_version: int = Field(ge=0)
    purpose: Purpose | None
    progress: list[ProgressInput] = Field(max_length=100)
    reason: str = Field(min_length=1, max_length=1000)


class MilestoneRead(BaseModel):
    stage_id: uuid.UUID
    completed: bool | None
    completed_date: date | None
    applicable: bool | None
    source: str
    editable: bool
    signed_sales: int = 0
    total_sales: int = 0


class PurchaseRead(BaseModel):
    id: uuid.UUID
    number: str
    kind: Literal["sale", "reservation"]
    status: str


class BuyerRead(BaseModel):
    id: uuid.UUID
    number: str
    name: str
    active: bool
    purpose: Purpose | None
    version: int
    purchases: list[PurchaseRead]
    milestones: list[MilestoneRead]
    completed_count: int
    applicable_count: int
    next_stage: str | None


class StageSummary(BaseModel):
    stage_id: uuid.UUID
    yes: int
    no: int
    unrecorded: int
    not_applicable: int
    purpose_unknown: int
    applicable: int
    missing_dates: int


class OperationsRead(BaseModel):
    pipeline_version: int
    stages: list[StageRead]
    buyers: list[BuyerRead]
    summaries: list[StageSummary]
    buyer_count: int
    golden_visa_count: int
    investment_count: int
    purpose_unknown_count: int
    can_configure: bool
    can_edit: bool
