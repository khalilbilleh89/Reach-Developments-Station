"""Saved views and preferences: owned by one person, visible to that person alone."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.workspace.models import UserPreference, UserSavedView
from app.modules.workspace.schemas import (
    PreferencesUpdate,
    SavedViewCreate,
    SavedViewRead,
    SavedViewUpdate,
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
