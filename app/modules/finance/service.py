"""
finance.service

Service layer for project-level financial summary computation.

Business rules enforced here:
  - Project must exist before any aggregation is attempted.
  - All aggregation is read-only; no records are created or mutated.
  - total_receivable = max(0, total_contract_value - total_collected)
    Clamped to zero to remain non-negative when receipts exceed contract
    value (e.g. due to rounding or adjusted contracts).
  - collection_ratio = min(total_collected / total_contract_value, 1.0)
    Clamped to 1.0 so over-collection never produces a ratio > 1.
    Defaults to 0.0 when total_contract_value is zero.
  - units_available is derived from the unit status counts, not from
    total_units - units_sold, so that reserved units are excluded from
    both buckets consistently.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.finance.repository import FinanceSummaryRepository
from app.modules.finance.schemas import ProjectFinanceSummaryResponse
from app.modules.projects.models import Project


class FinanceSummaryService:
    """Computes aggregated financial metrics for a project."""

    def __init__(self, db: Session) -> None:
        self.repo = FinanceSummaryRepository(db)
        self.db = db

    def get_project_summary(self, project_id: str) -> ProjectFinanceSummaryResponse:
        """Return the aggregated financial summary for a project.

        Raises HTTP 404 if the project does not exist.
        All derived monetary values are clamped to prevent invalid schema
        states when accounting data contains over-collection or rounding.
        """
        self._require_project(project_id)

        unit_counts = self.repo.get_unit_counts_by_project(project_id)
        contract_agg = self.repo.get_contract_aggregates_by_project(project_id)
        total_collected = round(self.repo.sum_collected_by_project(project_id), 2)

        total_contract_value = round(contract_agg.total_value, 2)
        total_receivable = round(max(0.0, total_contract_value - total_collected), 2)

        if total_contract_value > 0:
            collection_ratio = round(
                min(total_collected / total_contract_value, 1.0), 6
            )
        else:
            collection_ratio = 0.0

        average_unit_price = round(contract_agg.average_price, 2)

        return ProjectFinanceSummaryResponse(
            project_id=project_id,
            total_units=unit_counts.total,
            units_sold=unit_counts.sold,
            units_available=unit_counts.available,
            total_contract_value=total_contract_value,
            total_collected=total_collected,
            total_receivable=total_receivable,
            collection_ratio=collection_ratio,
            average_unit_price=average_unit_price,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_id: str) -> Project:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id!r} not found.",
            )
        return project
