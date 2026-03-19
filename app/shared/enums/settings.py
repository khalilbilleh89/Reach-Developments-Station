"""Settings-domain enumerations."""

from enum import Enum


class PricingPriceMode(str, Enum):
    """Governs how an optional-feature price (parking, storage, balcony) is applied."""

    FIXED = "fixed"          # flat amount added to unit price
    PERCENTAGE = "percentage"  # percentage of base unit price
    EXCLUDED = "excluded"    # feature not priced (not offered / included for free)


class CommissionCalculationMode(str, Enum):
    """Calculation strategy for commission pool distribution."""

    MARGINAL = "marginal"       # applied slab-by-slab on value tiers
    CUMULATIVE = "cumulative"   # applied to full contract value once threshold met


class ProjectTemplateStatus(str, Enum):
    """Lifecycle status of a project template."""

    ACTIVE = "active"
    INACTIVE = "inactive"
