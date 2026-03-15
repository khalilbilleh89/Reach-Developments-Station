"""
Tests for the pricing service layer.

Validates business logic, unit linkage, and pricing calculation correctness.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.pricing.schemas import UnitPricingAttributesCreate
from app.modules.pricing.service import PricingService


def _make_unit(db: Session, project_code: str = "PRJ-PS") -> str:
    """Create a full hierarchy and return a unit ID."""
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit

    project = Project(name="Pricing Project", code=project_code)
    db.add(project)
    db.flush()

    phase = Phase(project_id=project.id, name="Phase 1", sequence=1)
    db.add(phase)
    db.flush()

    building = Building(phase_id=phase.id, name="Block A", code="BLK-A")
    db.add(building)
    db.flush()

    floor = Floor(building_id=building.id, name="Floor 1", code="FL-01", sequence_number=1)
    db.add(floor)
    db.flush()

    unit = Unit(floor_id=floor.id, unit_number="101", unit_type="studio", internal_area=100.0)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit.id


_VALID_ATTRS = UnitPricingAttributesCreate(
    base_price_per_sqm=5000.0,
    floor_premium=10_000.0,
    view_premium=15_000.0,
    corner_premium=5_000.0,
    size_adjustment=2_000.0,
    custom_adjustment=-1_000.0,
)


# ---------------------------------------------------------------------------
# Attribute management
# ---------------------------------------------------------------------------

def test_set_pricing_attributes(db_session: Session):
    unit_id = _make_unit(db_session)
    service = PricingService(db_session)
    attrs = service.set_pricing_attributes(unit_id, _VALID_ATTRS)
    assert attrs.unit_id == unit_id
    assert attrs.base_price_per_sqm == pytest.approx(5000.0)
    assert attrs.floor_premium == pytest.approx(10_000.0)


def test_set_pricing_attributes_invalid_unit(db_session: Session):
    service = PricingService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.set_pricing_attributes("no-such-unit", _VALID_ATTRS)
    assert exc_info.value.status_code == 404


def test_get_pricing_attributes(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-GETA")
    service = PricingService(db_session)
    service.set_pricing_attributes(unit_id, _VALID_ATTRS)
    attrs = service.get_pricing_attributes(unit_id)
    assert attrs.unit_id == unit_id
    assert attrs.view_premium == pytest.approx(15_000.0)


def test_get_pricing_attributes_not_set(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-NOATTR")
    service = PricingService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.get_pricing_attributes(unit_id)
    assert exc_info.value.status_code == 404


def test_get_pricing_attributes_invalid_unit(db_session: Session):
    service = PricingService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.get_pricing_attributes("no-such-unit")
    assert exc_info.value.status_code == 404


def test_upsert_replaces_existing_attributes(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-UPS")
    service = PricingService(db_session)
    service.set_pricing_attributes(unit_id, _VALID_ATTRS)
    updated = UnitPricingAttributesCreate(
        base_price_per_sqm=6000.0,
        floor_premium=20_000.0,
        view_premium=0.0,
        corner_premium=0.0,
        size_adjustment=0.0,
        custom_adjustment=0.0,
    )
    attrs = service.set_pricing_attributes(unit_id, updated)
    assert attrs.base_price_per_sqm == pytest.approx(6000.0)
    assert attrs.floor_premium == pytest.approx(20_000.0)
    assert attrs.view_premium == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Price calculation
# ---------------------------------------------------------------------------

def test_calculate_unit_price(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-CALC")
    service = PricingService(db_session)
    service.set_pricing_attributes(unit_id, _VALID_ATTRS)
    result = service.calculate_unit_price(unit_id)
    # unit_area = internal_area = 100.0 (no gross_area set)
    # base = 100 * 5000 = 500_000
    # premiums = 10_000 + 15_000 + 5_000 + 2_000 + (-1_000) = 31_000
    # final = 531_000
    assert result.unit_id == unit_id
    assert result.unit_area == pytest.approx(100.0)
    assert result.base_unit_price == pytest.approx(500_000.0)
    assert result.premium_total == pytest.approx(31_000.0)
    assert result.final_unit_price == pytest.approx(531_000.0)


def test_calculate_unit_price_invalid_unit(db_session: Session):
    service = PricingService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.calculate_unit_price("no-such-unit")
    assert exc_info.value.status_code == 404


def test_calculate_unit_price_no_attributes(db_session: Session):
    unit_id = _make_unit(db_session, "PRJ-NOCALC")
    service = PricingService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.calculate_unit_price(unit_id)
    assert exc_info.value.status_code == 422


def test_calculate_project_price_summary(db_session: Session):
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit

    project = Project(name="Summary Project", code="PRJ-SUM")
    db_session.add(project)
    db_session.flush()

    phase = Phase(project_id=project.id, name="Phase 1", sequence=1)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Block A", code="BLK-A")
    db_session.add(building)
    db_session.flush()

    floor = Floor(building_id=building.id, name="Floor 1", code="FL-01", sequence_number=1)
    db_session.add(floor)
    db_session.flush()

    unit1 = Unit(floor_id=floor.id, unit_number="101", unit_type="studio", internal_area=100.0)
    unit2 = Unit(floor_id=floor.id, unit_number="102", unit_type="studio", internal_area=80.0)
    db_session.add_all([unit1, unit2])
    db_session.commit()
    db_session.refresh(unit1)
    db_session.refresh(unit2)

    service = PricingService(db_session)
    attrs = UnitPricingAttributesCreate(
        base_price_per_sqm=5000.0,
        floor_premium=0.0,
        view_premium=0.0,
        corner_premium=0.0,
        size_adjustment=0.0,
        custom_adjustment=0.0,
    )
    service.set_pricing_attributes(unit1.id, attrs)
    service.set_pricing_attributes(unit2.id, attrs)

    summary = service.calculate_project_price_summary(project.id)
    assert summary.project_id == project.id
    assert summary.total_units_priced == 2
    # total = 100 * 5000 + 80 * 5000 = 500_000 + 400_000 = 900_000
    assert summary.total_value == pytest.approx(900_000.0)


def test_calculate_project_price_summary_invalid_project(db_session: Session):
    service = PricingService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.calculate_project_price_summary("no-such-project")
    assert exc_info.value.status_code == 404


def test_calculate_project_price_summary_no_priced_units(db_session: Session):
    from app.modules.projects.models import Project

    project = Project(name="Empty Project", code="PRJ-EMPTY")
    db_session.add(project)
    db_session.commit()

    service = PricingService(db_session)
    summary = service.calculate_project_price_summary(project.id)
    assert summary.total_units_priced == 0
    assert summary.total_value == pytest.approx(0.0)
    assert summary.items == []


def test_project_summary_skips_units_with_incomplete_attributes(db_session: Session):
    """Units with missing pricing attributes must be skipped in project summary."""
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit

    project = Project(name="Skip Test Project", code="PRJ-SKIP")
    db_session.add(project)
    db_session.flush()

    phase = Phase(project_id=project.id, name="Phase 1", sequence=1)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Block A", code="BLK-A")
    db_session.add(building)
    db_session.flush()

    floor = Floor(building_id=building.id, name="Floor 1", code="FL-01", sequence_number=1)
    db_session.add(floor)
    db_session.flush()

    # unit1: fully priced; unit2: partially priced (missing fields stored as None)
    unit1 = Unit(floor_id=floor.id, unit_number="101", unit_type="studio", internal_area=100.0)
    unit2 = Unit(floor_id=floor.id, unit_number="102", unit_type="studio", internal_area=80.0)
    db_session.add_all([unit1, unit2])
    db_session.commit()
    db_session.refresh(unit1)
    db_session.refresh(unit2)

    service = PricingService(db_session)

    # Set complete attributes for unit1 only
    complete_attrs = UnitPricingAttributesCreate(
        base_price_per_sqm=5000.0,
        floor_premium=0.0,
        view_premium=0.0,
        corner_premium=0.0,
        size_adjustment=0.0,
        custom_adjustment=0.0,
    )
    service.set_pricing_attributes(unit1.id, complete_attrs)

    # Manually insert an incomplete record for unit2 (base_price_per_sqm is None)
    from app.modules.pricing.models import UnitPricingAttributes
    incomplete = UnitPricingAttributes(unit_id=unit2.id)
    db_session.add(incomplete)
    db_session.commit()

    summary = service.calculate_project_price_summary(project.id)
    # Only unit1 should be included; unit2 must be skipped
    assert summary.total_units_priced == 1
    assert summary.total_value == pytest.approx(500_000.0)
    priced_ids = [item.unit_id for item in summary.items]
    assert unit1.id in priced_ids
    assert unit2.id not in priced_ids


def test_unit_price_and_summary_produce_consistent_outputs(db_session: Session):
    """Direct unit price and project summary must produce identical outputs for the same unit."""
    unit_id = _make_unit(db_session, "PRJ-CONS")
    service = PricingService(db_session)

    attrs = UnitPricingAttributesCreate(
        base_price_per_sqm=5000.0,
        floor_premium=10_000.0,
        view_premium=15_000.0,
        corner_premium=5_000.0,
        size_adjustment=2_000.0,
        custom_adjustment=-1_000.0,
    )
    service.set_pricing_attributes(unit_id, attrs)

    direct = service.calculate_unit_price(unit_id)

    from app.modules.projects.models import Project
    from app.modules.units.models import Unit
    from app.modules.floors.models import Floor
    from app.modules.buildings.models import Building
    from app.modules.phases.models import Phase

    unit = db_session.query(Unit).filter(Unit.id == unit_id).first()
    floor = db_session.query(Floor).filter(Floor.id == unit.floor_id).first()
    building = db_session.query(Building).filter(Building.id == floor.building_id).first()
    phase = db_session.query(Phase).filter(Phase.id == building.phase_id).first()

    summary = service.calculate_project_price_summary(phase.project_id)
    assert summary.total_units_priced == 1
    summary_item = summary.items[0]

    assert direct.base_unit_price == pytest.approx(summary_item.base_unit_price)
    assert direct.premium_total == pytest.approx(summary_item.premium_total)
    assert direct.final_unit_price == pytest.approx(summary_item.final_unit_price)
