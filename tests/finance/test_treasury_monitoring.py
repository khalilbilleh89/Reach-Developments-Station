"""
Tests for the treasury monitoring service and API endpoint.

Validates:
  - portfolio cash position (recognized revenue aggregation)
  - receivable exposure aggregation
  - overdue receivables calculation
  - liquidity ratio computation
  - project exposure ranking (highest exposure first)
  - forecast inflow per project
  - GET /finance/treasury/monitoring API endpoint schema

Edge cases:
  - no projects in system (empty portfolio)
  - projects with no receivables
  - projects with only overdue receivables
  - all receivables current (overdue == 0)
"""

import pytest
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.modules.finance.treasury_monitoring_service import TreasuryMonitoringService
from app.modules.finance.schemas import (
    TreasuryMonitoringResponse,
    ProjectExposureEntry,
)


# ---------------------------------------------------------------------------
# Helper functions — reused across test classes
# ---------------------------------------------------------------------------

_tm_seq: dict[str, int] = {}


def _make_project(db_session: Session, code: str) -> str:
    from app.modules.projects.models import Project

    project = Project(name=f"Treasury Monitoring Project {code}", code=code)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


def _make_unit(db_session: Session, project_id: str, unit_number: str) -> str:
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _tm_seq.get(project_id, 0) + 1
    _tm_seq[project_id] = seq

    phase = Phase(project_id=project_id, name=f"Phase {seq}", sequence=seq)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"TM-BLK-{unit_number}")
    db_session.add(building)
    db_session.flush()

    floor = Floor(
        building_id=building.id,
        name="Floor 1",
        code="TM-FL-01",
        sequence_number=1,
    )
    db_session.add(floor)
    db_session.flush()

    unit = Unit(
        floor_id=floor.id,
        unit_number=unit_number,
        unit_type="studio",
        internal_area=100.0,
        status="available",
    )
    db_session.add(unit)
    db_session.commit()
    db_session.refresh(unit)
    return unit.id


def _make_contract(
    db_session: Session,
    unit_id: str,
    contract_price: float,
    contract_number: str,
    email: str,
) -> str:
    from app.modules.sales.models import Buyer, SalesContract

    buyer = Buyer(full_name="Test Buyer", email=email, phone="+9620000001")
    db_session.add(buyer)
    db_session.flush()

    contract = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer.id,
        contract_number=contract_number,
        contract_date=date(2026, 1, 1),
        contract_price=contract_price,
    )
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)
    return contract.id


def _make_installment(
    db_session: Session,
    contract_id: str,
    amount: float,
    installment_number: int,
    due_date: date,
    status: str = "pending",
) -> None:
    from app.modules.sales.models import ContractPaymentSchedule

    line = ContractPaymentSchedule(
        contract_id=contract_id,
        installment_number=installment_number,
        due_date=due_date,
        amount=amount,
        status=status,
    )
    db_session.add(line)
    db_session.commit()


# ---------------------------------------------------------------------------
# Unit tests — empty portfolio
# ---------------------------------------------------------------------------


class TestTreasuryMonitoringEmpty:
    """Tests for an empty portfolio (no contracts, no installments)."""

    def test_empty_portfolio_returns_zeros(self, db_session: Session):
        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert isinstance(result, TreasuryMonitoringResponse)
        assert result.cash_position == 0.0
        assert result.receivables_exposure == 0.0
        assert result.overdue_receivables == 0.0
        assert result.liquidity_ratio == 0.0
        assert result.forecast_next_month == 0.0
        assert result.project_count == 0
        assert result.project_exposures == []

    def test_project_with_no_contracts_not_in_exposures(self, db_session: Session):
        _make_project(db_session, "TM-EMPTY-01")
        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert result.project_exposures == []


# ---------------------------------------------------------------------------
# Unit tests — cash position
# ---------------------------------------------------------------------------


