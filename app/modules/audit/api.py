"""Read-only audit routes.

There is deliberately no POST, PATCH, PUT or DELETE here. Audit events are
written only as a side effect of the change they describe, inside that change's
transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.access.dependencies import ActorContext, DbSession, require_roles
from app.modules.access.models import ROLE_AUDITOR, ROLE_SYSTEM_ADMIN
from app.modules.audit import service
from app.modules.audit.schemas import AuditEventPage, AuditEventRead

router = APIRouter(prefix="/audit-events", tags=["audit"])

#: Audit history is restricted to the two roles whose job is oversight. It is
#: not widened to executive viewers without a stated requirement.
require_audit_reader = require_roles(ROLE_SYSTEM_ADMIN, ROLE_AUDITOR)

AuditReader = Annotated[ActorContext, Depends(require_audit_reader)]


@router.get("", response_model=AuditEventPage, summary="Read audit history")
def list_audit_events(
    session: DbSession,
    _actor: AuditReader,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    actor_user_id: Annotated[uuid.UUID | None, Query()] = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: Annotated[uuid.UUID | None, Query()] = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
    occurred_from: Annotated[datetime | None, Query()] = None,
    occurred_to: Annotated[datetime | None, Query()] = None,
) -> AuditEventPage:
    rows, total = service.list_events(
        session,
        limit=limit,
        offset=offset,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )
    return AuditEventPage(
        items=[
            AuditEventRead(
                id=event.id,
                occurred_at=event.occurred_at,
                actor_user_id=event.actor_user_id,
                actor_display_name=display_name,
                action=event.action,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                reason=event.reason,
                source=event.source,
                correlation_id=event.correlation_id,
                before_data=event.before_data,
                after_data=event.after_data,
            )
            for event, display_name in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
