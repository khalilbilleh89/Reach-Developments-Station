"""
construction.repository

Data access layer for the Construction domain.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.construction.models import ConstructionMilestone, ConstructionScope
from app.modules.construction.schemas import (
    ConstructionMilestoneCreate,
    ConstructionMilestoneUpdate,
    ConstructionScopeCreate,
    ConstructionScopeUpdate,
)


class ConstructionScopeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: ConstructionScopeCreate) -> ConstructionScope:
        scope = ConstructionScope(**data.model_dump())
        self.db.add(scope)
        self.db.commit()
        self.db.refresh(scope)
        return scope

    def get_by_id(self, scope_id: str) -> Optional[ConstructionScope]:
        return (
            self.db.query(ConstructionScope)
            .filter(ConstructionScope.id == scope_id)
            .first()
        )

    def get_by_links(
        self,
        project_id: Optional[str],
        phase_id: Optional[str],
        building_id: Optional[str],
    ) -> Optional[ConstructionScope]:
        """Return an existing scope matching the given link combination."""
        return (
            self.db.query(ConstructionScope)
            .filter(
                ConstructionScope.project_id == project_id,
                ConstructionScope.phase_id == phase_id,
                ConstructionScope.building_id == building_id,
            )
            .first()
        )

    def list(
        self,
        project_id: Optional[str] = None,
        phase_id: Optional[str] = None,
        building_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConstructionScope]:
        query = self.db.query(ConstructionScope)
        if project_id:
            query = query.filter(ConstructionScope.project_id == project_id)
        if phase_id:
            query = query.filter(ConstructionScope.phase_id == phase_id)
        if building_id:
            query = query.filter(ConstructionScope.building_id == building_id)
        return query.order_by(ConstructionScope.name, ConstructionScope.id).offset(skip).limit(limit).all()

    def count(
        self,
        project_id: Optional[str] = None,
        phase_id: Optional[str] = None,
        building_id: Optional[str] = None,
    ) -> int:
        query = self.db.query(ConstructionScope)
        if project_id:
            query = query.filter(ConstructionScope.project_id == project_id)
        if phase_id:
            query = query.filter(ConstructionScope.phase_id == phase_id)
        if building_id:
            query = query.filter(ConstructionScope.building_id == building_id)
        return query.count()

    def update(self, scope: ConstructionScope, data: ConstructionScopeUpdate) -> ConstructionScope:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(scope, field, value)
        self.db.commit()
        self.db.refresh(scope)
        return scope

    def delete(self, scope: ConstructionScope) -> None:
        self.db.delete(scope)
        self.db.commit()


class ConstructionMilestoneRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: ConstructionMilestoneCreate) -> ConstructionMilestone:
        milestone = ConstructionMilestone(**data.model_dump())
        self.db.add(milestone)
        self.db.commit()
        self.db.refresh(milestone)
        return milestone

    def get_by_id(self, milestone_id: str) -> Optional[ConstructionMilestone]:
        return (
            self.db.query(ConstructionMilestone)
            .filter(ConstructionMilestone.id == milestone_id)
            .first()
        )

    def get_by_scope_and_sequence(self, scope_id: str, sequence: int) -> Optional[ConstructionMilestone]:
        return (
            self.db.query(ConstructionMilestone)
            .filter(
                ConstructionMilestone.scope_id == scope_id,
                ConstructionMilestone.sequence == sequence,
            )
            .first()
        )

    def list(
        self,
        scope_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConstructionMilestone]:
        query = self.db.query(ConstructionMilestone)
        if scope_id:
            query = query.filter(ConstructionMilestone.scope_id == scope_id)
        return query.order_by(ConstructionMilestone.scope_id, ConstructionMilestone.sequence).offset(skip).limit(limit).all()

    def count(self, scope_id: Optional[str] = None) -> int:
        query = self.db.query(ConstructionMilestone)
        if scope_id:
            query = query.filter(ConstructionMilestone.scope_id == scope_id)
        return query.count()

    def update(self, milestone: ConstructionMilestone, data: ConstructionMilestoneUpdate) -> ConstructionMilestone:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(milestone, field, value)
        self.db.commit()
        self.db.refresh(milestone)
        return milestone

    def delete(self, milestone: ConstructionMilestone) -> None:
        self.db.delete(milestone)
        self.db.commit()
