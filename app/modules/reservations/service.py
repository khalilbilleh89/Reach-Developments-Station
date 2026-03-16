"""
reservations.service

Application-layer orchestration for the unit reservation lifecycle.

Responsibilities:
  - Validate unit existence before any operation
  - Prevent double-reservation of the same unit (one ACTIVE per unit)
  - Manage status transitions: cancel, expire, convert
  - Delegate persistence to the repository

All public methods return Pydantic response schemas; ORM objects never cross
the service boundary into API handlers.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
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

        reservation = self._repo.create(data)
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
        """Partially update a reservation (notes, expires_at, status).

        Raises:
            404 — if the reservation does not exist.
        """
        reservation = self._require_reservation(reservation_id)

        if data.notes is not None:
            reservation.notes = data.notes
        if data.expires_at is not None:
            reservation.expires_at = data.expires_at
        if data.status is not None:
            reservation.status = data.status.value

        updated = self._repo.save(reservation)
        return ReservationResponse.model_validate(updated)

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def cancel_reservation(self, reservation_id: str) -> ReservationResponse:
        """Cancel an active reservation.

        Raises:
            404 — if the reservation does not exist.
            409 — if the reservation is not in ACTIVE status.
        """
        reservation = self._require_reservation(reservation_id)

        if reservation.status != ReservationStatus.active.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot cancel reservation with status '{reservation.status}'. "
                    "Only active reservations can be cancelled."
                ),
            )

        reservation.status = ReservationStatus.cancelled.value
        saved = self._repo.save(reservation)
        return ReservationResponse.model_validate(saved)

    def expire_reservation(self, reservation_id: str) -> ReservationResponse:
        """Mark a reservation as expired.

        Raises:
            404 — if the reservation does not exist.
            409 — if the reservation is not in ACTIVE status.
        """
        reservation = self._require_reservation(reservation_id)

        if reservation.status != ReservationStatus.active.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot expire reservation with status '{reservation.status}'. "
                    "Only active reservations can be expired."
                ),
            )

        reservation.status = ReservationStatus.expired.value
        saved = self._repo.save(reservation)
        return ReservationResponse.model_validate(saved)

    def convert_to_contract(self, reservation_id: str) -> ReservationResponse:
        """Mark a reservation as converted (when a contract is created).

        Raises:
            404 — if the reservation does not exist.
            409 — if the reservation is not in ACTIVE status.
        """
        reservation = self._require_reservation(reservation_id)

        if reservation.status != ReservationStatus.active.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot convert reservation with status '{reservation.status}'. "
                    "Only active reservations can be converted."
                ),
            )

        reservation.status = ReservationStatus.converted.value
        saved = self._repo.save(reservation)
        return ReservationResponse.model_validate(saved)

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
            # SQLite returns naive datetimes; treat them as UTC for comparison.
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= now:
                res.status = ReservationStatus.expired.value
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
