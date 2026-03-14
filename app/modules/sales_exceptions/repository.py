"""
sales_exceptions.repository

Pure database-access layer for the SalesException entity.

All aggregation (SUM, COUNT) is performed in SQL — no Python-side loops.
No business rules live here.
"""

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.sales_exceptions.models import SalesException
from app.shared.enums.sales_exceptions import ApprovalStatus


class SalesExceptionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, exception: SalesException) -> SalesException:
        self.db.add(exception)
        self.db.commit()
        self.db.refresh(exception)
        return exception

    def save(self, exception: SalesException) -> SalesException:
        self.db.commit()
        self.db.refresh(exception)
        return exception

    # ------------------------------------------------------------------
    # Single-record reads
    # ------------------------------------------------------------------

    def get_by_id(self, exception_id: str) -> Optional[SalesException]:
        return (
            self.db.query(SalesException)
            .filter(SalesException.id == exception_id)
            .first()
        )

    # ------------------------------------------------------------------
    # List reads
    # ------------------------------------------------------------------

    def list_by_project(
        self,
        project_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SalesException]:
        return (
            self.db.query(SalesException)
            .filter(SalesException.project_id == project_id)
            .order_by(SalesException.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_project(self, project_id: str) -> int:
        return (
            self.db.query(SalesException)
            .filter(SalesException.project_id == project_id)
            .count()
        )

    def list_by_unit(self, unit_id: str) -> List[SalesException]:
        return (
            self.db.query(SalesException)
            .filter(SalesException.unit_id == unit_id)
            .order_by(SalesException.created_at.desc())
            .all()
        )

    def list_pending(self, project_id: str) -> List[SalesException]:
        return (
            self.db.query(SalesException)
            .filter(
                SalesException.project_id == project_id,
                SalesException.approval_status == ApprovalStatus.PENDING.value,
            )
            .order_by(SalesException.created_at.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # Aggregations (SQL-level)
    # ------------------------------------------------------------------

    def count_by_status(self, project_id: str, status: ApprovalStatus) -> int:
        return (
            self.db.query(SalesException)
            .filter(
                SalesException.project_id == project_id,
                SalesException.approval_status == status.value,
            )
            .count()
        )

    def sum_discount_by_project(self, project_id: str) -> float:
        result = (
            self.db.query(
                func.coalesce(func.sum(SalesException.discount_amount), 0)
            )
            .filter(
                SalesException.project_id == project_id,
                SalesException.approval_status == ApprovalStatus.APPROVED.value,
            )
            .scalar()
        )
        return float(result)

    def sum_incentive_value_by_project(self, project_id: str) -> float:
        result = (
            self.db.query(
                func.coalesce(func.sum(SalesException.incentive_value), 0)
            )
            .filter(
                SalesException.project_id == project_id,
                SalesException.approval_status == ApprovalStatus.APPROVED.value,
            )
            .scalar()
        )
        return float(result)
