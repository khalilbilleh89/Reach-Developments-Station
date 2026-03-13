"""
sales.repository

Data access layer for Buyer, Reservation, and SalesContract entities.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.sales.models import Buyer, Reservation, SalesContract
from app.modules.sales.schemas import (
    BuyerCreate,
    ReservationCreate,
    SalesContractCreate,
)
from app.shared.enums.sales import ContractStatus, ReservationStatus


class BuyerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: BuyerCreate) -> Buyer:
        buyer = Buyer(**data.model_dump())
        self.db.add(buyer)
        self.db.commit()
        self.db.refresh(buyer)
        return buyer

    def get_by_id(self, buyer_id: str) -> Optional[Buyer]:
        return self.db.query(Buyer).filter(Buyer.id == buyer_id).first()

    def list(self, skip: int = 0, limit: int = 100) -> List[Buyer]:
        return self.db.query(Buyer).offset(skip).limit(limit).all()

    def count(self) -> int:
        return self.db.query(Buyer).count()


class ReservationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: ReservationCreate) -> Reservation:
        reservation = Reservation(**data.model_dump())
        self.db.add(reservation)
        self.db.commit()
        self.db.refresh(reservation)
        return reservation

    def get_by_id(self, reservation_id: str) -> Optional[Reservation]:
        return (
            self.db.query(Reservation)
            .filter(Reservation.id == reservation_id)
            .first()
        )

    def list(
        self,
        unit_id: Optional[str] = None,
        buyer_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Reservation]:
        query = self.db.query(Reservation)
        if unit_id:
            query = query.filter(Reservation.unit_id == unit_id)
        if buyer_id:
            query = query.filter(Reservation.buyer_id == buyer_id)
        return query.offset(skip).limit(limit).all()

    def count(
        self,
        unit_id: Optional[str] = None,
        buyer_id: Optional[str] = None,
    ) -> int:
        query = self.db.query(Reservation)
        if unit_id:
            query = query.filter(Reservation.unit_id == unit_id)
        if buyer_id:
            query = query.filter(Reservation.buyer_id == buyer_id)
        return query.count()

    def get_active_by_unit(self, unit_id: str) -> Optional[Reservation]:
        """Return the active reservation for a unit, if any."""
        return (
            self.db.query(Reservation)
            .filter(
                Reservation.unit_id == unit_id,
                Reservation.status == ReservationStatus.ACTIVE.value,
            )
            .first()
        )

    def list_by_buyer(self, buyer_id: str) -> List[Reservation]:
        return (
            self.db.query(Reservation)
            .filter(Reservation.buyer_id == buyer_id)
            .all()
        )

    def save(self, reservation: Reservation) -> Reservation:
        self.db.commit()
        self.db.refresh(reservation)
        return reservation


class SalesContractRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: SalesContractCreate) -> SalesContract:
        contract = SalesContract(**data.model_dump())
        self.db.add(contract)
        self.db.commit()
        self.db.refresh(contract)
        return contract

    def get_by_id(self, contract_id: str) -> Optional[SalesContract]:
        return (
            self.db.query(SalesContract)
            .filter(SalesContract.id == contract_id)
            .first()
        )

    def get_by_contract_number(self, contract_number: str) -> Optional[SalesContract]:
        return (
            self.db.query(SalesContract)
            .filter(SalesContract.contract_number == contract_number)
            .first()
        )

    def list(
        self,
        unit_id: Optional[str] = None,
        buyer_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SalesContract]:
        query = self.db.query(SalesContract)
        if unit_id:
            query = query.filter(SalesContract.unit_id == unit_id)
        if buyer_id:
            query = query.filter(SalesContract.buyer_id == buyer_id)
        return query.offset(skip).limit(limit).all()

    def count(
        self,
        unit_id: Optional[str] = None,
        buyer_id: Optional[str] = None,
    ) -> int:
        query = self.db.query(SalesContract)
        if unit_id:
            query = query.filter(SalesContract.unit_id == unit_id)
        if buyer_id:
            query = query.filter(SalesContract.buyer_id == buyer_id)
        return query.count()

    def get_open_by_unit(self, unit_id: str) -> Optional[SalesContract]:
        """Return the open (draft or active) contract for a unit, if any."""
        return (
            self.db.query(SalesContract)
            .filter(
                SalesContract.unit_id == unit_id,
                SalesContract.status.in_(
                    [ContractStatus.DRAFT.value, ContractStatus.ACTIVE.value]
                ),
            )
            .first()
        )

    def list_by_buyer(self, buyer_id: str) -> List[SalesContract]:
        return (
            self.db.query(SalesContract)
            .filter(SalesContract.buyer_id == buyer_id)
            .all()
        )

    def save(self, contract: SalesContract) -> SalesContract:
        self.db.commit()
        self.db.refresh(contract)
        return contract
