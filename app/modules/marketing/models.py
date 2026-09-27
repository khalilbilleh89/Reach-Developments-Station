"""Audited marketing records, with explicit money and percentage columns."""

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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketingContent(Base):
    __tablename__ = "marketing_content"
    __table_args__ = (
        CheckConstraint("kind IN ('bio', 'branding')", name="content_kind"),
        Index(
            "uq_marketing_content_live",
            "project_id",
            "kind",
            unique=True,
            postgresql_where=text("NOT is_deleted"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)


class RentalScenario(Base):
    __tablename__ = "marketing_rental_scenarios"
    __table_args__ = (
        CheckConstraint("mode IN ('long_term', 'short_term')", name="rental_mode"),
        CheckConstraint("area_basis IN ('net', 'gross')", name="rental_area"),
        CheckConstraint("exit_method IN ('appreciation', 'cap_rate')", name="rental_exit"),
        CheckConstraint(
            "price_override IS NULL OR (price_override > 0 AND unit_id IS NOT NULL)",
            name="rental_price",
        ),
        Index(
            "uq_marketing_rental_default",
            "project_id",
            "mode",
            unique=True,
            postgresql_where=text("NOT is_deleted AND unit_id IS NULL"),
        ),
        Index(
            "uq_marketing_rental_unit",
            "project_id",
            "unit_id",
            "mode",
            unique=True,
            postgresql_where=text("NOT is_deleted AND unit_id IS NOT NULL"),
        ),
        CheckConstraint("annual_rent_per_sqm >= 0", name="annual_rent_per_sqm"),
        CheckConstraint("annual_expense_per_sqm >= 0", name="annual_expense_per_sqm"),
        CheckConstraint("setup_cost >= 0", name="setup_cost"),
        CheckConstraint("vacancy_percent >= 0 AND vacancy_percent <= 100", name="vacancy_percent"),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100", name="discount_percent"
        ),
        CheckConstraint(
            "acquisition_cost_percent >= 0 AND acquisition_cost_percent <= 100",
            name="acquisition_cost_percent",
        ),
        CheckConstraint(
            "selling_cost_percent >= 0 AND selling_cost_percent <= 100", name="selling_cost_percent"
        ),
        CheckConstraint(
            "income_growth_percent > -100 AND income_growth_percent <= 100",
            name="income_growth_percent",
        ),
        CheckConstraint(
            "expense_growth_percent > -100 AND expense_growth_percent <= 100",
            name="expense_growth_percent",
        ),
        CheckConstraint(
            "appreciation_percent > -100 AND appreciation_percent <= 100",
            name="appreciation_percent",
        ),
        CheckConstraint(
            "exit_cap_percent > 0 AND exit_cap_percent <= 100", name="exit_cap_percent"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT")
    )
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    area_basis: Mapped[str] = mapped_column(String(20), nullable=False)
    exit_method: Mapped[str] = mapped_column(String(20), nullable=False)
    price_override: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    annual_rent_per_sqm: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    annual_expense_per_sqm: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    setup_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    vacancy_percent: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    acquisition_cost_percent: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    selling_cost_percent: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    income_growth_percent: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    expense_growth_percent: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    appreciation_percent: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    exit_cap_percent: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(320), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)


class MarketIndicator(Base):
    __tablename__ = "marketing_indicators"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    name: Mapped[str] = mapped_column(String(320), nullable=False)
    geography: Mapped[str] = mapped_column(String(320), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(320), nullable=False)
    period: Mapped[str] = mapped_column(String(320), nullable=False)
    source: Mapped[str] = mapped_column(String(320), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    commentary: Mapped[str] = mapped_column(String(4000), nullable=False)
