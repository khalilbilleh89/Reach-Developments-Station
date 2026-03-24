"""
concept_design.repository

Data access layer for ConceptOption and ConceptUnitMixLine entities.

PR-CONCEPT-052
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session, selectinload

from app.modules.concept_design.models import ConceptOption, ConceptUnitMixLine
from app.modules.concept_design.schemas import (
    ConceptOptionCreate,
    ConceptOptionUpdate,
    ConceptUnitMixLineCreate,
)


class ConceptOptionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: ConceptOptionCreate) -> ConceptOption:
        option = ConceptOption(
            project_id=data.project_id,
            scenario_id=data.scenario_id,
            name=data.name,
            status=data.status,
            description=data.description,
            site_area=data.site_area,
            gross_floor_area=data.gross_floor_area,
            building_count=data.building_count,
            floor_count=data.floor_count,
        )
        self.db.add(option)
        self.db.commit()
        self.db.refresh(option)
        return option

    def get_by_id(self, concept_option_id: str) -> Optional[ConceptOption]:
        return (
            self.db.query(ConceptOption)
            .filter(ConceptOption.id == concept_option_id)
            .first()
        )

    def get_by_id_with_mix(self, concept_option_id: str) -> Optional[ConceptOption]:
        return (
            self.db.query(ConceptOption)
            .options(selectinload(ConceptOption.mix_lines))
            .filter(ConceptOption.id == concept_option_id)
            .first()
        )

    def list(
        self,
        project_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConceptOption]:
        query = self.db.query(ConceptOption)
        if project_id is not None:
            query = query.filter(ConceptOption.project_id == project_id)
        if scenario_id is not None:
            query = query.filter(ConceptOption.scenario_id == scenario_id)
        return (
            query.order_by(ConceptOption.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(
        self,
        project_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
    ) -> int:
        query = self.db.query(ConceptOption)
        if project_id is not None:
            query = query.filter(ConceptOption.project_id == project_id)
        if scenario_id is not None:
            query = query.filter(ConceptOption.scenario_id == scenario_id)
        return query.count()

    def update(self, option: ConceptOption, data: ConceptOptionUpdate) -> ConceptOption:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(option, field, value)
        self.db.commit()
        self.db.refresh(option)
        return option


class ConceptUnitMixLineRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self, concept_option_id: str, data: ConceptUnitMixLineCreate
    ) -> ConceptUnitMixLine:
        line = ConceptUnitMixLine(
            concept_option_id=concept_option_id,
            unit_type=data.unit_type,
            units_count=data.units_count,
            avg_internal_area=data.avg_internal_area,
            avg_sellable_area=data.avg_sellable_area,
            mix_percentage=data.mix_percentage,
        )
        self.db.add(line)
        self.db.commit()
        self.db.refresh(line)
        return line

    def list_for_option(self, concept_option_id: str) -> List[ConceptUnitMixLine]:
        return (
            self.db.query(ConceptUnitMixLine)
            .filter(ConceptUnitMixLine.concept_option_id == concept_option_id)
            .order_by(ConceptUnitMixLine.unit_type.asc())
            .all()
        )
