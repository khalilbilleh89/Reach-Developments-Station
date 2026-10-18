"""Project-scoped drawing calibration and unit footprint authoring."""

import struct
import subprocess
import sys
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory.models import Masterplan, MasterplanMapping, Unit
from app.modules.inventory.permissions import (
    require_inventory_structure_writer,
    require_operational_project,
    visible_phase_ids,
)
from app.modules.projects.schemas import StrictRequest
from app.modules.projects.service import lock_project

MAX_BYTES = 10 * 1024 * 1024


class PlanInput(StrictRequest):
    title: str = Field(min_length=1, max_length=200)
    source_reference: str = Field(min_length=1, max_length=500)
    kind: Literal["plan", "render", "elevation"] = "plan"
    width_m: Decimal | None = Field(default=None, gt=0, le=10000, decimal_places=4)

    @model_validator(mode="after")
    def nonblank(self) -> "PlanInput":
        self.title = self.title.strip()
        self.source_reference = self.source_reference.strip()
        if not self.title or not self.source_reference:
            raise ValueError("Title and source reference are required.")
        return self


class PlanUpdate(PlanInput):
    version: int = Field(ge=1)


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    source_reference: str
    filename: str
    kind: str
    page_number: int
    pixel_width: int
    pixel_height: int
    width_m: Decimal | None
    version: int


class MappingInput(StrictRequest):
    unit_id: uuid.UUID
    points: list[tuple[float, float]] = Field(min_length=3, max_length=64)
    base_m: Decimal = Field(ge=0, le=1000, decimal_places=4)
    height_m: Decimal = Field(gt=0, le=1000, decimal_places=4)

    @model_validator(mode="after")
    def polygon(self) -> "MappingInput":
        points = self.points
        if any(not (0 <= x <= 1 and 0 <= y <= 1) for x, y in points):
            raise ValueError("Every vertex must lie on the drawing.")
        if len(set(points)) != len(points):
            raise ValueError("Vertices must be distinct; do not repeat the first point.")
        edges = list(zip(points, points[1:] + points[:1], strict=True))
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)
        if abs(area) < 0.000001:
            raise ValueError("A footprint must have a measurable area.")

        def cross(a: tuple, b: tuple, c: tuple) -> float:
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        for i, (a, b) in enumerate(edges):
            for j, (c, d) in enumerate(edges):
                if j <= i or j == i + 1 or (i == 0 and j == len(edges) - 1):
                    continue
                # Inclusive intersections reject touching and collinear overlaps too.
                if (
                    max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0]))
                    and max(min(a[1], b[1]), min(c[1], d[1]))
                    <= min(max(a[1], b[1]), max(c[1], d[1]))
                    and cross(a, b, c) * cross(a, b, d) <= 0
                    and cross(c, d, a) * cross(c, d, b) <= 0
                ):
                    raise ValueError("Footprint edges must not cross or touch.")
        return self


class MappingUpdate(MappingInput):
    version: int = Field(ge=1)


class MappingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    unit_id: uuid.UUID
    plan_id: uuid.UUID
    points: list[tuple[float, float]]
    base_m: Decimal
    height_m: Decimal
    version: int


def require_scope(session: Session, project_id: uuid.UUID, actor: ActorContext) -> None:
    # A full masterplan image itself exposes all phases. Filtering its outlines
    # cannot make it safe for a selected-phase membership.
    if visible_phase_ids(session, project_id=project_id, actor=actor) is not None:
        raise PermissionDeniedError("Masterplan requires whole-project access.")


def writable(session: Session, project_id: uuid.UUID, actor: ActorContext) -> None:
    require_inventory_structure_writer(actor)
    require_scope(session, project_id, actor)
    require_operational_project(lock_project(session, project_id))


def get_plan(session: Session, project_id: uuid.UUID, plan_id: uuid.UUID) -> Masterplan:
    row = session.scalar(
        select(Masterplan)
        .where(Masterplan.id == plan_id, Masterplan.project_id == project_id)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Drawing not found.")
    return row


def audit(
    session: Session,
    actor: ActorContext,
    row: Masterplan | MasterplanMapping,
    action: str,
    before: dict | None = None,
    reason: str | None = None,
) -> None:
    schema = PlanRead if isinstance(row, Masterplan) else MappingRead
    record_event(
        session,
        action=f"masterplan.{action}",
        entity_type="masterplan" if isinstance(row, Masterplan) else "masterplan_mapping",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after={
            "project_id": str(row.project_id),
            **schema.model_validate(row).model_dump(mode="json"),
            **({"reason": reason} if reason else {}),
        },
    )


def create_plan(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    payload: PlanInput,
    filename: str,
    page_number: int,
    data: bytes,
) -> Masterplan:
    writable(session, project_id, actor)
    if not data or len(data) > MAX_BYTES:
        raise ValidationError("Choose a PDF, PNG, JPEG or WebP file up to 10 MiB.")
    # Each PDFium instance is process-local. A malformed or complex input has a
    # wall-clock bound and cannot crash the API worker or execute embedded script.
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.modules.inventory.masterplan_render", str(page_number)],
            input=data,
            capture_output=True,
            timeout=30,
            check=True,
        )
        preview = result.stdout
        if not preview.startswith(b"\x89PNG\r\n\x1a\n") or len(preview) > 25 * 1024 * 1024:
            raise ValueError("Invalid preview")
        width, height = struct.unpack(">II", preview[16:24])
    except (subprocess.SubprocessError, ValueError, struct.error) as exc:
        raise ValidationError(
            "Could not render this file/page. Use an unencrypted PDF or a PNG, JPEG or WebP image."
        ) from exc
    row = Masterplan(
        project_id=project_id,
        **payload.model_dump(),
        filename=filename.replace("\\", "/").split("/")[-1][:200] or "drawing",
        page_number=page_number,
        pixel_width=width,
        pixel_height=height,
        source_data=data,
        preview_data=preview,
    )
    session.add(row)
    session.flush()
    audit(session, actor, row, "created")
    session.commit()
    return row


