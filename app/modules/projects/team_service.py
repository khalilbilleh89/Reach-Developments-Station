"""Scoped, version-checked directory writes with retained deletion and audit."""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.agreement_service import validate_document
from app.modules.projects.models import Project
from app.modules.projects.permissions import (
    PROJECT_WRITER_ROLES,
    visible_projects,
    whole_project_ids,
)
from app.modules.projects.team_models import ProjectTeamMember, TeamJobDescription
from app.modules.projects.team_schemas import JobDescriptionRead, TeamDirectory, TeamMemberRead


def can_manage(session: Session, project_id: uuid.UUID, actor: ActorContext) -> bool:
    return bool(
        (actor.is_system_admin or actor.role_keys.intersection(PROJECT_WRITER_ROLES))
        and session.scalar(
            select(Project.id).where(
                Project.id == project_id, Project.id.in_(whole_project_ids(actor))
            )
        )
    )


def scope(
    session: Session, project_id: uuid.UUID, actor: ActorContext, *, write: bool = False
) -> None:
    query = visible_projects(select(Project).where(Project.id == project_id), actor=actor)
    if write:
        query = query.with_for_update().execution_options(populate_existing=True)
    if session.scalar(query) is None:
        raise NotFoundError("Project not found.")
    if write and not can_manage(session, project_id, actor):
        raise PermissionDeniedError(
            "Only whole-project administrators and project managers can manage the team."
        )


def directory(session: Session, project_id: uuid.UUID, actor: ActorContext) -> TeamDirectory:
    scope(session, project_id, actor)
    rows = session.scalars(
        select(ProjectTeamMember)
        .where(ProjectTeamMember.project_id == project_id, ProjectTeamMember.is_deleted.is_(False))
        .order_by(ProjectTeamMember.name, ProjectTeamMember.id)
    ).all()
    documents = {
        file.member_id: file
        for file in session.scalars(
            select(TeamJobDescription)
            .join(ProjectTeamMember)
            .where(
                ProjectTeamMember.project_id == project_id,
                ProjectTeamMember.is_deleted.is_(False),
                TeamJobDescription.is_deleted.is_(False),
            )
        )
    }
    return TeamDirectory(
        members=[
            TeamMemberRead.model_validate(row).model_copy(
                update={
                    "job_description": JobDescriptionRead.model_validate(documents[row.id])
                    if row.id in documents
                    else None
                }
            )
            for row in rows
        ],
        can_manage=can_manage(session, project_id, actor),
    )


def member(
    session: Session, project_id: uuid.UUID, member_id: uuid.UUID, version: int | None
) -> ProjectTeamMember:
    row = session.scalar(
        select(ProjectTeamMember)
        .where(
            ProjectTeamMember.project_id == project_id,
            ProjectTeamMember.id == member_id,
            ProjectTeamMember.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Team member not found.")
    if version is not None and row.version != version:
        raise ConflictError(
            "This person was changed by someone else. "
            "Return to the directory and refresh before trying again."
        )
    return row


def snapshot(row: ProjectTeamMember) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def save(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    values: dict,
    member_id: uuid.UUID | None = None,
) -> TeamMemberRead:
    scope(session, project_id, actor, write=True)
    row = (
        member(session, project_id, member_id, values.pop("version"))
        if member_id
        else ProjectTeamMember(project_id=project_id)
    )
    before = snapshot(row) if member_id else None
    for key, value in values.items():
        setattr(row, key, value)
    if member_id:
        row.version += 1
    else:
        session.add(row)
    session.flush()
    record_event(
        session,
        action="update" if member_id else "create",
        entity_type="project_team_member",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=snapshot(row),
    )
    session.commit()
    return read_member(session, row)


def remove(
    session: Session,
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    actor: ActorContext,
    version: int,
    reason: str,
) -> None:
    scope(session, project_id, actor, write=True)
    row = member(session, project_id, member_id, version)
    if not reason.strip():
        raise ValidationError("A reason for deletion is required.")
    before = snapshot(row)
    row.is_deleted = True
    row.version += 1
    session.flush()
    record_event(
        session,
        action="delete",
        entity_type="project_team_member",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before=before,
        after=snapshot(row),
    )
    session.commit()


def current_document(session: Session, member_id: uuid.UUID) -> TeamJobDescription | None:
    return session.scalar(
        select(TeamJobDescription)
        .where(TeamJobDescription.member_id == member_id, TeamJobDescription.is_deleted.is_(False))
        .execution_options(populate_existing=True)
    )


def read_member(session: Session, row: ProjectTeamMember) -> TeamMemberRead:
    result = TeamMemberRead.model_validate(row)
    document = current_document(session, row.id)
    result.job_description = JobDescriptionRead.model_validate(document) if document else None
    return result


def authorize_document_upload(
    session: Session, project_id: uuid.UUID, member_id: uuid.UUID, actor: ActorContext, version: int
) -> None:
    # Check before streaming without holding the project write lock across client I/O.
    try:
        scope(session, project_id, actor)
        if not can_manage(session, project_id, actor):
            raise PermissionDeniedError(
                "Only whole-project administrators and project managers can manage the team."
            )
        member(session, project_id, member_id, version)
    finally:
        session.rollback()


def document_snapshot(row: TeamJobDescription) -> dict:
    return {
        "id": row.id,
        "member_id": row.member_id,
        "filename": row.filename,
        "sha256": row.sha256,
        "is_deleted": row.is_deleted,
    }


def save_document(
    session: Session,
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    actor: ActorContext,
    version: int,
    filename: str,
    document: bytes,
) -> TeamMemberRead:
    filename = validate_document(filename, document)
    scope(session, project_id, actor, write=True)
    person = member(session, project_id, member_id, version)
    previous = current_document(session, member_id)
    before = document_snapshot(previous) if previous else None
    if previous:
        previous.is_deleted = True
        session.flush()
    row = TeamJobDescription(
        member_id=member_id,
        filename=filename,
        document=document,
        sha256=hashlib.sha256(document).hexdigest(),
    )
    session.add(row)
    person.version += 1
    session.flush()
    record_event(
        session,
        action="replace" if previous else "create",
        entity_type="team_job_description",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=document_snapshot(row),
        reason="Replaced job description" if previous else None,
    )
    session.commit()
    return read_member(session, person)


def download_document(
    session: Session, project_id: uuid.UUID, member_id: uuid.UUID, actor: ActorContext
) -> TeamJobDescription:
    scope(session, project_id, actor)
    member(session, project_id, member_id, None)
    row = current_document(session, member_id)
    if row is None:
        raise NotFoundError("No job description is attached.")
    return row


def remove_document(
    session: Session,
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    actor: ActorContext,
    version: int,
    reason: str,
) -> None:
    scope(session, project_id, actor, write=True)
    person = member(session, project_id, member_id, version)
    row = current_document(session, member_id)
    if row is None:
        raise NotFoundError("No job description is attached.")
    if not reason.strip():
        raise ValidationError("Enter a reason for deletion.")
    before = document_snapshot(row)
    row.is_deleted = True
    person.version += 1
    session.flush()
    record_event(
        session,
        action="delete",
        entity_type="team_job_description",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=document_snapshot(row),
        reason=reason.strip(),
    )
    session.commit()
