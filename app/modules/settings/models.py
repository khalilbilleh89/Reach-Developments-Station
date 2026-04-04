"""
settings.models

ORM models for the Settings business domain.

This module provides the governance layer for core platform business rules.
It defines reusable policy and template objects that downstream modules
(pricing, commission, project setup) can reference without embedding
hardcoded defaults in their own code.

Entities
--------
PricingPolicy     — Named pricing-behaviour defaults (markup, feature price modes).
CommissionPolicy  — Named commission-pool and calculation-mode defaults.
ProjectTemplate   — Reusable project-setup template that bundles default policies.

Design contract
---------------
These models govern defaults and policy metadata only.  They do NOT contain
formula implementations, finance calculations, or contract logic.
All monetary formula engines remain in their respective domain modules.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants.currency import DEFAULT_CURRENCY
from app.db.base import Base, TimestampMixin
from app.shared.enums.settings import CommissionCalculationMode, PricingPriceMode


class PricingPolicy(Base, TimestampMixin):
    """Named set of pricing-behaviour defaults.

    Governs how the platform applies markup and optional-feature prices.
    Multiple policies may exist; at most one may be flagged is_default=True.
    """

    __tablename__ = "settings_pricing_policies"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_CURRENCY)
    base_markup_percent: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=Decimal("0.0000")
    )
    balcony_price_factor: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=Decimal("0.0000")
    )
    parking_price_mode: Mapped[str] = mapped_column(
        String(50), nullable=False, default=PricingPriceMode.EXCLUDED.value
    )
    storage_price_mode: Mapped[str] = mapped_column(
        String(50), nullable=False, default=PricingPriceMode.EXCLUDED.value
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CommissionPolicy(Base, TimestampMixin):
    """Named commission-pool and calculation-mode defaults.

    Governs the overall pool percentage and the slab-application strategy.
    Multiple policies may exist; at most one may be flagged is_default=True.
    """

    __tablename__ = "settings_commission_policies"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pool_percent: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=Decimal("0.0000")
    )
    calculation_mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CommissionCalculationMode.MARGINAL.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProjectTemplate(Base, TimestampMixin):
    """Reusable project-setup template.

    Bundles a default pricing policy, a default commission policy, and a
    preferred currency so that new projects can be bootstrapped consistently.
    Both FK references are nullable — a template may exist before policies
    are created, and policies are managed independently.
    """

    __tablename__ = "settings_project_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_pricing_policy_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("settings_pricing_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    default_commission_policy_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("settings_commission_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    default_currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default=DEFAULT_CURRENCY
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
