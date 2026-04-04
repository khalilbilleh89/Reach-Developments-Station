"""
core.constants.currency

Canonical currency codes used by the platform.

Only codes that are actually referenced in domain models or API contracts
are listed here.  This is not an exhaustive ISO 4217 registry.

Usage
-----
Import the constants directly in ORM models and Pydantic schemas so that the
platform has one authoritative DEFAULT_CURRENCY definition:

    from app.core.constants.currency import DEFAULT_CURRENCY

Forbidden
---------
Do not hardcode inline "AED" (or any other currency string) as a Python
default value in ORM model columns or Pydantic schema fields.  Always use
the imported constant so future changes propagate automatically.
"""

# ---------------------------------------------------------------------------
# Supported currency codes (ISO 4217)
# ---------------------------------------------------------------------------

CURRENCY_AED = "AED"  # UAE Dirham — primary platform currency
CURRENCY_JOD = "JOD"  # Jordanian Dinar
CURRENCY_USD = "USD"  # US Dollar

# Ordered list of ISO codes the platform supports.  Used for validation and
# frontend currency-selector components.
SUPPORTED_CURRENCIES: list[str] = [CURRENCY_AED, CURRENCY_JOD, CURRENCY_USD]

# ---------------------------------------------------------------------------
# Platform default
# ---------------------------------------------------------------------------

# The canonical default currency for all monetary fields, ORM column defaults,
# and Pydantic schema defaults across the platform.
#
# All ORM models must import and reference this constant rather than using
# inline string literals so that the default stays consistent system-wide.
DEFAULT_CURRENCY: str = CURRENCY_AED
