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


# ---------------------------------------------------------------------------
# Pre-project independence tests (PR-B1)
# ---------------------------------------------------------------------------

def test_create_feasibility_run_without_project(db_session: Session):
    """FeasibilityRun can be created without a project (pre-project scenario)."""
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(
        FeasibilityRunCreate(scenario_name="Pre-Project Scenario")
    )
    assert run.id is not None
    assert run.project_id is None
    assert run.scenario_name == "Pre-Project Scenario"


def test_standalone_run_full_calculation(db_session: Session):
    """Full feasibility workflow executes without a project being present."""
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(
        FeasibilityRunCreate(scenario_name="Standalone Base", scenario_type=FeasibilityScenarioType.BASE)
    )
    assert run.project_id is None

    service.update_assumptions(run.id, _VALID_ASSUMPTIONS)
    result = service.run_feasibility_calculation(run.id)
    assert result.gdv == pytest.approx(3_000_000.0)
    assert result.developer_profit == pytest.approx(1_990_000.0)


# ---------------------------------------------------------------------------
# Scenario linkage (PR-FEAS-001)
# ---------------------------------------------------------------------------

def _make_scenario(db: Session, name: str = "Test Scenario") -> str:
    from app.modules.scenario.models import Scenario

    scenario = Scenario(name=name, code=name[:10].replace(" ", "-"), source_type="feasibility")
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario.id


def test_create_feasibility_run_with_scenario_id(db_session: Session):
    """FeasibilityRun can be created with a scenario_id linking it to the Scenario Engine."""
    scenario_id = _make_scenario(db_session, name="Baseline Scenario")
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(
        FeasibilityRunCreate(scenario_name="Scenario Run", scenario_id=scenario_id)
    )
    assert run.id is not None
    assert run.scenario_id == scenario_id


def test_create_feasibility_run_invalid_scenario_raises_404(db_session: Session):
    """FeasibilityRun creation with a non-existent scenario_id must raise 404."""
    service = FeasibilityService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.create_feasibility_run(
            FeasibilityRunCreate(scenario_name="Test", scenario_id="no-such-scenario")
        )
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Viability evaluation (PR-FEAS-001)
# ---------------------------------------------------------------------------

def test_calculation_result_contains_viability_fields(db_session: Session):
    """Feasibility result must include viability_status, risk_level, decision, payback_period."""
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(FeasibilityRunCreate(scenario_name="Viability Test"))
    service.update_assumptions(run.id, _VALID_ASSUMPTIONS)
    result = service.run_feasibility_calculation(run.id)
    assert result.viability_status is not None
    assert result.risk_level is not None
    assert result.decision is not None
    # payback_period is set for profitable scenarios
    assert result.payback_period is not None


def test_viable_project_returns_viable_decision(db_session: Session):
    """Project with high profit margin (≥20 %) must return VIABLE decision."""
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(FeasibilityRunCreate(scenario_name="High Margin"))
    # profit_margin ≈ 1_990_000 / 3_000_000 ≈ 66 % → VIABLE
    service.update_assumptions(run.id, _VALID_ASSUMPTIONS)
    result = service.run_feasibility_calculation(run.id)
    assert result.viability_status == "VIABLE"
    assert result.decision == "VIABLE"


def test_marginal_project_returns_marginal_decision(db_session: Session):
    """Project with 10-19 % profit margin must return MARGINAL decision."""
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(FeasibilityRunCreate(scenario_name="Marginal"))
    # Set assumptions so profit_margin ≈ 15 %
    # gdv = 1000 * 1000 = 1_000_000; construction = 1000 * 700 = 700_000
    # soft = 700_000 * 0.05 = 35_000; finance = 700_000 * 0.05 = 35_000
    # sales = 1_000_000 * 0.065 = 65_000; total_cost = 835_000
    # profit = 165_000; margin = 165_000 / 1_000_000 = 16.5 %
    marginal_assumptions = FeasibilityAssumptionsCreate(
        sellable_area_sqm=1000.0,
        avg_sale_price_per_sqm=1000.0,
        construction_cost_per_sqm=700.0,
        soft_cost_ratio=0.05,
        finance_cost_ratio=0.05,
        sales_cost_ratio=0.065,
        development_period_months=24,
    )
    service.update_assumptions(run.id, marginal_assumptions)
    result = service.run_feasibility_calculation(run.id)
    assert result.viability_status == "MARGINAL"
    assert result.decision == "MARGINAL"


