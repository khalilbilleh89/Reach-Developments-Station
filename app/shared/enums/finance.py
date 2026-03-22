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


# ---------------------------------------------------------------------------
# Collections / receivables enumerations
# ---------------------------------------------------------------------------


class ReceiptStatus(str, Enum):
    """Lifecycle status of a payment receipt."""

    RECORDED = "recorded"
    REVERSED = "reversed"


class ReceivableStatus(str, Enum):
    """Lifecycle status of a receivable record."""

    PENDING = "pending"
    DUE = "due"
    OVERDUE = "overdue"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    """Method used to settle a payment receipt."""

    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"
    CHEQUE = "cheque"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Collections alerts enumerations
# ---------------------------------------------------------------------------


class AlertSeverity(str, Enum):
    """Severity tier of a collections alert."""

    WARNING = "warning"
    CRITICAL = "critical"
    HIGH_RISK = "high_risk"


class AlertType(str, Enum):
    """Lifecycle type of a collections alert."""

    OVERDUE_7_DAYS = "overdue_7_days"
    OVERDUE_30_DAYS = "overdue_30_days"
    OVERDUE_90_DAYS = "overdue_90_days"


# ---------------------------------------------------------------------------
# Receipt matching enumerations
# ---------------------------------------------------------------------------


class MatchStrategy(str, Enum):
    """Strategy used when matching a payment to installments."""

    EXACT = "exact"
    PARTIAL = "partial"
    MULTI_INSTALLMENT = "multi_installment"
    UNMATCHED = "unmatched"


# ---------------------------------------------------------------------------
# Financial risk alert enumerations
# ---------------------------------------------------------------------------


class RiskAlertSeverity(str, Enum):
    """Severity tier of a financial risk alert produced by the alert engine."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RiskAlertType(str, Enum):
    """Machine-readable category keys for financial risk alerts."""

    OVERDUE_EXPOSURE = "OVERDUE_EXPOSURE"
    COLLECTION_EFFICIENCY_COLLAPSE = "COLLECTION_EFFICIENCY_COLLAPSE"
    RECEIVABLES_SURGE = "RECEIVABLES_SURGE"
    LIQUIDITY_STRESS = "LIQUIDITY_STRESS"


# ---------------------------------------------------------------------------
# Feasibility viability enumerations
# ---------------------------------------------------------------------------


class FeasibilityViabilityStatus(str, Enum):
    """Overall viability rating produced by the feasibility evaluation."""

    VIABLE = "VIABLE"
    MARGINAL = "MARGINAL"
    NOT_VIABLE = "NOT_VIABLE"


class FeasibilityRiskLevel(str, Enum):
    """Risk level associated with a feasibility evaluation."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FeasibilityDecision(str, Enum):
    """Decision recommendation produced by the feasibility engine."""

    VIABLE = "VIABLE"
    MARGINAL = "MARGINAL"
    NOT_VIABLE = "NOT_VIABLE"
