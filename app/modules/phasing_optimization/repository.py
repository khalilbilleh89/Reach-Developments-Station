"""
phasing_optimization.repository

Read-only data access for phasing optimization intelligence.

Queries project phases, unit inventory by phase, contract dates, feasibility
data, and approved baseline status needed to generate phasing recommendations.

All methods are read-only — no phase or source records are mutated.
"""

from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.feasibility.models import FeasibilityAssumptions, FeasibilityResult, FeasibilityRun
from app.modules.floors.models import Floor
from app.modules.phases.models import Phase
from app.modules.projects.models import Project
from app.modules.sales.models import SalesContract
from app.modules.tender_comparison.models import ConstructionCostComparisonSet
from app.modules.units.models import Unit


class PhasingOptimizationRepository:
    """Read-only repository for phasing optimization data access."""

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
    # Phase helpers (per project)
    # ------------------------------------------------------------------

    def get_phases_for_project(self, project_id: str) -> List[Phase]:
        """Return all phases for a project ordered by sequence ascending."""
        return (
            self.db.query(Phase)
            .filter(Phase.project_id == project_id)
            .order_by(Phase.sequence)
            .all()
        )

    # ------------------------------------------------------------------
    # Unit counts by phase (per project)
    # ------------------------------------------------------------------

    def get_unit_counts_by_phase_for_project(
        self, project_id: str
    ) -> Dict[str, Dict[str, int]]:
        """Return per-phase unit status counts for a single project.

        Returns {phase_id: {status: count}}.
        """
        rows = (
            self.db.query(Phase.id, Unit.status, func.count(Unit.id))
            .join(Building, Building.phase_id == Phase.id)
            .join(Floor, Floor.building_id == Building.id)
            .join(Unit, Unit.floor_id == Floor.id)
            .filter(Phase.project_id == project_id)
            .group_by(Phase.id, Unit.status)
            .all()
        )
        result: Dict[str, Dict[str, int]] = {}
        for phase_id, status, count in rows:
            result.setdefault(phase_id, {})[status] = count
        return result

    # ------------------------------------------------------------------
    # Contract date helpers (for absorption velocity)
    # ------------------------------------------------------------------

    def get_contract_date_bounds_for_project(
        self, project_id: str
    ) -> Optional[Tuple]:
        """Return (min_contract_date, max_contract_date, contract_count) for a project.

        Returns None when the project has no non-cancelled contracts or has < 2 contracts.
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
    # Approved baseline flag (project readiness signal)
    # ------------------------------------------------------------------

    def has_approved_baseline(self, project_id: str) -> bool:
        """Return True when the project has at least one approved tender baseline."""
        return (
            self.db.query(ConstructionCostComparisonSet)
            .filter(ConstructionCostComparisonSet.project_id == project_id)
            .filter(ConstructionCostComparisonSet.is_approved_baseline.is_(True))
            .limit(1)
            .count()
            > 0
        )

    # ------------------------------------------------------------------
    # Bulk portfolio helpers (avoids N+1 in build_portfolio_phasing_insights)
    # ------------------------------------------------------------------

    def get_phases_by_project(self) -> Dict[str, List[Phase]]:
        """Return project_id -> [Phase...] (ordered by sequence) for all projects.

        Single query to avoid N+1 when building portfolio phasing insights.
        """
        phases = self.db.query(Phase).order_by(Phase.project_id, Phase.sequence).all()
        result: Dict[str, List[Phase]] = {}
        for phase in phases:
            result.setdefault(phase.project_id, []).append(phase)
        return result

    def get_unit_counts_by_phase_by_project(
        self,
    ) -> Dict[str, Dict[str, Dict[str, int]]]:
        """Return project_id -> phase_id -> status -> count for all projects.

        Single query to avoid N+1 when building portfolio phasing insights.
        """
        rows = (
            self.db.query(
                Phase.project_id,
                Phase.id,
                Unit.status,
                func.count(Unit.id),
            )
            .join(Building, Building.phase_id == Phase.id)
            .join(Floor, Floor.building_id == Building.id)
            .join(Unit, Unit.floor_id == Floor.id)
            .group_by(Phase.project_id, Phase.id, Unit.status)
            .all()
        )
        result: Dict[str, Dict[str, Dict[str, int]]] = {}
        for project_id, phase_id, status, count in rows:
            result.setdefault(project_id, {}).setdefault(phase_id, {})[status] = count
        return result

    def get_contract_date_bounds_by_project(
        self,
    ) -> Dict[str, Tuple]:
        """Return project_id -> (min_date, max_date, count) for all projects.

        Single query to avoid N+1 when building portfolio phasing insights.
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
        """Return project_id -> (FeasibilityResult, FeasibilityAssumptions) for
        the most recent calculated run per project, in a minimal number of queries.
        """
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

    def get_approved_baseline_flags(self) -> Dict[str, bool]:
        """Return project_id -> True for projects with an approved tender baseline.

        Single query to avoid N+1 when building portfolio phasing insights.
        Only projects that have at least one approved baseline appear in the dict.
        """
        rows = (
            self.db.query(ConstructionCostComparisonSet.project_id)
            .filter(ConstructionCostComparisonSet.is_approved_baseline.is_(True))
            .distinct()
            .all()
        )
        return {row[0]: True for row in rows if row[0] is not None}
