"""
construction.repository

Data access layer for the Construction domain.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from sqlalchemy import case, func, over, select
from sqlalchemy.orm import Session, selectinload

from app.modules.buildings.models import Building
from app.modules.construction.models import (
    ConstructionCostItem,
    ConstructionEngineeringItem,
    ConstructionMilestone,
    ConstructionMilestoneDependency,
    ConstructionProgressUpdate,
    ConstructionScope,
)
from app.modules.phases.models import Phase
from app.shared.enums.construction import EngineeringStatus, MilestoneStatus
from app.modules.construction.schemas import (
    ConstructionMilestoneCreate,
    ConstructionMilestoneUpdate,
    ConstructionScopeCreate,
    ConstructionScopeUpdate,
    EngineeringItemCreate,
    EngineeringItemUpdate,
    MilestoneDependencyCreate,
    ProgressUpdateCreate,
)

if TYPE_CHECKING:
    from app.modules.construction.models import (
        ConstructionContractor,
        ConstructionProcurementPackage,
    )
    from app.modules.construction.schemas import (
        ContractorCreate,
        ContractorUpdate,
        ProcurementPackageCreate,
        ProcurementPackageUpdate,
    )


class ConstructionScopeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: ConstructionScopeCreate) -> ConstructionScope:
        scope = ConstructionScope(**data.model_dump())
        self.db.add(scope)
        self.db.commit()
        self.db.refresh(scope)
        return scope

    def get_by_id(self, scope_id: str) -> Optional[ConstructionScope]:
        return (
            self.db.query(ConstructionScope)
            .filter(ConstructionScope.id == scope_id)
            .first()
        )

    def get_by_links(
        self,
        project_id: Optional[str],
        phase_id: Optional[str],
        building_id: Optional[str],
    ) -> Optional[ConstructionScope]:
        """Return an existing scope matching the given link combination."""
        return (
            self.db.query(ConstructionScope)
            .filter(
                ConstructionScope.project_id == project_id,
                ConstructionScope.phase_id == phase_id,
                ConstructionScope.building_id == building_id,
            )
            .first()
        )

    def list(
        self,
        project_id: Optional[str] = None,
        phase_id: Optional[str] = None,
        building_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConstructionScope]:
        query = self.db.query(ConstructionScope)
        if project_id:
            query = query.filter(ConstructionScope.project_id == project_id)
        if phase_id:
            query = query.filter(ConstructionScope.phase_id == phase_id)
        if building_id:
            query = query.filter(ConstructionScope.building_id == building_id)
        return query.order_by(ConstructionScope.name, ConstructionScope.id).offset(skip).limit(limit).all()

    def count(
        self,
        project_id: Optional[str] = None,
        phase_id: Optional[str] = None,
        building_id: Optional[str] = None,
    ) -> int:
        query = self.db.query(ConstructionScope)
        if project_id:
            query = query.filter(ConstructionScope.project_id == project_id)
        if phase_id:
            query = query.filter(ConstructionScope.phase_id == phase_id)
        if building_id:
            query = query.filter(ConstructionScope.building_id == building_id)
        return query.count()

    def update(self, scope: ConstructionScope, data: ConstructionScopeUpdate) -> ConstructionScope:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(scope, field, value)
        self.db.commit()
        self.db.refresh(scope)
        return scope

    def delete(self, scope: ConstructionScope) -> None:
        self.db.delete(scope)
        self.db.commit()


class ConstructionMilestoneRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: ConstructionMilestoneCreate) -> ConstructionMilestone:
        milestone = ConstructionMilestone(**data.model_dump())
        self.db.add(milestone)
        self.db.commit()
        self.db.refresh(milestone)
        return milestone

    def get_by_id(self, milestone_id: str) -> Optional[ConstructionMilestone]:
        return (
            self.db.query(ConstructionMilestone)
            .filter(ConstructionMilestone.id == milestone_id)
            .first()
        )

    def get_by_scope_and_sequence(self, scope_id: str, sequence: int) -> Optional[ConstructionMilestone]:
        return (
            self.db.query(ConstructionMilestone)
            .filter(
                ConstructionMilestone.scope_id == scope_id,
                ConstructionMilestone.sequence == sequence,
            )
            .first()
        )

    def list(
        self,
        scope_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConstructionMilestone]:
        query = self.db.query(ConstructionMilestone)
        if scope_id:
            query = query.filter(ConstructionMilestone.scope_id == scope_id)
        return query.order_by(ConstructionMilestone.scope_id, ConstructionMilestone.sequence).offset(skip).limit(limit).all()

    def list_all_for_scope(self, scope_id: str) -> List[ConstructionMilestone]:
        """Return all milestones for a scope without pagination.

        Used by aggregation workflows (e.g. cost variance) that must operate
        over the full milestone set to produce correct project-level totals.
        """
        return (
            self.db.query(ConstructionMilestone)
            .filter(ConstructionMilestone.scope_id == scope_id)
            .order_by(ConstructionMilestone.sequence)
            .all()
        )

    def count(self, scope_id: Optional[str] = None) -> int:
        query = self.db.query(ConstructionMilestone)
        if scope_id:
            query = query.filter(ConstructionMilestone.scope_id == scope_id)
        return query.count()

    def update(self, milestone: ConstructionMilestone, data: ConstructionMilestoneUpdate) -> ConstructionMilestone:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(milestone, field, value)
        self.db.commit()
        self.db.refresh(milestone)
        return milestone

    def delete(self, milestone: ConstructionMilestone) -> None:
        self.db.delete(milestone)
        self.db.commit()


class ConstructionEngineeringItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, scope_id: str, data: EngineeringItemCreate) -> ConstructionEngineeringItem:
        item = ConstructionEngineeringItem(scope_id=scope_id, **data.model_dump())
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_by_id(self, item_id: str) -> Optional[ConstructionEngineeringItem]:
        return (
            self.db.query(ConstructionEngineeringItem)
            .filter(ConstructionEngineeringItem.id == item_id)
            .first()
        )

    def list(
        self,
        scope_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConstructionEngineeringItem]:
        return (
            self.db.query(ConstructionEngineeringItem)
            .filter(ConstructionEngineeringItem.scope_id == scope_id)
            .order_by(ConstructionEngineeringItem.created_at, ConstructionEngineeringItem.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, scope_id: str) -> int:
        return (
            self.db.query(ConstructionEngineeringItem)
            .filter(ConstructionEngineeringItem.scope_id == scope_id)
            .count()
        )

    def update(
        self, item: ConstructionEngineeringItem, data: EngineeringItemUpdate
    ) -> ConstructionEngineeringItem:
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in update_data.items():
            setattr(item, field, value)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item: ConstructionEngineeringItem) -> None:
        self.db.delete(item)
        self.db.commit()


class ConstructionProgressUpdateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, milestone_id: str, data: ProgressUpdateCreate) -> ConstructionProgressUpdate:
        from datetime import datetime, timezone

        raw = data.reported_at
        if raw is None:
            reported_at = datetime.now(timezone.utc)
        elif raw.tzinfo is None:
            reported_at = raw.replace(tzinfo=timezone.utc)
        else:
            reported_at = raw.astimezone(timezone.utc)
        update = ConstructionProgressUpdate(
            milestone_id=milestone_id,
            progress_percent=data.progress_percent,
            status_note=data.status_note,
            reported_by=data.reported_by,
            reported_at=reported_at,
        )
        self.db.add(update)
        self.db.commit()
        self.db.refresh(update)
        return update

    def get_by_id(self, update_id: str) -> Optional[ConstructionProgressUpdate]:
        return (
            self.db.query(ConstructionProgressUpdate)
            .filter(ConstructionProgressUpdate.id == update_id)
            .first()
        )

    def list(
        self,
        milestone_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConstructionProgressUpdate]:
        return (
            self.db.query(ConstructionProgressUpdate)
            .filter(ConstructionProgressUpdate.milestone_id == milestone_id)
            .order_by(ConstructionProgressUpdate.reported_at, ConstructionProgressUpdate.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, milestone_id: str) -> int:
        return (
            self.db.query(ConstructionProgressUpdate)
            .filter(ConstructionProgressUpdate.milestone_id == milestone_id)
            .count()
        )

    def delete(self, update: ConstructionProgressUpdate) -> None:
        self.db.delete(update)
        self.db.commit()


class ConstructionCostItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, scope_id: str, data) -> "ConstructionCostItem":
        from app.modules.construction.models import ConstructionCostItem

        item = ConstructionCostItem(scope_id=scope_id, **data.model_dump())
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_by_id(self, cost_item_id: str) -> Optional["ConstructionCostItem"]:
        from app.modules.construction.models import ConstructionCostItem

        return (
            self.db.query(ConstructionCostItem)
            .filter(ConstructionCostItem.id == cost_item_id)
            .first()
        )

    def list(
        self,
        scope_id: str,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
    ) -> List["ConstructionCostItem"]:
        from app.modules.construction.models import ConstructionCostItem

        query = self.db.query(ConstructionCostItem).filter(
            ConstructionCostItem.scope_id == scope_id
        )
        if category:
            query = query.filter(ConstructionCostItem.cost_category == category)
        return (
            query.order_by(ConstructionCostItem.created_at, ConstructionCostItem.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, scope_id: str, category: Optional[str] = None) -> int:
        from app.modules.construction.models import ConstructionCostItem

        query = self.db.query(ConstructionCostItem).filter(
            ConstructionCostItem.scope_id == scope_id
        )
        if category:
            query = query.filter(ConstructionCostItem.cost_category == category)
        return query.count()

    def update(self, item: "ConstructionCostItem", data) -> "ConstructionCostItem":
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item: "ConstructionCostItem") -> None:
        self.db.delete(item)
        self.db.commit()

    def get_scope_totals(
        self, scope_id: str
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """Return (total_budget, total_committed, total_actual) for a scope via DB SUM."""
        from app.modules.construction.models import ConstructionCostItem

        row = (
            self.db.query(
                func.coalesce(func.sum(ConstructionCostItem.budget_amount), 0).label("budget"),
                func.coalesce(func.sum(ConstructionCostItem.committed_amount), 0).label("committed"),
                func.coalesce(func.sum(ConstructionCostItem.actual_amount), 0).label("actual"),
            )
            .filter(ConstructionCostItem.scope_id == scope_id)
            .one()
        )
        return (
            Decimal(str(row.budget)),
            Decimal(str(row.committed)),
            Decimal(str(row.actual)),
        )

    def get_scope_totals_by_category(
        self, scope_id: str
    ) -> Dict[str, Tuple[Decimal, Decimal, Decimal]]:
        """Return per-category (budget, committed, actual) sums via DB GROUP BY."""
        from app.modules.construction.models import ConstructionCostItem

        rows = (
            self.db.query(
                ConstructionCostItem.cost_category,
                func.coalesce(func.sum(ConstructionCostItem.budget_amount), 0).label("budget"),
                func.coalesce(func.sum(ConstructionCostItem.committed_amount), 0).label("committed"),
                func.coalesce(func.sum(ConstructionCostItem.actual_amount), 0).label("actual"),
            )
            .filter(ConstructionCostItem.scope_id == scope_id)
            .group_by(ConstructionCostItem.cost_category)
            .all()
        )
        return {
            row.cost_category: (
                Decimal(str(row.budget)),
                Decimal(str(row.committed)),
                Decimal(str(row.actual)),
            )
            for row in rows
        }


class ConstructionDashboardRepository:
    """Read-only aggregation helpers for the construction dashboard."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_scopes_for_project(self, project_id: str) -> List[ConstructionScope]:
        """Return all construction scopes that belong to a project.

        Includes scopes linked at any level of the hierarchy:
          - directly via ConstructionScope.project_id
          - indirectly via ConstructionScope.phase_id → Phase.project_id
          - indirectly via ConstructionScope.building_id → Building.phase_id → Phase.project_id
        """
        phase_ids = select(Phase.id).where(Phase.project_id == project_id)
        building_ids = (
            select(Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .where(Phase.project_id == project_id)
        )

        return (
            self.db.query(ConstructionScope)
            .filter(
                (ConstructionScope.project_id == project_id)
                | ConstructionScope.phase_id.in_(phase_ids)
                | ConstructionScope.building_id.in_(building_ids)
            )
            .order_by(ConstructionScope.name, ConstructionScope.id)
            .all()
        )

    def count_engineering_items_by_scope(
        self, scope_ids: List[str]
    ) -> Dict[str, Tuple[int, int, int]]:
        """Return {scope_id: (total, open, completed)} via DB GROUP BY.

        ``open`` is defined as status != 'completed'.
        """
        if not scope_ids:
            return {}

        completed_val = EngineeringStatus.COMPLETED.value
        rows = (
            self.db.query(
                ConstructionEngineeringItem.scope_id,
                func.count(ConstructionEngineeringItem.id).label("total"),
                func.sum(
                    case(
                        (ConstructionEngineeringItem.status == completed_val, 1),
                        else_=0,
                    )
                ).label("completed"),
            )
            .filter(ConstructionEngineeringItem.scope_id.in_(scope_ids))
            .group_by(ConstructionEngineeringItem.scope_id)
            .all()
        )
        result: Dict[str, Tuple[int, int, int]] = {sid: (0, 0, 0) for sid in scope_ids}
        for row in rows:
            total = int(row.total)
            completed = int(row.completed or 0)
            result[row.scope_id] = (total, total - completed, completed)
        return result

    def count_milestones_by_scope(
        self, scope_ids: List[str]
    ) -> Dict[str, Tuple[int, int]]:
        """Return {scope_id: (total, completed)} via DB GROUP BY."""
        if not scope_ids:
            return {}

        completed_val = MilestoneStatus.COMPLETED.value
        rows = (
            self.db.query(
                ConstructionMilestone.scope_id,
                func.count(ConstructionMilestone.id).label("total"),
                func.sum(
                    case(
                        (ConstructionMilestone.status == completed_val, 1),
                        else_=0,
                    )
                ).label("completed"),
            )
            .filter(ConstructionMilestone.scope_id.in_(scope_ids))
            .group_by(ConstructionMilestone.scope_id)
            .all()
        )
        result: Dict[str, Tuple[int, int]] = {sid: (0, 0) for sid in scope_ids}
        for row in rows:
            result[row.scope_id] = (int(row.total), int(row.completed or 0))
        return result

    def count_overdue_milestones_by_scope(
        self, scope_ids: List[str], today: date
    ) -> Dict[str, int]:
        """Return {scope_id: overdue_count}.

        A milestone is overdue when its target_date is before *today* and its
        status is not ``completed``.
        """
        if not scope_ids:
            return {}

        completed_val = MilestoneStatus.COMPLETED.value
        rows = (
            self.db.query(
                ConstructionMilestone.scope_id,
                func.count(ConstructionMilestone.id).label("overdue"),
            )
            .filter(
                ConstructionMilestone.scope_id.in_(scope_ids),
                ConstructionMilestone.target_date < today,
                ConstructionMilestone.status != completed_val,
            )
            .group_by(ConstructionMilestone.scope_id)
            .all()
        )
        result: Dict[str, int] = {sid: 0 for sid in scope_ids}
        for row in rows:
            result[row.scope_id] = int(row.overdue)
        return result

    def latest_progress_by_scope(
        self, scope_ids: List[str]
    ) -> Dict[str, Optional[int]]:
        """Return {scope_id: latest_progress_percent}.

        Uses a window function to determine the latest progress update per scope
        at the DB level, ordered by ``reported_at desc, id desc`` for a
        deterministic tie-breaker.  Returns ``None`` for scopes that have no
        progress updates.
        """
        if not scope_ids:
            return {}

        row_num = over(
            func.row_number(),
            partition_by=ConstructionMilestone.scope_id,
            order_by=[
                ConstructionProgressUpdate.reported_at.desc(),
                ConstructionProgressUpdate.id.desc(),
            ],
        ).label("rn")

        inner = (
            self.db.query(
                ConstructionMilestone.scope_id,
                ConstructionProgressUpdate.progress_percent,
                row_num,
            )
            .join(
                ConstructionProgressUpdate,
                ConstructionProgressUpdate.milestone_id == ConstructionMilestone.id,
            )
            .filter(ConstructionMilestone.scope_id.in_(scope_ids))
            .subquery()
        )

        rows = (
            self.db.query(inner.c.scope_id, inner.c.progress_percent)
            .filter(inner.c.rn == 1)
            .all()
        )

        result: Dict[str, Optional[int]] = {sid: None for sid in scope_ids}
        for row in rows:
            result[row.scope_id] = int(row.progress_percent)
        return result

    def cost_summary_by_scope(
        self, scope_ids: List[str]
    ) -> Dict[str, Tuple[Decimal, Decimal, Decimal]]:
        """Return {scope_id: (total_budget, total_committed, total_actual)} via DB SUM."""
        if not scope_ids:
            return {}

        rows = (
            self.db.query(
                ConstructionCostItem.scope_id,
                func.coalesce(func.sum(ConstructionCostItem.budget_amount), 0).label("budget"),
                func.coalesce(func.sum(ConstructionCostItem.committed_amount), 0).label("committed"),
                func.coalesce(func.sum(ConstructionCostItem.actual_amount), 0).label("actual"),
            )
            .filter(ConstructionCostItem.scope_id.in_(scope_ids))
            .group_by(ConstructionCostItem.scope_id)
            .all()
        )
        result: Dict[str, Tuple[Decimal, Decimal, Decimal]] = {
            sid: (Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))
            for sid in scope_ids
        }
        for row in rows:
            result[row.scope_id] = (
                Decimal(str(row.budget)),
                Decimal(str(row.committed)),
                Decimal(str(row.actual)),
            )
        return result


