"""
land.service

Business logic for the Land Underwriting domain.
Handles validation, derived area calculations, and valuation computations.
"""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.land.repository import LandAssumptionsRepository, LandParcelRepository, LandValuationRepository
from app.modules.land.schemas import (
    LandAssumptionCreate,
    LandAssumptionResponse,
    LandParcelCreate,
    LandParcelList,
    LandParcelResponse,
    LandParcelUpdate,
    LandValuationCreate,
    LandValuationResponse,
)
from app.modules.projects.repository import ProjectRepository


class LandService:
    def __init__(self, db: Session) -> None:
        self.parcel_repo = LandParcelRepository(db)
        self.assumptions_repo = LandAssumptionsRepository(db)
        self.valuation_repo = LandValuationRepository(db)
        self.project_repo = ProjectRepository(db)

    # ------------------------------------------------------------------
    # Parcel operations
    # ------------------------------------------------------------------

    def create_parcel(self, data: LandParcelCreate) -> LandParcelResponse:
        if data.project_id is not None:
            project = self.project_repo.get_by_id(data.project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project '{data.project_id}' not found.",
                )
            existing = self.parcel_repo.get_by_project_and_code(data.project_id, data.parcel_code)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Parcel with code '{data.parcel_code}' already exists in project '{data.project_id}'.",
                )
        else:
            existing = self.parcel_repo.get_standalone_by_code(data.parcel_code)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A standalone parcel with code '{data.parcel_code}' already exists.",
                )
        try:
            parcel = self.parcel_repo.create(data)
        except IntegrityError:
            self.parcel_repo.db.rollback()
            if data.project_id is None:
                detail = f"A standalone parcel with code '{data.parcel_code}' already exists."
            else:
                detail = f"Parcel with code '{data.parcel_code}' already exists in project '{data.project_id}'."
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            )
        return LandParcelResponse.model_validate(parcel)

    def get_parcel(self, parcel_id: str) -> LandParcelResponse:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Land parcel '{parcel_id}' not found.",
            )
        return LandParcelResponse.model_validate(parcel)

    def list_parcels(self, project_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> LandParcelList:
        parcels = self.parcel_repo.list(project_id=project_id, skip=skip, limit=limit)
        total = self.parcel_repo.count(project_id=project_id)
        return LandParcelList(
            items=[LandParcelResponse.model_validate(p) for p in parcels],
            total=total,
        )

    def update_parcel(self, parcel_id: str, data: LandParcelUpdate) -> LandParcelResponse:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Land parcel '{parcel_id}' not found.",
            )
        updated = self.parcel_repo.update(parcel, data)
        return LandParcelResponse.model_validate(updated)

    # ------------------------------------------------------------------
    # Assumptions operations
    # ------------------------------------------------------------------

    def create_assumptions(self, parcel_id: str, data: LandAssumptionCreate) -> LandAssumptionResponse:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Land parcel '{parcel_id}' not found.",
            )

        # Derived calculations
        buildable_area: Optional[float] = None
        sellable_area: Optional[float] = None

        if parcel.land_area_sqm is not None and parcel.permitted_far is not None:
            buildable_area = float(parcel.land_area_sqm) * float(parcel.permitted_far)

        if buildable_area is not None and data.expected_sellable_ratio is not None:
            sellable_area = buildable_area * data.expected_sellable_ratio

        assumptions = self.assumptions_repo.create(parcel_id, data, buildable_area, sellable_area)
        return LandAssumptionResponse.model_validate(assumptions)

    def get_assumptions(self, parcel_id: str) -> List[LandAssumptionResponse]:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Land parcel '{parcel_id}' not found.",
            )
        assumptions = self.assumptions_repo.get_by_parcel(parcel_id)
        return [LandAssumptionResponse.model_validate(a) for a in assumptions]

    # ------------------------------------------------------------------
    # Valuation operations
    # ------------------------------------------------------------------

    def create_valuation(self, parcel_id: str, data: LandValuationCreate) -> LandValuationResponse:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Land parcel '{parcel_id}' not found.",
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Land parcel '{parcel_id}' not found.",
            )
        valuations = self.valuation_repo.list_by_parcel(parcel_id)
        return [LandValuationResponse.model_validate(v) for v in valuations]
