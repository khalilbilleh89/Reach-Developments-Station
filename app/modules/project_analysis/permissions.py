"""Whole-project membership plus one permission decision per section."""

import uuid
from typing import Annotated

from fastapi import Depends, Path

from app.core.errors import PermissionDeniedError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.inventory.permissions import visible_phase_ids
from app.modules.projects.models import Project
from app.modules.projects.permissions import require_project_access

COMMON = frozenset({"project_manager", "finance", "approver_cfo", "executive_viewer", "auditor"})
READERS = {
    "fundamental": COMMON | {"sales_operations"},
    "financial": COMMON,
    "technical": COMMON | {"design_engineering"},
}


def require_section(actor: ActorContext, section: str) -> None:
    if not actor.is_system_admin and not actor.role_keys.intersection(READERS[section]):
        raise PermissionDeniedError(f"You do not have permission to read {section} analysis.")


def accessible_project(
    project_id: Annotated[uuid.UUID, Path()], session: DbSession, actor: ActiveActor
) -> Project:
    project = require_project_access(session, project_id=project_id, actor=actor)
    if visible_phase_ids(session, project_id=project.id, actor=actor) is not None:
        raise PermissionDeniedError(
            "Analysis requires whole-project access; a phase subset is not project truth."
        )
    return project


AnalysisProject = Annotated[Project, Depends(accessible_project)]