class ConstructionMilestoneDependencyRepository:
    """Persistence and retrieval for construction milestone dependencies."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: MilestoneDependencyCreate) -> ConstructionMilestoneDependency:
        dep = ConstructionMilestoneDependency(
            predecessor_id=data.predecessor_id,
            successor_id=data.successor_id,
            lag_days=data.lag_days,
        )
        self.db.add(dep)
        self.db.commit()
        self.db.refresh(dep)
        return dep

    def get_by_id(self, dependency_id: str) -> Optional[ConstructionMilestoneDependency]:
        return (
            self.db.query(ConstructionMilestoneDependency)
            .filter(ConstructionMilestoneDependency.id == dependency_id)
            .first()
        )

    def get_by_pair(
        self, predecessor_id: str, successor_id: str
    ) -> Optional[ConstructionMilestoneDependency]:
        """Return an existing dependency for the given predecessor/successor pair."""
        return (
            self.db.query(ConstructionMilestoneDependency)
            .filter(
                ConstructionMilestoneDependency.predecessor_id == predecessor_id,
                ConstructionMilestoneDependency.successor_id == successor_id,
            )
            .first()
        )

    def list_for_scope(self, scope_id: str) -> List[ConstructionMilestoneDependency]:
        """Return all dependencies where BOTH predecessor and successor belong to the scope.

        Using AND (not OR) ensures schedule computation only sees fully
        in-scope edges and is not polluted by any cross-scope records.
        """
        from sqlalchemy import select as sa_select

        milestone_ids_subq = sa_select(ConstructionMilestone.id).where(
            ConstructionMilestone.scope_id == scope_id
        )
        return (
            self.db.query(ConstructionMilestoneDependency)
            .filter(
                ConstructionMilestoneDependency.predecessor_id.in_(milestone_ids_subq)
                & ConstructionMilestoneDependency.successor_id.in_(milestone_ids_subq)
            )
            .order_by(
                ConstructionMilestoneDependency.predecessor_id,
                ConstructionMilestoneDependency.successor_id,
            )
            .all()
        )

    def list_for_milestone(
        self, milestone_id: str
    ) -> List[ConstructionMilestoneDependency]:
        """Return all dependencies where the milestone is predecessor or successor."""
        return (
            self.db.query(ConstructionMilestoneDependency)
            .filter(
                (ConstructionMilestoneDependency.predecessor_id == milestone_id)
                | (ConstructionMilestoneDependency.successor_id == milestone_id)
            )
            .all()
        )

    def get_milestones_with_dependencies(
        self, scope_id: str
    ) -> List[ConstructionMilestone]:
        """Return all milestones for a scope (for schedule computation)."""
        return (
            self.db.query(ConstructionMilestone)
            .filter(ConstructionMilestone.scope_id == scope_id)
            .order_by(ConstructionMilestone.sequence)
            .all()
        )

    def delete(self, dep: ConstructionMilestoneDependency) -> None:
        self.db.delete(dep)
        self.db.commit()


class ConstructionContractorRepository:
    """Persistence and retrieval for construction contractors."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: ContractorCreate) -> ConstructionContractor:
        from app.modules.construction.models import ConstructionContractor

        contractor = ConstructionContractor(**data.model_dump())
        self.db.add(contractor)
        self.db.commit()
        self.db.refresh(contractor)
        return contractor

    def get_by_id(self, contractor_id: str) -> Optional[ConstructionContractor]:
        from app.modules.construction.models import ConstructionContractor

        return (
            self.db.query(ConstructionContractor)
            .filter(ConstructionContractor.id == contractor_id)
            .first()
        )

    def get_by_code(self, contractor_code: str) -> Optional[ConstructionContractor]:
        from app.modules.construction.models import ConstructionContractor

        return (
            self.db.query(ConstructionContractor)
            .filter(ConstructionContractor.contractor_code == contractor_code)
            .first()
        )

    def list(self, skip: int = 0, limit: int = 100) -> List[ConstructionContractor]:
        from app.modules.construction.models import ConstructionContractor

        return (
            self.db.query(ConstructionContractor)
            .order_by(ConstructionContractor.contractor_name, ConstructionContractor.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        from app.modules.construction.models import ConstructionContractor

        return self.db.query(ConstructionContractor).count()

    def update(
        self,
        contractor: ConstructionContractor,
        data: ContractorUpdate,
    ) -> ConstructionContractor:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(contractor, field, value)
        self.db.commit()
        self.db.refresh(contractor)
        return contractor

    def delete(self, contractor: ConstructionContractor) -> None:
        self.db.delete(contractor)
        self.db.commit()


class ConstructionProcurementPackageRepository:
    """Persistence and retrieval for construction procurement packages."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: ProcurementPackageCreate) -> ConstructionProcurementPackage:
        from app.modules.construction.models import ConstructionProcurementPackage

        package = ConstructionProcurementPackage(**data.model_dump())
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)
        return package

    def get_by_id(self, package_id: str) -> Optional[ConstructionProcurementPackage]:
        from app.modules.construction.models import ConstructionProcurementPackage

        return (
            self.db.query(ConstructionProcurementPackage)
            .filter(ConstructionProcurementPackage.id == package_id)
            .first()
        )

    def get_by_scope_and_code(
        self, scope_id: str, package_code: str
    ) -> Optional[ConstructionProcurementPackage]:
        from app.modules.construction.models import ConstructionProcurementPackage

        return (
            self.db.query(ConstructionProcurementPackage)
            .filter(
                ConstructionProcurementPackage.scope_id == scope_id,
                ConstructionProcurementPackage.package_code == package_code,
            )
            .first()
        )

    def list_for_scope(
        self, scope_id: str, skip: int = 0, limit: int = 100
    ) -> List[ConstructionProcurementPackage]:
        from app.modules.construction.models import ConstructionProcurementPackage

        return (
            self.db.query(ConstructionProcurementPackage)
            .filter(ConstructionProcurementPackage.scope_id == scope_id)
            .order_by(
                ConstructionProcurementPackage.package_code,
                ConstructionProcurementPackage.id,
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_all_for_scope(
        self, scope_id: str
    ) -> List[ConstructionProcurementPackage]:
        from app.modules.construction.models import ConstructionProcurementPackage

        return (
            self.db.query(ConstructionProcurementPackage)
            .filter(ConstructionProcurementPackage.scope_id == scope_id)
            .order_by(ConstructionProcurementPackage.package_code)
            .all()
        )

    def count_for_scope(self, scope_id: str) -> int:
        from app.modules.construction.models import ConstructionProcurementPackage

        return (
            self.db.query(ConstructionProcurementPackage)
            .filter(ConstructionProcurementPackage.scope_id == scope_id)
            .count()
        )

    def update(
        self,
        package: ConstructionProcurementPackage,
        data: ProcurementPackageUpdate,
    ) -> ConstructionProcurementPackage:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(package, field, value)
        self.db.commit()
        self.db.refresh(package)
        return package

    def assign_contractor(
        self, package: ConstructionProcurementPackage, contractor_id: Optional[str]
    ) -> ConstructionProcurementPackage:
        package.contractor_id = contractor_id
        self.db.commit()
        self.db.refresh(package)
        return package

    def link_milestone(
        self,
        package: ConstructionProcurementPackage,
        milestone: "ConstructionMilestone",
    ) -> None:
        if milestone not in package.milestones:
            package.milestones.append(milestone)
            self.db.commit()

    def unlink_milestone(
        self,
        package: ConstructionProcurementPackage,
        milestone: "ConstructionMilestone",
    ) -> None:
        if milestone in package.milestones:
            package.milestones.remove(milestone)
            self.db.commit()

    def list_milestones_for_package(
        self, package: ConstructionProcurementPackage
    ) -> List["ConstructionMilestone"]:
        return list(package.milestones)

    def delete(self, package: ConstructionProcurementPackage) -> None:
        self.db.delete(package)
        self.db.commit()


class ConstructionRiskRepository:
    """Read-only data loading for construction risk alert computation."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def load_scope_packages_with_milestones(
        self, scope_id: str
    ) -> List[ConstructionProcurementPackage]:
        """Return all packages for a scope with milestones eagerly loaded."""
        from app.modules.construction.models import ConstructionProcurementPackage

        return (
            self.db.query(ConstructionProcurementPackage)
            .options(selectinload(ConstructionProcurementPackage.milestones))
            .filter(ConstructionProcurementPackage.scope_id == scope_id)
            .order_by(ConstructionProcurementPackage.package_code)
            .all()
        )

    def load_contractor_packages_with_milestones(
        self, contractor_id: str
    ) -> List[ConstructionProcurementPackage]:
        """Return all packages assigned to a contractor with milestones loaded."""
        from app.modules.construction.models import ConstructionProcurementPackage

        return (
            self.db.query(ConstructionProcurementPackage)
            .options(selectinload(ConstructionProcurementPackage.milestones))
            .filter(ConstructionProcurementPackage.contractor_id == contractor_id)
            .order_by(ConstructionProcurementPackage.package_code)
            .all()
        )

    def load_scope_contractor_ids(self, scope_id: str) -> List[str]:
        """Return the distinct contractor IDs linked to a scope via packages."""
        from app.modules.construction.models import ConstructionProcurementPackage

        rows = (
            self.db.query(ConstructionProcurementPackage.contractor_id)
            .filter(
                ConstructionProcurementPackage.scope_id == scope_id,
                ConstructionProcurementPackage.contractor_id.is_not(None),
            )
            .distinct()
            .all()
        )
        return [row[0] for row in rows if row[0] is not None]

    def load_contractors_by_ids(
        self, contractor_ids: List[str]
    ) -> List["ConstructionContractor"]:
        """Return contractor records for the given IDs, ordered by name."""
        from app.modules.construction.models import ConstructionContractor

        if not contractor_ids:
            return []
        return (
            self.db.query(ConstructionContractor)
            .filter(ConstructionContractor.id.in_(contractor_ids))
            .order_by(ConstructionContractor.contractor_name)
            .all()
        )

    def load_scope_milestone_dataset(
        self, scope_id: str
    ) -> tuple[List["ConstructionContractor"], List[ConstructionProcurementPackage]]:
        """Load all contractors and packages with milestones for a scope.

        Returns a 2-tuple of (contractors, packages).  Packages are loaded with
        milestones eagerly via ``selectinload`` in a small, fixed number of SQL
        queries (one for packages and one or more SELECT IN queries for the
        related milestones).  Contractors are loaded in a separate query keyed
        by the contractor IDs found in those packages.

        This method is the single entry point for scope-wide scorecard and
        ranking dataset loading, eliminating N+1 query patterns in the
        analytics layer.
        """
        packages = self.load_scope_packages_with_milestones(scope_id)
        contractor_ids = list(
            {pkg.contractor_id for pkg in packages if pkg.contractor_id is not None}
        )
        contractors = self.load_contractors_by_ids(contractor_ids)
        return contractors, packages

    def load_project_milestone_dataset(
        self, scope_ids: List[str]
    ) -> tuple[List["ConstructionContractor"], List[ConstructionProcurementPackage]]:
        """Load all contractors and packages with milestones for a list of scopes.

        Uses a fixed number of SQL queries regardless of scope count:
        one query for all packages across all scopes, one or more SELECT IN
        queries for milestones, and one for all unique contractors.

        This is the batch counterpart of ``load_scope_milestone_dataset`` and
        eliminates O(#scopes) query amplification when computing project-level
        rollups.

        Parameters
        ----------
        scope_ids:
            IDs of all scopes to load data for.  Typically all scopes within
            a single project.

        Returns
        -------
        (contractors, packages)
            contractors — unique ConstructionContractor records across all
                          scopes.
            packages    — ConstructionProcurementPackage records with
                          milestones eagerly loaded, across all scopes.
        """
        if not scope_ids:
            return [], []
        from app.modules.construction.models import ConstructionProcurementPackage

        packages = (
            self.db.query(ConstructionProcurementPackage)
            .options(selectinload(ConstructionProcurementPackage.milestones))
            .filter(ConstructionProcurementPackage.scope_id.in_(scope_ids))
            .order_by(ConstructionProcurementPackage.package_code)
            .all()
        )
        contractor_ids = list(
            {pkg.contractor_id for pkg in packages if pkg.contractor_id is not None}
        )
        contractors = self.load_contractors_by_ids(contractor_ids)
        return contractors, packages

