"""Sales draft intake with an explicit, atomic add-to-Sales boundary."""

import hashlib
import io
import json
import uuid

from openpyxl import load_workbook
from pydantic import ValidationError as SchemaError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceError,
    ValidationError,
)
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory.models import Unit
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import agents, permissions, schemas, service
from app.modules.sales import import_draft_workbook as workbook
from app.modules.sales.import_draft_models import SalesImportDraft


def authorize(actor: ActorContext) -> None:
    # Complete workbooks contain buyer identity, legal and payment information.
    if not actor.is_master_admin:
        raise PermissionDeniedError("Only Boss may import and review complete Sales workbooks.")


def fingerprint(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def scoped_unit(session: Session, project: Project, actor: ActorContext, payload: dict) -> Unit:
    reference = payload["Sales"][0]["unit_reference"]
    unit = session.scalar(
        select(Unit).where(Unit.project_id == project.id, Unit.unit_reference == reference)
    )
    if unit is None:
        raise ValidationError("Unit reference not found in this project.")
    permissions.require_sellable_unit(session, project=project, actor=actor, unit_id=unit.id)
    client_id = payload["Sales"][0].get("client_id")
    if client_id:
        permissions.require_visible_client(
            session, project=project, actor=actor, client_id=uuid.UUID(client_id)
        )
    agent_id = (payload.get("Buyer") or [{}])[0].get("agent_id")
    if agent_id:
        service.require_agent(session, project_id=project.id, agent_id=uuid.UUID(agent_id))
    return unit


def template(
    session: Session, project: Project, actor: ActorContext, draft: SalesImportDraft | None = None
) -> bytes:
    authorize(actor)
    content = workbook.template(
        str(project.id), [(draft.source_key, draft.payload)] if draft else None
    )
    book = load_workbook(io.BytesIO(content))
    units = book.create_sheet("Unit reference")
    units.append(["unit_reference", "commercial_status"])
    for unit in session.scalars(
        select(Unit).where(Unit.project_id == project.id).order_by(Unit.unit_reference)
    ):
        units.append([unit.unit_reference, unit.commercial_status])
        for cell in units[units.max_row]:
            cell.data_type = "s"
    buyers = book.create_sheet("Buyer reference")
    buyers.append(["client_id", "display_name"])
    for client in service.list_clients(session, project=project, actor=actor):
        buyers.append([str(client.id), client.display_name])
        for cell in buyers[buyers.max_row]:
            cell.data_type = "s"
    roster = book.create_sheet("Agent reference")
    roster.append(["agent_id", "display_name", "country", "branch", "branch_leader"])
    for agent in agents.list_agents(session, project=project, actor=actor, active_only=True):
        roster.append(
            [str(agent.id), agent.display_name, agent.country, agent.branch, agent.branch_leader]
        )
        for cell in roster[roster.max_row]:
            cell.data_type = "s"
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def process(
    session: Session, project: Project, actor: ActorContext, body: bytes, *, apply: bool
) -> dict:
    authorize(actor)
    parsed = workbook.parse(body, str(project.id))
    lock_project(session, project.id)
    issues, duplicates, candidates = [], [], []
    for number, key, payload in parsed:
        try:
            payload = workbook.validate_payload(payload)
            unit = scoped_unit(session, project, actor, payload)
            digest = fingerprint(payload)
            prior = session.scalar(
                select(SalesImportDraft).where(
                    SalesImportDraft.project_id == project.id, SalesImportDraft.source_key == key
                )
            )
            if prior:
                if prior.fingerprint != digest:
                    raise ConflictError(
                        "This sale_key already has different details. Open and edit its draft."
                    )
                duplicates.append({"row": number, "source": "existing"})
            else:
                candidates.append(
                    SalesImportDraft(
                        project_id=project.id,
                        unit_id=unit.id,
                        source_key=key,
                        payload=payload,
                        fingerprint=digest,
                        created_by_user_id=actor.user_id,
                    )
                )
        except SchemaError as exc:
            issues.extend(
                {"row": number, "column": ".".join(map(str, error["loc"])), "message": error["msg"]}
                for error in exc.errors(include_input=False, include_url=False)
            )
        except ServiceError as exc:
            issues.append({"row": number, "column": None, "message": exc.detail})
    applied = apply and not issues
    if applied:
        for row in candidates:
            session.add(row)
            session.flush()
            audit(session, actor, row, "created", "Excel import")
        session.commit()
    else:
        session.rollback()
    return {
        "total_rows": len(parsed),
        "new_count": len(candidates),
        "created_count": len(candidates) if applied else 0,
        "duplicate_count": len(duplicates),
        "duplicates": duplicates[:200],
        "duplicates_truncated": len(duplicates) > 200,
        "applied": applied,
        "error_count": len(issues),
        "issues": issues[:200],
        "issues_truncated": len(issues) > 200,
    }


def audit(
    session: Session, actor: ActorContext, row: SalesImportDraft, action: str, reason: str
) -> None:
    record_event(
        session,
        action=f"sales_import_draft.{action}",
        entity_type="sales_import_draft",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason,
        after={
            "project_id": row.project_id,
            "source_key": row.source_key,
            "version": row.version,
            "fingerprint": row.fingerprint,
            "reservation_id": row.reservation_id,
        },
    )


def list_drafts(
    session: Session, project: Project, actor: ActorContext, *, offset: int = 0
) -> list[SalesImportDraft]:
    authorize(actor)
    return list(
        session.scalars(
            select(SalesImportDraft)
            .where(SalesImportDraft.project_id == project.id)
            .order_by(SalesImportDraft.created_at.desc(), SalesImportDraft.id)
            .offset(offset)
            .limit(50)
        )
    )


def get_draft(
    session: Session,
    project: Project,
    actor: ActorContext,
    draft_id: uuid.UUID,
    *,
    lock: bool = False,
) -> SalesImportDraft:
    authorize(actor)
    statement = select(SalesImportDraft).where(
        SalesImportDraft.project_id == project.id, SalesImportDraft.id == draft_id
    )
    if lock:
        lock_project(session, project.id)
        statement = statement.with_for_update().execution_options(populate_existing=True)
    row = session.scalar(statement)
    if row is None:
        raise NotFoundError("Sales import draft not found.")
    return row


def check_edit(row: SalesImportDraft, version: int) -> None:
    if row.version != version:
        raise ConflictError("The draft changed. Refresh and review the latest version.")
    if row.status != "draft":
        raise ConflictError(
            "This draft was already added. Use the transaction's normal correction "
            "or removal workflow."
        )


def edit(
    session: Session,
    project: Project,
    actor: ActorContext,
    draft_id: uuid.UUID,
    version: int,
    payload: dict,
    reason: str,
) -> SalesImportDraft:
    row = get_draft(session, project, actor, draft_id, lock=True)
    check_edit(row, version)
    row.payload = workbook.validate_payload(payload)
    row.unit_id = scoped_unit(session, project, actor, row.payload).id
    row.fingerprint = fingerprint(row.payload)
    row.version += 1
    audit(session, actor, row, "updated", reason)
    session.commit()
    return row


def delete_draft(
    session: Session,
    project: Project,
    actor: ActorContext,
    draft_id: uuid.UUID,
    version: int,
    reason: str,
) -> None:
    row = get_draft(session, project, actor, draft_id, lock=True)
    check_edit(row, version)
    audit(session, actor, row, "deleted", reason)
    session.delete(row)
    session.commit()


def add_to_sales(
    session: Session,
    project: Project,
    actor: ActorContext,
    draft_id: uuid.UUID,
    version: int,
    reason: str,
) -> SalesImportDraft:
    row = get_draft(session, project, actor, draft_id, lock=True)
    check_edit(row, version)
    payload = workbook.validate_payload(row.payload)
    unit = scoped_unit(session, project, actor, payload)
    root = payload["Sales"][0]
    try:
        client_id = root.get("client_id")
        if client_id:
            if payload.get("Buyer") or payload.get("Agent") or payload.get("Parties"):
                raise ValidationError(
                    "An existing buyer is linked without edits. Remove Buyer/Agent/Parties "
                    "rows or create a new buyer."
                )
            client = permissions.require_visible_client(
                session, project=project, actor=actor, client_id=uuid.UUID(client_id)
            )
        else:
            fields = schemas.ClientCreateRequest.model_validate(payload["Buyer"][0]).model_dump(
                exclude_none=True
            )
            if payload.get("Agent"):
                if fields.get("agent_id"):
                    raise ValidationError(
                        "Choose an existing agent_id or a new Agent row, not both."
                    )
                agent_fields = schemas.SalesAgentCreateRequest.model_validate(
                    payload["Agent"][0]
                ).model_dump()
                matches = [
                    agent
                    for agent in agents.list_agents(
                        session, project=project, actor=actor, active_only=True
                    )
                    if all(
                        (getattr(agent, key) or "").strip().casefold()
                        == (value or "").strip().casefold()
                        for key, value in agent_fields.items()
                    )
                ]
                agent = (
                    matches[0]
                    if matches
                    else agents.create_agent(
                        session, project=project, actor=actor, fields=agent_fields, commit=False
                    )
                )
                fields["agent_id"] = agent.id
            if not payload.get("Parties"):
                fields.setdefault("sole_purchaser_name", fields["display_name"])
            elif fields.get("sole_purchaser_name"):
                raise ValidationError("Use Parties or sole_purchaser_name, not both.")
            client = service.create_client(
                session, project=project, actor=actor, commit=False, **fields
            )
            for party in payload.get("Parties", []):
                service.create_party(
                    session,
                    project=project,
                    actor=actor,
                    client=client,
                    commit=False,
                    **schemas.PartyCreateRequest.model_validate(party).model_dump(
                        exclude_none=True
                    ),
                )
        terms = schemas.ReservationCreateRequest.model_validate(
            {**(payload.get("Reservation") or [{}])[0], "unit_id": unit.id, "client_id": client.id}
        ).model_dump(exclude_none=True)
        # The reviewer must provide actual commercial dates where the project has no defaults.
        reservation = service.create_reservation(
            session, project=project, actor=actor, commit=False, **terms
        )
        for adjustment in payload.get("Adjustments", []):
            service.create_adjustment(
                session,
                project=project,
                actor=actor,
                reservation_id=reservation.id,
                commit=False,
                **schemas.AdjustmentCreateRequest.model_validate(adjustment).model_dump(
                    exclude_none=True
                ),
            )
        row.reservation_id = reservation.id
        row.status = "added"
        row.version += 1
        audit(session, actor, row, "added", reason)
        session.commit()
        return row
    except Exception:
        session.rollback()
        raise
