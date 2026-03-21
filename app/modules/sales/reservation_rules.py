"""
sales.reservation_rules

Formal state machine for sales-domain reservation lifecycle.

States:
  active    — reservation is live and blocking the unit
  expired   — reservation passed its expiry date without conversion
  cancelled — reservation was cancelled before conversion
  converted — reservation was successfully converted to a contract

Allowed transitions:
  active    → expired, cancelled, converted
  expired   → cancelled
  cancelled → (terminal)
  converted → (terminal)
"""

from fastapi import HTTPException, status

from app.shared.enums.sales import ReservationStatus

# ---------------------------------------------------------------------------
# Formal state machine
# ---------------------------------------------------------------------------

_ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    ReservationStatus.ACTIVE.value: [
        ReservationStatus.EXPIRED.value,
        ReservationStatus.CANCELLED.value,
        ReservationStatus.CONVERTED.value,
    ],
    ReservationStatus.EXPIRED.value: [
        ReservationStatus.CANCELLED.value,
    ],
    ReservationStatus.CANCELLED.value: [],
    ReservationStatus.CONVERTED.value: [],
}


def assert_valid_reservation_transition(current: str, target: str) -> None:
    """Raise 422 if the requested status transition is not permitted."""
    allowed = _ALLOWED_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Invalid reservation state transition: '{current}' → '{target}'. "
                f"Allowed from '{current}': {allowed or ['(none — terminal state)']}"
            ),
        )


def assert_reservation_is_active(reservation_status: str, reservation_id: str) -> None:
    """Raise 409 if the reservation is not in ACTIVE status."""
    if reservation_status != ReservationStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Reservation '{reservation_id}' is not active. "
                f"Current status: '{reservation_status}'."
            ),
        )


def assert_reservation_is_convertible(reservation_status: str, reservation_id: str) -> None:
    """Raise 409 if the reservation cannot be linked to a contract.

    A reservation must be ACTIVE to be converted.
    A CONVERTED reservation indicates it was already used by another contract.
    """
    if reservation_status != ReservationStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Reservation '{reservation_id}' is not active "
                f"and cannot be converted to a contract. "
                f"Current status: '{reservation_status}'."
            ),
        )
