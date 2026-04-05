"""
projects.service

Business logic for the Project entity and project attribute definitions/options.
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.projects.models import Project, ProjectAttributeDefinition, ProjectAttributeOption
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import (
    AttributeDefinitionCreate,
    AttributeDefinitionList,
    AttributeDefinitionResponse,
    AttributeDefinitionUpdate,
    AttributeOptionCreate,
    AttributeOptionResponse,
    AttributeOptionUpdate,
    HierarchyBuilding,
    HierarchyFloor,
    HierarchyPhase,
    ProjectCreate,
    ProjectHierarchy,
    ProjectLifecycleSummaryResponse,
    ProjectList,
    ProjectResponse,
    ProjectSummary,
    ProjectUpdate,
)
from app.shared.enums.project import ProjectStatus


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.repo = ProjectRepository(db)

    def create_project(self, data: ProjectCreate) -> ProjectResponse:
        existing = self.repo.get_by_code(data.code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project with code '{data.code}' already exists.",
            )
        project = self.repo.create(data)
        return ProjectResponse.model_validate(project)

    def get_project(self, project_id: str) -> ProjectResponse:
        project = self._require_project(project_id)
        return ProjectResponse.model_validate(project)

    def list_projects(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ProjectStatus] = None,
        search: Optional[str] = None,
    ) -> ProjectList:
        status_value = status.value if status else None
        projects = self.repo.list(skip=skip, limit=limit, status=status_value, search=search)
        total = self.repo.count(status=status_value, search=search)
        return ProjectList(
            items=[ProjectResponse.model_validate(p) for p in projects],
            total=total,
        )

    def update_project(self, project_id: str, data: ProjectUpdate) -> ProjectResponse:
        project = self._require_project(project_id)
        # Guard: base_currency is immutable once financial records exist
        if "base_currency" in data.model_fields_set and data.base_currency != project.base_currency:
            if self.repo.has_financial_records(project_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Cannot change base_currency after financial records exist "
                        "for this project. Currency is locked once scenarios, "
                        "feasibility runs, construction costs, or land parcels "
                        "have been recorded."
                    ),
                )
        # Validate date range using merged values: payload overrides persisted
        effective_start = (
            data.start_date if "start_date" in data.model_fields_set else project.start_date
        )
        effective_end = (
            data.target_end_date
            if "target_end_date" in data.model_fields_set
            else project.target_end_date
        )
        if effective_start and effective_end and effective_end < effective_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="target_end_date must be on or after start_date.",
            )
        updated = self.repo.update(project, data)
        return ProjectResponse.model_validate(updated)

    def delete_project(self, project_id: str) -> None:
        project = self._require_project(project_id)
        if self.repo.has_phases(project_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Project '{project_id}' cannot be deleted because it has "
                    "dependent phase records. Remove all dependent phases first."
                ),
            )
        self.repo.delete(project)

    def archive_project(self, project_id: str) -> ProjectResponse:
        """Set a project's status to on_hold, effectively archiving it."""
        project = self._require_project(project_id)
        if project.status == ProjectStatus.ON_HOLD.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project '{project_id}' is already archived (on_hold).",
            )
        archive_data = ProjectUpdate(status=ProjectStatus.ON_HOLD)
        updated = self.repo.update(project, archive_data)
        return ProjectResponse.model_validate(updated)

    def get_project_summary(self, project_id: str) -> ProjectSummary:
        """Return aggregated KPI summary for a project's phases."""
        self._require_project(project_id)
        data = self.repo.get_project_phase_summary(project_id)
        return ProjectSummary(project_id=project_id, **data)

    def get_project_lifecycle_summary(self, project_id: str) -> ProjectLifecycleSummaryResponse:
        """Return cross-module lifecycle readiness summary for a project.

        Derives lifecycle stage and recommended next step from real module records.
        This is a read-only, non-destructive operation.
        """
        project = self._require_project(project_id)
        flags = self.repo.get_lifecycle_flags(project_id)

        has_scenarios = flags["scenario_count"] > 0
        has_active_scenario = flags["has_active_scenario"]
        has_feasibility_runs = flags["feasibility_run_count"] > 0
        has_calculated_feasibility = flags["has_calculated_feasibility"]
        has_phases = flags["phase_count"] > 0
        has_construction_records = flags["construction_record_count"] > 0
        has_approved_tender_baseline = flags["has_approved_tender_baseline"]

        # A project reaches portfolio_visible when it has both governance
        # (approved baseline) and active cost records — i.e. it is fully
        # monitorable and eligible for portfolio roll-up.
        has_portfolio_visibility = has_approved_tender_baseline and has_construction_records

        # Derive current stage and next step deterministically
        current_stage, recommended_next_step, next_step_route, blocked_reason = (
            _derive_lifecycle_stage(
                project_id=project_id,
                has_scenarios=has_scenarios,
                has_feasibility_runs=has_feasibility_runs,
                has_calculated_feasibility=has_calculated_feasibility,
                has_phases=has_phases,
                has_construction_records=has_construction_records,
                has_approved_tender_baseline=has_approved_tender_baseline,
                has_portfolio_visibility=has_portfolio_visibility,
            )
        )

        return ProjectLifecycleSummaryResponse(
            project_id=project_id,
            has_scenarios=has_scenarios,
            has_active_scenario=has_active_scenario,
            has_feasibility_runs=has_feasibility_runs,
            has_calculated_feasibility=has_calculated_feasibility,
            has_phases=has_phases,
            has_construction_records=has_construction_records,
            has_approved_tender_baseline=has_approved_tender_baseline,
            has_portfolio_visibility=has_portfolio_visibility,
            scenario_count=flags["scenario_count"],
            feasibility_run_count=flags["feasibility_run_count"],
            construction_record_count=flags["construction_record_count"],
            current_stage=current_stage,
            recommended_next_step=recommended_next_step,
            next_step_route=next_step_route,
            blocked_reason=blocked_reason,
            last_updated_at=project.updated_at,
        )

    def get_project_hierarchy(self, project_id: str) -> ProjectHierarchy:
        """Return the full Project → Phase → Building → Floor hierarchy with unit counts."""
        self._require_project(project_id)
        rows = self.repo.get_hierarchy(project_id)

        # Assemble nested structure from flat query rows
        phases_map: dict[str, HierarchyPhase] = {}
        buildings_map: dict[str, HierarchyBuilding] = {}

        for row in rows:
            if row.phase_id not in phases_map:
                phases_map[row.phase_id] = HierarchyPhase(
                    phase_id=row.phase_id,
                    name=row.phase_name,
                    sequence=row.phase_sequence,
                    buildings=[],
                )
            if row.building_id is None:
                continue
            if row.building_id not in buildings_map:
                building = HierarchyBuilding(
                    building_id=row.building_id,
                    name=row.building_name,
                    code=row.building_code,
                    floors=[],
                )
                buildings_map[row.building_id] = building
                phases_map[row.phase_id].buildings.append(building)
            if row.floor_id is None:
                continue
            floor = HierarchyFloor(
                floor_id=row.floor_id,
                name=row.floor_name,
                code=row.floor_code,
                sequence_number=row.floor_sequence,
                unit_count=row.unit_count,
            )
            buildings_map[row.building_id].floors.append(floor)

        return ProjectHierarchy(
            project_id=project_id,
            phases=list(phases_map.values()),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_id: str) -> Project:
        project = self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        return project

    # ------------------------------------------------------------------
    # Attribute Definitions
    # ------------------------------------------------------------------

    def list_attribute_definitions(self, project_id: str) -> AttributeDefinitionList:
        """List all attribute definitions for a project."""
        self._require_project(project_id)
        definitions = self.repo.list_definitions(project_id)
        items = [AttributeDefinitionResponse.model_validate(d) for d in definitions]
        return AttributeDefinitionList(items=items, total=len(items))

    def create_attribute_definition(
        self, project_id: str, data: AttributeDefinitionCreate
    ) -> AttributeDefinitionResponse:
        """Create a project attribute definition.

        Raises 409 if a definition with the same key already exists for this project.
        """
        from sqlalchemy.exc import IntegrityError

        self._require_project(project_id)
        existing = self.repo.get_definition_by_project_and_key(project_id, data.key)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Attribute definition with key '{data.key}' already exists "
                    f"for project '{project_id}'."
                ),
            )
        try:
            definition = self.repo.create_definition(project_id, data)
        except IntegrityError:
            self.repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Attribute definition with key '{data.key}' already exists "
                    f"for project '{project_id}' (concurrent request)."
                ),
            )
        return AttributeDefinitionResponse.model_validate(definition)

    def update_attribute_definition(
        self, project_id: str, definition_id: str, data: AttributeDefinitionUpdate
    ) -> AttributeDefinitionResponse:
        """Update label or is_active flag of a definition."""
        self._require_project(project_id)
        definition = self._require_definition(project_id, definition_id)
        updated = self.repo.update_definition(definition, data)
        return AttributeDefinitionResponse.model_validate(updated)

    # ------------------------------------------------------------------
    # Attribute Options
    # ------------------------------------------------------------------

    def create_attribute_option(
        self, project_id: str, definition_id: str, data: AttributeOptionCreate
    ) -> AttributeOptionResponse:
        """Add an option to a definition.

        Raises 409 if an option with the same value or label already exists.
        """
        from sqlalchemy.exc import IntegrityError

        self._require_project(project_id)
        definition = self._require_definition(project_id, definition_id)

        if self.repo.get_option_by_definition_and_value(definition.id, data.value):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An option with value '{data.value}' already exists in this definition.",
            )
        if self.repo.get_option_by_definition_and_label(definition.id, data.label):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An option with label '{data.label}' already exists in this definition.",
            )

        try:
            option = self.repo.create_option(definition.id, data)
        except IntegrityError:
            self.repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An option with the same value or label already exists in this definition (concurrent request).",
            )
        return AttributeOptionResponse.model_validate(option)

    def update_attribute_option(
        self,
        project_id: str,
        definition_id: str,
        option_id: str,
        data: AttributeOptionUpdate,
    ) -> AttributeOptionResponse:
        """Update label, sort_order, or is_active of an option."""
        self._require_project(project_id)
        definition = self._require_definition(project_id, definition_id)
        option = self._require_option(definition.id, option_id)

        # Check label uniqueness if label is being changed
        if data.label is not None and data.label != option.label:
            conflict = self.repo.get_option_by_definition_and_label(definition.id, data.label)
            if conflict and conflict.id != option_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"An option with label '{data.label}' already exists in this definition.",
                )

        updated = self.repo.update_option(option, data)
        return AttributeOptionResponse.model_validate(updated)

    # ------------------------------------------------------------------
    # Internal helpers — definitions/options
    # ------------------------------------------------------------------

    def _require_definition(
        self, project_id: str, definition_id: str
    ) -> ProjectAttributeDefinition:
        definition = self.repo.get_definition_by_id(definition_id)
        if not definition or definition.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attribute definition '{definition_id}' not found for project '{project_id}'.",
            )
        return definition

    def _require_option(
        self, definition_id: str, option_id: str
    ) -> ProjectAttributeOption:
        option = self.repo.get_option_by_id(option_id)
        if not option or option.definition_id != definition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attribute option '{option_id}' not found for this definition.",
            )
        return option


