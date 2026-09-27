"""Scoped, version-checked directory writes with retained deletion and audit."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.models import Project
from app.modules.projects.permissions import (
    PROJECT_WRITER_ROLES,
    visible_projects,
    whole_project_ids,
)
from app.modules.projects.team_models import ProjectTeamMember
from app.modules.projects.team_schemas import TeamDirectory, TeamMemberRead


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
    return TeamDirectory(
        members=[TeamMemberRead.model_validate(row) for row in rows],
        can_manage=can_manage(session, project_id, actor),
    )


def member(
    session: Session, project_id: uuid.UUID, member_id: uuid.UUID, version: int
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
    if row.version != version:
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
    return TeamMemberRead.model_validate(row)


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
