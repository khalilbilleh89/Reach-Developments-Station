"""
registration.schemas

Pydantic request/response schemas for the Registration/Conveyancing domain.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.shared.enums.registration import CaseStatus, MilestoneStatus


# ---------------------------------------------------------------------------
# RegistrationCase schemas
# ---------------------------------------------------------------------------

class RegistrationCaseCreate(BaseModel):
    project_id: str
    unit_id: str
    sale_contract_id: str
    buyer_name: str = Field(..., min_length=1, max_length=200)
    buyer_identifier: Optional[str] = Field(default=None, max_length=100)
    jurisdiction: Optional[str] = Field(default=None, max_length=100)
    opened_at: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class RegistrationCaseUpdate(BaseModel):
    status: Optional[CaseStatus] = None
    buyer_identifier: Optional[str] = Field(default=None, max_length=100)
    jurisdiction: Optional[str] = Field(default=None, max_length=100)
    opened_at: Optional[date] = None
    submitted_at: Optional[date] = None
    completed_at: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class RegistrationMilestoneResponse(BaseModel):
    id: str
    registration_case_id: str
    step_code: str
    step_name: str
    sequence: int
    status: MilestoneStatus
    due_date: Optional[date]
    completed_at: Optional[datetime]
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RegistrationDocumentResponse(BaseModel):
    id: str
    registration_case_id: str
    document_type: str
    is_required: bool
    is_received: bool
    received_at: Optional[date]
    reference_number: Optional[str]
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RegistrationCaseResponse(BaseModel):
    id: str
    project_id: str
    unit_id: str
    sale_contract_id: str
    buyer_name: str
    buyer_identifier: Optional[str]
    jurisdiction: Optional[str]
    status: CaseStatus
    opened_at: Optional[date]
    submitted_at: Optional[date]
    completed_at: Optional[date]
    notes: Optional[str]
    milestones: list[RegistrationMilestoneResponse] = []
    documents: list[RegistrationDocumentResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RegistrationCaseListResponse(BaseModel):
    total: int
    items: list[RegistrationCaseResponse]


# ---------------------------------------------------------------------------
# Milestone update schema
# ---------------------------------------------------------------------------

class RegistrationMilestoneUpdate(BaseModel):
    status: Optional[MilestoneStatus] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    remarks: Optional[str] = Field(default=None, max_length=1000)


# ---------------------------------------------------------------------------
# Document update schema
# ---------------------------------------------------------------------------

class RegistrationDocumentUpdate(BaseModel):
    is_received: Optional[bool] = None
    received_at: Optional[date] = None
    reference_number: Optional[str] = Field(default=None, max_length=100)
    remarks: Optional[str] = Field(default=None, max_length=1000)


# ---------------------------------------------------------------------------
# Project registration summary schema
# ---------------------------------------------------------------------------

class RegistrationSummaryResponse(BaseModel):
    project_id: str
    total_sold_units: int = Field(..., ge=0)
    registration_cases_open: int = Field(..., ge=0)
    registration_cases_completed: int = Field(..., ge=0)
    sold_not_registered: int = Field(..., ge=0)
    registration_completion_ratio: float = Field(..., ge=0, le=1)
