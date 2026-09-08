"""Management facts, source provenance and explicit coverage. No calculations."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.project_analysis.schemas import Forecast, Ratio

Availability = Literal["available", "partial", "unavailable"]


class MoneyMetric(BaseModel):
    metric_code: str
    currency: str
    amount: Decimal | None
    availability: Availability
    reason: str | None = None
    contributing_project_count: int = 0
    missing_project_count: int = 0
    source_basis: str
    source_version_id: uuid.UUID | None = None
    drilldown: str


class Evaluation(BaseModel):
    risk_code: str
    availability: Availability
    reason: str | None = None


class Risk(BaseModel):
    risk_id: str
    risk_code: str
    category: str
    severity: Literal["high", "attention"]
    project_id: uuid.UUID
    project_code: str
    project_name: str
    title: str
    reason: str
    source_metric: str
    source_value: str
    currency: str | None = None
    basis: str
    observation_date: date
    availability: Literal["available"] = "available"
    drilldown: str


class Design(BaseModel):
    availability: Availability
    reason: str | None = None
    engagement_id: uuid.UUID | None = None
    consultant_name: str | None = None
    current_stage: str | None = None
    planned_date: date | None = None
    forecast_date: date | None = None
    actual_date: date | None = None
    stage_status: str | None = None
    stage_count: int = 0
    deliverable_count: int = 0


class ProjectSummary(BaseModel):
    project_id: uuid.UUID
    code: str
    name: str
    status: str
    currency: str
    as_of: date
    total_units: int
    eligible_units: int
    available_units: int
    committed_units: int
    active_sold_units: int
    remaining_units: int
    sales_penetration: Ratio
    sales_run_rate: Forecast
    money: list[MoneyMetric]
    cashflow_reason_code: str | None = None
    cashflow_observed_currencies: list[str]
    permit_count: int
    design: Design
    risks: list[Risk]
    risk_evaluations: list[Evaluation]
    risk_count: int
    highest_risk: Literal["high", "attention"] | None = None
    coverage: Availability
    drilldown: str


class ProjectPage(BaseModel):
    as_of: date
    items: list[ProjectSummary]
    total: int
    offset: int
    limit: int


class RiskPage(BaseModel):
    as_of: date
    items: list[Risk]
    total: int
    offset: int
    limit: int
    unavailable_project_count: int


class Overview(BaseModel):
    as_of: date
    project_count: int
    projects_requiring_attention: int
    projects_with_incomplete_coverage: int
    eligible_units: int
    committed_units: int
    active_sold_units: int
    sales_penetration: Ratio
    money: list[MoneyMetric]
    risk_count: int
    priority_risks: list[Risk]
    unavailable_risk_evaluations: dict[str, int] = Field(default_factory=dict)
    source_basis: str = (
        "Current authorized whole-project state; monetary "
        "totals remain separated by source currency."
    )
