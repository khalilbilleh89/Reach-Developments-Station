"""
Tests for the Revenue Recognition Engine (PR-FIN-032).

Validates:
  - Revenue schedule generation across all three recognition strategies
  - Correct period allocation and revenue totals
  - Empty schedule for scenarios with no unit sales
  - Scenario-not-found HTTP 404 handling
  - Service integration with the scenario/project/contract data hierarchy
"""

import pytest
from datetime import date

from sqlalchemy.orm import Session

from app.modules.finance.revenue_engine import generate_revenue_schedule
from app.modules.finance.revenue_models import (
    RecognitionStrategy,
    RevenueScheduleInput,
    UnitSaleData,
)
from app.modules.finance.revenue_service import ScenarioRevenueService


# ---------------------------------------------------------------------------
# Helpers shared between pure engine and integration tests
# ---------------------------------------------------------------------------


def _sale(
    contract_id: str,
    total: float,
    contract_date: date,
    delivery_date: date | None = None,
    milestones: dict | None = None,
) -> UnitSaleData:
    return UnitSaleData(
        contract_id=contract_id,
        contract_total=total,
        contract_date=contract_date,
        delivery_date=delivery_date,
        construction_completion_by_period=milestones or {},
    )


def _input(
    scenario_id: str,
    sales: list,
    strategy: RecognitionStrategy = RecognitionStrategy.ON_CONTRACT_SIGNING,
) -> RevenueScheduleInput:
    return RevenueScheduleInput(
        scenario_id=scenario_id,
        unit_sales=sales,
        strategy=strategy,
    )


# ---------------------------------------------------------------------------
# Pure engine — ON_CONTRACT_SIGNING
# ---------------------------------------------------------------------------


class TestRevenueEngineOnContractSigning:
    """Tests for the on_contract_signing recognition strategy."""

    def test_single_sale_single_period(self):
        sales = [_sale("c-001", 500_000.0, date(2026, 1, 15))]
        result = generate_revenue_schedule(_input("s-001", sales))

        assert result.scenario_id == "s-001"
        assert result.strategy == RecognitionStrategy.ON_CONTRACT_SIGNING.value
        assert len(result.revenue_schedule) == 1
        assert result.revenue_schedule[0].period == "2026-01"
        assert result.revenue_schedule[0].revenue == pytest.approx(500_000.0)
        assert result.total_revenue == pytest.approx(500_000.0)

    def test_multiple_sales_same_period(self):
        sales = [
            _sale("c-001", 300_000.0, date(2026, 3, 1)),
            _sale("c-002", 200_000.0, date(2026, 3, 20)),
        ]
        result = generate_revenue_schedule(_input("s-002", sales))

        assert len(result.revenue_schedule) == 1
        assert result.revenue_schedule[0].period == "2026-03"
        assert result.revenue_schedule[0].revenue == pytest.approx(500_000.0)
        assert result.total_revenue == pytest.approx(500_000.0)

    def test_sales_across_multiple_periods_sorted(self):
        sales = [
            _sale("c-001", 100_000.0, date(2026, 3, 1)),
            _sale("c-002", 200_000.0, date(2026, 1, 15)),
            _sale("c-003", 150_000.0, date(2026, 2, 10)),
        ]
        result = generate_revenue_schedule(_input("s-003", sales))

        periods = [e.period for e in result.revenue_schedule]
        assert periods == ["2026-01", "2026-02", "2026-03"], "schedule must be sorted"
        assert result.revenue_schedule[0].revenue == pytest.approx(200_000.0)
        assert result.revenue_schedule[1].revenue == pytest.approx(150_000.0)
        assert result.revenue_schedule[2].revenue == pytest.approx(100_000.0)
        assert result.total_revenue == pytest.approx(450_000.0)

    def test_no_sales_returns_empty_schedule(self):
        result = generate_revenue_schedule(_input("s-004", []))

        assert result.revenue_schedule == []
        assert result.total_revenue == 0.0

    def test_total_revenue_equals_sum_of_entries(self):
        sales = [
            _sale("c-001", 123_456.78, date(2026, 1, 1)),
            _sale("c-002", 654_321.22, date(2026, 2, 1)),
        ]
        result = generate_revenue_schedule(_input("s-005", sales))

        computed_total = sum(e.revenue for e in result.revenue_schedule)
        assert result.total_revenue == pytest.approx(computed_total)


# ---------------------------------------------------------------------------
# Pure engine — ON_UNIT_DELIVERY
# ---------------------------------------------------------------------------


