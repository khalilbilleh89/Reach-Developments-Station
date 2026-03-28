"""
pricing_optimization.repository

Read-only data access for pricing optimization intelligence.

Queries unit inventory, pricing records, contract dates, and feasibility
data needed to generate demand-responsive pricing recommendations.

All methods are read-only — no pricing or source records are mutated.
"""

from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.feasibility.models import FeasibilityAssumptions, FeasibilityResult, FeasibilityRun
from app.modules.floors.models import Floor
from app.modules.phases.models import Phase
from app.modules.pricing.models import UnitPricing
from app.modules.projects.models import Project
from app.modules.sales.models import SalesContract
from app.modules.units.models import Unit


class PricingOptimizationRepository:
    """Read-only repository for pricing optimization data access."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Project helpers
    # ------------------------------------------------------------------

    def get_project(self, project_id: str) -> Optional[Project]:
        """Return a project by ID, or None if not found."""
        return self.db.query(Project).filter(Project.id == project_id).first()

    def list_projects(self) -> List[Project]:
        """Return all projects ordered by name."""
        return self.db.query(Project).order_by(Project.name).all()

    # ------------------------------------------------------------------
    # Unit type aggregates (per project)
    # ------------------------------------------------------------------

    def get_unit_type_status_counts_for_project(
        self, project_id: str
    ) -> Dict[str, Dict[str, int]]:
        """Return per-unit-type status counts for a single project.

        Returns {unit_type: {status: count}}.
        """
        rows = (
            self.db.query(Unit.unit_type, Unit.status, func.count(Unit.id))
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .group_by(Unit.unit_type, Unit.status)
            .all()
        )
        result: Dict[str, Dict[str, int]] = {}
        for unit_type, status, count in rows:
            result.setdefault(unit_type, {})[status] = count
        return result

    def get_avg_price_by_unit_type_for_project(
        self, project_id: str
    ) -> Dict[str, float]:
        """Return avg final_price per unit type from active (non-archived) pricing records.

        Returns {unit_type: avg_price}.  Unit types with no pricing records are excluded.
        """
        rows = (
            self.db.query(Unit.unit_type, func.avg(UnitPricing.final_price))
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .join(UnitPricing, UnitPricing.unit_id == Unit.id)
            .filter(Phase.project_id == project_id)
            .filter(UnitPricing.pricing_status.notin_(["archived"]))
            .group_by(Unit.unit_type)
            .all()
        )
        return {
            unit_type: float(avg_price)
            for unit_type, avg_price in rows
            if avg_price is not None
        }

    # ------------------------------------------------------------------
    # Contract date helpers (for absorption velocity)
    # ------------------------------------------------------------------

    def get_contract_date_bounds_for_project(
        self, project_id: str
    ) -> Optional[Tuple]:
        """Return (min_contract_date, max_contract_date, contract_count) for a project.

        Returns None when the project has no non-cancelled contracts.
        """
        row = (
            self.db.query(
                func.min(SalesContract.contract_date),
                func.max(SalesContract.contract_date),
                func.count(SalesContract.id),
            )
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .filter(SalesContract.status.notin_(["cancelled"]))
            .one()
        )
        first_date, last_date, count = row
        if first_date is None or last_date is None or count < 2:
            return None
        return (first_date, last_date, count)

    # ------------------------------------------------------------------
    # Feasibility inputs (for planned absorption rate)
    # ------------------------------------------------------------------

    def get_feasibility_inputs_for_project(
        self, project_id: str
    ) -> Optional[Tuple]:
        """Return (FeasibilityResult, FeasibilityAssumptions) for the most recent
        calculated feasibility run for a project.

        Returns None when no calculated feasibility run exists.
        """
        latest_run = (
            self.db.query(FeasibilityRun)
            .filter(FeasibilityRun.project_id == project_id)
            .filter(FeasibilityRun.status == "calculated")
            .order_by(FeasibilityRun.created_at.desc())
            .first()
        )
        if latest_run is None:
            return None

        feas_result = (
            self.db.query(FeasibilityResult)
            .filter(FeasibilityResult.run_id == latest_run.id)
            .first()
        )
        feas_assumptions = (
            self.db.query(FeasibilityAssumptions)
            .filter(FeasibilityAssumptions.run_id == latest_run.id)
            .first()
        )
        return (feas_result, feas_assumptions)

    # ------------------------------------------------------------------
    # Bulk portfolio helpers (avoids N+1 in build_portfolio_pricing_insights)
    # ------------------------------------------------------------------

    def get_unit_type_status_counts_by_project(
        self,
    ) -> Dict[str, Dict[str, Dict[str, int]]]:
        """Return project_id → unit_type → status → count for all projects.

        Single query to avoid N+1 when building portfolio pricing insights.
        """
        rows = (
            self.db.query(
                Phase.project_id,
                Unit.unit_type,
                Unit.status,
                func.count(Unit.id),
            )
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .group_by(Phase.project_id, Unit.unit_type, Unit.status)
            .all()
        )
        result: Dict[str, Dict[str, Dict[str, int]]] = {}
        for project_id, unit_type, status, count in rows:
            result.setdefault(project_id, {}).setdefault(unit_type, {})[status] = count
        return result

    def get_avg_price_by_unit_type_by_project(
        self,
    ) -> Dict[str, Dict[str, float]]:
        """Return project_id → unit_type → avg_price for all projects.

        Single query to avoid N+1 when building portfolio pricing insights.
        Only includes unit types with active (non-archived) pricing records.
        """
        rows = (
            self.db.query(
                Phase.project_id,
                Unit.unit_type,
                func.avg(UnitPricing.final_price),
            )
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .join(UnitPricing, UnitPricing.unit_id == Unit.id)
            .filter(UnitPricing.pricing_status.notin_(["archived"]))
            .group_by(Phase.project_id, Unit.unit_type)
            .all()
        )
        result: Dict[str, Dict[str, float]] = {}
        for project_id, unit_type, avg_price in rows:
            if avg_price is not None:
                result.setdefault(project_id, {})[unit_type] = float(avg_price)
        return result

    def get_contract_date_bounds_by_project(
        self,
    ) -> Dict[str, Tuple]:
        """Return project_id → (min_date, max_date, count) for all projects.

        Single query to avoid N+1 when building portfolio pricing insights.
        Projects with < 2 non-cancelled contracts are excluded.
        """
        rows = (
            self.db.query(
                Phase.project_id,
                func.min(SalesContract.contract_date),
                func.max(SalesContract.contract_date),
                func.count(SalesContract.id),
            )
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(SalesContract.status.notin_(["cancelled"]))
            .group_by(Phase.project_id)
            .all()
        )
        return {
            project_id: (first_date, last_date, count)
            for project_id, first_date, last_date, count in rows
            if first_date is not None and last_date is not None and count >= 2
        }

    def get_feasibility_inputs_by_project(
        self,
    ) -> Dict[str, Tuple]:
        """Return project_id → (FeasibilityResult, FeasibilityAssumptions) for
        the most recent calculated run per project, in a minimal number of queries.

        Uses a subquery to find the latest calculated run per project.
        """
        # Subquery: latest created_at per project for calculated runs
        latest_run_subq = (
            self.db.query(
                FeasibilityRun.project_id,
                func.max(FeasibilityRun.created_at).label("max_created_at"),
            )
            .filter(FeasibilityRun.project_id.isnot(None))
            .filter(FeasibilityRun.status == "calculated")
            .group_by(FeasibilityRun.project_id)
            .subquery()
        )

        rows = (
            self.db.query(FeasibilityRun, FeasibilityResult, FeasibilityAssumptions)
            .join(
                latest_run_subq,
                (FeasibilityRun.project_id == latest_run_subq.c.project_id)
                & (FeasibilityRun.created_at == latest_run_subq.c.max_created_at),
            )
            .outerjoin(FeasibilityResult, FeasibilityResult.run_id == FeasibilityRun.id)
            .outerjoin(
                FeasibilityAssumptions, FeasibilityAssumptions.run_id == FeasibilityRun.id
            )
            .filter(FeasibilityRun.status == "calculated")
            .all()
        )

        result: Dict[str, Tuple] = {}
        for run, feas_result, feas_assumptions in rows:
            if run.project_id:
                result[run.project_id] = (feas_result, feas_assumptions)
        return result
