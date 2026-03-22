"""
core.constants.land

Centralised land domain constants.

Imports the canonical enum definitions from the shared enums layer and
re-exports them through this constants package so that all downstream
consumers can import from a single location.
"""

from app.shared.enums.project import LandParcelStatus, LandScenarioType  # noqa: F401

# ---------------------------------------------------------------------------
# Convenience value aliases
# ---------------------------------------------------------------------------

# Parcel status values
PARCEL_STATUS_DRAFT = LandParcelStatus.DRAFT.value
PARCEL_STATUS_UNDER_REVIEW = LandParcelStatus.UNDER_REVIEW.value
PARCEL_STATUS_APPROVED = LandParcelStatus.APPROVED.value
PARCEL_STATUS_ARCHIVED = LandParcelStatus.ARCHIVED.value

# Scenario type values (land-context)
LAND_SCENARIO_BASE = LandScenarioType.BASE.value
LAND_SCENARIO_UPSIDE = LandScenarioType.UPSIDE.value
LAND_SCENARIO_DOWNSIDE = LandScenarioType.DOWNSIDE.value
LAND_SCENARIO_INVESTOR = LandScenarioType.INVESTOR.value

# Default values
DEFAULT_PARCEL_STATUS = PARCEL_STATUS_DRAFT
DEFAULT_LAND_SCENARIO_TYPE = LAND_SCENARIO_BASE