class TestRevenueEngineOnUnitDelivery:
    """Tests for the on_unit_delivery recognition strategy."""

    def test_single_sale_delivery_date(self):
        sales = [
            _sale(
                "c-001",
                500_000.0,
                date(2026, 1, 1),
                delivery_date=date(2026, 12, 15),
            )
        ]
        result = generate_revenue_schedule(
            _input("s-010", sales, RecognitionStrategy.ON_UNIT_DELIVERY)
        )

        assert len(result.revenue_schedule) == 1
        assert result.revenue_schedule[0].period == "2026-12"
        assert result.revenue_schedule[0].revenue == pytest.approx(500_000.0)

    def test_falls_back_to_contract_date_when_no_delivery_date(self):
        sales = [_sale("c-002", 400_000.0, date(2026, 2, 1), delivery_date=None)]
        result = generate_revenue_schedule(
            _input("s-011", sales, RecognitionStrategy.ON_UNIT_DELIVERY)
        )

        assert result.revenue_schedule[0].period == "2026-02"

    def test_multiple_sales_different_delivery_dates(self):
        sales = [
            _sale("c-001", 300_000.0, date(2026, 1, 1), delivery_date=date(2026, 6, 1)),
            _sale("c-002", 200_000.0, date(2026, 1, 1), delivery_date=date(2026, 9, 1)),
        ]
        result = generate_revenue_schedule(
            _input("s-012", sales, RecognitionStrategy.ON_UNIT_DELIVERY)
        )

        assert len(result.revenue_schedule) == 2
        assert result.revenue_schedule[0].period == "2026-06"
        assert result.revenue_schedule[1].period == "2026-09"
        assert result.total_revenue == pytest.approx(500_000.0)


# ---------------------------------------------------------------------------
# Pure engine — ON_CONSTRUCTION_PROGRESS
# ---------------------------------------------------------------------------


class TestRevenueEngineOnConstructionProgress:
    """Tests for the on_construction_progress recognition strategy."""

    def test_even_milestone_split(self):
        milestones = {"2026-01": 25.0, "2026-02": 50.0, "2026-03": 75.0, "2026-04": 100.0}
        sales = [_sale("c-001", 400_000.0, date(2026, 1, 1), milestones=milestones)]
        result = generate_revenue_schedule(
            _input("s-020", sales, RecognitionStrategy.ON_CONSTRUCTION_PROGRESS)
        )

        periods = {e.period: e.revenue for e in result.revenue_schedule}
        assert periods["2026-01"] == pytest.approx(100_000.0)
        assert periods["2026-02"] == pytest.approx(100_000.0)
        assert periods["2026-03"] == pytest.approx(100_000.0)
        # Last period gets the remainder
        assert periods["2026-04"] == pytest.approx(100_000.0)
        assert result.total_revenue == pytest.approx(400_000.0)

    def test_total_revenue_preserved_across_milestones(self):
        milestones = {"2026-01": 30.0, "2026-02": 70.0, "2026-03": 100.0}
        sales = [_sale("c-001", 300_000.0, date(2026, 1, 1), milestones=milestones)]
        result = generate_revenue_schedule(
            _input("s-021", sales, RecognitionStrategy.ON_CONSTRUCTION_PROGRESS)
        )

        assert result.total_revenue == pytest.approx(300_000.0)

    def test_fallback_to_signing_when_no_milestones(self):
        sales = [_sale("c-001", 250_000.0, date(2026, 5, 1), milestones={})]
        result = generate_revenue_schedule(
            _input("s-022", sales, RecognitionStrategy.ON_CONSTRUCTION_PROGRESS)
        )

        assert len(result.revenue_schedule) == 1
        assert result.revenue_schedule[0].period == "2026-05"
        assert result.revenue_schedule[0].revenue == pytest.approx(250_000.0)

    def test_multiple_sales_different_milestone_maps(self):
        milestones_a = {"2026-01": 50.0, "2026-02": 100.0}
        milestones_b = {"2026-02": 100.0}
        sales = [
            _sale("c-001", 200_000.0, date(2026, 1, 1), milestones=milestones_a),
            _sale("c-002", 100_000.0, date(2026, 2, 1), milestones=milestones_b),
        ]
        result = generate_revenue_schedule(
            _input("s-023", sales, RecognitionStrategy.ON_CONSTRUCTION_PROGRESS)
        )

        periods = {e.period: e.revenue for e in result.revenue_schedule}
        # c-001: 50% in Jan = 100_000, 50% (remainder) in Feb = 100_000
        # c-002: 100% in Feb = 100_000
        assert periods["2026-01"] == pytest.approx(100_000.0)
        assert periods["2026-02"] == pytest.approx(200_000.0)
        assert result.total_revenue == pytest.approx(300_000.0)


# ---------------------------------------------------------------------------
# Schedule result invariants
# ---------------------------------------------------------------------------


