"""Current design programme belonging only to the active engagement."""

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.consultant_engineering.models import (
    ConsultantDeliverable,
    ConsultantDesignStage,
    ConsultantEngagement,
)


@dataclass
class DesignPosition:
    engagement_id: uuid.UUID
    consultant_name: str
    current_stage: str | None = None
    planned_date: date | None = None
    forecast_date: date | None = None
    actual_date: date | None = None
    stage_status: str | None = None
    stage_count: int = 0
    deliverable_count: int = 0
    undated_open_items: int = 0
    overdue_stages: list[tuple[uuid.UUID, str, date]] = field(default_factory=list)
    overdue_deliverables: list[tuple[uuid.UUID, str, date]] = field(default_factory=list)
    open_stages: list[tuple[uuid.UUID, str, date, str, date | None, date | None, date | None]] = (
        field(default_factory=list)
    )
    open_deliverables: list[tuple[uuid.UUID, str, date, str]] = field(default_factory=list)


def positions(
    session: Session, project_ids: Select, as_of: date
) -> dict[uuid.UUID, DesignPosition]:
    active = select(ConsultantEngagement.id).where(
        ConsultantEngagement.project_id.in_(project_ids), ConsultantEngagement.status == "active"
    )
    result = {
        row.project_id: DesignPosition(row.id, row.consultant_name)
        for row in session.scalars(
            select(ConsultantEngagement).where(ConsultantEngagement.id.in_(active))
        )
    }
    for stage in session.scalars(
        select(ConsultantDesignStage)
        .where(ConsultantDesignStage.engagement_id.in_(active))
        .order_by(ConsultantDesignStage.sequence, ConsultantDesignStage.id)
    ):
        target = result[stage.project_id]
        target.stage_count += 1
        if stage.status in {"completed", "cancelled"}:
            continue
        if target.current_stage is None or (
            stage.status in {"in_progress", "on_hold"} and target.stage_status == "not_started"
        ):
            target.current_stage = stage.name
            target.planned_date = stage.planned_date
            target.forecast_date = stage.forecast_date
            target.actual_date = stage.actual_completion_date
            target.stage_status = stage.status
        due = stage.forecast_date or stage.planned_date
        if due is not None and stage.actual_completion_date is None:
            target.open_stages.append(
                (
                    stage.id,
                    stage.name,
                    due,
                    stage.status,
                    stage.planned_date,
                    stage.forecast_date,
                    stage.actual_completion_date,
                )
            )
        if due is None:
            target.undated_open_items += 1
        elif due < as_of and stage.actual_completion_date is None:
            target.overdue_stages.append((stage.id, stage.name, due))
    for item in session.scalars(
        select(ConsultantDeliverable).where(ConsultantDeliverable.engagement_id.in_(active))
    ):
        target = result[item.project_id]
        target.deliverable_count += 1
        if item.status in {"accepted", "superseded", "cancelled"}:
            continue
        if item.due_date is None:
            target.undated_open_items += 1
        else:
            target.open_deliverables.append((item.id, item.name, item.due_date, item.status))
            if item.due_date < as_of:
                target.overdue_deliverables.append((item.id, item.name, item.due_date))
    return result
