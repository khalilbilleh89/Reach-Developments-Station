"""
sales.contract_rules

Formal state machine and business rules for the sales contract lifecycle.

States:
  draft     — contract created but not yet formally executed
  active    — contract is formally active; unit is sold
  cancelled — contract was cancelled (from draft or active)
  completed — contract has been fully executed (terminal)

Allowed transitions:
  draft     → active, cancelled
  active    → cancelled, completed
  cancelled → (terminal)
  completed → (terminal)

Rules:
  - Contract activation requires a linked reservation
  - Contract activation requires the reservation to be in CONVERTED status
  - Only one draft-or-active contract per unit is allowed at any time
"""

from fastapi import HTTPException, status

from app.shared.enums.sales import ContractStatus, ReservationStatus

# ---------------------------------------------------------------------------
# Formal state machine
# ---------------------------------------------------------------------------

_ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    ContractStatus.DRAFT.value: [
        ContractStatus.ACTIVE.value,
        ContractStatus.CANCELLED.value,
    ],
    ContractStatus.ACTIVE.value: [
        ContractStatus.CANCELLED.value,
        ContractStatus.COMPLETED.value,
    ],
    ContractStatus.CANCELLED.value: [],
    ContractStatus.COMPLETED.value: [],
}


def assert_valid_contract_transition(current: str, target: str) -> None:
    """Raise 422 if the requested contract status transition is not permitted."""
    allowed = _ALLOWED_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Invalid contract state transition: '{current}' → '{target}'. "
                f"Allowed from '{current}': {allowed or ['(none — terminal state)']}"
            ),
        )


def assert_contract_has_reservation(contract_id: str, reservation_id: str | None) -> None:
    """Raise 422 if the contract has no linked reservation.

    Contract activation requires a valid reservation linkage. Contracts
    created without a reservation cannot be activated.
    """
    if not reservation_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Contract '{contract_id}' cannot be activated: "
                "no reservation is linked to this contract. "
                "Contract activation requires a valid reservation."
            ),
        )


def assert_reservation_is_converted(
    contract_id: str, reservation_id: str, reservation_status: str
) -> None:
    """Raise 409 if the linked reservation is not in CONVERTED status.

    When a contract is activated, its reservation must already be CONVERTED
    (which happens automatically when the contract is created from a reservation).
    """
    if reservation_status != ReservationStatus.CONVERTED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Contract '{contract_id}' cannot be activated: "
                f"linked reservation '{reservation_id}' is in status "
                f"'{reservation_status}', expected 'converted'."
            ),
        )
