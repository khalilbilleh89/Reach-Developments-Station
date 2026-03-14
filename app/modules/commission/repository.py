"""
commission.repository

Pure database-access layer for the Commission domain.

Responsibilities
----------------
* CRUD and list queries for CommissionPlan, CommissionSlab, CommissionPayout,
  and CommissionPayoutLine.
* SQL-level aggregations (SUM, COUNT) for summary queries.

Design contract
---------------
* No slab validation, payout calculation, or business logic here.
* Does NOT mutate SalesContract, Unit, Project, or any other domain record.
"""

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.commission.models import (
    CommissionPayout,
    CommissionPayoutLine,
    CommissionPlan,
    CommissionSlab,
)
from app.shared.enums.commission import CommissionPayoutStatus


class CommissionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # CommissionPlan
    # ------------------------------------------------------------------

    def create_plan(self, plan: CommissionPlan) -> CommissionPlan:
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def save_plan(self, plan: CommissionPlan) -> CommissionPlan:
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def get_plan_by_id(self, plan_id: str) -> Optional[CommissionPlan]:
        return (
            self.db.query(CommissionPlan)
            .filter(CommissionPlan.id == plan_id)
            .first()
        )

    def list_plans_by_project(
        self, project_id: str, skip: int = 0, limit: int = 100
    ) -> List[CommissionPlan]:
        return (
            self.db.query(CommissionPlan)
            .filter(CommissionPlan.project_id == project_id)
            .order_by(CommissionPlan.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------
    # CommissionSlab
    # ------------------------------------------------------------------

    def create_slab(self, slab: CommissionSlab) -> CommissionSlab:
        self.db.add(slab)
        self.db.commit()
        self.db.refresh(slab)
        return slab

    def list_slabs_by_plan(self, plan_id: str) -> List[CommissionSlab]:
        return (
            self.db.query(CommissionSlab)
            .filter(CommissionSlab.commission_plan_id == plan_id)
            .order_by(CommissionSlab.sequence.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # CommissionPayout
    # ------------------------------------------------------------------

    def create_payout(self, payout: CommissionPayout) -> CommissionPayout:
        self.db.add(payout)
        self.db.flush()
        return payout

    def save_payout(self, payout: CommissionPayout) -> CommissionPayout:
        self.db.commit()
        self.db.refresh(payout)
        return payout

    def get_payout_by_id(self, payout_id: str) -> Optional[CommissionPayout]:
        return (
            self.db.query(CommissionPayout)
            .filter(CommissionPayout.id == payout_id)
            .first()
        )

    def get_payout_by_sale_contract(
        self, sale_contract_id: str
    ) -> Optional[CommissionPayout]:
        return (
            self.db.query(CommissionPayout)
            .filter(CommissionPayout.sale_contract_id == sale_contract_id)
            .filter(
                CommissionPayout.status != CommissionPayoutStatus.CANCELLED.value
            )
            .first()
        )

    def list_payouts_by_project(
        self, project_id: str, skip: int = 0, limit: int = 100
    ) -> List[CommissionPayout]:
        return (
            self.db.query(CommissionPayout)
            .filter(CommissionPayout.project_id == project_id)
            .order_by(CommissionPayout.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_payouts_by_project(self, project_id: str) -> int:
        return (
            self.db.query(CommissionPayout)
            .filter(CommissionPayout.project_id == project_id)
            .count()
        )

    def count_payouts_by_status(
        self, project_id: str, status: CommissionPayoutStatus
    ) -> int:
        return (
            self.db.query(CommissionPayout)
            .filter(
                CommissionPayout.project_id == project_id,
                CommissionPayout.status == status.value,
            )
            .count()
        )

    def sum_commission_by_project(self, project_id: str) -> float:
        result = (
            self.db.query(
                func.coalesce(func.sum(CommissionPayout.commission_pool_value), 0)
            )
            .filter(CommissionPayout.project_id == project_id)
            .scalar()
        )
        return float(result)

    def sum_gross_value_by_project(self, project_id: str) -> float:
        result = (
            self.db.query(
                func.coalesce(func.sum(CommissionPayout.gross_sale_value), 0)
            )
            .filter(CommissionPayout.project_id == project_id)
            .scalar()
        )
        return float(result)

    # ------------------------------------------------------------------
    # CommissionPayoutLine
    # ------------------------------------------------------------------

    def create_payout_line(self, line: CommissionPayoutLine) -> CommissionPayoutLine:
        self.db.add(line)
        self.db.flush()
        return line

    def list_lines_by_payout(
        self, payout_id: str
    ) -> List[CommissionPayoutLine]:
        return (
            self.db.query(CommissionPayoutLine)
            .filter(CommissionPayoutLine.commission_payout_id == payout_id)
            .order_by(CommissionPayoutLine.created_at.asc())
            .all()
        )
