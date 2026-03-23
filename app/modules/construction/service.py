"""
construction.service

Business logic for the Construction domain.

Validates project / phase / building linkage and enforces milestone
lifecycle rules within each scope.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.modules.construction.models import ConstructionMilestone, ConstructionMilestoneDependency
    from app.modules.construction.schedule_engine import SchedulePhase

from app.core.errors import ValidationError as DomainValidationError
from app.modules.buildings.repository import BuildingRepository
from app.modules.construction.exceptions import ConstructionConflictError
from app.modules.construction.repository import (
    ConstructionCostItemRepository,
    ConstructionDashboardRepository,
    ConstructionEngineeringItemRepository,
    ConstructionMilestoneRepository,
    ConstructionMilestoneDependencyRepository,
    ConstructionProgressUpdateRepository,
    ConstructionScopeRepository,
)
from app.modules.construction.schedule_engine import compute_schedule
from app.modules.construction.schemas import (
    ConstructionCostItemCreate,
    ConstructionCostItemList,
    ConstructionCostItemResponse,
    ConstructionCostItemUpdate,
    ConstructionCostSummary,
    ConstructionDashboardResponse,
    ConstructionDashboardScopeSummary,
    ConstructionMilestoneCreate,
    ConstructionMilestoneList,
    ConstructionMilestoneResponse,
    ConstructionMilestoneUpdate,
    ConstructionScopeCreate,
    ConstructionScopeList,
    ConstructionScopeResponse,
    ConstructionScopeUpdate,
    CriticalPathResponse,
    EngineeringItemCreate,
    EngineeringItemList,
    EngineeringItemResponse,
    EngineeringItemUpdate,
    MilestoneCostRow,
    MilestoneCostUpdate,
    MilestoneDependencyCreate,
    MilestoneDependencyList,
    MilestoneDependencyResponse,
    MilestoneProgressRow,
    MilestoneProgressUpdate,
    MilestoneVarianceRow,
    ProgressUpdateCreate,
    ProgressUpdateList,
    ProgressUpdateResponse,
    SchedulePhaseRow,
    ScopeMilestoneCostResponse,
    ScopeProgressResponse,
    ScopeScheduleResponse,
    ScopeVarianceResponse,
)
from app.modules.phases.repository import PhaseRepository
from app.modules.projects.repository import ProjectRepository


class ConstructionService:
    def __init__(self, db: Session) -> None:
        self.scope_repo = ConstructionScopeRepository(db)
        self.milestone_repo = ConstructionMilestoneRepository(db)
        self.engineering_repo = ConstructionEngineeringItemRepository(db)
        self.progress_repo = ConstructionProgressUpdateRepository(db)
        self.cost_repo = ConstructionCostItemRepository(db)
        self.dashboard_repo = ConstructionDashboardRepository(db)
        self.dependency_repo = ConstructionMilestoneDependencyRepository(db)
        self.project_repo = ProjectRepository(db)
        self.phase_repo = PhaseRepository(db)
        self.building_repo = BuildingRepository(db)

    # ── Scope operations ─────────────────────────────────────────────────────

    def create_scope(self, data: ConstructionScopeCreate) -> ConstructionScopeResponse:
        self._validate_links(data.project_id, data.phase_id, data.building_id)

        existing = self.scope_repo.get_by_links(
            data.project_id, data.phase_id, data.building_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A construction scope already exists for the given project/phase/building combination.",
            )

        try:
            scope = self.scope_repo.create(data)
        except IntegrityError:
            self.scope_repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A construction scope already exists for the given project/phase/building combination.",
            )
        return ConstructionScopeResponse.model_validate(scope)

    def list_scopes(
        self,
        project_id: str | None = None,
        phase_id: str | None = None,
        building_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> ConstructionScopeList:
        scopes = self.scope_repo.list(
            project_id=project_id,
            phase_id=phase_id,
            building_id=building_id,
            skip=skip,
            limit=limit,
        )
        total = self.scope_repo.count(
            project_id=project_id,
            phase_id=phase_id,
            building_id=building_id,
        )
        return ConstructionScopeList(
            items=[ConstructionScopeResponse.model_validate(s) for s in scopes],
            total=total,
        )

    def get_scope(self, scope_id: str) -> ConstructionScopeResponse:
        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )
        return ConstructionScopeResponse.model_validate(scope)

    def update_scope(self, scope_id: str, data: ConstructionScopeUpdate) -> ConstructionScopeResponse:
        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )
        updated = self.scope_repo.update(scope, data)
        return ConstructionScopeResponse.model_validate(updated)

    def delete_scope(self, scope_id: str) -> None:
        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )
        self.scope_repo.delete(scope)

    # ── Milestone operations ─────────────────────────────────────────────────

    def create_milestone(self, data: ConstructionMilestoneCreate) -> ConstructionMilestoneResponse:
        scope = self.scope_repo.get_by_id(data.scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{data.scope_id}' not found.",
            )
        existing = self.milestone_repo.get_by_scope_and_sequence(data.scope_id, data.sequence)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A milestone with sequence {data.sequence} already exists in scope '{data.scope_id}'.",
            )
        try:
            milestone = self.milestone_repo.create(data)
        except IntegrityError:
            self.milestone_repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A milestone with sequence {data.sequence} already exists in scope '{data.scope_id}'.",
            )
        return ConstructionMilestoneResponse.model_validate(milestone)

    def list_milestones(
        self,
        scope_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> ConstructionMilestoneList:
        milestones = self.milestone_repo.list(scope_id=scope_id, skip=skip, limit=limit)
        total = self.milestone_repo.count(scope_id=scope_id)
        return ConstructionMilestoneList(
            items=[ConstructionMilestoneResponse.model_validate(m) for m in milestones],
            total=total,
        )

    def get_milestone(self, milestone_id: str) -> ConstructionMilestoneResponse:
        milestone = self.milestone_repo.get_by_id(milestone_id)
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction milestone '{milestone_id}' not found.",
            )
        return ConstructionMilestoneResponse.model_validate(milestone)

    def update_milestone(self, milestone_id: str, data: ConstructionMilestoneUpdate) -> ConstructionMilestoneResponse:
        milestone = self.milestone_repo.get_by_id(milestone_id)
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction milestone '{milestone_id}' not found.",
            )
        # Validate sequence uniqueness if it changed
        if data.sequence is not None and data.sequence != milestone.sequence:
            existing = self.milestone_repo.get_by_scope_and_sequence(milestone.scope_id, data.sequence)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A milestone with sequence {data.sequence} already exists in scope '{milestone.scope_id}'.",
                )
        try:
            updated = self.milestone_repo.update(milestone, data)
        except IntegrityError:
            self.milestone_repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A milestone with sequence {data.sequence} already exists in scope '{milestone.scope_id}'.",
            )
        return ConstructionMilestoneResponse.model_validate(updated)

    def delete_milestone(self, milestone_id: str) -> None:
        milestone = self.milestone_repo.get_by_id(milestone_id)
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction milestone '{milestone_id}' not found.",
            )
        self.milestone_repo.delete(milestone)

    # ── Engineering item operations ──────────────────────────────────────────

    def create_engineering_item(
        self, scope_id: str, data: EngineeringItemCreate
    ) -> EngineeringItemResponse:
        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )
        try:
            item = self.engineering_repo.create(scope_id, data)
        except IntegrityError:
            self.engineering_repo.db.rollback()
            raise ConstructionConflictError("Construction engineering item integrity error")
        return EngineeringItemResponse.model_validate(item)

    def list_engineering_items(
        self,
        scope_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> EngineeringItemList:
        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )
        items = self.engineering_repo.list(scope_id=scope_id, skip=skip, limit=limit)
        total = self.engineering_repo.count(scope_id=scope_id)
        return EngineeringItemList(
            items=[EngineeringItemResponse.model_validate(i) for i in items],
            total=total,
        )

    def get_engineering_item(self, item_id: str) -> EngineeringItemResponse:
        item = self.engineering_repo.get_by_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engineering item '{item_id}' not found.",
            )
        return EngineeringItemResponse.model_validate(item)

    def update_engineering_item(
        self, item_id: str, data: EngineeringItemUpdate
    ) -> EngineeringItemResponse:
        item = self.engineering_repo.get_by_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engineering item '{item_id}' not found.",
            )
        try:
            updated = self.engineering_repo.update(item, data)
        except IntegrityError:
            self.engineering_repo.db.rollback()
            raise ConstructionConflictError("Construction engineering item integrity error")
        return EngineeringItemResponse.model_validate(updated)

    def delete_engineering_item(self, item_id: str) -> None:
        item = self.engineering_repo.get_by_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engineering item '{item_id}' not found.",
            )
        self.engineering_repo.delete(item)

    # ── Progress update operations ───────────────────────────────────────────

    def create_progress_update(
        self, milestone_id: str, data: ProgressUpdateCreate
    ) -> ProgressUpdateResponse:
        milestone = self.milestone_repo.get_by_id(milestone_id)
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction milestone '{milestone_id}' not found.",
            )
        update = self.progress_repo.create(milestone_id, data)
        return ProgressUpdateResponse.model_validate(update)

    def list_progress_updates(
        self,
        milestone_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> ProgressUpdateList:
        milestone = self.milestone_repo.get_by_id(milestone_id)
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction milestone '{milestone_id}' not found.",
            )
        updates = self.progress_repo.list(milestone_id=milestone_id, skip=skip, limit=limit)
        total = self.progress_repo.count(milestone_id=milestone_id)
        return ProgressUpdateList(
            items=[ProgressUpdateResponse.model_validate(u) for u in updates],
            total=total,
        )

    def get_progress_update(self, update_id: str) -> ProgressUpdateResponse:
        update = self.progress_repo.get_by_id(update_id)
        if not update:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Progress update '{update_id}' not found.",
            )
        return ProgressUpdateResponse.model_validate(update)

    def delete_progress_update(self, update_id: str) -> None:
        update = self.progress_repo.get_by_id(update_id)
        if not update:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Progress update '{update_id}' not found.",
            )
        self.progress_repo.delete(update)

    # ── Cost item operations ─────────────────────────────────────────────────

    def create_cost_item(
        self, scope_id: str, data: ConstructionCostItemCreate
    ) -> ConstructionCostItemResponse:
        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )
        item = self.cost_repo.create(scope_id, data)
        return ConstructionCostItemResponse.from_orm_with_variance(item)

    def list_cost_items(
        self,
        scope_id: str,
        skip: int = 0,
        limit: int = 100,
        category: str | None = None,
    ) -> ConstructionCostItemList:
        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )
        items = self.cost_repo.list(scope_id=scope_id, skip=skip, limit=limit, category=category)
        total = self.cost_repo.count(scope_id=scope_id, category=category)
        return ConstructionCostItemList(
            items=[ConstructionCostItemResponse.from_orm_with_variance(i) for i in items],
            total=total,
        )

    def get_cost_item(self, cost_item_id: str) -> ConstructionCostItemResponse:
        item = self.cost_repo.get_by_id(cost_item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction cost item '{cost_item_id}' not found.",
            )
        return ConstructionCostItemResponse.from_orm_with_variance(item)

    def update_cost_item(
        self, cost_item_id: str, data: ConstructionCostItemUpdate
    ) -> ConstructionCostItemResponse:
        from decimal import Decimal as D

        item = self.cost_repo.get_by_id(cost_item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction cost item '{cost_item_id}' not found.",
            )

        # Compute merged amounts to enforce the "at least one non-zero" invariant
        update_fields = data.model_dump(exclude_unset=True)
        D_ZERO = D("0.00")

        def _merged(field: str, existing) -> D:
            val = update_fields[field] if field in update_fields else existing
            return val if val is not None else D_ZERO

        merged_budget = _merged("budget_amount", item.budget_amount)
        merged_committed = _merged("committed_amount", item.committed_amount)
        merged_actual = _merged("actual_amount", item.actual_amount)
        if merged_budget == 0 and merged_committed == 0 and merged_actual == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="At least one of budget_amount, committed_amount, or actual_amount must be non-zero.",
            )

        updated = self.cost_repo.update(item, data)
        return ConstructionCostItemResponse.from_orm_with_variance(updated)

    def delete_cost_item(self, cost_item_id: str) -> None:
        item = self.cost_repo.get_by_id(cost_item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction cost item '{cost_item_id}' not found.",
            )
        self.cost_repo.delete(item)

    def get_scope_cost_summary(self, scope_id: str) -> ConstructionCostSummary:
        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )

        total_budget, total_committed, total_actual = self.cost_repo.get_scope_totals(scope_id)
        category_rows = self.cost_repo.get_scope_totals_by_category(scope_id)

        by_category: dict = {}
        for cat, (b, c, a) in category_rows.items():
            by_category[cat] = {
                "budget": b,
                "committed": c,
                "actual": a,
                "variance_to_budget": a - b,
                "variance_to_commitment": a - c,
            }

        return ConstructionCostSummary(
            scope_id=scope_id,
            total_budget=total_budget,
            total_committed=total_committed,
            total_actual=total_actual,
            total_variance_to_budget=total_actual - total_budget,
            total_variance_to_commitment=total_actual - total_committed,
            by_category=by_category,
        )

    # ── Dashboard ────────────────────────────────────────────────────────────

    def get_project_construction_dashboard(
        self, project_id: str
    ) -> ConstructionDashboardResponse:
        from datetime import date

        project = self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )

        scopes = self.dashboard_repo.list_scopes_for_project(project_id)
        scope_ids = [s.id for s in scopes]

        today = date.today()
        eng_counts = self.dashboard_repo.count_engineering_items_by_scope(scope_ids)
        milestone_counts = self.dashboard_repo.count_milestones_by_scope(scope_ids)
        overdue_counts = self.dashboard_repo.count_overdue_milestones_by_scope(scope_ids, today)
        progress_map = self.dashboard_repo.latest_progress_by_scope(scope_ids)
        cost_map = self.dashboard_repo.cost_summary_by_scope(scope_ids)

        scope_summaries: list[ConstructionDashboardScopeSummary] = []
        total_budget = Decimal("0.00")
        total_committed = Decimal("0.00")
        total_actual = Decimal("0.00")
        scopes_active = 0

        for scope in scopes:
            sid = scope.id
            eng_total, eng_open, eng_completed = eng_counts.get(sid, (0, 0, 0))
            ms_total, ms_completed = milestone_counts.get(sid, (0, 0))
            ms_overdue = overdue_counts.get(sid, 0)
            latest_progress = progress_map.get(sid)
            s_budget, s_committed, s_actual = cost_map.get(
                sid, (Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))
            )

            is_active = (
                eng_open > 0
                or ms_total > ms_completed
                or s_budget > Decimal("0.00")
                or s_committed > Decimal("0.00")
                or s_actual > Decimal("0.00")
            )
            if is_active:
                scopes_active += 1

            total_budget += s_budget
            total_committed += s_committed
            total_actual += s_actual

            scope_summaries.append(
                ConstructionDashboardScopeSummary(
                    scope_id=sid,
                    scope_name=scope.name,
                    engineering_items_total=eng_total,
                    engineering_items_open=eng_open,
                    engineering_items_completed=eng_completed,
                    milestones_total=ms_total,
                    milestones_completed=ms_completed,
                    milestones_overdue=ms_overdue,
                    latest_progress_percent=latest_progress,
                    total_budget=s_budget,
                    total_committed=s_committed,
                    total_actual=s_actual,
                    variance_to_budget=s_actual - s_budget,
                    variance_to_commitment=s_actual - s_committed,
                )
            )

        eng_open_total = sum(s.engineering_items_open for s in scope_summaries)
        ms_overdue_total = sum(s.milestones_overdue for s in scope_summaries)

        return ConstructionDashboardResponse(
            project_id=project_id,
            scopes_total=len(scopes),
            scopes_active=scopes_active,
            engineering_items_open_total=eng_open_total,
            milestones_overdue_total=ms_overdue_total,
            total_budget=total_budget,
            total_committed=total_committed,
            total_actual=total_actual,
            variance_to_budget=total_actual - total_budget,
            variance_to_commitment=total_actual - total_committed,
            scopes=scope_summaries,
        )

    # ── Private helpers ──────────────────────────────────────────────────────

    def _validate_links(
        self,
        project_id: str | None,
        phase_id: str | None,
        building_id: str | None,
    ) -> None:
        """Verify that referenced project / phase / building actually exist."""
        if project_id:
            project = self.project_repo.get_by_id(project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project '{project_id}' not found.",
                )
        if phase_id:
            phase = self.phase_repo.get_by_id(phase_id)
            if not phase:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Phase '{phase_id}' not found.",
                )
        if building_id:
            building = self.building_repo.get_by_id(building_id)
            if not building:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Building '{building_id}' not found.",
                )

    # ── Dependency operations ─────────────────────────────────────────────────

    def create_dependency(
        self, data: MilestoneDependencyCreate
    ) -> MilestoneDependencyResponse:
        """Create a finish-to-start dependency between two milestones.

        Validates:
        - Both milestones exist.
        - Dependency pair is unique (no duplicates).
        - Resulting graph contains no cycles.
        """
        predecessor = self.milestone_repo.get_by_id(data.predecessor_id)
        if not predecessor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Predecessor milestone '{data.predecessor_id}' not found.",
            )
        successor = self.milestone_repo.get_by_id(data.successor_id)
        if not successor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Successor milestone '{data.successor_id}' not found.",
            )

        # Reject cross-scope dependencies — both milestones must share a scope
        if predecessor.scope_id != successor.scope_id:
            raise DomainValidationError(
                f"Predecessor milestone '{data.predecessor_id}' belongs to scope "
                f"'{predecessor.scope_id}', but successor milestone "
                f"'{data.successor_id}' belongs to scope '{successor.scope_id}'. "
                "Dependencies must connect milestones within the same scope."
            )

        existing = self.dependency_repo.get_by_pair(
            data.predecessor_id, data.successor_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Dependency from '{data.predecessor_id}' to "
                    f"'{data.successor_id}' already exists."
                ),
            )

        # Determine the shared scope for cycle validation.
        # Build a prospective graph combining existing deps + new dep for the scope.
        scope_id = successor.scope_id
        milestones = self.dependency_repo.get_milestones_with_dependencies(scope_id)
        existing_deps = self.dependency_repo.list_for_scope(scope_id)

        prospective_phases = self._build_schedule_phases(milestones, existing_deps)
        # Add the proposed dependency to check for cycles
        for sp in prospective_phases:
            if sp.phase_id == data.successor_id:
                if data.predecessor_id not in sp.predecessor_ids:
                    sp.predecessor_ids.append(data.predecessor_id)
                    sp.lag_days[data.predecessor_id] = data.lag_days
                break

        from app.modules.construction.schedule_engine import detect_cycle

        cycle = detect_cycle(prospective_phases)
        if cycle is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Adding this dependency would create a circular dependency: "
                    f"{' → '.join(cycle)}"
                ),
            )

        try:
            dep = self.dependency_repo.create(data)
        except IntegrityError:
            self.dependency_repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Dependency from '{data.predecessor_id}' to "
                    f"'{data.successor_id}' already exists."
                ),
            )
        return MilestoneDependencyResponse.model_validate(dep)

    def get_dependency(self, dependency_id: str) -> MilestoneDependencyResponse:
        dep = self.dependency_repo.get_by_id(dependency_id)
        if not dep:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dependency '{dependency_id}' not found.",
            )
        return MilestoneDependencyResponse.model_validate(dep)

    def list_dependencies_for_scope(self, scope_id: str) -> MilestoneDependencyList:
        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )
        deps = self.dependency_repo.list_for_scope(scope_id)
        return MilestoneDependencyList(
            items=[MilestoneDependencyResponse.model_validate(d) for d in deps],
            total=len(deps),
        )

    def delete_dependency(self, dependency_id: str) -> None:
        dep = self.dependency_repo.get_by_id(dependency_id)
        if not dep:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dependency '{dependency_id}' not found.",
            )
        self.dependency_repo.delete(dep)

    # ── Schedule operations ───────────────────────────────────────────────────

    def get_scope_schedule(self, scope_id: str) -> ScopeScheduleResponse:
        """Compute and return the full CPM schedule for a construction scope."""
        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )
        milestones = self.dependency_repo.get_milestones_with_dependencies(scope_id)
        deps = self.dependency_repo.list_for_scope(scope_id)
        schedule_phases = self._build_schedule_phases(milestones, deps)

        try:
            output = compute_schedule(schedule_phases)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            )

        id_to_name = {m.id: m.name for m in milestones}
        id_to_duration = {m.id: (m.duration_days or 0) for m in milestones}
        rows = [
            SchedulePhaseRow(
                milestone_id=r.phase_id,
                milestone_name=id_to_name.get(r.phase_id, r.phase_id),
                duration_days=id_to_duration.get(r.phase_id, 0),
                earliest_start=r.earliest_start,
                earliest_finish=r.earliest_finish,
                latest_start=r.latest_start,
                latest_finish=r.latest_finish,
                total_float=r.total_float,
                is_critical=r.is_critical,
                delay_days=r.delay_days,
            )
            for r in output.phases
        ]
        return ScopeScheduleResponse(
            scope_id=scope_id,
            project_duration=output.project_duration,
            critical_path=output.critical_path,
            phases=rows,
        )

    def get_critical_path(self, scope_id: str) -> CriticalPathResponse:
        """Return the critical path summary for a construction scope."""
        schedule = self.get_scope_schedule(scope_id)
        critical_ids = schedule.critical_path
        id_to_name = {r.milestone_id: r.milestone_name for r in schedule.phases}
        return CriticalPathResponse(
            scope_id=scope_id,
            project_duration=schedule.project_duration,
            critical_path_milestone_ids=critical_ids,
            critical_path_milestone_names=[
                id_to_name.get(mid, mid) for mid in critical_ids
            ],
            total_phases=len(schedule.phases),
            critical_phases=len(critical_ids),
        )

    # ── Progress tracking operations ──────────────────────────────────────────

    def update_milestone_progress(
        self, milestone_id: str, data: MilestoneProgressUpdate
    ) -> ConstructionMilestoneResponse:
        """Update actual progress fields on a construction milestone."""
        from datetime import datetime, timezone

        milestone = self.milestone_repo.get_by_id(milestone_id)
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction milestone '{milestone_id}' not found.",
            )

        milestone.progress_percent = data.progress_percent
        if data.actual_start_day is not None:
            milestone.actual_start_day = data.actual_start_day
        if data.actual_finish_day is not None:
            milestone.actual_finish_day = data.actual_finish_day
        milestone.last_progress_update_at = datetime.now(timezone.utc)

        self.milestone_repo.db.commit()
        self.milestone_repo.db.refresh(milestone)
        return ConstructionMilestoneResponse.model_validate(milestone)

    def get_scope_progress(self, scope_id: str) -> ScopeProgressResponse:
        """Return aggregated progress overview for a construction scope."""
        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )

        milestones = self.milestone_repo.list(scope_id=scope_id)
        total = len(milestones)
        started = sum(
            1 for m in milestones if m.actual_start_day is not None
        )
        completed = sum(
            1 for m in milestones
            if (m.progress_percent is not None and m.progress_percent >= 100.0)
            or m.actual_finish_day is not None
        )

        if total > 0:
            overall_pct = sum(
                (m.progress_percent or 0.0) for m in milestones
            ) / total
        else:
            overall_pct = 0.0

        rows = [
            MilestoneProgressRow(
                milestone_id=m.id,
                milestone_name=m.name,
                sequence=m.sequence,
                progress_percent=m.progress_percent,
                actual_start_day=m.actual_start_day,
                actual_finish_day=m.actual_finish_day,
                last_progress_update_at=m.last_progress_update_at,
            )
            for m in milestones
        ]

        return ScopeProgressResponse(
            scope_id=scope_id,
            total_milestones=total,
            started_milestones=started,
            completed_milestones=completed,
            overall_completion_percent=round(overall_pct, 2),
            milestones=rows,
        )

    def get_scope_schedule_variance(self, scope_id: str) -> ScopeVarianceResponse:
        """Return schedule variance analysis for a construction scope."""
        from app.modules.construction.variance_engine import (
            MilestoneProgress,
            compute_variance,
        )

        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )

        # Load milestones and dependencies
        milestones = self.dependency_repo.get_milestones_with_dependencies(scope_id)
        deps = self.dependency_repo.list_for_scope(scope_id)

        # Compute the pure CPM planned schedule (without actual_start_day) so that
        # planned_start / planned_finish represent the original schedule baseline.
        planned_phases = self._build_schedule_phases_planned(milestones, deps)
        try:
            planned_output = compute_schedule(planned_phases)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            )

        planned_map = {r.phase_id: r for r in planned_output.phases}
        id_to_name = {m.id: m.name for m in milestones}

        # Load progress data from the full milestone list
        all_milestones = self.milestone_repo.list(scope_id=scope_id)
        progress_data = {m.id: m for m in all_milestones}

        # Build MilestoneProgress inputs using planned (unshifted) dates
        progress_inputs = []
        for m in milestones:
            if m.id not in planned_map:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Milestone '{m.id}' could not be scheduled — "
                        "ensure all milestones have valid duration_days and no circular dependencies."
                    ),
                )
            plan = planned_map[m.id]
            prog = progress_data.get(m.id)
            progress_inputs.append(
                MilestoneProgress(
                    milestone_id=m.id,
                    planned_start=plan.earliest_start,
                    planned_finish=plan.earliest_finish,
                    is_critical=plan.is_critical,
                    actual_start_day=prog.actual_start_day if prog else None,
                    actual_finish_day=prog.actual_finish_day if prog else None,
                    progress_percent=prog.progress_percent if prog else None,
                )
            )

        variance_result = compute_variance(
            scope_id=scope_id,
            milestones=progress_inputs,
            critical_path=planned_output.critical_path,
        )

        variance_rows = [
            MilestoneVarianceRow(
                milestone_id=vr.milestone_id,
                milestone_name=id_to_name.get(vr.milestone_id, vr.milestone_id),
                planned_start=vr.planned_start,
                planned_finish=vr.planned_finish,
                actual_start_day=vr.actual_start_day,
                actual_finish_day=vr.actual_finish_day,
                progress_percent=vr.progress_percent,
                schedule_variance_days=vr.schedule_variance_days,
                completion_variance_days=vr.completion_variance_days,
                milestone_status=vr.milestone_status.value,
                is_critical=vr.is_critical,
                risk_exposed=vr.risk_exposed,
            )
            for vr in variance_result.milestones
        ]

        return ScopeVarianceResponse(
            scope_id=scope_id,
            project_delay_days=variance_result.project_delay_days,
            critical_path_shift=variance_result.critical_path_shift,
            affected_milestones=variance_result.affected_milestones,
            milestones=variance_rows,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_schedule_phases(
        milestones: list["ConstructionMilestone"],
        deps: list["ConstructionMilestoneDependency"],
    ) -> list["SchedulePhase"]:
        """Convert ORM milestones and dependency records to SchedulePhase objects.

        Passes actual_start_day through so the effective schedule reflects
        any delays already recorded on milestones.
        """
        from app.modules.construction.schedule_engine import SchedulePhase

        dep_map: dict[str, list[tuple[str, int]]] = {}
        for d in deps:
            dep_map.setdefault(d.successor_id, []).append(
                (d.predecessor_id, d.lag_days)
            )

        phases: list[SchedulePhase] = []
        for m in milestones:
            predecessor_ids = [p for p, _ in dep_map.get(m.id, [])]
            lag_days = {p: lag for p, lag in dep_map.get(m.id, [])}
            phases.append(
                SchedulePhase(
                    phase_id=m.id,
                    duration_days=m.duration_days or 0,
                    predecessor_ids=predecessor_ids,
                    lag_days=lag_days,
                    actual_start_day=m.actual_start_day,
                )
            )
        return phases

    @staticmethod
    def _build_schedule_phases_planned(
        milestones: list["ConstructionMilestone"],
        deps: list["ConstructionMilestoneDependency"],
    ) -> list["SchedulePhase"]:
        """Build SchedulePhase objects using planned data only (no actual_start_day).

        Used to compute the pure CPM baseline for variance analysis so that
        planned_start / planned_finish are unaffected by actual progress.
        """
        from app.modules.construction.schedule_engine import SchedulePhase

        dep_map: dict[str, list[tuple[str, int]]] = {}
        for d in deps:
            dep_map.setdefault(d.successor_id, []).append(
                (d.predecessor_id, d.lag_days)
            )

        phases: list[SchedulePhase] = []
        for m in milestones:
            predecessor_ids = [p for p, _ in dep_map.get(m.id, [])]
            lag_days = {p: lag for p, lag in dep_map.get(m.id, [])}
            phases.append(
                SchedulePhase(
                    phase_id=m.id,
                    duration_days=m.duration_days or 0,
                    predecessor_ids=predecessor_ids,
                    lag_days=lag_days,
                    actual_start_day=None,
                )
            )
        return phases

    # ── Cost tracking operations ──────────────────────────────────────────────

    def update_milestone_cost(
        self, milestone_id: str, data: MilestoneCostUpdate
    ) -> ConstructionMilestoneResponse:
        """Update planned_cost and/or actual_cost on a construction milestone."""
        from datetime import datetime, timezone

        milestone = self.milestone_repo.get_by_id(milestone_id)
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction milestone '{milestone_id}' not found.",
            )

        if data.planned_cost is not None:
            milestone.planned_cost = data.planned_cost
        if data.actual_cost is not None:
            milestone.actual_cost = data.actual_cost
        milestone.cost_last_updated_at = datetime.now(timezone.utc)

        self.milestone_repo.db.commit()
        self.milestone_repo.db.refresh(milestone)
        return ConstructionMilestoneResponse.model_validate(milestone)

    def get_scope_milestone_cost(self, scope_id: str) -> ScopeMilestoneCostResponse:
        """Return milestone-level cost variance overview for a construction scope."""
        from app.modules.construction.cost_engine import MilestoneCostData, compute_cost_variance

        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )

        milestones = self.milestone_repo.list(scope_id=scope_id)

        cost_inputs = [
            MilestoneCostData(
                milestone_id=m.id,
                planned_cost=m.planned_cost,
                actual_cost=m.actual_cost,
            )
            for m in milestones
        ]

        result = compute_cost_variance(scope_id=scope_id, milestones=cost_inputs)

        id_to_milestone = {m.id: m for m in milestones}

        milestone_rows = [
            MilestoneCostRow(
                milestone_id=cv.milestone_id,
                milestone_name=id_to_milestone[cv.milestone_id].name,
                sequence=id_to_milestone[cv.milestone_id].sequence,
                planned_cost=cv.planned_cost,
                actual_cost=cv.actual_cost,
                cost_variance=cv.cost_variance,
                cost_variance_percent=cv.cost_variance_percent,
                cost_last_updated_at=id_to_milestone[cv.milestone_id].cost_last_updated_at,
            )
            for cv in result.milestones
        ]

        return ScopeMilestoneCostResponse(
            scope_id=scope_id,
            project_budget=result.project_budget,
            project_actual_cost=result.project_actual_cost,
            project_cost_variance=result.project_cost_variance,
            project_overrun_percent=result.project_overrun_percent,
            milestones=milestone_rows,
        )

