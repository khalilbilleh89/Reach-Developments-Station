"""Marketing contains indicative buyer returns, never developer margins."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.modules.access.dependencies import ActorContext
from app.modules.projects.models import Project
from app.modules.projects.permissions import whole_project_ids

MARKETING_READERS = frozenset(
    {
        "system_admin",
        "project_manager",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
        "sales_operations",
        "sales_advisor",
    }
)
MARKETING_WRITERS = frozenset({"system_admin", "project_manager", "finance", "sales_operations"})


def scope(
    session: Session, project_id: uuid.UUID, actor: ActorContext, *, write: bool = False
) -> Project:
    query = select(Project).where(
        Project.id == project_id, Project.id.in_(whole_project_ids(actor))
    )
    if write:
        query = query.with_for_update().execution_options(populate_existing=True)
    project = session.scalars(query).first()
    if project is None:
        raise NotFoundError("Project not found.")
    if not actor.is_system_admin and not actor.role_keys.intersection(
        MARKETING_WRITERS if write else MARKETING_READERS
    ):
        raise PermissionDeniedError("Marketing is not available to your role.")
    return project
