"""
phases.repository

Data access layer for the Phase entity.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.phases.models import Phase
from app.modules.phases.schemas import PhaseCreate, PhaseUpdate


class PhaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: PhaseCreate) -> Phase:
        phase = Phase(**data.model_dump())
        self.db.add(phase)
        self.db.commit()
        self.db.refresh(phase)
        return phase

    def get_by_id(self, phase_id: str) -> Optional[Phase]:
        return self.db.query(Phase).filter(Phase.id == phase_id).first()

    def get_by_project_and_sequence(self, project_id: str, sequence: int) -> Optional[Phase]:
        return (
            self.db.query(Phase)
            .filter(Phase.project_id == project_id, Phase.sequence == sequence)
            .first()
        )

    def list(self, project_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Phase]:
        query = self.db.query(Phase)
        if project_id:
            query = query.filter(Phase.project_id == project_id)
        return query.order_by(Phase.sequence).offset(skip).limit(limit).all()

    def count(self, project_id: Optional[str] = None) -> int:
        query = self.db.query(Phase)
        if project_id:
            query = query.filter(Phase.project_id == project_id)
        return query.count()

    def update(self, phase: Phase, data: PhaseUpdate) -> Phase:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(phase, field, value)
        self.db.commit()
        self.db.refresh(phase)
        return phase

    def delete(self, phase: Phase) -> None:
        self.db.delete(phase)
        self.db.commit()
