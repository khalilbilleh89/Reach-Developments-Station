"""Small, project-owned final-draft library with bounded, immutable documents."""

import hashlib
import io
import uuid
import zipfile
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.agreement_models import ProjectAgreement
from app.modules.projects.agreement_schemas import AgreementFields, AgreementRead, AgreementUpdate
from app.modules.projects.models import Project
from app.modules.projects.permissions import whole_project_ids

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
AGREEMENT_READERS = frozenset(
    {
        "system_admin",
        "project_manager",
        "sales_operations",
        "sales_advisor",
        "legal",
        "collections",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
    }
)
AGREEMENT_WRITERS = frozenset({"system_admin", "project_manager", "sales_operations", "legal"})


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
    if not actor.is_system_admin and not actor.role_keys.intersection(
        AGREEMENT_WRITERS if write else AGREEMENT_READERS
    ):
        raise PermissionDeniedError("You do not have permission to access agreements.")


def agreement(session: Session, project_id: uuid.UUID, agreement_id: uuid.UUID) -> ProjectAgreement:
    row = session.scalars(
        select(ProjectAgreement)
        .where(
            ProjectAgreement.id == agreement_id,
            ProjectAgreement.project_id == project_id,
            ProjectAgreement.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError("Agreement not found.")
    return row


def list_agreements(session: Session, project_id: uuid.UUID) -> list[AgreementRead]:
    rows = session.scalars(
        select(ProjectAgreement)
        .where(ProjectAgreement.project_id == project_id, ProjectAgreement.is_deleted.is_(False))
        .order_by(ProjectAgreement.created_at, ProjectAgreement.id)
    ).all()
    return [AgreementRead.model_validate(row) for row in rows]


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
    suffix = PurePosixPath(filename).suffix.lower()
    valid = suffix == ".pdf" and document.startswith(b"%PDF-")
    if suffix == ".doc":
        valid = document.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(document)) as archive:
                names = set(archive.namelist())
                valid = {"[Content_Types].xml", "word/document.xml"} <= names and not any(
                    name.lower().endswith("vbaproject.bin") for name in names
                )
        except (zipfile.BadZipFile, ValueError):
            valid = False
    if not valid:
        raise ValidationError(
            "Upload a PDF or Word document (.pdf, .doc, .docx) matching its file type."
        )
    return filename


def snapshot(row: ProjectAgreement) -> dict:
    return {
        **AgreementRead.model_validate(row).model_dump(),
        "project_id": row.project_id,
        "sha256": row.sha256,
        "is_deleted": row.is_deleted,
    }


def audit(
    session: Session,
    row: ProjectAgreement,
    actor: ActorContext,
    action: str,
    before: dict | None = None,
    reason: str | None = None,
) -> None:
    session.flush()
    record_event(
        session,
        action=action,
        entity_type="project_agreement",
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
    fields: AgreementFields,
    filename: str,
    document: bytes,
) -> ProjectAgreement:
    row = ProjectAgreement(
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
        if not actor.is_system_admin and not actor.role_keys.intersection(AGREEMENT_WRITERS):
            raise PermissionDeniedError("You do not have permission to access agreements.")
    finally:
        session.rollback()


def create_locked(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    fields: AgreementFields,
    filename: str,
    document: bytes,
) -> ProjectAgreement:
    """Take the project lock, re-check authority, then store the received document."""
    scope(session, project_id, actor, write=True)
    return create(session, project_id, actor, fields, filename, document)


def check_version(row: ProjectAgreement, expected_version: int) -> None:
    if row.version != expected_version:
        raise ConflictError("This agreement changed. Reload the register before trying again.")


def update(
    session: Session, row: ProjectAgreement, actor: ActorContext, fields: AgreementUpdate
) -> ProjectAgreement:
    check_version(row, fields.expected_version)
    before = snapshot(row)
    for key, value in fields.model_dump(exclude={"expected_version"}).items():
        setattr(row, key, value)
    row.version += 1
    audit(session, row, actor, "update", before)
    return row


def remove(
    session: Session, row: ProjectAgreement, actor: ActorContext, reason: str, expected_version: int
) -> None:
    check_version(row, expected_version)
    if not reason.strip():
        raise ValidationError("Enter a reason for deletion.")
    before = snapshot(row)
    row.is_deleted = True
    row.version += 1
    audit(session, row, actor, "delete", before, reason.strip())
