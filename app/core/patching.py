"""How a PATCH body becomes a set of assignments.

`docs/ENGINEERING_RULES.md` §7 states the rule this implements: routes build the
change set with ``exclude_unset=True``, so an absent key and an explicit
``null`` arrive differently and must stay different all the way into the
service. It lives in ``app/core`` because it is a request-shape convention
shared by every module, and it knows nothing about any domain.
"""

from __future__ import annotations

from app.core.errors import ValidationError


def resolve_updates(
    changes: dict[str, object], *, fields: tuple[str, ...], clearable: frozenset[str]
) -> dict[str, object]:
    """Turn a PATCH body into the assignments to apply.

    Absent says nothing about the field; ``null`` says the value is gone. A
    ``null`` aimed at a column that cannot hold one is a client error, not
    something to drop on the floor and answer 200 to.
    """
    resolved: dict[str, object] = {}
    for field in fields:
        if field not in changes:
            continue
        value = changes[field]
        if value is None and field not in clearable:
            raise ValidationError(f"{field} cannot be null.")
        resolved[field] = value.strip() if isinstance(value, str) else value
    return resolved
