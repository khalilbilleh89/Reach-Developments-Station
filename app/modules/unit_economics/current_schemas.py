"""Current cost analysis: exact amounts, explicit source coverage, no writable totals."""

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.projects.schemas import StrictRequest
from app.modules.unit_economics.schemas import DecimalStr, Money, SignedMoney

Rate = Annotated[DecimalStr, Field(ge=0, le=1, max_digits=9, decimal_places=6)]


class CostSettingsInputs(StrictRequest):
    gross_area_type_id: uuid.UUID
    supplemental_soft_cost: Money | None = None
    additional_cost: Money | None = None
    finance_cost: Money | None = None
    commission_rate_fraction: Rate | None = None
    profit_tax_rate_fraction: Rate | None = None
    notes: str | None = Field(default=None, max_length=1000)


class CostSettingsWrite(CostSettingsInputs):
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)


class CostSettingsRead(CostSettingsInputs):
    model_config = ConfigDict(from_attributes=True)
    currency_id: uuid.UUID
    revision: int


class CostFigures(BaseModel):
    gross_area_sqm: DecimalStr | None = None
    hard_cost: Money | None = None
    hard_cost_per_sqm: Money | None = None
    land_cost: Money | None = None
    soft_cost: Money | None = None
    additional_cost: Money | None = None
    finance_cost: Money | None = None
    direct_cost: Money | None = None
    seller_cost: Money | None = None
    commission_cost: Money | None = None
    total_cost: Money | None = None
    total_cost_per_sqm: Money | None = None
    revenue: Money | None = None
    profit_before_tax: SignedMoney | None = None
    tax_amount: Money | None = None
    net_profit: SignedMoney | None = None


class CurrentUnitCost(CostFigures):
    unit_id: uuid.UUID
    unit_reference: str
    building_id: uuid.UUID
    building_name: str
    floor_id: uuid.UUID | None
    floor_name: str
    sale_id: uuid.UUID | None
    revenue_basis: Literal["sold", "asking_price", "unavailable"]
    commission_basis: str
    issues: list[str]


class CurrentCostGroup(CostFigures):
    id: str
    label: str
    building_id: uuid.UUID | None = None
    unit_count: int
    sold_count: int
    cost_complete_count: int
    net_profit_complete_count: int
    sold_revenue: Money | None = None
    forecast_revenue: Money | None = None


class CostSource(BaseModel):
    category: str
    reference: str
    amount: Money | None


class CurrentCostAnalysis(BaseModel):
    as_of_date: date
    currency_id: uuid.UUID
    currency_code: str
    gross_area_label: str | None
    settings: CostSettingsRead | None
    issues: list[str]
    sources: list[CostSource]
    units: list[CurrentUnitCost]
    buildings: list[CurrentCostGroup]
    floors: list[CurrentCostGroup]
    project: CurrentCostGroup
