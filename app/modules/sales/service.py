"""
sales.service

Application-layer orchestration for the Sales domain.
Enforces business rules for buyers, reservations, and contracts.
"""

from datetime import datetime, timezone
from datetime import date as date_type
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.sales.contract_rules import (
    assert_contract_has_reservation,
    assert_reservation_is_converted,
    assert_valid_contract_transition,
)
from app.modules.sales.models import Buyer, ContractPaymentSchedule, Reservation, SalesContract
from app.modules.sales.repository import (
    BuyerRepository,
    ContractPaymentScheduleRepository,
    ReservationRepository,
    SalesContractRepository,
)
from app.modules.sales.reservation_rules import (
    assert_reservation_is_convertible,
    assert_valid_reservation_transition,
)
from app.modules.sales.schemas import (
    BuyerCreate,
    BuyerListResponse,
    BuyerResponse,
    BuyerUpdate,
    ContractPaymentRecordRequest,
    ContractPaymentScheduleListResponse,
    ContractPaymentScheduleResponse,
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
from app.shared.enums.project import UnitStatus
from app.shared.enums.sales import ContractPaymentStatus, ContractStatus, ReservationStatus

# ---------------------------------------------------------------------------
# Default payment schedule milestones
# ---------------------------------------------------------------------------
# Each tuple is (label, percentage_of_total, days_after_contract_date)
_DEFAULT_MILESTONES = [
    ("Reservation Deposit", 0.10, 0),
    ("Contract Signing",    0.20, 30),
    ("Construction Milestone", 0.40, 180),
    ("Handover",            0.30, 365),
]


def _build_installment_items(contract: "SalesContract") -> list["ContractPaymentSchedule"]:
    """Build default installment rows for a contract without persisting them.

    Rounds early installments to 2 decimal places.  The final installment is
    set to ``contract_price - sum(earlier_installments)`` so the schedule
    always totals *exactly* the contract price, regardless of rounding effects.
    """
    price = round(float(contract.contract_price), 2)
    base_date: date_type = contract.contract_date
    items: list[ContractPaymentSchedule] = []
    cumulative = 0.0
    last_idx = len(_DEFAULT_MILESTONES) - 1
    for i, (_, pct, days) in enumerate(_DEFAULT_MILESTONES):
        due = base_date + timedelta(days=days)
        if i == last_idx:
            amount = round(price - cumulative, 2)
        else:
            amount = round(price * pct, 2)
            cumulative += amount
        items.append(
            ContractPaymentSchedule(
                contract_id=contract.id,
                installment_number=i + 1,
                due_date=due,
                amount=amount,
                currency="AED",
                status=ContractPaymentStatus.PENDING.value,
            )
        )
    return items


class SalesService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self.buyer_repo = BuyerRepository(db)
        self.reservation_repo = ReservationRepository(db)
        self.contract_repo = SalesContractRepository(db)
        self.unit_repo = UnitRepository(db)
        self.payment_schedule_repo = ContractPaymentScheduleRepository(db)

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
        assert_valid_reservation_transition(
            reservation.status, ReservationStatus.CANCELLED.value
        )
        reservation.status = ReservationStatus.CANCELLED.value
        self.reservation_repo.save(reservation)
        return ReservationResponse.model_validate(reservation)

    def expire_reservation(self, reservation_id: str) -> ReservationResponse:
        reservation = self._require_reservation(reservation_id)
        assert_valid_reservation_transition(
            reservation.status, ReservationStatus.EXPIRED.value
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
            assert_reservation_is_convertible(reservation.status, data.reservation_id)

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
        assert_valid_contract_transition(contract.status, ContractStatus.CANCELLED.value)
        contract.status = ContractStatus.CANCELLED.value
        # Release the unit back to available when a contract is cancelled
        self._set_unit_status(contract.unit_id, UnitStatus.AVAILABLE.value)
        self.contract_repo.save(contract)
        return SalesContractResponse.model_validate(contract)

    def activate_contract(self, contract_id: str) -> SalesContractResponse:
        """Activate a draft contract, transitioning it to the ACTIVE state.

        Rules enforced:
          - Contract must be in DRAFT status.
          - Contract must have a linked reservation.
          - The linked reservation must be in CONVERTED status.
          - Unit status is set to UNDER_CONTRACT atomically.
          - Default payment schedule is created in the same transaction.

        All state changes (contract status, unit status, installment rows) are
        committed in a single transaction so that no partial ACTIVE state can
        exist without a complete payment schedule.

        Raises:
            404 — if the contract does not exist.
            422 — if the contract has no reservation linkage.
            422 — if the transition is not permitted by the state machine.
            409 — if the linked reservation is not in CONVERTED status.
        """
        contract = self._require_contract(contract_id)
        assert_valid_contract_transition(contract.status, ContractStatus.ACTIVE.value)
        assert_contract_has_reservation(contract_id, contract.reservation_id)

        # Validate the linked reservation is properly converted
        reservation = self._require_reservation(contract.reservation_id)
        assert_reservation_is_converted(contract_id, contract.reservation_id, reservation.status)

        # Mutate contract and unit — no commit yet
        contract.status = ContractStatus.ACTIVE.value
        self._set_unit_status(contract.unit_id, UnitStatus.UNDER_CONTRACT.value)

        # Stage installment rows into the same session — no commit yet
        for item in _build_installment_items(contract):
            self._db.add(item)

        # Single atomic commit: contract status + unit status + installments
        self._db.commit()
        self._db.refresh(contract)
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

    def _set_unit_status(self, unit_id: str, new_unit_status: str) -> None:
        """Set the unit's availability status on the ORM object without committing.

        The caller is responsible for calling the repository's save() method
        (which calls db.commit()) to persist the change atomically with the
        associated contract/reservation update.
        """
        unit = self.unit_repo.get_by_id(unit_id)
        if unit is not None:
            unit.status = new_unit_status


# ---------------------------------------------------------------------------
# Contract Payment Service
# ---------------------------------------------------------------------------


class ContractPaymentService:
    """Handles payment schedule generation, recording, and status updates."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self.contract_repo = SalesContractRepository(db)
        self.payment_schedule_repo = ContractPaymentScheduleRepository(db)

    # ------------------------------------------------------------------
    # Schedule management
    # ------------------------------------------------------------------

    def generate_payment_schedule(
        self, contract_id: str
    ) -> ContractPaymentScheduleListResponse:
        """Generate the default payment schedule for a contract.

        Raises 404 if the contract does not exist.
        Raises 409 if a schedule already exists (caught at both service and DB
        level — the DB-level unique constraint on (contract_id, installment_number)
        is the authoritative concurrency guard).
        """
        contract = self._require_contract(contract_id)

        existing = self.payment_schedule_repo.count_by_contract(contract_id)
        if existing > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Contract '{contract_id}' already has a payment schedule.",
            )

        items = _build_installment_items(contract)
        try:
            saved = self.payment_schedule_repo.bulk_create(items)
        except IntegrityError:
            self._db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Contract '{contract_id}' already has a payment schedule.",
            )
        return ContractPaymentScheduleListResponse(
            total=len(saved),
            items=[ContractPaymentScheduleResponse.model_validate(s) for s in saved],
        )

    def list_schedule(
        self, contract_id: str
    ) -> ContractPaymentScheduleListResponse:
        """Return all installments for a contract, ordered by installment_number.

        Raises 404 if the contract does not exist.
        """
        self._require_contract(contract_id)
        items = self.payment_schedule_repo.list_by_contract(contract_id)
        return ContractPaymentScheduleListResponse(
            total=len(items),
            items=[ContractPaymentScheduleResponse.model_validate(i) for i in items],
        )

    def record_payment(
        self, contract_id: str, data: ContractPaymentRecordRequest
    ) -> ContractPaymentScheduleResponse:
        """Mark an installment as PAID.

        Raises 404 if the contract or installment does not exist.
        Raises 409 if the installment is already paid or cancelled.
        """
        self._require_contract(contract_id)
        item = self.payment_schedule_repo.get_by_contract_and_installment(
            contract_id, data.installment_number
        )
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Installment #{data.installment_number} not found "
                    f"for contract '{contract_id}'."
                ),
            )
        if item.status == ContractPaymentStatus.PAID.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Installment #{data.installment_number} is already paid.",
            )
        if item.status == ContractPaymentStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Installment #{data.installment_number} is cancelled and cannot be paid.",
            )

        item.status = ContractPaymentStatus.PAID.value
        item.paid_at = data.paid_at or datetime.now(timezone.utc)
        if data.payment_reference is not None:
            item.payment_reference = data.payment_reference

        self.payment_schedule_repo.save(item)
        return ContractPaymentScheduleResponse.model_validate(item)

    def mark_overdue(self, contract_id: str) -> ContractPaymentScheduleListResponse:
        """Mark all past-due PENDING installments as OVERDUE.

        Raises 404 if the contract does not exist.
        """
        self._require_contract(contract_id)
        today = date_type.today()
        items = self.payment_schedule_repo.list_by_contract(contract_id)
        updated: list[ContractPaymentSchedule] = []
        for item in items:
            if (
                item.status == ContractPaymentStatus.PENDING.value
                and item.due_date < today
            ):
                item.status = ContractPaymentStatus.OVERDUE.value
                updated.append(item)
        if updated:
            self._db.commit()
            for item in updated:
                self._db.refresh(item)
        return ContractPaymentScheduleListResponse(
            total=len(items),
            items=[ContractPaymentScheduleResponse.model_validate(i) for i in items],
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_contract(self, contract_id: str) -> SalesContract:
        contract = self.contract_repo.get_by_id(contract_id)
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract '{contract_id}' not found.",
            )
        return contract
