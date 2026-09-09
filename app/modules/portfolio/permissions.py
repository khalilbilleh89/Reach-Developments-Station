"""Whole-project authorization applied before any source read."""

import uuid

from sqlalchemy import Select

from app.core.errors import PermissionDeniedError
from app.modules.access.dependencies import ActorContext
from app.modules.projects.permissions import whole_project_ids

READERS = frozenset(
    {"system_admin", "executive_viewer", "approver_cfo", "finance", "project_manager", "auditor"}
)


def authorized_projects(actor: ActorContext) -> Select[tuple[uuid.UUID]]:
    """A role enables Portfolio; an active all-phase membership supplies its rows."""
    if not actor.is_system_admin and not actor.role_keys.intersection(READERS):
        raise PermissionDeniedError("You do not have permission to read Portfolio.")
    return whole_project_ids(actor)
