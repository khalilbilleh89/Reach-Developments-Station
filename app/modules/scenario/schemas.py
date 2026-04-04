"""
scenario.schemas

Pydantic request/response schemas for the Scenario Engine API.

All payloads are strongly typed.  ORM models are never leaked directly.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.constants.currency import DEFAULT_CURRENCY
from app.core.constants.scenario import DEFAULT_SCENARIO_SOURCE_TYPE


# ---------------------------------------------------------------------------
# Scenario schemas
# ---------------------------------------------------------------------------


class ScenarioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=100)
    source_type: str = Field(DEFAULT_SCENARIO_SOURCE_TYPE, max_length=50)
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


# ---------------------------------------------------------------------------
# Financial scenario run schemas
# ---------------------------------------------------------------------------


class FinancialScenarioAssumptionsSchema(BaseModel):
    """Request schema for financial scenario assumptions.

    Mirrors FinancialScenarioAssumptions in the engine but is a Pydantic model
    for HTTP request/response serialisation.
    """

    gdv: float = Field(..., gt=0, description="Gross Development Value")
    total_cost: float = Field(..., gt=0, description="Total development cost")
    equity_invested: float = Field(..., ge=0, description="Equity portion of funding")
    sellable_area_sqm: float = Field(..., gt=0, description="Sellable floor area in sqm")
    avg_sale_price_per_sqm: float = Field(
        ..., gt=0, description="Average sale price per sqm"
    )
    development_period_months: int = Field(
        ..., gt=0, description="Development period in months"
    )
    annual_discount_rate: float = Field(
        default=0.10, ge=0.0, lt=1.0, description="Annual discount rate for NPV"
    )
    sales_pace_months_override: Optional[int] = Field(
        default=None, gt=0, description="Override sales period (slower/faster sales case)"
    )
    pricing_uplift_pct: Optional[float] = Field(
        default=None, description="Price increase fraction (e.g. 0.05 = +5%)"
    )
    cost_inflation_pct: Optional[float] = Field(
        default=None, description="Cost inflation fraction (e.g. 0.10 = +10%)"
    )
    debt_ratio: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Debt fraction of total funding"
    )
    label: str = Field(default="Base Case", min_length=1, max_length=255)
    notes: Optional[str] = None
    currency: str = Field(
        default=DEFAULT_CURRENCY,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code for all monetary inputs (e.g. 'AED', 'USD').",
    )


class FinancialScenarioRunCreate(BaseModel):
    """Request payload for creating and executing a financial scenario run."""

    assumptions: FinancialScenarioAssumptionsSchema
    overrides: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Override values merged on top of baseline assumptions. "
            "Only keys matching FinancialScenarioAssumptions fields are applied."
        ),
    )
    is_baseline: bool = Field(
        default=False,
        description="Mark this run as the baseline for comparison purposes.",
    )


class FinancialScenarioReturnMetrics(BaseModel):
    """Return and profitability metrics produced by the Calculation Engine."""

    gross_profit: float
    developer_margin: float
    roi: float
    roe: float
    irr: float
    npv: float
    equity_multiple: float
    payback_period_months: float
    break_even_price_per_sqm: float
    break_even_sellable_sqm: float


class FinancialScenarioRunResponse(BaseModel):
    """Response schema for a persisted financial scenario run."""

    id: str
    scenario_id: str
    label: str
    notes: Optional[str]
    is_baseline: bool
    assumptions_json: Optional[Dict[str, Any]]
    results_json: Optional[Dict[str, Any]]
    irr: Optional[float]
    npv: Optional[float]
    roi: Optional[float]
    developer_margin: Optional[float]
    gross_profit: Optional[float]
    currency: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FinancialScenarioRunList(BaseModel):
    """Paginated list of financial scenario runs."""

    items: List[FinancialScenarioRunResponse]
    total: int


class FinancialScenarioCompareRequest(BaseModel):
    """Request to compare a list of financial scenario run IDs side-by-side."""

    run_ids: List[str] = Field(
        ..., min_length=2, description="At least two run IDs to compare."
    )


class FinancialScenarioRunDelta(BaseModel):
    """Delta metrics for a single run relative to the baseline run."""

    run_id: str
    label: str
    gross_profit_delta: float
    developer_margin_delta: float
    roi_delta: float
    roe_delta: float
    irr_delta: float
    npv_delta: float
    equity_multiple_delta: float
    payback_period_months_delta: float


class FinancialScenarioCompareResponse(BaseModel):
    """Side-by-side comparison of multiple financial scenario runs."""

    baseline_run_id: str
    baseline_label: str
    runs: List[FinancialScenarioRunResponse]
    deltas: List[FinancialScenarioRunDelta]
