"""All included projects must still be readable; history never grants access."""

from sqlalchemy import Select, exists, select

from app.core.errors import PermissionDeniedError
from app.modules.access.dependencies import ActorContext
from app.modules.management_reporting.models import Snapshot, SnapshotProject
from app.modules.portfolio.permissions import authorized_projects


def require_writer(actor: ActorContext) -> None:
    if not actor.is_system_admin and not actor.has_any_role("project_manager"):
        raise PermissionDeniedError("Only project management may capture management snapshots.")


def readable(actor: ActorContext) -> Select:
    scope = authorized_projects(actor)
    denied = exists(
        select(SnapshotProject.project_id).where(
            SnapshotProject.snapshot_id == Snapshot.id, SnapshotProject.project_id.not_in(scope)
        )
    )
    return select(Snapshot.id).where(~denied)
