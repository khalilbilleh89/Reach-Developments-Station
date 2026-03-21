"""
pricing.status_rules

Canonical lifecycle states and valid transitions for per-unit pricing records.

States
------
draft      — Initial state when a pricing record is first created.
submitted  — Analyst has submitted the pricing for review.
reviewed   — Legacy alias for submitted; accepted for backward compatibility.
approved   — Pricing has been formally approved; record becomes immutable.
archived   — Pricing has been superseded by a newer record; terminal state.

Transitions (canonical)
-----------------------
draft      → submitted  (analyst submits for review)
submitted  → approved   (approver signs off)
approved   → archived   (superseded when new pricing is created)

No backward transitions are permitted.

The ``reviewed`` status is treated as equivalent to ``submitted`` for
backward compatibility.  New code should use ``submitted``.
"""

from fastapi import HTTPException, status

# Ordered sequence of canonical lifecycle states.
PRICING_STATUSES = ("draft", "submitted", "reviewed", "approved", "archived")

# Map of allowed forward transitions.
# ``reviewed`` is included alongside ``submitted`` for backward compatibility.
VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft":     frozenset({"submitted", "reviewed"}),
    "submitted": frozenset({"approved"}),
    "reviewed":  frozenset({"approved"}),
    "approved":  frozenset({"archived"}),
    "archived":  frozenset(),
}

# Statuses that make a pricing record effectively immutable (no price edits).
IMMUTABLE_STATUSES: frozenset[str] = frozenset({"approved", "archived"})

# Status that marks a record as no longer active (superseded).
ARCHIVED_STATUS = "archived"

# Status required for a unit to be eligible for sales.
SALES_ELIGIBLE_STATUS = "approved"


def can_transition(from_status: str, to_status: str) -> bool:
    """Return True when transitioning *from_status* → *to_status* is allowed."""
    allowed = VALID_TRANSITIONS.get(from_status, frozenset())
    return to_status in allowed


def assert_valid_transition(from_status: str, to_status: str) -> None:
    """Raise HTTP 422 when the status transition is not permitted.

    Callers that hold the current status of a pricing record and want to
    apply a new status should call this before persisting the change.
    """
    if not can_transition(from_status, to_status):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Invalid pricing status transition: '{from_status}' → '{to_status}'. "
                f"Allowed next states from '{from_status}': "
                f"{sorted(VALID_TRANSITIONS.get(from_status, frozenset())) or 'none'}."
            ),
        )


def is_immutable(pricing_status: str) -> bool:
    """Return True when the pricing record with *pricing_status* cannot be edited."""
    return pricing_status in IMMUTABLE_STATUSES
