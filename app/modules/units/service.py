"""
units.service

Business logic for the Unit entity.
Enforces: unit must belong to a valid floor; unit number must be unique per floor.

Also contains UnitDynamicAttributeService (PR-033) for managing project-defined
attribute selections on units.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.modules.buildings.models import Building
from app.modules.floors.models import Floor
from app.modules.floors.repository import FloorRepository
from app.modules.phases.models import Phase
from app.modules.projects.repository import ProjectRepository
from app.modules.units.models import Unit as UnitModel, UnitDynamicAttributeValue
from app.modules.units.pricing_adapter import UnitPricingAdapter
from app.modules.units.repository import UnitDynamicAttributeRepository, UnitRepository
from app.modules.units.status_rules import assert_valid_transition
from app.modules.units.schemas import (
    UnitCreate,
    UnitDynamicAttributesSaveRequest,
    UnitDynamicAttributeValueResponse,
    UnitList,
    UnitReadinessResponse,
    UnitResponse,
    UnitUpdate,
)

_AVAILABLE_STATUS = "available"


class UnitService:
    def __init__(self, db: Session) -> None:
        self.repo = UnitRepository(db)
        self.floor_repo = FloorRepository(db)
        self._db = db

    # ------------------------------------------------------------------
    # Hierarchy validation
    # ------------------------------------------------------------------

    def validate_unit_hierarchy(self, floor_id: str) -> Floor:
        """Verify that *floor_id* exists and belongs to a complete hierarchy.

        Traverses Floor → Building → Phase to confirm all three levels are
        present.  Raises HTTP 404 when the floor does not exist.  Raises
        HTTP 422 when the floor is attached to a missing building, or the
        building is attached to a missing phase (broken reference chain).

        Returns the validated Floor ORM object.
        """
        floor = self.floor_repo.get_by_id(floor_id)
        if not floor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Floor '{floor_id}' not found.",
            )
        # Traverse the hierarchy to verify completeness.
        building = self._db.query(Building).filter(Building.id == floor.building_id).first()
        if not building:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Floor '{floor_id}' is not attached to a valid building.",
            )
        phase = self._db.query(Phase).filter(Phase.id == building.phase_id).first()
        if not phase:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Building '{building.id}' is not attached to a valid project phase.",
            )
        return floor

    # ------------------------------------------------------------------
    # Dimension validation
    # ------------------------------------------------------------------

    def _validate_apartment_attributes(self, data: UnitCreate | UnitUpdate) -> None:
        """Validate cross-field apartment attribute rules.

        Per-field non-negative constraints (bedrooms >= 0, bathrooms >= 0, etc.)
        are already enforced by Pydantic schema-level Field(ge=0) definitions.
        Only cross-field business rules belong here.
        """
        # If has_roof_garden is explicitly False, roof_garden_area must be null or 0
        has_roof_garden = getattr(data, "has_roof_garden", None)
        roof_garden_area = getattr(data, "roof_garden_area", None)
        if (
            has_roof_garden is False
            and roof_garden_area is not None
            and roof_garden_area > 0
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="roof_garden_area must be null or 0 when has_roof_garden is false.",
            )

    def validate_unit_dimensions(
        self,
        data: UnitCreate | UnitUpdate,
        existing_unit: Optional[UnitModel] = None,
    ) -> None:
        """Validate dimensional consistency of area fields.

        Validates against the *effective* post-update values: values present in
        the request payload override the current unit, and missing fields fall
        back to the existing persisted unit (when ``existing_unit`` is provided).
        For pure creates, only the provided fields are considered.

        Rules enforced:
          - gross_area must be >= internal_area.
          - livable_area must be <= internal_area.
        """
        payload_internal_area = getattr(data, "internal_area", None)
        payload_gross_area = getattr(data, "gross_area", None)
        payload_livable_area = getattr(data, "livable_area", None)

        def _effective(field: str, payload_value):
            if payload_value is not None:
                return payload_value
            if existing_unit is not None:
                return getattr(existing_unit, field, None)
            return None

        internal_area = _effective("internal_area", payload_internal_area)
        gross_area = _effective("gross_area", payload_gross_area)
        livable_area = _effective("livable_area", payload_livable_area)

        if internal_area is not None and gross_area is not None:
            if gross_area < internal_area:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"gross_area ({gross_area}) must be >= internal_area ({internal_area})."
                    ),
                )

        if internal_area is not None and livable_area is not None:
            if livable_area > internal_area:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"livable_area ({livable_area}) must be <= internal_area ({internal_area})."
                    ),
                )

    # ------------------------------------------------------------------
    # Readiness checks
    # ------------------------------------------------------------------

    def get_unit_readiness(self, unit_id: str) -> UnitReadinessResponse:
        """Return a deterministic readiness report for *unit_id*.

        Pricing readiness: unit status must be 'available'.
        Sales readiness: unit status must be 'available' AND the unit must
        have a formal pricing record with pricing_status == 'approved'.

        Raises HTTP 404 when the unit does not exist.
        """
        unit = self.repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )

        pricing_blocking: List[str] = []
        sales_blocking: List[str] = []

        # Pricing readiness gate: unit must be in 'available' state.
        if unit.status != _AVAILABLE_STATUS:
            pricing_blocking.append(
                f"Unit status is '{unit.status}'; only 'available' units accept new pricing."
            )

        # Sales readiness gate: inherit pricing gate, plus approved pricing required.
        sales_blocking.extend(pricing_blocking)

        pricing_adapter = UnitPricingAdapter(self._db)
        pricing_status = pricing_adapter.get_pricing_status(unit_id)
        if pricing_status != "approved":
            reason = (
                "No formal pricing record found."
                if pricing_status is None
                else f"Pricing record is '{pricing_status}'; must be 'approved' before sale."
            )
            sales_blocking.append(reason)

        return UnitReadinessResponse(
            unit_id=unit_id,
            is_ready_for_pricing=len(pricing_blocking) == 0,
            is_ready_for_sales=len(sales_blocking) == 0,
            pricing_blocking_reasons=pricing_blocking,
            sales_blocking_reasons=sales_blocking,
        )

    def assert_unit_ready_for_pricing(self, unit_id: str) -> None:
        """Raise HTTP 422 when *unit_id* is not ready for pricing operations.

        A unit is ready for pricing when its status is 'available'.
        Raises HTTP 404 when the unit does not exist.
        """
        readiness = self.get_unit_readiness(unit_id)
        if not readiness.is_ready_for_pricing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Unit is not ready for pricing: "
                    + "; ".join(readiness.pricing_blocking_reasons)
                ),
            )

    def assert_unit_ready_for_sales(self, unit_id: str) -> None:
        """Raise HTTP 422 when *unit_id* is not ready for sales operations.

        A unit is ready for sales when its status is 'available' and it has
        a formal pricing record with pricing_status == 'approved'.
        Raises HTTP 404 when the unit does not exist.
        """
        readiness = self.get_unit_readiness(unit_id)
        if not readiness.is_ready_for_sales:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Unit is not ready for sales: "
                    + "; ".join(readiness.sales_blocking_reasons)
                ),
            )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_unit(self, data: UnitCreate) -> UnitResponse:
        self.validate_unit_hierarchy(data.floor_id)
        existing = self.repo.get_by_floor_and_number(data.floor_id, data.unit_number)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unit '{data.unit_number}' already exists on floor '{data.floor_id}'.",
            )
        self._validate_apartment_attributes(data)
        self.validate_unit_dimensions(data)
        unit = self.repo.create(data)
        return UnitResponse.model_validate(unit)

    def get_unit(self, unit_id: str) -> UnitResponse:
        unit = self.repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        return UnitResponse.model_validate(unit)

    def list_units(
        self,
        floor_id: str | None = None,
        project_id: str | None = None,
        building_id: str | None = None,
        unit_status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> UnitList:
        units = self.repo.list(
            floor_id=floor_id,
            project_id=project_id,
            building_id=building_id,
            status=unit_status,
            skip=skip,
            limit=limit,
        )
        total = self.repo.count(
            floor_id=floor_id,
            project_id=project_id,
            building_id=building_id,
            status=unit_status,
        )
        return UnitList(
            items=[UnitResponse.model_validate(u) for u in units],
            total=total,
        )

    def update_unit(self, unit_id: str, data: UnitUpdate) -> UnitResponse:
        unit = self.repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        if data.status is not None:
            try:
                assert_valid_transition(unit.status, data.status.value)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=str(exc),
                ) from exc
        self._validate_apartment_attributes(data)
        self.validate_unit_dimensions(data, existing_unit=unit)
        updated = self.repo.update(unit, data)
        return UnitResponse.model_validate(updated)

    def delete_unit(self, unit_id: str) -> None:
        unit = self.repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        self.repo.delete(unit)


class UnitDynamicAttributeService:
    """Business logic for unit dynamic attribute values (PR-033).

    Validates project-scope integrity: unit, definition, and option must all
    belong to the same project. Option must belong to the referenced definition.
    Does not calculate pricing — it only stores and validates selections.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.unit_repo = UnitRepository(db)
        self.dav_repo = UnitDynamicAttributeRepository(db)
        self.project_repo = ProjectRepository(db)

    def _get_unit_project_id(self, unit_id: str) -> Optional[str]:
        """Return the project_id for the given unit via a single joined query."""
        from app.modules.units.models import Unit as UnitModel

        row = (
            self.db.query(Phase.project_id)
            .join(Building, Building.phase_id == Phase.id)
            .join(Floor, Floor.building_id == Building.id)
            .join(UnitModel, UnitModel.floor_id == Floor.id)
            .filter(UnitModel.id == unit_id)
            .scalar()
        )
        return row

    def _build_response(
        self, value: UnitDynamicAttributeValue
    ) -> UnitDynamicAttributeValueResponse:
        return UnitDynamicAttributeValueResponse(
            id=value.id,
            unit_id=value.unit_id,
            definition_id=value.definition_id,
            option_id=value.option_id,
            definition_key=value.definition.key,
            definition_label=value.definition.label,
            option_value=value.option.value,
            option_label=value.option.label,
        )

    def list_dynamic_attributes(
        self, unit_id: str
    ) -> list[UnitDynamicAttributeValueResponse]:
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        values = self.dav_repo.list_by_unit(unit_id)
        return [self._build_response(v) for v in values]

    def save_dynamic_attributes(
        self, unit_id: str, data: UnitDynamicAttributesSaveRequest
    ) -> list[UnitDynamicAttributeValueResponse]:
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )

        project_id = self._get_unit_project_id(unit_id)
        if not project_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Could not resolve project for unit.",
            )

        results = []
        for item in data.attributes:
            definition = self.project_repo.get_definition_by_id(item.definition_id)
            if not definition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Attribute definition '{item.definition_id}' not found.",
                )
            if definition.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Attribute definition '{item.definition_id}' does not belong "
                        f"to the same project as unit '{unit_id}'."
                    ),
                )
            option = self.project_repo.get_option_by_id(item.option_id)
            if not option:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Attribute option '{item.option_id}' not found.",
                )
            if option.definition_id != item.definition_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Attribute option '{item.option_id}' does not belong to "
                        f"definition '{item.definition_id}'."
                    ),
                )
            value = self.dav_repo.upsert(unit_id, item.definition_id, item.option_id)
            results.append(self._build_response(value))

        return results
