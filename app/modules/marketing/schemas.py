"""Closed, bounded marketing inputs. Percentage fields use percent, not fractions."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=320)]
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=9, decimal_places=4)]
Growth = Annotated[Decimal, Field(gt=-100, le=100, max_digits=9, decimal_places=4)]


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Narrative(Request):
    paragraph: Text = ""
    bullets: list[Label] = Field(default_factory=list, max_length=50)


class Nearby(Request):
    name: Label
    duration_minutes: int | None = Field(default=None, ge=0, le=10080)
    travel_mode: Literal["drive", "walk", "transit", "cycle"] = "drive"
    note: Text = ""


class Bio(Request):
    country: Narrative = Field(default_factory=Narrative)
    area: Narrative = Field(default_factory=Narrative)
    project: Narrative = Field(default_factory=Narrative)
    location: Narrative = Field(default_factory=Narrative)
    nearby: list[Nearby] = Field(default_factory=list, max_length=100)
    amenities: list[Label] = Field(default_factory=list, max_length=100)
    roi_min_percent: Percent | None = None
    roi_max_percent: Percent | None = None
    roi_basis: Text = ""
    source: Text = ""
    as_of: date | None = None

    @model_validator(mode="after")
    def roi_range(self) -> "Bio":
        lo, hi = self.roi_min_percent, self.roi_max_percent
        if (lo is None) != (hi is None) or (lo is not None and hi is not None and lo > hi):
            raise ValueError("Enter both ROI range limits, with minimum no greater than maximum.")
        if lo is not None and (not self.roi_basis or not self.source or not self.as_of):
            raise ValueError("An ROI range requires its period/basis, source and as-at date.")
        return self


class BrandColor(Request):
    name: Label
    hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    usage: Text = ""


class BrandFont(Request):
    family: Label
    usage: Text = ""


class Branding(Request):
    project_name: Text = ""
    name_definition: Text = ""
    colors: list[BrandColor] = Field(default_factory=list, max_length=30)
    fonts: list[BrandFont] = Field(default_factory=list, max_length=20)
    source: Text = ""
    as_of: date | None = None


class ContentWrite(Request):
    expected_version: int = Field(ge=0)
    data: Bio | Branding


class ContentRead(BaseModel):
    version: int
    data: Bio | Branding


class ScenarioWrite(Request):
    expected_version: int = Field(default=0, ge=0)
    unit_id: uuid.UUID | None = None
    mode: Literal["long_term", "short_term"]
    area_basis: Literal["net", "gross"] = "net"
    currency_id: uuid.UUID
    annual_rent_per_sqm: Money
    annual_expense_per_sqm: Money
    vacancy_percent: Percent
    income_growth_percent: Growth
    expense_growth_percent: Growth
    appreciation_percent: Growth
    exit_cap_percent: Annotated[Decimal, Field(gt=0, le=100, decimal_places=4)]
    discount_percent: Percent
    acquisition_cost_percent: Percent
    selling_cost_percent: Percent
    setup_cost: Money
    price_override: Money | None = None
    exit_method: Literal["appreciation", "cap_rate"] = "appreciation"
    source: Label
    as_of: date

    @model_validator(mode="after")
    def specific_price(self) -> "ScenarioWrite":
        if self.price_override is not None and (not self.unit_id or self.price_override <= 0):
            raise ValueError("A positive purchase price override belongs to an individual unit.")
        return self


class ScenarioRead(ScenarioWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    unit_reference: str | None = None


class IndicatorWrite(Request):
    expected_version: int = Field(default=0, ge=0)
    name: Label
    geography: Label
    value: Annotated[Decimal, Field(max_digits=18, decimal_places=4)]
    unit: Label
    period: Label
    as_of: date
    source: Label
    commentary: Text = ""


class IndicatorRead(IndicatorWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int


class Removal(Request):
    expected_version: int = Field(ge=1)
    reason: Label


class ProjectionYear(BaseModel):
    year: int
    gross_revenue: Decimal
    vacancy_amount: Decimal
    effective_revenue: Decimal
    expenses: Decimal
    noi: Decimal
    property_value: Decimal
    cashflow: Decimal


class Projection(BaseModel):
    initial_investment: Decimal
    gross_yield_percent: Decimal
    net_yield_percent: Decimal
    monthly_potential_revenue: Decimal
    appreciation_value: Decimal
    capital_gain: Decimal
    cap_value: Decimal
    sale_proceeds: Decimal
    roi_percent: Decimal
    irr_percent: Decimal | None
    irr_reason: str | None
    npv: Decimal
    simple_payback_years: Decimal | None
    rental_payback_years: Decimal | None
    total_payback_year: int | None
    years: list[ProjectionYear]


class UnitScenario(BaseModel):
    mode: str
    scenario_id: uuid.UUID | None = None
    source_scope: str | None = None
    area_sqm: Decimal | None = None
    price: Decimal | None = None
    price_basis: str | None = None
    currency_id: uuid.UUID | None = None
    unavailable: str | None = None
    projection: Projection | None = None


class UnitResult(BaseModel):
    unit_id: uuid.UUID
    reference: str
    scenarios: list[UnitScenario]


class UnitRegister(BaseModel):
    total: int
    units: list[UnitResult]
