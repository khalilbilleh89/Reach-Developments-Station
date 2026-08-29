"""The phase security boundary, and who may change what inside inventory.

PR-MVP-02 answered "may this person open this project". Inventory adds a second,
narrower question — "which phases of it may they see" — because a development
routinely gives a contractor, a broker or a joint-venture partner one phase and
not the rest.

The narrowing is applied in SQL, never by fetching everything and filtering
afterwards: units carry areas, features and commercial state, and a list the
caller may not see should never reach memory, the query plan or one careless
refactor away from the response body.

Deliberately small functions over a policy engine. There are no permission
strings, no resource types and nothing to evaluate: a phase is either in the
caller's scope or it is not, and each role either holds a named right or it does
not.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.inventory.models import (
    Building,
    Floor,
    Phase,
    Unit,
    UserPhaseAccess,
)
from app.modules.projects.models import PHASE_SCOPE_SELECTED, Project, UserProjectAccess
from app.modules.projects.permissions import require_project_access

#: Roles that may shape the physical catalogue: phases, buildings, floors, units,
#: sub-assets and draft area schedules. Design / Engineering builds the model of
#: the development; it does not decide who may see it or what it costs.
STRUCTURE_WRITER_ROLES = frozenset({"system_admin", "project_manager", "design_engineering"})

#: Roles that own the project's identity and configuration: phases, area types
#: and the approval of a measured area schedule.
PROJECT_CONFIG_ROLES = frozenset({"system_admin", "project_manager"})

#: Who may confirm the drawings a unit is built from.
DRAWINGS_APPROVAL_ROLES = frozenset({"system_admin", "project_manager", "design_engineering"})

#: Who may confirm a unit is legally saleable.
LEGAL_ELIGIBILITY_ROLES = frozenset({"system_admin", "project_manager", "legal"})

#: Who may schedule a release, batch it, or block one.
RELEASE_CONTROL_ROLES = frozenset({"system_admin", "project_manager", "sales_operations"})

#: Who may move a unit between the commercial states inventory owns.
COMMERCIAL_TRANSITION_ROLES = RELEASE_CONTROL_ROLES

#: The right each release-control field requires. Written once, here, so a route
#: cannot quietly accept a field it never checked.
RELEASE_CONTROL_FIELD_ROLES: dict[str, frozenset[str]] = {
    "drawings_approved": DRAWINGS_APPROVAL_ROLES,
    "legal_sale_eligible": LEGAL_ELIGIBILITY_ROLES,
    "release_date": RELEASE_CONTROL_ROLES,
    "release_batch": RELEASE_CONTROL_ROLES,
    "block_reason": RELEASE_CONTROL_ROLES,
}

_NOT_FOUND_DETAIL = "Project not found."
_PHASE_NOT_FOUND_DETAIL = "Phase not found."
_FORBIDDEN_DETAIL = "You do not have permission to perform this action."


def _selected_scope_membership(
    session: Session, *, project_id: uuid.UUID, actor: ActorContext
) -> UserProjectAccess | None:
    """The caller's membership row when — and only when — it narrows phases.

    Returning ``None`` means "sees every phase", which covers a System
    Administrator, an ``all``-scope member, and the impossible case of no row at
    all (the project boundary has already refused that caller).
    """
    if actor.is_system_admin:
        return None
    membership = session.scalars(
        select(UserProjectAccess).where(
            UserProjectAccess.project_id == project_id,
            UserProjectAccess.user_id == actor.user_id,
            UserProjectAccess.is_active.is_(True),
        )
    ).first()
    if membership is None or membership.phase_scope != PHASE_SCOPE_SELECTED:
        return None
    return membership


def visible_phase_ids(
    session: Session, *, project_id: uuid.UUID, actor: ActorContext
) -> Select[tuple[uuid.UUID]] | None:
    """A subquery of the phase ids this caller may see, or ``None`` for all.

    ``None`` is not "no phases" — it is "no narrowing needed", which is why
    every caller checks for it explicitly rather than treating the result as a
    plain list.
    """
    if _selected_scope_membership(session, project_id=project_id, actor=actor) is None:
        return None
    return select(UserPhaseAccess.phase_id).where(
        UserPhaseAccess.project_id == project_id,
        UserPhaseAccess.user_id == actor.user_id,
        UserPhaseAccess.is_active.is_(True),
    )


def visible_phases(
    statement: Select[tuple[Phase]],
    session: Session,
    *,
    project_id: uuid.UUID,
    actor: ActorContext,
) -> Select[tuple[Phase]]:
    """Narrow a phase query to the caller's scope."""
    allowed = visible_phase_ids(session, project_id=project_id, actor=actor)
    if allowed is None:
        return statement
    return statement.where(Phase.id.in_(allowed))


