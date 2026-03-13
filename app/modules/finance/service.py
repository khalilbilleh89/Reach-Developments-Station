"""
finance.service

Service layer for project-level financial summary computation.

Business rules enforced here:
  - Project must exist before any aggregation is attempted.
  - All aggregation is read-only; no records are created or mutated.
  - total_receivable = total_contract_value - total_collected
  - collection_ratio = total_collected / total_contract_value
    (0.0 when total_contract_value is zero to avoid division by zero)
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
        """
        self._require_project(project_id)

        total_units = self.repo.count_units_by_project(project_id)
        units_sold = self.repo.count_units_sold_by_project(project_id)
        units_available = self.repo.count_units_available_by_project(project_id)

        total_contract_value = round(
            self.repo.sum_contract_value_by_project(project_id), 2
        )
        total_collected = round(self.repo.sum_collected_by_project(project_id), 2)
        total_receivable = round(total_contract_value - total_collected, 2)

        if total_contract_value > 0:
            collection_ratio = round(total_collected / total_contract_value, 6)
        else:
            collection_ratio = 0.0

        average_unit_price = round(
            self.repo.average_contract_price_by_project(project_id), 2
        )

        return ProjectFinanceSummaryResponse(
            project_id=project_id,
            total_units=total_units,
            units_sold=units_sold,
            units_available=units_available,
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
