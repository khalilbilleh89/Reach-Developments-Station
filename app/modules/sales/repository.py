"""
sales.repository

Data access layer for Buyer, Reservation, SalesContract, and
ContractPaymentSchedule entities.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.sales.models import (
    Buyer,
    ContractPaymentSchedule,
    Reservation,
    SalesContract,
)
from app.modules.sales.schemas import (
    BuyerCreate,
    ReservationCreate,
    SalesContractCreate,
)
from app.shared.enums.sales import ContractPaymentStatus, ContractStatus, ReservationStatus


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


class ContractPaymentScheduleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, schedule_item: ContractPaymentSchedule) -> ContractPaymentSchedule:
        self.db.add(schedule_item)
        self.db.flush()
        return schedule_item

    def bulk_create(
        self, items: List[ContractPaymentSchedule]
    ) -> List[ContractPaymentSchedule]:
        for item in items:
            self.db.add(item)
        self.db.commit()
        for item in items:
            self.db.refresh(item)
        return items

    def list_by_contract(self, contract_id: str) -> List[ContractPaymentSchedule]:
        return (
            self.db.query(ContractPaymentSchedule)
            .filter(ContractPaymentSchedule.contract_id == contract_id)
            .order_by(ContractPaymentSchedule.installment_number)
            .all()
        )

    def get_by_contract_and_installment(
        self, contract_id: str, installment_number: int
    ) -> Optional[ContractPaymentSchedule]:
        return (
            self.db.query(ContractPaymentSchedule)
            .filter(
                ContractPaymentSchedule.contract_id == contract_id,
                ContractPaymentSchedule.installment_number == installment_number,
            )
            .first()
        )

    def count_by_contract(self, contract_id: str) -> int:
        return (
            self.db.query(ContractPaymentSchedule)
            .filter(ContractPaymentSchedule.contract_id == contract_id)
            .count()
        )

    def save(
        self, item: ContractPaymentSchedule
    ) -> ContractPaymentSchedule:
        self.db.commit()
        self.db.refresh(item)
        return item
