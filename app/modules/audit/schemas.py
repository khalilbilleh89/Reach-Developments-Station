"""Public contracts for reading audit history."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    """One recorded governance change."""

    id: uuid.UUID
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    actor_display_name: str | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    reason: str | None
    source: str
    correlation_id: uuid.UUID
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None


class AuditEventPage(BaseModel):
    """One bounded page of audit history, newest first."""

    items: list[AuditEventRead]
    total: int
    limit: int
    offset: int
