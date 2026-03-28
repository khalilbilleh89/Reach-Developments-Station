"""
tender_comparison.repository

Database access layer for the Tender Comparison domain.

All business-rule enforcement lives in the service layer.
This layer only issues safe, project-scoped queries.
Source construction cost records are never mutated here.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.tender_comparison.models import (
    ConstructionCostComparisonLine,
    ConstructionCostComparisonSet,
)
from app.modules.tender_comparison.schemas import (
    ConstructionCostComparisonLineCreate,
    ConstructionCostComparisonLineUpdate,
    ConstructionCostComparisonSetCreate,
    ConstructionCostComparisonSetUpdate,
)


class TenderComparisonRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Comparison Set CRUD ───────────────────────────────────────────────────

    def create_set(
        self,
        project_id: str,
        data: ConstructionCostComparisonSetCreate,
    ) -> ConstructionCostComparisonSet:
        comparison_set = ConstructionCostComparisonSet(
            project_id=project_id,
            **data.model_dump(),
        )
        self.db.add(comparison_set)
        self.db.commit()
        self.db.refresh(comparison_set)
        return comparison_set

    def get_set_by_id(
        self, set_id: str
    ) -> Optional[ConstructionCostComparisonSet]:
        return self.db.get(ConstructionCostComparisonSet, set_id)

    def list_sets_by_project(
        self,
        project_id: str,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConstructionCostComparisonSet]:
        q = self.db.query(ConstructionCostComparisonSet).filter(
            ConstructionCostComparisonSet.project_id == project_id
        )
        if is_active is not None:
            q = q.filter(ConstructionCostComparisonSet.is_active == is_active)
        return (
            q.order_by(ConstructionCostComparisonSet.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_sets_by_project(
        self,
        project_id: str,
        is_active: Optional[bool] = None,
    ) -> int:
        q = self.db.query(ConstructionCostComparisonSet).filter(
            ConstructionCostComparisonSet.project_id == project_id
        )
        if is_active is not None:
            q = q.filter(ConstructionCostComparisonSet.is_active == is_active)
        return q.count()

    def update_set(
        self,
        comparison_set: ConstructionCostComparisonSet,
        data: ConstructionCostComparisonSetUpdate,
    ) -> ConstructionCostComparisonSet:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(comparison_set, field, value)
        self.db.commit()
        self.db.refresh(comparison_set)
        return comparison_set

    # ── Comparison Line CRUD ──────────────────────────────────────────────────

    def create_line(
        self,
        comparison_set_id: str,
        data: ConstructionCostComparisonLineCreate,
        variance_amount: Decimal,
        variance_pct: Optional[Decimal],
    ) -> ConstructionCostComparisonLine:
        line = ConstructionCostComparisonLine(
            comparison_set_id=comparison_set_id,
            cost_category=data.cost_category.value,
            baseline_amount=data.baseline_amount,
            comparison_amount=data.comparison_amount,
            variance_amount=variance_amount,
            variance_pct=variance_pct,
            variance_reason=data.variance_reason.value,
            notes=data.notes,
        )
        self.db.add(line)
        self.db.commit()
        self.db.refresh(line)
        return line

    def get_line_by_id(
        self, line_id: str
    ) -> Optional[ConstructionCostComparisonLine]:
        return self.db.get(ConstructionCostComparisonLine, line_id)

    def update_line(
        self,
        line: ConstructionCostComparisonLine,
        data: ConstructionCostComparisonLineUpdate,
        variance_amount: Decimal,
        variance_pct: Optional[Decimal],
    ) -> ConstructionCostComparisonLine:
        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            # Enum fields: store the .value string
            if hasattr(value, "value"):
                setattr(line, field, value.value)
            else:
                setattr(line, field, value)
        line.variance_amount = variance_amount
        line.variance_pct = variance_pct
        self.db.commit()
        self.db.refresh(line)
        return line

    def delete_line(self, line: ConstructionCostComparisonLine) -> None:
        self.db.delete(line)
        self.db.commit()

    # ── Set variance summary ──────────────────────────────────────────────────

    def get_set_totals(
        self, set_id: str
    ) -> Tuple[int, Decimal, Decimal, Decimal]:
        """Compute line count, total baseline, total comparison, total variance
        for a comparison set via DB aggregation.

        Returns (line_count, total_baseline, total_comparison, total_variance).
        """
        row = (
            self.db.query(
                func.count(ConstructionCostComparisonLine.id),
                func.coalesce(
                    func.sum(ConstructionCostComparisonLine.baseline_amount), 0
                ),
                func.coalesce(
                    func.sum(ConstructionCostComparisonLine.comparison_amount), 0
                ),
                func.coalesce(
                    func.sum(ConstructionCostComparisonLine.variance_amount), 0
                ),
            )
            .filter(
                ConstructionCostComparisonLine.comparison_set_id == set_id
            )
            .one()
        )
        return (
            int(row[0]),
            Decimal(str(row[1])),
            Decimal(str(row[2])),
            Decimal(str(row[3])),
        )

    # ── Baseline governance ───────────────────────────────────────────────────

    def get_active_baseline_for_project(
        self, project_id: str
    ) -> Optional[ConstructionCostComparisonSet]:
        """Return the currently approved baseline set for a project, or None.

        Ordered by approved_at DESC so that if data integrity ever produces more
        than one approved baseline (e.g., from a concurrent race), the most
        recently approved record is returned deterministically.
        """
        return (
            self.db.query(ConstructionCostComparisonSet)
            .filter(
                ConstructionCostComparisonSet.project_id == project_id,
                ConstructionCostComparisonSet.is_approved_baseline.is_(True),
            )
            .order_by(ConstructionCostComparisonSet.approved_at.desc())
            .first()
        )

    def deactivate_baseline(
        self, comparison_set: ConstructionCostComparisonSet
    ) -> None:
        """Clear baseline approval state on a set (does NOT commit)."""
        comparison_set.is_approved_baseline = False
        comparison_set.approved_at = None
        comparison_set.approved_by_user_id = None

    def approve_baseline(
        self,
        comparison_set: ConstructionCostComparisonSet,
        approved_at: datetime,
        approved_by_user_id: str,
    ) -> ConstructionCostComparisonSet:
        """Mark a set as the approved baseline and commit.

        The caller is responsible for deactivating any prior active baseline
        within the same transaction before calling this method.
        """
        comparison_set.is_approved_baseline = True
        comparison_set.approved_at = approved_at
        comparison_set.approved_by_user_id = approved_by_user_id
        self.db.commit()
        self.db.refresh(comparison_set)
        return comparison_set
