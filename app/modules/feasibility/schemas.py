"""
feasibility.schemas

Pydantic request/response schemas for the Feasibility Engine API.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.core.constants.currency import DEFAULT_CURRENCY
from app.shared.enums.finance import FeasibilityDecision, FeasibilityRiskLevel, FeasibilityScenarioType, FeasibilityViabilityStatus


# ---------------------------------------------------------------------------
# FeasibilityRun schemas
# ---------------------------------------------------------------------------

class FeasibilityRunCreate(BaseModel):
    project_id: Optional[str] = None
    scenario_id: Optional[str] = None
    scenario_name: str = Field(..., min_length=1, max_length=255)
    scenario_type: FeasibilityScenarioType = FeasibilityScenarioType.BASE
    notes: Optional[str] = None
    # Lineage — PR-CONCEPT-063
    source_concept_option_id: Optional[str] = None
    seed_source_type: Optional[str] = None


class FeasibilityRunUpdate(BaseModel):
    project_id: Optional[str] = None
    scenario_name: Optional[str] = Field(None, min_length=1, max_length=255)
    scenario_type: Optional[FeasibilityScenarioType] = None
    notes: Optional[str] = None


class FeasibilityRunResponse(BaseModel):
    id: str
    project_id: Optional[str]
    project_name: Optional[str]
    scenario_id: Optional[str]
    scenario_name: str
    scenario_type: FeasibilityScenarioType
    notes: Optional[str]
    # Lineage — PR-CONCEPT-063
    source_concept_option_id: Optional[str]
    seed_source_type: Optional[str]
    # Lifecycle state — PR-FEAS-03
    status: Literal["draft", "assumptions_defined", "calculated"]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeasibilityRunList(BaseModel):
    items: List[FeasibilityRunResponse]
    total: int


# ---------------------------------------------------------------------------
# FeasibilityAssumptions schemas
# ---------------------------------------------------------------------------

class FeasibilityAssumptionsCreate(BaseModel):
    sellable_area_sqm: float = Field(..., gt=0)
    avg_sale_price_per_sqm: float = Field(..., gt=0)
    construction_cost_per_sqm: float = Field(..., gt=0)
    soft_cost_ratio: float = Field(..., ge=0, le=1)
    finance_cost_ratio: float = Field(..., ge=0, le=1)
    sales_cost_ratio: float = Field(..., ge=0, le=1)
    development_period_months: int = Field(..., ge=1)
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=3)
    notes: Optional[str] = None


class FeasibilityAssumptionsUpdate(BaseModel):
    sellable_area_sqm: Optional[float] = Field(None, gt=0)
    avg_sale_price_per_sqm: Optional[float] = Field(None, gt=0)
    construction_cost_per_sqm: Optional[float] = Field(None, gt=0)
    soft_cost_ratio: Optional[float] = Field(None, ge=0, le=1)
    finance_cost_ratio: Optional[float] = Field(None, ge=0, le=1)
    sales_cost_ratio: Optional[float] = Field(None, ge=0, le=1)
    development_period_months: Optional[int] = Field(None, ge=1)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    notes: Optional[str] = None


class FeasibilityAssumptionsResponse(BaseModel):
    id: str
    run_id: str
    sellable_area_sqm: Optional[float]
    avg_sale_price_per_sqm: Optional[float]
    construction_cost_per_sqm: Optional[float]
    soft_cost_ratio: Optional[float]
    finance_cost_ratio: Optional[float]
    sales_cost_ratio: Optional[float]
    development_period_months: Optional[int]
    currency: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# FeasibilityResult schemas
# ---------------------------------------------------------------------------

class FeasibilityResultResponse(BaseModel):
    id: str
    run_id: str
    gdv: Optional[float]
    construction_cost: Optional[float]
    soft_cost: Optional[float]
    finance_cost: Optional[float]
    sales_cost: Optional[float]
    total_cost: Optional[float]
    developer_profit: Optional[float]
    currency: str
    profit_margin: Optional[float]
    irr_estimate: Optional[float]
    irr: Optional[float]
    equity_multiple: Optional[float]
    break_even_price: Optional[float]
    break_even_units: Optional[float]
    profit_per_sqm: Optional[float]
    scenario_outputs: Optional[dict]
    viability_status: Optional[FeasibilityViabilityStatus]
    risk_level: Optional[FeasibilityRiskLevel]
    decision: Optional[FeasibilityDecision]
    payback_period: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Convenience endpoint schemas
# ---------------------------------------------------------------------------

class FeasibilityRunRequest(BaseModel):
    """Payload for the convenience POST /feasibility/run endpoint."""

    project_id: Optional[str] = None
    scenario_id: Optional[str] = None
    scenario_name: str = Field("Auto Run", min_length=1, max_length=255)
    scenario_type: FeasibilityScenarioType = FeasibilityScenarioType.BASE
    sellable_area_sqm: float = Field(..., gt=0)
    avg_sale_price_per_sqm: float = Field(..., gt=0)
    construction_cost_per_sqm: float = Field(..., gt=0)
    soft_cost_ratio: float = Field(..., ge=0, le=1)
    finance_cost_ratio: float = Field(..., ge=0, le=1)
    sales_cost_ratio: float = Field(..., ge=0, le=1)
    development_period_months: int = Field(..., ge=1)
    currency: str = Field(
        default=DEFAULT_CURRENCY,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code for all monetary inputs (e.g. 'AED', 'USD').",
    )
    notes: Optional[str] = None



# ---------------------------------------------------------------------------
# Lifecycle Lineage / Traceability schemas — PR-CONCEPT-065
# ---------------------------------------------------------------------------


class FeasibilityLineageResponse(BaseModel):
    """Lifecycle traceability response for a feasibility run.

    Composes upstream and downstream lineage from canonical lineage fields:
    - source_concept_option_id:        concept option that seeded this run (if any)
    - reverse_seeded_concept_options:  IDs of concept options seeded from this run
    - project_id:                      project context (if any)

    All IDs are sourced from live DB state — no client-side lineage is
    invented here.
    """

    record_type: Literal["feasibility_run"] = "feasibility_run"
    record_id: str
    source_concept_option_id: Optional[str]
    reverse_seeded_concept_options: List[str]
    project_id: Optional[str]


# ---------------------------------------------------------------------------
# Construction cost context — PR-V6-10
# ---------------------------------------------------------------------------


class FeasibilityConstructionCostContextResponse(BaseModel):
    """Read-only construction cost context for a feasibility run.

    Surfaces recorded construction cost totals alongside the feasibility-side
    assumed construction cost so reviewers can compare both without any
    auto-recalculation of feasibility results.

    Fields are null-safe — partial data (e.g. run has no project, or project
    has no cost records) is reflected via nulls and an explanatory ``note``.
    The ``note`` is always populated with a human-readable summary of the
    comparison state.

    Forbidden:
    - This schema must not be used to write back to feasibility or construction
      records.
    - Variance fields are transparent arithmetic only; they are not financial
      formula outputs.
    """

    feasibility_run_id: str
    project_id: Optional[str]

    # Recorded side — sourced from construction cost records (active only)
    has_cost_records: bool
    active_record_count: int
    recorded_construction_cost_total: Optional[Decimal]
    by_category: Optional[Dict[str, Decimal]]
    by_stage: Optional[Dict[str, Decimal]]

    # Feasibility-side assumption — construction_cost_per_sqm × sellable_area_sqm
    # Null when assumptions have not been defined yet.
    assumed_construction_cost: Optional[float]

    # Variance (recorded − assumed) — populated only when both sides exist
    variance_amount: Optional[Decimal]
    variance_pct: Optional[float]

    # Human-readable summary of comparison state
    note: str
