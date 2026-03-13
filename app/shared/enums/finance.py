"""Finance-related enumerations."""

from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    PARTIALLY_PAID = "partially_paid"


class MilestoneTriggerType(str, Enum):
    TIME_BASED = "time_based"
    CONSTRUCTION_MILESTONE = "construction_milestone"
    SALES_MILESTONE = "sales_milestone"


class FeasibilityScenarioType(str, Enum):
    BASE = "base"
    UPSIDE = "upside"
    DOWNSIDE = "downside"
    INVESTOR = "investor"
