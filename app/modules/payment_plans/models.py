"""
payment_plans.models

ORM models for PaymentPlanTemplate and PaymentSchedule.

PaymentPlanTemplate — reusable plan configuration that defines installment
  structure, down payment, frequency, and handover rules.

PaymentSchedule — individual installment lines generated from a template for
  a specific contract.  One contract has many PaymentSchedule rows.
"""

from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Numeric, String, Boolean, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.finance import InstallmentFrequency, PaymentPlanType, PaymentScheduleStatus


class PaymentPlanTemplate(Base, TimestampMixin):
    """Reusable payment plan blueprint applied to sales contracts."""

    __tablename__ = "payment_plan_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=PaymentPlanType.STANDARD_INSTALLMENTS.value,
    )
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    down_payment_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    number_of_installments: Mapped[int] = mapped_column(Integer, nullable=False)
    installment_frequency: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=InstallmentFrequency.MONTHLY.value,
    )
    handover_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    schedules: Mapped[list["PaymentSchedule"]] = relationship(
        "PaymentSchedule", back_populates="template"
    )


class PaymentSchedule(Base, TimestampMixin):
    """Single installment line generated for a specific contract."""

    __tablename__ = "payment_schedules"
    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "installment_number",
            name="uq_payment_schedules_contract_installment",
        ),
    )

    contract_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sales_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("payment_plan_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=PaymentScheduleStatus.PENDING.value,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    template: Mapped[Optional["PaymentPlanTemplate"]] = relationship(
        "PaymentPlanTemplate", back_populates="schedules"
    )
