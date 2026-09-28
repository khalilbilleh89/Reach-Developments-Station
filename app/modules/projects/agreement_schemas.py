import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.projects.schemas import StrictRequest


class AgreementFields(StrictRequest):
    name: str = Field(min_length=1, max_length=320)
    signing_company: str = Field(min_length=1, max_length=320)
    draft_created_on: date

    @field_validator("name", "signing_company")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a value.")
        return value.strip()


class AgreementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    signing_company: str
    draft_created_on: date
    filename: str
    version: int


class AgreementUpdate(AgreementFields):
    expected_version: int = Field(ge=1)


class AgreementUpload(AgreementFields):
    filename: str = Field(min_length=1, max_length=255)


class AgreementRemoval(StrictRequest):
    reason: str = Field(min_length=1, max_length=500)
    expected_version: int = Field(ge=1)
