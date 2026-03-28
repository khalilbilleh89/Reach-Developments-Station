"""
construction_costs.repository

Database access layer for the Construction Cost Records domain.

All business-rule enforcement lives in the service layer.
This layer only issues safe, project-scoped queries.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.construction_costs.models import ConstructionCostRecord
from app.modules.construction_costs.schemas import (
    ConstructionCostRecordCreate,
    ConstructionCostRecordUpdate,
)
from app.shared.enums.construction_costs import CostCategory, CostStage


class ConstructionCostRecordRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        project_id: str,
        data: ConstructionCostRecordCreate,
    ) -> ConstructionCostRecord:
        record = ConstructionCostRecord(
            project_id=project_id,
            **data.model_dump(),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_id(self, record_id: str) -> Optional[ConstructionCostRecord]:
        return self.db.get(ConstructionCostRecord, record_id)

    def list_by_project(
        self,
        project_id: str,
        is_active: Optional[bool] = None,
        cost_category: Optional[CostCategory] = None,
        cost_stage: Optional[CostStage] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConstructionCostRecord]:
        q = self.db.query(ConstructionCostRecord).filter(
            ConstructionCostRecord.project_id == project_id
        )
        if is_active is not None:
            q = q.filter(ConstructionCostRecord.is_active == is_active)
        if cost_category is not None:
            q = q.filter(ConstructionCostRecord.cost_category == cost_category.value)
        if cost_stage is not None:
            q = q.filter(ConstructionCostRecord.cost_stage == cost_stage.value)
        return (
            q.order_by(ConstructionCostRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_project(
        self,
        project_id: str,
        is_active: Optional[bool] = None,
        cost_category: Optional[CostCategory] = None,
        cost_stage: Optional[CostStage] = None,
    ) -> int:
        q = self.db.query(ConstructionCostRecord).filter(
            ConstructionCostRecord.project_id == project_id
        )
        if is_active is not None:
            q = q.filter(ConstructionCostRecord.is_active == is_active)
        if cost_category is not None:
            q = q.filter(ConstructionCostRecord.cost_category == cost_category.value)
        if cost_stage is not None:
            q = q.filter(ConstructionCostRecord.cost_stage == cost_stage.value)
        return q.count()

    def get_aggregate_summary(
        self, project_id: str
    ) -> Tuple[int, Decimal, Dict[str, Decimal], Dict[str, Decimal]]:
        """Compute grand total, per-category totals, and per-stage totals via DB
        aggregation (active records only).

        Returns a tuple of:
          (active_record_count, grand_total, by_category, by_stage)

        All aggregation is performed in the database — no Python-side record
        loading is involved.
        """
        base_filter = [
            ConstructionCostRecord.project_id == project_id,
            ConstructionCostRecord.is_active.is_(True),
        ]

        # Grand total + count in one query
        count_total = (
            self.db.query(
                func.count(ConstructionCostRecord.id),
                func.coalesce(func.sum(ConstructionCostRecord.amount), 0),
            )
            .filter(*base_filter)
            .one()
        )
        active_count: int = count_total[0]
        grand_total = Decimal(str(count_total[1]))

        # Per-category totals
        category_rows = (
            self.db.query(
                ConstructionCostRecord.cost_category,
                func.sum(ConstructionCostRecord.amount),
            )
            .filter(*base_filter)
            .group_by(ConstructionCostRecord.cost_category)
            .all()
        )
        by_category: Dict[str, Decimal] = {
            cat: Decimal(str(total)) for cat, total in category_rows
        }

        # Per-stage totals
        stage_rows = (
            self.db.query(
                ConstructionCostRecord.cost_stage,
                func.sum(ConstructionCostRecord.amount),
            )
            .filter(*base_filter)
            .group_by(ConstructionCostRecord.cost_stage)
            .all()
        )
        by_stage: Dict[str, Decimal] = {
            stage: Decimal(str(total)) for stage, total in stage_rows
        }

        return active_count, grand_total, by_category, by_stage

    def update(
        self,
        record: ConstructionCostRecord,
        data: ConstructionCostRecordUpdate,
    ) -> ConstructionCostRecord:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        self.db.commit()
        self.db.refresh(record)
        return record

    def archive(self, record: ConstructionCostRecord) -> ConstructionCostRecord:
        record.is_active = False
        self.db.commit()
        self.db.refresh(record)
        return record
