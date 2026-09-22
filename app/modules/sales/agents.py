"""Project Agent roster and audited transaction attribution corrections."""

import uuid

from sqlalchemy import delete, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import record_event
from app.modules.commissions.read import agent_has_commission_history
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import permissions, service
from app.modules.sales.models import Client, Reservation, SaleContract, SalesAgent

AGENT_FIELDS = ("display_name", "country", "branch", "branch_leader", "is_active")


def _clean(fields: dict[str, object]) -> dict[str, object]:
    cleaned = {
        key: (value.strip() or None) if isinstance(value, str) else value
        for key, value in fields.items()
    }
    if "display_name" in cleaned and not cleaned["display_name"]:
        raise ValidationError("Agent name is required.")
    if "is_active" in cleaned and cleaned["is_active"] is None:
        raise ValidationError("Agent active status is required.")
    return cleaned


def list_agents(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    active_only: bool = False,
    search: str = "",
) -> list[SalesAgent]:
    permissions.require_sales_reader(actor)
    query = select(SalesAgent).where(SalesAgent.project_id == project.id)
    if active_only:
        query = query.where(SalesAgent.is_active.is_(True))
    if search.strip():
        query = query.where(SalesAgent.display_name.ilike(f"%{search.strip()}%"))
    return list(session.scalars(query.order_by(SalesAgent.display_name, SalesAgent.id)))


def get_agent(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    agent_id: uuid.UUID,
) -> SalesAgent:
    permissions.require_sales_reader(actor)
    return service.require_agent(session, project_id=project.id, agent_id=agent_id, active=False)


def create_agent(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    fields: dict[str, object],
) -> SalesAgent:
    permissions.require_client_writer(actor)
    project = lock_project(session, project.id)
    agent = SalesAgent(
        project_id=project.id,
        created_by_user_id=actor.user_id,
        **_clean(fields),
    )
    session.add(agent)
    session.flush()
    record_event(
        session,
        action="sales_agent.created",
        entity_type="sales_agent",
        entity_id=agent.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        after={"project_id": str(project.id), "display_name": agent.display_name},
    )
    session.commit()
    session.refresh(agent)
    return agent


def update_agent(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    agent_id: uuid.UUID,
    fields: dict[str, object],
) -> SalesAgent:
    permissions.require_client_writer(actor)
    project = lock_project(session, project.id)
    agent = session.scalar(
        select(SalesAgent)
        .where(SalesAgent.id == agent_id, SalesAgent.project_id == project.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if agent is None:
        raise NotFoundError("Agent not found.")
    before = {key: getattr(agent, key) for key in AGENT_FIELDS}
    fields = _clean(fields)
    for key, value in fields.items():
        setattr(agent, key, value)
    agent.updated_by_user_id = actor.user_id
    session.flush()
    changed = sorted(key for key in fields if before[key] != getattr(agent, key))
    action = (
        "sales_agent.deactivated"
        if before["is_active"] and not agent.is_active
        else "sales_agent.reactivated"
        if not before["is_active"] and agent.is_active
        else "sales_agent.updated"
    )
    record_event(
        session,
        action=action,
        entity_type="sales_agent",
        entity_id=agent.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before={"project_id": str(project.id), **before},
        after={
            "project_id": str(project.id),
            **{key: getattr(agent, key) for key in AGENT_FIELDS},
            "changed_fields": changed,
        },
    )
    session.commit()
    session.refresh(agent)
    return agent


def delete_agent(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    agent_id: uuid.UUID,
    reason: str,
) -> None:
    permissions.require_client_writer(actor)
    reason = service._require_reason(reason, detail="Give a reason for deleting this Agent.")
    project = lock_project(session, project.id)
    agent = session.scalar(
        select(SalesAgent)
        .where(SalesAgent.id == agent_id, SalesAgent.project_id == project.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if agent is None:
        raise NotFoundError("Agent not found.")
    for model in (Client, Reservation, SaleContract):
        if session.scalar(
            select(exists().where(model.project_id == project.id, model.agent_id == agent.id))
        ):
            raise ConflictError("This Agent has buyer or transaction history. Deactivate instead.")
    if agent_has_commission_history(session, project_id=project.id, sales_agent_id=agent.id):
        raise ConflictError("This Agent has commission history. Deactivate instead.")
    if session.scalar(
        select(
            exists().where(
                AuditEvent.entity_type == "sales_agent",
                AuditEvent.entity_id == agent.id,
                AuditEvent.action == "sales_agent.assigned",
            )
        )
    ):
        raise ConflictError("This Agent has attribution history. Deactivate instead.")
    try:
        session.execute(
            delete(SalesAgent).where(SalesAgent.id == agent.id, SalesAgent.project_id == project.id)
        )
        session.flush()
        record_event(
            session,
            action="sales_agent.deleted",
            entity_type="sales_agent",
            entity_id=agent.id,
            actor_user_id=actor.user_id,
            correlation_id=actor.correlation_id,
            reason=reason,
            before={"project_id": str(project.id), "display_name": agent.display_name},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("This Agent is referenced. Deactivate instead.") from exc


def update_sale_agent(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor: ActorContext,
    reason: str,
    agent_id: uuid.UUID | None,
) -> SaleContract:
    permissions.require_client_writer(actor)
    project = lock_project(session, project.id)
    sale = service.get_sale(session, project=project, sale_id=sale_id, actor=actor)
    sale = service._lock_sale(session, project_id=project.id, sale_id=sale.id)
    if sale.status == "cancelled":
        raise ConflictError("A cancelled sale's attribution is retained as history.")
    reason = service._require_reason(reason, detail="Give a reason for correcting the agent.")
    agent = (
        service.require_agent(session, project_id=project.id, agent_id=agent_id)
        if agent_id
        else None
    )
    before = {
        "agent_id": str(sale.agent_id) if sale.agent_id else None,
        "agent_name": sale.agent_name,
        "agent_country": sale.agent_country,
        "agent_branch": sale.agent_branch,
        "agent_branch_leader": sale.agent_branch_leader,
    }
    sale.agent_id = agent.id if agent else None
    sale.agent_country = agent.country if agent else None
    sale.agent_branch = agent.branch if agent else None
    sale.agent_branch_leader = agent.branch_leader if agent else None
    sale.agent_name = agent.display_name if agent else None
    record_event(
        session,
        action="sale_contract.agent_updated",
        entity_type="sale_contract",
        entity_id=sale.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason,
        before=before,
        after={
            "agent_id": str(sale.agent_id) if sale.agent_id else None,
            "agent_name": sale.agent_name,
            "agent_country": sale.agent_country,
            "agent_branch": sale.agent_branch,
            "agent_branch_leader": sale.agent_branch_leader,
        },
    )
    if agent:
        service.record_agent_assignment(session, agent_id=agent.id, sale_id=sale.id, actor=actor)
    session.commit()
    session.refresh(sale)
    return sale
