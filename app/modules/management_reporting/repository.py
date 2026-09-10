"""Bounded metadata lists; authorize before loading a historical document."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.access.dependencies import ActorContext
from app.modules.management_reporting import canonical, permissions, schemas
from app.modules.management_reporting.models import Snapshot


def detail(session: Session, actor: ActorContext, identifier: uuid.UUID) -> schemas.SnapshotOut:
    row = session.scalar(
        select(Snapshot).where(
            Snapshot.id == identifier, Snapshot.id.in_(permissions.readable(actor))
        )
    )
    if row is None:
        raise NotFoundError("Management snapshot not found.")
    if row.schema_version != 1:
        raise ConflictError("This snapshot schema version requires an explicit reporting adapter.")
    result = schemas.SnapshotOut.model_validate(row)
    if canonical.content_hash(result) != result.content_hash:
        raise ConflictError("Snapshot integrity verification failed.")
    return result


def page(
    session: Session,
    actor: ActorContext,
    *,
    scope: str | None,
    project_id: uuid.UUID | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> schemas.SnapshotPage:
    query = select(*[getattr(Snapshot, key) for key in schemas.SnapshotHeader.model_fields]).where(
        Snapshot.id.in_(permissions.readable(actor))
    )
    if scope:
        query = query.where(Snapshot.scope_type == scope)
    if project_id:
        query = query.where(Snapshot.project_id == project_id)
    if created_from:
        query = query.where(Snapshot.captured_at >= created_from)
    if created_to:
        query = query.where(Snapshot.captured_at <= created_to)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.execute(
        query.order_by(Snapshot.captured_at.desc(), Snapshot.id.desc()).limit(limit).offset(offset)
    ).mappings()
    return schemas.SnapshotPage(
        items=[schemas.SnapshotHeader.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