class TestRevenueScheduleInvariants:
    """Cross-strategy invariants that must hold regardless of strategy used."""

    @pytest.mark.parametrize(
        "strategy",
        [
            RecognitionStrategy.ON_CONTRACT_SIGNING,
            RecognitionStrategy.ON_UNIT_DELIVERY,
            RecognitionStrategy.ON_CONSTRUCTION_PROGRESS,
        ],
    )
    def test_schedule_is_chronologically_sorted(self, strategy: RecognitionStrategy):
        sales = [
            _sale("c-001", 100_000.0, date(2026, 6, 1), delivery_date=date(2026, 6, 1)),
            _sale("c-002", 100_000.0, date(2026, 1, 1), delivery_date=date(2026, 1, 1)),
        ]
        result = generate_revenue_schedule(_input("s-inv", sales, strategy))

        periods = [e.period for e in result.revenue_schedule]
        assert periods == sorted(periods), "revenue schedule must be in ascending order"

    @pytest.mark.parametrize(
        "strategy",
        [
            RecognitionStrategy.ON_CONTRACT_SIGNING,
            RecognitionStrategy.ON_UNIT_DELIVERY,
            RecognitionStrategy.ON_CONSTRUCTION_PROGRESS,
        ],
    )
    def test_all_revenues_non_negative(self, strategy: RecognitionStrategy):
        sales = [_sale("c-001", 0.0, date(2026, 1, 1))]
        result = generate_revenue_schedule(_input("s-inv2", sales, strategy))

        for entry in result.revenue_schedule:
            assert entry.revenue >= 0.0

    @pytest.mark.parametrize(
        "strategy",
        [
            RecognitionStrategy.ON_CONTRACT_SIGNING,
            RecognitionStrategy.ON_UNIT_DELIVERY,
        ],
    )
    def test_total_equals_sum_of_contract_totals(self, strategy: RecognitionStrategy):
        sales = [
            _sale("c-001", 111_111.11, date(2026, 1, 1), delivery_date=date(2026, 1, 1)),
            _sale("c-002", 222_222.22, date(2026, 2, 1), delivery_date=date(2026, 2, 1)),
        ]
        result = generate_revenue_schedule(_input("s-inv3", sales, strategy))

        expected = sum(s.contract_total for s in sales)
        assert result.total_revenue == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# Integration tests — ScenarioRevenueService with SQLite DB
# ---------------------------------------------------------------------------

_rev_seq: dict[str, int] = {}


def _make_project(db: Session, code: str) -> str:
    from app.modules.projects.models import Project

    p = Project(name=f"Rev Engine Project {code}", code=code)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p.id