def update_plan(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    plan_id: uuid.UUID,
    payload: PlanUpdate,
) -> Masterplan:
    writable(session, project_id, actor)
    row = get_plan(session, project_id, plan_id)
    if row.version != payload.version:
        raise ConflictError("Drawing changed. Reload before editing.")
    before = PlanRead.model_validate(row).model_dump(mode="json")
    for key, value in payload.model_dump(exclude={"version"}).items():
        setattr(row, key, value)
    row.version += 1
    audit(session, actor, row, "updated", before)
    session.commit()
    return row


def mappings(
    session: Session, project_id: uuid.UUID, plan_id: uuid.UUID
) -> list[MasterplanMapping]:
    return list(
        session.scalars(
            select(MasterplanMapping)
            .where(MasterplanMapping.project_id == project_id, MasterplanMapping.plan_id == plan_id)
            .order_by(MasterplanMapping.id)
        )
    )


def save_mapping(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    plan_id: uuid.UUID,
    payload: MappingInput,
    mapping_id: uuid.UUID | None = None,
) -> MasterplanMapping:
    writable(session, project_id, actor)
    get_plan(session, project_id, plan_id)
    unit = session.scalar(
        select(Unit).where(
            Unit.id == payload.unit_id,
            Unit.project_id == project_id,
            Unit.is_active.is_(True),
            Unit.removed_at.is_(None),
        )
    )
    if unit is None:
        raise NotFoundError("Active unit not found in this project.")
    duplicates = select(MasterplanMapping.id).where(
        MasterplanMapping.project_id == project_id,
        MasterplanMapping.plan_id == plan_id,
        MasterplanMapping.unit_id == payload.unit_id,
    )
    if mapping_id:
        duplicates = duplicates.where(MasterplanMapping.id != mapping_id)
    if session.scalar(duplicates) is not None:
        raise ConflictError("This unit already has a footprint on this drawing. Edit it instead.")
    row = None
    before = None
    if mapping_id:
        row = get_mapping(session, project_id, plan_id, mapping_id)
        if not isinstance(payload, MappingUpdate) or row.version != payload.version:
            raise ConflictError("Footprint changed. Reload before editing.")
        before = MappingRead.model_validate(row).model_dump(mode="json")
    values = payload.model_dump(exclude={"version"})
    values["points"] = [list(point) for point in payload.points]
    if row:
        for key, value in values.items():
            setattr(row, key, value)
        row.version += 1
    else:
        row = MasterplanMapping(project_id=project_id, plan_id=plan_id, **values)
        session.add(row)
    session.flush()
    audit(session, actor, row, "mapping_updated" if mapping_id else "mapping_created", before)
    session.commit()
    return row


def get_mapping(
    session: Session, project_id: uuid.UUID, plan_id: uuid.UUID, mapping_id: uuid.UUID
) -> MasterplanMapping:
    row = session.scalar(
        select(MasterplanMapping)
        .where(
            MasterplanMapping.id == mapping_id,
            MasterplanMapping.project_id == project_id,
            MasterplanMapping.plan_id == plan_id,
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Footprint not found.")
    return row


def delete(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    plan_id: uuid.UUID,
    version: int,
    reason: str,
    mapping_id: uuid.UUID | None = None,
) -> None:
    writable(session, project_id, actor)
    plan = get_plan(session, project_id, plan_id)
    row = get_mapping(session, project_id, plan_id, mapping_id) if mapping_id else plan
    if row.version != version:
        raise ConflictError("Record changed. Reload before deleting.")
    if not reason.strip():
        raise ValidationError("A deletion reason is required.")
    if not mapping_id and mappings(session, project_id, plan_id):
        raise ConflictError(
            "Delete this drawing's unit footprints first. Inventory and sales records are retained."
        )
    audit(
        session, actor, row, "mapping_deleted" if mapping_id else "deleted", reason=reason.strip()
    )
    session.delete(row)
    session.commit()


def preview(session: Session, project_id: uuid.UUID, plan_id: uuid.UUID) -> bytes:
    row = session.scalar(
        select(Masterplan)
        .where(Masterplan.id == plan_id, Masterplan.project_id == project_id)
        .options(undefer(Masterplan.preview_data))
    )
    if row is None:
        raise NotFoundError("Drawing not found.")
    return row.preview_data


def source(session: Session, project_id: uuid.UUID, plan_id: uuid.UUID) -> tuple[str, bytes]:
    row = session.scalar(
        select(Masterplan)
        .where(Masterplan.id == plan_id, Masterplan.project_id == project_id)
        .options(undefer(Masterplan.source_data))
    )
    if row is None:
        raise NotFoundError("Drawing not found.")
    return row.filename, row.source_data
