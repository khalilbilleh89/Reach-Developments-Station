"""Explicit context, coverage and Decimal results for management reads."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class Context(BaseModel):
    project_id: uuid.UUID
    as_of: date
    period_from: date
    period_to: date
    filters: dict[str, str | None]
    currency: str
    source_basis: str
    snapshot_as_of: date


class Availability(BaseModel):
    availability: Literal["available", "partial", "unavailable"] = "available"
    reason: str | None = None
    source_basis: str
    sample_size: int = 0


class Ratio(Availability):
    numerator: int | None = None
    denominator: int | None = None
    percentage: Decimal | None = None


class Money(BaseModel):
    currency: str
    amount: Decimal


class Demand(Availability):
    label: str
    inventory_count: int
    sales_count: int
    demand_share: Ratio
    penetration: Ratio


class Ranking(Availability):
    source_key: str | None = None
    label: str
    sales_count: int
    contracted_value: list[Money]
    share: Ratio


class Month(BaseModel):
    month: date
    activations: int = 0
    cancellations: int = 0
    net_absorption: int = 0
    contracted_value: list[Money] = Field(default_factory=list)


class Forecast(Availability):
    window_from: date
    window_to: date
    observed_months: int
    monthly_net_absorption: list[int]
    remaining_units: int | None
    average_monthly_absorption: Decimal | None = None
    estimated_months_to_sell: Decimal | None = None


class Position(Availability):
    total_units: int
    eligible_units: int
    available_units: int
    committed_units: int
    active_sold_units: int
    remaining_units: int
    commercial: dict[str, int]
    legal: dict[str, int]
    delivery: dict[str, int]
    penetration: Ratio


class Premium(Availability):
    property_type: str
    view: str
    baseline: str
    currency: str | None = None
    area_unit: str | None = None
    baseline_sample: int
    view_price_per_gross_area: Decimal | None = None
    baseline_price_per_gross_area: Decimal | None = None
    percentage: Decimal | None = None


class Fundamental(BaseModel):
    context: Context
    position: Position
    monthly_sales: list[Month]
    sales_basis: Availability
    branches: list[Ranking]
    salespeople: list[Ranking]
    ranking_basis: Availability
    forecast: Forecast
    property_types: list[Demand]
    views: list[Demand]
    view_basis: Availability
    observed_premiums: list[Premium]


class CashMonth(BaseModel):
    month: date
    currency: str
    new_sales_count: int = 0
    contracted_sales_value: Decimal = Decimal("0")
    customer_cash_received: Decimal = Decimal("0")
    project_cash_outflow: Decimal = Decimal("0")
    customer_refunds: Decimal = Decimal("0")
    financing_inflow: Decimal = Decimal("0")
    financing_outflow: Decimal = Decimal("0")
    net_actual_cash_movement: Decimal = Decimal("0")


class Financial(BaseModel):
    context: Context
    basis: Availability
    cash_scope: str
    monthly: list[CashMonth]


class Area(Availability):
    component: str
    unit_of_measure: str
    minimum: Decimal
    maximum: Decimal
    average: Decimal


class Technical(BaseModel):
    context: Context
    basis: Availability
    product_types: dict[str, int]
    areas: list[Area]
    area_coverage: Availability
    features: dict[str, int]
    feature_coverage: Ratio
    attachments: dict[str, int]
    permits: dict[str, int]
    permit_basis: Availability
    consultant: dict[str, str | int | None]
    consultant_basis: Availability
    construction_stages: list[dict[str, str | int]]
    construction_basis: Availability
