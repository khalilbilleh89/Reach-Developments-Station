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


# ---------------------------------------------------------------------------
# Construction cashflow forecast enumerations  (PR-FIN-034)
# ---------------------------------------------------------------------------


class ConstructionSpreadMethod(str, Enum):
    """Method used to distribute construction costs across forecast periods.

    LINEAR
        Costs are distributed uniformly across the execution window.
        monthly_cost = planned_amount / duration_months

    S_CURVE
        Costs follow an S-curve distribution (reserved for future PRs).
    """

    LINEAR = "linear"
    S_CURVE = "s_curve"


class ConstructionForecastScope(str, Enum):
    """Scope level at which a construction cashflow forecast is computed."""

    PROJECT = "project"
    PHASE = "phase"
    PORTFOLIO = "portfolio"


# Default probability that planned construction work will execute.
DEFAULT_EXECUTION_PROBABILITY: float = 1.0

# Default cost spread method for construction cashflow forecasting.
DEFAULT_SPREAD_METHOD: str = "linear"


# ---------------------------------------------------------------------------
# Construction financing enumerations  (PR-FIN-036)
# ---------------------------------------------------------------------------


class ConstructionLoanDrawMethod(str, Enum):
    """Method used to determine when and how debt is drawn down.

    PRO_RATA
        Debt is drawn proportionally in each period based on the debt_ratio.
        debt_draw = period_cost × debt_ratio

    FRONT_LOADED
        Debt is drawn first; equity injected only after debt is exhausted
        (reserved for future PRs).

    BACK_LOADED
        Equity is injected first; debt drawn after equity is exhausted
        (reserved for future PRs).
    """

    PRO_RATA = "pro_rata"
    FRONT_LOADED = "front_loaded"
    BACK_LOADED = "back_loaded"


class ConstructionEquityInjectionMethod(str, Enum):
    """Method used to determine when equity contributions are made.

    PRO_RATA
        Equity is contributed proportionally in each period based on the
        equity_ratio.  equity_contribution = period_cost × equity_ratio

    UPFRONT
        All equity is injected in the first active period
        (reserved for future PRs).

    ON_DEMAND
        Equity is injected only when a funding gap exists after debt drawdown
        (reserved for future PRs).
    """

    PRO_RATA = "pro_rata"
    UPFRONT = "upfront"
    ON_DEMAND = "on_demand"


# Default proportion of construction cost funded by debt.
DEFAULT_DEBT_RATIO: float = 0.60

# Default proportion of construction cost funded by equity (1 − debt_ratio).
DEFAULT_EQUITY_RATIO: float = 0.40

# Default financing probability (probability that financing will be required).
DEFAULT_FINANCING_PROBABILITY: float = 1.0

# Default offset (months) from construction start before financing begins.
DEFAULT_FINANCING_START_OFFSET: int = 0
