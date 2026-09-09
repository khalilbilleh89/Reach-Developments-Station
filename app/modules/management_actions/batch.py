"""Read contracts for Portfolio and Project composition."""

from datetime import date

from sqlalchemy import Result, Select, func, select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.management_actions.models import ManagementAction as Action
from app.modules.management_actions.repository import TERMINAL
from app.modules.projects.models import Project


def due_rows(session: Session, scope: Select, horizon_end: date) -> Result:
    """All eligible dated candidates, streamed for globally bounded selection."""
    return session.execute(
        select(Action, Project.code, Project.name, User.display_name)
        .join(Project, Project.id == Action.project_id)
        .join(User, User.id == Action.owner_user_id)
        .where(
            Action.project_id.in_(scope),
            Action.status.not_in(TERMINAL),
            Action.due_date <= horizon_end,
        )
        .execution_options(yield_per=100)
    )


def summary(session: Session, scope: Select, as_of: date) -> dict:
    row = session.execute(
        select(
            func.count(Action.id).filter(Action.status.not_in(TERMINAL)),
            func.count(Action.id).filter(Action.status.not_in(TERMINAL), Action.due_date < as_of),
            func.min(Action.due_date).filter(Action.status.not_in(TERMINAL)),
            func.count(Action.id).filter(
                Action.status.not_in(TERMINAL), Action.source_type != "manual"
            ),
        ).where(Action.project_id.in_(scope))
    ).one()
    return {
        "open_count": row[0],
        "overdue_count": row[1],
        "next_due_date": row[2],
        "source_linked_open_count": row[3],
    }
