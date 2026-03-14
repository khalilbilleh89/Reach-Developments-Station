"""
sales_exceptions.service

Application-layer orchestration for the SalesException domain.

Core rules enforced here:
  1. Exception must reference a valid unit (unit must exist).
  2. Discount must be non-negative  (requested_price ≤ base_price).
  3. Discount must not exceed the configured maximum (MAX_DISCOUNT_PERCENTAGE).
  4. Once approved or rejected, an exception becomes immutable
     (status cannot be changed again).

Derived calculations performed here:
  discount_amount      = base_price - requested_price
  discount_percentage  = discount_amount / base_price
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.sales_exceptions.models import SalesException
from app.modules.sales_exceptions.repository import SalesExceptionRepository
from app.modules.sales_exceptions.schemas import (
    SalesExceptionApproval,
    SalesExceptionCreate,
    SalesExceptionListResponse,
    SalesExceptionResponse,
    SalesExceptionSummary,
    SalesExceptionUpdate,
)
from app.modules.units.repository import UnitRepository
from app.modules.projects.repository import ProjectRepository
from app.shared.enums.sales_exceptions import ApprovalStatus

# Maximum allowed discount as a fraction of base price (configurable).
_MAX_DISCOUNT_PERCENTAGE: float = 0.30  # 30 %


class SalesExceptionService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = SalesExceptionRepository(db)
        self._unit_repo = UnitRepository(db)
        self._project_repo = ProjectRepository(db)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_exception(self, data: SalesExceptionCreate) -> SalesExceptionResponse:
        self._require_project(data.project_id)
        self._require_unit(data.unit_id)

        discount_amount = round(data.base_price - data.requested_price, 2)
        discount_pct = round(discount_amount / data.base_price, 4)

        if discount_pct > _MAX_DISCOUNT_PERCENTAGE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Discount of {discount_pct * 100:.2f}% exceeds the maximum "
                    f"allowed discount of {_MAX_DISCOUNT_PERCENTAGE * 100:.0f}%."
                ),
            )

        exc = SalesException(
            project_id=data.project_id,
            unit_id=data.unit_id,
            sale_contract_id=data.sale_contract_id,
            exception_type=data.exception_type.value,
            base_price=data.base_price,
            requested_price=data.requested_price,
            discount_amount=discount_amount,
            discount_percentage=discount_pct,
            incentive_value=data.incentive_value,
            incentive_description=data.incentive_description,
            requested_by=data.requested_by,
            notes=data.notes,
            approval_status=ApprovalStatus.PENDING.value,
        )
        exc = self._repo.create(exc)
        return SalesExceptionResponse.model_validate(exc)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_exception(self, exception_id: str) -> SalesExceptionResponse:
        exc = self._require_exception(exception_id)
        return SalesExceptionResponse.model_validate(exc)

    def list_by_project(
        self,
        project_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> SalesExceptionListResponse:
        self._require_project(project_id)
        items = self._repo.list_by_project(project_id, skip=skip, limit=limit)
        total = self._repo.count_by_project(project_id)
        return SalesExceptionListResponse(
            total=total,
            items=[SalesExceptionResponse.model_validate(e) for e in items],
        )

    def get_project_summary(self, project_id: str) -> SalesExceptionSummary:
        self._require_project(project_id)
        total = self._repo.count_by_project(project_id)
        pending = self._repo.count_by_status(project_id, ApprovalStatus.PENDING)
        approved = self._repo.count_by_status(project_id, ApprovalStatus.APPROVED)
        rejected = self._repo.count_by_status(project_id, ApprovalStatus.REJECTED)
        total_discount = self._repo.sum_discount_by_project(project_id)
        total_incentive = self._repo.sum_incentive_value_by_project(project_id)
        return SalesExceptionSummary(
            project_id=project_id,
            total_exceptions=total,
            pending_exceptions=pending,
            approved_exceptions=approved,
            rejected_exceptions=rejected,
            total_discount_amount=total_discount,
            total_incentive_value=total_incentive,
        )

    # ------------------------------------------------------------------
    # Update (pending only)
    # ------------------------------------------------------------------

    def update_exception(
        self, exception_id: str, data: SalesExceptionUpdate
    ) -> SalesExceptionResponse:
        exc = self._require_exception(exception_id)
        self._require_pending(exc)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(exc, field, value)
        exc = self._repo.save(exc)
        return SalesExceptionResponse.model_validate(exc)

    # ------------------------------------------------------------------
    # Approve / Reject
    # ------------------------------------------------------------------

    def approve_exception(
        self, exception_id: str, data: SalesExceptionApproval
    ) -> SalesExceptionResponse:
        exc = self._require_exception(exception_id)
        self._require_pending(exc)
        exc.approval_status = ApprovalStatus.APPROVED.value
        exc.approved_by = data.approved_by
        exc.approved_at = datetime.now(timezone.utc)
        if data.notes is not None:
            exc.notes = data.notes
        exc = self._repo.save(exc)
        return SalesExceptionResponse.model_validate(exc)

    def reject_exception(
        self, exception_id: str, data: SalesExceptionApproval
    ) -> SalesExceptionResponse:
        exc = self._require_exception(exception_id)
        self._require_pending(exc)
        exc.approval_status = ApprovalStatus.REJECTED.value
        exc.approved_by = data.approved_by
        exc.approved_at = datetime.now(timezone.utc)
        if data.notes is not None:
            exc.notes = data.notes
        exc = self._repo.save(exc)
        return SalesExceptionResponse.model_validate(exc)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_id: str):
        project = self._project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        return project

    def _require_unit(self, unit_id: str):
        unit = self._unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        return unit

    def _require_exception(self, exception_id: str) -> SalesException:
        exc = self._repo.get_by_id(exception_id)
        if not exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SalesException '{exception_id}' not found.",
            )
        return exc

    def _require_pending(self, exc: SalesException) -> None:
        if exc.approval_status != ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"SalesException '{exc.id}' has already been "
                    f"'{exc.approval_status}' and is now immutable."
                ),
            )
