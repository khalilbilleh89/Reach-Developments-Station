"""
scenario.repository

Data access layer for Scenario and ScenarioVersion entities.

Business rules and cross-module concerns must not live here.
"""

from typing import List, Optional

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

    def get_by_ids(self, scenario_ids: List[str]) -> List[Scenario]:
        return self.db.query(Scenario).filter(Scenario.id.in_(scenario_ids)).all()


class ScenarioVersionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def next_version_number(self, scenario_id: str) -> int:
        """Return the next version number for a given scenario (1-based)."""
        existing = (
            self.db.query(ScenarioVersion)
            .filter(ScenarioVersion.scenario_id == scenario_id)
            .count()
        )
        return existing + 1

    def create(self, scenario_id: str, data: ScenarioVersionCreate) -> ScenarioVersion:
        version_number = self.next_version_number(scenario_id)
        version = ScenarioVersion(
            scenario_id=scenario_id,
            version_number=version_number,
            title=data.title,
            notes=data.notes,
            assumptions_json=data.assumptions_json,
            comparison_metrics_json=data.comparison_metrics_json,
            created_by=data.created_by,
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
