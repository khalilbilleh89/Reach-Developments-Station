"""
reservations.reservation_rules

Formal state machine for the unit reservation lifecycle.

States:
  draft     — reservation created but not yet active
  active    — reservation is live and blocking the unit
  expired   — reservation passed its expiry date without conversion
  cancelled — reservation was cancelled before conversion
  converted — reservation was successfully converted to a contract

Allowed transitions:
  draft     → active, cancelled
  active    → expired, cancelled, converted
  expired   → cancelled
  cancelled → (terminal)
  converted → (terminal)
"""

from fastapi import HTTPException, status

from app.modules.reservations.schemas import ReservationStatus

# ---------------------------------------------------------------------------
# Formal state machine — allowed transitions
# ---------------------------------------------------------------------------

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
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


def assert_valid_transition(current: str, target: str) -> None:
    """Raise 422 if the requested status transition is not permitted by the state machine."""
    allowed = ALLOWED_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Invalid reservation state transition: "
                f"'{current}' → '{target}'. "
                f"Allowed from '{current}': {allowed or ['(none — terminal state)']}"
            ),
        )
