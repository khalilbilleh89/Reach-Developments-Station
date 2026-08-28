"""Country configuration tables.

This module stores configuration. It performs no financial calculation: tax is
recorded here and applied by the domains that later charge it.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: Monetary amounts. NUMERIC always — never float, anywhere, for money.
MONEY = Numeric(18, 2)

#: Rates are stored as explicit fractions: 0.160000 means 16%. The column name
#: always ends in ``_rate_fraction`` so the unit can never be misread.
RATE = Numeric(9, 6)

#: Area units a country pack may declare. Deliberately closed — this is not a
#: unit-conversion engine.
AREA_UNITS = ("sqm", "sqft")

#: What a tax rule attaches to.
TAX_APPLIES_TO = ("sale", "rental", "service_charge", "construction", "other")

#: What the rate is applied against.
TAX_CALCULATION_BASIS = ("net_amount", "gross_amount")


def _in_list(column: str, allowed: tuple[str, ...]) -> str:
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"


class Currency(Base):
    """A currency the business actually transacts in. No FX rates, no market data."""

    __tablename__ = "currencies"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(3), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(8), nullable=True)
    minor_units: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("code = upper(code) AND length(code) = 3", name="code_upper_alpha3"),
        CheckConstraint("minor_units BETWEEN 0 AND 6", name="minor_units_range"),
    )


class CountryPack(Base):
    """Per-country configuration container.

    A configuration record, not a statement of legal or tax compliance.
    """

    __tablename__ = "country_packs"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    locale: Mapped[str] = mapped_column(String(35), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    default_currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("currencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    area_unit: Mapped[str] = mapped_column(String(8), nullable=False)
    fiscal_year_start_month: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "country_code = upper(country_code) AND length(country_code) = 2",
            name="country_code_upper_alpha2",
        ),
        CheckConstraint(_in_list("area_unit", AREA_UNITS), name="area_unit_allowed"),
        CheckConstraint("fiscal_year_start_month BETWEEN 1 AND 12", name="fiscal_month_range"),
    )


class TaxRule(Base):
    """An effective-dated tax configuration entry for one country pack."""

    __tablename__ = "tax_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    country_pack_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("country_packs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tax_code: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    applies_to: Mapped[str] = mapped_column(String(32), nullable=False)
    calculation_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Explicit fraction. 0.160000 is 16 per cent.
    rate_fraction: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("rate_fraction >= 0 AND rate_fraction <= 1", name="rate_fraction_range"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="valid_range"),
        CheckConstraint(_in_list("applies_to", TAX_APPLIES_TO), name="applies_to_allowed"),
        CheckConstraint(
            _in_list("calculation_basis", TAX_CALCULATION_BASIS), name="calculation_basis_allowed"
        ),
    )


class ReferenceValue(Base):
    """A configurable lookup value, optionally scoped to a country pack.

    Intentionally small. This is a controlled dictionary, not a custom-field
    system, not dynamic schema, and not a rules engine. Constrained custom
    fields arrive in PR-MVP-03 and stay constrained there.
    """

    __tablename__ = "reference_values"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: NULL means the value is global rather than country-specific.
    country_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("country_packs.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="valid_range"),
        # PostgreSQL treats NULLs as distinct in a UNIQUE constraint, so a single
        # constraint over (country_pack_id, category, code) would let unlimited
        # duplicate global values through. Two partial indexes cover both scopes.
        Index(
            "uq_reference_values_country_scope",
            "country_pack_id",
            "category",
            "code",
            unique=True,
            postgresql_where=text("country_pack_id IS NOT NULL"),
        ),
        Index(
            "uq_reference_values_global_scope",
            "category",
            "code",
            unique=True,
            postgresql_where=text("country_pack_id IS NULL"),
        ),
    )


class CountryApprovalThreshold(Base):
    """Baseline control limits for one country pack.

    Explicit columns, not a rules engine. This PR stores the policy; the
    domains that can breach it execute the approval behaviour when they exist.
    Every column below has a named consumer on the roadmap.
    """

    __tablename__ = "country_approval_thresholds"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: One row per country pack. The uniqueness lives in ``__table_args__`` so
    #: exactly one named constraint reaches the database.
    country_pack_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("country_packs.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Pricing and discounting — PR-MVP-04.
    discount_review_rate_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    discount_review_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    pricing_requires_finance_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    pricing_requires_commercial_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Unit economics — PR-MVP-08.
    minimum_margin_rate_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)

    # Custom payment plans — PR-MVP-06.
    custom_plan_min_down_payment_rate_fraction: Mapped[Decimal | None] = mapped_column(
        RATE, nullable=True
    )
    custom_plan_max_duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_plan_max_post_handover_rate_fraction: Mapped[Decimal | None] = mapped_column(
        RATE, nullable=True
    )
    custom_plan_max_npv_cost_rate_fraction: Mapped[Decimal | None] = mapped_column(
        RATE, nullable=True
    )

    # Collections dual control — PR-MVP-07.
    receipt_reversal_requires_dual_control: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    refund_requires_dual_control: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # Construction control — PR-MVP-09.
    construction_variation_review_amount: Mapped[Decimal | None] = mapped_column(
        MONEY, nullable=True
    )
    forecast_reset_variance_rate_fraction: Mapped[Decimal | None] = mapped_column(
        RATE, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "discount_review_rate_fraction IS NULL "
            "OR (discount_review_rate_fraction >= 0 AND discount_review_rate_fraction <= 1)",
            name="discount_review_rate_range",
        ),
        CheckConstraint(
            "minimum_margin_rate_fraction IS NULL "
            "OR (minimum_margin_rate_fraction >= 0 AND minimum_margin_rate_fraction <= 1)",
            name="minimum_margin_rate_range",
        ),
        CheckConstraint(
            "custom_plan_min_down_payment_rate_fraction IS NULL "
            "OR (custom_plan_min_down_payment_rate_fraction >= 0 "
            "AND custom_plan_min_down_payment_rate_fraction <= 1)",
            name="min_down_payment_rate_range",
        ),
        CheckConstraint(
            "custom_plan_max_post_handover_rate_fraction IS NULL "
            "OR (custom_plan_max_post_handover_rate_fraction >= 0 "
            "AND custom_plan_max_post_handover_rate_fraction <= 1)",
            name="post_handover_rate_range",
        ),
        CheckConstraint(
            "custom_plan_max_npv_cost_rate_fraction IS NULL "
            "OR (custom_plan_max_npv_cost_rate_fraction >= 0 "
            "AND custom_plan_max_npv_cost_rate_fraction <= 1)",
            name="npv_cost_rate_range",
        ),
        CheckConstraint(
            "forecast_reset_variance_rate_fraction IS NULL "
            "OR (forecast_reset_variance_rate_fraction >= 0 "
            "AND forecast_reset_variance_rate_fraction <= 1)",
            name="forecast_variance_rate_range",
        ),
        CheckConstraint(
            "custom_plan_max_duration_months IS NULL "
            "OR (custom_plan_max_duration_months > 0 AND custom_plan_max_duration_months <= 600)",
            name="plan_duration_range",
        ),
        CheckConstraint(
            "discount_review_amount IS NULL OR discount_review_amount >= 0",
            name="discount_review_amount_non_negative",
        ),
        CheckConstraint(
            "construction_variation_review_amount IS NULL "
            "OR construction_variation_review_amount >= 0",
            name="variation_amount_non_negative",
        ),
        # Unnamed on purpose: the metadata naming convention renders this as
        # ``uq_country_approval_thresholds_country_pack_id``.
        UniqueConstraint("country_pack_id"),
    )
