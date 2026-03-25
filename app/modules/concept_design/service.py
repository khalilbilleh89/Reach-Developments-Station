"""
concept_design.service

Application-layer orchestration for the Concept Design module.

Coordinates repository access and concept engine computation.
Raises domain errors (ResourceNotFoundError) that the central error
handler translates into HTTP responses.

PR-CONCEPT-052, PR-CONCEPT-054, PR-CONCEPT-056, PR-CONCEPT-060
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ResourceNotFoundError, ValidationError
from app.core.logging import get_logger
from app.modules.buildings.models import Building
from app.modules.concept_design.comparison_engine import (
    ConceptOptionComparisonInput,
    compute_concept_comparison,
)
from app.modules.concept_design.engine import (
    MixLineInput,
    compute_sellable_area,
    compute_unit_count,
    run_concept_engine,
)
from app.modules.concept_design.financial_engine import estimate_concept_financials
from app.modules.concept_design.repository import (
    ConceptOptionRepository,
    ConceptUnitMixLineRepository,
)
from app.modules.concept_design.schemas import (
    ConceptOptionComparisonResponse,
    ConceptOptionComparisonRowResponse,
    ConceptOptionCreate,
    ConceptOptionListResponse,
    ConceptOptionResponse,
    ConceptOptionSummaryResponse,
    ConceptOptionUpdate,
    ConceptPromotionRequest,
    ConceptPromotionResponse,
    ConceptUnitMixLineCreate,
    ConceptUnitMixLineResponse,
    SeedFeasibilityRequest,
    SeedFeasibilityResponse,
)
from app.modules.concept_design.validation import run_zoning_validation
from app.modules.feasibility.service import FeasibilityService
from app.modules.floors.models import Floor
from app.modules.land.models import LandParcel
from app.modules.phases.repository import PhaseRepository
from app.modules.phases.schemas import PhaseCreate
from app.modules.projects.repository import ProjectRepository
from app.modules.scenario.repository import ScenarioRepository
from app.modules.units.models import Unit
from app.shared.enums.project import BuildingStatus, FloorStatus, PhaseStatus, UnitStatus, UnitType

_logger = get_logger("reach_developments.concept_design")

# ---------------------------------------------------------------------------
# Unit-type normalisation helper
# ---------------------------------------------------------------------------

_UNIT_TYPE_ALIASES: dict[str, str] = {
    "studio": UnitType.STUDIO.value,
    "1br": UnitType.ONE_BEDROOM.value,
    "1 bedroom": UnitType.ONE_BEDROOM.value,
    "one bedroom": UnitType.ONE_BEDROOM.value,
    "1-bedroom": UnitType.ONE_BEDROOM.value,
    "2br": UnitType.TWO_BEDROOM.value,
    "2 bedroom": UnitType.TWO_BEDROOM.value,
    "two bedroom": UnitType.TWO_BEDROOM.value,
    "2-bedroom": UnitType.TWO_BEDROOM.value,
    "3br": UnitType.THREE_BEDROOM.value,
    "3 bedroom": UnitType.THREE_BEDROOM.value,
    "three bedroom": UnitType.THREE_BEDROOM.value,
    "3-bedroom": UnitType.THREE_BEDROOM.value,
    "4br": UnitType.FOUR_BEDROOM.value,
    "4 bedroom": UnitType.FOUR_BEDROOM.value,
    "four bedroom": UnitType.FOUR_BEDROOM.value,
    "4-bedroom": UnitType.FOUR_BEDROOM.value,
    "villa": UnitType.VILLA.value,
    "townhouse": UnitType.TOWNHOUSE.value,
    "retail": UnitType.RETAIL.value,
    "office": UnitType.OFFICE.value,
    "penthouse": UnitType.PENTHOUSE.value,
}

_VALID_UNIT_TYPES: frozenset[str] = frozenset(m.value for m in UnitType)


def _normalise_unit_type(raw: str) -> str:
    """Map a free-form concept mix unit_type string to a valid UnitType enum value.

    Input is stripped of leading/trailing whitespace and lower-cased before
    matching, so values such as 'ONE_BEDROOM', ' 1BR ', or 'Studio' all
    resolve to the correct canonical form.  Unrecognised values fall back to
    'studio'.
    """
    normalised = raw.strip().lower()
    if normalised in _VALID_UNIT_TYPES:
        return normalised
    return _UNIT_TYPE_ALIASES.get(normalised, UnitType.STUDIO.value)


class ConceptDesignService:
    def __init__(self, db: Session) -> None:
        self.option_repo = ConceptOptionRepository(db)
        self.mix_repo = ConceptUnitMixLineRepository(db)
        self.project_repo = ProjectRepository(db)
        self.scenario_repo = ScenarioRepository(db)
        self.phase_repo = PhaseRepository(db)

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
    # Land context resolution — PR-CONCEPT-060
    # ------------------------------------------------------------------

    def _fetch_land_parcel_for_scenario(
        self, scenario_id: str
    ) -> Optional[LandParcel]:
        """Return the LandParcel associated with *scenario_id*, or None.

        Returns None if the scenario does not exist or has no land_id.

        If the scenario exists and has a land_id but the referenced land
        parcel cannot be found, this method logs a warning and raises a
        ValidationError to avoid silently skipping inheritance/validation
        while the scenario still claims to have land.
        """
        scenario = self.scenario_repo.get_by_id(scenario_id)
        if scenario is None or scenario.land_id is None:
            return None

        land_parcel = (
            self.scenario_repo.db.query(LandParcel)
            .filter(LandParcel.id == scenario.land_id)
            .first()
        )

        if land_parcel is None:
            _logger.warning(
                "Scenario '%s' references missing LandParcel '%s'. "
                "Raising ValidationError to prevent silent fallback.",
                scenario_id,
                scenario.land_id,
            )
            raise ValidationError(
                f"Scenario '{scenario_id}' references a non-existent land parcel.",
                details={
                    "scenario_id": scenario_id,
                    "land_id": scenario.land_id,
                },
            )

        return land_parcel

    def _resolve_effective_far_limit(
        self,
        *,
        land_far: Optional[float],
        override_far: Optional[float],
        manual_far: Optional[float],
    ) -> Optional[float]:
        """Return the effective FAR limit using priority: override > land > manual.

        Priority order (PR-CONCEPT-060):
        1. concept_override_far_limit  — explicit user override
        2. land.permitted_far          — inherited from upstream land parcel
        3. far_limit                   — manually entered on the concept option
        """
        if override_far is not None:
            return override_far
        if land_far is not None:
            return land_far
        return manual_far

    def _resolve_effective_density_limit(
        self,
        *,
        land_density: Optional[float],
        override_density: Optional[float],
        manual_density: Optional[float],
    ) -> Optional[float]:
        """Return the effective density limit using priority: override > land > manual.

        Priority order (PR-CONCEPT-060):
        1. concept_override_density_limit  — explicit user override
        2. land.density_ratio              — inherited from upstream land parcel
        3. density_limit                   — manually entered on the concept option
        """
        if override_density is not None:
            return override_density
        if land_density is not None:
            return land_density
        return manual_density

    # ------------------------------------------------------------------
    # Zoning / structural validation — PR-CONCEPT-059
    # ------------------------------------------------------------------

    def _validate_concept_zoning(
        self,
        site_area: Optional[float],
        gross_floor_area: Optional[float],
        far_limit: Optional[float],
        density_limit: Optional[float],
        sellable_area: Optional[float] = None,
        unit_count: Optional[int] = None,
    ) -> None:
        """Run zoning and structural validation rules.

        Raises :class:`~app.core.errors.ValidationError` when one or more
        rules are violated, with a structured ``violations`` list in the
        details payload.

        Rules where the required inputs are absent are silently skipped so
        that concept options without all constraint fields configured are
        not blocked.
        """
        violations = run_zoning_validation(
            site_area=site_area,
            gross_floor_area=gross_floor_area,
            far_limit=far_limit,
            density_limit=density_limit,
            sellable_area=sellable_area,
            unit_count=unit_count,
        )
        if violations:
            raise ValidationError(
                "Concept option violates zoning or structural constraints.",
                details={
                    "violations": [
                        {
                            "rule": v.rule,
                            "message": v.message,
                            "details": v.details,
                        }
                        for v in violations
                    ]
                },
            )

    # ------------------------------------------------------------------
    # Effective constraint resolution — PR-CONCEPT-060
    # ------------------------------------------------------------------

    def _resolve_land_constraints_for_option(
        self, option_land_id: Optional[str]
    ) -> tuple[Optional[float], Optional[float]]:
        """Return (land_far, land_density) for the given land_id.

        Fetches the LandParcel and extracts ``permitted_far`` and
        ``density_ratio``.  Returns (None, None) if land_id is absent or the
        parcel cannot be found.

        This helper centralises the repeated query pattern used by
        ``update_concept_option`` and ``promote_concept_option`` so the lookup
        logic lives in exactly one place.
        """
        if option_land_id is None:
            return None, None
        land_parcel = (
            self.scenario_repo.db.query(LandParcel)
            .filter(LandParcel.id == option_land_id)
            .first()
        )
        if land_parcel is None:
            return None, None
        land_far = (
            float(land_parcel.permitted_far) if land_parcel.permitted_far is not None else None
        )
        land_density = (
            float(land_parcel.density_ratio) if land_parcel.density_ratio is not None else None
        )
        return land_far, land_density

    # ------------------------------------------------------------------
    # ConceptOption CRUD
    # ------------------------------------------------------------------

    def create_concept_option(self, data: ConceptOptionCreate) -> ConceptOptionResponse:
        self._validate_project_if_present(data.project_id)
        self._validate_scenario_if_present(data.scenario_id)

        # ── Land / Scenario context inheritance — PR-CONCEPT-060 ──────
        land_id: Optional[str] = None
        inherited_site_area: Optional[float] = None
        inherited_far: Optional[float] = None
        inherited_density: Optional[float] = None

        if data.scenario_id is not None:
            land_parcel = self._fetch_land_parcel_for_scenario(data.scenario_id)
            if land_parcel is not None:
                land_id = land_parcel.id
                if land_parcel.land_area_sqm is not None:
                    inherited_site_area = float(land_parcel.land_area_sqm)
                if land_parcel.permitted_far is not None:
                    inherited_far = float(land_parcel.permitted_far)
                if land_parcel.density_ratio is not None:
                    inherited_density = float(land_parcel.density_ratio)
                _logger.info(
                    "ConceptOption inheriting land context land_id=%s "
                    "site_area=%s far=%s density=%s",
                    land_id,
                    inherited_site_area,
                    inherited_far,
                    inherited_density,
                )

        # When a scenario with a land parcel is supplied, auto-populate
        # site_area, far_limit, and density_limit from the parcel if the
        # caller did not explicitly provide those values.
        effective_site_area = data.site_area if data.site_area is not None else inherited_site_area
        effective_far = self._resolve_effective_far_limit(
            land_far=inherited_far,
            override_far=data.concept_override_far_limit,
            manual_far=data.far_limit,
        )
        effective_density = self._resolve_effective_density_limit(
            land_density=inherited_density,
            override_density=data.concept_override_density_limit,
            manual_density=data.density_limit,
        )

        self._validate_concept_zoning(
            site_area=effective_site_area,
            gross_floor_area=data.gross_floor_area,
            far_limit=effective_far,
            density_limit=effective_density,
        )

        # Store the resolved values back so the DB row reflects the
        # inherited/effective values even if the caller omitted them.
        updates: dict = {}
        if data.site_area is None and inherited_site_area is not None:
            updates["site_area"] = inherited_site_area
        if data.far_limit is None and effective_far is not None:
            updates["far_limit"] = effective_far
        if data.density_limit is None and effective_density is not None:
            updates["density_limit"] = effective_density
        if updates:
            data = data.model_copy(update=updates)

        option = self.option_repo.create(data, land_id=land_id)
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

        # Merge incoming values with existing values to validate the
        # resulting state, not just the patched fields in isolation.
        update_data = data.model_dump(exclude_unset=True)
        merged_site_area = float(option.site_area) if option.site_area is not None else None
        merged_gfa = float(option.gross_floor_area) if option.gross_floor_area is not None else None
        merged_far_limit = float(option.far_limit) if option.far_limit is not None else None
        merged_density_limit = float(option.density_limit) if option.density_limit is not None else None
        merged_override_far = (
            float(option.concept_override_far_limit)
            if option.concept_override_far_limit is not None
            else None
        )
        merged_override_density = (
            float(option.concept_override_density_limit)
            if option.concept_override_density_limit is not None
            else None
        )

        if "site_area" in update_data:
            merged_site_area = update_data["site_area"]
        if "gross_floor_area" in update_data:
            merged_gfa = update_data["gross_floor_area"]
        if "far_limit" in update_data:
            merged_far_limit = update_data["far_limit"]
        if "density_limit" in update_data:
            merged_density_limit = update_data["density_limit"]
        if "concept_override_far_limit" in update_data:
            merged_override_far = update_data["concept_override_far_limit"]
        if "concept_override_density_limit" in update_data:
            merged_override_density = update_data["concept_override_density_limit"]

        # Resolve the land-inherited constraints for this option (if any).
        # land_id is read from the existing option — it is set at creation time
        # and cannot be changed via an update (scenario context is immutable).
        land_far, land_density = self._resolve_land_constraints_for_option(option.land_id)

        effective_far = self._resolve_effective_far_limit(
            land_far=land_far,
            override_far=merged_override_far,
            manual_far=merged_far_limit,
        )
        effective_density = self._resolve_effective_density_limit(
            land_density=land_density,
            override_density=merged_override_density,
            manual_density=merged_density_limit,
        )

        self._validate_concept_zoning(
            site_area=merged_site_area,
            gross_floor_area=merged_gfa,
            far_limit=effective_far,
            density_limit=effective_density,
        )

        option = self.option_repo.update(option, data)
        return ConceptOptionResponse.model_validate(option)

    def delete_concept_option(self, concept_option_id: str) -> None:
        """Delete a concept option and its unit mix lines.

        Deletion is forbidden when the concept option has already been promoted
        (``is_promoted=True``) because it becomes the traceability origin for
        the project phase, buildings, floors, and units that were created during
        promotion.  Attempting to delete a promoted option raises
        :class:`~app.core.errors.ConflictError`.
        """
        option = self.option_repo.get_by_id(concept_option_id)
        if option is None:
            raise ResourceNotFoundError(
                f"ConceptOption '{concept_option_id}' not found."
            )
        if option.is_promoted:
            raise ConflictError(
                "Cannot delete a promoted concept option. "
                "Promoted concepts are the origin of project structure and must remain immutable.",
                details={"concept_option_id": concept_option_id},
            )
        _logger.info("Deleting ConceptOption id=%s name=%r", option.id, option.name)
        self.option_repo.delete(option)

    # ------------------------------------------------------------------
    # Duplication — PR-CONCEPT-058
    # ------------------------------------------------------------------

    def _generate_duplicate_name(
        self,
        source_name: str,
        project_id: Optional[str],
        scenario_id: Optional[str],
    ) -> str:
        """Return a unique name for a duplicated concept option.

        Naming convention:
        - First copy:  ``"<name> (Copy)"``
        - Further copies: ``"<name> (Copy 2)"``, ``"<name> (Copy 3)"``, …

        Uniqueness is checked against all concept options that share the same
        project_id / scenario_id scope as the source.
        """
        existing_names = self.option_repo.get_names_in_scope(
            project_id=project_id,
            scenario_id=scenario_id,
        )

        candidate = f"{source_name} (Copy)"
        if candidate not in existing_names:
            return candidate

        counter = 2
        while True:
            candidate = f"{source_name} (Copy {counter})"
            if candidate not in existing_names:
                return candidate
            counter += 1

    def duplicate_concept_option(self, concept_option_id: str) -> ConceptOptionResponse:
        """Duplicate a concept option and its unit mix lines.

        Duplication rules
        -----------------
        * The concept option must exist.
        * Archived concept options cannot be duplicated.
        * Promoted options *can* be duplicated — the copy starts unpromoted.
        * The duplicate receives a generated name: ``"<original> (Copy)"``,
          ``"<original> (Copy 2)"``, etc.
        * ``is_promoted``, ``promoted_at``, ``promoted_project_id``, and
          ``promotion_notes`` are NOT copied.
        """
        option = self.option_repo.get_by_id_with_mix(concept_option_id)
        if option is None:
            raise ResourceNotFoundError(
                f"ConceptOption '{concept_option_id}' not found."
            )
        if option.status == "archived":
            raise ConflictError(
                "Cannot duplicate an archived concept option.",
                details={"concept_option_id": concept_option_id},
            )

        new_name = self._generate_duplicate_name(
            option.name, option.project_id, option.scenario_id
        )
        clone = self.option_repo.clone_concept_option(option, new_name)
        self.mix_repo.clone_for_option(option.mix_lines, clone.id)
        self.option_repo.db.commit()
        self.option_repo.db.refresh(clone)

        _logger.info(
            "ConceptOption duplicated source_id=%s new_id=%s new_name=%r",
            option.id,
            clone.id,
            clone.name,
        )
        return ConceptOptionResponse.model_validate(clone)

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
            land_id=option.land_id,
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
            far_limit=float(option.far_limit) if option.far_limit is not None else None,
            density_limit=(
                float(option.density_limit)
                if option.density_limit is not None
                else None
            ),
            concept_override_far_limit=(
                float(option.concept_override_far_limit)
                if option.concept_override_far_limit is not None
                else None
            ),
            concept_override_density_limit=(
                float(option.concept_override_density_limit)
                if option.concept_override_density_limit is not None
                else None
            ),
            unit_count=metrics.unit_count,
            sellable_area=metrics.sellable_area,
            efficiency_ratio=metrics.efficiency_ratio,
            average_unit_area=metrics.average_unit_area,
            mix_lines=[
                ConceptUnitMixLineResponse.model_validate(line)
                for line in option.mix_lines
            ],
        )

    # ------------------------------------------------------------------
    # Comparison (multi-option side-by-side)
    # ------------------------------------------------------------------

    def compare_concept_options(
        self,
        project_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        price_per_sqm: Optional[float] = None,
        price_per_unit: Optional[float] = None,
    ) -> ConceptOptionComparisonResponse:
        """Return a structured comparison of all concept options for a project or scenario.

        Exactly one of *project_id* or *scenario_id* must be provided.
        Supplying both or neither raises :class:`~app.core.errors.ValidationError`.

        Optional pricing parameters *price_per_sqm* and *price_per_unit* are
        used to derive financial GDV metrics (PR-CONCEPT-062).  When omitted
        all financial metric fields are None.
        """
        if project_id is not None and scenario_id is not None:
            raise ValidationError(
                "Provide either 'project_id' or 'scenario_id', not both.",
                details={"project_id": project_id, "scenario_id": scenario_id},
            )
        if project_id is None and scenario_id is None:
            raise ValidationError(
                "Either 'project_id' or 'scenario_id' must be provided.",
            )

        if project_id is not None:
            self._validate_project_if_present(project_id)
            options = self.option_repo.list_by_project_id(project_id)
            basis = "project"
        else:
            assert scenario_id is not None
            self._validate_scenario_if_present(scenario_id)
            options = self.option_repo.list_by_scenario_id(scenario_id)
            basis = "scenario"

        comparison_inputs = []
        for option in options:
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
            financial = estimate_concept_financials(
                sellable_area=metrics.sellable_area,
                unit_count=metrics.unit_count,
                price_per_sqm=price_per_sqm,
                price_per_unit=price_per_unit,
            )
            comparison_inputs.append(
                ConceptOptionComparisonInput(
                    concept_option_id=option.id,
                    name=option.name,
                    status=option.status,
                    unit_count=metrics.unit_count,
                    sellable_area=metrics.sellable_area,
                    efficiency_ratio=metrics.efficiency_ratio,
                    average_unit_area=metrics.average_unit_area,
                    building_count=option.building_count,
                    floor_count=option.floor_count,
                    estimated_gdv=financial.estimated_gdv,
                    estimated_revenue_per_sqm=financial.estimated_revenue_per_sqm,
                    estimated_revenue_per_unit=financial.estimated_revenue_per_unit,
                )
            )

        result = compute_concept_comparison(comparison_inputs, basis)

        return ConceptOptionComparisonResponse(
            comparison_basis=result.comparison_basis,
            option_count=result.option_count,
            best_sellable_area_option_id=result.best_sellable_area_option_id,
            best_efficiency_option_id=result.best_efficiency_option_id,
            best_unit_count_option_id=result.best_unit_count_option_id,
            best_gdv_option_id=result.best_gdv_option_id,
            rows=[
                ConceptOptionComparisonRowResponse(
                    concept_option_id=row.concept_option_id,
                    name=row.name,
                    status=row.status,
                    unit_count=row.unit_count,
                    sellable_area=row.sellable_area,
                    efficiency_ratio=row.efficiency_ratio,
                    average_unit_area=row.average_unit_area,
                    building_count=row.building_count,
                    floor_count=row.floor_count,
                    sellable_area_delta_vs_best=row.sellable_area_delta_vs_best,
                    efficiency_delta_vs_best=row.efficiency_delta_vs_best,
                    unit_count_delta_vs_best=row.unit_count_delta_vs_best,
                    is_best_sellable_area=row.is_best_sellable_area,
                    is_best_efficiency=row.is_best_efficiency,
                    is_best_unit_count=row.is_best_unit_count,
                    estimated_gdv=row.estimated_gdv,
                    estimated_revenue_per_sqm=row.estimated_revenue_per_sqm,
                    estimated_revenue_per_unit=row.estimated_revenue_per_unit,
                    gdv_delta_vs_best=row.gdv_delta_vs_best,
                    is_best_gdv=row.is_best_gdv,
                )
                for row in result.rows
            ],
        )

    # ------------------------------------------------------------------
    # Promotion — PR-CONCEPT-054
    # ------------------------------------------------------------------

    def promote_concept_option(
        self,
        concept_option_id: str,
        payload: ConceptPromotionRequest,
    ) -> ConceptPromotionResponse:
        """Promote a concept option into a structured downstream project phase.

        Promotion rules
        ---------------
        * The concept option must exist.
        * The concept option must not be archived.
        * The concept option must not already be promoted.
        * The concept option must have building_count, floor_count, and at
          least one unit mix line to qualify as structurally complete.
        * The concept option must pass all applicable zoning and structural
          validation rules (FAR, efficiency, density) — PR-CONCEPT-059.
        * A target project must be resolvable — either from the concept
          option's own project_id or from payload.target_project_id.

        Project linkage strategy
        ------------------------
        * If the concept option already has a project_id, that project is
          used as the promotion target.  payload.target_project_id must
          either be absent or match the concept's project_id; supplying a
          different value raises ValidationError.
        * If the concept option has no project_id, payload.target_project_id
          is required.

        On success, a new Phase is created under the target project, and
        the concept option is marked as promoted (is_promoted=True,
        promoted_at, promoted_project_id, promotion_notes are persisted).
        """
        option = self.option_repo.get_by_id_with_mix(concept_option_id)
        if option is None:
            raise ResourceNotFoundError(
                f"ConceptOption '{concept_option_id}' not found."
            )

        # ── Promotability checks ──────────────────────────────────────
        if option.status == "archived":
            raise ValidationError(
                "Archived concept options cannot be promoted.",
                details={"status": option.status},
            )

        if option.is_promoted:
            raise ConflictError(
                f"ConceptOption '{concept_option_id}' has already been promoted.",
                details={"promoted_project_id": option.promoted_project_id},
            )

        missing: list[str] = []
        if not option.building_count:
            missing.append("building_count")
        if not option.floor_count:
            missing.append("floor_count")
        if not option.mix_lines:
            missing.append("unit mix lines")
        if missing:
            raise ValidationError(
                "Concept option does not have sufficient structural data for promotion.",
                details={"missing_fields": missing},
            )

        # ── Zoning / structural validation — PR-CONCEPT-059 ──────────
        # Compute aggregate mix metrics so that efficiency and density
        # rules can be evaluated against the full unit program.
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
        promo_unit_count = compute_unit_count(mix_inputs)
        promo_sellable_area = compute_sellable_area(mix_inputs)

        # Resolve effective constraints (PR-CONCEPT-060 priority order)
        promo_land_far, promo_land_density = self._resolve_land_constraints_for_option(
            option.land_id
        )

        promo_effective_far = self._resolve_effective_far_limit(
            land_far=promo_land_far,
            override_far=(
                float(option.concept_override_far_limit)
                if option.concept_override_far_limit is not None
                else None
            ),
            manual_far=float(option.far_limit) if option.far_limit is not None else None,
        )
        promo_effective_density = self._resolve_effective_density_limit(
            land_density=promo_land_density,
            override_density=(
                float(option.concept_override_density_limit)
                if option.concept_override_density_limit is not None
                else None
            ),
            manual_density=(
                float(option.density_limit) if option.density_limit is not None else None
            ),
        )

        self._validate_concept_zoning(
            site_area=float(option.site_area) if option.site_area is not None else None,
            gross_floor_area=(
                float(option.gross_floor_area)
                if option.gross_floor_area is not None
                else None
            ),
            far_limit=promo_effective_far,
            density_limit=promo_effective_density,
            sellable_area=promo_sellable_area,
            unit_count=promo_unit_count,
        )

        # ── Project linkage strategy ──────────────────────────────────
        if (
            option.project_id is not None
            and payload.target_project_id is not None
            and payload.target_project_id != option.project_id
        ):
            raise ValidationError(
                "Conflicting project targets: the concept option is already linked "
                "to a different project than the supplied 'target_project_id'.",
                details={
                    "concept_project_id": option.project_id,
                    "requested_target_project_id": payload.target_project_id,
                },
            )
        target_project_id: Optional[str] = option.project_id or payload.target_project_id
        if target_project_id is None:
            raise ValidationError(
                "A target project is required for promotion. "
                "Either link the concept option to a project or supply "
                "'target_project_id' in the request.",
            )
        self._validate_project_if_present(target_project_id)

        # ── Determine phase sequence ──────────────────────────────────
        # Use max(sequence)+1 so the result is correct even when phases have
        # been deleted or resequenced (non-dense sequence history).
        max_seq = self.phase_repo.get_max_sequence(project_id=target_project_id)
        next_sequence = (max_seq or 0) + 1

        # ── Create structured phase ───────────────────────────────────
        phase_name = (
            payload.phase_name
            if payload.phase_name
            else f"Phase {next_sequence} — {option.name}"
        )
        phase_data = PhaseCreate(
            project_id=target_project_id,
            name=phase_name,
            sequence=next_sequence,
            status=PhaseStatus.PLANNED,
            description=(
                f"Promoted from concept option '{option.name}'. "
                f"Buildings: {option.building_count}, floors: {option.floor_count}, "
                f"unit mix lines: {len(option.mix_lines)}."
            ),
        )

        # ── Atomically persist phase, scaffolding, and promotion metadata ──
        # Stage all writes before the single commit so that a failure in
        # any step leaves no partial state in the database.
        promoted_at = datetime.now(timezone.utc)
        # apply_create() flushes the session internally, making phase.id
        # available to child records without an extra explicit flush here.
        phase = self.phase_repo.apply_create(phase_data)

        # ── Create buildings ──────────────────────────────────────────
        building_count: int = option.building_count  # type: ignore[assignment]
        floor_count: int = option.floor_count  # type: ignore[assignment]

        buildings: list[Building] = []
        for i in range(building_count):
            # Use single letters A–Z for the first 26 buildings, then AA, AB, …
            if i < 26:
                label = chr(ord("A") + i)
            else:
                label = chr(ord("A") + i // 26 - 1) + chr(ord("A") + i % 26)
            building = Building(
                phase_id=phase.id,
                name=f"Building {label}",
                code=f"BLK-{label}",
                floors_count=floor_count,
                status=BuildingStatus.PLANNED.value,
            )
            self.option_repo.db.add(building)
            buildings.append(building)
        self.option_repo.db.flush()  # generate building ids

        # ── Create floors ─────────────────────────────────────────────
        # All floors across all buildings, indexed for unit assignment.
        all_floors: list[Floor] = []
        for building in buildings:
            for seq in range(1, floor_count + 1):
                floor = Floor(
                    building_id=building.id,
                    name=f"Floor {seq}",
                    code=f"FL-{seq:02d}",
                    sequence_number=seq,
                    status=FloorStatus.PLANNED.value,
                )
                self.option_repo.db.add(floor)
                all_floors.append(floor)
        self.option_repo.db.flush()  # generate floor ids

        # ── Create units from mix lines ───────────────────────────────
        # Units are distributed sequentially across all floors (round-robin).
        # Per-floor unit counter tracks the next unit number for each floor.
        floor_unit_counters: dict[str, int] = {f.id: 0 for f in all_floors}
        floor_cycle_index = 0
        total_floors = len(all_floors)
        units_created_count = 0

        for mix_line in option.mix_lines:
            unit_type = _normalise_unit_type(mix_line.unit_type)
            if mix_line.avg_internal_area is not None:
                internal_area = float(mix_line.avg_internal_area)
            elif mix_line.avg_sellable_area is not None:
                internal_area = float(mix_line.avg_sellable_area)
            else:
                internal_area = 0.0
            for _ in range(mix_line.units_count):
                target_floor = all_floors[floor_cycle_index % total_floors]
                floor_cycle_index += 1
                floor_unit_counters[target_floor.id] += 1
                unit_number = str(floor_unit_counters[target_floor.id])
                unit = Unit(
                    floor_id=target_floor.id,
                    unit_number=unit_number,
                    unit_type=unit_type,
                    status=UnitStatus.AVAILABLE.value,
                    internal_area=internal_area if internal_area > 0 else 0.0,
                )
                self.option_repo.db.add(unit)
                units_created_count += 1

        self.option_repo.apply_promotion_fields(
            option,
            promoted_project_id=target_project_id,
            promoted_at=promoted_at,
            promotion_notes=payload.promotion_notes,
        )
        self.option_repo.db.commit()
        self.option_repo.db.refresh(phase)
        self.option_repo.db.refresh(option)

        _logger.info(
            "ConceptOption promoted id=%s → project=%s phase=%s "
            "buildings=%d floors=%d units=%d",
            concept_option_id,
            target_project_id,
            phase.id,
            building_count,
            len(all_floors),
            units_created_count,
        )

        return ConceptPromotionResponse(
            concept_option_id=concept_option_id,
            promoted_project_id=target_project_id,
            promoted_phase_id=phase.id,
            promoted_phase_name=phase.name,
            promoted_at=promoted_at,
            promotion_notes=payload.promotion_notes,
            buildings_created=building_count,
            floors_created=len(all_floors),
            units_created=units_created_count,
        )

    # ------------------------------------------------------------------
    # Seed-Feasibility — PR-CONCEPT-063
    # ------------------------------------------------------------------

    def seed_feasibility_from_concept_option(
        self,
        concept_option_id: str,
        payload: SeedFeasibilityRequest,
    ) -> SeedFeasibilityResponse:
        """Seed a feasibility run from a concept option.

        Seeding rules
        -------------
        * The concept option must exist.
        * The concept option must not be archived (archived options are
          excluded from forward-lifecycle actions).
        * The concept option's computed sellable_area is transferred to the
          new feasibility run's assumptions.  If no mix lines carry a
          sellable area the field is seeded as None, and assumptions are
          not persisted — the caller must supply sellable_area via the
          dedicated assumptions endpoint before running a calculation.

        The new feasibility run inherits the concept option's scenario_id
        to preserve cross-module lineage.

        This method does not perform financial calculations; it only creates
        the run and assumptions records.  Calculation must be triggered
        separately via POST /feasibility/runs/{id}/calculate.
        """
        option = self.option_repo.get_by_id_with_mix(concept_option_id)
        if option is None:
            raise ResourceNotFoundError(
                f"ConceptOption '{concept_option_id}' not found."
            )

        if option.status == "archived":
            raise ValidationError(
                "Archived concept options cannot seed a feasibility run.",
                details={"status": option.status},
            )

        # Compute sellable_area from mix lines via concept engine
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
        unit_count = compute_unit_count(mix_inputs)
        sellable_area = compute_sellable_area(mix_inputs)

        scenario_name = (
            payload.scenario_name
            if payload.scenario_name
            else f"Feasibility — {option.name}"
        )

        feasibility_service = FeasibilityService(self.option_repo.db)
        run_response = feasibility_service.create_seeded_run(
            source_concept_option_id=concept_option_id,
            scenario_id=option.scenario_id,
            scenario_name=scenario_name,
            sellable_area_sqm=sellable_area,
            avg_sale_price_per_sqm=payload.avg_sale_price_per_sqm,
            construction_cost_per_sqm=payload.construction_cost_per_sqm,
            soft_cost_ratio=payload.soft_cost_ratio,
            finance_cost_ratio=payload.finance_cost_ratio,
            sales_cost_ratio=payload.sales_cost_ratio,
            development_period_months=payload.development_period_months,
            notes=payload.notes,
        )

        _logger.info(
            "Feasibility run seeded from concept option: concept_option_id=%s "
            "feasibility_run_id=%s sellable_area_sqm=%s",
            concept_option_id,
            run_response.id,
            sellable_area,
        )

        assumptions_seeded = (
            sellable_area is not None
            and payload.avg_sale_price_per_sqm is not None
            and payload.construction_cost_per_sqm is not None
            and payload.development_period_months is not None
        )

        return SeedFeasibilityResponse(
            feasibility_run_id=run_response.id,
            source_concept_option_id=concept_option_id,
            seed_source_type="concept_option",
            scenario_name=scenario_name,
            scenario_id=option.scenario_id,
            seeded_sellable_area_sqm=sellable_area,
            seeded_unit_count=unit_count,
            assumptions_seeded=assumptions_seeded,
        )

