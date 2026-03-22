"""
scenario.service

Application-layer orchestration for the Scenario Engine lifecycle.

Rules enforced here:
  - Duplication creates a new Scenario with lineage and resets status to draft.
  - Only one ScenarioVersion per Scenario may be approved at a time.
  - Comparison is metadata-driven; no formulas are duplicated here.
  - Project creation from scenario is out of scope for this PR.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.scenario.repository import ScenarioRepository, ScenarioVersionRepository
from app.modules.scenario.schemas import (
    ScenarioCompareItem,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioCreate,
    ScenarioDuplicateRequest,
    ScenarioList,
    ScenarioResponse,
    ScenarioUpdate,
    ScenarioVersionCreate,
    ScenarioVersionList,
    ScenarioVersionResponse,
)
from app.core.constants.scenario import (
    ScenarioStatus,
    VALID_SOURCE_TYPES,
)
from app.core.errors import ResourceNotFoundError, ValidationError


class ScenarioService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.scenario_repo = ScenarioRepository(db)
        self.version_repo = ScenarioVersionRepository(db)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_scenario(self, scenario_id: str):
        scenario = self.scenario_repo.get_by_id(scenario_id)
        if not scenario:
            raise ResourceNotFoundError(
                f"Scenario '{scenario_id}' not found.",
                details={"scenario_id": scenario_id},
            )
        return scenario

    def _require_version(self, version_id: str):
        version = self.version_repo.get_by_id(version_id)
        if not version:
            raise ResourceNotFoundError(
                f"ScenarioVersion '{version_id}' not found.",
                details={"version_id": version_id},
            )
        return version

    # ------------------------------------------------------------------
    # Scenario CRUD
    # ------------------------------------------------------------------

    def create_scenario(self, data: ScenarioCreate) -> ScenarioResponse:
        if data.source_type not in VALID_SOURCE_TYPES:
            raise ValidationError(
                f"source_type must be one of: {sorted(VALID_SOURCE_TYPES)}.",
                details={"source_type": data.source_type},
            )
        scenario = self.scenario_repo.create(data)
        return ScenarioResponse.model_validate(scenario)

    def get_scenario(self, scenario_id: str) -> ScenarioResponse:
        scenario = self._require_scenario(scenario_id)
        return ScenarioResponse.model_validate(scenario)

    def list_scenarios(
        self,
        skip: int = 0,
        limit: int = 100,
        source_type: Optional[str] = None,
        project_id: Optional[str] = None,
        land_id: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> ScenarioList:
        items = self.scenario_repo.list_all(
            skip=skip,
            limit=limit,
            source_type=source_type,
            project_id=project_id,
            land_id=land_id,
            status=status_filter,
        )
        total = self.scenario_repo.count_all(
            source_type=source_type,
            project_id=project_id,
            land_id=land_id,
            status=status_filter,
        )
        return ScenarioList(
            items=[ScenarioResponse.model_validate(s) for s in items],
            total=total,
        )

    def update_scenario(self, scenario_id: str, data: ScenarioUpdate) -> ScenarioResponse:
        scenario = self._require_scenario(scenario_id)
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        if update_data:
            self.scenario_repo.update_fields(scenario, **update_data)
        return ScenarioResponse.model_validate(scenario)

    # ------------------------------------------------------------------
    # Duplication
    # ------------------------------------------------------------------

    def duplicate_scenario(
        self, scenario_id: str, request: ScenarioDuplicateRequest
    ) -> ScenarioResponse:
        """Create a new scenario derived from an existing one.

        The new scenario:
          - records lineage via base_scenario_id
          - starts with status=draft
          - copies the latest version assumptions as its first version
        """
        source = self._require_scenario(scenario_id)

        new_data = ScenarioCreate(
            name=request.name,
            code=request.code,
            source_type=source.source_type,
            project_id=source.project_id,
            land_id=source.land_id,
            notes=request.notes,
        )
        new_scenario = self.scenario_repo.create(new_data, base_scenario_id=source.id)

        # Copy the latest version assumptions as the first version of the duplicate.
        latest = self.version_repo.get_latest(scenario_id)
        if latest is not None:
            self.version_repo.create(
                new_scenario.id,
                ScenarioVersionCreate(
                    title=latest.title,
                    notes=f"Copied from scenario '{source.name}' v{latest.version_number}.",
                    assumptions_json=latest.assumptions_json,
                    comparison_metrics_json=None,
                ),
                created_by=latest.created_by,
            )

        return ScenarioResponse.model_validate(new_scenario)

    # ------------------------------------------------------------------
    # Approval / archival
    # ------------------------------------------------------------------

    def approve_scenario(self, scenario_id: str) -> ScenarioResponse:
        """Mark the scenario as approved.

        The latest version is marked as the approved version.
        All mutations are delegated to repository methods; a single db.commit()
        in this service method makes the full transition atomic so the DB is
        never left in a half-approved state.
        """
        scenario = self._require_scenario(scenario_id)
        if scenario.status == ScenarioStatus.ARCHIVED.value:
            raise ValidationError(
                "An archived scenario cannot be approved.",
                details={"scenario_id": scenario_id},
            )
        latest = self.version_repo.approve_latest(scenario_id)
        if latest is None:
            raise ValidationError(
                "Cannot approve a scenario with no versions.",
                details={"scenario_id": scenario_id},
            )
        self.scenario_repo.mark_approved(scenario)
        # Single commit: all three mutations (clear, approve, status) are atomic.
        self.db.commit()
        self.db.refresh(scenario)
        return ScenarioResponse.model_validate(scenario)

    def archive_scenario(self, scenario_id: str) -> ScenarioResponse:
        scenario = self._require_scenario(scenario_id)
        self.scenario_repo.update_status(scenario, ScenarioStatus.ARCHIVED.value)
        return ScenarioResponse.model_validate(scenario)

    # ------------------------------------------------------------------
    # Version operations
    # ------------------------------------------------------------------

    def create_version(
        self, scenario_id: str, data: ScenarioVersionCreate, created_by: Optional[str] = None
    ) -> ScenarioVersionResponse:
        self._require_scenario(scenario_id)
        version = self.version_repo.create(scenario_id, data, created_by=created_by)
        return ScenarioVersionResponse.model_validate(version)

    def list_versions(self, scenario_id: str) -> ScenarioVersionList:
        self._require_scenario(scenario_id)
        versions = self.version_repo.list_by_scenario(scenario_id)
        total = self.version_repo.count_by_scenario(scenario_id)
        return ScenarioVersionList(
            items=[ScenarioVersionResponse.model_validate(v) for v in versions],
            total=total,
        )

    def get_latest_version(self, scenario_id: str) -> ScenarioVersionResponse:
        self._require_scenario(scenario_id)
        latest = self.version_repo.get_latest(scenario_id)
        if latest is None:
            raise ResourceNotFoundError(
                f"No versions found for scenario '{scenario_id}'.",
                details={"scenario_id": scenario_id},
            )
        return ScenarioVersionResponse.model_validate(latest)

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare_scenarios(self, request: ScenarioCompareRequest) -> ScenarioCompareResponse:
        """Assemble side-by-side comparison metadata for a list of scenarios.

        Comparison is metadata-driven: assumptions and KPI outputs from each
        scenario's latest version are surfaced.  No formulas are duplicated
        here; calculation results should be stored in comparison_metrics_json
        by callers after running through the Calculation Engine.

        Latest versions are fetched in a single batch query (no N+1).
        Results are emitted in the same order as request.scenario_ids.
        """
        scenarios = self.scenario_repo.get_by_ids(request.scenario_ids)
        found_ids = {s.id for s in scenarios}
        missing = [sid for sid in request.scenario_ids if sid not in found_ids]
        if missing:
            raise ResourceNotFoundError(
                f"Scenarios not found: {missing}",
                details={"missing_ids": missing},
            )

        # Batch fetch all latest versions in one query.
        latest_by_id = self.version_repo.get_latest_for_ids(request.scenario_ids)

        # Build a map for O(1) lookup, then emit in request order.
        scenarios_by_id = {s.id: s for s in scenarios}
        items: List[ScenarioCompareItem] = []
        for sid in request.scenario_ids:
            scenario = scenarios_by_id[sid]
            latest = latest_by_id.get(sid)
            items.append(
                ScenarioCompareItem(
                    scenario_id=scenario.id,
                    scenario_name=scenario.name,
                    status=scenario.status,
                    latest_version_number=latest.version_number if latest else None,
                    assumptions_json=latest.assumptions_json if latest else None,
                    comparison_metrics_json=latest.comparison_metrics_json if latest else None,
                )
            )
        return ScenarioCompareResponse(scenarios=items)
