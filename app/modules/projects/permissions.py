"""The project security boundary.

Every project-scoped route establishes membership here before it looks at
anything else. Access is a row in ``user_project_access``, checked in the
database — never a list of projects filtered in Python afterwards.

Deliberately four small functions and one dependency, not a policy engine.
There are no permission strings, no resource types and no expressions to
evaluate: the questions are "may this person see this project", "may they
change things in it" and "may they see money", and each has one answer.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.projects.models import Project, UserProjectAccess

#: Roles that may change project records they have access to.
PROJECT_WRITER_ROLES = frozenset({"system_admin", "project_manager"})

#: Roles that may maintain planning controls, permits and document references.
#: Design / Engineering runs the approvals process; it does not own the project
#: identity or the land deal.
TECHNICAL_WRITER_ROLES = PROJECT_WRITER_ROLES | {"design_engineering"}

#: Roles cleared to see development cost. Land price and permit fees are
#: commercially sensitive, so this is an allow-list: a role not named here sees
#: null, not a rounded or zeroed figure.
FINANCIAL_ROLES = frozenset(
    {
        "system_admin",
        "project_manager",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
    }
)

#: Returned whenever a project — or a record inside one — is not visible to the
#: caller. Never 403: a 403 would confirm that the identifier names something
#: real, which is exactly what an attacker enumerating UUIDs wants to learn.
_NOT_FOUND_DETAIL = "Project not found."

_FORBIDDEN_DETAIL = "You do not have permission to perform this action."


def has_project_access(session: Session, *, project_id: uuid.UUID, actor: ActorContext) -> bool:
    """Whether ``actor`` may see this project at all.

    A System Administrator administers the whole system and so needs no
    membership row; everyone else needs an active one. Holding the right global
    role is not access: a Project Manager sees the projects they are on, not
    every project.
    """
    if actor.is_system_admin:
        return session.get(Project, project_id) is not None
    membership = session.scalars(
        select(UserProjectAccess).where(
            UserProjectAccess.project_id == project_id,
            UserProjectAccess.user_id == actor.user_id,
            UserProjectAccess.is_active.is_(True),
        )
    ).first()
    return membership is not None


def visible_projects(statement: Select[tuple[Project]], *, actor: ActorContext) -> Select:
    """Narrow a project query to what ``actor`` may see.

    Applied in SQL rather than by filtering results afterwards: fetching every
    project and discarding the ones the caller may not see would put them in
    memory, in the query plan and one refactor away from the response.
    """
    if actor.is_system_admin:
        return statement
    return statement.where(
        Project.id.in_(
            select(UserProjectAccess.project_id).where(
                UserProjectAccess.user_id == actor.user_id,
                UserProjectAccess.is_active.is_(True),
            )
        )
    )


def require_project_access(
    session: Session, *, project_id: uuid.UUID, actor: ActorContext
) -> Project:
    """Load a project the caller is allowed to see, or raise 404.

    The single entry point to a project. Nested resources are then loaded *by
    this project's id*, so a permit or parcel identifier belonging to another
    project cannot be substituted into a path the caller does have access to.
    """
    project = session.get(Project, project_id)
    if project is None or not has_project_access(session, project_id=project_id, actor=actor):
        raise NotFoundError(_NOT_FOUND_DETAIL)
    return project


def require_project_role(actor: ActorContext, roles: frozenset[str]) -> None:
    """Refuse a caller who is inside the project but holds none of ``roles``.

    403 here, not 404: the caller can already see this project, so there is
    nothing left to conceal — only an action to refuse.
    """
    if not actor.role_keys.intersection(roles):
        raise PermissionDeniedError(_FORBIDDEN_DETAIL)


def require_project_writer(actor: ActorContext) -> None:
    """Gate changes to project identity, land and access-bearing records."""
    require_project_role(actor, PROJECT_WRITER_ROLES)


def require_technical_writer(actor: ActorContext) -> None:
    """Gate changes to planning controls, permits and document references."""
    require_project_role(actor, TECHNICAL_WRITER_ROLES)


def can_view_project_financials(actor: ActorContext) -> bool:
    """Whether development cost may be included in a response for this caller."""
    return bool(actor.role_keys.intersection(FINANCIAL_ROLES))


def accessible_project(
    project_id: Annotated[uuid.UUID, Path()],
    session: DbSession,
    actor: ActiveActor,
) -> Project:
    """FastAPI dependency resolving ``{project_id}`` to a project the caller may see."""
    return require_project_access(session, project_id=project_id, actor=actor)


#: Every project-scoped route depends on this, so the boundary cannot be
#: forgotten in one handler.
AccessibleProject = Annotated[Project, Depends(accessible_project)]
