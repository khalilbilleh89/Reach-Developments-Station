"""Capture one coherent database view; a failed owner read aborts everything."""

import uuid
from datetime import UTC

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.core.errors import NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.management_actions import reporting as actions
from app.modules.management_actions.schemas import ReportingFrontier
from app.modules.management_reporting import canonical, permissions, schemas
from app.modules.management_reporting.models import Snapshot, SnapshotProject
from app.modules.portfolio import outlook, service
from app.modules.portfolio.permissions import authorized_projects
from app.modules.projects.models import Project


def capture(actor: ActorContext, command: schemas.Create) -> schemas.SnapshotOut:
    permissions.require_writer(actor)
    # Authentication may already have read in the request session. This dedicated
    # transaction sets isolation BEFORE its first query, using the canonical engine.
    with (
        get_engine().connect().execution_options(isolation_level="REPEATABLE READ") as connection,
        Session(connection, autoflush=False, expire_on_commit=False) as session,
        session.begin(),
    ):
        return compose(session, actor, command)


def compose(session: Session, actor: ActorContext, command: schemas.Create) -> schemas.SnapshotOut:
    captured_at = (
        session.execute(text("SELECT clock_timestamp(), pg_current_snapshot()"))
        .one()[0]
        .astimezone(UTC)
    )
    as_of = captured_at.date()
    scope = authorized_projects(actor)
    if command.project_id:
        scope = scope.where(Project.id == command.project_id)
    projects = service.summaries(session, scope, as_of)
    if not projects:
        if command.project_id:
            raise NotFoundError("Project not found.")
        raise ValidationError("No authorized whole projects are available to capture.")
    # JSON array order is explicit even where owner facts originate in sets.
    for project in projects:
        project.money.sort(key=lambda row: (row.metric_code, row.currency))
        project.risk_evaluations.sort(key=lambda row: row.risk_code)
    forwards = []
    for days in (30, 60, 90):
        report = outlook.page(session, scope, as_of, horizon_days=days, limit=2**31 - 1, offset=0)
        report.limit = report.total
        report.currency_buckets.sort(key=lambda row: row.currency)
        report.coverage.sort(key=lambda row: (row.source, row.reason))
        forwards.append(report)
    position = actions.position(session, scope, as_of)
    counts = schemas.ActionCounts(
        **{
            status: sum(a.status == status for a in position)
            for status in ("open", "in_progress", "completed", "cancelled")
        },
        overdue=sum(a.status in ("open", "in_progress") and a.due_date < as_of for a in position),
    )
    overview = service.overview(projects, as_of)
    overview.money.sort(key=lambda row: (row.metric_code, row.currency))
    result = schemas.SnapshotOut(
        id=uuid.uuid4(),
        scope_type=command.scope,
        project_id=command.project_id,
        label=command.label,
        as_of_date=as_of,
        captured_at=captured_at,
        created_by_user_id=actor.user_id,
        creator_display_name=actor.display_name,
        schema_version=1,
        project_count=len(projects),
        incomplete_project_count=overview.projects_with_incomplete_coverage,
        content_hash="",
        payload=schemas.Payload(
            overview=overview,
            projects=projects,
            outlooks=forwards,
            actions=[a for a in position if a.status in ("open", "in_progress")],
            action_frontier=[
                ReportingFrontier(id=a.id, project_id=a.project_id, version=a.version)
                for a in position
            ],
            action_counts=counts,
            development=[
                schemas.DevelopmentFact.model_validate(fact)
                for fact in (
                    *service.development.reporting_permits(session, scope),
                    *service.consultant.reporting_design(session, scope),
                )
            ],
        ),
    )
    result.content_hash = canonical.content_hash(result)
    session.add(
        Snapshot(
            **result.model_dump(exclude={"payload"}), payload=result.payload.model_dump(mode="json")
        )
    )
    session.flush()
    session.add_all(
        SnapshotProject(snapshot_id=result.id, project_id=p.project_id) for p in projects
    )
    session.flush()
    return result
