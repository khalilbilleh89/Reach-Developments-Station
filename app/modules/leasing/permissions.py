"""Leasing uses whole-project commercial readers; advisors stay assigned-only in Sales."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.modules.access.dependencies import ActorContext
from app.modules.projects.models import Project
from app.modules.projects.permissions import whole_project_ids

LEASING_READERS = frozenset(
    {
        "system_admin",
        "project_manager",
        "sales_operations",
        "legal",
        "collections",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
    }
)
LEASING_WRITERS = frozenset({"system_admin", "project_manager", "sales_operations"})


def require_reader(actor: ActorContext) -> None:
    if not actor.role_keys.intersection(LEASING_READERS):
        raise PermissionDeniedError("Leasing is not available to your role.")


def scope(
    session: Session, project_id: uuid.UUID, actor: ActorContext, *, write: bool = False
) -> Project:
    query = select(Project).where(
        Project.id == project_id, Project.id.in_(whole_project_ids(actor))
    )
    if write:
        query = query.with_for_update().execution_options(populate_existing=True)
    project = session.scalar(query)
    if project is None:
        raise NotFoundError("Project not found.")
    require_reader(actor)
    if write and not actor.role_keys.intersection(LEASING_WRITERS):
        raise PermissionDeniedError(
            "Only leasing operators and project managers can manage instructions."
        )
    return project
