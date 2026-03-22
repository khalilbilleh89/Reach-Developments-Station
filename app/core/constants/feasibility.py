"""
core.constants.feasibility

Centralised feasibility domain constants.

Imports the canonical enum definitions from the shared enums layer and
re-exports them through this constants package so that all downstream
consumers (models, schemas, services) can import from a single location.
"""

from app.shared.enums.finance import (  # noqa: F401
    FeasibilityDecision,
    FeasibilityRiskLevel,
    FeasibilityScenarioType,
    FeasibilityViabilityStatus,
)

# ---------------------------------------------------------------------------
# Convenience value aliases — avoids .value lookups at call sites
# ---------------------------------------------------------------------------

# Viability status values
VIABILITY_VIABLE = FeasibilityViabilityStatus.VIABLE.value
VIABILITY_MARGINAL = FeasibilityViabilityStatus.MARGINAL.value
VIABILITY_NOT_VIABLE = FeasibilityViabilityStatus.NOT_VIABLE.value

# Risk level values
RISK_LOW = FeasibilityRiskLevel.LOW.value
RISK_MEDIUM = FeasibilityRiskLevel.MEDIUM.value
RISK_HIGH = FeasibilityRiskLevel.HIGH.value

# Decision values
DECISION_VIABLE = FeasibilityDecision.VIABLE.value
DECISION_MARGINAL = FeasibilityDecision.MARGINAL.value
DECISION_NOT_VIABLE = FeasibilityDecision.NOT_VIABLE.value

# Scenario type values
SCENARIO_TYPE_BASE = FeasibilityScenarioType.BASE.value
SCENARIO_TYPE_UPSIDE = FeasibilityScenarioType.UPSIDE.value
SCENARIO_TYPE_DOWNSIDE = FeasibilityScenarioType.DOWNSIDE.value
SCENARIO_TYPE_INVESTOR = FeasibilityScenarioType.INVESTOR.value

# Default scenario type used when none is provided
DEFAULT_SCENARIO_TYPE = SCENARIO_TYPE_BASE
