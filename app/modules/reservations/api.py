"""
reservations.api

FastAPI router for the unit reservation endpoints.

Routes:
  POST   /reservations                        → create reservation
  GET    /reservations/{reservation_id}       → get reservation
  PATCH  /reservations/{reservation_id}       → update reservation
  POST   /reservations/{reservation_id}/cancel   → cancel reservation
  POST   /reservations/{reservation_id}/convert  → convert to contract
  GET    /projects/{project_id}/reservations  → list by project
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.reservations.schemas import (
    ReservationCreate,
    ReservationListResponse,
    ReservationResponse,
    ReservationUpdate,
)
from app.modules.reservations.service import ReservationService

router = APIRouter(tags=["reservations"])


def _svc(db: Session = Depends(get_db)) -> ReservationService:
    return ReservationService(db)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post(
    "/reservations",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a unit reservation",
)
def create_reservation(
    data: ReservationCreate,
    svc: ReservationService = Depends(_svc),
) -> ReservationResponse:
    """Place a new hold on a unit for a prospective buyer.

    Returns 409 if the unit already has an active reservation.
    Returns 404 if the unit does not exist.
    """
    return svc.create_reservation(data)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


@router.get(
    "/reservations/{reservation_id}",
    response_model=ReservationResponse,
    summary="Get a reservation by ID",
)
def get_reservation(
    reservation_id: str,
    svc: ReservationService = Depends(_svc),
) -> ReservationResponse:
    """Return the full reservation record for the given ID.

    Returns 404 if the reservation does not exist.
    """
    return svc.get_reservation(reservation_id)


@router.get(
    "/projects/{project_id}/reservations",
    response_model=ReservationListResponse,
    summary="List all reservations for a project",
)
def list_project_reservations(
    project_id: str,
    svc: ReservationService = Depends(_svc),
) -> ReservationListResponse:
    """Return all reservations for units belonging to the given project."""
    return svc.list_reservations_by_project(project_id)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.patch(
    "/reservations/{reservation_id}",
    response_model=ReservationResponse,
    summary="Update a reservation",
)
def update_reservation(
    reservation_id: str,
    data: ReservationUpdate,
    svc: ReservationService = Depends(_svc),
) -> ReservationResponse:
    """Partially update a reservation (notes, expires_at, status).

    Returns 404 if the reservation does not exist.
    """
    return svc.update_reservation(reservation_id, data)


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


@router.post(
    "/reservations/{reservation_id}/cancel",
    response_model=ReservationResponse,
    summary="Cancel a reservation",
)
def cancel_reservation(
    reservation_id: str,
    svc: ReservationService = Depends(_svc),
) -> ReservationResponse:
    """Cancel an active reservation.

    Returns 409 if the reservation is not in ACTIVE status.
    Returns 404 if the reservation does not exist.
    """
    return svc.cancel_reservation(reservation_id)


@router.post(
    "/reservations/{reservation_id}/convert",
    response_model=ReservationResponse,
    summary="Convert a reservation to contract",
)
def convert_reservation(
    reservation_id: str,
    svc: ReservationService = Depends(_svc),
) -> ReservationResponse:
    """Mark a reservation as converted into a formal sales contract.

    Returns 409 if the reservation is not in ACTIVE status.
    Returns 404 if the reservation does not exist.
    """
    return svc.convert_to_contract(reservation_id)
