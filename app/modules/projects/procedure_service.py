"""Project-scoped manual procedure maps with versioned, audited retention."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.models import Project
from app.modules.projects.permissions import PROJECT_WRITER_ROLES, whole_project_ids
from app.modules.projects.procedure_models import ProjectProcedure
from app.modules.projects.procedure_schemas import (
    ProcedureDirectory,
    ProcedureFields,
    ProcedureRead,
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
    if write and not actor.role_keys.intersection(PROJECT_WRITER_ROLES):
        raise PermissionDeniedError("Only project managers and administrators can edit procedures.")


def read(row: ProjectProcedure) -> ProcedureRead:
    fields = ProcedureFields.model_validate(row.payload)
    return ProcedureRead(
        **fields.model_dump(),
        id=row.id,
        project_id=row.project_id,
        version=row.version,
    )


def directory(session: Session, project_id: uuid.UUID, actor: ActorContext) -> ProcedureDirectory:
    scope(session, project_id, actor)
    rows = session.scalars(
        select(ProjectProcedure)
        .where(ProjectProcedure.project_id == project_id, ProjectProcedure.is_deleted.is_(False))
        .order_by(ProjectProcedure.title, ProjectProcedure.id)
    ).all()
    return ProcedureDirectory(
        procedures=[read(row) for row in rows],
        can_manage=bool(actor.role_keys.intersection(PROJECT_WRITER_ROLES)),
    )


def current(
    session: Session, project_id: uuid.UUID, procedure_id: uuid.UUID, version: int
) -> ProjectProcedure:
    row = session.scalar(
        select(ProjectProcedure)
        .where(
            ProjectProcedure.project_id == project_id,
            ProjectProcedure.id == procedure_id,
            ProjectProcedure.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Procedure not found.")
    if row.version != version:
        raise ConflictError(
            "This procedure changed. Return to Procedure and refresh before editing again."
        )
    return row


def snapshot(row: ProjectProcedure) -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "title": row.title,
        "payload": row.payload,
        "version": row.version,
        "is_deleted": row.is_deleted,
    }


def save(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    fields: ProcedureFields,
    procedure_id: uuid.UUID | None = None,
    version: int = 1,
) -> ProcedureRead:
    scope(session, project_id, actor, write=True)
    row = (
        current(session, project_id, procedure_id, version)
        if procedure_id
        else ProjectProcedure(project_id=project_id)
    )
    before = snapshot(row) if procedure_id else None
    row.title = fields.title
    row.payload = ProcedureFields.model_validate(fields.model_dump(exclude={"version"})).model_dump(
        mode="json"
    )
    if procedure_id:
        row.version += 1
    else:
        session.add(row)
    session.flush()
    record_event(
        session,
        action="update" if procedure_id else "create",
        entity_type="project_procedure",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=snapshot(row),
    )
    session.commit()
    return read(row)


def remove(
    session: Session,
    project_id: uuid.UUID,
    procedure_id: uuid.UUID,
    actor: ActorContext,
    version: int,
    reason: str,
) -> None:
    scope(session, project_id, actor, write=True)
    row = current(session, project_id, procedure_id, version)
    if not reason.strip():
        raise ValidationError("Enter a reason for deletion.")
    before = snapshot(row)
    row.is_deleted = True
    row.version += 1
    session.flush()
    record_event(
        session,
        action="delete",
        entity_type="project_procedure",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before=before,
        after=snapshot(row),
    )
    session.commit()