def test_not_viable_project_returns_not_viable_decision(db_session: Session):
    """Project with profit margin < 10 % must return NOT_VIABLE decision."""
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(FeasibilityRunCreate(scenario_name="Not Viable"))
    # Set assumptions so profit_margin ≈ 5 %
    # gdv = 1000 * 1000 = 1_000_000; construction = 1000 * 850 = 850_000
    # soft = 850_000 * 0.05 = 42_500; finance = 850_000 * 0.03 = 25_500
    # sales = 1_000_000 * 0.03 = 30_000; total_cost = 948_000
    # profit = 52_000; margin = 5.2 %
    not_viable_assumptions = FeasibilityAssumptionsCreate(
        sellable_area_sqm=1000.0,
        avg_sale_price_per_sqm=1000.0,
        construction_cost_per_sqm=850.0,
        soft_cost_ratio=0.05,
        finance_cost_ratio=0.03,
        sales_cost_ratio=0.03,
        development_period_months=24,
    )
    service.update_assumptions(run.id, not_viable_assumptions)
    result = service.run_feasibility_calculation(run.id)
    assert result.viability_status == "NOT_VIABLE"
    assert result.decision == "NOT_VIABLE"


def test_payback_period_none_for_unprofitable_scenario(db_session: Session):
    """Payback period must be None when profit margin is zero or negative."""
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(FeasibilityRunCreate(scenario_name="Zero Profit"))
    # profit_margin = 0: gdv == total_cost
    zero_profit_assumptions = FeasibilityAssumptionsCreate(
        sellable_area_sqm=1000.0,
        avg_sale_price_per_sqm=1000.0,
        construction_cost_per_sqm=970.0,
        soft_cost_ratio=0.0,
        finance_cost_ratio=0.0,
        sales_cost_ratio=0.03,
        development_period_months=24,
    )
    service.update_assumptions(run.id, zero_profit_assumptions)
    result = service.run_feasibility_calculation(run.id)
    assert result.payback_period is None


# ---------------------------------------------------------------------------
# run_feasibility_for_scenario convenience method (PR-FEAS-001)
# ---------------------------------------------------------------------------

from app.modules.feasibility.schemas import FeasibilityRunRequest


def test_run_feasibility_for_scenario(db_session: Session):
    """run_feasibility_for_scenario should create run, assumptions, and return result."""
    service = FeasibilityService(db_session)
    req = FeasibilityRunRequest(
        scenario_name="Quick Eval",
        sellable_area_sqm=1000.0,
        avg_sale_price_per_sqm=3000.0,
        construction_cost_per_sqm=800.0,
        soft_cost_ratio=0.10,
        finance_cost_ratio=0.05,
        sales_cost_ratio=0.03,
        development_period_months=24,
    )
    result = service.run_feasibility_for_scenario(req)
    assert result.gdv == pytest.approx(3_000_000.0)
    assert result.viability_status == "VIABLE"
    assert result.decision == "VIABLE"


def test_run_feasibility_for_scenario_invalid_project(db_session: Session):
    """run_feasibility_for_scenario with non-existent project_id must raise 404."""
    service = FeasibilityService(db_session)
    req = FeasibilityRunRequest(
        project_id="no-such-project",
        scenario_name="Test",
        sellable_area_sqm=1000.0,
        avg_sale_price_per_sqm=3000.0,
        construction_cost_per_sqm=800.0,
        soft_cost_ratio=0.10,
        finance_cost_ratio=0.05,
        sales_cost_ratio=0.03,
        development_period_months=24,
    )
    with pytest.raises(HTTPException) as exc_info:
        service.run_feasibility_for_scenario(req)
    assert exc_info.value.status_code == 404


def test_run_feasibility_for_scenario_with_scenario_id(db_session: Session):
    """run_feasibility_for_scenario with valid scenario_id must link the run."""
    scenario_id = _make_scenario(db_session, name="FS Scenario")
    service = FeasibilityService(db_session)
    req = FeasibilityRunRequest(
        scenario_id=scenario_id,
        scenario_name="FS Run",
        sellable_area_sqm=1000.0,
        avg_sale_price_per_sqm=3000.0,
        construction_cost_per_sqm=800.0,
        soft_cost_ratio=0.10,
        finance_cost_ratio=0.05,
        sales_cost_ratio=0.03,
        development_period_months=24,
    )
    result = service.run_feasibility_for_scenario(req)
    assert result.gdv == pytest.approx(3_000_000.0)
    assert result.viability_status is not None


