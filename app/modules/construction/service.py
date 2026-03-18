"""
construction.service

Business logic for the Construction domain.

Validates project / phase / building linkage and enforces milestone
lifecycle rules within each scope.
"""

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.buildings.repository import BuildingRepository
from app.modules.construction.exceptions import ConstructionConflictError
from app.modules.construction.repository import (
    ConstructionCostItemRepository,
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
        item = self.cost_repo.get_by_id(cost_item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction cost item '{cost_item_id}' not found.",
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
        from decimal import Decimal as D

        scope = self.scope_repo.get_by_id(scope_id)
        if not scope:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Construction scope '{scope_id}' not found.",
            )
        items = self.cost_repo.list(scope_id=scope_id, skip=0, limit=10000)

        total_budget = D("0.00")
        total_committed = D("0.00")
        total_actual = D("0.00")
        by_category: dict = {}

        for item in items:
            b = item.budget_amount or D("0.00")
            c = item.committed_amount or D("0.00")
            a = item.actual_amount or D("0.00")
            total_budget += b
            total_committed += c
            total_actual += a
            cat = item.cost_category
            if cat not in by_category:
                by_category[cat] = {
                    "budget": D("0.00"),
                    "committed": D("0.00"),
                    "actual": D("0.00"),
                }
            by_category[cat]["budget"] += b
            by_category[cat]["committed"] += c
            by_category[cat]["actual"] += a

        # Convert Decimal values to float for JSON serialisability in the dict
        for cat_data in by_category.values():
            cat_data["variance_to_budget"] = float(cat_data["actual"] - cat_data["budget"])
            cat_data["variance_to_commitment"] = float(cat_data["actual"] - cat_data["committed"])
            cat_data["budget"] = float(cat_data["budget"])
            cat_data["committed"] = float(cat_data["committed"])
            cat_data["actual"] = float(cat_data["actual"])

        return ConstructionCostSummary(
            scope_id=scope_id,
            total_budget=total_budget,
            total_committed=total_committed,
            total_actual=total_actual,
            total_variance_to_budget=total_actual - total_budget,
            total_variance_to_commitment=total_actual - total_committed,
            by_category=by_category,
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

