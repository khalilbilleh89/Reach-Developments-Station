"""Project drawing library: immutable PDFs, versioned metadata and retained removal."""

import base64
import hashlib
import subprocess
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.consultant_engineering.drawing_schemas import (
    DrawingFields,
    DrawingRead,
    DrawingUpdate,
)
from app.modules.consultant_engineering.models import ProjectDrawing
from app.modules.consultant_engineering.permissions import EDITOR_ROLES, READER_ROLES
from app.modules.projects.models import Project
from app.modules.projects.permissions import whole_project_ids

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


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
        raise PermissionDeniedError("You do not have permission to access drawings.")


def drawing(session: Session, project_id: uuid.UUID, drawing_id: uuid.UUID) -> ProjectDrawing:
    row = session.scalars(
        select(ProjectDrawing)
        .where(
            ProjectDrawing.id == drawing_id,
            ProjectDrawing.project_id == project_id,
            ProjectDrawing.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError("Drawing not found.")
    return row


def list_drawings(session: Session, project_id: uuid.UUID) -> list[DrawingRead]:
    rows = session.scalars(
        select(ProjectDrawing)
        .where(ProjectDrawing.project_id == project_id, ProjectDrawing.is_deleted.is_(False))
        .order_by(ProjectDrawing.created_at, ProjectDrawing.id)
    ).all()
    return [DrawingRead.model_validate(row) for row in rows]


def validate_document(filename: str, document: bytes) -> str:
    filename = filename.strip()
    if (
        not filename
        or len(filename) > 255
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
        or "/" in filename
        or "\\" in filename
    ):
        raise ValidationError("Enter a valid document filename.")
    if not 0 < len(document) <= MAX_DOCUMENT_BYTES:
        raise ValidationError("Upload a non-empty document up to 10 MB.")
    if not filename.lower().endswith(".pdf") or not document.startswith(b"%PDF-"):
        raise ValidationError("Upload a PDF matching its .pdf file type.")
    return filename


def snapshot(row: ProjectDrawing) -> dict:
    return {
        **DrawingRead.model_validate(row).model_dump(),
        "project_id": row.project_id,
        "sha256": row.sha256,
        "is_deleted": row.is_deleted,
    }


def audit(
    session: Session,
    row: ProjectDrawing,
    actor: ActorContext,
    action: str,
    before: dict | None = None,
    reason: str | None = None,
) -> None:
    session.flush()
    record_event(
        session,
        action=action,
        entity_type="project_drawing",
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
    fields: DrawingFields,
    filename: str,
    document: bytes,
) -> ProjectDrawing:
    row = ProjectDrawing(
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
            raise PermissionDeniedError("You do not have permission to access drawings.")
    finally:
        session.rollback()


def create_locked(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    fields: DrawingFields,
    filename: str,
    document: bytes,
) -> ProjectDrawing:
    """Take the project lock, re-check authority, then store the received document."""
    scope(session, project_id, actor, write=True)
    return create(session, project_id, actor, fields, filename, document)


def check_version(row: ProjectDrawing, expected_version: int) -> None:
    if row.version != expected_version:
        raise ConflictError("This drawing changed. Reload the register before trying again.")


def update(
    session: Session, row: ProjectDrawing, actor: ActorContext, fields: DrawingUpdate
) -> ProjectDrawing:
    check_version(row, fields.expected_version)
    before = snapshot(row)
    for key, value in fields.model_dump(exclude={"expected_version"}).items():
        setattr(row, key, value)
    row.version += 1
    audit(session, row, actor, "update", before)
    return row


def remove(
    session: Session, row: ProjectDrawing, actor: ActorContext, reason: str, expected_version: int
) -> None:
    check_version(row, expected_version)
    if not reason.strip():
        raise ValidationError("Enter a reason for deletion.")
    before = snapshot(row)
    row.is_deleted = True
    row.version += 1
    audit(session, row, actor, "delete", before, reason.strip())


def preview(data: bytes, page: int) -> dict:
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.modules.consultant_engineering.drawing_render",
                str(page - 1),
            ],
            input=data,
            capture_output=True,
            timeout=30,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        count, image = result.stdout.split(b"\n", 1)
        if not image.startswith(b"\x89PNG\r\n\x1a\n") or len(image) > 25 * 1024 * 1024:
            raise ValueError("Invalid preview")
        return {
            "page_count": int(count),
            "image": "data:image/png;base64," + base64.b64encode(image).decode("ascii"),
        }
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        raise ValidationError("Could not preview this page. Use a valid, unencrypted PDF.") from exc
