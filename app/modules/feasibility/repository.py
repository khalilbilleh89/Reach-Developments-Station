"""
feasibility.repository

Data access layer for FeasibilityRun, FeasibilityAssumptions, and FeasibilityResult entities.
"""

from typing import List, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload, selectinload

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
            scenario_id=data.scenario_id,
            scenario_name=data.scenario_name,
            scenario_type=data.scenario_type.value,
            notes=data.notes,
            source_concept_option_id=data.source_concept_option_id,
            seed_source_type=data.seed_source_type,
            status="draft",
        )
        self.db.add(run)
        self.db.commit()
        # Re-fetch with eager project load so project_name is available immediately.
        return self.get_by_id(run.id)

    def set_status(self, run: FeasibilityRun, status: str) -> FeasibilityRun:
        """Update the lifecycle status of a run and persist the change."""
        run.status = status
        self.db.commit()
        return run

    def set_status_by_id(self, run_id: str, status: str) -> None:
        """Update the lifecycle status of a run by ID without re-fetching the run.

        updated_at is set explicitly because SQLAlchemy bulk updates bypass the
        ORM onupdate handler defined on TimestampMixin.
        """
        self.db.query(FeasibilityRun).filter(FeasibilityRun.id == run_id).update(
            {"status": status, "updated_at": datetime.now(timezone.utc)}
        )
        self.db.commit()

    def get_by_id(self, run_id: str) -> Optional[FeasibilityRun]:
        """Return a single run with the project relationship eagerly loaded."""
        return (
            self.db.query(FeasibilityRun)
            .options(joinedload(FeasibilityRun.project))
            .filter(FeasibilityRun.id == run_id)
            .first()
        )

    def list_by_project(self, project_id: str, skip: int = 0, limit: int = 100) -> List[FeasibilityRun]:
        """Return runs for a project with the project relationship eagerly loaded."""
        return (
            self.db.query(FeasibilityRun)
            .options(selectinload(FeasibilityRun.project))
            .filter(FeasibilityRun.project_id == project_id)
            .order_by(FeasibilityRun.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_project(self, project_id: str) -> int:
        return self.db.query(FeasibilityRun).filter(FeasibilityRun.project_id == project_id).count()

    def list_all(self, skip: int = 0, limit: int = 100) -> List[FeasibilityRun]:
        """Return all runs with the project relationship eagerly loaded."""
        return (
            self.db.query(FeasibilityRun)
            .options(selectinload(FeasibilityRun.project))
            .order_by(FeasibilityRun.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_all(self) -> int:
        return self.db.query(FeasibilityRun).count()

    def list_by_source_concept_option_id(
        self, concept_option_id: str
    ) -> List[FeasibilityRun]:
        """Return all feasibility runs seeded from a given concept option.

        Used for lifecycle lineage: identifies downstream runs created via
        the seed-feasibility workflow (PR-CONCEPT-063).
        """
        return (
            self.db.query(FeasibilityRun)
            .filter(FeasibilityRun.source_concept_option_id == concept_option_id)
            .order_by(FeasibilityRun.created_at.asc())
            .all()
        )

    def delete(self, run: FeasibilityRun) -> None:
        """Delete a feasibility run and cascade to owned assumptions and result."""
        self.db.delete(run)
        self.db.commit()

    def update(self, run: FeasibilityRun, data: FeasibilityRunUpdate) -> FeasibilityRun:
        # Fields that may be explicitly set to None (unlink / clear).
        # All other None values are treated as "not provided" and skipped.
        _NULLABLE_FIELDS = {"project_id", "notes"}
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "scenario_type" and value is not None:
                setattr(run, field, value.value if hasattr(value, "value") else value)
            elif value is None and field not in _NULLABLE_FIELDS:
                # Skip None for non-nullable fields; project_id and notes may be
                # explicitly cleared (unlink / remove notes).
                continue
            else:
                setattr(run, field, value)
        self.db.commit()
        # Re-fetch with eager project load so project_name is available immediately.
        return self.get_by_id(run.id)


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

    def update_partial(
        self, existing: FeasibilityAssumptions, data: FeasibilityAssumptionsUpdate
    ) -> FeasibilityAssumptions:
        """Apply only the supplied fields to an existing assumptions record."""
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing, field, value)
        self.db.commit()
        self.db.refresh(existing)
        return existing

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
        irr: float,
        equity_multiple: float,
        break_even_price: float,
        break_even_units: float,
        scenario_outputs: dict,
        viability_status: Optional[str] = None,
        risk_level: Optional[str] = None,
        decision: Optional[str] = None,
        payback_period: Optional[float] = None,
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
            existing.irr = irr
            existing.equity_multiple = equity_multiple
            existing.break_even_price = break_even_price
            existing.break_even_units = break_even_units
            existing.scenario_outputs = scenario_outputs
            existing.viability_status = viability_status
            existing.risk_level = risk_level
            existing.decision = decision
            existing.payback_period = payback_period
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
            irr=irr,
            equity_multiple=equity_multiple,
            break_even_price=break_even_price,
            break_even_units=break_even_units,
            scenario_outputs=scenario_outputs,
            viability_status=viability_status,
            risk_level=risk_level,
            decision=decision,
            payback_period=payback_period,
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