def _units_in_visible_phases(allowed: Select[tuple[uuid.UUID]]) -> Select[tuple[uuid.UUID]]:
    """Unit ids whose floor sits in a building of one of ``allowed``."""
    return (
        select(Unit.id)
        .join(Floor, Floor.id == Unit.floor_id)
        .join(Building, Building.id == Floor.building_id)
        .where(Building.phase_id.in_(allowed))
    )


def visible_units(
    statement: Select[tuple[Unit]],
    session: Session,
    *,
    project_id: uuid.UUID,
    actor: ActorContext,
) -> Select[tuple[Unit]]:
    """Narrow a unit query to the phases the caller may see.

    The join runs in the database. A restricted caller's query never selects the
    rows they may not have, so a filter they control cannot widen it and a later
    ``for unit in units`` cannot leak one.
    """
    allowed = visible_phase_ids(session, project_id=project_id, actor=actor)
    if allowed is None:
        return statement
    return statement.where(Unit.id.in_(_units_in_visible_phases(allowed)))


def require_phase(
    session: Session, *, project: Project, phase_id: uuid.UUID, actor: ActorContext
) -> Phase:
    """Load a phase of this project the caller may see, or raise 404.

    404 rather than 403 for a phase outside the caller's scope: a 403 would
    confirm the identifier names a real phase of a real project, which is what
    someone enumerating identifiers wants to learn.
    """
    phase = session.scalars(
        select(Phase).where(Phase.id == phase_id, Phase.project_id == project.id)
    ).first()
    if phase is None:
        raise NotFoundError(_PHASE_NOT_FOUND_DETAIL)
    allowed = visible_phase_ids(session, project_id=project.id, actor=actor)
    if allowed is not None and phase.id not in set(session.scalars(allowed)):
        raise NotFoundError(_PHASE_NOT_FOUND_DETAIL)
    return phase


def require_unit(
    session: Session, *, project: Project, unit_id: uuid.UUID, actor: ActorContext
) -> Unit:
    """Load a unit of this project the caller may see, or raise 404.

    Scoped by project *and* by phase, and loaded by both at once — never fetched
    by primary key and checked afterwards, which is the shape that lets one
    project's identifier be substituted into another's path.
    """
    statement = select(Unit).where(Unit.id == unit_id, Unit.project_id == project.id)
    unit = session.scalars(
        visible_units(statement, session, project_id=project.id, actor=actor)
    ).first()
    if unit is None:
        raise NotFoundError("Unit not found.")
    return unit


def require_role(actor: ActorContext, roles: frozenset[str], *, detail: str) -> None:
    """Refuse a caller inside the project who holds none of ``roles``."""
    if not actor.role_keys.intersection(roles):
        raise PermissionDeniedError(detail)


def require_inventory_structure_writer(actor: ActorContext) -> None:
    """Gate changes to buildings, floors, units and sub-assets."""
    require_role(actor, STRUCTURE_WRITER_ROLES, detail=_FORBIDDEN_DETAIL)


def require_project_configurer(actor: ActorContext) -> None:
    """Gate phases, area types and area-schedule approval."""
    require_role(actor, PROJECT_CONFIG_ROLES, detail=_FORBIDDEN_DETAIL)


def require_inventory_release_writer(actor: ActorContext, fields: list[str]) -> None:
    """Check every release-control field the request names, not just the first.

    Each field has its own owning role — drawings belong to design, legal
    eligibility to legal, the release calendar to sales operations — so a caller
    may legitimately be allowed one field of a request and refused another.
    """
    for field in fields:
        allowed = RELEASE_CONTROL_FIELD_ROLES.get(field)
        if allowed is None or not actor.role_keys.intersection(allowed):
            raise PermissionDeniedError(
                f"You do not have permission to change {field.replace('_', ' ')}."
            )


def require_commercial_transition_writer(actor: ActorContext) -> None:
    """Gate holding, releasing and unreleasing a unit."""
    require_role(actor, COMMERCIAL_TRANSITION_ROLES, detail=_FORBIDDEN_DETAIL)


def accessible_project_for_inventory(
    project_id: Annotated[uuid.UUID, Path()],
    session: DbSession,
    actor: ActiveActor,
) -> Project:
    """Resolve ``{project_id}`` to a project the caller may open.

    Inventory reuses the project boundary unchanged and then narrows by phase;
    it does not re-implement membership, so the two can never disagree.
    """
    return require_project_access(session, project_id=project_id, actor=actor)


InventoryProject = Annotated[Project, Depends(accessible_project_for_inventory)]
