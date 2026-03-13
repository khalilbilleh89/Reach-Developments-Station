"""
pricing.service

Application-layer orchestration for pricing workflows.
Validates domain invariants and coordinates repository and engine calls.
"""

from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.pricing.engines.pricing_engine import PricingInputs, run_pricing
from app.modules.pricing.repository import UnitPricingAttributesRepository
from app.modules.pricing.schemas import (
    ProjectPriceSummaryItem,
    ProjectPriceSummaryResponse,
    UnitPricingAttributesCreate,
    UnitPricingAttributesResponse,
    UnitPriceResponse,
)
from app.modules.units.repository import UnitRepository


class PricingService:
    def __init__(self, db: Session) -> None:
        self.attrs_repo = UnitPricingAttributesRepository(db)
        self.unit_repo = UnitRepository(db)
        self._db = db

    # ------------------------------------------------------------------
    # Attribute management
    # ------------------------------------------------------------------

    def set_pricing_attributes(
        self, unit_id: str, data: UnitPricingAttributesCreate
    ) -> UnitPricingAttributesResponse:
        """Create or replace pricing attributes for a unit."""
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        attrs = self.attrs_repo.upsert(unit_id, data)
        return UnitPricingAttributesResponse.model_validate(attrs)

    def get_pricing_attributes(self, unit_id: str) -> UnitPricingAttributesResponse:
        """Get the pricing attributes for a unit."""
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        attrs = self.attrs_repo.get_by_unit(unit_id)
        if not attrs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No pricing attributes found for unit '{unit_id}'.",
            )
        return UnitPricingAttributesResponse.model_validate(attrs)

    # ------------------------------------------------------------------
    # Price calculation
    # ------------------------------------------------------------------

    def _resolve_unit_area(self, unit) -> float:
        """Resolve effective unit area: gross_area if set, else internal_area."""
        if unit.gross_area is not None:
            return float(unit.gross_area)
        return float(unit.internal_area)

    def _validate_pricing_attributes(self, attrs, unit_id: str) -> None:
        """Raise 422 if any required pricing attribute is missing."""
        for field in self._REQUIRED_PRICING_FIELDS:
            if getattr(attrs, field) is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Pricing attribute '{field}' is required but missing for unit '{unit_id}'.",
                )

    _REQUIRED_PRICING_FIELDS = (
        "base_price_per_sqm",
        "floor_premium",
        "view_premium",
        "corner_premium",
        "size_adjustment",
        "custom_adjustment",
    )

    def _has_complete_pricing_attributes(self, attrs) -> bool:
        """Return True if all required pricing attributes are present, False otherwise."""
        return all(getattr(attrs, field) is not None for field in self._REQUIRED_PRICING_FIELDS)

    def _run_pricing_for_area(self, unit_area: float, attrs):
        """Build PricingInputs from a unit area and stored attributes and run the engine."""
        return run_pricing(
            PricingInputs(
                unit_area=unit_area,
                base_price_per_sqm=float(attrs.base_price_per_sqm),
                floor_premium=float(attrs.floor_premium),
                view_premium=float(attrs.view_premium),
                corner_premium=float(attrs.corner_premium),
                size_adjustment=float(attrs.size_adjustment),
                custom_adjustment=float(attrs.custom_adjustment),
            )
        )

    def calculate_unit_price(self, unit_id: str) -> UnitPriceResponse:
        """Calculate the final price for a single unit."""
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        attrs = self.attrs_repo.get_by_unit(unit_id)
        if not attrs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Pricing attributes must be set before calculating price for unit '{unit_id}'.",
            )
        self._validate_pricing_attributes(attrs, unit_id)

        unit_area = self._resolve_unit_area(unit)
        outputs = self._run_pricing_for_area(unit_area, attrs)
        return UnitPriceResponse(
            unit_id=unit_id,
            unit_area=unit_area,
            base_unit_price=outputs.base_unit_price,
            premium_total=outputs.premium_total,
            final_unit_price=outputs.final_unit_price,
        )

    def calculate_project_price_summary(self, project_id: str) -> ProjectPriceSummaryResponse:
        """Calculate pricing for all priced units in a project."""
        from app.modules.projects.repository import ProjectRepository
        from app.modules.units.models import Unit
        from app.modules.floors.models import Floor
        from app.modules.buildings.models import Building
        from app.modules.phases.models import Phase

        project_repo = ProjectRepository(self._db)
        project = project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )

        # Fetch all units for this project via hierarchy join
        units = (
            self._db.query(Unit)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .all()
        )

        unit_ids = [u.id for u in units]
        attrs_list = self.attrs_repo.list_by_unit_ids(unit_ids)
        attrs_by_unit = {a.unit_id: a for a in attrs_list}
        units_by_id = {u.id: u for u in units}

        items: List[ProjectPriceSummaryItem] = []
        total_value = 0.0

        for uid, attrs in attrs_by_unit.items():
            unit = units_by_id[uid]
            # Skip units with incomplete attributes
            if not self._has_complete_pricing_attributes(attrs):
                continue

            unit_area = self._resolve_unit_area(unit)
            outputs = self._run_pricing_for_area(unit_area, attrs)
            items.append(
                ProjectPriceSummaryItem(
                    unit_id=uid,
                    unit_area=unit_area,
                    base_unit_price=outputs.base_unit_price,
                    premium_total=outputs.premium_total,
                    final_unit_price=outputs.final_unit_price,
                )
            )
            total_value += outputs.final_unit_price

        return ProjectPriceSummaryResponse(
            project_id=project_id,
            total_units_priced=len(items),
            total_value=total_value,
            items=items,
        )

