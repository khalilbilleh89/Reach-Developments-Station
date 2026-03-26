"""
concept_design.schemas

Pydantic request/response schemas for the Concept Design API.

PR-CONCEPT-052, PR-CONCEPT-054, PR-CONCEPT-059, PR-CONCEPT-060, PR-CONCEPT-065
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# ConceptOption schemas
# ---------------------------------------------------------------------------

class ConceptOptionCreate(BaseModel):
    project_id: Optional[str] = None
    scenario_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255)
    status: str = Field(default="draft", pattern="^(draft|active|archived)$")
    description: Optional[str] = None
    site_area: Optional[float] = Field(default=None, gt=0)
    gross_floor_area: Optional[float] = Field(default=None, gt=0)
    building_count: Optional[int] = Field(default=None, ge=1)
    floor_count: Optional[int] = Field(default=None, ge=1)
    # Zoning constraint inputs — PR-CONCEPT-059
    far_limit: Optional[float] = Field(default=None, gt=0)
    density_limit: Optional[float] = Field(default=None, gt=0)
    # Land / Scenario integration overrides — PR-CONCEPT-060
    # These take priority over the inherited land constraints when set.
    concept_override_far_limit: Optional[float] = Field(default=None, gt=0)
    concept_override_density_limit: Optional[float] = Field(default=None, gt=0)


class ConceptOptionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    status: Optional[str] = Field(default=None, pattern="^(draft|active|archived)$")
    description: Optional[str] = None
    site_area: Optional[float] = Field(default=None, gt=0)
    gross_floor_area: Optional[float] = Field(default=None, gt=0)
    building_count: Optional[int] = Field(default=None, ge=1)
    floor_count: Optional[int] = Field(default=None, ge=1)
    # Zoning constraint inputs — PR-CONCEPT-059
    far_limit: Optional[float] = Field(default=None, gt=0)
    density_limit: Optional[float] = Field(default=None, gt=0)
    # Land / Scenario integration overrides — PR-CONCEPT-060
    concept_override_far_limit: Optional[float] = Field(default=None, gt=0)
    concept_override_density_limit: Optional[float] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def reject_explicit_null_for_non_nullable_fields(self) -> "ConceptOptionUpdate":
        """Prevent callers from explicitly nulling out non-nullable DB fields.

        name and status are NOT NULL in the database.  If a client sends
        ``{"name": null}`` or ``{"status": null}`` the value would appear in
        model_fields_set with None, which would propagate to the ORM and cause
        a DB-level IntegrityError.  Catch and reject it here cleanly.
        """
        for field in ("name", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"'{field}' cannot be set to null.")
        return self


class ConceptOptionResponse(BaseModel):
    id: str
    project_id: Optional[str]
    scenario_id: Optional[str]
    name: str
    status: str
    description: Optional[str]
    site_area: Optional[float]
    gross_floor_area: Optional[float]
    building_count: Optional[int]
    floor_count: Optional[int]
    # Zoning constraint inputs — PR-CONCEPT-059
    far_limit: Optional[float]
    density_limit: Optional[float]
    # Land / Scenario integration — PR-CONCEPT-060
    land_id: Optional[str]
    concept_override_far_limit: Optional[float]
    concept_override_density_limit: Optional[float]
    is_promoted: bool
    promoted_at: Optional[datetime]
    promoted_project_id: Optional[str]
    promotion_notes: Optional[str]
    # Reverse-lineage — PR-CONCEPT-064
    source_feasibility_run_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConceptOptionListResponse(BaseModel):
    items: List[ConceptOptionResponse]
    total: int


# ---------------------------------------------------------------------------
# ConceptUnitMixLine schemas
# ---------------------------------------------------------------------------

class ConceptUnitMixLineCreate(BaseModel):
    unit_type: str = Field(..., min_length=1, max_length=100)
    units_count: int = Field(..., ge=1)
    avg_internal_area: Optional[float] = Field(default=None, gt=0)
    avg_sellable_area: Optional[float] = Field(default=None, gt=0)
    mix_percentage: Optional[float] = Field(default=None, ge=0, le=100)


class ConceptUnitMixLineResponse(BaseModel):
    id: str
    concept_option_id: str
    unit_type: str
    units_count: int
    avg_internal_area: Optional[float]
    avg_sellable_area: Optional[float]
    mix_percentage: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ConceptOptionSummary — derived metrics from the concept engine
# ---------------------------------------------------------------------------

class ConceptOptionSummaryResponse(BaseModel):
    concept_option_id: str
    name: str
    status: str
    project_id: Optional[str]
    scenario_id: Optional[str]
    # Land / Scenario integration — PR-CONCEPT-060
    land_id: Optional[str]
    # Input overrides (stored on option)
    site_area: Optional[float]
    gross_floor_area: Optional[float]
    building_count: Optional[int]
    floor_count: Optional[int]
    # Zoning constraint inputs — PR-CONCEPT-059
    far_limit: Optional[float]
    density_limit: Optional[float]
    # Land integration overrides — PR-CONCEPT-060
    concept_override_far_limit: Optional[float]
    concept_override_density_limit: Optional[float]
    # Derived from mix lines
    unit_count: int
    sellable_area: Optional[float]
    efficiency_ratio: Optional[float]
    average_unit_area: Optional[float]
    mix_lines: List[ConceptUnitMixLineResponse]


# ---------------------------------------------------------------------------
# Concept Option Comparison schemas — PR-CONCEPT-053
# ---------------------------------------------------------------------------


class ConceptOptionComparisonRowResponse(BaseModel):
    concept_option_id: str
    name: str
    status: str
    unit_count: int
    sellable_area: Optional[float]
    efficiency_ratio: Optional[float]
    average_unit_area: Optional[float]
    building_count: Optional[int]
    floor_count: Optional[int]
    sellable_area_delta_vs_best: Optional[float]
    efficiency_delta_vs_best: Optional[float]
    unit_count_delta_vs_best: int
    is_best_sellable_area: bool
    is_best_efficiency: bool
    is_best_unit_count: bool
    # Financial metrics — PR-CONCEPT-062
    estimated_gdv: Optional[float]
    estimated_revenue_per_sqm: Optional[float]
    estimated_revenue_per_unit: Optional[float]
    gdv_delta_vs_best: Optional[float]
    is_best_gdv: bool


class ConceptOptionComparisonResponse(BaseModel):
    comparison_basis: str
    option_count: int
    best_sellable_area_option_id: Optional[str]
    best_efficiency_option_id: Optional[str]
    best_unit_count_option_id: Optional[str]
    # Financial best — PR-CONCEPT-062
    best_gdv_option_id: Optional[str]
    rows: List[ConceptOptionComparisonRowResponse]


# ---------------------------------------------------------------------------
# Concept Option Promotion schemas — PR-CONCEPT-054
# ---------------------------------------------------------------------------


class ConceptPromotionRequest(BaseModel):
    """Request payload for promoting a concept option into project structuring.

    target_project_id is required when the concept option has no project_id
    already set.  If the concept option is already linked to a project,
    target_project_id must be omitted or match the option's existing project_id;
    supplying a conflicting value will be rejected by validation.

    phase_name overrides the default generated phase name.
    promotion_notes is stored on the concept option for audit purposes.
    """

    target_project_id: Optional[str] = None
    phase_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    promotion_notes: Optional[str] = None


class ConceptPromotionResponse(BaseModel):
    """Response returned after a successful concept option promotion."""

    concept_option_id: str
    promoted_project_id: str
    promoted_phase_id: str
    promoted_phase_name: str
    promoted_at: datetime
    promotion_notes: Optional[str]
    buildings_created: int
    floors_created: int
    units_created: int


# ---------------------------------------------------------------------------
# Seed-Feasibility schemas — PR-CONCEPT-063
# ---------------------------------------------------------------------------


class SeedFeasibilityRequest(BaseModel):
    """Request payload for seeding a feasibility run from a concept option.

    The concept's computed sellable_area is automatically transferred to the
    new feasibility run's assumptions when available.

    Financial assumption fields are optional.  When all three key fields
    (avg_sale_price_per_sqm, construction_cost_per_sqm,
    development_period_months) are provided AND the concept option has a
    computable sellable_area, the assumptions record is persisted on the new
    run and ``assumptions_seeded`` is returned as True.  If any of these
    conditions is missing, the run is still created without assumptions; the
    caller must supply them later via the
    POST /feasibility/runs/{id}/assumptions endpoint.

    scenario_name defaults to a generated label based on the concept option's
    name if omitted.
    """

    scenario_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    avg_sale_price_per_sqm: Optional[float] = Field(default=None, gt=0)
    construction_cost_per_sqm: Optional[float] = Field(default=None, gt=0)
    soft_cost_ratio: float = Field(default=0.10, ge=0, le=1)
    finance_cost_ratio: float = Field(default=0.05, ge=0, le=1)
    sales_cost_ratio: float = Field(default=0.03, ge=0, le=1)
    development_period_months: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = None


class SeedFeasibilityResponse(BaseModel):
    """Response returned after successfully seeding a feasibility run from a concept option.

    seeded_sellable_area_sqm is the value transferred from the concept engine.
    It will be None when the concept option has no unit mix lines with sellable
    area set — in that case the assumptions record is not persisted and the
    caller must supply sellable_area via the assumptions endpoint before
    running a calculation.
    """

    feasibility_run_id: str
    source_concept_option_id: str
    seed_source_type: str
    scenario_name: str
    scenario_id: Optional[str]
    seeded_sellable_area_sqm: Optional[float]
    seeded_unit_count: int
    assumptions_seeded: bool


# ---------------------------------------------------------------------------
# Seed-Concept-from-Feasibility schemas — PR-CONCEPT-064
# ---------------------------------------------------------------------------


class SeedConceptFromFeasibilityResponse(BaseModel):
    """Response returned after successfully creating a concept option from a
    feasibility run.

    Lineage metadata:
    - concept_option_id: the newly created concept option
    - source_feasibility_run_id: the feasibility run that seeded it
    - scenario_id: inherited from the feasibility run (if set)
    - project_id: inherited from the feasibility run (if linked)
    - seed_source_type: always 'feasibility_run' for this flow
    """

    concept_option_id: str
    source_feasibility_run_id: str
    scenario_id: Optional[str]
    project_id: Optional[str]
    seed_source_type: str



# ---------------------------------------------------------------------------
# Lifecycle Lineage / Traceability schemas — PR-CONCEPT-065
# ---------------------------------------------------------------------------


class ConceptLineageResponse(BaseModel):
    """Lifecycle traceability response for a concept option.

    Composes upstream and downstream lineage from canonical lineage fields:
    - source_feasibility_run_id:  the feasibility run that seeded this concept (if any)
    - downstream_feasibility_runs: IDs of feasibility runs seeded from this concept
    - scenario_id:  shared scenario context (if any)
    - project_id:  project context (if any)

    All IDs are sourced from live DB state — no client-side lineage is
    invented here.
    """

    record_type: Literal["concept_option"] = "concept_option"
    record_id: str
    source_feasibility_run_id: Optional[str]
    downstream_feasibility_runs: List[str]
    scenario_id: Optional[str]
    project_id: Optional[str]
