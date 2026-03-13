"""
sales.service

Application-layer orchestration for the Sales domain.
Enforces business rules for buyers, reservations, and contracts.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.sales.models import Buyer, Reservation, SalesContract
from app.modules.sales.repository import (
    BuyerRepository,
    ReservationRepository,
    SalesContractRepository,
)
from app.modules.sales.schemas import (
    BuyerCreate,
    BuyerListResponse,
    BuyerResponse,
    BuyerUpdate,
    ReservationCreate,
    ReservationListResponse,
    ReservationResponse,
    ReservationUpdate,
    SalesContractCreate,
    SalesContractListResponse,
    SalesContractResponse,
    SalesContractUpdate,
)
from app.modules.units.repository import UnitRepository
from app.shared.enums.sales import ContractStatus, ReservationStatus


class SalesService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self.buyer_repo = BuyerRepository(db)
        self.reservation_repo = ReservationRepository(db)
        self.contract_repo = SalesContractRepository(db)
        self.unit_repo = UnitRepository(db)

    # ------------------------------------------------------------------
    # Buyer operations
    # ------------------------------------------------------------------

    def create_buyer(self, data: BuyerCreate) -> BuyerResponse:
        buyer = self.buyer_repo.create(data)
        return BuyerResponse.model_validate(buyer)

    def get_buyer(self, buyer_id: str) -> BuyerResponse:
        buyer = self._require_buyer(buyer_id)
        return BuyerResponse.model_validate(buyer)

    def list_buyers(self, skip: int = 0, limit: int = 100) -> BuyerListResponse:
        buyers = self.buyer_repo.list(skip=skip, limit=limit)
        total = self.buyer_repo.count()
        return BuyerListResponse(
            total=total,
            items=[BuyerResponse.model_validate(b) for b in buyers],
        )

    # ------------------------------------------------------------------
    # Reservation operations
    # ------------------------------------------------------------------

    def create_reservation(self, data: ReservationCreate) -> ReservationResponse:
        self._require_unit(data.unit_id)
        self._require_buyer(data.buyer_id)
        self._require_pricing_for_unit(data.unit_id)

        existing = self.reservation_repo.get_active_by_unit(data.unit_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unit '{data.unit_id}' already has an active reservation.",
            )

        reservation = self.reservation_repo.create(data)
        return ReservationResponse.model_validate(reservation)

    def get_reservation(self, reservation_id: str) -> ReservationResponse:
        reservation = self._require_reservation(reservation_id)
        return ReservationResponse.model_validate(reservation)

    def list_reservations(
        self,
        unit_id: str | None = None,
        buyer_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> ReservationListResponse:
        reservations = self.reservation_repo.list(
            unit_id=unit_id, buyer_id=buyer_id, skip=skip, limit=limit
        )
        total = self.reservation_repo.count(unit_id=unit_id, buyer_id=buyer_id)
        return ReservationListResponse(
            total=total,
            items=[ReservationResponse.model_validate(r) for r in reservations],
        )

    def update_reservation(
        self, reservation_id: str, data: ReservationUpdate
    ) -> ReservationResponse:
        reservation = self._require_reservation(reservation_id)
        if reservation.status != ReservationStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Reservation '{reservation_id}' is not active and cannot be updated.",
            )
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(reservation, field, value)
        self.reservation_repo.save(reservation)
        return ReservationResponse.model_validate(reservation)

    def cancel_reservation(self, reservation_id: str) -> ReservationResponse:
        reservation = self._require_reservation(reservation_id)
        if reservation.status != ReservationStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only active reservations can be cancelled. "
                       f"Current status: '{reservation.status}'.",
            )
        reservation.status = ReservationStatus.CANCELLED.value
        self.reservation_repo.save(reservation)
        return ReservationResponse.model_validate(reservation)

    def expire_reservation(self, reservation_id: str) -> ReservationResponse:
        reservation = self._require_reservation(reservation_id)
        if reservation.status != ReservationStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only active reservations can be expired. "
                       f"Current status: '{reservation.status}'.",
            )
        reservation.status = ReservationStatus.EXPIRED.value
        self.reservation_repo.save(reservation)
        return ReservationResponse.model_validate(reservation)

    # ------------------------------------------------------------------
    # Contract operations
    # ------------------------------------------------------------------

    def create_contract(self, data: SalesContractCreate) -> SalesContractResponse:
        self._require_unit(data.unit_id)
        self._require_buyer(data.buyer_id)

        # Enforce contract_number uniqueness
        if self.contract_repo.get_by_contract_number(data.contract_number):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Contract number '{data.contract_number}' is already in use.",
            )

        # Block if a draft or active contract already exists for this unit
        open_contract = self.contract_repo.get_open_by_unit(data.unit_id)
        if open_contract:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unit '{data.unit_id}' already has a contract in 'draft' or 'active' status.",
            )

        # If a reservation_id is supplied, validate it before touching anything
        reservation = None
        if data.reservation_id:
            reservation = self._require_reservation(data.reservation_id)
            if reservation.unit_id != data.unit_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Reservation unit does not match the contract unit.",
                )
            if reservation.buyer_id != data.buyer_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Reservation buyer does not match the contract buyer.",
                )
            if reservation.status != ReservationStatus.ACTIVE.value:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Reservation '{data.reservation_id}' is not active "
                           f"and cannot be converted to a contract.",
                )

        # Atomic: create contract and convert reservation in a single commit
        contract = SalesContract(**data.model_dump())
        self._db.add(contract)
        if reservation is not None:
            reservation.status = ReservationStatus.CONVERTED.value
        self._db.commit()
        self._db.refresh(contract)

        return SalesContractResponse.model_validate(contract)

    def get_contract(self, contract_id: str) -> SalesContractResponse:
        contract = self._require_contract(contract_id)
        return SalesContractResponse.model_validate(contract)

    def list_contracts(
        self,
        unit_id: str | None = None,
        buyer_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> SalesContractListResponse:
        contracts = self.contract_repo.list(
            unit_id=unit_id, buyer_id=buyer_id, skip=skip, limit=limit
        )
        total = self.contract_repo.count(unit_id=unit_id, buyer_id=buyer_id)
        return SalesContractListResponse(
            total=total,
            items=[SalesContractResponse.model_validate(c) for c in contracts],
        )

    def update_contract(
        self, contract_id: str, data: SalesContractUpdate
    ) -> SalesContractResponse:
        contract = self._require_contract(contract_id)
        if contract.status not in (
            ContractStatus.DRAFT.value,
            ContractStatus.ACTIVE.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Contract '{contract_id}' cannot be updated in status '{contract.status}'.",
            )
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(contract, field, value)
        self.contract_repo.save(contract)
        return SalesContractResponse.model_validate(contract)

    def cancel_contract(self, contract_id: str) -> SalesContractResponse:
        contract = self._require_contract(contract_id)
        if contract.status not in (
            ContractStatus.DRAFT.value,
            ContractStatus.ACTIVE.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only draft or active contracts can be cancelled. "
                       f"Current status: '{contract.status}'.",
            )
        contract.status = ContractStatus.CANCELLED.value
        self.contract_repo.save(contract)
        return SalesContractResponse.model_validate(contract)

    def convert_reservation_to_contract(
        self, reservation_id: str, data: SalesContractCreate
    ) -> SalesContractResponse:
        """Convenience operation: convert an active reservation directly to a contract."""
        if data.reservation_id and data.reservation_id != reservation_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="reservation_id in payload must match the URL reservation ID.",
            )
        # Ensure the payload references the correct reservation
        data_with_res = data.model_copy(update={"reservation_id": reservation_id})
        return self.create_contract(data_with_res)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_unit(self, unit_id: str):
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        return unit

    def _require_buyer(self, buyer_id: str) -> Buyer:
        buyer = self.buyer_repo.get_by_id(buyer_id)
        if not buyer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Buyer '{buyer_id}' not found.",
            )
        return buyer

    def _require_reservation(self, reservation_id: str) -> Reservation:
        reservation = self.reservation_repo.get_by_id(reservation_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reservation '{reservation_id}' not found.",
            )
        return reservation

    def _require_contract(self, contract_id: str) -> SalesContract:
        contract = self.contract_repo.get_by_id(contract_id)
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract '{contract_id}' not found.",
            )
        return contract

    def _require_pricing_for_unit(self, unit_id: str) -> None:
        """Raise 422 if no pricing attributes exist for the unit."""
        from app.modules.pricing.repository import UnitPricingAttributesRepository

        pricing_repo = UnitPricingAttributesRepository(self._db)
        attrs = pricing_repo.get_by_unit(unit_id)
        if not attrs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unit '{unit_id}' must have pricing attributes set before it can be reserved.",
            )
