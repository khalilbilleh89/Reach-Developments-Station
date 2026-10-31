"""Saved views and preferences: owned by one person, visible to that person alone."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory.models import Unit
from app.modules.inventory.permissions import visible_units
from app.modules.projects.models import Project
from app.modules.projects.permissions import visible_projects
from app.modules.sales.models import Client
from app.modules.sales.permissions import SALES_READER_ROLES, visible_clients
from app.modules.workspace.models import UserPreference, UserSavedView
from app.modules.workspace.schemas import (
    ClientHit,
    PreferencesUpdate,
    ProjectHit,
    SavedViewCreate,
    SavedViewRead,
    SavedViewUpdate,
    SearchRead,
    UnitHit,
)

#: How many views one person may keep on one register. A register with more
#: saved views than that is a register whose filters need a redesign.
MAX_VIEWS_PER_SCREEN = 20


def _snapshot(row: UserSavedView) -> dict:
    return {
        **SavedViewRead.model_validate(row).model_dump(mode="json"),
        "user_id": str(row.user_id),
    }


def _audit(
    session: Session,
    row: UserSavedView,
    actor: ActorContext,
    action: str,
    before: dict | None = None,
) -> None:
    session.flush()
    record_event(
        session,
        action=action,
        entity_type="user_saved_view",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=_snapshot(row) if action != "delete" else None,
    )


def list_views(session: Session, actor: ActorContext, screen: str | None) -> list[UserSavedView]:
    query = select(UserSavedView).where(UserSavedView.user_id == actor.user_id)
    if screen is not None:
        query = query.where(UserSavedView.screen == screen)
    query = query.order_by(
        UserSavedView.screen, UserSavedView.pinned.desc(), UserSavedView.name, UserSavedView.id
    )
    return list(session.scalars(query))


def _own_view(session: Session, actor: ActorContext, view_id: uuid.UUID) -> UserSavedView:
    row = session.get(UserSavedView, view_id)
    # Another person's view is not found rather than forbidden: its existence
    # is theirs to know.
    if row is None or row.user_id != actor.user_id:
        raise NotFoundError("Saved view not found.")
    return row


def _refuse_duplicate_name(
    session: Session, actor: ActorContext, screen: str, name: str, except_id: uuid.UUID | None
) -> None:
    query = select(UserSavedView.id).where(
        UserSavedView.user_id == actor.user_id,
        UserSavedView.screen == screen,
        UserSavedView.name == name,
    )
    if except_id is not None:
        query = query.where(UserSavedView.id != except_id)
    if session.scalar(query) is not None:
        raise ConflictError(f"A view named “{name}” already exists on this register.")


def create_view(session: Session, actor: ActorContext, payload: SavedViewCreate) -> UserSavedView:
    name = payload.name.strip()
    if not name:
        raise ConflictError("A view needs a name.")
    _refuse_duplicate_name(session, actor, payload.screen, name, None)
    existing = len(
        list(
            session.scalars(
                select(UserSavedView.id).where(
                    UserSavedView.user_id == actor.user_id, UserSavedView.screen == payload.screen
                )
            )
        )
    )
    if existing >= MAX_VIEWS_PER_SCREEN:
        raise ConflictError(
            f"This register already holds {MAX_VIEWS_PER_SCREEN} saved views; remove one first."
        )
    row = UserSavedView(
        user_id=actor.user_id,
        screen=payload.screen,
        name=name,
        filters=payload.filters,
        sort=payload.sort,
        pinned=payload.pinned,
    )
    session.add(row)
    _audit(session, row, actor, "create")
    session.commit()
    session.refresh(row)
    return row


def update_view(
    session: Session, actor: ActorContext, view_id: uuid.UUID, payload: SavedViewUpdate
) -> UserSavedView:
    row = _own_view(session, actor, view_id)
    before = _snapshot(row)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        name = changes["name"].strip()
        if not name:
            raise ConflictError("A view needs a name.")
        _refuse_duplicate_name(session, actor, row.screen, name, row.id)
        row.name = name
    if "filters" in changes and changes["filters"] is not None:
        row.filters = changes["filters"]
    if "sort" in changes:
        row.sort = changes["sort"]
    if "pinned" in changes and changes["pinned"] is not None:
        row.pinned = changes["pinned"]
    _audit(session, row, actor, "update", before)
    session.commit()
    session.refresh(row)
    return row


def delete_view(session: Session, actor: ActorContext, view_id: uuid.UUID) -> None:
    row = _own_view(session, actor, view_id)
    before = _snapshot(row)
    session.delete(row)
    session.flush()
    record_event(
        session,
        action="delete",
        entity_type="user_saved_view",
        entity_id=view_id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=None,
    )
    session.commit()


def read_preferences(session: Session, actor: ActorContext) -> UserPreference:
    row = session.get(UserPreference, actor.user_id)
    # A person who has never chosen gets the defaults; nothing is written by a read.
    return (
        row
        if row is not None
        else UserPreference(user_id=actor.user_id, register_density="comfortable")
    )


def update_preferences(
    session: Session, actor: ActorContext, payload: PreferencesUpdate
) -> UserPreference:
    row = session.get(UserPreference, actor.user_id)
    if row is None:
        row = UserPreference(user_id=actor.user_id)
        session.add(row)
    row.register_density = payload.register_density
    session.commit()
    session.refresh(row)
    return row


# --------------------------------------------------------------------------- #
# Global search (design system F2)
# --------------------------------------------------------------------------- #

#: How many of each kind a query returns. The palette shows a handful; a
#: person who wants more narrows the query.
SEARCH_LIMIT = 6
#: How many projects a unit or buyer search looks inside. Each is narrowed by
#: that project's own phase and advisor rules, so the cost is one query per
#: project; a portfolio larger than this searches its first projects by code.
SEARCH_PROJECT_SPAN = 25


def search(session: Session, actor: ActorContext, query: str) -> SearchRead:
    """Projects, units and buyers matching ``query``, each as the caller may see them.

    Every list is scoped the same way the register it comes from is scoped:
    projects by membership, units by phase grant inside each visible project,
    buyers by the sales reader roles and an advisor's own book. Nothing is
    fetched and filtered afterwards; the narrowing is in each query.
    """
    needle = query.strip()
    if len(needle) < 2:
        return SearchRead(query=needle, projects=[], units=[], clients=[])
    pattern = f"%{needle}%"

    projects = list(
        session.scalars(
            visible_projects(
                select(Project).where(Project.name.ilike(pattern) | Project.code.ilike(pattern)),
                actor=actor,
            )
            .order_by(Project.code)
            .limit(SEARCH_LIMIT)
        )
    )
    span = list(
        session.scalars(
            visible_projects(select(Project), actor=actor)
            .order_by(Project.code)
            .limit(SEARCH_PROJECT_SPAN)
        )
    )

    units: list[UnitHit] = []
    for project in span:
        if len(units) >= SEARCH_LIMIT:
            break
        statement = visible_units(
            select(Unit).where(
                Unit.project_id == project.id,
                Unit.is_active.is_(True),
                Unit.unit_reference.ilike(pattern) | Unit.unit_number.ilike(pattern),
            ),
            session,
            project_id=project.id,
            actor=actor,
        )
        for unit in session.scalars(
            statement.order_by(Unit.unit_reference).limit(SEARCH_LIMIT - len(units))
        ):
            units.append(
                UnitHit(
                    id=unit.id,
                    project_id=project.id,
                    project_code=project.code,
                    unit_reference=unit.unit_reference,
                    unit_number=unit.unit_number,
                    commercial_status=unit.commercial_status,
                )
            )

    clients: list[ClientHit] = []
    if actor.has_any_role(*SALES_READER_ROLES):
        for project in span:
            if len(clients) >= SEARCH_LIMIT:
                break
            statement = visible_clients(
                select(Client).where(
                    Client.project_id == project.id,
                    Client.display_name.ilike(pattern) | Client.client_number.ilike(pattern),
                ),
                actor=actor,
            )
            for row in session.scalars(
                statement.order_by(Client.client_number).limit(SEARCH_LIMIT - len(clients))
            ):
                clients.append(
                    ClientHit(
                        id=row.id,
                        project_id=project.id,
                        project_code=project.code,
                        client_number=row.client_number,
                        display_name=row.display_name,
                    )
                )

    return SearchRead(
        query=needle,
        projects=[ProjectHit.model_validate(project) for project in projects],
        units=units,
        clients=clients,
    )
