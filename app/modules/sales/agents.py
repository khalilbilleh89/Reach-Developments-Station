"""Correct commercial attribution without changing financial or legal terms."""

import uuid

from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import permissions, service
from app.modules.sales.models import SaleContract

AGENT_FIELDS = ("agent_country", "agent_branch", "agent_branch_leader", "agent_name")


def update_sale_agent(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor: ActorContext,
    reason: str,
    fields: dict[str, str | None],
) -> SaleContract:
    permissions.require_client_writer(actor)
    project = lock_project(session, project.id)
    sale = service.get_sale(session, project=project, sale_id=sale_id, actor=actor)
    sale = service._lock_sale(session, project_id=project.id, sale_id=sale.id)
    if sale.status == "cancelled":
        raise ConflictError("A cancelled sale's attribution is retained as history.")
    reason = service._require_reason(reason, detail="Give a reason for correcting the agent.")
    changed = []
    for name in AGENT_FIELDS:
        value = fields[name]
        value = value.strip() or None if value is not None else None
        if getattr(sale, name) != value:
            changed.append(name)
            setattr(sale, name, value)
    record_event(
        session,
        action="sale_contract.agent_updated",
        entity_type="sale_contract",
        entity_id=sale.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason,
        after={"changed_fields": changed},
    )
    session.commit()
    session.refresh(sale)
    return sale
