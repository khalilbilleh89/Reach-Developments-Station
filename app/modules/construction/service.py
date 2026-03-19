"""
construction.service

Business logic for the Construction domain.

Validates project / phase / building linkage and enforces milestone
lifecycle rules within each scope.
"""

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.buildings.repository import BuildingRepository
from app.modules.construction.exceptions import ConstructionConflictError
from app.modules.construction.repository import (
    ConstructionCostItemRepository,
    ConstructionDashboardRepository,
    ConstructionEngineeringItemRepository,
    ConstructionMilestoneRepository,
    ConstructionProgressUpdateRepository,
    ConstructionScopeRepository,
)
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
    EngineeringItemCreate,
    EngineeringItemList,
    EngineeringItemResponse,
    EngineeringItemUpdate,
    ProgressUpdateCreate,
    ProgressUpdateList,
    ProgressUpdateResponse,
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

