"""Read inventory applicability without changing inventory or delivery status."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.modules.consultant_engineering.models import ProjectReportUnit, ProjectSiteReport
from app.modules.consultant_engineering.report_schemas import ReportFields
from app.modules.inventory.models import Building, Floor, Phase, Unit


def choices(session: Session, project_id: uuid.UUID) -> dict:
    buildings = session.execute(
        select(Building.id, Building.code, Building.name)
        .join(Phase, Phase.id == Building.phase_id)
        .where(
            Building.project_id == project_id,
            Building.is_active.is_(True),
            Phase.is_active.is_(True),
        )
        .order_by(Building.code, Building.id)
    ).all()
    units = session.execute(
        select(Unit.id, Unit.unit_reference, Building.id.label("building_id"))
        .outerjoin(Floor, Floor.id == Unit.floor_id)
        .join(Building, Building.id == func.coalesce(Unit.building_id, Floor.building_id))
        .where(
            Unit.project_id == project_id,
            Unit.is_active.is_(True),
            Unit.removed_at.is_(None),
            Building.id.in_([b.id for b in buildings]),
            (Unit.floor_id.is_(None) | Floor.is_active.is_(True)),
        )
        .order_by(Unit.unit_reference, Unit.id)
    ).all()
    return {
        "buildings": [{"id": b.id, "label": f"{b.code} — {b.name}"} for b in buildings],
        "units": [
            {"id": u.id, "label": u.unit_reference, "building_id": u.building_id} for u in units
        ],
    }


def apply(session: Session, row: ProjectSiteReport, fields: ReportFields) -> None:
    # Both metadata writes and inventory removal serialize on the project lock.
    # An unchanged retained assignment may be edited even after a unit is removed.
    available = (
        choices(session, row.project_id)
        if fields.kind != "site_report"
        else {"buildings": [], "units": []}
    )
    if fields.building_id != row.building_id:
        selected = next((b for b in available["buildings"] if b["id"] == fields.building_id), None)
        if fields.building_id and selected is None:
            raise ValidationError("Choose an active building in this project.")
        row.building_label = selected["label"] if selected else None
    retained = {link.unit_id: link for link in row.units}
    units = {u["id"]: u for u in available["units"]}
    links = []
    for unit_id in fields.unit_ids:
        if unit_id in retained:
            links.append(retained[unit_id])
        elif unit_id in units:
            links.append(
                ProjectReportUnit(
                    project_id=row.project_id, unit_id=unit_id, unit_label=units[unit_id]["label"]
                )
            )
        else:
            raise ValidationError("Choose active units in this project.")
    row.units = links
    for key, value in fields.model_dump(
        exclude={"unit_ids", "expected_version", "source_url"}
    ).items():
        setattr(row, key, value)
