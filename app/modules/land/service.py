"""
land.service

Business logic for the Land Underwriting domain.
Handles validation, derived area calculations, and valuation computations.
"""

from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.calculation_engine.registry import (
    LandInputs,
    calculate_buildable_area,
    calculate_land_underwriting_metrics,
    calculate_sellable_area,
)
from app.modules.land.models import LandParcel
from app.modules.land.repository import LandAssumptionsRepository, LandParcelRepository, LandValuationRepository
from app.modules.land.schemas import (
    LandAssumptionCreate,
    LandAssumptionResponse,
    LandParcelCreate,
    LandParcelList,
    LandParcelResponse,
    LandParcelUpdate,
    LandValuationCreate,
    LandValuationEngineRequest,
    LandValuationResponse,
)
from app.modules.projects.repository import ProjectRepository
from app.core.errors import ConflictError, ResourceNotFoundError


class LandService:
    def __init__(self, db: Session) -> None:
        self.parcel_repo = LandParcelRepository(db)
        self.assumptions_repo = LandAssumptionsRepository(db)
        self.valuation_repo = LandValuationRepository(db)
        self.project_repo = ProjectRepository(db)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_parcel_metrics(self, parcel: LandParcel) -> Dict[str, Optional[float]]:
        """Compute land basis metrics from parcel fields via Calculation Engine.

        Always-computable metrics (when acquisition_price is available):
          effective_land_basis, gross_land_price_per_sqm,
          effective_land_price_per_gross_sqm, effective_land_price_per_buildable_sqm,
          effective_land_price_per_sellable_sqm.

        Conditionally-computable metrics (from latest engine valuation if available):
          supported_acquisition_price, residual_land_value, margin_impact.

        Returns null for any metric whose required inputs are absent.
        """
        if parcel.acquisition_price is None:
            return {}

        acquisition_price = float(parcel.acquisition_price)
        transaction_cost = float(parcel.transaction_cost) if parcel.transaction_cost is not None else 0.0
        land_area_sqm = float(parcel.land_area_sqm) if parcel.land_area_sqm is not None else 0.0
        buildable_area_sqm = float(parcel.buildable_area_sqm) if parcel.buildable_area_sqm is not None else 0.0
        sellable_area_sqm = float(parcel.sellable_area_sqm) if parcel.sellable_area_sqm is not None else 0.0

        inputs = LandInputs(
            land_area_sqm=land_area_sqm,
            acquisition_price=acquisition_price,
            buildable_area_sqm=buildable_area_sqm,
            sellable_area_sqm=sellable_area_sqm,
            gdv=0.0,
            total_development_cost=0.0,
            developer_margin_target=0.0,
            transaction_cost=transaction_cost,
        )
        outputs = calculate_land_underwriting_metrics(inputs)

        metrics: Dict[str, Optional[float]] = {
            "effective_land_basis": outputs.effective_land_basis,
            "gross_land_price_per_sqm": outputs.land_price_per_sqm if land_area_sqm > 0 else None,
            "effective_land_price_per_gross_sqm": outputs.effective_land_price_per_gross_sqm if land_area_sqm > 0 else None,
            "effective_land_price_per_buildable_sqm": outputs.effective_land_price_per_buildable_sqm if buildable_area_sqm > 0 else None,
            "effective_land_price_per_sellable_sqm": outputs.effective_land_price_per_sellable_sqm if sellable_area_sqm > 0 else None,
        }

        # Enrich with residual metrics from the latest engine valuation if available.
        # Uses a single deterministic query (ORDER BY created_at DESC LIMIT 1) to
        # avoid an N+1 load of all valuations and to ensure a consistent result.
        latest = self.valuation_repo.get_latest_engine_valuation(parcel.id)
        if latest is not None:
            metrics["supported_acquisition_price"] = float(latest.max_land_bid) if latest.max_land_bid is not None else None
            metrics["residual_land_value"] = float(latest.residual_land_value) if latest.residual_land_value is not None else None
            metrics["margin_impact"] = float(latest.residual_margin) if latest.residual_margin is not None else None

        return metrics

    def _build_parcel_response(self, parcel: LandParcel) -> LandParcelResponse:
        """Build a LandParcelResponse enriched with computed basis metrics."""
        response = LandParcelResponse.model_validate(parcel)
        metrics = self._compute_parcel_metrics(parcel)
        if metrics:
            return response.model_copy(update=metrics)
        return response

    # ------------------------------------------------------------------
    # Parcel operations
    # ------------------------------------------------------------------

    def create_parcel(self, data: LandParcelCreate) -> LandParcelResponse:
        if data.project_id is not None:
            project = self.project_repo.get_by_id(data.project_id)
            if not project:
                raise ResourceNotFoundError(
                    f"Project '{data.project_id}' not found.",
                    details={"project_id": data.project_id},
                )
            existing = self.parcel_repo.get_by_project_and_code(data.project_id, data.parcel_code)
            if existing:
                raise ConflictError(
                    f"Parcel with code '{data.parcel_code}' already exists in project '{data.project_id}'.",
                    details={"parcel_code": data.parcel_code, "project_id": data.project_id},
                )
        else:
            existing = self.parcel_repo.get_standalone_by_code(data.parcel_code)
            if existing:
                raise ConflictError(
                    f"A standalone parcel with code '{data.parcel_code}' already exists.",
                    details={"parcel_code": data.parcel_code},
                )
        try:
            parcel = self.parcel_repo.create(data)
        except IntegrityError:
            self.parcel_repo.db.rollback()
            if data.project_id is None:
                detail = f"A standalone parcel with code '{data.parcel_code}' already exists."
                details = {"parcel_code": data.parcel_code}
            else:
                detail = f"Parcel with code '{data.parcel_code}' already exists in project '{data.project_id}'."
                details = {"parcel_code": data.parcel_code, "project_id": data.project_id}
            raise ConflictError(detail, details=details)
        return self._build_parcel_response(parcel)

    def get_parcel(self, parcel_id: str) -> LandParcelResponse:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise ResourceNotFoundError(
                f"Land parcel '{parcel_id}' not found.",
                details={"parcel_id": parcel_id},
            )
        return self._build_parcel_response(parcel)

    def list_parcels(self, project_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> LandParcelList:
        parcels = self.parcel_repo.list(project_id=project_id, skip=skip, limit=limit)
        total = self.parcel_repo.count(project_id=project_id)
        return LandParcelList(
            items=[self._build_parcel_response(p) for p in parcels],
            total=total,
        )

    def update_parcel(self, parcel_id: str, data: LandParcelUpdate) -> LandParcelResponse:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise ResourceNotFoundError(
                f"Land parcel '{parcel_id}' not found.",
                details={"parcel_id": parcel_id},
            )
        updated = self.parcel_repo.update(parcel, data)
        return self._build_parcel_response(updated)

    def delete_parcel(self, parcel_id: str) -> None:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise ResourceNotFoundError(
                f"Land parcel '{parcel_id}' not found.",
                details={"parcel_id": parcel_id},
            )
        self.parcel_repo.delete(parcel)

    def assign_to_project(self, parcel_id: str, project_id: str) -> LandParcelResponse:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise ResourceNotFoundError(
                f"Land parcel '{parcel_id}' not found.",
                details={"parcel_id": parcel_id},
            )
        project = self.project_repo.get_by_id(project_id)
        if not project:
            raise ResourceNotFoundError(
                f"Project '{project_id}' not found.",
                details={"project_id": project_id},
            )
        # Check that parcel is not already assigned to a different project
        if parcel.project_id is not None and parcel.project_id != project_id:
            raise ConflictError(
                f"Land parcel '{parcel_id}' is already assigned to project '{parcel.project_id}'.",
                details={"parcel_id": parcel_id, "existing_project_id": parcel.project_id},
            )
        # Already assigned to the target project — idempotent success
        if parcel.project_id == project_id:
            return self._build_parcel_response(parcel)
        # Check for code conflict within target project
        existing = self.parcel_repo.get_by_project_and_code(project_id, parcel.parcel_code)
        if existing:
            raise ConflictError(
                f"A parcel with code '{parcel.parcel_code}' already exists in project '{project_id}'.",
                details={"parcel_code": parcel.parcel_code, "project_id": project_id},
            )
        # Perform assignment — guard against concurrency-driven IntegrityError
        try:
            parcel.project_id = project_id
            self.parcel_repo.db.commit()
            self.parcel_repo.db.refresh(parcel)
        except IntegrityError:
            self.parcel_repo.db.rollback()
            raise ConflictError(
                f"A parcel with code '{parcel.parcel_code}' already exists in project '{project_id}'.",
                details={"parcel_code": parcel.parcel_code, "project_id": project_id},
            )
        return self._build_parcel_response(parcel)

    # ------------------------------------------------------------------
    # Assumptions operations
    # ------------------------------------------------------------------

    def create_assumptions(self, parcel_id: str, data: LandAssumptionCreate) -> LandAssumptionResponse:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise ResourceNotFoundError(
                f"Land parcel '{parcel_id}' not found.",
                details={"parcel_id": parcel_id},
            )

        # Derived calculations via the centralized Calculation Engine
        buildable_area: Optional[float] = None
        sellable_area: Optional[float] = None

        if parcel.land_area_sqm is not None and parcel.permitted_far is not None:
            buildable_area = calculate_buildable_area(
                float(parcel.land_area_sqm), float(parcel.permitted_far)
            )

        if buildable_area is not None and data.expected_sellable_ratio is not None:
            sellable_area = calculate_sellable_area(buildable_area, data.expected_sellable_ratio)

        assumptions = self.assumptions_repo.create(parcel_id, data, buildable_area, sellable_area)
        return LandAssumptionResponse.model_validate(assumptions)

    def get_assumptions(self, parcel_id: str) -> List[LandAssumptionResponse]:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise ResourceNotFoundError(
                f"Land parcel '{parcel_id}' not found.",
                details={"parcel_id": parcel_id},
            )
        assumptions = self.assumptions_repo.get_by_parcel(parcel_id)
        return [LandAssumptionResponse.model_validate(a) for a in assumptions]

    # ------------------------------------------------------------------
    # Valuation operations
    # ------------------------------------------------------------------

    def create_valuation(self, parcel_id: str, data: LandValuationCreate) -> LandValuationResponse:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise ResourceNotFoundError(
                f"Land parcel '{parcel_id}' not found.",
                details={"parcel_id": parcel_id},
            )

        # Retrieve latest assumptions to obtain sellable area (if any)
        assumptions_list = self.assumptions_repo.get_by_parcel(parcel_id)
        sellable_area: Optional[float] = None
        if assumptions_list:
            latest = assumptions_list[-1]
            if latest.expected_sellable_area_sqm is not None:
                sellable_area = float(latest.expected_sellable_area_sqm)

        # Derived valuation calculations
        gdv: Optional[float] = None
        cost: Optional[float] = None
        rlv: Optional[float] = None
        rlv_per_sqm: Optional[float] = None

        if sellable_area is not None and data.assumed_sale_price_per_sqm is not None:
            gdv = sellable_area * data.assumed_sale_price_per_sqm

        if sellable_area is not None and data.assumed_cost_per_sqm is not None:
            cost = sellable_area * data.assumed_cost_per_sqm

        if gdv is not None and cost is not None:
            rlv = gdv - cost

        if rlv is not None and parcel.land_area_sqm is not None and float(parcel.land_area_sqm) > 0:
            rlv_per_sqm = rlv / float(parcel.land_area_sqm)

        valuation = self.valuation_repo.create(parcel_id, data, gdv, cost, rlv, rlv_per_sqm)
        return LandValuationResponse.model_validate(valuation)

    def list_valuations(self, parcel_id: str) -> List[LandValuationResponse]:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise ResourceNotFoundError(
                f"Land parcel '{parcel_id}' not found.",
                details={"parcel_id": parcel_id},
            )
        valuations = self.valuation_repo.list_by_parcel(parcel_id)
        return [LandValuationResponse.model_validate(v) for v in valuations]

    def calculate_land_valuation(self, parcel_id: str, data: LandValuationEngineRequest) -> LandValuationResponse:
        from app.modules.land.engines.valuation_engine import ValuationInputs, run_land_valuation

        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise ResourceNotFoundError(
                f"Land parcel '{parcel_id}' not found.",
                details={"parcel_id": parcel_id},
            )

        inputs = ValuationInputs(
            gdv=data.gdv,
            construction_cost=data.construction_cost,
            soft_cost_percentage=data.soft_cost_percentage,
            developer_margin_target=data.developer_margin_target,
            sellable_area_sqm=data.sellable_area_sqm,
        )
        outputs = run_land_valuation(inputs)

        valuation = self.valuation_repo.create_from_engine(parcel_id, data, outputs)
        return LandValuationResponse.model_validate(valuation)
