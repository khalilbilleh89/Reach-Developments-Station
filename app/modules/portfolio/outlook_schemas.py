"""Current owner observations, with explicit horizon and coverage."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.project_analysis.schemas import Forecast

Kind = Literal[
    "commercial_sellout",
    "scheduled_collection_due",
    "cashflow_forecast",
    "construction_eac",
    "permit_due",
    "consultant_stage_due",
    "consultant_deliverable_due",
    "management_action_due",
]


class Item(BaseModel):
    source_key: str
    item_type: Kind
    project_id: uuid.UUID
    project_code: str
    project_name: str
    title: str
    due_date: date | None = None
    observation_date: date
    availability: Literal["available", "partial", "unavailable"] = "available"
    reason: str | None = None
    basis: str
    currency: str | None = None
    amount: Decimal | None = None
    source_version_id: uuid.UUID | None = None
    source_as_of: date | None = None
    status: str | None = None
    blocking: bool | None = None
    planned_date: date | None = None
    forecast_date: date | None = None
    actual_date: date | None = None
    lowpoint_month: date | None = None
    first_deficit_month: date | None = None
    peak_deficit: Decimal | None = None
    forecast_end_month: date | None = None
    control_budget: Decimal | None = None
    budget_version_id: uuid.UUID | None = None
    commercial: Forecast | None = None
    owner_user_id: uuid.UUID | None = None
    owner_display_name: str | None = None
    drilldown: str


class CurrencyBucket(BaseModel):
    currency: str
    scheduled_outstanding_due: Decimal = Decimal(0)
    contributing_project_count: int = 0
    unavailable_project_count: int = 0


class Coverage(BaseModel):
    source: str
    unavailable_project_count: int = 0
    undated_item_count: int = 0
    reason: str


class Outlook(BaseModel):
    as_of: date
    horizon_days: Literal[30, 60, 90]
    horizon_end: date
    date_basis: str = (
        "UTC business date; dated items include today through horizon end, "
        "inclusive. Overdue open management actions are also included."
    )
    cashflow_basis: str = (
        "FORECAST: governed monthly closing positions for calendar months "
        "intersecting the horizon, including full boundary months; no daily "
        "proration."
    )
    authorized_project_count: int
    summary_counts: dict[str, int] = Field(default_factory=dict)
    currency_buckets: list[CurrencyBucket] = Field(default_factory=list)
    coverage: list[Coverage] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)
    total: int = 0
    offset: int
    limit: int
