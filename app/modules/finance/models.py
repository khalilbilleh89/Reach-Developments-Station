"""
finance.models

Analytics fact table ORM models for the Finance module.

These tables store materialized analytics-ready financial data derived from
the operational financial engines (revenue recognition, collections aging,
cashflow forecast).  They are not the source of truth — they are populated
by the AnalyticsService and queried by dashboards for fast reporting.

Tables:
  fact_revenue              — Monthly recognized revenue per project / unit.
  fact_collections          — Payments received by project / month.
  fact_receivables_snapshot — Point-in-time receivable aging snapshots.
"""

from datetime import date

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FactRevenue(Base, TimestampMixin):
    """Monthly recognized revenue materialized per project and unit.

    Populated by AnalyticsService.build_revenue_fact().
    Each row represents recognized revenue for one (project, unit, month)
    combination.  The table is rebuilt from scratch on every analytics run.
    """

    __tablename__ = "fact_revenue"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        index=True,
        comment="Calendar month in YYYY-MM format.",
    )
    recognized_revenue: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0.0
    )
    contract_value: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0.0
    )


class FactCollections(Base, TimestampMixin):
    """Payments received materialized by project, month, and payment method.

    Populated by AnalyticsService.build_collections_fact().
    Each row represents total collected amount for one
    (project, month, payment_method) combination.
    """

    __tablename__ = "fact_collections"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    month: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        index=True,
        comment="Calendar month in YYYY-MM format.",
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    payment_method: Mapped[str] = mapped_column(
        String(50), nullable=False, default="bank_transfer"
    )


class FactReceivablesSnapshot(Base, TimestampMixin):
    """Point-in-time snapshot of receivable aging buckets per project.

    Populated by AnalyticsService.build_receivable_snapshot().
    Each row represents the aging state for a single project at the
    snapshot_date.  Allows historical aging trend analysis.
    """

    __tablename__ = "fact_receivables_snapshot"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_receivables: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0.0
    )
    bucket_0_30: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0.0
    )
    bucket_31_60: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0.0
    )
    bucket_61_90: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0.0
    )
    bucket_90_plus: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0.0
    )
