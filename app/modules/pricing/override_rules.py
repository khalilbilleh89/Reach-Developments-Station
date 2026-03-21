"""
Price override rules.

Enforces override authorization thresholds:
  ≤2%: Sales Manager
  ≤5%: Development Director
  >5%: CEO
"""

from fastapi import HTTPException, status

# Override authority thresholds by role (percentage of base_price).
# Each role can self-approve overrides up to (and including) their threshold.
OVERRIDE_THRESHOLDS: dict[str, float] = {
    "sales_manager": 2.0,
    "development_director": 5.0,
    "ceo": float("inf"),  # CEO has unlimited override authority.
}

# Human-readable role labels.
ROLE_LABELS: dict[str, str] = {
    "sales_manager": "Sales Manager",
    "development_director": "Development Director",
    "ceo": "CEO",
}

# Ordered authority hierarchy (lowest to highest).
ROLE_HIERARCHY = ["sales_manager", "development_director", "ceo"]


def calculate_override_percent(override_amount: float, base_price: float) -> float:
    """Return the absolute override percentage relative to *base_price*.

    Returns 0.0 when *base_price* is zero to avoid division by zero.
    The percentage is always non-negative (absolute value of the ratio).
    """
    if base_price == 0:
        return 0.0
    return abs(override_amount) / base_price * 100.0


def required_approver_role(override_percent: float) -> str:
    """Return the minimum role required to self-approve an override of *override_percent*.

    Iterates the authority hierarchy from lowest to highest and returns the
    first role whose threshold covers the requested override percentage.

    Returns 'ceo' for any override percentage (CEO always has authority).
    """
    for role in ROLE_HIERARCHY:
        if override_percent <= OVERRIDE_THRESHOLDS[role]:
            return role
    return "ceo"


def assert_override_allowed(user_role: str, override_percent: float) -> None:
    """Raise HTTP 422 when *user_role* is not authorised for an override of *override_percent*.

    Parameters
    ----------
    user_role:
        The caller's role key (e.g. ``'sales_manager'``, ``'ceo'``).
    override_percent:
        Absolute override percentage against base_price (non-negative).

    Raises
    ------
    HTTPException 422
        When the role is unknown or the override exceeds the role's authority
        threshold.  The detail message identifies the required escalation role.
    """
    if user_role not in OVERRIDE_THRESHOLDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Unknown role '{user_role}'. "
                f"Accepted roles: {', '.join(ROLE_HIERARCHY)}."
            ),
        )
    allowed_threshold = OVERRIDE_THRESHOLDS[user_role]
    if override_percent > allowed_threshold:
        required_role = required_approver_role(override_percent)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Override of {override_percent:.2f}% exceeds the authority of "
                f"'{ROLE_LABELS.get(user_role, user_role)}' "
                f"(limit: {allowed_threshold:.1f}%). "
                f"Escalate to: {ROLE_LABELS.get(required_role, required_role)}."
            ),
        )
