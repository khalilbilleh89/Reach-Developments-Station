"""Commercially sensitive commission permissions."""

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
        "sales_operations",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
    }
)
PREPARER_ROLES = frozenset({"project_manager", "sales_operations", "finance"})
RELEASER_ROLES = frozenset({"finance", "approver_cfo"})


def require_role(actor: ActorContext, roles: frozenset[str], message: str) -> None:
    if not actor.role_keys.intersection(roles):
        raise PermissionDeniedError(message)


def require_preparer(actor: ActorContext) -> None:
    require_role(
        actor,
        PREPARER_ROLES,
        "Only Project Manager, Sales Operations or Finance may prepare commissions.",
    )


def require_releaser(actor: ActorContext) -> None:
    require_role(
        actor, RELEASER_ROLES, "Only Finance or Approver / CFO may release or reverse commissions."
    )


def accessible_project(
    project_id: Annotated[uuid.UUID, Path()], session: DbSession, actor: ActiveActor
) -> Project:
    project = require_project_access(session, project_id=project_id, actor=actor)
    require_role(actor, READER_ROLES, "You do not have permission to view commissions.")
    if visible_phase_ids(session, project_id=project.id, actor=actor) is not None:
        raise PermissionDeniedError(
            "Commissions are whole-project commercial truth and cannot be shown "
            "as a partial phase view."
        )
    return project


CommissionProject = Annotated[Project, Depends(accessible_project)]
