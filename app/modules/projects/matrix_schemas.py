"""Six explicit strategy templates, with bounded plain-text inputs."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.projects.schemas import StrictRequest

Framework = Literal["swot", "pestel", "porter", "bcg", "ansoff", "fishbone"]
CATEGORIES = {
    "swot": ["Strengths", "Weaknesses", "Opportunities", "Threats"],
    "pestel": ["Political", "Economic", "Social", "Technological", "Environmental", "Legal"],
    "porter": ["New entrants", "Suppliers", "Competitive rivalry", "Buyers", "Substitutes"],
    "ansoff": [
        "Market penetration",
        "Product development",
        "Market development",
        "Diversification",
    ],
    "fishbone": ["People", "Process", "Technology", "Materials", "Measurement", "Environment"],
    "bcg": [],
}


class MatrixTextRequest(StrictRequest):
    @field_validator("*", mode="after")
    @classmethod
    def reject_nul(cls, value: object) -> object:
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Text cannot contain null characters.")
        return value


class MatrixItem(MatrixTextRequest):
    label: str = Field(min_length=1, max_length=300)
    notes: str = Field(default="", max_length=2000)
    category: str = Field(default="", max_length=80)
    growth_pct: Decimal | None = Field(
        default=None, ge=-100, le=1000, max_digits=8, decimal_places=3
    )
    relative_share: Decimal | None = Field(
        default=None, ge=0, le=1000, max_digits=8, decimal_places=3
    )

    @field_validator("label")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter an item label.")
        return value.strip()


class MatrixFields(MatrixTextRequest):
    title: str = Field(min_length=1, max_length=200)
    framework: Framework
    as_of: date
    context: str = Field(default="", max_length=4000)
    effect: str = Field(default="", max_length=300)
    growth_threshold_pct: Decimal = Field(
        default=Decimal("10"), gt=0, le=100, max_digits=6, decimal_places=3
    )
    items: list[MatrixItem] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def title_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a title.")
        return value.strip()

    @model_validator(mode="after")
    def template_inputs(self) -> "MatrixFields":
        for item in self.items:
            if self.framework == "bcg":
                if item.growth_pct is None or item.relative_share is None:
                    raise ValueError("BCG items need growth (%) and relative market share (x).")
                if item.category:
                    raise ValueError("BCG categories are calculated from growth and share.")
            elif item.category not in CATEGORIES[self.framework]:
                raise ValueError("Choose a category belonging to this framework.")
            elif item.growth_pct is not None or item.relative_share is not None:
                raise ValueError("Growth and share apply only to BCG.")
        if self.framework == "fishbone" and not self.effect.strip():
            raise ValueError("Enter the problem or effect to investigate.")
        return self


class MatrixUpdate(MatrixFields):
    version: int = Field(ge=1)


class MatrixRemoval(MatrixTextRequest):
    version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class MatrixPoint(BaseModel):
    label: str
    category: str
    x: int
    y: int


class MatrixRead(MatrixFields):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    points: list[MatrixPoint] = Field(default_factory=list)


class MatrixDirectory(BaseModel):
    analyses: list[MatrixRead]
    can_manage: bool
