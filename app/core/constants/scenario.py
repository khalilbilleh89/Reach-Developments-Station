"""
core.constants.scenario

Centralised scenario domain constants.

Provides the canonical status and source-type string values used by the
Scenario Engine, eliminating inline literal sets in service and model code.
"""

from enum import Enum


class ScenarioStatus(str, Enum):
    """Lifecycle status of a Scenario record."""

    DRAFT = "draft"
    APPROVED = "approved"
    ARCHIVED = "archived"


class ScenarioSourceType(str, Enum):
    """Planning layer that owns or originated a Scenario."""

    LAND = "land"
    FEASIBILITY = "feasibility"
    CONCEPT = "concept"
    GENERAL = "general"


# ---------------------------------------------------------------------------
# Convenience sets used for validation
# ---------------------------------------------------------------------------

VALID_STATUSES: frozenset[str] = frozenset(s.value for s in ScenarioStatus)
VALID_SOURCE_TYPES: frozenset[str] = frozenset(s.value for s in ScenarioSourceType)

# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

DEFAULT_SCENARIO_STATUS = ScenarioStatus.DRAFT.value
DEFAULT_SCENARIO_SOURCE_TYPE = ScenarioSourceType.FEASIBILITY.value
