"""Project report library: immutable PDFs, versioned metadata and retained removal."""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event

# Reuse the bounded PDF worker and source validation used by Plans.
from app.modules.consultant_engineering.drawing_service import (
    MAX_DOCUMENT_BYTES as MAX_DOCUMENT_BYTES,
)
from app.modules.consultant_engineering.drawing_service import (
    inspect_document as inspect_document,
)
from app.modules.consultant_engineering.drawing_service import (
    preview as preview,
)
from app.modules.consultant_engineering.drawing_service import (
    validate_document as validate_document,
)
from app.modules.consultant_engineering.models import ProjectSiteReport
from app.modules.consultant_engineering.permissions import EDITOR_ROLES, READER_ROLES
from app.modules.consultant_engineering.report_schemas import (
    ReportFields,
    ReportLink,
    ReportRead,
    ReportUpdate,
)
from app.modules.projects.models import Project
from app.modules.projects.permissions import whole_project_ids


def scope(
    session: Session, project_id: uuid.UUID, actor: ActorContext, *, write: bool = False
) -> None:
    query = select(Project).where(
        Project.id == project_id, Project.id.in_(whole_project_ids(actor))
    )
    if write:
        query = query.with_for_update().execution_options(populate_existing=True)
    if session.scalars(query).first() is None:
        raise NotFoundError("Project not found.")
    if not actor.role_keys.intersection(EDITOR_ROLES if write else READER_ROLES):
        raise PermissionDeniedError("You do not have permission to access reports.")


def report(session: Session, project_id: uuid.UUID, report_id: uuid.UUID) -> ProjectSiteReport:
    row = session.scalars(
        select(ProjectSiteReport)
        .where(
            ProjectSiteReport.id == report_id,
            ProjectSiteReport.project_id == project_id,
            ProjectSiteReport.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError("Report not found.")
    return row


def list_reports(session: Session, project_id: uuid.UUID) -> list[ReportRead]:
    rows = session.scalars(
        select(ProjectSiteReport)
        .where(ProjectSiteReport.project_id == project_id, ProjectSiteReport.is_deleted.is_(False))
        .order_by(
            ProjectSiteReport.report_date.desc(),
            ProjectSiteReport.created_at.desc(),
            ProjectSiteReport.id,
        )
    ).all()
    return [ReportRead.model_validate(row) for row in rows]


def snapshot(row: ProjectSiteReport) -> dict:
    return {
        **ReportRead.model_validate(row).model_dump(),
        "project_id": row.project_id,
        "sha256": row.sha256,
        "is_deleted": row.is_deleted,
    }


def audit(
    session: Session,
    row: ProjectSiteReport,
    actor: ActorContext,
    action: str,
    before: dict | None = None,
    reason: str | None = None,
) -> None:
    session.flush()
    record_event(
        session,
        action=action,
        entity_type="project_report",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=snapshot(row),
        reason=reason,
    )
    session.commit()


def create(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    fields: ReportFields,
    filename: str,
    document: bytes,
) -> ProjectSiteReport:
    row = ProjectSiteReport(
        project_id=project_id,
        **fields.model_dump(),
        filename=validate_document(filename, document),
        document=document,
        sha256=hashlib.sha256(document).hexdigest(),
    )
    session.add(row)
    audit(session, row, actor, "create")
    return row


def authorize_upload(session: Session, project_id: uuid.UUID, actor: ActorContext) -> None:
    """Refuse an upload before its body is read, holding no lock afterwards."""
    try:
        scope(session, project_id, actor, write=False)
        if not actor.role_keys.intersection(EDITOR_ROLES):
            raise PermissionDeniedError("You do not have permission to access reports.")
    finally:
        session.rollback()


def create_locked(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    fields: ReportFields,
    filename: str,
    document: bytes,
) -> ProjectSiteReport:
    """Take the project lock, re-check authority, then store the received document."""
    scope(session, project_id, actor, write=True)
    return create(session, project_id, actor, fields, filename, document)


def check_version(row: ProjectSiteReport, expected_version: int) -> None:
    if row.version != expected_version:
        raise ConflictError("This report changed. Reload the register before trying again.")


def update(
    session: Session, row: ProjectSiteReport, actor: ActorContext, fields: ReportUpdate
) -> ProjectSiteReport:
    check_version(row, fields.expected_version)
    before = snapshot(row)
    for key, value in fields.model_dump(exclude={"expected_version"}).items():
        setattr(row, key, value)
    row.version += 1
    audit(session, row, actor, "update", before)
    return row


def remove(
    session: Session,
    row: ProjectSiteReport,
    actor: ActorContext,
    reason: str,
    expected_version: int,
) -> None:
    check_version(row, expected_version)
    if not reason.strip():
        raise ValidationError("Enter a reason for deletion.")
    before = snapshot(row)
    row.is_deleted = True
    row.version += 1
    audit(session, row, actor, "delete", before, reason.strip())


def create_link(
    session: Session, project_id: uuid.UUID, actor: ActorContext, fields: ReportLink
) -> ProjectSiteReport:
    scope(session, project_id, actor, write=True)
    row = ProjectSiteReport(project_id=project_id, **fields.model_dump())
    session.add(row)
    audit(session, row, actor, "create")
    return row
