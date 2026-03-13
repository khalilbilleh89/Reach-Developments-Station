"""
sales.models

ORM models for the Sales domain: Buyer, Reservation, SalesContract.
"""

from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.shared.enums.sales import ContractStatus, ReservationStatus


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
    reservation_date: Mapped[str] = mapped_column(String(30), nullable=False)
    expiry_date: Mapped[str] = mapped_column(String(30), nullable=False)
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

    Only one active contract per unit is allowed at any time.
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
        index=True,
    )
    contract_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    contract_date: Mapped[str] = mapped_column(String(30), nullable=False)
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
