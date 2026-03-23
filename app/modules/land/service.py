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
from app.modules.land.models import LandAssembly, LandParcel
from app.modules.land.repository import LandAssumptionsRepository, LandParcelRepository, LandValuationRepository
from app.modules.land.schemas import (
    LandAssumptionCreate,
    LandAssumptionResponse,
    LandAssemblyCreate,
    LandAssemblyList,
    LandAssemblyParcelSummary,
    LandAssemblyResponse,
    LandAssemblySummary,
    LandParcelCreate,
    LandParcelList,
    LandParcelResponse,
    LandParcelUpdate,
    LandValuationCreate,
    LandValuationEngineRequest,
    LandValuationResponse,
)
from app.modules.projects.repository import ProjectRepository
from app.core.errors import ConflictError, ResourceNotFoundError, ValidationError
from app.core.logging import get_logger

_logger = get_logger("reach_developments.land")


class LandService:
    def __init__(self, db: Session) -> None:
        self.parcel_repo = LandParcelRepository(db)
        self.assumptions_repo = LandAssumptionsRepository(db)
        self.valuation_repo = LandValuationRepository(db)
        self.project_repo = ProjectRepository(db)
        from app.modules.land.repository import LandAssemblyRepository
        self.assembly_repo = LandAssemblyRepository(db)

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
        _logger.info("Land parcel created: id=%s code=%r", parcel.id, parcel.parcel_code)
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
        _logger.info("Land engine valuation created: parcel_id=%s", parcel_id)
        return LandValuationResponse.model_validate(valuation)

    # ------------------------------------------------------------------
    # Assembly operations
    # ------------------------------------------------------------------

    def _build_assembly_response(self, assembly: "LandAssembly") -> LandAssemblyResponse:
        """Build a LandAssemblyResponse including member parcel summaries."""
        parcel_ids = self.assembly_repo.get_parcel_ids(assembly.id)
        parcels_out: list = []
        for pid in parcel_ids:
            parcel = self.parcel_repo.get_by_id(pid)
            if parcel is not None:
                parcels_out.append(
                    LandAssemblyParcelSummary(
                        parcel_id=parcel.id,
                        parcel_name=parcel.parcel_name,
                        parcel_code=parcel.parcel_code,
                        land_area_sqm=float(parcel.land_area_sqm) if parcel.land_area_sqm else None,
                        frontage_m=float(parcel.frontage_m) if parcel.frontage_m else None,
                        zoning_category=parcel.zoning_category,
                        acquisition_price=(
                            float(parcel.acquisition_price) if parcel.acquisition_price else None
                        ),
                    )
                )
        return LandAssemblyResponse(
            id=assembly.id,
            assembly_name=assembly.assembly_name,
            assembly_code=assembly.assembly_code,
            notes=assembly.notes,
            status=assembly.status,
            parcel_count=assembly.parcel_count,
            total_area_sqm=float(assembly.total_area_sqm) if assembly.total_area_sqm else None,
            total_frontage_m=(
                float(assembly.total_frontage_m) if assembly.total_frontage_m else None
            ),
            total_acquisition_price=(
                float(assembly.total_acquisition_price)
                if assembly.total_acquisition_price
                else None
            ),
            total_transaction_cost=(
                float(assembly.total_transaction_cost)
                if assembly.total_transaction_cost
                else None
            ),
            effective_land_basis=(
                float(assembly.effective_land_basis) if assembly.effective_land_basis else None
            ),
            weighted_permitted_far=(
                float(assembly.weighted_permitted_far)
                if assembly.weighted_permitted_far
                else None
            ),
            dominant_zoning_category=assembly.dominant_zoning_category,
            mixed_zoning=assembly.mixed_zoning,
            has_utilities=assembly.has_utilities,
            has_corner_plot=assembly.has_corner_plot,
            assembly_results_json=assembly.assembly_results_json,
            parcel_ids=parcel_ids,
            parcels=parcels_out,
            created_at=assembly.created_at,
            updated_at=assembly.updated_at,
        )

    def _build_assembly_summary(self, assembly: "LandAssembly") -> LandAssemblySummary:
        return LandAssemblySummary(
            id=assembly.id,
            assembly_name=assembly.assembly_name,
            assembly_code=assembly.assembly_code,
            status=assembly.status,
            parcel_count=assembly.parcel_count,
            total_area_sqm=float(assembly.total_area_sqm) if assembly.total_area_sqm else None,
            mixed_zoning=assembly.mixed_zoning,
            dominant_zoning_category=assembly.dominant_zoning_category,
            effective_land_basis=(
                float(assembly.effective_land_basis) if assembly.effective_land_basis else None
            ),
            created_at=assembly.created_at,
            updated_at=assembly.updated_at,
        )

    def _parcels_to_metrics(self, parcels: list) -> list:
        """Convert ORM LandParcel records to ParcelMetrics for the engine."""
        from app.modules.land.aggregation_engine import ParcelMetrics
        return [
            ParcelMetrics(
                parcel_id=p.id,
                land_area_sqm=float(p.land_area_sqm) if p.land_area_sqm is not None else None,
                frontage_m=float(p.frontage_m) if p.frontage_m is not None else None,
                acquisition_price=(
                    float(p.acquisition_price) if p.acquisition_price is not None else None
                ),
                transaction_cost=(
                    float(p.transaction_cost) if p.transaction_cost is not None else None
                ),
                permitted_far=(
                    float(p.permitted_far) if p.permitted_far is not None else None
                ),
                zoning_category=p.zoning_category,
                utilities_available=bool(p.utilities_available),
                corner_plot=bool(p.corner_plot),
            )
            for p in parcels
        ]

    def create_assembly(self, data: LandAssemblyCreate) -> LandAssemblyResponse:
        """Validate, aggregate, and persist a new land parcel assembly."""
        from app.modules.land.aggregation_engine import aggregate_parcels

        # Check assembly code uniqueness
        existing = self.assembly_repo.get_by_code(data.assembly_code)
        if existing:
            raise ConflictError(
                f"An assembly with code '{data.assembly_code}' already exists.",
                details={"assembly_code": data.assembly_code},
            )

        # Reject duplicate parcel IDs in the request
        if len(data.parcel_ids) != len(set(data.parcel_ids)):
            raise ValidationError(
                "Duplicate parcel IDs are not allowed in a single assembly request.",
                details={"parcel_ids": data.parcel_ids},
            )

        # Validate all requested parcels exist
        parcels = []
        for pid in data.parcel_ids:
            parcel = self.parcel_repo.get_by_id(pid)
            if not parcel:
                raise ResourceNotFoundError(
                    f"Land parcel '{pid}' not found.",
                    details={"parcel_id": pid},
                )
            parcels.append(parcel)

        # Ensure no parcel is already in another assembly
        for parcel in parcels:
            existing_assembly_id = self.assembly_repo.get_assembly_id_for_parcel(parcel.id)
            if existing_assembly_id is not None:
                raise ConflictError(
                    f"Parcel '{parcel.id}' is already assigned to assembly "
                    f"'{existing_assembly_id}'.",
                    details={
                        "parcel_id": parcel.id,
                        "existing_assembly_id": existing_assembly_id,
                    },
                )

        # Run the pure aggregation engine
        metrics = self._parcels_to_metrics(parcels)
        result = aggregate_parcels(metrics)

        assembly = self.assembly_repo.create(
            assembly_name=data.assembly_name,
            assembly_code=data.assembly_code,
            notes=data.notes,
            status=data.status.value,
            parcel_ids=data.parcel_ids,
            result=result,
        )
        _logger.info(
            "Land assembly created: id=%s code=%r parcels=%d",
            assembly.id,
            assembly.assembly_code,
            result.parcel_count,
        )
        return self._build_assembly_response(assembly)

    def get_assembly(self, assembly_id: str) -> LandAssemblyResponse:
        assembly = self.assembly_repo.get_by_id(assembly_id)
        if not assembly:
            raise ResourceNotFoundError(
                f"Land assembly '{assembly_id}' not found.",
                details={"assembly_id": assembly_id},
            )
        return self._build_assembly_response(assembly)

    def list_assemblies(self, skip: int = 0, limit: int = 100) -> LandAssemblyList:
        assemblies = self.assembly_repo.list(skip=skip, limit=limit)
        total = self.assembly_repo.count()
        return LandAssemblyList(
            items=[self._build_assembly_summary(a) for a in assemblies],
            total=total,
        )

    def delete_assembly(self, assembly_id: str) -> None:
        assembly = self.assembly_repo.get_by_id(assembly_id)
        if not assembly:
            raise ResourceNotFoundError(
                f"Land assembly '{assembly_id}' not found.",
                details={"assembly_id": assembly_id},
            )
        self.assembly_repo.delete(assembly)

    def recompute_assembly(self, assembly_id: str) -> LandAssemblyResponse:
        """Recompute aggregate metrics from current parcel source data.

        Loads the current member parcel records, re-runs the aggregation
        engine, updates the assembly snapshot, and returns the refreshed
        response.  If a member parcel has been deleted since the assembly
        was created, it is silently skipped during recomputation.
        """
        from app.modules.land.aggregation_engine import aggregate_parcels

        assembly = self.assembly_repo.get_by_id(assembly_id)
        if not assembly:
            raise ResourceNotFoundError(
                f"Land assembly '{assembly_id}' not found.",
                details={"assembly_id": assembly_id},
            )

        parcel_ids = self.assembly_repo.get_parcel_ids(assembly_id)
        parcels = [
            p
            for pid in parcel_ids
            if (p := self.parcel_repo.get_by_id(pid)) is not None
        ]

        if not parcels:
            raise ValidationError(
                "Assembly has no valid member parcels; cannot recompute.",
                details={"assembly_id": assembly_id},
            )

        metrics = self._parcels_to_metrics(parcels)
        result = aggregate_parcels(metrics)
        updated = self.assembly_repo.update_aggregation(assembly, result)
        _logger.info("Land assembly recomputed: id=%s", assembly_id)
        return self._build_assembly_response(updated)
