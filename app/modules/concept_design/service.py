"""
concept_design.service

Application-layer orchestration for the Concept Design module.

Coordinates repository access and concept engine computation.
Raises domain errors (ResourceNotFoundError) that the central error
handler translates into HTTP responses.

PR-CONCEPT-052
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError
from app.core.logging import get_logger
from app.modules.concept_design.engine import MixLineInput, run_concept_engine
from app.modules.concept_design.repository import (
    ConceptOptionRepository,
    ConceptUnitMixLineRepository,
)
from app.modules.concept_design.schemas import (
    ConceptOptionCreate,
    ConceptOptionListResponse,
    ConceptOptionResponse,
    ConceptOptionSummaryResponse,
    ConceptOptionUpdate,
    ConceptUnitMixLineCreate,
    ConceptUnitMixLineResponse,
)
from app.modules.projects.repository import ProjectRepository
from app.modules.scenario.repository import ScenarioRepository

_logger = get_logger("reach_developments.concept_design")


class ConceptDesignService:
    def __init__(self, db: Session) -> None:
        self.option_repo = ConceptOptionRepository(db)
        self.mix_repo = ConceptUnitMixLineRepository(db)
        self.project_repo = ProjectRepository(db)
        self.scenario_repo = ScenarioRepository(db)

    # ------------------------------------------------------------------
    # Linked-resource validators
    # ------------------------------------------------------------------

    def _validate_project_if_present(self, project_id: Optional[str]) -> None:
        """Raise ResourceNotFoundError if project_id is provided but does not exist."""
        if project_id is not None:
            project = self.project_repo.get_by_id(project_id)
            if not project:
                raise ResourceNotFoundError(
                    f"Project '{project_id}' not found.",
                    details={"project_id": project_id},
                )

    def _validate_scenario_if_present(self, scenario_id: Optional[str]) -> None:
        """Raise ResourceNotFoundError if scenario_id is provided but does not exist."""
        if scenario_id is not None:
            scenario = self.scenario_repo.get_by_id(scenario_id)
            if not scenario:
                raise ResourceNotFoundError(
                    f"Scenario '{scenario_id}' not found.",
                    details={"scenario_id": scenario_id},
                )

    # ------------------------------------------------------------------
    # ConceptOption CRUD
    # ------------------------------------------------------------------

    def create_concept_option(self, data: ConceptOptionCreate) -> ConceptOptionResponse:
        self._validate_project_if_present(data.project_id)
        self._validate_scenario_if_present(data.scenario_id)
        option = self.option_repo.create(data)
        _logger.info("ConceptOption created id=%s name=%r", option.id, option.name)
        return ConceptOptionResponse.model_validate(option)

    def get_concept_option(self, concept_option_id: str) -> ConceptOptionResponse:
        option = self.option_repo.get_by_id(concept_option_id)
        if option is None:
            raise ResourceNotFoundError(
                f"ConceptOption '{concept_option_id}' not found."
            )
        return ConceptOptionResponse.model_validate(option)

    def list_concept_options(
        self,
        project_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> ConceptOptionListResponse:
        items = self.option_repo.list(
            project_id=project_id,
            scenario_id=scenario_id,
            skip=skip,
            limit=limit,
        )
        total = self.option_repo.count(
            project_id=project_id, scenario_id=scenario_id
        )
        return ConceptOptionListResponse(
            items=[ConceptOptionResponse.model_validate(o) for o in items],
            total=total,
        )

    def update_concept_option(
        self, concept_option_id: str, data: ConceptOptionUpdate
    ) -> ConceptOptionResponse:
        option = self.option_repo.get_by_id(concept_option_id)
        if option is None:
            raise ResourceNotFoundError(
                f"ConceptOption '{concept_option_id}' not found."
            )
        option = self.option_repo.update(option, data)
        return ConceptOptionResponse.model_validate(option)

    # ------------------------------------------------------------------
    # Unit mix
    # ------------------------------------------------------------------

    def add_concept_mix_line(
        self, concept_option_id: str, data: ConceptUnitMixLineCreate
    ) -> ConceptUnitMixLineResponse:
        option = self.option_repo.get_by_id(concept_option_id)
        if option is None:
            raise ResourceNotFoundError(
                f"ConceptOption '{concept_option_id}' not found."
            )
        line = self.mix_repo.add(concept_option_id, data)
        return ConceptUnitMixLineResponse.model_validate(line)

    # ------------------------------------------------------------------
    # Summary (option + derived metrics)
    # ------------------------------------------------------------------

    def get_concept_option_summary(
        self, concept_option_id: str
    ) -> ConceptOptionSummaryResponse:
        option = self.option_repo.get_by_id_with_mix(concept_option_id)
        if option is None:
            raise ResourceNotFoundError(
                f"ConceptOption '{concept_option_id}' not found."
            )

        mix_inputs = [
            MixLineInput(
                unit_type=line.unit_type,
                units_count=line.units_count,
                avg_sellable_area=(
                    float(line.avg_sellable_area)
                    if line.avg_sellable_area is not None
                    else None
                ),
            )
            for line in option.mix_lines
        ]

        metrics = run_concept_engine(
            mix_lines=mix_inputs,
            gross_floor_area=(
                float(option.gross_floor_area)
                if option.gross_floor_area is not None
                else None
            ),
        )

        return ConceptOptionSummaryResponse(
            concept_option_id=option.id,
            name=option.name,
            status=option.status,
            project_id=option.project_id,
            scenario_id=option.scenario_id,
            site_area=(
                float(option.site_area) if option.site_area is not None else None
            ),
            gross_floor_area=(
                float(option.gross_floor_area)
                if option.gross_floor_area is not None
                else None
            ),
            building_count=option.building_count,
            floor_count=option.floor_count,
            unit_count=metrics.unit_count,
            sellable_area=metrics.sellable_area,
            efficiency_ratio=metrics.efficiency_ratio,
            average_unit_area=metrics.average_unit_area,
            mix_lines=[
                ConceptUnitMixLineResponse.model_validate(line)
                for line in option.mix_lines
            ],
        )
