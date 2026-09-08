"""Narrow whole-project access for consultant engineering."""

import uuid
from typing import Annotated

from fastapi import Depends, Path

from app.core.errors import PermissionDeniedError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.inventory.permissions import visible_phase_ids
from app.modules.projects.models import Project
from app.modules.projects.permissions import require_project_access

READER_ROLES = frozenset(
    {
        "project_manager",
        "design_engineering",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
    }
)
EDITOR_ROLES = frozenset({"project_manager", "design_engineering"})


def require_reader(actor: ActorContext) -> None:
    if not actor.role_keys.intersection(READER_ROLES):
        raise PermissionDeniedError("You do not have permission to view Consultant Engineer.")


def require_editor(actor: ActorContext) -> None:
    if not actor.role_keys.intersection(EDITOR_ROLES):
        raise PermissionDeniedError(
            "Only Project Manager or Design / Engineering may change consultant design records."
        )


def accessible_project(
    project_id: Annotated[uuid.UUID, Path()], session: DbSession, actor: ActiveActor
) -> Project:
    project = require_project_access(session, project_id=project_id, actor=actor)
    require_reader(actor)
    if visible_phase_ids(session, project_id=project.id, actor=actor) is not None:
        raise PermissionDeniedError(
            "Consultant Engineer is whole-project design truth and cannot be shown "
            "as a partial phase view."
        )
    return project


ConsultantProject = Annotated[Project, Depends(accessible_project)]
