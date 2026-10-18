"""Scoped analysis persistence and exact Decimal BCG classification/geometry."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.matrix_models import ProjectMatrix
from app.modules.projects.matrix_schemas import (
    MatrixDirectory,
    MatrixFields,
    MatrixPoint,
    MatrixRead,
)
from app.modules.projects.models import Project
from app.modules.projects.permissions import PROJECT_WRITER_ROLES, whole_project_ids


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
        raise PermissionDeniedError("Only project managers and administrators can edit analyses.")


def points(fields: MatrixFields) -> list[MatrixPoint]:
    if fields.framework != "bcg":
        return []
    result = []
    for item in fields.items:
        share, growth = item.relative_share, item.growth_pct
        assert share is not None and growth is not None
        high_share = share >= 1
        high_growth = growth >= fields.growth_threshold_pct
        category = (
            ("Stars" if high_share else "Question marks")
            if high_growth
            else ("Cash cows" if high_share else "Dogs")
        )
        # Piecewise bounded axes keep the exact 1x and chosen growth crossings central.
        # Coordinates are display-only; source decimals are always returned unchanged.
        x = 500 - 450 * (share - 1) / max(share, Decimal(1))
        delta = growth - fields.growth_threshold_pct
        y = 300 - 250 * delta / (abs(delta) + fields.growth_threshold_pct)
        result.append(MatrixPoint(label=item.label, category=category, x=int(x), y=int(y)))
    return result


def read(row: ProjectMatrix) -> MatrixRead:
    fields = MatrixFields.model_validate(row.payload)
    return MatrixRead(
        **fields.model_dump(),
        id=row.id,
        project_id=row.project_id,
        version=row.version,
        points=points(fields),
    )


def directory(session: Session, project_id: uuid.UUID, actor: ActorContext) -> MatrixDirectory:
    scope(session, project_id, actor)
    rows = session.scalars(
        select(ProjectMatrix)
        .where(ProjectMatrix.project_id == project_id, ProjectMatrix.is_deleted.is_(False))
        .order_by(ProjectMatrix.title, ProjectMatrix.id)
    ).all()
    return MatrixDirectory(
        analyses=[read(row) for row in rows],
        can_manage=bool(actor.role_keys.intersection(PROJECT_WRITER_ROLES)),
    )


def current(
    session: Session, project_id: uuid.UUID, matrix_id: uuid.UUID, version: int
) -> ProjectMatrix:
    row = session.scalar(
        select(ProjectMatrix)
        .where(
            ProjectMatrix.project_id == project_id,
            ProjectMatrix.id == matrix_id,
            ProjectMatrix.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Analysis not found.")
    if row.version != version:
        raise ConflictError(
            "This analysis changed. Return to Matrix and refresh before editing again."
        )
    return row


def snapshot(row: ProjectMatrix) -> dict:
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
    fields: MatrixFields,
    matrix_id: uuid.UUID | None = None,
    version: int = 1,
) -> MatrixRead:
    scope(session, project_id, actor, write=True)
    row = (
        current(session, project_id, matrix_id, version)
        if matrix_id
        else ProjectMatrix(project_id=project_id)
    )
    before = snapshot(row) if matrix_id else None
    row.title = fields.title
    row.payload = MatrixFields.model_validate(fields.model_dump(exclude={"version"})).model_dump(
        mode="json"
    )
    if matrix_id:
        row.version += 1
    else:
        session.add(row)
    session.flush()
    record_event(
        session,
        action="update" if matrix_id else "create",
        entity_type="project_matrix",
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
    matrix_id: uuid.UUID,
    actor: ActorContext,
    version: int,
    reason: str,
) -> None:
    scope(session, project_id, actor, write=True)
    row = current(session, project_id, matrix_id, version)
    if not reason.strip():
        raise ValidationError("Enter a reason for deletion.")
    before = snapshot(row)
    row.is_deleted = True
    row.version += 1
    session.flush()
    record_event(
        session,
        action="delete",
        entity_type="project_matrix",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before=before,
        after=snapshot(row),
    )
    session.commit()
