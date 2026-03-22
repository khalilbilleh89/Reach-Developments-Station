"""
app.core.calculation_engine.types

Typed input/output dataclass contracts for the Calculation Engine.

All engine functions accept and return these dataclasses so consumers have
a stable, versioned interface that is independent of any ORM, HTTP, or
persistence concern.

No database access, service orchestration, or HTTP logic belongs here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Area contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AreaInputs:
    """Inputs required to compute derived area metrics."""

    land_area_sqm: float
    permitted_far: float  # floor-area ratio, e.g. 2.5 = 250 % buildable
    sellable_ratio: float  # fraction of buildable area that is sellable, e.g. 0.85


@dataclass(frozen=True)
class AreaOutputs:
    """Derived area metrics produced by the areas engine."""

    buildable_area_sqm: float
    sellable_area_sqm: float


# ---------------------------------------------------------------------------
# Pricing contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PricingInputs:
    """Inputs required to compute a unit's final selling price."""

    internal_area_sqm: float
    base_price_per_sqm: float
    attached_area_sqm: float = 0.0
    attached_area_rate_per_sqm: float = 0.0  # discounted rate for balcony/terrace
    floor_premium: float = 0.0
    view_premium: float = 0.0
    corner_premium: float = 0.0
    size_adjustment: float = 0.0
    custom_adjustment: float = 0.0
    escalation_rate: float = 0.0  # decimal fraction, e.g. 0.05 for 5 %
    discount_amount: float = 0.0  # absolute currency amount


@dataclass(frozen=True)
class PricingOutputs:
    """Derived pricing metrics for a single unit."""

    base_unit_price: float
    attached_area_price: float
    premium_total: float
    pre_escalation_price: float
    escalated_price: float
    final_unit_price: float  # escalated price minus discount


# ---------------------------------------------------------------------------
# Return / profitability contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReturnInputs:
    """Inputs required to compute project return and profitability metrics."""

    gdv: float  # Gross Development Value
    total_cost: float  # total project cost (construction + soft + finance + sales)
    equity_invested: float  # equity portion of project funding
    sellable_area_sqm: float  # used for break-even price per sqm
    avg_sale_price_per_sqm: float  # used for break-even sellable sqm calculation
    development_period_months: int  # used for IRR cashflow model


@dataclass(frozen=True)
class ReturnOutputs:
    """Derived return and profitability metrics."""

    gross_profit: float
    developer_margin: float  # gross_profit / gdv
    roi: float  # gross_profit / total_cost
    roe: float  # gross_profit / equity_invested  (0.0 when equity_invested == 0)
    irr: float  # annualised IRR from development cashflow model
    npv: float  # NPV at the discount rate used during calculation
    equity_multiple: float  # gdv / total_cost
    payback_period_months: float  # months to recover total_cost from equal monthly revenue
    break_even_price_per_sqm: float  # total_cost / sellable_area_sqm
    break_even_sellable_sqm: float  # total_cost / avg_sale_price_per_sqm


# ---------------------------------------------------------------------------
# Cashflow contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CashflowInputs:
    """Monthly inflow and outflow arrays for cashflow analysis."""

    monthly_inflows: List[float] = field(default_factory=list)
    monthly_outflows: List[float] = field(default_factory=list)


@dataclass(frozen=True)
class CashflowOutputs:
    """Derived cashflow metrics over the analysis period."""

    net_monthly: List[float]
    cumulative: List[float]
    total_inflow: float
    total_outflow: float
    peak_deficit: float  # most negative cumulative value; 0.0 when always positive
    months_to_breakeven: int  # first month where cumulative >= 0; -1 if never


# ---------------------------------------------------------------------------
# Land underwriting contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LandInputs:
    """Inputs required to compute land underwriting metrics."""

    land_area_sqm: float
    acquisition_price: float  # total land acquisition cost
    buildable_area_sqm: float
    sellable_area_sqm: float
    gdv: float
    total_development_cost: float  # excluding land acquisition
    developer_margin_target: float  # decimal fraction, e.g. 0.20 for 20 %


@dataclass(frozen=True)
class LandOutputs:
    """Derived land underwriting metrics."""

    land_price_per_sqm: float  # acquisition_price / land_area_sqm
    land_price_per_buildable_sqm: float  # acquisition_price / buildable_area_sqm
    land_price_per_sellable_sqm: float  # acquisition_price / sellable_area_sqm
    residual_land_value: float  # gdv - total_development_cost - target_profit
    max_supported_acquisition_price: float  # same as residual_land_value
    margin_impact: float  # residual_land_value / gdv
