"""Narrow read-only snapshot and append-only execution contracts."""

from datetime import date, datetime

from sqlalchemy import Integer, Select, Uuid, column, select, values
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.management_actions.models import ManagementAction as Action
from app.modules.management_actions.models import ManagementActionHistory as History
from app.modules.management_actions.schemas import Identity, ReportingAction, ReportingFrontier


def position(session: Session, scope: Select, as_of: date) -> list[ReportingAction]:
    rows = session.execute(
        select(Action, User.display_name)
        .join(User, User.id == Action.owner_user_id)
        .where(Action.project_id.in_(scope))
        .order_by(
            (Action.status.in_(("open", "in_progress")) & (Action.due_date < as_of)).desc(),
            Action.due_date,
            Action.project_id,
            Action.id,
        )
    )
    return [
        ReportingAction(
            id=a.id,
            project_id=a.project_id,
            title=a.title,
            owner=Identity(user_id=a.owner_user_id, display_name=name),
            due_date=a.due_date,
            status=a.status,
            source_type=a.source_type,
            source_code=a.source_code,
            created_at=a.created_at,
            updated_at=a.updated_at,
            version=a.version,
        )
        for a, name in rows
    ]


def execution(
    session: Session, captured: list[ReportingFrontier], low: datetime, high: datetime
) -> dict[str, int]:
    """Upper version watermarks exclude transactions committed after capture.

    No live Action or user join: renames/status changes cannot rewrite a report.
    The inclusive upper / exclusive lower timestamp interval never double counts
    an event across adjacent intervals. Repeated completions count as events.
    """
    counts = dict.fromkeys(("created", "started", "completed", "reopened", "cancelled"), 0)
    if not captured:
        return counts
    frontier = (
        values(column("action_id", Uuid), column("version", Integer), name="captured_actions")
        .data([(a.id, a.version) for a in captured])
        .cte()
    )
    rows = session.execute(
        select(History.event_type, History.changes)
        .join(
            frontier,
            (History.action_id == frontier.c.action_id) & (History.version <= frontier.c.version),
        )
        .where(History.occurred_at > low, History.occurred_at <= high)
    )
    for event, changes in rows:
        if event in ("created", "reopened"):
            counts[event] += 1
        elif event == "status_changed":
            target = changes.get("status", {}).get("new")
            name = {
                "in_progress": "started",
                "completed": "completed",
                "cancelled": "cancelled",
            }.get(target)
            if name:
                counts[name] += 1
    return counts
