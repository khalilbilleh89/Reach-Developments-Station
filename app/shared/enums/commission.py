"""Commission-related enumerations."""

from enum import Enum


class CalculationMode(str, Enum):
    MARGINAL = "marginal"
    CUMULATIVE = "cumulative"


class CommissionPayoutStatus(str, Enum):
    DRAFT = "draft"
    CALCULATED = "calculated"
    APPROVED = "approved"
    CANCELLED = "cancelled"


class CommissionPartyType(str, Enum):
    SALES_REP = "sales_rep"
    TEAM_LEAD = "team_lead"
    MANAGER = "manager"
    BROKER = "broker"
    PLATFORM = "platform"
