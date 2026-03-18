"""
feasibility.service

Application-layer orchestration for feasibility workflows.
Validates domain invariants and coordinates repository and engine calls.
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.feasibility.engines.feasibility_engine import FeasibilityInputs, run_feasibility
from app.modules.feasibility.repository import (
    FeasibilityAssumptionsRepository,
    FeasibilityResultRepository,
    FeasibilityRunRepository,
)
from app.modules.feasibility.schemas import (
    FeasibilityAssumptionsCreate,
    FeasibilityAssumptionsResponse,
    FeasibilityResultResponse,
    FeasibilityRunCreate,
    FeasibilityRunList,
    FeasibilityRunResponse,
    FeasibilityRunUpdate,
)
from app.modules.projects.repository import ProjectRepository


class FeasibilityService:
    def __init__(self, db: Session) -> None:
        self.run_repo = FeasibilityRunRepository(db)
        self.assumptions_repo = FeasibilityAssumptionsRepository(db)
        self.result_repo = FeasibilityResultRepository(db)
        self.project_repo = ProjectRepository(db)

    # ------------------------------------------------------------------
    # Run operations
    # ------------------------------------------------------------------

    def create_feasibility_run(self, data: FeasibilityRunCreate) -> FeasibilityRunResponse:
        if data.project_id is not None:
            project = self.project_repo.get_by_id(data.project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project '{data.project_id}' not found.",
                )
        run = self.run_repo.create(data)
        return FeasibilityRunResponse.model_validate(run)

    def get_feasibility_run(self, run_id: str) -> FeasibilityRunResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feasibility run '{run_id}' not found.",
            )
        return FeasibilityRunResponse.model_validate(run)

    def list_feasibility_runs(
        self, project_id: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> FeasibilityRunList:
        if project_id:
            runs = self.run_repo.list_by_project(project_id, skip=skip, limit=limit)
            total = self.run_repo.count_by_project(project_id)
        else:
            runs = self.run_repo.list_all(skip=skip, limit=limit)
            total = self.run_repo.count_all()
        return FeasibilityRunList(
            items=[FeasibilityRunResponse.model_validate(r) for r in runs],
            total=total,
        )

    def update_feasibility_run(self, run_id: str, data: FeasibilityRunUpdate) -> FeasibilityRunResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feasibility run '{run_id}' not found.",
            )
        updated = self.run_repo.update(run, data)
        return FeasibilityRunResponse.model_validate(updated)

    # ------------------------------------------------------------------
    # Assumptions operations
    # ------------------------------------------------------------------

    def update_assumptions(
        self, run_id: str, data: FeasibilityAssumptionsCreate
    ) -> FeasibilityAssumptionsResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feasibility run '{run_id}' not found.",
            )
        assumptions = self.assumptions_repo.upsert(run_id, data)
        return FeasibilityAssumptionsResponse.model_validate(assumptions)

    def get_assumptions(self, run_id: str) -> FeasibilityAssumptionsResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feasibility run '{run_id}' not found.",
            )
        assumptions = self.assumptions_repo.get_by_run(run_id)
        if not assumptions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No assumptions found for feasibility run '{run_id}'.",
            )
        return FeasibilityAssumptionsResponse.model_validate(assumptions)

    # ------------------------------------------------------------------
    # Calculation operations
    # ------------------------------------------------------------------

    def run_feasibility_calculation(self, run_id: str) -> FeasibilityResultResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feasibility run '{run_id}' not found.",
            )
        assumptions = self.assumptions_repo.get_by_run(run_id)
        if not assumptions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Assumptions must be set before calculating feasibility run '{run_id}'.",
            )
        # Validate all required fields are present
        required_fields = [
            "sellable_area_sqm",
            "avg_sale_price_per_sqm",
            "construction_cost_per_sqm",
            "soft_cost_ratio",
            "finance_cost_ratio",
            "sales_cost_ratio",
            "development_period_months",
        ]
        for field in required_fields:
            if getattr(assumptions, field) is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Assumption field '{field}' is required but missing.",
                )

        inputs = FeasibilityInputs(
            sellable_area_sqm=float(assumptions.sellable_area_sqm),
            avg_sale_price_per_sqm=float(assumptions.avg_sale_price_per_sqm),
            construction_cost_per_sqm=float(assumptions.construction_cost_per_sqm),
            soft_cost_ratio=float(assumptions.soft_cost_ratio),
            finance_cost_ratio=float(assumptions.finance_cost_ratio),
            sales_cost_ratio=float(assumptions.sales_cost_ratio),
            development_period_months=int(assumptions.development_period_months),
        )
        outputs = run_feasibility(inputs)
        result = self.result_repo.create_or_replace(
            run_id=run_id,
            gdv=outputs.gdv,
            construction_cost=outputs.construction_cost,
            soft_cost=outputs.soft_cost,
            finance_cost=outputs.finance_cost,
            sales_cost=outputs.sales_cost,
            total_cost=outputs.total_cost,
            developer_profit=outputs.developer_profit,
            profit_margin=outputs.profit_margin,
            irr_estimate=outputs.irr_estimate,
        )
        return FeasibilityResultResponse.model_validate(result)

    def get_feasibility_result(self, run_id: str) -> FeasibilityResultResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feasibility run '{run_id}' not found.",
            )
        result = self.result_repo.get_by_run(run_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result found for feasibility run '{run_id}'. Run the calculation first.",
            )
        return FeasibilityResultResponse.model_validate(result)

