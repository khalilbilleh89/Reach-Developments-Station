"""
feasibility.repository

Data access layer for FeasibilityRun, FeasibilityAssumptions, and FeasibilityResult entities.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.feasibility.models import FeasibilityAssumptions, FeasibilityResult, FeasibilityRun
from app.modules.feasibility.schemas import (
    FeasibilityAssumptionsCreate,
    FeasibilityAssumptionsUpdate,
    FeasibilityRunCreate,
    FeasibilityRunUpdate,
)


class FeasibilityRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: FeasibilityRunCreate) -> FeasibilityRun:
        run = FeasibilityRun(
            project_id=data.project_id,
            scenario_name=data.scenario_name,
            scenario_type=data.scenario_type.value,
            notes=data.notes,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_by_id(self, run_id: str) -> Optional[FeasibilityRun]:
        return self.db.query(FeasibilityRun).filter(FeasibilityRun.id == run_id).first()

    def list_by_project(self, project_id: str, skip: int = 0, limit: int = 100) -> List[FeasibilityRun]:
        return (
            self.db.query(FeasibilityRun)
            .filter(FeasibilityRun.project_id == project_id)
            .order_by(FeasibilityRun.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_project(self, project_id: str) -> int:
        return self.db.query(FeasibilityRun).filter(FeasibilityRun.project_id == project_id).count()

    def list_all(self, skip: int = 0, limit: int = 100) -> List[FeasibilityRun]:
        return (
            self.db.query(FeasibilityRun)
            .order_by(FeasibilityRun.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_all(self) -> int:
        return self.db.query(FeasibilityRun).count()

    def update(self, run: FeasibilityRun, data: FeasibilityRunUpdate) -> FeasibilityRun:
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in update_data.items():
            if field == "scenario_type":
                setattr(run, field, value.value if hasattr(value, "value") else value)
            else:
                setattr(run, field, value)
        self.db.commit()
        self.db.refresh(run)
        return run


class FeasibilityAssumptionsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(self, run_id: str, data: FeasibilityAssumptionsCreate) -> FeasibilityAssumptions:
        """Create or replace assumptions for a run (one set per run)."""
        existing = self.get_by_run(run_id)
        if existing:
            update_data = data.model_dump()
            for field, value in update_data.items():
                setattr(existing, field, value)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        assumptions = FeasibilityAssumptions(run_id=run_id, **data.model_dump())
        self.db.add(assumptions)
        self.db.commit()
        self.db.refresh(assumptions)
        return assumptions

    def get_by_run(self, run_id: str) -> Optional[FeasibilityAssumptions]:
        return (
            self.db.query(FeasibilityAssumptions)
            .filter(FeasibilityAssumptions.run_id == run_id)
            .first()
        )


class FeasibilityResultRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_or_replace(
        self,
        run_id: str,
        gdv: float,
        construction_cost: float,
        soft_cost: float,
        finance_cost: float,
        sales_cost: float,
        total_cost: float,
        developer_profit: float,
        profit_margin: float,
        irr_estimate: float,
    ) -> FeasibilityResult:
        """Create or replace the result for a run (one result per run)."""
        existing = self.get_by_run(run_id)
        if existing:
            existing.gdv = gdv
            existing.construction_cost = construction_cost
            existing.soft_cost = soft_cost
            existing.finance_cost = finance_cost
            existing.sales_cost = sales_cost
            existing.total_cost = total_cost
            existing.developer_profit = developer_profit
            existing.profit_margin = profit_margin
            existing.irr_estimate = irr_estimate
            self.db.commit()
            self.db.refresh(existing)
            return existing
        result = FeasibilityResult(
            run_id=run_id,
            gdv=gdv,
            construction_cost=construction_cost,
            soft_cost=soft_cost,
            finance_cost=finance_cost,
            sales_cost=sales_cost,
            total_cost=total_cost,
            developer_profit=developer_profit,
            profit_margin=profit_margin,
            irr_estimate=irr_estimate,
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def get_by_run(self, run_id: str) -> Optional[FeasibilityResult]:
        return (
            self.db.query(FeasibilityResult)
            .filter(FeasibilityResult.run_id == run_id)
            .first()
        )

