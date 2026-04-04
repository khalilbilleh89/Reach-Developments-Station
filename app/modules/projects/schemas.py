"""
projects.schemas

Pydantic request/response schemas for the Project CRUD API,
and for project-level attribute definitions and options.
"""

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.core.constants.currency import DEFAULT_CURRENCY, SUPPORTED_CURRENCIES
from app.shared.enums.project import ProjectStatus

# ---------------------------------------------------------------------------
# Supported attribute definition keys — extend here as new types are added.
# ---------------------------------------------------------------------------
SUPPORTED_DEFINITION_KEYS = Literal["view_type"]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=100)
    developer_name: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    status: ProjectStatus = ProjectStatus.PIPELINE
    description: Optional[str] = None
    base_currency: str = Field(
        default=DEFAULT_CURRENCY,
        min_length=3,
        max_length=3,
        description=(
            f"ISO 4217 currency code for this project. "
            f"Supported: {', '.join(SUPPORTED_CURRENCIES)}. "
            f"Defaults to '{DEFAULT_CURRENCY}'."
        ),
    )

    @model_validator(mode="after")
    def target_end_not_before_start(self) -> "ProjectCreate":
        if self.start_date and self.target_end_date and self.target_end_date < self.start_date:
            raise ValueError("target_end_date must be on or after start_date")
        return self


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    developer_name: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    status: Optional[ProjectStatus] = None
    description: Optional[str] = None
    base_currency: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code. When supplied, updates the project base currency.",
    )

    @model_validator(mode="after")
    def target_end_not_before_start(self) -> "ProjectUpdate":
        if self.start_date and self.target_end_date and self.target_end_date < self.start_date:
            raise ValueError("target_end_date must be on or after start_date")
        return self


class ProjectResponse(BaseModel):
    id: str
    name: str
    code: str
    developer_name: Optional[str]
    location: Optional[str]
    start_date: Optional[date]
    target_end_date: Optional[date]
    status: ProjectStatus
    description: Optional[str]
    base_currency: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectList(BaseModel):
    items: List[ProjectResponse]
    total: int


class ProjectSummary(BaseModel):
    """Aggregated KPI summary for a single project."""

    project_id: str
    total_phases: int
    active_phases: int
    planned_phases: int
    completed_phases: int
    earliest_start_date: Optional[date]
    latest_target_completion: Optional[date]
    # Unit inventory KPIs (aggregated through the full hierarchy)
    total_units: int
    available_units: int
    reserved_units: int
    under_contract_units: int
    registered_units: int


# ---------------------------------------------------------------------------
# Project Lifecycle Summary
# ---------------------------------------------------------------------------

class ProjectLifecycleSummaryResponse(BaseModel):
    """Cross-module lifecycle readiness summary for a project.

    All flags are derived from real module records — no assumptions are made.
    The current_stage and recommended_next_step fields are deterministic
    derivations based on the presence and status of linked module records.

    Lifecycle stages (in progression order):
      land_defined                — project record exists
      scenario_defined            — at least one scenario linked
      feasibility_ready           — at least one feasibility run linked
      feasibility_calculated      — at least one feasibility run with status='calculated'
      structure_ready             — project hierarchy has phases (structure defined)
      construction_baseline_pending — construction records exist but no approved baseline
      construction_monitored      — approved tender baseline exists
      portfolio_visible           — project is active/completed and visible in portfolio
    """

    project_id: str
    # Presence flags — derived from real records
    has_scenarios: bool
    has_active_scenario: bool
    has_feasibility_runs: bool
    has_calculated_feasibility: bool
    has_phases: bool
    has_construction_records: bool
    has_approved_tender_baseline: bool
    # Composite readiness flag — True when project is fully governed and has
    # active cost records (approved baseline AND construction_records present).
    has_portfolio_visibility: bool
    # Counts for context
    scenario_count: int
    feasibility_run_count: int
    construction_record_count: int
    # Derived lifecycle state
    current_stage: str
    recommended_next_step: str
    next_step_route: Optional[str]
    blocked_reason: Optional[str]
    last_updated_at: datetime


# ---------------------------------------------------------------------------
# Project Attribute Options
# ---------------------------------------------------------------------------

class AttributeOptionCreate(BaseModel):
    value: str = Field(..., min_length=1, max_length=255)
    label: str = Field(..., min_length=1, max_length=255)
    sort_order: int = Field(default=0, ge=0)


class AttributeOptionUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=255)
    sort_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class AttributeOptionResponse(BaseModel):
    id: str
    definition_id: str
    value: str
    label: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Project Attribute Definitions
# ---------------------------------------------------------------------------

class AttributeDefinitionCreate(BaseModel):
    key: SUPPORTED_DEFINITION_KEYS
    label: str = Field(..., min_length=1, max_length=255)
    input_type: str = Field(default="select", max_length=50)


class AttributeDefinitionUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None


class AttributeDefinitionResponse(BaseModel):
    id: str
    project_id: str
    key: str
    label: str
    input_type: str
    is_active: bool
    options: List[AttributeOptionResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AttributeDefinitionList(BaseModel):
    items: List[AttributeDefinitionResponse]
    total: int


# ---------------------------------------------------------------------------
# Project Hierarchy
# ---------------------------------------------------------------------------

class HierarchyFloor(BaseModel):
    floor_id: str
    name: str
    code: str
    sequence_number: int
    unit_count: int


class HierarchyBuilding(BaseModel):
    building_id: str
    name: str
    code: str
    floors: List[HierarchyFloor]


class HierarchyPhase(BaseModel):
    phase_id: str
    name: str
    sequence: int
    buildings: List[HierarchyBuilding]


class ProjectHierarchy(BaseModel):
    project_id: str
    phases: List[HierarchyPhase]
