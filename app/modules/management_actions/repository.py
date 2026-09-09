"""Scoped, bounded action reads; no global action lookup or per-row user fetch."""

import uuid
from datetime import date, timedelta

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import NotFoundError
from app.modules.access.models import User
from app.modules.management_actions import schemas
from app.modules.management_actions.models import ManagementAction as Action
from app.modules.projects.models import Project

TERMINAL = ("completed", "cancelled")


def due_state(action: Action, as_of: date) -> str:
    if action.status in TERMINAL:
        return "closed"
    if action.due_date < as_of:
        return "overdue"
    return "due_soon" if action.due_date <= as_of + timedelta(days=7) else "future"


def find(session: Session, scope: Select, action_id: uuid.UUID, *, lock: bool = False) -> Action:
    statement = select(Action).where(Action.project_id.in_(scope), Action.id == action_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    action = session.scalar(statement)
    if action is None:
        raise NotFoundError("Management action not found.")
    return action


def filtered(
    scope: Select,
    as_of: date,
    *,
    owner_user_id: uuid.UUID | None = None,
    status: str | None = None,
    due: str | None = None,
    source_type: str | None = None,
    source_key: str | None = None,
) -> Select:
    statement = select(Action.id).where(Action.project_id.in_(scope))
    for column, value in (
        (Action.owner_user_id, owner_user_id),
        (Action.status, status),
        (Action.source_type, source_type),
        (Action.source_key, source_key),
    ):
        if value is not None:
            statement = statement.where(column == value)
    if due == "closed":
        statement = statement.where(Action.status.in_(TERMINAL))
    elif due:
        statement = statement.where(Action.status.not_in(TERMINAL))
        if due == "overdue":
            statement = statement.where(Action.due_date < as_of)
        elif due == "due_soon":
            statement = statement.where(Action.due_date.between(as_of, as_of + timedelta(days=7)))
        else:
            statement = statement.where(Action.due_date > as_of + timedelta(days=7))
    return statement


def records(
    session: Session, ids: Select, as_of: date, *, limit: int, offset: int
) -> list[schemas.ActionOut]:
    owner, creator = aliased(User), aliased(User)
    rows = session.execute(
        select(Action, Project.code, Project.name, owner.display_name, creator.display_name)
        .join(Project, Project.id == Action.project_id)
        .join(owner, owner.id == Action.owner_user_id)
        .join(creator, creator.id == Action.created_by_user_id)
        .where(Action.id.in_(ids))
        .order_by(
            case(((Action.status.not_in(TERMINAL)) & (Action.due_date < as_of), 0), else_=1),
            Action.due_date,
            Project.code,
            Project.id,
            Action.id,
        )
        .offset(offset)
        .limit(limit)
    )
    result = []
    for action, code, name, owner_name, creator_name in rows:
        values = {column.name: getattr(action, column.name) for column in Action.__table__.columns}
        result.append(
            schemas.ActionOut(
                **values,
                project_code=code,
                project_name=name,
                due_state=due_state(action, as_of),
                owner=schemas.Identity(user_id=action.owner_user_id, display_name=owner_name),
                created_by=schemas.Identity(
                    user_id=action.created_by_user_id, display_name=creator_name
                ),
            )
        )
    return result


def page(
    session: Session, ids: Select, as_of: date, *, limit: int, offset: int
) -> schemas.ActionPage:
    return schemas.ActionPage(
        as_of=as_of,
        items=records(session, ids, as_of, limit=limit, offset=offset),
        total=session.scalar(select(func.count()).select_from(ids.subquery())),
        limit=limit,
        offset=offset,
    )
