"""
core.constants

Unified domain constants layer.

Provides a single import surface for all shared constants across the
platform.  Individual sub-modules group constants by domain.

Usage examples::

    from app.core.constants import scenario, feasibility, land, currency, units
    from app.core.constants.scenario import ScenarioStatus, VALID_SOURCE_TYPES
    from app.core.constants.feasibility import FeasibilityViabilityStatus
"""

from app.core.constants import (  # noqa: F401
    common,
    currency,
    feasibility,
    land,
    scenario,
    units,
)
