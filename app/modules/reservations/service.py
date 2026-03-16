"""
reservations.service

Application-layer orchestration for the unit reservation lifecycle.

Responsibilities:
  - Validate unit existence before any operation
  - Prevent double-reservation of the same unit (one ACTIVE per unit)
  - Manage status transitions via a formal state machine
  - Enforce unit availability rules on status change
  - Delegate persistence to the repository

All public methods return Pydantic response schemas; ORM objects never cross
the service boundary into API handlers.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.reservations.repository import ReservationRepository
from app.modules.reservations.schemas import (
    ReservationCreate,
    ReservationListResponse,
    ReservationResponse,
    ReservationStatus,
    ReservationUpdate,
)
from app.modules.units.repository import UnitRepository
from app.shared.enums.project import UnitStatus

# ---------------------------------------------------------------------------
# Formal state machine — allowed transitions
# ---------------------------------------------------------------------------

_ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    ReservationStatus.draft.value: [
        ReservationStatus.active.value,
        ReservationStatus.cancelled.value,
    ],
    ReservationStatus.active.value: [
        ReservationStatus.expired.value,
        ReservationStatus.cancelled.value,
        ReservationStatus.converted.value,
    ],
    ReservationStatus.expired.value: [
        ReservationStatus.cancelled.value,
    ],
    ReservationStatus.cancelled.value: [],
    ReservationStatus.converted.value: [],
}

# Map from new reservation status to the corresponding unit availability status.
_UNIT_STATUS_MAP: dict[str, str] = {
    ReservationStatus.active.value: UnitStatus.RESERVED.value,
    ReservationStatus.expired.value: UnitStatus.AVAILABLE.value,
    ReservationStatus.cancelled.value: UnitStatus.AVAILABLE.value,
    ReservationStatus.converted.value: UnitStatus.UNDER_CONTRACT.value,
    # DRAFT does not affect unit availability
}


class ReservationService:
    """Service for managing the UnitReservation lifecycle."""

    def __init__(self, db: Session) -> None:
        self._repo = ReservationRepository(db)
        self._unit_repo = UnitRepository(db)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_reservation(self, data: ReservationCreate) -> ReservationResponse:
        """Create a new active reservation for a unit.

        Raises:
            404  — if the unit does not exist.
            409  — if the unit already has an active reservation.
        """
        self._require_unit(data.unit_id)

        existing = self._repo.get_active_by_unit(data.unit_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unit '{data.unit_id}' already has an active reservation.",
            )

        try:
            reservation = self._repo.create(data)
        except IntegrityError:
            self._repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unit '{data.unit_id}' already has an active reservation.",
            )
        return ReservationResponse.model_validate(reservation)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_reservation(self, reservation_id: str) -> ReservationResponse:
        """Fetch a single reservation by ID.

        Raises:
            404 — if the reservation does not exist.
        """
        reservation = self._require_reservation(reservation_id)
        return ReservationResponse.model_validate(reservation)

    def get_active_by_unit(self, unit_id: str) -> ReservationResponse | None:
        """Return the active reservation for a unit, or None."""
        reservation = self._repo.get_active_by_unit(unit_id)
        if reservation is None:
            return None
        return ReservationResponse.model_validate(reservation)

    def list_reservations_by_project(self, project_id: str) -> ReservationListResponse:
        """Return all reservations for units within the given project."""
        reservations = self._repo.list_by_project(project_id)
        return ReservationListResponse(
            total=len(reservations),
            items=[ReservationResponse.model_validate(r) for r in reservations],
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_reservation(
        self, reservation_id: str, data: ReservationUpdate
    ) -> ReservationResponse:
        """Partially update an active reservation (notes, expires_at).

        Only ACTIVE reservations may be updated. Status transitions must go
        through the dedicated lifecycle endpoints (cancel, expire, convert).

        Uses model_fields_set so that explicitly-provided nulls (e.g.
        ``{"notes": null}``) clear the field, while omitted fields are left
        unchanged.

        Raises:
            404 — if the reservation does not exist.
            409 — if the reservation is not in ACTIVE status.
        """
        reservation = self._require_reservation(reservation_id)

        if reservation.status != ReservationStatus.active.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot update reservation with status '{reservation.status}'. "
                    "Only active reservations can be updated."
                ),
            )

        provided = data.model_fields_set
        if "notes" in provided:
            reservation.notes = data.notes
        if "expires_at" in provided:
            reservation.expires_at = data.expires_at

        updated = self._repo.save(reservation)
        return ReservationResponse.model_validate(updated)

    # ------------------------------------------------------------------
    # Status transitions — central state machine
    # ------------------------------------------------------------------

    def transition_reservation_status(
        self, reservation_id: str, new_status: ReservationStatus
    ) -> ReservationResponse:
        """Transition a reservation to a new lifecycle status.

        Validates the transition against the formal state machine and
        enforces unit availability rules:
          - ACTIVE    → unit becomes reserved
          - CANCELLED / EXPIRED → unit becomes available
          - CONVERTED → unit becomes under contract

        Raises:
            404 — if the reservation does not exist.
            422 — if the transition is not permitted by the state machine.
            409 — if activating would create a duplicate active reservation.
        """
        reservation = self._require_reservation(reservation_id)
        current = reservation.status
        target = new_status.value

        allowed = _ALLOWED_TRANSITIONS.get(current, [])
        if target not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Invalid reservation state transition: "
                    f"'{current}' → '{target}'. "
                    f"Allowed from '{current}': {allowed or ['(none — terminal state)']}"
                ),
            )

        # Prevent a second ACTIVE reservation on the same unit.
        if target == ReservationStatus.active.value:
            existing = self._repo.get_active_by_unit(reservation.unit_id)
            if existing and existing.id != reservation.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Unit '{reservation.unit_id}' already has an active reservation."
                    ),
                )

        reservation.status = target
        saved = self._repo.save(reservation)

        # Sync unit availability with the new reservation status.
        unit_status = _UNIT_STATUS_MAP.get(target)
        if unit_status is not None:
            self._update_unit_status(reservation.unit_id, unit_status)

        return ReservationResponse.model_validate(saved)

    def cancel_reservation(self, reservation_id: str) -> ReservationResponse:
        """Cancel an active or expired reservation.

        Delegates to the central state machine.

        Raises:
            404 — if the reservation does not exist.
            422 — if the reservation is not in ACTIVE or EXPIRED status.
        """
        return self.transition_reservation_status(
            reservation_id, ReservationStatus.cancelled
        )

    def expire_reservation(self, reservation_id: str) -> ReservationResponse:
        """Mark a reservation as expired.

        Delegates to the central state machine.

        Raises:
            404 — if the reservation does not exist.
            422 — if the reservation is not in ACTIVE status.
        """
        return self.transition_reservation_status(
            reservation_id, ReservationStatus.expired
        )

    def convert_to_contract(self, reservation_id: str) -> ReservationResponse:
        """Mark a reservation as converted (when a contract is created).

        Delegates to the central state machine.

        Raises:
            404 — if the reservation does not exist.
            422 — if the reservation is not in ACTIVE status.
        """
        return self.transition_reservation_status(
            reservation_id, ReservationStatus.converted
        )

    # ------------------------------------------------------------------
    # Auto-expiry helper (called by scheduled tasks / admin endpoints)
    # ------------------------------------------------------------------

    def expire_overdue_reservations(self) -> int:
        """Expire all active reservations whose expires_at is in the past.

        Returns the number of reservations transitioned to EXPIRED.
        """
        from app.modules.reservations.models import UnitReservation

        now = datetime.now(timezone.utc)
        active_reservations = (
            self._repo.db.query(UnitReservation)
            .filter(
                UnitReservation.status == ReservationStatus.active.value,
                UnitReservation.expires_at.isnot(None),
            )
            .all()
        )

        expired_count = 0
        for res in active_reservations:
            expires = res.expires_at
            if expires is None:
                continue
            # Normalize naive datetimes (e.g. from SQLite) to UTC before comparing.
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= now:
                res.status = ReservationStatus.expired.value
                # Update unit availability for each expired reservation.
                self._update_unit_status(res.unit_id, UnitStatus.AVAILABLE.value)
                expired_count += 1

        if expired_count:
            self._repo.db.commit()

        return expired_count

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_unit(self, unit_id: str):
        unit = self._unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        return unit

    def _require_reservation(self, reservation_id: str):
        reservation = self._repo.get_by_id(reservation_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reservation '{reservation_id}' not found.",
            )
        return reservation

    def _update_unit_status(self, unit_id: str, new_unit_status: str) -> None:
        """Update the unit's availability status to reflect the reservation state."""
        from app.modules.units.schemas import UnitUpdate

        unit = self._unit_repo.get_by_id(unit_id)
        if unit is not None:
            self._unit_repo.update(unit, UnitUpdate(status=new_unit_status))
