"""
registration.models

ORM models for the Registration/Conveyancing domain.

Tracks the post-sale legal transfer workflow for sold units.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.registration import CaseStatus, MilestoneStatus


class RegistrationCase(Base, TimestampMixin):
    """Legal transfer case for a sold unit.

    One registration case per sold unit (active cases must be unique per unit).
    Tracks the full lifecycle from SPA signing to title issuance.
    """

    __tablename__ = "registration_cases"

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
    sale_contract_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sales_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    buyer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    buyer_identifier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CaseStatus.DRAFT.value,
    )
    opened_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    submitted_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    milestones: Mapped[list["RegistrationMilestone"]] = relationship(
        "RegistrationMilestone",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="RegistrationMilestone.sequence",
    )
    documents: Mapped[list["RegistrationDocument"]] = relationship(
        "RegistrationDocument",
        back_populates="case",
        cascade="all, delete-orphan",
    )


class RegistrationMilestone(Base, TimestampMixin):
    """A single stage in the registration case workflow.

    Ordered by sequence so the client can display progress steps in order.
    """

    __tablename__ = "registration_milestones"

    registration_case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("registration_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_code: Mapped[str] = mapped_column(String(50), nullable=False)
    step_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MilestoneStatus.PENDING.value,
    )
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    remarks: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    case: Mapped["RegistrationCase"] = relationship(
        "RegistrationCase", back_populates="milestones"
    )


class RegistrationDocument(Base, TimestampMixin):
    """A document required or received for a registration case."""

    __tablename__ = "registration_documents"

    registration_case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("registration_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_received: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    case: Mapped["RegistrationCase"] = relationship(
        "RegistrationCase", back_populates="documents"
    )
