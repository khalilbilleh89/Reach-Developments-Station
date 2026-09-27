"""Plain-text questions and answers; no executable or rich-text content."""

import uuid

from pydantic import BaseModel, Field, field_validator

from app.modules.projects.schemas import StrictRequest


class FaqInput(StrictRequest):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=20000)

    @field_validator("question", "answer")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter both a question and an answer.")
        return value.strip()


class FaqUpdate(FaqInput):
    expected_version: int = Field(ge=1)


class FaqRead(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    version: int


class FaqList(BaseModel):
    items: list[FaqRead]
    can_edit: bool
