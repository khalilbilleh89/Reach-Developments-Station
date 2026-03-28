"""
construction_costs.service

Business logic for the Construction Cost Records domain.

Validates project existence, enforces enum integrity, and exposes
simple per-project summary aggregates (grouped totals by category/stage).
No feasibility formulas or downstream finance writes are performed here.
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.construction_costs.models import ConstructionCostRecord
from app.modules.construction_costs.repository import ConstructionCostRecordRepository
from app.modules.construction_costs.schemas import (
    ConstructionCostRecordCreate,
    ConstructionCostRecordList,
    ConstructionCostRecordResponse,
    ConstructionCostRecordUpdate,
    ConstructionCostSummaryResponse,
)
from app.modules.projects.models import Project
from app.shared.enums.construction_costs import CostCategory, CostStage


class ConstructionCostService:
    def __init__(self, db: Session) -> None:
        self.repo = ConstructionCostRecordRepository(db)
        self.db = db

    # ── helpers ───────────────────────────────────────────────────────────────

    def _require_project(self, project_id: str) -> Project:
        project = self.db.get(Project, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        return project

    def _require_record(self, record_id: str) -> ConstructionCostRecord:
        record = self.repo.get_by_id(record_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction cost record '{record_id}' not found.",
            )
        return record

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create_record(
        self,
        project_id: str,
        data: ConstructionCostRecordCreate,
    ) -> ConstructionCostRecordResponse:
        self._require_project(project_id)
        record = self.repo.create(project_id, data)
        return ConstructionCostRecordResponse.model_validate(record)

    def list_records(
        self,
        project_id: str,
        is_active: Optional[bool] = None,
        cost_category: Optional[CostCategory] = None,
        cost_stage: Optional[CostStage] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> ConstructionCostRecordList:
        self._require_project(project_id)
        items = self.repo.list_by_project(
            project_id,
            is_active=is_active,
            cost_category=cost_category,
            cost_stage=cost_stage,
            skip=skip,
            limit=limit,
        )
        total = self.repo.count_by_project(
            project_id,
            is_active=is_active,
            cost_category=cost_category,
            cost_stage=cost_stage,
        )
        return ConstructionCostRecordList(
            total=total,
            items=[ConstructionCostRecordResponse.model_validate(r) for r in items],
        )

    def get_record(self, record_id: str) -> ConstructionCostRecordResponse:
        record = self._require_record(record_id)
        return ConstructionCostRecordResponse.model_validate(record)

    def update_record(
        self,
        record_id: str,
        data: ConstructionCostRecordUpdate,
    ) -> ConstructionCostRecordResponse:
        record = self._require_record(record_id)
        updated = self.repo.update(record, data)
        return ConstructionCostRecordResponse.model_validate(updated)

    def archive_record(self, record_id: str) -> ConstructionCostRecordResponse:
        record = self._require_record(record_id)
        archived = self.repo.archive(record)
        return ConstructionCostRecordResponse.model_validate(archived)

    # ── summary aggregates ────────────────────────────────────────────────────

    def get_project_summary(self, project_id: str) -> ConstructionCostSummaryResponse:
        """Return DB-aggregated totals by category and by stage (active records only).

        Aggregation is performed in the database via GROUP BY / SUM — no
        Python-side record fetching or arbitrary row limits are involved.
        These are transparent sums; they are not financial formula outputs.
        """
        self._require_project(project_id)
        active_count, grand_total, by_category, by_stage = (
            self.repo.get_aggregate_summary(project_id)
        )
        return ConstructionCostSummaryResponse(
            project_id=project_id,
            active_record_count=active_count,
            grand_total=grand_total,
            by_category=by_category,
            by_stage=by_stage,
        )
