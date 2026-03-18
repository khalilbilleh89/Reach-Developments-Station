"""
Unit status rules.

Enforces valid unit status transitions:
  Available → Reserved → Under Contract → Registered

Each transition is one-way — no backwards movement is allowed once a
unit advances in the commercial pipeline.
"""

from app.shared.enums.project import UnitStatus

# Forward-only adjacency: maps each state to the *one* state it may advance to.
_ALLOWED_TRANSITIONS: dict[str, str] = {
    UnitStatus.AVAILABLE.value: UnitStatus.RESERVED.value,
    UnitStatus.RESERVED.value: UnitStatus.UNDER_CONTRACT.value,
    UnitStatus.UNDER_CONTRACT.value: UnitStatus.REGISTERED.value,
}


def is_valid_transition(current: str, requested: str) -> bool:
    """Return True when *requested* is a valid next state from *current*.

    A no-op transition (same → same) is always considered valid — it is
    idempotent and causes no data change in the unit record.
    """
    if current == requested:
        return True
    return _ALLOWED_TRANSITIONS.get(current) == requested


def assert_valid_transition(current: str, requested: str) -> None:
    """Raise ValueError when the transition is not permitted.

    Callers should convert this into an HTTP 422 at the service layer.
    """
    if not is_valid_transition(current, requested):
        allowed = _ALLOWED_TRANSITIONS.get(current, "none")
        raise ValueError(
            f"Invalid status transition: '{current}' → '{requested}'. "
            f"Allowed next state from '{current}': '{allowed}'."
        )
