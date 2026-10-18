"""Project evidence choices and retained removal. Existing links remain valid."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects import service
from app.modules.projects.models import (
    CATEGORY_DOCUMENT_TYPE,
    DocumentReference,
    Project,
    ProjectDocumentType,
)
from app.modules.settings.service import effective_reference_values, require_active_reference_value


def types(session: Session, project: Project) -> list[dict]:
    configured = effective_reference_values(
        session, category=CATEGORY_DOCUMENT_TYPE, country_pack_id=project.country_pack_id
    )
    rows = {
        v.code: {
            "id": v.id,
            "code": v.code,
            "label": v.label,
            "is_active": v.is_active,
            "removable": False,
        }
        for v in configured
    }
    for row in session.scalars(
        select(ProjectDocumentType)
        .where(ProjectDocumentType.project_id == project.id)
        .order_by(ProjectDocumentType.label)
    ):
        rows[row.code] = {
            "id": row.id,
            "code": row.code,
            "label": row.label,
            "is_active": True,
            "removable": True,
        }
    return list(rows.values())


def require_type(session: Session, project: Project, code: str) -> None:
    if (
        session.scalar(
            select(ProjectDocumentType.id).where(
                ProjectDocumentType.project_id == project.id, ProjectDocumentType.code == code
            )
        )
        is None
    ):
        require_active_reference_value(
            session,
            category=CATEGORY_DOCUMENT_TYPE,
            code=code,
            country_pack_id=project.country_pack_id,
        )


def add_type(session: Session, project: Project, actor: ActorContext, label: str) -> dict:
    project = service.lock_project(session, project.id)
    label = label.strip()
    if not label:
        raise ValidationError("Enter a document type name.")
    if any(v["label"].casefold() == label.casefold() for v in types(session, project)):
        raise ConflictError("A document type with this name already exists.")
    row = ProjectDocumentType(project_id=project.id, code="DOC_" + uuid.uuid4().hex, label=label)
    session.add(row)
    session.flush()
    record_event(
        session,
        action="document_type.created",
        entity_type="project_document_type",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        after={"project_id": project.id, "code": row.code, "label": row.label},
    )
    result = {
        "id": row.id,
        "code": row.code,
        "label": row.label,
        "is_active": True,
        "removable": True,
    }
    session.commit()
    return result


def remove_type(
    session: Session, project: Project, actor: ActorContext, type_id: uuid.UUID, reason: str
) -> None:
    service.lock_project(session, project.id)
    row = session.scalar(
        select(ProjectDocumentType).where(
            ProjectDocumentType.id == type_id, ProjectDocumentType.project_id == project.id
        )
    )
    if row is None:
        raise NotFoundError("Document type not found. Jurisdiction types are managed in Settings.")
    if session.scalar(
        select(DocumentReference.id)
        .where(
            DocumentReference.project_id == project.id,
            DocumentReference.document_type_code == row.code,
        )
        .limit(1)
    ):
        raise ConflictError("This type is used by retained document history and cannot be deleted.")
    record_event(
        session,
        action="document_type.deleted",
        entity_type="project_document_type",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before={"project_id": project.id, "code": row.code, "label": row.label},
        reason=reason,
    )
    session.delete(row)
    session.commit()


def remove_document(
    session: Session, project: Project, actor: ActorContext, document_id: uuid.UUID, reason: str
) -> None:
    service.lock_project(session, project.id)
    row = service.get_document(session, project_id=project.id, document_id=document_id)
    before = service._snapshot(row, service._DOCUMENT_FIELDS)
    row.is_deleted = True
    row.is_active = False
    session.flush()
    record_event(
        session,
        action="document_reference.deleted",
        entity_type=service.ENTITY_DOCUMENT_REFERENCE,
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=service._snapshot(row, service._DOCUMENT_FIELDS),
        reason=reason,
    )
    session.commit()
