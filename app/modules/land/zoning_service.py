"""
land.zoning_service

Service orchestration layer for the Land Zoning & Regulation Engine.

Responsibilities:
- Validate zoning inputs via Pydantic schemas
- Invoke the zoning engine
- Return structured results for API or feasibility model consumption

No persistence is introduced in this layer.
"""

from app.modules.land.schemas import ZoningEvaluateRequest, ZoningResultResponse
from app.modules.land.zoning_engine import ZoningInputs, run_zoning_calculation


class ZoningService:
    """Stateless service that validates inputs and orchestrates the zoning engine."""

    def evaluate(self, request: ZoningEvaluateRequest) -> ZoningResultResponse:
        """Validate zoning parameters and compute development capacity.

        Parameters
        ----------
        request:
            Validated :class:`ZoningEvaluateRequest` Pydantic model.

        Returns
        -------
        ZoningResultResponse
            Structured zoning result ready for API serialisation.
        """
        inputs = ZoningInputs(
            land_area=request.land_area,
            far=request.far,
            coverage_ratio=request.coverage_ratio,
            max_height_m=request.max_height_m,
            floor_height_m=request.floor_height_m,
            parking_ratio=request.parking_ratio,
            setback_front=request.setback_front,
            setback_side=request.setback_side,
            setback_rear=request.setback_rear,
            avg_unit_size_sqm=request.avg_unit_size_sqm,
        )
        result = run_zoning_calculation(inputs)

        return ZoningResultResponse(
            max_buildable_area=result.max_buildable_area,
            max_footprint_area=result.max_footprint_area,
            max_floors=result.max_floors,
            setback_adjusted_area=result.setback_adjusted_area,
            effective_footprint=result.effective_footprint,
            effective_buildable_area=result.effective_buildable_area,
            estimated_unit_capacity=result.estimated_unit_capacity,
            parking_required=result.parking_required,
        )
