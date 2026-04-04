"""
cashflow.models

ORM models for the Cashflow Forecasting domain.

Entities
--------
CashflowForecast       — A generated forecast snapshot for a project.
CashflowForecastPeriod — A time-bucket row within a forecast.

Design contract
---------------
These models are projection/read-only in terms of financial truth.
They do NOT modify payment plans, collections, finance summaries, or
sales contracts. Forecast rows are derived, not source-of-truth transactions.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants.currency import DEFAULT_CURRENCY
from app.db.base import Base, TimestampMixin
from app.shared.enums.cashflow import (
    CashflowForecastBasis,
    CashflowForecastStatus,
    CashflowPeriodType,
)


class CashflowForecast(Base, TimestampMixin):
    """Generated forecast snapshot for a project.

    Stores the assumptions used to generate the forecast so it can be
    reproduced deterministically from those assumptions.
    """

    __tablename__ = "cashflow_forecasts"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    forecast_name: Mapped[str] = mapped_column(String(200), nullable=False)
    forecast_basis: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CashflowForecastBasis.ACTUAL_PLUS_SCHEDULED.value,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CashflowPeriodType.MONTHLY.value,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CashflowForecastStatus.DRAFT.value,
    )
    opening_balance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    collection_factor: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    assumptions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    generated_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)


class CashflowForecastPeriod(Base, TimestampMixin):
    """Time-bucket row within a forecast.

    Each row represents one period (e.g. one calendar month) of the forecast
    window and stores both the expected inflows/outflows and any actual
    inflows observed for that period.
    """

    __tablename__ = "cashflow_forecast_periods"

    __table_args__ = (
        UniqueConstraint(
            "cashflow_forecast_id",
            "sequence",
            name="uq_cashflow_forecast_periods_forecast_seq",
        ),
    )

    cashflow_forecast_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cashflow_forecasts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    opening_balance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    expected_inflows: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    actual_inflows: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    expected_outflows: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_CURRENCY)
    net_cashflow: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    closing_balance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    receivables_due: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    receivables_overdue: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
