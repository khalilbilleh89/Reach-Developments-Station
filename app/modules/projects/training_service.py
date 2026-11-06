"""Scoped training media, bounded immutable files and retained removal."""

import hashlib
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, undefer

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.marketing.assets import file_payload
from app.modules.projects.training_models import ProjectTraining
from app.modules.projects.training_permissions import scope
from app.modules.projects.training_schemas import AssetCreate, AssetRead, AssetRegister, AssetUpdate

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_PDF_BYTES = 10 * 1024 * 1024


def authorize_upload(session: Session, project_id: uuid.UUID, actor: ActorContext) -> None:
    try:
        scope(session, project_id, actor, write=True)
    finally:
        session.rollback()


def get_asset(
    session: Session, project_id: uuid.UUID, asset_id: uuid.UUID, *, include_data: bool = False
) -> ProjectTraining:
    query = select(ProjectTraining).where(
        ProjectTraining.project_id == project_id,
        ProjectTraining.id == asset_id,
        ProjectTraining.is_deleted.is_(False),
    )
    if include_data:
        query = query.options(undefer(ProjectTraining.data))
    row = session.scalar(query.execution_options(populate_existing=True))
    if row is None:
        raise NotFoundError("Training material not found.")
    return row


def register(
    session: Session,
    project_id: uuid.UUID,
    search: str,
    category: str,
    kind: str | None,
    offset: int,
    limit: int,
) -> AssetRegister:
    base = (
        ProjectTraining.project_id == project_id,
        ProjectTraining.is_deleted.is_(False),
    )
    filters = list(base)
    if search:
        filters.append(
            or_(
                ProjectTraining.title.icontains(search, autoescape=True),
                ProjectTraining.description.icontains(search, autoescape=True),
                ProjectTraining.category.icontains(search, autoescape=True),
            )
        )
    if category:
        filters.append(ProjectTraining.category == category)
    if kind:
        filters.append(ProjectTraining.kind == kind)
    total = session.scalar(select(func.count()).select_from(ProjectTraining).where(*filters))
    rows = session.scalars(
        select(ProjectTraining)
        .where(*filters)
        .order_by(
            ProjectTraining.execution_date.desc(),
            ProjectTraining.created_at.desc(),
            ProjectTraining.id,
        )
        .offset(offset)
        .limit(limit)
    )
    categories = session.scalars(
        select(ProjectTraining.category).where(*base).distinct().order_by(ProjectTraining.category)
    )
    return AssetRegister(
        total=total, items=[AssetRead.model_validate(r) for r in rows], categories=list(categories)
    )


def snapshot(row: ProjectTraining) -> dict:
    return {
        **AssetRead.model_validate(row).model_dump(),
        "project_id": row.project_id,
        "sha256": row.sha256,
        "is_deleted": row.is_deleted,
    }


def commit(
    session: Session,
    row: ProjectTraining,
    actor: ActorContext,
    before: dict | None = None,
    reason: str | None = None,
) -> ProjectTraining:
    session.add(row)
    session.flush()
    record_event(
        session,
        entity_type="project_training",
        entity_id=row.id,
        action="delete" if reason else "update" if before else "create",
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=snapshot(row),
        reason=reason,
    )
    session.commit()
    return row


def create(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    body: AssetCreate,
    filename: str | None = None,
    data: bytes | None = None,
) -> ProjectTraining:
    # Decode before taking the write lock; request already authorized before streaming.
    payload = file_payload(body.kind, filename or "", data) if data is not None else None
    if (payload is None) == (body.external_url is None):
        raise ValidationError("Choose one uploaded file or one external link.")
    scope(session, project_id, actor, write=True)
    count = session.scalar(
        select(func.count())
        .select_from(ProjectTraining)
        .where(
            ProjectTraining.project_id == project_id,
            ProjectTraining.is_deleted.is_(False),
        )
    )
    if count >= 500:
        raise ValidationError(
            "Attachment limit reached. Delete an unused item before adding another."
        )
    row = ProjectTraining(project_id=project_id, **body.model_dump())
    if payload:
        row.filename, row.media_type, row.data = payload
        row.byte_count = len(row.data)
        row.sha256 = hashlib.sha256(row.data).hexdigest()
    return commit(session, row, actor)


def change(
    session: Session,
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    actor: ActorContext,
    expected_version: int,
    body: AssetUpdate | None = None,
    reason: str | None = None,
) -> ProjectTraining:
    scope(session, project_id, actor, write=True)
    row = get_asset(session, project_id, asset_id)
    if row.version != expected_version:
        raise ConflictError("This attachment changed. Reload before trying again.")
    before = snapshot(row)
    if reason is not None:
        row.is_deleted = True
    elif body:
        for key, value in body.model_dump(exclude={"expected_version"}).items():
            setattr(row, key, value)
    row.version += 1
    return commit(session, row, actor, before, reason)
