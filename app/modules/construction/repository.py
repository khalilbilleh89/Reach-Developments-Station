"""
construction.repository

Data access layer for the Construction domain.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.construction.models import (
    ConstructionEngineeringItem,
    ConstructionMilestone,
    ConstructionProgressUpdate,
    ConstructionScope,
)
from app.modules.construction.schemas import (
    ConstructionMilestoneCreate,
    ConstructionMilestoneUpdate,
    ConstructionScopeCreate,
    ConstructionScopeUpdate,
    EngineeringItemCreate,
    EngineeringItemUpdate,
    ProgressUpdateCreate,
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


class ConstructionEngineeringItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, scope_id: str, data: EngineeringItemCreate) -> ConstructionEngineeringItem:
        item = ConstructionEngineeringItem(scope_id=scope_id, **data.model_dump())
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_by_id(self, item_id: str) -> Optional[ConstructionEngineeringItem]:
        return (
            self.db.query(ConstructionEngineeringItem)
            .filter(ConstructionEngineeringItem.id == item_id)
            .first()
        )

    def list(
        self,
        scope_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConstructionEngineeringItem]:
        return (
            self.db.query(ConstructionEngineeringItem)
            .filter(ConstructionEngineeringItem.scope_id == scope_id)
            .order_by(ConstructionEngineeringItem.created_at, ConstructionEngineeringItem.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, scope_id: str) -> int:
        return (
            self.db.query(ConstructionEngineeringItem)
            .filter(ConstructionEngineeringItem.scope_id == scope_id)
            .count()
        )

    def update(
        self, item: ConstructionEngineeringItem, data: EngineeringItemUpdate
    ) -> ConstructionEngineeringItem:
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in update_data.items():
            setattr(item, field, value)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item: ConstructionEngineeringItem) -> None:
        self.db.delete(item)
        self.db.commit()


class ConstructionProgressUpdateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, milestone_id: str, data: ProgressUpdateCreate) -> ConstructionProgressUpdate:
        from datetime import datetime, timezone

        raw = data.reported_at
        if raw is None:
            reported_at = datetime.now(timezone.utc)
        elif raw.tzinfo is None:
            reported_at = raw.replace(tzinfo=timezone.utc)
        else:
            reported_at = raw.astimezone(timezone.utc)
        update = ConstructionProgressUpdate(
            milestone_id=milestone_id,
            progress_percent=data.progress_percent,
            status_note=data.status_note,
            reported_by=data.reported_by,
            reported_at=reported_at,
        )
        self.db.add(update)
        self.db.commit()
        self.db.refresh(update)
        return update

    def get_by_id(self, update_id: str) -> Optional[ConstructionProgressUpdate]:
        return (
            self.db.query(ConstructionProgressUpdate)
            .filter(ConstructionProgressUpdate.id == update_id)
            .first()
        )

    def list(
        self,
        milestone_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConstructionProgressUpdate]:
        return (
            self.db.query(ConstructionProgressUpdate)
            .filter(ConstructionProgressUpdate.milestone_id == milestone_id)
            .order_by(ConstructionProgressUpdate.reported_at, ConstructionProgressUpdate.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, milestone_id: str) -> int:
        return (
            self.db.query(ConstructionProgressUpdate)
            .filter(ConstructionProgressUpdate.milestone_id == milestone_id)
            .count()
        )

    def delete(self, update: ConstructionProgressUpdate) -> None:
        self.db.delete(update)
        self.db.commit()
