"""Buyer-level operations. No writes to reservations, contracts or legal events."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.models import Project
from app.modules.projects.permissions import whole_project_ids
from app.modules.projects.service import lock_project
from app.modules.sales import permissions, service
from app.modules.sales.models import SaleLegalEvent
from app.modules.sales.operations_models import (
    OperationBuyer,
    OperationPipeline,
    OperationProgress,
    OperationStage,
)
from app.modules.sales.operations_schemas import (
    BuyerInput,
    BuyerRead,
    MilestoneRead,
    OperationsRead,
    PipelineInput,
    PurchaseRead,
    StageRead,
    StageSummary,
)

CONFIG_ROLES = frozenset({"system_admin", "project_manager", "sales_operations"})
EDIT_ROLES = frozenset({"sales_operations", "legal"})
DEFAULTS = (
    ("eoi", "Signed EOI", "property_purchase", "manual"),
    ("reservation", "Signed Reservation", "property_purchase", "manual"),
    ("engagement", "Signed Engagement Letter", "property_purchase", "manual"),
    ("spa", "Signed SPA", "property_purchase", "buyer_signed_spa"),
    ("poa", "Signed POA", "property_purchase", "manual"),
    ("clearance", "Bank Clearance", "property_purchase", "manual"),
    ("bank", "Opened Bank Account", "property_purchase", "manual"),
    ("submission", "Golden Visa Submission", "golden_visa", "manual"),
    ("issuance", "Golden Visa Issuance", "golden_visa", "manual"),
)


def allowed(actor: ActorContext, roles: frozenset[str]) -> bool:
    return actor.is_master_admin or bool(actor.role_keys.intersection(roles))


def require_access(session: Session, project: Project, actor: ActorContext) -> None:
    permissions.require_sales_reader(actor)
    # These facts belong to the buyer across all their purchases. A selected-phase
    # member must not learn a milestone arising from that buyer's hidden purchase.
    if (
        session.scalar(
            select(Project.id).where(
                Project.id == project.id, Project.id.in_(whole_project_ids(actor))
            )
        )
        is None
    ):
        raise NotFoundError("Project-wide buyer operations are not available.")


def _write(
    session: Session, project: Project, actor: ActorContext, *, config: bool = False
) -> None:
    require_access(session, project, actor)
    if not allowed(actor, CONFIG_ROLES if config else EDIT_ROLES):
        raise PermissionDeniedError(
            "You do not have permission to change these operations records."
        )
    lock_project(session, project.id)


def _default_stages(project_id: uuid.UUID) -> list[StageRead]:
    return [
        StageRead(
            id=uuid.uuid5(project_id, f"operations:{key}"),
            label=label,
            section=section,
            position=index,
            source=source,
            is_active=True,
        )
        for index, (key, label, section, source) in enumerate(DEFAULTS)
    ]


def configuration(session: Session, project_id: uuid.UUID) -> tuple[int, list[StageRead]]:
    pipeline = session.get(OperationPipeline, project_id)
    if pipeline is None:
        return 0, _default_stages(project_id)
    stages = session.scalars(
        select(OperationStage)
        .where(OperationStage.project_id == project_id)
        .order_by(OperationStage.position, OperationStage.id)
    )
    return pipeline.version, [
        StageRead.model_validate(stage, from_attributes=True) for stage in stages
    ]


def _initialize(session: Session, project_id: uuid.UUID) -> OperationPipeline:
    pipeline = session.get(OperationPipeline, project_id)
    if pipeline is None:
        pipeline = OperationPipeline(project_id=project_id, version=1)
        session.add(pipeline)
        session.flush()
        for stage in _default_stages(project_id):
            session.add(OperationStage(project_id=project_id, **stage.model_dump()))
        session.flush()
    return pipeline


def _audit(
    session: Session,
    actor: ActorContext,
    project: Project,
    action: str,
    entity_id: uuid.UUID,
    *,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> None:
    record_event(
        session,
        action=f"operations.{action}",
        entity_type="buyer_operations",
        entity_id=entity_id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after={"project_id": str(project.id), **(after or {})},
        reason=reason,
    )


def save_configuration(
    session: Session, project: Project, actor: ActorContext, payload: PipelineInput
) -> None:
    _write(session, project, actor, config=True)
    version, previous = configuration(session, project.id)
    if payload.expected_version != version:
        raise ConflictError("The pipeline changed. Reload before saving.")
    supplied = [stage.id for stage in payload.stages if stage.id is not None]
    if len(supplied) != len(set(supplied)):
        raise ValidationError("A stage cannot appear twice.")
    if set(supplied) != {stage.id for stage in previous}:
        raise ValidationError("Keep existing stages; use Delete to remove a stage.")
    pipeline = _initialize(session, project.id)
    for index, item in enumerate(payload.stages):
        if item.id is None:
            row = OperationStage(project_id=project.id, source="manual")
            session.add(row)
        else:
            row = session.scalar(
                select(OperationStage).where(
                    OperationStage.id == item.id, OperationStage.project_id == project.id
                )
            )
        row.label, row.section, row.position, row.is_active = (
            item.label,
            item.section,
            index,
            item.is_active,
        )
    pipeline.version = version + 1
    session.flush()
    _, updated = configuration(session, project.id)
    _audit(
        session,
        actor,
        project,
        "pipeline_saved",
        project.id,
        before={"stages": [stage.model_dump(mode="json") for stage in previous]},
        after={"stages": [stage.model_dump(mode="json") for stage in updated]},
    )
    session.commit()


def delete_stage(
    session: Session,
    project: Project,
    actor: ActorContext,
    stage_id: uuid.UUID,
    version: int,
    reason: str,
) -> None:
    _write(session, project, actor, config=True)
    current, stages = configuration(session, project.id)
    if current != version:
        raise ConflictError("The pipeline changed. Reload before deleting.")
    if not any(stage.id == stage_id for stage in stages):
        raise NotFoundError("Stage not found.")
    if not reason.strip():
        raise ValidationError("Give a reason for deletion.")
    pipeline = _initialize(session, project.id)
    row = session.scalar(
        select(OperationStage).where(
            OperationStage.project_id == project.id, OperationStage.id == stage_id
        )
    )
    before = StageRead.model_validate(row, from_attributes=True).model_dump(mode="json")
    used = (
        session.scalar(
            select(OperationProgress.stage_id)
            .where(
                OperationProgress.project_id == project.id, OperationProgress.stage_id == stage_id
            )
            .limit(1)
        )
        is not None
    )
    if used:
        row.is_active = False
    else:
        session.delete(row)
    pipeline.version = current + 1
    _audit(
        session,
        actor,
        project,
        "stage_retired" if used else "stage_deleted",
        stage_id,
        before=before,
        reason=reason.strip(),
    )
    session.commit()


def read(session: Session, project: Project, actor: ActorContext) -> OperationsRead:
    require_access(session, project, actor)
    version, stages = configuration(session, project.id)
    clients = service.list_clients(session, project=project, actor=actor)
    ids = [client.id for client in clients]
    profiles = {
        row.client_id: row
        for row in session.scalars(
            select(OperationBuyer).where(
                OperationBuyer.project_id == project.id, OperationBuyer.client_id.in_(ids)
            )
        )
    }
    progress = {
        (row.client_id, row.stage_id): row
        for row in session.scalars(
            select(OperationProgress).where(
                OperationProgress.project_id == project.id, OperationProgress.client_id.in_(ids)
            )
        )
    }
    sales = service.list_sales(session, project=project, actor=actor)
    reservations = service.list_reservations(session, project=project, actor=actor)
    # Bulk legal read, restricted to the same authorized sales as the register.
    events = list(
        session.scalars(
            select(SaleLegalEvent).where(
                SaleLegalEvent.project_id == project.id,
                SaleLegalEvent.sale_contract_id.in_([sale.id for sale in sales]),
            )
        )
    )
    reversed_ids = {event.reverses_event_id for event in events if event.reverses_event_id}
    signed = {}
    for event in events:
        if (
            event.event_type == "buyer_signed"
            and event.reverses_event_id is None
            and event.id not in reversed_ids
        ):
            signed[event.sale_contract_id] = max(
                signed.get(event.sale_contract_id, event.event_date), event.event_date
            )
    sales_by_client: dict[uuid.UUID, list] = {}
    purchases: dict[uuid.UUID, list[PurchaseRead]] = {}
    for sale in sales:
        purchases.setdefault(sale.client_id, []).append(
            PurchaseRead(id=sale.id, number=sale.sale_number, kind="sale", status=sale.status)
        )
        if sale.status != "cancelled":
            sales_by_client.setdefault(sale.client_id, []).append(sale)
    for reservation in reservations:
        if reservation.status != "converted":
            purchases.setdefault(reservation.client_id, []).append(
                PurchaseRead(
                    id=reservation.id,
                    number=reservation.reservation_number,
                    kind="reservation",
                    status=reservation.status,
                )
            )
    buyers = []
    for client in clients:
        profile = profiles.get(client.id)
        purpose = profile.purpose if profile else None
        milestones = []
        for stage in stages:
            saved = progress.get((client.id, stage.id))
            applicable = (
                True
                if stage.section == "property_purchase"
                else (None if purpose is None else purpose == "golden_visa")
            )
            current_sales = sales_by_client.get(client.id, [])
            dates = [signed[sale.id] for sale in current_sales if sale.id in signed]
            linked = stage.source == "buyer_signed_spa" and bool(current_sales)
            completed = (
                (len(dates) == len(current_sales))
                if linked
                else (saved.completed if saved else None)
            )
            completion_date = (
                max(dates)
                if linked and completed
                else (saved.completed_date if saved and not linked else None)
            )
            milestones.append(
                MilestoneRead(
                    stage_id=stage.id,
                    completed=completed,
                    completed_date=completion_date,
                    applicable=applicable,
                    source="Sales · buyer signature (all current purchases)"
                    if linked
                    else "Operations",
                    editable=not linked and applicable is True,
                    signed_sales=len(dates) if linked else 0,
                    total_sales=len(current_sales) if linked else 0,
                )
            )
        active = {stage.id: stage for stage in stages if stage.is_active}
        applicable_rows = [
            row for row in milestones if row.stage_id in active and row.applicable is True
        ]
        buyers.append(
            BuyerRead(
                id=client.id,
                number=client.client_number,
                name=client.display_name,
                active=client.is_active,
                purpose=purpose,
                version=profile.version if profile else 0,
                purchases=purchases.get(client.id, []),
                milestones=milestones,
                completed_count=sum(row.completed is True for row in applicable_rows),
                applicable_count=len(applicable_rows),
                next_stage=next(
                    (
                        active[row.stage_id].label
                        for row in applicable_rows
                        if row.completed is not True
                    ),
                    None,
                ),
            )
        )
    summaries = []
    for stage in stages:
        rows = [
            next(row for row in buyer.milestones if row.stage_id == stage.id) for buyer in buyers
        ]
        applicable = [row for row in rows if row.applicable is True]
        summaries.append(
            StageSummary(
                stage_id=stage.id,
                yes=sum(row.completed is True for row in applicable),
                no=sum(row.completed is False for row in applicable),
                unrecorded=sum(row.completed is None for row in applicable),
                not_applicable=sum(row.applicable is False for row in rows),
                purpose_unknown=sum(row.applicable is None for row in rows),
                applicable=len(applicable),
                missing_dates=sum(
                    row.completed is True and row.completed_date is None for row in applicable
                ),
            )
        )
    return OperationsRead(
        pipeline_version=version,
        stages=stages,
        buyers=buyers,
        summaries=summaries,
        buyer_count=len(buyers),
        golden_visa_count=sum(b.purpose == "golden_visa" for b in buyers),
        investment_count=sum(b.purpose == "investment_only" for b in buyers),
        purpose_unknown_count=sum(b.purpose is None for b in buyers),
        can_configure=allowed(actor, CONFIG_ROLES),
        can_edit=allowed(actor, EDIT_ROLES),
    )


def save_buyer(
    session: Session,
    project: Project,
    actor: ActorContext,
    client_id: uuid.UUID,
    payload: BuyerInput,
) -> None:
    _write(session, project, actor)
    permissions.require_visible_client(session, project=project, actor=actor, client_id=client_id)
    answer = read(session, project, actor)
    buyer = next(row for row in answer.buyers if row.id == client_id)
    if (
        buyer.version != payload.expected_version
        or answer.pipeline_version != payload.pipeline_version
    ):
        raise ConflictError("Buyer progress or the pipeline changed. Reload before saving.")
    if not payload.reason.strip():
        raise ValidationError("Give a reason for this update.")
    stage_map = {stage.id: stage for stage in answer.stages}
    seen = set()
    for entry in payload.progress:
        if entry.stage_id in seen or entry.stage_id not in stage_map:
            raise ValidationError("Each progress entry must identify a different project stage.")
        seen.add(entry.stage_id)
        stage = stage_map[entry.stage_id]
        milestone = next(row for row in buyer.milestones if row.stage_id == stage.id)
        if not stage.is_active or (stage.source == "buyer_signed_spa" and milestone.total_sales):
            raise ConflictError(
                "This stage is retired or linked to Sales. Update the owning record."
            )
        if stage.section == "golden_visa" and payload.purpose != "golden_visa":
            raise ValidationError("Choose Golden Visa before changing visa progress.")
    _initialize(session, project.id)
    profile = session.scalar(
        select(OperationBuyer).where(
            OperationBuyer.project_id == project.id, OperationBuyer.client_id == client_id
        )
    )
    if profile is None:
        profile = OperationBuyer(project_id=project.id, client_id=client_id)
        session.add(profile)
    profile.purpose, profile.version = payload.purpose, buyer.version + 1
    session.flush()
    for entry in payload.progress:
        row = session.scalar(
            select(OperationProgress).where(
                OperationProgress.project_id == project.id,
                OperationProgress.client_id == client_id,
                OperationProgress.stage_id == entry.stage_id,
            )
        )
        if row is None:
            row = OperationProgress(
                project_id=project.id, client_id=client_id, stage_id=entry.stage_id
            )
            session.add(row)
        row.completed, row.completed_date = entry.completed, entry.completed_date
    _audit(
        session,
        actor,
        project,
        "buyer_updated",
        client_id,
        before={
            "purpose": buyer.purpose,
            "milestones": [row.model_dump(mode="json") for row in buyer.milestones],
        },
        after=payload.model_dump(mode="json"),
        reason=payload.reason.strip(),
    )
    session.commit()


def delete_buyer_progress(
    session: Session,
    project: Project,
    actor: ActorContext,
    client_id: uuid.UUID,
    version: int,
    reason: str,
) -> None:
    _write(session, project, actor)
    permissions.require_visible_client(session, project=project, actor=actor, client_id=client_id)
    profile = session.scalar(
        select(OperationBuyer).where(
            OperationBuyer.project_id == project.id, OperationBuyer.client_id == client_id
        )
    )
    if profile is None:
        raise NotFoundError("No manually recorded operations to delete.")
    if profile.version != version:
        raise ConflictError("Buyer progress changed. Reload before deleting.")
    if not reason.strip():
        raise ValidationError("Give a reason for deletion.")
    rows = list(
        session.scalars(
            select(OperationProgress).where(
                OperationProgress.project_id == project.id, OperationProgress.client_id == client_id
            )
        )
    )
    _audit(
        session,
        actor,
        project,
        "buyer_progress_deleted",
        client_id,
        before={
            "purpose": profile.purpose,
            "progress": [
                {
                    "stage_id": str(row.stage_id),
                    "completed": row.completed,
                    "completed_date": str(row.completed_date) if row.completed_date else None,
                }
                for row in rows
            ],
        },
        reason=reason.strip(),
    )
    session.execute(
        delete(OperationProgress).where(
            OperationProgress.project_id == project.id, OperationProgress.client_id == client_id
        )
    )
    # Retain the revision frontier to reject stale edits after delete/re-create.
    profile.purpose = None
    profile.version += 1
    session.commit()
