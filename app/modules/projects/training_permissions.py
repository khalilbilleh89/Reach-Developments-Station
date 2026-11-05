"""Whole-project Creative reading and project-writer management."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.modules.access.dependencies import ActorContext
from app.modules.projects.models import Project
from app.modules.projects.permissions import PROJECT_WRITER_ROLES, whole_project_ids


def scope(
    session: Session, project_id: uuid.UUID, actor: ActorContext, *, write: bool = False
) -> None:
    query = select(Project).where(
        Project.id == project_id, Project.id.in_(whole_project_ids(actor))
    )
    if write:
        query = query.with_for_update().execution_options(populate_existing=True)
    if session.scalar(query) is None:
        raise NotFoundError("Project not found.")
    if write and not actor.role_keys.intersection(PROJECT_WRITER_ROLES):
        raise PermissionDeniedError("Only project managers and administrators can manage training.")
