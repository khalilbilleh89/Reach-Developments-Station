"""Company registration evidence: bounded PDFs, immutable bytes and retained removal."""

import hashlib
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects import company_service
from app.modules.projects.company_models import CompanyDocument
from app.modules.projects.company_schemas import DOCUMENT_CATEGORIES, DocumentRead

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
    metadata: dict | None = None,
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
    apply_metadata(row, metadata or {}, creating=True)
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
    metadata: dict | None = None,
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
        apply_metadata(row, metadata or {})
    row.version += 1
    audit(session, row, actor, "delete" if reason is not None else "update", before, reason)


def apply_metadata(row: CompanyDocument, values: dict, *, creating: bool = False) -> None:
    previous_category = row.category
    previous_reminder = row.reminder_date
    for key, value in values.items():
        setattr(row, key, value.strip() or None if isinstance(value, str) else value)
    if creating or row.category != previous_category or "other_category" in values:
        if (creating or row.category) and row.category not in DOCUMENT_CATEGORIES:
            raise ValidationError("Select a document category.")
        if row.category == "Other" and not row.other_category:
            raise ValidationError("Specify the other document category.")
        if row.category != "Other":
            row.other_category = None
    if creating and row.verification_status is None:
        row.verification_status = "needs_review"
    if row.issue_date and row.issue_date_not_stated:
        raise ValidationError("Enter an issue date or select Not stated.")
    if row.expiry_date and row.expiry_note:
        raise ValidationError("Enter an expiry date or select an expiry note.")
    if row.issue_date and row.expiry_date and row.issue_date > row.expiry_date:
        raise ValidationError("Expiry date must be on or after the issue date.")
    if row.reminder_days:
        if not row.expiry_date:
            raise ValidationError("A renewal reminder needs an expiry date.")
        if row.expiry_date.toordinal() <= row.reminder_days:
            raise ValidationError("The expiry date is too early for this reminder.")
        row.reminder_date = row.expiry_date - timedelta(days=row.reminder_days)
    elif "reminder_days" in values and "reminder_date" not in values:
        row.reminder_date = None
    if row.reminder_date and not row.reminder_days and row.reminder_date != previous_reminder:
        raise ValidationError("Select a reminder of 30, 60 or 90 days before expiry.")
    if row.reminder_date and (not row.expiry_date or row.reminder_date > row.expiry_date):
        raise ValidationError("A renewal reminder needs an expiry date on or after the reminder.")


def create_link(
    session: Session,
    project_id: uuid.UUID,
    company_id: uuid.UUID,
    actor: ActorContext,
    values: dict,
) -> CompanyDocument:
    company_service.scope(session, project_id, actor, write=True)
    company_service.company(session, project_id, company_id)
    row = CompanyDocument(company_id=company_id)
    apply_metadata(row, values, creating=True)
    session.add(row)
    audit(session, row, actor, "create")
    return row
