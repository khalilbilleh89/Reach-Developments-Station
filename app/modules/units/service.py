"""
units.service

Business logic for the Unit entity.
Enforces: unit must belong to a valid floor; unit number must be unique per floor.

Also contains UnitDynamicAttributeService (PR-033) for managing project-defined
attribute selections on units.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.modules.buildings.models import Building
from app.modules.floors.models import Floor
from app.modules.floors.repository import FloorRepository
from app.modules.phases.models import Phase
from app.modules.projects.repository import ProjectRepository
from app.modules.units.models import UnitDynamicAttributeValue
from app.modules.units.repository import UnitDynamicAttributeRepository, UnitRepository
from app.modules.units.schemas import (
    UnitCreate,
    UnitDynamicAttributesSaveRequest,
    UnitDynamicAttributeValueResponse,
    UnitList,
    UnitResponse,
    UnitUpdate,
)


class UnitService:
    def __init__(self, db: Session) -> None:
        self.repo = UnitRepository(db)
        self.floor_repo = FloorRepository(db)

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

    def create_unit(self, data: UnitCreate) -> UnitResponse:
        floor = self.floor_repo.get_by_id(data.floor_id)
        if not floor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Floor '{data.floor_id}' not found.",
            )
        existing = self.repo.get_by_floor_and_number(data.floor_id, data.unit_number)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unit '{data.unit_number}' already exists on floor '{data.floor_id}'.",
            )
        self._validate_apartment_attributes(data)
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
        self, floor_id: str | None = None, skip: int = 0, limit: int = 100
    ) -> UnitList:
        units = self.repo.list(floor_id=floor_id, skip=skip, limit=limit)
        total = self.repo.count(floor_id=floor_id)
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
        self._validate_apartment_attributes(data)
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

    def list_dynamic_attributes(self, unit_id: str) -> list[UnitDynamicAttributeValueResponse]:
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
