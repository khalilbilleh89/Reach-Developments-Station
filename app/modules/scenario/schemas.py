"""
scenario.schemas

Pydantic request/response schemas for the Scenario Engine API.

All payloads are strongly typed.  ORM models are never leaked directly.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Scenario schemas
# ---------------------------------------------------------------------------


class ScenarioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=100)
    source_type: str = Field("feasibility", max_length=50)
    project_id: Optional[str] = None
    land_id: Optional[str] = None
    notes: Optional[str] = None


class ScenarioUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class ScenarioResponse(BaseModel):
    id: str
    name: str
    code: Optional[str]
    status: str
    source_type: str
    project_id: Optional[str]
    land_id: Optional[str]
    base_scenario_id: Optional[str]
    is_active: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScenarioList(BaseModel):
    items: List[ScenarioResponse]
    total: int


# ---------------------------------------------------------------------------
# ScenarioVersion schemas
# ---------------------------------------------------------------------------


class ScenarioVersionCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    assumptions_json: Optional[Dict[str, Any]] = None
    comparison_metrics_json: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = Field(None, max_length=255)


class ScenarioVersionResponse(BaseModel):
    id: str
    scenario_id: str
    version_number: int
    title: Optional[str]
    notes: Optional[str]
    assumptions_json: Optional[Dict[str, Any]]
    comparison_metrics_json: Optional[Dict[str, Any]]
    created_by: Optional[str]
    is_approved: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScenarioVersionList(BaseModel):
    items: List[ScenarioVersionResponse]
    total: int


# ---------------------------------------------------------------------------
# Duplicate schema
# ---------------------------------------------------------------------------


class ScenarioDuplicateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Comparison schema
# ---------------------------------------------------------------------------


class ScenarioCompareRequest(BaseModel):
    scenario_ids: List[str] = Field(..., min_length=2)


class ScenarioCompareItem(BaseModel):
    scenario_id: str
    scenario_name: str
    status: str
    latest_version_number: Optional[int]
    assumptions_json: Optional[Dict[str, Any]]
    comparison_metrics_json: Optional[Dict[str, Any]]


class ScenarioCompareResponse(BaseModel):
    scenarios: List[ScenarioCompareItem]
