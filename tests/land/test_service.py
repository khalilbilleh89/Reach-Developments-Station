"""
Tests for the land service layer.

Validates business logic, project linkage, derived calculations, and
boundary protection for the Land Underwriting domain.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.land.schemas import (
    LandAssumptionCreate,
    LandParcelCreate,
    LandParcelUpdate,
    LandValuationCreate,
)
from app.modules.land.service import LandService
from app.shared.enums.project import LandParcelStatus, LandScenarioType


def _make_project(db: Session, code: str = "PRJ-LAND-SVC") -> str:
    from app.modules.projects.models import Project

    project = Project(name="Land Service Project", code=code)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project.id


def _make_parcel(db: Session, code: str = "PCL-SVC-001", project_id: str | None = None) -> str:
    service = LandService(db)
    parcel = service.create_parcel(
        LandParcelCreate(
            parcel_name="Service Test Parcel",
            parcel_code=code,
            land_area_sqm=10000.0,
            permitted_far=2.5,
            project_id=project_id,
        )
    )
    return parcel.id


# ---------------------------------------------------------------------------
# Parcel creation
# ---------------------------------------------------------------------------

def test_create_parcel_with_project(db_session: Session):
    """LandParcel linked to an existing project is created successfully."""
    project_id = _make_project(db_session)
    service = LandService(db_session)
    parcel = service.create_parcel(
        LandParcelCreate(
            project_id=project_id,
            parcel_name="Project Parcel",
            parcel_code="PCL-WITH-PRJ",
        )
    )
    assert parcel.id is not None
    assert parcel.project_id == project_id
    assert parcel.parcel_code == "PCL-WITH-PRJ"
    assert parcel.status == LandParcelStatus.DRAFT


def test_create_parcel_without_project(db_session: Session):
    """LandParcel can be created without a project (pre-project land intake)."""
    service = LandService(db_session)
    parcel = service.create_parcel(
        LandParcelCreate(parcel_name="Standalone Parcel", parcel_code="PCL-NO-PRJ")
    )
    assert parcel.id is not None
    assert parcel.project_id is None
    assert parcel.parcel_code == "PCL-NO-PRJ"


def test_create_parcel_invalid_project_raises_404(db_session: Session):
    """Providing a non-existent project_id raises HTTP 404."""
    service = LandService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.create_parcel(
            LandParcelCreate(
                project_id="no-such-project",
                parcel_name="Bad Parcel",
                parcel_code="PCL-BAD",
            )
        )
    assert exc_info.value.status_code == 404


def test_create_parcel_duplicate_code_in_project_raises_409(db_session: Session):
    """Duplicate parcel_code within the same project raises HTTP 409."""
    project_id = _make_project(db_session)
    service = LandService(db_session)
    service.create_parcel(
        LandParcelCreate(project_id=project_id, parcel_name="First", parcel_code="PCL-DUP")
    )
    with pytest.raises(HTTPException) as exc_info:
        service.create_parcel(
            LandParcelCreate(project_id=project_id, parcel_name="Second", parcel_code="PCL-DUP")
        )
    assert exc_info.value.status_code == 409


def test_create_standalone_parcel_duplicate_code_raises_409(db_session: Session):
    """Duplicate parcel_code among standalone parcels raises HTTP 409."""
    service = LandService(db_session)
    service.create_parcel(LandParcelCreate(parcel_name="First SA", parcel_code="PCL-SA-DUP"))
    with pytest.raises(HTTPException) as exc_info:
        service.create_parcel(LandParcelCreate(parcel_name="Second SA", parcel_code="PCL-SA-DUP"))
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Parcel retrieval and update
# ---------------------------------------------------------------------------

def test_get_parcel_by_id(db_session: Session):
    """get_parcel returns the parcel for a valid ID."""
    parcel_id = _make_parcel(db_session)
    service = LandService(db_session)
    result = service.get_parcel(parcel_id)
    assert result.id == parcel_id


def test_get_parcel_not_found_raises_404(db_session: Session):
    """get_parcel raises HTTP 404 for an unknown ID."""
    service = LandService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.get_parcel("no-such-parcel")
    assert exc_info.value.status_code == 404


def test_list_parcels_without_filter(db_session: Session):
    """list_parcels returns all parcels when no filter is applied."""
    _make_parcel(db_session, code="PCL-LIST-001")
    _make_parcel(db_session, code="PCL-LIST-002")
    service = LandService(db_session)
    result = service.list_parcels()
    assert result.total >= 2


def test_list_parcels_filtered_by_project(db_session: Session):
    """list_parcels filtered by project_id returns only project parcels."""
    project_id = _make_project(db_session, code="PRJ-FILTER")
    service = LandService(db_session)
    service.create_parcel(
        LandParcelCreate(project_id=project_id, parcel_name="P1", parcel_code="PCL-FLT-001")
    )
    service.create_parcel(
        LandParcelCreate(project_id=project_id, parcel_name="P2", parcel_code="PCL-FLT-002")
    )
    # Standalone parcel — must not appear in project-filtered list
    service.create_parcel(LandParcelCreate(parcel_name="Standalone", parcel_code="PCL-FLT-SA"))

    result = service.list_parcels(project_id=project_id)
    assert result.total == 2
    assert all(item.project_id == project_id for item in result.items)


def test_update_parcel_status(db_session: Session):
    """update_parcel changes the parcel status correctly."""
    parcel_id = _make_parcel(db_session, code="PCL-UPD")
    service = LandService(db_session)
    updated = service.update_parcel(parcel_id, LandParcelUpdate(status=LandParcelStatus.UNDER_REVIEW))
    assert updated.status == LandParcelStatus.UNDER_REVIEW


def test_update_parcel_not_found_raises_404(db_session: Session):
    """update_parcel raises HTTP 404 for an unknown parcel ID."""
    service = LandService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.update_parcel("no-such-parcel", LandParcelUpdate(city="Dubai"))
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Assumptions — boundary: owned by land, not feasibility
# ---------------------------------------------------------------------------

def test_create_assumptions_derives_areas(db_session: Session):
    """Assumptions creation auto-computes buildable and sellable areas from parcel data."""
    parcel_id = _make_parcel(db_session, code="PCL-ASM-DERIVED")
    service = LandService(db_session)
    # land_area=10000, FAR=2.5 → buildable=25000; ratio=0.8 → sellable=20000
    assumptions = service.create_assumptions(
        parcel_id,
        LandAssumptionCreate(target_use="residential", expected_sellable_ratio=0.8),
    )
    assert assumptions.expected_buildable_area_sqm == pytest.approx(25000.0, rel=1e-3)
    assert assumptions.expected_sellable_area_sqm == pytest.approx(20000.0, rel=1e-3)
    assert assumptions.parcel_id == parcel_id


def test_create_assumptions_without_far_skips_derivation(db_session: Session):
    """When parcel has no FAR set, derived areas remain None."""
    service = LandService(db_session)
    parcel = service.create_parcel(
        LandParcelCreate(
            parcel_name="No FAR Parcel",
            parcel_code="PCL-NO-FAR",
            land_area_sqm=5000.0,
            # permitted_far intentionally omitted
        )
    )
    assumptions = service.create_assumptions(
        parcel.id,
        LandAssumptionCreate(expected_sellable_ratio=0.75),
    )
    assert assumptions.expected_buildable_area_sqm is None
    assert assumptions.expected_sellable_area_sqm is None


def test_create_assumptions_invalid_parcel_raises_404(db_session: Session):
    """create_assumptions raises HTTP 404 for an unknown parcel ID."""
    service = LandService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.create_assumptions("no-such-parcel", LandAssumptionCreate(target_use="mixed_use"))
    assert exc_info.value.status_code == 404


def test_get_assumptions_invalid_parcel_raises_404(db_session: Session):
    """get_assumptions raises HTTP 404 for an unknown parcel ID."""
    service = LandService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.get_assumptions("no-such-parcel")
    assert exc_info.value.status_code == 404


def test_assumptions_pre_project_parcel(db_session: Session):
    """Assumptions can be attached to a standalone (pre-project) parcel."""
    service = LandService(db_session)
    parcel = service.create_parcel(
        LandParcelCreate(
            parcel_name="Pre-Project Parcel",
            parcel_code="PCL-PP-ASM",
            land_area_sqm=8000.0,
            permitted_far=3.0,
        )
    )
    assert parcel.project_id is None
    assumptions = service.create_assumptions(
        parcel.id,
        LandAssumptionCreate(target_use="commercial", expected_sellable_ratio=0.65),
    )
    assert assumptions.parcel_id == parcel.id
    assert assumptions.expected_buildable_area_sqm == pytest.approx(24000.0, rel=1e-3)


# ---------------------------------------------------------------------------
# Valuation — boundary: owned by land, derives from land assumptions
# ---------------------------------------------------------------------------

def test_create_valuation_derives_rlv(db_session: Session):
    """Valuation creation computes GDV, cost, and residual land value correctly."""
    parcel_id = _make_parcel(db_session, code="PCL-VAL-RLV")
    service = LandService(db_session)
    service.create_assumptions(parcel_id, LandAssumptionCreate(expected_sellable_ratio=0.8))
    # sellable = 10000 * 2.5 * 0.8 = 20000
    valuation = service.create_valuation(
        parcel_id,
        LandValuationCreate(
            scenario_name="Base Case",
            scenario_type=LandScenarioType.BASE,
            assumed_sale_price_per_sqm=5000.0,
            assumed_cost_per_sqm=3000.0,
        ),
    )
    # GDV = 20000 * 5000 = 100_000_000
    # Cost = 20000 * 3000 = 60_000_000
    # RLV = 40_000_000
    # RLV/sqm = 40_000_000 / 10000 = 4000
    assert valuation.expected_gdv == pytest.approx(100_000_000.0, rel=1e-3)
    assert valuation.expected_cost == pytest.approx(60_000_000.0, rel=1e-3)
    assert valuation.residual_land_value == pytest.approx(40_000_000.0, rel=1e-3)
    assert valuation.land_value_per_sqm == pytest.approx(4000.0, rel=1e-3)


def test_create_valuation_without_assumptions_has_no_derived_values(db_session: Session):
    """Valuation without prior assumptions has None for all derived fields."""
    parcel_id = _make_parcel(db_session, code="PCL-VAL-NOASM")
    service = LandService(db_session)
    valuation = service.create_valuation(
        parcel_id,
        LandValuationCreate(
            scenario_name="Empty Scenario",
            scenario_type=LandScenarioType.BASE,
            assumed_sale_price_per_sqm=5000.0,
            assumed_cost_per_sqm=3000.0,
        ),
    )
    assert valuation.expected_gdv is None
    assert valuation.expected_cost is None
    assert valuation.residual_land_value is None


def test_create_valuation_invalid_parcel_raises_404(db_session: Session):
    """create_valuation raises HTTP 404 for an unknown parcel ID."""
    service = LandService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.create_valuation(
            "no-such-parcel",
            LandValuationCreate(scenario_name="X", scenario_type=LandScenarioType.BASE),
        )
    assert exc_info.value.status_code == 404


def test_list_valuations_invalid_parcel_raises_404(db_session: Session):
    """list_valuations raises HTTP 404 for an unknown parcel ID."""
    service = LandService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.list_valuations("no-such-parcel")
    assert exc_info.value.status_code == 404


def test_valuation_pre_project_parcel(db_session: Session):
    """Valuations can be created for a standalone (pre-project) parcel."""
    service = LandService(db_session)
    parcel = service.create_parcel(
        LandParcelCreate(
            parcel_name="Pre-Project Valuation",
            parcel_code="PCL-PP-VAL",
            land_area_sqm=10000.0,
            permitted_far=2.5,
        )
    )
    assert parcel.project_id is None
    service.create_assumptions(parcel.id, LandAssumptionCreate(expected_sellable_ratio=0.8))
    valuation = service.create_valuation(
        parcel.id,
        LandValuationCreate(
            scenario_name="Pre-Project Base",
            scenario_type=LandScenarioType.BASE,
            assumed_sale_price_per_sqm=4500.0,
            assumed_cost_per_sqm=2500.0,
        ),
    )
    assert valuation.parcel_id == parcel.id
    # GDV = 20000 * 4500 = 90_000_000
    assert valuation.expected_gdv == pytest.approx(90_000_000.0, rel=1e-3)


def test_multiple_valuation_scenarios(db_session: Session):
    """Multiple valuation scenarios (base, upside, downside) can exist on one parcel."""
    parcel_id = _make_parcel(db_session, code="PCL-MULTI-SCEN")
    service = LandService(db_session)
    service.create_assumptions(parcel_id, LandAssumptionCreate(expected_sellable_ratio=0.75))
    for scenario_type, name in [
        (LandScenarioType.BASE, "Base"),
        (LandScenarioType.UPSIDE, "Upside"),
        (LandScenarioType.DOWNSIDE, "Downside"),
    ]:
        service.create_valuation(
            parcel_id,
            LandValuationCreate(scenario_name=name, scenario_type=scenario_type),
        )
    valuations = service.list_valuations(parcel_id)
    assert len(valuations) == 3
