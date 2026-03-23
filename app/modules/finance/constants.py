"""
finance.constants

Shared constants for the finance module.

Centralises status lists, enumerations, and other invariants used across
multiple services to prevent drift if additional statuses are introduced
in the future.
"""

from enum import Enum

from app.shared.enums.sales import ContractPaymentStatus

# Installment statuses that represent collectible outstanding receivables.
# CANCELLED installments are not receivable obligations and are excluded.
RECEIVABLE_STATUSES = [
    ContractPaymentStatus.PENDING.value,
    ContractPaymentStatus.OVERDUE.value,
]

# ---------------------------------------------------------------------------
# Cashflow forecast enumerations
# ---------------------------------------------------------------------------


class ForecastGranularity(str, Enum):
    """Time-bucket granularity for cashflow forecast periods."""

    MONTHLY = "monthly"


class ForecastScopeType(str, Enum):
    """Scope level at which a cashflow forecast is computed."""

    CONTRACT = "contract"
    PROJECT = "project"
    PORTFOLIO = "portfolio"


class ForecastMode(str, Enum):
    """Forecast assumption mode controlling expected-collection probability.

    DETERMINISTIC
        100% collection probability for all outstanding installments.
        Overdue carry-forward applied when carry_forward_overdue is True.
        This is the default mode for PR-33.

    PROBABILISTIC
        Expected collections scaled by the caller-supplied
        default_collection_probability (0–1).
    """

    DETERMINISTIC = "deterministic"
    PROBABILISTIC = "probabilistic"


# ---------------------------------------------------------------------------
# Cashflow forecast defaults
# ---------------------------------------------------------------------------

# Default collection probability used in DETERMINISTIC mode.
DEFAULT_COLLECTION_PROBABILITY: float = 1.0

# When True, installments overdue before the forecast window are carried
# into the first period of the window by default.
DEFAULT_CARRY_FORWARD_OVERDUE: bool = True