# ---------------------------------------------------------------------------
# Lifecycle stage derivation — module-level helper (pure function)
# ---------------------------------------------------------------------------

def _derive_lifecycle_stage(
    project_id: str,
    has_scenarios: bool,
    has_feasibility_runs: bool,
    has_calculated_feasibility: bool,
    has_phases: bool,
    has_construction_records: bool,
    has_approved_tender_baseline: bool,
    has_portfolio_visibility: bool,
) -> tuple[str, str, str | None, str | None]:
    """Derive lifecycle stage and recommended next step from module presence flags.

    Returns a tuple of:
      (current_stage, recommended_next_step, next_step_route, blocked_reason)

    Stages progress in the following order:
      land_defined → scenario_defined → feasibility_ready →
      feasibility_calculated → structure_ready →
      construction_baseline_pending → construction_monitored →
      portfolio_visible

    Rules are deterministic and based only on flag arguments.

    portfolio_visible requires both has_approved_tender_baseline AND
    has_construction_records — meaning the project is fully governed and
    has active cost data eligible for portfolio roll-up.
    """
    if has_portfolio_visibility:
        return (
            "portfolio_visible",
            "View this project in portfolio monitoring.",
            "/portfolio",
            None,
        )

    if has_approved_tender_baseline:
        return (
            "construction_monitored",
            "Load construction cost records to enable portfolio-level monitoring.",
            f"/projects/{project_id}/construction-costs",
            None,
        )

    if has_construction_records and not has_approved_tender_baseline:
        return (
            "construction_baseline_pending",
            "Approve a tender baseline to unlock construction monitoring.",
            f"/projects/{project_id}/tender-comparisons",
            "No approved tender baseline exists for this project.",
        )

    if has_phases:
        return (
            "structure_ready",
            "Add construction cost records to begin cost tracking.",
            f"/projects/{project_id}/construction-costs",
            None,
        )

    if has_calculated_feasibility:
        return (
            "feasibility_calculated",
            "Define project structure (phases, buildings, units) to continue.",
            f"/projects/{project_id}/structure",
            None,
        )

    if has_feasibility_runs:
        return (
            "feasibility_ready",
            "Run feasibility calculation to evaluate viability.",
            f"/feasibility",
            "Feasibility run exists but has not been calculated yet.",
        )

    if has_scenarios:
        return (
            "scenario_defined",
            "Create a feasibility run to evaluate the scenario.",
            f"/feasibility",
            None,
        )

    return (
        "land_defined",
        "Create a development scenario to begin planning.",
        f"/scenarios",
        None,
    )
