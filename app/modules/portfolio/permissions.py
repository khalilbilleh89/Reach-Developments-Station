"""Whole-project authorization applied before any source read."""

import uuid

from sqlalchemy import Select, select

from app.core.errors import PermissionDeniedError
from app.modules.access.dependencies import ActorContext
from app.modules.projects.models import PHASE_SCOPE_ALL, Project, UserProjectAccess

READERS = frozenset(
    {"system_admin", "executive_viewer", "approver_cfo", "finance", "project_manager", "auditor"}
)


def authorized_projects(actor: ActorContext) -> Select[tuple[uuid.UUID]]:
    """A role enables Portfolio; an active all-phase membership supplies its rows."""
    if not actor.is_system_admin and not actor.role_keys.intersection(READERS):
        raise PermissionDeniedError("You do not have permission to read Portfolio.")
    statement = select(Project.id)
    if actor.is_system_admin:
        return statement
    return statement.where(
        Project.id.in_(
            select(UserProjectAccess.project_id).where(
                UserProjectAccess.user_id == actor.user_id,
                UserProjectAccess.is_active.is_(True),
                UserProjectAccess.phase_scope == PHASE_SCOPE_ALL,
            )
        )
    )
