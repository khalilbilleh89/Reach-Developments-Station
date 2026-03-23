"""
land.repository

Data access layer for LandParcel, LandAssumptions, LandValuation, and
LandAssembly / LandAssemblyParcel entities.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.land.models import (
    LandAssembly,
    LandAssemblyParcel,
    LandAssumptions,
    LandParcel,
    LandValuation,
)
from app.modules.land.schemas import (
    LandAssumptionCreate,
    LandParcelCreate,
    LandParcelUpdate,
    LandValuationCreate,
    LandValuationEngineRequest,
)
from app.modules.land.engines.valuation_engine import ValuationOutputs
from app.modules.land.aggregation_engine import AssemblyAggregationResult


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


class LandAssemblyRepository:
    """Data access layer for LandAssembly and LandAssemblyParcel entities.

    Business math and validation logic must not appear here.  This layer
    handles only persistence and retrieval.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Assembly CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        assembly_name: str,
        assembly_code: str,
        notes: Optional[str],
        status: str,
        parcel_ids: List[str],
        result: AssemblyAggregationResult,
    ) -> LandAssembly:
        """Persist a new assembly and its parcel membership records."""
        assembly = LandAssembly(
            assembly_name=assembly_name,
            assembly_code=assembly_code,
            notes=notes,
            status=status,
            parcel_count=result.parcel_count,
            total_area_sqm=result.total_area_sqm,
            total_frontage_m=result.total_frontage_m,
            total_acquisition_price=result.total_acquisition_price,
            total_transaction_cost=result.total_transaction_cost,
            effective_land_basis=result.effective_land_basis,
            weighted_permitted_far=result.weighted_permitted_far,
            dominant_zoning_category=result.dominant_zoning_category,
            mixed_zoning=result.mixed_zoning,
            has_utilities=result.has_utilities,
            has_corner_plot=result.has_corner_plot,
            assembly_results_json={
                "parcel_count": result.parcel_count,
                "total_area_sqm": result.total_area_sqm,
                "total_frontage_m": result.total_frontage_m,
                "total_acquisition_price": result.total_acquisition_price,
                "total_transaction_cost": result.total_transaction_cost,
                "effective_land_basis": result.effective_land_basis,
                "weighted_permitted_far": result.weighted_permitted_far,
                "dominant_zoning_category": result.dominant_zoning_category,
                "mixed_zoning": result.mixed_zoning,
                "has_utilities": result.has_utilities,
                "has_corner_plot": result.has_corner_plot,
                "zoning_category_counts": result.zoning_category_counts,
            },
        )
        self.db.add(assembly)
        self.db.flush()  # obtain assembly.id before creating join records

        for parcel_id in parcel_ids:
            membership = LandAssemblyParcel(
                assembly_id=assembly.id,
                parcel_id=parcel_id,
            )
            self.db.add(membership)

        self.db.commit()
        self.db.refresh(assembly)
        return assembly

    def get_by_id(self, assembly_id: str) -> Optional[LandAssembly]:
        return (
            self.db.query(LandAssembly)
            .filter(LandAssembly.id == assembly_id)
            .first()
        )

    def get_by_code(self, assembly_code: str) -> Optional[LandAssembly]:
        return (
            self.db.query(LandAssembly)
            .filter(LandAssembly.assembly_code == assembly_code)
            .first()
        )

    def list(self, skip: int = 0, limit: int = 100) -> List[LandAssembly]:
        return (
            self.db.query(LandAssembly)
            .order_by(LandAssembly.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        return self.db.query(LandAssembly).count()

    def update_aggregation(
        self, assembly: LandAssembly, result: AssemblyAggregationResult
    ) -> LandAssembly:
        """Update snapshot fields on an existing assembly after recomputation."""
        assembly.parcel_count = result.parcel_count
        assembly.total_area_sqm = result.total_area_sqm
        assembly.total_frontage_m = result.total_frontage_m
        assembly.total_acquisition_price = result.total_acquisition_price
        assembly.total_transaction_cost = result.total_transaction_cost
        assembly.effective_land_basis = result.effective_land_basis
        assembly.weighted_permitted_far = result.weighted_permitted_far
        assembly.dominant_zoning_category = result.dominant_zoning_category
        assembly.mixed_zoning = result.mixed_zoning
        assembly.has_utilities = result.has_utilities
        assembly.has_corner_plot = result.has_corner_plot
        assembly.assembly_results_json = {
            "parcel_count": result.parcel_count,
            "total_area_sqm": result.total_area_sqm,
            "total_frontage_m": result.total_frontage_m,
            "total_acquisition_price": result.total_acquisition_price,
            "total_transaction_cost": result.total_transaction_cost,
            "effective_land_basis": result.effective_land_basis,
            "weighted_permitted_far": result.weighted_permitted_far,
            "dominant_zoning_category": result.dominant_zoning_category,
            "mixed_zoning": result.mixed_zoning,
            "has_utilities": result.has_utilities,
            "has_corner_plot": result.has_corner_plot,
            "zoning_category_counts": result.zoning_category_counts,
        }
        self.db.commit()
        self.db.refresh(assembly)
        return assembly

    def delete(self, assembly: LandAssembly) -> None:
        self.db.delete(assembly)
        self.db.commit()

    # ------------------------------------------------------------------
    # Membership queries
    # ------------------------------------------------------------------

    def get_parcel_ids(self, assembly_id: str) -> List[str]:
        """Return the ordered list of parcel IDs that belong to an assembly.

        Ordered by (created_at, parcel_id) to guarantee stable, deterministic
        ordering across queries and DB backends.
        """
        rows = (
            self.db.query(LandAssemblyParcel.parcel_id)
            .filter(LandAssemblyParcel.assembly_id == assembly_id)
            .order_by(LandAssemblyParcel.created_at, LandAssemblyParcel.parcel_id)
            .all()
        )
        return [row[0] for row in rows]

    def get_parcels_for_assembly(self, parcel_ids: List[str]) -> List[LandParcel]:
        """Fetch all LandParcel records for the given IDs in a single query.

        Parcels whose IDs are not found (e.g. deleted since assembly creation)
        are omitted from the result.  Ordering follows the supplied id list.
        """
        if not parcel_ids:
            return []
        parcels_by_id = {
            p.id: p
            for p in self.db.query(LandParcel).filter(LandParcel.id.in_(parcel_ids)).all()
        }
        return [parcels_by_id[pid] for pid in parcel_ids if pid in parcels_by_id]

    def get_assembly_id_for_parcel(self, parcel_id: str) -> Optional[str]:
        """Return the assembly_id that currently owns a parcel, or None."""
        row = (
            self.db.query(LandAssemblyParcel.assembly_id)
            .filter(LandAssemblyParcel.parcel_id == parcel_id)
            .first()
        )
        return row[0] if row else None
