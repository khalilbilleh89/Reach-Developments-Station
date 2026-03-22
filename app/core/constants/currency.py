"""
core.constants.currency

Canonical currency codes used by the platform.

Only codes that are actually referenced in domain models or API contracts
are listed here.  This is not an exhaustive ISO 4217 registry.
"""

# ---------------------------------------------------------------------------
# Supported currency codes
# ---------------------------------------------------------------------------

CURRENCY_JOD = "JOD"
CURRENCY_USD = "USD"

# Default currency used when none is explicitly provided.
DEFAULT_CURRENCY = CURRENCY_JOD
