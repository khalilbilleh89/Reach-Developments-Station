"""
finance.revenue_models

Data structures for the Revenue Recognition Engine.

These are pure data-transfer objects used to pass information between
the service layer and the calculation engine.  No database access occurs
in this module.

Recognition strategies
----------------------
ON_CONTRACT_SIGNING
    Revenue is recognized in the calendar month that the sales contract
    was signed.  This is the simplest strategy and requires no additional
    data beyond the contract date.

ON_CONSTRUCTION_PROGRESS
    Revenue is recognized proportionally as construction milestones are
    reached.  The proportion of the contract price recognized each period
    equals the construction-completion percentage for that period.  When
    milestone data is unavailable the engine falls back to equal monthly
    distribution across the construction duration.

ON_UNIT_DELIVERY
    Revenue is recognized in full in the calendar month that the unit is
    delivered to the buyer (i.e. handover date).  Contracts without a
    delivery date are deferred to the last month of the schedule window.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional


class RecognitionStrategy(str, Enum):
    """Supported revenue recognition strategies."""

    ON_CONTRACT_SIGNING = "on_contract_signing"
    ON_CONSTRUCTION_PROGRESS = "on_construction_progress"
    ON_UNIT_DELIVERY = "on_unit_delivery"


@dataclass(frozen=True)
class UnitSaleData:
    """Raw data for a single unit sale required by the recognition engine.

    Attributes
    ----------
    contract_id:
        Unique identifier of the sales contract.
    contract_total:
        Full price agreed in the contract (before any discounts that are
        applied at payment-schedule level).
    contract_date:
        Calendar date on which the contract was signed.  Used by the
        ON_CONTRACT_SIGNING strategy.
    delivery_date:
        Expected or actual unit handover date.  Used by the
        ON_UNIT_DELIVERY strategy.  May be None when not yet set.
    construction_completion_by_period:
        Mapping of calendar month (``YYYY-MM``) → cumulative completion
        percentage (0–100).  Used by the ON_CONSTRUCTION_PROGRESS
        strategy.  Empty when milestones are unavailable.
    """

    contract_id: str
    contract_total: float
    contract_date: date
    delivery_date: Optional[date] = None
    construction_completion_by_period: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RevenueScheduleInput:
    """All inputs required to generate a revenue schedule for a scenario.

    Attributes
    ----------
    scenario_id:
        The ID of the originating scenario.
    unit_sales:
        List of unit sale records to include in the schedule.
    strategy:
        Recognition strategy to apply.
    """

    scenario_id: str
    unit_sales: List[UnitSaleData]
    strategy: RecognitionStrategy = RecognitionStrategy.ON_CONTRACT_SIGNING


@dataclass(frozen=True)
class RevenueScheduleEntry:
    """Revenue recognized in a single calendar period.

    Attributes
    ----------
    period:
        Calendar month in ``YYYY-MM`` format.
    revenue:
        Total revenue recognized in this period (rounded to 2 d.p.).
    """

    period: str
    revenue: float


@dataclass(frozen=True)
class RevenueScheduleResult:
    """Computed revenue schedule for a scenario.

    Attributes
    ----------
    scenario_id:
        The originating scenario identifier.
    strategy:
        Name of the recognition strategy that was applied.
    revenue_schedule:
        Chronologically ordered list of period-revenue entries.
    total_revenue:
        Sum of all period revenues (convenience field).
    """

    scenario_id: str
    strategy: str
    revenue_schedule: List[RevenueScheduleEntry]
    total_revenue: float
