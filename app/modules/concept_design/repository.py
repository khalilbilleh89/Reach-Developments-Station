"""
concept_design.repository

Data access layer for ConceptOption and ConceptUnitMixLine entities.

PR-CONCEPT-052, PR-CONCEPT-054
"""

from __future__ import annotations

from datetime import datetime
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

    def list_by_project_id(self, project_id: str) -> List[ConceptOption]:
        """Return all concept options for a project, with mix lines eagerly loaded."""
        return (
            self.db.query(ConceptOption)
            .options(selectinload(ConceptOption.mix_lines))
            .filter(ConceptOption.project_id == project_id)
            .order_by(ConceptOption.id.asc())
            .all()
        )

    def list_by_scenario_id(self, scenario_id: str) -> List[ConceptOption]:
        """Return all concept options for a scenario, with mix lines eagerly loaded."""
        return (
            self.db.query(ConceptOption)
            .options(selectinload(ConceptOption.mix_lines))
            .filter(ConceptOption.scenario_id == scenario_id)
            .order_by(ConceptOption.id.asc())
            .all()
        )

    def update(self, option: ConceptOption, data: ConceptOptionUpdate) -> ConceptOption:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(option, field, value)
        self.db.commit()
        self.db.refresh(option)
        return option

    def update_promotion_fields(
        self,
        option: ConceptOption,
        promoted_project_id: str,
        promoted_at: datetime,
        promotion_notes: Optional[str],
    ) -> ConceptOption:
        """Persist promotion metadata on the concept option."""
        option.is_promoted = True
        option.promoted_project_id = promoted_project_id
        option.promoted_at = promoted_at
        option.promotion_notes = promotion_notes
        self.db.commit()
        self.db.refresh(option)
        return option

    def apply_promotion_fields(
        self,
        option: ConceptOption,
        promoted_project_id: str,
        promoted_at: datetime,
        promotion_notes: Optional[str],
    ) -> None:
        """Stage promotion metadata on the concept option without committing."""
        option.is_promoted = True
        option.promoted_project_id = promoted_project_id
        option.promoted_at = promoted_at
        option.promotion_notes = promotion_notes

    def delete(self, option: ConceptOption) -> None:
        """Delete a concept option and its unit mix lines (cascade) and commit."""
        self.db.delete(option)
        self.db.commit()

    def get_names_in_scope(
        self,
        project_id: Optional[str],
        scenario_id: Optional[str],
    ) -> set[str]:
        """Return the set of all concept option names within the given scope.

        Used by the duplication service to check name uniqueness without
        loading full ORM objects or imposing an arbitrary row limit.

        Both project_id and scenario_id are matched exactly — None is treated
        as IS NULL so that unscoped options do not bleed into project/scenario
        scopes and vice versa.
        """
        query = self.db.query(ConceptOption.name)
        if project_id is not None:
            query = query.filter(ConceptOption.project_id == project_id)
        else:
            query = query.filter(ConceptOption.project_id.is_(None))
        if scenario_id is not None:
            query = query.filter(ConceptOption.scenario_id == scenario_id)
        else:
            query = query.filter(ConceptOption.scenario_id.is_(None))
        return {row[0] for row in query.all()}

    def clone_concept_option(self, source: ConceptOption, new_name: str) -> ConceptOption:
        """Stage a copy of *source* with *new_name* and flush to obtain an id.

        The caller is responsible for committing after all related clone
        operations (e.g. unit mix lines) have been staged.

        Promotion metadata (is_promoted, promoted_at, promoted_project_id,
        promotion_notes) is intentionally NOT copied so the clone starts as a
        fresh, unpromoted concept option.
        """
        clone = ConceptOption(
            project_id=source.project_id,
            scenario_id=source.scenario_id,
            name=new_name,
            status=source.status,
            description=source.description,
            site_area=source.site_area,
            gross_floor_area=source.gross_floor_area,
            building_count=source.building_count,
            floor_count=source.floor_count,
        )
        self.db.add(clone)
        self.db.flush()
        return clone


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

    def clone_for_option(
        self, source_lines: List[ConceptUnitMixLine], new_option_id: str
    ) -> None:
        """Stage copies of *source_lines* for *new_option_id*.

        The caller is responsible for committing after all related clone
        operations have been staged.
        """
        for line in source_lines:
            self.db.add(
                ConceptUnitMixLine(
                    concept_option_id=new_option_id,
                    unit_type=line.unit_type,
                    units_count=line.units_count,
                    avg_internal_area=line.avg_internal_area,
                    avg_sellable_area=line.avg_sellable_area,
                    mix_percentage=line.mix_percentage,
                )
            )
