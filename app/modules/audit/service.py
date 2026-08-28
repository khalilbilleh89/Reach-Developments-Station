"""The audit write contract.

Other modules call :func:`record_event`. They never touch
:class:`~app.modules.audit.models.AuditEvent` directly, and audit never reaches
into their tables.

The event is added to the caller's session and flushed, never committed here:
the caller owns the transaction, so the audit row and the change it describes
commit or roll back together.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AUDIT_SOURCE_API, AuditEvent

#: Field names whose values must never reach the audit trail, whatever the
#: caller passes. Matched case-insensitively against a substring of the key so
#: that `password_hash`, `new_password` and `token_hash` are all caught. Fail
#: closed: an unanticipated secret field is redacted by default rather than
#: needing to be remembered.
_REDACTED_KEY_FRAGMENTS = ("password", "token", "secret", "hash")

#: Keys that trip the substring rule but carry no secret. Kept explicit and
#: short — every entry is a deliberate decision that this field is safe, not a
#: convenience. `must_change_password` is a boolean flag whose value is exactly
#: what an auditor reviewing an account reset needs to see.
_NON_SECRET_KEYS = frozenset({"must_change_password"})

#: Substituted for a redacted value, so the trail still shows that a field
#: changed without recording what it changed to.
REDACTED = "[redacted]"


def _serialize(value: object) -> object:
    """Return a JSON-safe representation that preserves financial precision.

    Decimals become strings: JSON numbers are floats, and a float is never an
    acceptable carrier for money or a rate.
    """
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, float):
        # Reached only if a caller passes one; record it losslessly and let the
        # column stay a string so nothing downstream infers float precision.
        return repr(value)
    if isinstance(value, dict):
        return snapshot(value)
    if isinstance(value, list | tuple | set | frozenset):
        return [_serialize(item) for item in value]
    return str(value)


def snapshot(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a JSON-safe, secret-free copy of ``data`` for before/after storage."""
    if data is None:
        return None
    result: dict[str, Any] = {}
    for key, value in data.items():
        lowered = key.casefold()
        if lowered not in _NON_SECRET_KEYS and any(
            fragment in lowered for fragment in _REDACTED_KEY_FRAGMENTS
        ):
            result[key] = REDACTED
            continue
        result[key] = _serialize(value)
    return result


def record_event(
    session: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    correlation_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
    reason: str | None = None,
    source: str = AUDIT_SOURCE_API,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add an audit event to the caller's open transaction.

    Does not commit. The caller's commit makes both the change and its audit
    record durable; the caller's rollback discards both.
    """
    event = AuditEvent(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        reason=reason,
        source=source,
        before_data=snapshot(before),
        after_data=snapshot(after),
    )
    session.add(event)
    session.flush()
    return event


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


def list_events(
    session: Session,
    *,
    limit: int,
    offset: int,
    actor_user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    action: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> tuple[list[tuple[AuditEvent, str | None]], int]:
    """Return one page of events, newest first, paired with the actor's name.

    Read-only by construction: this module exposes no update or delete path.
    """
    filters = []
    if actor_user_id is not None:
        filters.append(AuditEvent.actor_user_id == actor_user_id)
    if entity_type is not None:
        filters.append(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        filters.append(AuditEvent.entity_id == entity_id)
    if action is not None:
        filters.append(AuditEvent.action == action)
    if occurred_from is not None:
        filters.append(AuditEvent.occurred_at >= occurred_from)
    if occurred_to is not None:
        filters.append(AuditEvent.occurred_at <= occurred_to)

    total = session.scalar(select(func.count()).select_from(AuditEvent).where(*filters)) or 0
    rows = session.execute(
        select(AuditEvent, User.display_name)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(*filters)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [(event, display_name) for event, display_name in rows], total