# ---------------------------------------------------------------------------
# Shared validation helper consistency (PR-FEAS-001A)
# ---------------------------------------------------------------------------

def test_create_run_and_run_for_scenario_use_same_project_validation(db_session: Session):
    """Both create_feasibility_run and run_feasibility_for_scenario must reject
    the same invalid project_id with 404, confirming shared validation logic."""
    service = FeasibilityService(db_session)

    with pytest.raises(HTTPException) as exc1:
        service.create_feasibility_run(
            FeasibilityRunCreate(project_id="no-such", scenario_name="Test A")
        )
    assert exc1.value.status_code == 404

    with pytest.raises(HTTPException) as exc2:
        service.run_feasibility_for_scenario(
            FeasibilityRunRequest(
                project_id="no-such",
                scenario_name="Test B",
                sellable_area_sqm=1000.0,
                avg_sale_price_per_sqm=3000.0,
                construction_cost_per_sqm=800.0,
                soft_cost_ratio=0.10,
                finance_cost_ratio=0.05,
                sales_cost_ratio=0.03,
                development_period_months=24,
            )
        )
    assert exc2.value.status_code == 404


def test_create_run_and_run_for_scenario_use_same_scenario_validation(db_session: Session):
    """Both code paths must reject the same invalid scenario_id with 404."""
    service = FeasibilityService(db_session)

    with pytest.raises(HTTPException) as exc1:
        service.create_feasibility_run(
            FeasibilityRunCreate(scenario_id="no-such", scenario_name="Test A")
        )
    assert exc1.value.status_code == 404

    with pytest.raises(HTTPException) as exc2:
        service.run_feasibility_for_scenario(
            FeasibilityRunRequest(
                scenario_id="no-such",
                scenario_name="Test B",
                sellable_area_sqm=1000.0,
                avg_sale_price_per_sqm=3000.0,
                construction_cost_per_sqm=800.0,
                soft_cost_ratio=0.10,
                finance_cost_ratio=0.05,
                sales_cost_ratio=0.03,
                development_period_months=24,
            )
        )
    assert exc2.value.status_code == 404


# ---------------------------------------------------------------------------
# Partial-state behaviour (PR-FEAS-001A)
#
# POST /feasibility/run performs sequential DB operations, not a single
# transaction.  If the calculation step raises, the run + assumptions already
# persisted remain retrievable.  This documents and validates that behaviour.
# ---------------------------------------------------------------------------

def test_partial_state_run_and_assumptions_persisted_without_result(db_session: Session):
    """A run with assumptions but no result is a valid intermediate state.

    This test documents the expected partial-state outcome: a run created via
    the step-by-step API (create run → set assumptions) has no result until
    POST .../calculate is called.  The run and assumptions are independently
    retrievable.
    """
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(FeasibilityRunCreate(scenario_name="Partial State"))
    service.update_assumptions(run.id, _VALID_ASSUMPTIONS)

    # Run exists and assumptions are persisted.
    fetched_run = service.get_feasibility_run(run.id)
    assert fetched_run.id == run.id
    fetched_assumptions = service.get_assumptions(run.id)
    assert fetched_assumptions.run_id == run.id

    # But no result exists yet — get_feasibility_result must return 404.
    with pytest.raises(HTTPException) as exc_info:
        service.get_feasibility_result(run.id)
    assert exc_info.value.status_code == 404


def test_partial_state_can_be_recovered_by_calculate(db_session: Session):
    """A run in partial state (run + assumptions, no result) can be recovered
    by calling run_feasibility_calculation — no new run needs to be created."""
    service = FeasibilityService(db_session)
    run = service.create_feasibility_run(FeasibilityRunCreate(scenario_name="Recoverable"))
    service.update_assumptions(run.id, _VALID_ASSUMPTIONS)

    # Confirm partial state.
    with pytest.raises(HTTPException):
        service.get_feasibility_result(run.id)

    # Recover by re-running the calculation step.
    result = service.run_feasibility_calculation(run.id)
    assert result.gdv == pytest.approx(3_000_000.0)
    assert result.viability_status is not None

    # Result is now persistently retrievable.
    fetched = service.get_feasibility_result(run.id)
    assert fetched.run_id == run.id
