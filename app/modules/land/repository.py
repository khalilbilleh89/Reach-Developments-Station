"""
land.repository

Data access layer for LandParcel, LandAssumptions, and LandValuation entities.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.land.models import LandAssumptions, LandParcel, LandValuation
from app.modules.land.schemas import (
    LandAssumptionCreate,
    LandParcelCreate,
    LandParcelUpdate,
    LandValuationCreate,
    LandValuationEngineRequest,
)
from app.modules.land.engines.valuation_engine import ValuationOutputs


class LandParcelRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: LandParcelCreate) -> LandParcel:
        parcel = LandParcel(**data.model_dump())
        self.db.add(parcel)
        self.db.commit()
        self.db.refresh(parcel)
        return parcel

    def get_by_id(self, parcel_id: str) -> Optional[LandParcel]:
        return self.db.query(LandParcel).filter(LandParcel.id == parcel_id).first()

    def get_by_project_and_code(self, project_id: str, parcel_code: str) -> Optional[LandParcel]:
        return (
            self.db.query(LandParcel)
            .filter(LandParcel.project_id == project_id, LandParcel.parcel_code == parcel_code)
            .first()
        )

    def get_standalone_by_code(self, parcel_code: str) -> Optional[LandParcel]:
        """Return a standalone (project_id IS NULL) parcel matching parcel_code."""
        return (
            self.db.query(LandParcel)
            .filter(LandParcel.project_id.is_(None), LandParcel.parcel_code == parcel_code)
            .first()
        )

    def list(self, project_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[LandParcel]:
        query = self.db.query(LandParcel)
        if project_id:
            query = query.filter(LandParcel.project_id == project_id)
        return query.offset(skip).limit(limit).all()

    def count(self, project_id: Optional[str] = None) -> int:
        query = self.db.query(LandParcel)
        if project_id:
            query = query.filter(LandParcel.project_id == project_id)
        return query.count()

    def update(self, parcel: LandParcel, data: LandParcelUpdate) -> LandParcel:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(parcel, field, value)
        self.db.commit()
        self.db.refresh(parcel)
        return parcel

    def delete(self, parcel: LandParcel) -> None:
        self.db.delete(parcel)
        self.db.commit()


class LandAssumptionsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, parcel_id: str, data: LandAssumptionCreate, buildable_area: Optional[float], sellable_area: Optional[float]) -> LandAssumptions:
        assumptions = LandAssumptions(
            parcel_id=parcel_id,
            target_use=data.target_use,
            expected_sellable_ratio=data.expected_sellable_ratio,
            expected_buildable_area_sqm=buildable_area,
            expected_sellable_area_sqm=sellable_area,
            parking_ratio=data.parking_ratio,
            service_area_ratio=data.service_area_ratio,
            notes=data.notes,
        )
        self.db.add(assumptions)
        self.db.commit()
        self.db.refresh(assumptions)
        return assumptions

    def get_by_parcel(self, parcel_id: str) -> List[LandAssumptions]:
        return (
            self.db.query(LandAssumptions)
            .filter(LandAssumptions.parcel_id == parcel_id)
            .all()
        )


class LandValuationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, parcel_id: str, data: LandValuationCreate, gdv: Optional[float], cost: Optional[float], rlv: Optional[float], rlv_per_sqm: Optional[float]) -> LandValuation:
        valuation = LandValuation(
            parcel_id=parcel_id,
            scenario_name=data.scenario_name,
            scenario_type=data.scenario_type.value,
            assumed_sale_price_per_sqm=data.assumed_sale_price_per_sqm,
            assumed_cost_per_sqm=data.assumed_cost_per_sqm,
            expected_gdv=gdv,
            expected_cost=cost,
            residual_land_value=rlv,
            land_value_per_sqm=rlv_per_sqm,
            valuation_notes=data.valuation_notes,
        )
        self.db.add(valuation)
        self.db.commit()
        self.db.refresh(valuation)
        return valuation

    def list_by_parcel(self, parcel_id: str) -> List[LandValuation]:
        return (
            self.db.query(LandValuation)
            .filter(LandValuation.parcel_id == parcel_id)
            .all()
        )

    def get_latest_engine_valuation(self, parcel_id: str) -> Optional[LandValuation]:
        """Return the most recently created engine valuation for a parcel.

        Only returns valuations that have engine-computed RLV data
        (``max_land_bid IS NOT NULL``). Returns ``None`` when no such
        valuation exists.
        """
        return (
            self.db.query(LandValuation)
            .filter(
                LandValuation.parcel_id == parcel_id,
                LandValuation.max_land_bid.isnot(None),
            )
            .order_by(LandValuation.created_at.desc())
            .limit(1)
            .first()
        )

    def create_from_engine(
        self,
        parcel_id: str,
        data: LandValuationEngineRequest,
        outputs: ValuationOutputs,
    ) -> LandValuation:
        from datetime import date

        valuation = LandValuation(
            parcel_id=parcel_id,
            scenario_name=data.scenario_name,
            scenario_type=data.scenario_type.value,
            expected_gdv=data.gdv,
            expected_cost=outputs.total_cost,
            residual_land_value=outputs.land_value,
            land_value_per_sqm=outputs.land_value_per_sqm,
            max_land_bid=outputs.max_land_bid,
            residual_margin=outputs.residual_margin,
            valuation_date=date.today(),
            valuation_inputs={
                "gdv": data.gdv,
                "construction_cost": data.construction_cost,
                "soft_cost_percentage": data.soft_cost_percentage,
                "developer_margin_target": data.developer_margin_target,
                "sellable_area_sqm": data.sellable_area_sqm,
            },
            valuation_notes=data.valuation_notes,
        )
        self.db.add(valuation)
        self.db.commit()
        self.db.refresh(valuation)
        return valuation
