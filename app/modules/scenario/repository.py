"""
scenario.repository

Data access layer for Scenario and ScenarioVersion entities.

Business rules and cross-module concerns must not live here.
"""

from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.scenario.models import Scenario, ScenarioVersion
from app.modules.scenario.schemas import ScenarioCreate, ScenarioVersionCreate


class ScenarioRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: ScenarioCreate, base_scenario_id: Optional[str] = None) -> Scenario:
        scenario = Scenario(
            name=data.name,
            code=data.code,
            source_type=data.source_type,
            project_id=data.project_id,
            land_id=data.land_id,
            base_scenario_id=base_scenario_id,
            notes=data.notes,
        )
        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def get_by_id(self, scenario_id: str) -> Optional[Scenario]:
        return self.db.query(Scenario).filter(Scenario.id == scenario_id).first()

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        source_type: Optional[str] = None,
        project_id: Optional[str] = None,
        land_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Scenario]:
        q = self.db.query(Scenario)
        if source_type is not None:
            q = q.filter(Scenario.source_type == source_type)
        if project_id is not None:
            q = q.filter(Scenario.project_id == project_id)
        if land_id is not None:
            q = q.filter(Scenario.land_id == land_id)
        if status is not None:
            q = q.filter(Scenario.status == status)
        return q.order_by(Scenario.created_at.asc()).offset(skip).limit(limit).all()

    def count_all(
        self,
        source_type: Optional[str] = None,
        project_id: Optional[str] = None,
        land_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        q = self.db.query(Scenario)
        if source_type is not None:
            q = q.filter(Scenario.source_type == source_type)
        if project_id is not None:
            q = q.filter(Scenario.project_id == project_id)
        if land_id is not None:
            q = q.filter(Scenario.land_id == land_id)
        if status is not None:
            q = q.filter(Scenario.status == status)
        return q.count()

    def update_status(self, scenario: Scenario, status: str) -> Scenario:
        scenario.status = status
        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def update_fields(self, scenario: Scenario, **kwargs: object) -> Scenario:
        for field, value in kwargs.items():
            setattr(scenario, field, value)
        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def mark_approved(self, scenario: Scenario) -> None:
        """Set status to 'approved'. Does NOT commit — caller coordinates the commit."""
        scenario.status = "approved"

    def get_by_ids(self, scenario_ids: List[str]) -> List[Scenario]:
        return self.db.query(Scenario).filter(Scenario.id.in_(scenario_ids)).all()


class ScenarioVersionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def next_version_number(self, scenario_id: str) -> int:
        """Return the next version number for a given scenario (1-based).

        Derived from MAX(version_number) + 1 rather than COUNT(*) + 1 so that
        gaps caused by deletions never produce duplicate version numbers.
        """
        max_num = (
            self.db.query(func.max(ScenarioVersion.version_number))
            .filter(ScenarioVersion.scenario_id == scenario_id)
            .scalar()
        )
        return 1 if max_num is None else max_num + 1

    def create(self, scenario_id: str, data: ScenarioVersionCreate, created_by: Optional[str] = None) -> ScenarioVersion:
        version_number = self.next_version_number(scenario_id)
        version = ScenarioVersion(
            scenario_id=scenario_id,
            version_number=version_number,
            title=data.title,
            notes=data.notes,
            assumptions_json=data.assumptions_json,
            comparison_metrics_json=data.comparison_metrics_json,
            created_by=created_by,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def get_by_id(self, version_id: str) -> Optional[ScenarioVersion]:
        return self.db.query(ScenarioVersion).filter(ScenarioVersion.id == version_id).first()

    def get_latest(self, scenario_id: str) -> Optional[ScenarioVersion]:
        return (
            self.db.query(ScenarioVersion)
            .filter(ScenarioVersion.scenario_id == scenario_id)
            .order_by(ScenarioVersion.version_number.desc())
            .first()
        )

    def list_by_scenario(self, scenario_id: str) -> List[ScenarioVersion]:
        return (
            self.db.query(ScenarioVersion)
            .filter(ScenarioVersion.scenario_id == scenario_id)
            .order_by(ScenarioVersion.version_number.asc())
            .all()
        )

    def count_by_scenario(self, scenario_id: str) -> int:
        return (
            self.db.query(ScenarioVersion)
            .filter(ScenarioVersion.scenario_id == scenario_id)
            .count()
        )

    def clear_approved(self, scenario_id: str) -> None:
        """Remove approval flag from all versions of a scenario."""
        self.db.query(ScenarioVersion).filter(
            ScenarioVersion.scenario_id == scenario_id,
            ScenarioVersion.is_approved.is_(True),
        ).update({"is_approved": False})
        self.db.commit()

    def set_approved(self, version: ScenarioVersion) -> ScenarioVersion:
        version.is_approved = True
        self.db.commit()
        self.db.refresh(version)
        return version

    def approve_latest(self, scenario_id: str) -> Optional[ScenarioVersion]:
        """Clear all approvals for the scenario and mark the latest version as approved.

        Does NOT commit — the caller coordinates with other repository mutations
        and issues the single commit to keep the full approval transition atomic.

        Returns the newly approved version, or None if no versions exist.
        """
        self.db.query(ScenarioVersion).filter(
            ScenarioVersion.scenario_id == scenario_id,
            ScenarioVersion.is_approved.is_(True),
        ).update({"is_approved": False})
        latest = self.get_latest(scenario_id)
        if latest is not None:
            latest.is_approved = True
        return latest

    def get_latest_for_ids(self, scenario_ids: List[str]) -> Dict[str, ScenarioVersion]:
        """Fetch the latest version for each scenario_id in a single query.

        Returns a dict keyed by scenario_id.  Scenarios with no versions are
        absent from the result.  This eliminates the N+1 query pattern in
        compare_scenarios().
        """
        if not scenario_ids:
            return {}
        sub = (
            self.db.query(
                ScenarioVersion.scenario_id,
                func.max(ScenarioVersion.version_number).label("max_ver"),
            )
            .filter(ScenarioVersion.scenario_id.in_(scenario_ids))
            .group_by(ScenarioVersion.scenario_id)
            .subquery()
        )
        versions = (
            self.db.query(ScenarioVersion)
            .join(
                sub,
                (ScenarioVersion.scenario_id == sub.c.scenario_id)
                & (ScenarioVersion.version_number == sub.c.max_ver),
            )
            .all()
        )
        return {v.scenario_id: v for v in versions}
