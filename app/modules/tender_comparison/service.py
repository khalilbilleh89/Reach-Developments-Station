"""
tender_comparison.service

Business logic for the Tender Comparison & Cost Variance domain.

Validates project and set existence, computes line variance transparently,
assembles summaries, and preserves read/write separation.

Source construction cost records and feasibility/finance records are never
mutated by this service.

PR-V6-13 additions:
  approve_tender_baseline  — approves a comparison set as the official project
    baseline, atomically deactivating any prior active baseline for the project.
  get_project_active_baseline — returns the currently approved baseline set for
    a project (or a no-baseline response).
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.tender_comparison.models import (
    ConstructionCostComparisonLine,
    ConstructionCostComparisonSet,
)
from app.modules.tender_comparison.repository import TenderComparisonRepository
from app.modules.tender_comparison.schemas import (
    ActiveTenderBaselineResponse,
    ConstructionCostComparisonLineCreate,
    ConstructionCostComparisonLineResponse,
    ConstructionCostComparisonLineUpdate,
    ConstructionCostComparisonSetCreate,
    ConstructionCostComparisonSetList,
    ConstructionCostComparisonSetListItem,
    ConstructionCostComparisonSetResponse,
    ConstructionCostComparisonSetUpdate,
    ConstructionCostComparisonSummaryResponse,
)
from app.modules.projects.models import Project


def _compute_variance(
    baseline: Decimal, comparison: Decimal
) -> tuple[Decimal, Optional[Decimal]]:
    """Compute variance amount and percentage.

    variance_amount = comparison - baseline
    variance_pct    = (variance_amount / baseline) * 100 when baseline != 0
                      else None
    """
    variance_amount = comparison - baseline
    if baseline != Decimal("0"):
        variance_pct = (variance_amount / baseline) * Decimal("100")
    else:
        variance_pct = None
    return variance_amount, variance_pct


class TenderComparisonService:
    def __init__(self, db: Session) -> None:
        self.repo = TenderComparisonRepository(db)
        self.db = db

    # ── helpers ───────────────────────────────────────────────────────────────

    def _require_project(self, project_id: str) -> Project:
        project = self.db.get(Project, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        return project

    def _require_set(self, set_id: str) -> ConstructionCostComparisonSet:
        comparison_set = self.repo.get_set_by_id(set_id)
        if comparison_set is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Comparison set '{set_id}' not found.",
            )
        return comparison_set

    def _require_line(self, line_id: str) -> ConstructionCostComparisonLine:
        line = self.repo.get_line_by_id(line_id)
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Comparison line '{line_id}' not found.",
            )
        return line

    # ── Comparison Set operations ─────────────────────────────────────────────

    def create_set(
        self,
        project_id: str,
        data: ConstructionCostComparisonSetCreate,
    ) -> ConstructionCostComparisonSetResponse:
        self._require_project(project_id)
        comparison_set = self.repo.create_set(project_id, data)
        return ConstructionCostComparisonSetResponse.model_validate(comparison_set)

    def list_sets(
        self,
        project_id: str,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> ConstructionCostComparisonSetList:
        self._require_project(project_id)
        sets = self.repo.list_sets_by_project(
            project_id, is_active=is_active, skip=skip, limit=limit
        )
        total = self.repo.count_sets_by_project(project_id, is_active=is_active)
        return ConstructionCostComparisonSetList(
            total=total,
            items=[
                ConstructionCostComparisonSetListItem.model_validate(s) for s in sets
            ],
        )

    def get_set(self, set_id: str) -> ConstructionCostComparisonSetResponse:
        comparison_set = self._require_set(set_id)
        return ConstructionCostComparisonSetResponse.model_validate(comparison_set)

    def update_set(
        self,
        set_id: str,
        data: ConstructionCostComparisonSetUpdate,
    ) -> ConstructionCostComparisonSetResponse:
        comparison_set = self._require_set(set_id)
        updated = self.repo.update_set(comparison_set, data)
        return ConstructionCostComparisonSetResponse.model_validate(updated)

    def get_set_summary(
        self, set_id: str
    ) -> ConstructionCostComparisonSummaryResponse:
        """Return DB-aggregated variance totals for a comparison set.

        total_variance_pct is only set when total_baseline != 0.
        """
        comparison_set = self._require_set(set_id)
        line_count, total_baseline, total_comparison, total_variance = (
            self.repo.get_set_totals(set_id)
        )
        if total_baseline != Decimal("0"):
            total_variance_pct = (total_variance / total_baseline) * Decimal("100")
        else:
            total_variance_pct = None

        return ConstructionCostComparisonSummaryResponse(
            comparison_set_id=set_id,
            project_id=comparison_set.project_id,
            line_count=line_count,
            total_baseline=total_baseline,
            total_comparison=total_comparison,
            total_variance=total_variance,
            total_variance_pct=total_variance_pct,
        )

    # ── Comparison Line operations ────────────────────────────────────────────

    def create_line(
        self,
        set_id: str,
        data: ConstructionCostComparisonLineCreate,
    ) -> ConstructionCostComparisonLineResponse:
        self._require_set(set_id)
        variance_amount, variance_pct = _compute_variance(
            Decimal(str(data.baseline_amount)),
            Decimal(str(data.comparison_amount)),
        )
        line = self.repo.create_line(
            set_id, data, variance_amount, variance_pct
        )
        return ConstructionCostComparisonLineResponse.model_validate(line)

    def update_line(
        self,
        line_id: str,
        data: ConstructionCostComparisonLineUpdate,
    ) -> ConstructionCostComparisonLineResponse:
        line = self._require_line(line_id)
        # Resolve effective amounts for variance recomputation
        new_baseline = (
            Decimal(str(data.baseline_amount))
            if data.baseline_amount is not None
            else Decimal(str(line.baseline_amount))
        )
        new_comparison = (
            Decimal(str(data.comparison_amount))
            if data.comparison_amount is not None
            else Decimal(str(line.comparison_amount))
        )
        variance_amount, variance_pct = _compute_variance(new_baseline, new_comparison)
        updated = self.repo.update_line(line, data, variance_amount, variance_pct)
        return ConstructionCostComparisonLineResponse.model_validate(updated)

    def delete_line(self, line_id: str) -> None:
        line = self._require_line(line_id)
        self.repo.delete_line(line)

    # ── Baseline governance ───────────────────────────────────────────────────

    def approve_tender_baseline(
        self,
        set_id: str,
        user_id: str,
    ) -> ConstructionCostComparisonSetResponse:
        """Approve a comparison set as the official project baseline.

        Rules enforced:
          - The comparison set must exist.
          - If the set is already the active baseline, the operation is
            idempotent: metadata is refreshed and the same record is returned.
          - Any prior approved baseline for the same project is deactivated
            atomically before approving the new one.
        """
        comparison_set = self._require_set(set_id)
        project_id = comparison_set.project_id

        # Deactivate the prior active baseline if it is a different set.
        prior = self.repo.get_active_baseline_for_project(project_id)
        if prior is not None and prior.id != set_id:
            self.repo.deactivate_baseline(prior)

        now = datetime.now(tz=timezone.utc)
        updated = self.repo.approve_baseline(comparison_set, now, user_id)
        return ConstructionCostComparisonSetResponse.model_validate(updated)

    def get_project_active_baseline(
        self, project_id: str
    ) -> ActiveTenderBaselineResponse:
        """Return the currently approved baseline set for a project.

        Returns a response indicating whether a baseline exists.  When no
        baseline has been approved, has_approved_baseline is False and
        baseline is None.
        """
        self._require_project(project_id)
        active = self.repo.get_active_baseline_for_project(project_id)
        if active is None:
            return ActiveTenderBaselineResponse(
                project_id=project_id,
                has_approved_baseline=False,
                baseline=None,
            )
        return ActiveTenderBaselineResponse(
            project_id=project_id,
            has_approved_baseline=True,
            baseline=ConstructionCostComparisonSetListItem.model_validate(active),
        )
