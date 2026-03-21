"""
sales.models

ORM models for the Sales domain: Buyer, Reservation, SalesContract,
ContractPaymentSchedule.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.sales import ContractPaymentStatus, ContractStatus, ReservationStatus


class Buyer(Base, TimestampMixin):
    """Commercial party linked to reservations and contracts."""

    __tablename__ = "buyers"

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    nationality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    reservations: Mapped[list["Reservation"]] = relationship(
        "Reservation", back_populates="buyer"
    )
    contracts: Mapped[list["SalesContract"]] = relationship(
        "SalesContract", back_populates="buyer"
    )


class Reservation(Base, TimestampMixin):
    """Provisional hold on a unit for a buyer.

    Only one active reservation per unit is allowed at any time.
    """

    __tablename__ = "reservations"

    unit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    buyer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("buyers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reservation_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ReservationStatus.ACTIVE.value,
    )
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    buyer: Mapped["Buyer"] = relationship("Buyer", back_populates="reservations")
    contract: Mapped[Optional["SalesContract"]] = relationship(
        "SalesContract", back_populates="reservation", uselist=False
    )


class SalesContract(Base, TimestampMixin):
    """Formal sale commitment for a unit.

    Only one draft-or-active contract per unit is allowed at any time.
    """

    __tablename__ = "sales_contracts"

    unit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    buyer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("buyers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reservation_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    contract_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    contract_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ContractStatus.DRAFT.value,
    )
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    buyer: Mapped["Buyer"] = relationship("Buyer", back_populates="contracts")
    reservation: Mapped[Optional["Reservation"]] = relationship(
        "Reservation", back_populates="contract"
    )
    payment_schedule: Mapped[list["ContractPaymentSchedule"]] = relationship(
        "ContractPaymentSchedule",
        back_populates="contract",
        order_by="ContractPaymentSchedule.installment_number",
    )


class ContractPaymentSchedule(Base, TimestampMixin):
    """Installment obligation linked to a sales contract.

    Generated when a contract is activated.  Each row represents a single
    payment milestone (e.g. reservation deposit, signing, construction,
    handover).
    """

    __tablename__ = "contract_payment_schedule"

    contract_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sales_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installment_number: Mapped[int] = mapped_column(nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="AED"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ContractPaymentStatus.PENDING.value,
        index=True,
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payment_reference: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    contract: Mapped["SalesContract"] = relationship(
        "SalesContract", back_populates="payment_schedule"
    )
