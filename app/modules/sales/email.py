"""Reusable project email templates, with scoped writes and retained audit snapshots."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.models import Project
from app.modules.projects.permissions import whole_project_ids
from app.modules.projects.service import lock_project
from app.modules.sales.email_models import CommercialEmail
from app.modules.sales.email_schemas import EmailInput, EmailList, EmailRead, EmailUpdate
from app.modules.sales.permissions import require_sales_reader

WRITERS = frozenset({"system_admin", "project_manager", "sales_operations"})


def can_edit(session: Session, project: Project, actor: ActorContext) -> bool:
    return (actor.is_master_admin or bool(actor.role_keys & WRITERS)) and session.scalar(
        select(Project.id).where(Project.id == project.id, Project.id.in_(whole_project_ids(actor)))
    ) is not None


def _write(session: Session, project: Project, actor: ActorContext) -> None:
    require_sales_reader(actor)
    if not can_edit(session, project, actor):
        raise PermissionDeniedError("You do not have permission to change project email templates.")
    lock_project(session, project.id)


def _read(row: CommercialEmail) -> EmailRead:
    return EmailRead.model_validate(row, from_attributes=True)


def list_emails(session: Session, project: Project, actor: ActorContext) -> EmailList:
    # General project guidance is shared with all assigned Sales readers, including
    # phase-scoped advisors. It contains no buyer- or unit-scoped source data.
    require_sales_reader(actor)
    rows = session.scalars(
        select(CommercialEmail)
        .where(CommercialEmail.project_id == project.id)
        .order_by(CommercialEmail.title, CommercialEmail.id)
    )
    return EmailList(items=[_read(row) for row in rows], can_edit=can_edit(session, project, actor))


def _row(session: Session, project: Project, email_id: uuid.UUID, version: int) -> CommercialEmail:
    row = session.scalar(
        select(CommercialEmail)
        .where(CommercialEmail.project_id == project.id, CommercialEmail.id == email_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Email template not found.")
    if row.version != version:
        raise ConflictError("This email template changed. Reload it before saving or deleting.")
    return row


def _audit(
    session: Session,
    project: Project,
    actor: ActorContext,
    action: str,
    row: CommercialEmail,
    before: dict | None = None,
    reason: str | None = None,
) -> None:
    record_event(
        session,
        action=f"email.{action}",
        entity_type="commercial_email",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after={"project_id": str(project.id), **_read(row).model_dump(mode="json")},
        reason=reason,
    )


def create(
    session: Session, project: Project, actor: ActorContext, payload: EmailInput
) -> EmailRead:
    _write(session, project, actor)
    row = CommercialEmail(project_id=project.id, **payload.model_dump())
    session.add(row)
    session.flush()
    _audit(session, project, actor, "created", row)
    result = _read(row)
    session.commit()
    return result


def update(
    session: Session,
    project: Project,
    actor: ActorContext,
    email_id: uuid.UUID,
    payload: EmailUpdate,
) -> EmailRead:
    _write(session, project, actor)
    row = _row(session, project, email_id, payload.expected_version)
    before = _read(row).model_dump(mode="json")
    row.title, row.body = payload.title, payload.body
    row.subject, row.category = payload.subject, payload.category
    row.version += 1
    _audit(session, project, actor, "updated", row, before)
    result = _read(row)
    session.commit()
    return result


def delete(
    session: Session,
    project: Project,
    actor: ActorContext,
    email_id: uuid.UUID,
    version: int,
    reason: str,
) -> None:
    _write(session, project, actor)
    if not reason.strip():
        raise ValidationError("Enter a reason for deletion.")
    row = _row(session, project, email_id, version)
    _audit(
        session, project, actor, "deleted", row, _read(row).model_dump(mode="json"), reason.strip()
    )
    session.delete(row)
    session.commit()
