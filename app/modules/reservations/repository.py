"""
reservations.repository

Database access layer for UnitReservation records.

Responsibilities:
  - CRUD operations on the unit_reservations table
  - Query helpers: get active reservation by unit, list by project
  - Save (commit) after in-place status mutations performed by the service

All business-rule enforcement (unit existence, duplicate-active checks, status
transition validation) is handled by the service layer.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.modules.reservations.models import UnitReservation
from app.modules.reservations.schemas import ReservationCreate, ReservationStatus
from app.modules.units.models import Unit


class ReservationRepository:
    """Database operations for UnitReservation."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_by_id(self, reservation_id: str) -> Optional[UnitReservation]:
        """Return a single reservation by its primary key, or None."""
        return (
            self.db.query(UnitReservation)
            .filter(UnitReservation.id == reservation_id)
            .first()
        )

    def get_active_by_unit(self, unit_id: str) -> Optional[UnitReservation]:
        """Return the ACTIVE reservation for a unit, or None if none exists."""
        return (
            self.db.query(UnitReservation)
            .filter(
                UnitReservation.unit_id == unit_id,
                UnitReservation.status == ReservationStatus.active.value,
            )
            .first()
        )

    def list_by_unit(self, unit_id: str) -> list[UnitReservation]:
        """Return all reservations for a specific unit (all statuses)."""
        return (
            self.db.query(UnitReservation)
            .filter(UnitReservation.unit_id == unit_id)
            .order_by(UnitReservation.created_at.desc())
            .all()
        )

    def list_by_project(self, project_id: str) -> list[UnitReservation]:
        """Return all reservations for units belonging to the given project.

        Joins through the asset hierarchy:
          unit_reservations → units → floors → buildings → phases → projects
        """
        from app.modules.floors.models import Floor
        from app.modules.buildings.models import Building
        from app.modules.phases.models import Phase

        return (
            self.db.query(UnitReservation)
            .join(Unit, UnitReservation.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .order_by(UnitReservation.created_at.desc())
            .all()
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, data: ReservationCreate) -> UnitReservation:
        """Insert a new reservation and return the persisted record."""
        reservation = UnitReservation(**data.model_dump())
        self.db.add(reservation)
        self.db.commit()
        self.db.refresh(reservation)
        return reservation

    def save(self, reservation: UnitReservation) -> UnitReservation:
        """Commit in-place mutations to an existing reservation record."""
        self.db.commit()
        self.db.refresh(reservation)
        return reservation
