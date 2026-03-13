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


# ---------------------------------------------------------------------------
# Payment plan enumerations
# ---------------------------------------------------------------------------


class PaymentPlanType(str, Enum):
    """Classification of the payment plan structure."""

    STANDARD_INSTALLMENTS = "standard_installments"
    MILESTONE = "milestone"
    POST_HANDOVER = "post_handover"
    CUSTOM = "custom"


class InstallmentFrequency(str, Enum):
    """Frequency at which installment due dates are generated."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CUSTOM = "custom"


class PaymentScheduleStatus(str, Enum):
    """Status of a single payment schedule line."""

    PENDING = "pending"
    DUE = "due"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
