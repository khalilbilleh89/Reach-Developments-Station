"""Portfolio visibility and the existing project-management write policy."""

import uuid

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import Role, User, UserRole
from app.modules.projects.models import PHASE_SCOPE_ALL, Project, UserProjectAccess
from app.modules.projects.permissions import FINANCIAL_ROLES as READERS
from app.modules.projects.permissions import PROJECT_WRITER_ROLES, whole_project_ids


def require_writer(actor: ActorContext) -> None:
    if not actor.role_keys.intersection(PROJECT_WRITER_ROLES):
        raise PermissionDeniedError(
            "Only a Project Manager or System Administrator may change management actions."
        )


def project_scope(actor: ActorContext, project_id: uuid.UUID | None = None) -> Select:
    if not actor.role_keys.intersection(READERS):
        raise PermissionDeniedError("You do not have permission to read management actions.")
    scope = whole_project_ids(actor)
    return scope.where(Project.id == project_id) if project_id else scope


def require_project(
    session: Session, actor: ActorContext, project_id: uuid.UUID, *, lock: bool = False
) -> None:
    statement = project_scope(actor, project_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    if session.scalar(statement) is None:
        raise NotFoundError("Portfolio project not found.")


def eligible_users(project_id: uuid.UUID) -> Select:
    roles = select(UserRole.user_id).join(Role, Role.id == UserRole.role_id)
    return select(User.id, User.display_name).where(
        User.is_active.is_(True),
        User.id.in_(roles.where(Role.key.in_(READERS))),
        or_(
            User.id.in_(roles.where(Role.key == "system_admin")),
            User.id.in_(
                select(UserProjectAccess.user_id).where(
                    UserProjectAccess.project_id == project_id,
                    UserProjectAccess.is_active.is_(True),
                    UserProjectAccess.phase_scope == PHASE_SCOPE_ALL,
                )
            ),
        ),
    )


def require_owner(session: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    if session.scalar(eligible_users(project_id).where(User.id == user_id)) is None:
        raise ValidationError("Owner must be an active eligible whole-project user.")