class TestTreasuryCashPosition:
    """Tests for cash position (total recognized / paid revenue)."""

    def test_no_paid_installments_cash_position_zero(self, db_session: Session):
        pid = _make_project(db_session, "TM-CASH-01")
        uid = _make_unit(db_session, pid, "TM-C01-U01")
        cid = _make_contract(
            db_session, uid, 200_000.0, "TM-CASH-C001", "cash01@test.com"
        )
        _make_installment(db_session, cid, 100_000.0, 1, date(2027, 1, 1), "pending")
        _make_installment(db_session, cid, 100_000.0, 2, date(2027, 2, 1), "pending")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert result.cash_position == pytest.approx(0.0)

    def test_fully_paid_contract_cash_position_equals_contract_value(
        self, db_session: Session
    ):
        pid = _make_project(db_session, "TM-CASH-02")
        uid = _make_unit(db_session, pid, "TM-C02-U01")
        cid = _make_contract(
            db_session, uid, 150_000.0, "TM-CASH-C002", "cash02@test.com"
        )
        _make_installment(db_session, cid, 75_000.0, 1, date(2025, 6, 1), "paid")
        _make_installment(db_session, cid, 75_000.0, 2, date(2025, 9, 1), "paid")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert result.cash_position == pytest.approx(150_000.0)

    def test_partial_payment_reflected_in_cash_position(self, db_session: Session):
        pid = _make_project(db_session, "TM-CASH-03")
        uid = _make_unit(db_session, pid, "TM-C03-U01")
        cid = _make_contract(
            db_session, uid, 200_000.0, "TM-CASH-C003", "cash03@test.com"
        )
        _make_installment(db_session, cid, 80_000.0, 1, date(2025, 6, 1), "paid")
        _make_installment(db_session, cid, 120_000.0, 2, date(2027, 3, 1), "pending")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert result.cash_position == pytest.approx(80_000.0)
        assert result.receivables_exposure == pytest.approx(120_000.0)


# ---------------------------------------------------------------------------
# Unit tests — receivable exposure and overdue
# ---------------------------------------------------------------------------


class TestTreasuryReceivableExposure:
    """Tests for receivable exposure and overdue calculations."""

    def test_all_current_receivables_overdue_is_zero(self, db_session: Session):
        pid = _make_project(db_session, "TM-RCV-01")
        uid = _make_unit(db_session, pid, "TM-RCV01-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "TM-RCV-C001", "rcv01@test.com"
        )
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid, 100_000.0, 1, future, "pending")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert result.receivables_exposure == pytest.approx(100_000.0)
        assert result.overdue_receivables == pytest.approx(0.0)

    def test_all_overdue_receivables(self, db_session: Session):
        pid = _make_project(db_session, "TM-RCV-02")
        uid = _make_unit(db_session, pid, "TM-RCV02-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "TM-RCV-C002", "rcv02@test.com"
        )
        past = date.today() - timedelta(days=60)
        _make_installment(db_session, cid, 100_000.0, 1, past, "overdue")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert result.receivables_exposure == pytest.approx(100_000.0)
        assert result.overdue_receivables == pytest.approx(100_000.0)

    def test_paid_and_cancelled_excluded_from_exposure(self, db_session: Session):
        pid = _make_project(db_session, "TM-RCV-03")
        uid = _make_unit(db_session, pid, "TM-RCV03-U01")
        cid = _make_contract(
            db_session, uid, 300_000.0, "TM-RCV-C003", "rcv03@test.com"
        )
        past = date.today() - timedelta(days=10)
        future = date.today() + timedelta(days=10)
        _make_installment(db_session, cid, 100_000.0, 1, past, "paid")
        _make_installment(db_session, cid, 100_000.0, 2, past, "cancelled")
        _make_installment(db_session, cid, 100_000.0, 3, future, "pending")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert result.receivables_exposure == pytest.approx(100_000.0)


# ---------------------------------------------------------------------------
# Unit tests — liquidity ratio
# ---------------------------------------------------------------------------


class TestTreasuryLiquidityRatio:
    """Tests for the liquidity ratio calculation."""

    def test_no_cash_no_receivables_liquidity_zero(self, db_session: Session):
        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()
        assert result.liquidity_ratio == pytest.approx(0.0)

    def test_fully_collected_liquidity_is_one(self, db_session: Session):
        pid = _make_project(db_session, "TM-LIQ-01")
        uid = _make_unit(db_session, pid, "TM-LIQ01-U01")
        cid = _make_contract(
            db_session, uid, 200_000.0, "TM-LIQ-C001", "liq01@test.com"
        )
        _make_installment(db_session, cid, 100_000.0, 1, date(2025, 1, 1), "paid")
        _make_installment(db_session, cid, 100_000.0, 2, date(2025, 2, 1), "paid")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        # cash_position = 200k, receivables_exposure = 0 → ratio = 1.0
        assert result.cash_position == pytest.approx(200_000.0)
        assert result.receivables_exposure == pytest.approx(0.0)
        assert result.liquidity_ratio == pytest.approx(1.0)

    def test_half_collected_liquidity_is_half(self, db_session: Session):
        pid = _make_project(db_session, "TM-LIQ-02")
        uid = _make_unit(db_session, pid, "TM-LIQ02-U01")
        cid = _make_contract(
            db_session, uid, 200_000.0, "TM-LIQ-C002", "liq02@test.com"
        )
        _make_installment(db_session, cid, 100_000.0, 1, date(2025, 1, 1), "paid")
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid, 100_000.0, 2, future, "pending")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        # cash_position = 100k, receivables_exposure = 100k → ratio = 0.5
        assert result.liquidity_ratio == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Unit tests — project exposure ranking
