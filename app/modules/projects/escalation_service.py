"""Scoped, version-checked escalation writes with retained deletion and audit."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.escalation_models import PriceEscalation
from app.modules.projects.escalation_schemas import EscalationRead, EscalationRegister
from app.modules.projects.models import Project
from app.modules.projects.permissions import (
    FINANCIAL_ROLES,
    whole_project_ids,
)

WRITER_ROLES = frozenset({"system_admin", "project_manager", "finance"})


def can_manage(session: Session, project_id: uuid.UUID, actor: ActorContext) -> bool:
    return bool(
        (actor.is_system_admin or actor.role_keys.intersection(WRITER_ROLES))
        and session.scalar(
            select(Project.id).where(
                Project.id == project_id, Project.id.in_(whole_project_ids(actor))
            )
        )
    )


def scope(
    session: Session, project_id: uuid.UUID, actor: ActorContext, *, write: bool = False
) -> None:
    query = select(Project).where(
        Project.id == project_id, Project.id.in_(whole_project_ids(actor))
    )
    if write:
        query = query.with_for_update().execution_options(populate_existing=True)
    if session.scalar(query) is None:
        raise NotFoundError("Project not found.")
    if not (actor.is_system_admin or actor.role_keys.intersection(FINANCIAL_ROLES)):
        raise PermissionDeniedError("You may not read price escalation strategy.")
    if write and not can_manage(session, project_id, actor):
        raise PermissionDeniedError(
            "Only administrators, project managers and Finance can manage price escalations."
        )


def read_entry(row: PriceEscalation) -> EscalationRead:
    return EscalationRead(
        id=row.id,
        project_id=row.project_id,
        effective_date=row.effective_date,
        escalation_percent=row.escalation_rate_fraction * 100,
        project_status=row.project_status,
        version=row.version,
    )


def directory(session: Session, project_id: uuid.UUID, actor: ActorContext) -> EscalationRegister:
    scope(session, project_id, actor)
    rows = session.scalars(
        select(PriceEscalation)
        .where(PriceEscalation.project_id == project_id, PriceEscalation.is_deleted.is_(False))
        .order_by(
            PriceEscalation.effective_date.desc(),
            PriceEscalation.created_at.desc(),
            PriceEscalation.id,
        )
    ).all()
    return EscalationRegister(
        entries=[read_entry(row) for row in rows], can_manage=can_manage(session, project_id, actor)
    )


def entry(
    session: Session, project_id: uuid.UUID, entry_id: uuid.UUID, version: int | None
) -> PriceEscalation:
    row = session.scalar(
        select(PriceEscalation)
        .where(
            PriceEscalation.project_id == project_id,
            PriceEscalation.id == entry_id,
            PriceEscalation.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Price escalation not found.")
    if version is not None and row.version != version:
        raise ConflictError(
            "This escalation was changed by someone else. "
            "Return to the register and refresh before trying again."
        )
    return row


def snapshot(row: PriceEscalation) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def save(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    values: dict,
    entry_id: uuid.UUID | None = None,
) -> EscalationRead:
    scope(session, project_id, actor, write=True)
    row = (
        entry(session, project_id, entry_id, values.pop("version"))
        if entry_id
        else PriceEscalation(project_id=project_id)
    )
    before = snapshot(row) if entry_id else None
    if "escalation_percent" in values:
        values["escalation_rate_fraction"] = values.pop("escalation_percent") / 100
    for key, value in values.items():
        setattr(row, key, value)
    if entry_id:
        row.version += 1
    else:
        session.add(row)
    session.flush()
    record_event(
        session,
        action="update" if entry_id else "create",
        entity_type="project_price_escalation",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=snapshot(row),
    )
    session.commit()
    return read_entry(row)


def remove(
    session: Session,
    project_id: uuid.UUID,
    entry_id: uuid.UUID,
    actor: ActorContext,
    version: int,
    reason: str,
) -> None:
    scope(session, project_id, actor, write=True)
    row = entry(session, project_id, entry_id, version)
    if not reason.strip():
        raise ValidationError("A reason for deletion is required.")
    before = snapshot(row)
    row.is_deleted = True
    row.version += 1
    session.flush()
    record_event(
        session,
        action="delete",
        entity_type="project_price_escalation",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before=before,
        after=snapshot(row),
    )
    session.commit()
