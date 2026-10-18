"""Company registration evidence: bounded PDFs, immutable bytes and retained removal."""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects import company_service
from app.modules.projects.company_models import CompanyDocument
from app.modules.projects.company_schemas import DocumentRead

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def document(session: Session, company_id: uuid.UUID, document_id: uuid.UUID) -> CompanyDocument:
    row = session.scalars(
        select(CompanyDocument)
        .where(
            CompanyDocument.id == document_id,
            CompanyDocument.company_id == company_id,
            CompanyDocument.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError("Company document not found.")
    return row


def list_documents(session: Session, company_id: uuid.UUID) -> list[DocumentRead]:
    rows = session.scalars(
        select(CompanyDocument)
        .where(
            CompanyDocument.company_id == company_id,
            CompanyDocument.is_deleted.is_(False),
        )
        .order_by(CompanyDocument.created_at, CompanyDocument.id)
    ).all()
    return [DocumentRead.model_validate(row) for row in rows]


def authorize_upload(
    session: Session, project_id: uuid.UUID, company_id: uuid.UUID, actor: ActorContext
) -> None:
    # End the read transaction before streaming; never hold a project lock over an upload.
    try:
        company_service.scope(session, project_id, actor)
        if not actor.is_system_admin and not actor.role_keys.intersection(
            company_service.COMPANY_WRITERS
        ):
            raise PermissionDeniedError("You do not have permission to upload company documents.")
        company_service.company(session, project_id, company_id)
    finally:
        session.rollback()


def snapshot(row: CompanyDocument) -> dict:
    return {
        **DocumentRead.model_validate(row).model_dump(),
        "company_id": row.company_id,
        "sha256": row.sha256,
        "is_deleted": row.is_deleted,
    }


def audit(
    session: Session,
    row: CompanyDocument,
    actor: ActorContext,
    action: str,
    before: dict | None = None,
    reason: str | None = None,
) -> None:
    session.flush()
    record_event(
        session,
        action=action,
        entity_type="company_document",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=snapshot(row),
        reason=reason,
    )
    session.commit()


def create_locked(
    session: Session,
    project_id: uuid.UUID,
    company_id: uuid.UUID,
    actor: ActorContext,
    label: str,
    filename: str,
    data: bytes,
) -> CompanyDocument:
    company_service.scope(session, project_id, actor, write=True)
    company_service.company(session, project_id, company_id)
    filename = filename.strip()
    if (
        not filename
        or len(filename) > 255
        or "/" in filename
        or "\\" in filename
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
    ):
        raise ValidationError("Enter a valid PDF filename.")
    if not 0 < len(data) <= MAX_DOCUMENT_BYTES:
        raise ValidationError("Upload a non-empty PDF up to 10 MB.")
    if not filename.lower().endswith(".pdf") or not data.startswith(b"%PDF-"):
        raise ValidationError("Upload a PDF document matching its .pdf file type.")
    row = CompanyDocument(
        company_id=company_id,
        label=label,
        filename=filename,
        document=data,
        sha256=hashlib.sha256(data).hexdigest(),
    )
    session.add(row)
    audit(session, row, actor, "create")
    return row


def change(
    session: Session,
    row: CompanyDocument,
    actor: ActorContext,
    expected_version: int,
    *,
    label: str | None = None,
    reason: str | None = None,
) -> None:
    if row.version != expected_version:
        raise ConflictError("This document changed. Reload the register before trying again.")
    before = snapshot(row)
    if reason is not None:
        if not reason.strip():
            raise ValidationError("Enter a reason for deletion.")
        row.is_deleted = True
    else:
        row.label = label
    row.version += 1
    audit(session, row, actor, "delete" if reason is not None else "update", before, reason)
