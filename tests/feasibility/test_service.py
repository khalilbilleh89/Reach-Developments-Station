"""
Tests for the feasibility service layer.

Validates business logic, project linkage, and assumption completeness checks.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.feasibility.schemas import FeasibilityAssumptionsCreate, FeasibilityRunCreate
from app.modules.feasibility.service import FeasibilityService
from app.shared.enums.finance import FeasibilityScenarioType


def _make_project(db: Session, code: str = "PRJ-FS") -> str:
    from app.modules.projects.models import Project

    project = Project(name="Feasibility Project", code=code)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project.id


_VALID_ASSUMPTIONS = FeasibilityAssumptionsCreate(
    sellable_area_sqm=1000.0,
    avg_sale_price_per_sqm=3000.0,
    construction_cost_per_sqm=800.0,
    soft_cost_ratio=0.10,
    finance_cost_ratio=0.05,
    sales_cost_ratio=0.03,
    development_period_months=24,
)


# ---------------------------------------------------------------------------
# Run creation
# ---------------------------------------------------------------------------

def test_create_feasibility_run(db_session: Session):
    project_id = _make_project(db_session)
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(
        FeasibilityRunCreate(
            project_id=project_id,
            scenario_name="Base Case",
            scenario_type=FeasibilityScenarioType.BASE,
        )
    )
    assert run.id is not None
    assert run.project_id == project_id
    assert run.scenario_name == "Base Case"
    assert run.scenario_type == FeasibilityScenarioType.BASE


def test_create_feasibility_run_invalid_project(db_session: Session):
    service = FeasibilityService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.create_feasibility_run(
            FeasibilityRunCreate(
                project_id="no-such-project",
                scenario_name="Test",
            )
        )
    assert exc_info.value.status_code == 404


def test_get_feasibility_run_not_found(db_session: Session):
    service = FeasibilityService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.get_feasibility_run("no-such-run")
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------

def test_update_assumptions(db_session: Session):
    project_id = _make_project(db_session, code="PRJ-ASM")
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(
        FeasibilityRunCreate(project_id=project_id, scenario_name="Base")
    )
    assumptions = service.update_assumptions(run.id, _VALID_ASSUMPTIONS)
    assert assumptions.run_id == run.id
    assert assumptions.sellable_area_sqm == pytest.approx(1000.0)
    assert assumptions.avg_sale_price_per_sqm == pytest.approx(3000.0)


def test_update_assumptions_invalid_run(db_session: Session):
    service = FeasibilityService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.update_assumptions("no-such-run", _VALID_ASSUMPTIONS)
    assert exc_info.value.status_code == 404


def test_get_assumptions_not_set_raises_404(db_session: Session):
    project_id = _make_project(db_session, code="PRJ-NOASM")
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(
        FeasibilityRunCreate(project_id=project_id, scenario_name="Base")
    )
    with pytest.raises(HTTPException) as exc_info:
        service.get_assumptions(run.id)
    assert exc_info.value.status_code == 404


def test_upsert_assumptions_replaces_existing(db_session: Session):
    project_id = _make_project(db_session, code="PRJ-UPS")
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(
        FeasibilityRunCreate(project_id=project_id, scenario_name="Base")
    )
    service.update_assumptions(run.id, _VALID_ASSUMPTIONS)
    updated_data = FeasibilityAssumptionsCreate(
        sellable_area_sqm=2000.0,
        avg_sale_price_per_sqm=4000.0,
        construction_cost_per_sqm=900.0,
        soft_cost_ratio=0.12,
        finance_cost_ratio=0.06,
        sales_cost_ratio=0.04,
        development_period_months=36,
    )
    assumptions = service.update_assumptions(run.id, updated_data)
    assert assumptions.sellable_area_sqm == pytest.approx(2000.0)
    assert assumptions.development_period_months == 36


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------

def test_run_feasibility_calculation(db_session: Session):
    project_id = _make_project(db_session, code="PRJ-CALC")
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(
        FeasibilityRunCreate(project_id=project_id, scenario_name="Base")
    )
    service.update_assumptions(run.id, _VALID_ASSUMPTIONS)
    result = service.run_feasibility_calculation(run.id)
    assert result.gdv == pytest.approx(3_000_000.0)
    assert result.total_cost == pytest.approx(1_010_000.0)
    assert result.developer_profit == pytest.approx(1_990_000.0)


def test_run_feasibility_calculation_without_assumptions_raises_422(db_session: Session):
    project_id = _make_project(db_session, code="PRJ-NOASMCALC")
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(
        FeasibilityRunCreate(project_id=project_id, scenario_name="Base")
    )
    with pytest.raises(HTTPException) as exc_info:
        service.run_feasibility_calculation(run.id)
    assert exc_info.value.status_code == 422


def test_run_feasibility_calculation_invalid_run_raises_404(db_session: Session):
    service = FeasibilityService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.run_feasibility_calculation("no-such-run")
    assert exc_info.value.status_code == 404


def test_get_feasibility_result_not_calculated_raises_404(db_session: Session):
    project_id = _make_project(db_session, code="PRJ-NORES")
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(
        FeasibilityRunCreate(project_id=project_id, scenario_name="Base")
    )
    with pytest.raises(HTTPException) as exc_info:
        service.get_feasibility_result(run.id)
    assert exc_info.value.status_code == 404


def test_recalculate_replaces_result(db_session: Session):
    project_id = _make_project(db_session, code="PRJ-RECALC")
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(
        FeasibilityRunCreate(project_id=project_id, scenario_name="Base")
    )
    service.update_assumptions(run.id, _VALID_ASSUMPTIONS)
    result1 = service.run_feasibility_calculation(run.id)

    updated_data = FeasibilityAssumptionsCreate(
        sellable_area_sqm=2000.0,
        avg_sale_price_per_sqm=3000.0,
        construction_cost_per_sqm=800.0,
        soft_cost_ratio=0.10,
        finance_cost_ratio=0.05,
        sales_cost_ratio=0.03,
        development_period_months=24,
    )
    service.update_assumptions(run.id, updated_data)
    result2 = service.run_feasibility_calculation(run.id)

    assert result1.id == result2.id
    assert result2.gdv == pytest.approx(6_000_000.0)