# ---------------------------------------------------------------------------


class TestTreasuryProjectExposureRanking:
    """Tests for project exposure ranking (sorted by receivable_exposure desc)."""

    def test_two_projects_ranked_by_exposure(self, db_session: Session):
        pid1 = _make_project(db_session, "TM-RANK-01")
        uid1 = _make_unit(db_session, pid1, "TM-RK01-U01")
        cid1 = _make_contract(
            db_session, uid1, 100_000.0, "TM-RANK-C001", "rank01@test.com"
        )
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid1, 100_000.0, 1, future, "pending")

        pid2 = _make_project(db_session, "TM-RANK-02")
        uid2 = _make_unit(db_session, pid2, "TM-RK02-U01")
        cid2 = _make_contract(
            db_session, uid2, 300_000.0, "TM-RANK-C002", "rank02@test.com"
        )
        _make_installment(db_session, cid2, 300_000.0, 1, future, "pending")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        exposures = result.project_exposures
        assert len(exposures) == 2
        # Higher exposure project should appear first
        assert exposures[0].receivable_exposure >= exposures[1].receivable_exposure
        assert exposures[0].receivable_exposure == pytest.approx(300_000.0)
        assert exposures[1].receivable_exposure == pytest.approx(100_000.0)

    def test_exposure_percentage_sums_to_100(self, db_session: Session):
        pid1 = _make_project(db_session, "TM-PCT-01")
        uid1 = _make_unit(db_session, pid1, "TM-PCT01-U01")
        cid1 = _make_contract(
            db_session, uid1, 200_000.0, "TM-PCT-C001", "pct01@test.com"
        )
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid1, 200_000.0, 1, future, "pending")

        pid2 = _make_project(db_session, "TM-PCT-02")
        uid2 = _make_unit(db_session, pid2, "TM-PCT02-U01")
        cid2 = _make_contract(
            db_session, uid2, 800_000.0, "TM-PCT-C002", "pct02@test.com"
        )
        _make_installment(db_session, cid2, 800_000.0, 1, future, "pending")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        total_pct = sum(e.exposure_percentage for e in result.project_exposures)
        assert total_pct == pytest.approx(100.0, abs=0.01)

    def test_project_with_no_receivables_not_in_exposures(self, db_session: Session):
        """A project whose installments are all PAID should not appear in exposures."""
        pid = _make_project(db_session, "TM-NOEXP-01")
        uid = _make_unit(db_session, pid, "TM-NE01-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "TM-NOEXP-C001", "noexp01@test.com"
        )
        _make_installment(db_session, cid, 100_000.0, 1, date(2025, 1, 1), "paid")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert all(e.project_id != pid for e in result.project_exposures)

    def test_project_entry_schema_fields_present(self, db_session: Session):
        pid = _make_project(db_session, "TM-SCHEMA-01")
        uid = _make_unit(db_session, pid, "TM-SCH01-U01")
        cid = _make_contract(
            db_session, uid, 50_000.0, "TM-SCHEMA-C001", "schema01@test.com"
        )
        future = date.today() + timedelta(days=15)
        _make_installment(db_session, cid, 50_000.0, 1, future, "pending")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert len(result.project_exposures) >= 1
        entry = next(e for e in result.project_exposures if e.project_id == pid)
        assert isinstance(entry, ProjectExposureEntry)
        assert entry.receivable_exposure >= 0.0
        assert 0.0 <= entry.exposure_percentage <= 100.0
        assert entry.forecast_inflow >= 0.0


# ---------------------------------------------------------------------------
# Integration tests — API endpoint
# ---------------------------------------------------------------------------


class TestTreasuryMonitoringAPI:
    """Tests for GET /finance/treasury/monitoring endpoint."""

    def test_empty_portfolio_returns_200_with_zeros(self, client):
        resp = client.get("/api/v1/finance/treasury/monitoring")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cash_position"] == 0.0
        assert data["receivables_exposure"] == 0.0
        assert data["overdue_receivables"] == 0.0
        assert data["liquidity_ratio"] == 0.0
        assert data["forecast_next_month"] == 0.0
        assert data["project_count"] == 0
        assert data["project_exposures"] == []

    def test_response_schema_has_all_required_fields(self, client):
        resp = client.get("/api/v1/finance/treasury/monitoring")
        assert resp.status_code == 200
        data = resp.json()
        required_keys = {
            "cash_position",
            "receivables_exposure",
            "overdue_receivables",
            "liquidity_ratio",
            "forecast_next_month",
            "project_count",
            "project_exposures",
        }
        assert required_keys.issubset(data.keys())