def _make_unit(db: Session, project_id: str, unit_number: str) -> str:
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _rev_seq.get(project_id, 0) + 1
    _rev_seq[project_id] = seq

    phase = Phase(project_id=project_id, name=f"Phase {seq}", sequence=seq)
    db.add(phase)
    db.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"BLK-{unit_number}")
    db.add(building)
    db.flush()

    floor = Floor(
        building_id=building.id, name="Floor 1", code="FL-01", sequence_number=1
    )
    db.add(floor)
    db.flush()

    unit = Unit(
        floor_id=floor.id,
        unit_number=unit_number,
        unit_type="studio",
        internal_area=80.0,
        status="available",
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit.id


def _make_contract(
    db: Session, unit_id: str, price: float, number: str, email: str,
    contract_date: date = date(2026, 1, 1),
) -> str:
    from app.modules.sales.models import Buyer, SalesContract

    buyer = Buyer(full_name="Test Buyer", email=email, phone="+9620000001")
    db.add(buyer)
    db.flush()

    contract = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer.id,
        contract_number=number,
        contract_date=contract_date,
        contract_price=price,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract.id


def _make_scenario(
    db: Session, name: str, project_id: str | None = None
) -> str:
    from app.modules.scenario.models import Scenario

    s = Scenario(name=name, project_id=project_id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s.id


class TestScenarioRevenueService:
    def test_empty_schedule_for_scenario_without_project(self, db_session: Session):
        sid = _make_scenario(db_session, "No-Project Scenario")
        svc = ScenarioRevenueService(db_session)
        result = svc.get_revenue_schedule(sid)

        assert result.scenario_id == sid
        assert result.revenue_schedule == []
        assert result.total_revenue == 0.0

    def test_scenario_not_found_raises_resource_not_found(self, db_session: Session):
        from app.core.errors import ResourceNotFoundError

        svc = ScenarioRevenueService(db_session)
        with pytest.raises(ResourceNotFoundError):
            svc.get_revenue_schedule("non-existent-scenario-id")

    def test_single_contract_on_signing(self, db_session: Session):
        pid = _make_project(db_session, "RE-SVC-01")
        uid = _make_unit(db_session, pid, "U-01")
        _make_contract(
            db_session, uid, 1_000_000.0, "CNT-RE-01", "resvc01@test.com",
            contract_date=date(2026, 3, 15),
        )
        sid = _make_scenario(db_session, "Scenario RE-SVC-01", project_id=pid)

        svc = ScenarioRevenueService(db_session)
        result = svc.get_revenue_schedule(sid, RecognitionStrategy.ON_CONTRACT_SIGNING)

        assert len(result.revenue_schedule) == 1
        assert result.revenue_schedule[0].period == "2026-03"
        assert result.revenue_schedule[0].revenue == pytest.approx(1_000_000.0)
        assert result.total_revenue == pytest.approx(1_000_000.0)

    def test_multiple_contracts_aggregated_by_period(self, db_session: Session):
        pid = _make_project(db_session, "RE-SVC-02")

        uid1 = _make_unit(db_session, pid, "U-10")
        _make_contract(
            db_session, uid1, 500_000.0, "CNT-RE-10", "resvc10@test.com",
            contract_date=date(2026, 1, 10),
        )

        uid2 = _make_unit(db_session, pid, "U-11")
        _make_contract(
            db_session, uid2, 300_000.0, "CNT-RE-11", "resvc11@test.com",
            contract_date=date(2026, 1, 20),
        )

        uid3 = _make_unit(db_session, pid, "U-12")
        _make_contract(
            db_session, uid3, 400_000.0, "CNT-RE-12", "resvc12@test.com",
            contract_date=date(2026, 2, 5),
        )

        sid = _make_scenario(db_session, "Scenario RE-SVC-02", project_id=pid)

        svc = ScenarioRevenueService(db_session)
        result = svc.get_revenue_schedule(sid, RecognitionStrategy.ON_CONTRACT_SIGNING)

        assert len(result.revenue_schedule) == 2
        periods = {e.period: e.revenue for e in result.revenue_schedule}
        assert periods["2026-01"] == pytest.approx(800_000.0)
        assert periods["2026-02"] == pytest.approx(400_000.0)
        assert result.total_revenue == pytest.approx(1_200_000.0)

    def test_project_with_no_contracts_returns_empty_schedule(self, db_session: Session):
        pid = _make_project(db_session, "RE-SVC-03")
        sid = _make_scenario(db_session, "Scenario RE-SVC-03", project_id=pid)

        svc = ScenarioRevenueService(db_session)
        result = svc.get_revenue_schedule(sid)

        assert result.revenue_schedule == []
        assert result.total_revenue == 0.0

    def test_strategy_propagated_to_result(self, db_session: Session):
        sid = _make_scenario(db_session, "Scenario RE-SVC-04")
        svc = ScenarioRevenueService(db_session)

        for strategy in RecognitionStrategy:
            result = svc.get_revenue_schedule(sid, strategy)
            assert result.strategy == strategy.value


# ---------------------------------------------------------------------------
# API-level integration tests
# ---------------------------------------------------------------------------


class TestRevenueRouterApi:
    def test_get_revenue_schedule_scenario_not_found(self, client):
        resp = client.get("/api/v1/finance/revenue/non-existent-scenario-id")
        assert resp.status_code == 404

    def test_get_revenue_schedule_no_sales(self, client, db_session: Session):
        pid = _make_project(db_session, "RE-API-01")
        sid = _make_scenario(db_session, "API Scenario RE-API-01", project_id=pid)

        resp = client.get(f"/api/v1/finance/revenue/{sid}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["scenario_id"] == sid
        assert data["strategy"] == RecognitionStrategy.ON_CONTRACT_SIGNING.value
        assert data["revenue_schedule"] == []
        assert data["total_revenue"] == 0.0

    def test_get_revenue_schedule_with_contracts(self, client, db_session: Session):
        pid = _make_project(db_session, "RE-API-02")
        uid = _make_unit(db_session, pid, "U-API-01")
        _make_contract(
            db_session, uid, 2_000_000.0, "CNT-RE-API-01", "reapi01@test.com",
            contract_date=date(2026, 6, 1),
        )
        sid = _make_scenario(db_session, "API Scenario RE-API-02", project_id=pid)

        resp = client.get(f"/api/v1/finance/revenue/{sid}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["total_revenue"] == pytest.approx(2_000_000.0)
        assert len(data["revenue_schedule"]) == 1
        assert data["revenue_schedule"][0]["period"] == "2026-06"

    def test_strategy_query_param_accepted(self, client, db_session: Session):
        sid = _make_scenario(db_session, "API Scenario RE-API-03")

        for strategy in RecognitionStrategy:
            resp = client.get(
                f"/api/v1/finance/revenue/{sid}",
                params={"strategy": strategy.value},
            )
            assert resp.status_code == 200
            assert resp.json()["strategy"] == strategy.value

    def test_invalid_strategy_returns_422(self, client, db_session: Session):
        sid = _make_scenario(db_session, "API Scenario RE-API-04")
        resp = client.get(
            f"/api/v1/finance/revenue/{sid}",
            params={"strategy": "invalid_strategy"},
        )
        assert resp.status_code == 422
