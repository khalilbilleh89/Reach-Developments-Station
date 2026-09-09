"""Atomic versioned mutations. Source-domain state is never written here."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ValidationError
from app.core.patching import resolve_updates
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import User
from app.modules.management_actions import permissions, repository, schemas
from app.modules.management_actions.models import ManagementAction as Action
from app.modules.management_actions.models import ManagementActionHistory as History

TRANSITIONS = {
    "open": {"in_progress", "completed", "cancelled"},
    "in_progress": {"open", "completed", "cancelled"},
    "completed": {"open"},
    "cancelled": {"open"},
}


def record(
    session: Session,
    action: Action,
    actor: ActorContext,
    event: str,
    changes: dict,
    reason: str | None,
) -> None:
    if "owner_user_id" in changes:
        change = changes["owner_user_id"]
        ids = [uuid.UUID(value) for value in (change["old"], change["new"]) if value]
        names = dict(
            session.execute(select(User.id, User.display_name).where(User.id.in_(ids))).all()
        )
        change["old_display_name"] = names.get(uuid.UUID(change["old"])) if change["old"] else None
        change["new_display_name"] = names.get(uuid.UUID(change["new"])) if change["new"] else None
    session.add(
        History(
            action_id=action.id,
            version=action.version,
            actor_user_id=actor.user_id,
            occurred_at=action.updated_at,
            event_type=event,
            changes=changes,
            reason=reason,
        )
    )


def create(session: Session, actor: ActorContext, payload: schemas.Create) -> Action:
    """Caller validates source provenance before this domain command is committed."""
    permissions.require_writer(actor)
    permissions.require_project(session, actor, payload.project_id, lock=True)
    permissions.require_owner(session, payload.project_id, payload.owner_user_id)
    now = datetime.now(UTC)
    action = Action(
        **payload.model_dump(),
        id=uuid.uuid4(),
        created_by_user_id=actor.user_id,
        status="open",
        version=1,
        created_at=now,
        updated_at=now,
    )
    session.add(action)
    session.flush()
    changes = {
        field: {"old": None, "new": str(getattr(action, field))}
        for field in ("title", "owner_user_id", "due_date", "status")
    }
    record(session, action, actor, "created", changes, None)
    session.commit()
    return action


def locked(session: Session, actor: ActorContext, action_id: uuid.UUID, version: int) -> Action:
    permissions.require_writer(actor)
    scope = permissions.project_scope(actor)
    action = repository.find(session, scope, action_id)
    permissions.require_project(session, actor, action.project_id, lock=True)
    action = repository.find(session, scope, action_id, lock=True)
    if action.version != version:
        raise ConflictError("This action changed. Reload it before saving again.")
    return action


def patch(
    session: Session, actor: ActorContext, action_id: uuid.UUID, payload: schemas.Patch
) -> Action:
    action = locked(session, actor, action_id, payload.expected_version)
    values = resolve_updates(
        payload.model_dump(exclude_unset=True),
        fields=("title", "description", "owner_user_id", "due_date"),
        clearable=frozenset({"description"}),
    )
    changes = {key: value for key, value in values.items() if getattr(action, key) != value}
    if not changes:
        return action
    if action.status in repository.TERMINAL:
        raise ConflictError("Reopen this action before editing it.")
    if (
        "due_date" in changes or ("owner_user_id" in changes and action.status == "in_progress")
    ) and not payload.reason:
        raise ValidationError(
            "A reason is required for a due-date change or reassignment after work has started."
        )
    if "owner_user_id" in changes:
        permissions.require_owner(session, action.project_id, changes["owner_user_id"])
    history = {
        key: {
            "old": str(getattr(action, key)) if getattr(action, key) is not None else None,
            "new": str(value) if value is not None else None,
        }
        for key, value in changes.items()
    }
    for key, value in changes.items():
        setattr(action, key, value)
    action.version += 1
    action.updated_at = datetime.now(UTC)
    record(session, action, actor, "updated", history, payload.reason)
    session.commit()
    return action


def transition(
    session: Session, actor: ActorContext, action_id: uuid.UUID, payload: schemas.Transition
) -> Action:
    action = locked(session, actor, action_id, payload.expected_version)
    if payload.status not in TRANSITIONS[action.status]:
        raise ConflictError("This status transition is not available.")
    reopened = action.status in repository.TERMINAL
    if (reopened or payload.status == "cancelled") and not payload.reason:
        raise ValidationError("A reason is required to cancel or reopen an action.")
    history = {"status": {"old": action.status, "new": payload.status}}
    action.status = payload.status
    action.version += 1
    action.updated_at = datetime.now(UTC)
    action.completed_at = action.updated_at if action.status == "completed" else None
    action.cancelled_at = action.updated_at if action.status == "cancelled" else None
    record(
        session,
        action,
        actor,
        "reopened" if reopened else "status_changed",
        history,
        payload.reason,
    )
    session.commit()
    return action
