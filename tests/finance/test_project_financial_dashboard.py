"""
Tests for the project financial dashboard service and API endpoint.

Validates:
  - Empty project case returns zero KPIs and empty trends
  - KPI calculations (recognized revenue, deferred revenue, receivables,
    overdue breakdown, forecast, collection efficiency)
  - Revenue trend aggregation filtered to the selected project
  - Collections trend aggregation filtered to the selected project
  - Receivables trend retrieval filtered to the selected project
  - API endpoint response shape
  - Auth enforcement (unauthenticated requests rejected)
  - Project not found / missing project handling

Test groups:
  - TestProjectFinancialKPIs        — KPI aggregation
  - TestProjectRevenueTrend         — Revenue trend from fact tables
  - TestProjectCollectionsTrend     — Collections trend from fact tables
  - TestProjectReceivablesTrend     — Receivables trend from fact tables
  - TestProjectFinancialDashboard   — Master composition method
  - TestProjectFinancialDashboardEndpoint — API endpoint auth and structure
"""

import pytest
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.finance.models import (
    FactCollections,
    FactReceivablesSnapshot,
    FactRevenue,
)
from app.modules.finance.project_financial_dashboard_service import (
    ProjectFinancialDashboardService,
)
from app.modules.finance.schemas import (
    ProjectFinancialDashboardResponse,
    ProjectFinancialKPIResponse,
    ProjectFinancialTrendEntry,
)


# ---------------------------------------------------------------------------
# Shared helper functions
# ---------------------------------------------------------------------------

_pfd_seq: dict[str, int] = {}


def _make_project(db_session: Session, code: str) -> str:
    from app.modules.projects.models import Project

    project = Project(name=f"PFD Project {code}", code=code)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


def _make_unit_for_project(db_session: Session, project_id: str, suffix: str) -> str:
    """Create a minimal unit fixture attached to a project via Phase/Building/Floor chain."""
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _pfd_seq.get(project_id, 0) + 1
    _pfd_seq[project_id] = seq

    phase = Phase(project_id=project_id, name=f"Phase {seq}", sequence=seq)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"PFD-BLK-{suffix}")
    db_session.add(building)
    db_session.flush()

    floor = Floor(
        building_id=building.id,
        name="Floor 1",
        code=f"PFD-FL-{suffix}",
        sequence_number=1,
    )
    db_session.add(floor)
    db_session.flush()

    unit = Unit(
        floor_id=floor.id,
        unit_number=suffix,
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


def _seed_revenue_fact(
    db_session: Session,
    project_id: str,
    unit_id: str,
    month: str,
    recognized_revenue: float,
    contract_value: float = 100_000.0,
) -> None:
    fact = FactRevenue(
        project_id=project_id,
        unit_id=unit_id,
        month=month,
        recognized_revenue=recognized_revenue,
        contract_value=contract_value,
    )
    db_session.add(fact)
    db_session.commit()


def _seed_collections_fact(
    db_session: Session,
    project_id: str,
    month: str,
    amount: float,
    payment_date: date | None = None,
) -> None:
    pd = payment_date or date(int(month[:4]), int(month[5:7]), 1)
    fact = FactCollections(
        project_id=project_id,
        payment_date=pd,
        month=month,
        amount=amount,
        payment_method="bank_transfer",
    )
    db_session.add(fact)
    db_session.commit()


def _seed_receivables_snapshot(
    db_session: Session,
    project_id: str,
    snapshot_date: date,
    total_receivables: float,
) -> None:
    snap = FactReceivablesSnapshot(
        project_id=project_id,
        snapshot_date=snapshot_date,
        total_receivables=total_receivables,
        bucket_0_30=total_receivables,
        bucket_31_60=0.0,
        bucket_61_90=0.0,
        bucket_90_plus=0.0,
    )
    db_session.add(snap)
    db_session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_client(db_session):
    """TestClient with authenticated payload and test DB override."""
    from fastapi.testclient import TestClient
    from app.main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_payload():
        return {"sub": "test-user", "roles": ["finance_manager"]}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_payload] = override_payload
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 1 — KPI aggregation
# ---------------------------------------------------------------------------


class TestProjectFinancialKPIs:
    """Tests for ProjectFinancialDashboardService.get_project_financial_kpis()."""

    def test_empty_project_returns_zero_kpis(self, db_session: Session):
        """Project with no contracts returns all-zero KPIs."""
        pid = _make_project(db_session, "PFD-KPI-00")
        svc = ProjectFinancialDashboardService(db_session)
        kpis = svc.get_project_financial_kpis(pid)

        assert isinstance(kpis, ProjectFinancialKPIResponse)
        assert kpis.recognized_revenue == pytest.approx(0.0)
        assert kpis.deferred_revenue == pytest.approx(0.0)
        assert kpis.receivables_exposure == pytest.approx(0.0)
        assert kpis.overdue_receivables == pytest.approx(0.0)
        assert kpis.overdue_percentage == pytest.approx(0.0)
        assert kpis.forecast_next_month == pytest.approx(0.0)
        assert kpis.collection_efficiency == pytest.approx(0.0)

    def test_recognized_and_deferred_revenue_from_paid_installments(
        self, db_session: Session
    ):
        """Recognized revenue equals sum of paid installments; deferred is the remainder."""
        pid = _make_project(db_session, "PFD-KPI-01")
        uid = _make_unit_for_project(db_session, pid, "PFD-K01-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "PFD-K01-C01", "pfdk01@test.com"
        )
        _make_installment(db_session, cid, 40_000.0, 1, date(2026, 1, 1), "paid")
        _make_installment(db_session, cid, 60_000.0, 2, date(2026, 6, 1), "pending")

        svc = ProjectFinancialDashboardService(db_session)
        kpis = svc.get_project_financial_kpis(pid)

        assert kpis.recognized_revenue == pytest.approx(40_000.0)
        assert kpis.deferred_revenue == pytest.approx(60_000.0)

    def test_receivables_exposure_is_total_outstanding(self, db_session: Session):
        """receivables_exposure equals outstanding (pending + overdue) installments."""
        pid = _make_project(db_session, "PFD-KPI-02")
        uid = _make_unit_for_project(db_session, pid, "PFD-K02-U01")
        cid = _make_contract(
            db_session, uid, 200_000.0, "PFD-K02-C01", "pfdk02@test.com"
        )
        _make_installment(db_session, cid, 50_000.0, 1, date(2025, 1, 1), "overdue")
        _make_installment(db_session, cid, 70_000.0, 2, date(2026, 6, 1), "pending")
        _make_installment(db_session, cid, 80_000.0, 3, date(2026, 1, 1), "paid")

        svc = ProjectFinancialDashboardService(db_session)
        kpis = svc.get_project_financial_kpis(pid)

        assert kpis.receivables_exposure == pytest.approx(120_000.0)

    def test_overdue_receivables_excludes_current_bucket(self, db_session: Session):
        """overdue_receivables sums all non-current aging buckets."""
        pid = _make_project(db_session, "PFD-KPI-03")
        uid = _make_unit_for_project(db_session, pid, "PFD-K03-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "PFD-K03-C01", "pfdk03@test.com"
        )
        # Overdue installment (past due date)
        _make_installment(db_session, cid, 30_000.0, 1, date(2025, 1, 1), "overdue")
        # Pending installment (future due date — will be in current bucket)
        future_due = date.today() + timedelta(days=10)
        _make_installment(db_session, cid, 70_000.0, 2, future_due, "pending")

        svc = ProjectFinancialDashboardService(db_session)
        kpis = svc.get_project_financial_kpis(pid)

        # Overdue must be positive and less than total exposure
        assert kpis.overdue_receivables > 0.0
        assert kpis.overdue_receivables < kpis.receivables_exposure

    def test_overdue_percentage_calculated_correctly(self, db_session: Session):
        """overdue_percentage = overdue_receivables / receivables_exposure * 100."""
        pid = _make_project(db_session, "PFD-KPI-04")
        uid = _make_unit_for_project(db_session, pid, "PFD-K04-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "PFD-K04-C01", "pfdk04@test.com"
        )
        # All overdue
        _make_installment(db_session, cid, 100_000.0, 1, date(2025, 1, 1), "overdue")

        svc = ProjectFinancialDashboardService(db_session)
        kpis = svc.get_project_financial_kpis(pid)

        assert kpis.overdue_percentage == pytest.approx(100.0, abs=0.1)

    def test_overdue_percentage_zero_when_no_receivables(self, db_session: Session):
        """overdue_percentage is 0.0 when there are no outstanding receivables."""
        pid = _make_project(db_session, "PFD-KPI-05")
        svc = ProjectFinancialDashboardService(db_session)
        kpis = svc.get_project_financial_kpis(pid)

        assert kpis.overdue_percentage == pytest.approx(0.0)

    def test_collection_efficiency_from_fact_tables(self, db_session: Session):
        """collection_efficiency = fact_collections / fact_revenue for the project."""
        pid = _make_project(db_session, "PFD-KPI-06")
        uid = _make_unit_for_project(db_session, pid, "PFD-K06-U01")
        _seed_revenue_fact(db_session, pid, uid, "2026-03", 100_000.0)
        _seed_collections_fact(db_session, pid, "2026-03", 75_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        kpis = svc.get_project_financial_kpis(pid)

        assert kpis.collection_efficiency == pytest.approx(0.75)

    def test_collection_efficiency_zero_when_no_revenue_facts(
        self, db_session: Session
    ):
        """collection_efficiency is 0.0 when there are no fact_revenue rows for the project."""
        pid = _make_project(db_session, "PFD-KPI-07")
        _seed_collections_fact(db_session, pid, "2026-03", 50_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        kpis = svc.get_project_financial_kpis(pid)

        assert kpis.collection_efficiency == pytest.approx(0.0)

    def test_collection_efficiency_scoped_to_project(self, db_session: Session):
        """Collection efficiency uses only the target project's fact rows."""
        pid1 = _make_project(db_session, "PFD-KPI-08A")
        pid2 = _make_project(db_session, "PFD-KPI-08B")
        uid1 = _make_unit_for_project(db_session, pid1, "PFD-K08A-U01")
        uid2 = _make_unit_for_project(db_session, pid2, "PFD-K08B-U01")

        _seed_revenue_fact(db_session, pid1, uid1, "2026-03", 100_000.0)
        _seed_collections_fact(db_session, pid1, "2026-03", 50_000.0)

        # Project 2 has much higher efficiency — should NOT bleed into project 1
        _seed_revenue_fact(db_session, pid2, uid2, "2026-03", 100_000.0)
        _seed_collections_fact(db_session, pid2, "2026-03", 99_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        kpis = svc.get_project_financial_kpis(pid1)

        assert kpis.collection_efficiency == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Test 2 — Revenue trend aggregation by project
# ---------------------------------------------------------------------------


class TestProjectRevenueTrend:
    """Tests for ProjectFinancialDashboardService.get_project_revenue_trend()."""

    def test_empty_project_returns_empty_trend(self, db_session: Session):
        pid = _make_project(db_session, "PFD-REV-00")
        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_revenue_trend(pid)

        assert result == []

    def test_single_month_entry_returned(self, db_session: Session):
        pid = _make_project(db_session, "PFD-REV-01")
        uid = _make_unit_for_project(db_session, pid, "PFD-R01-U01")
        _seed_revenue_fact(db_session, pid, uid, "2026-03", 50_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_revenue_trend(pid)

        assert len(result) == 1
        assert isinstance(result[0], ProjectFinancialTrendEntry)
        assert result[0].period == "2026-03"
        assert result[0].value == pytest.approx(50_000.0)

    def test_multiple_months_aggregated_and_ordered(self, db_session: Session):
        """Revenue from the same project in different months is ordered ascending."""
        pid = _make_project(db_session, "PFD-REV-02")
        uid = _make_unit_for_project(db_session, pid, "PFD-R02-U01")
        _seed_revenue_fact(db_session, pid, uid, "2026-05", 40_000.0)
        _seed_revenue_fact(db_session, pid, uid, "2026-03", 30_000.0)
        _seed_revenue_fact(db_session, pid, uid, "2026-04", 20_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_revenue_trend(pid)

        periods = [e.period for e in result]
        assert periods == sorted(periods)
        values = {e.period: e.value for e in result}
        assert values["2026-03"] == pytest.approx(30_000.0)
        assert values["2026-04"] == pytest.approx(20_000.0)
        assert values["2026-05"] == pytest.approx(40_000.0)

    def test_revenue_trend_scoped_to_project(self, db_session: Session):
        """Revenue trend returns only the target project's rows, not other projects'."""
        pid1 = _make_project(db_session, "PFD-REV-03A")
        pid2 = _make_project(db_session, "PFD-REV-03B")
        uid1 = _make_unit_for_project(db_session, pid1, "PFD-R03A-U01")
        uid2 = _make_unit_for_project(db_session, pid2, "PFD-R03B-U01")
        _seed_revenue_fact(db_session, pid1, uid1, "2026-06", 25_000.0)
        _seed_revenue_fact(db_session, pid2, uid2, "2026-06", 35_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_revenue_trend(pid1)

        assert len(result) == 1
        assert result[0].value == pytest.approx(25_000.0)

    def test_same_month_multiple_units_aggregated(self, db_session: Session):
        """Revenue from multiple units in the same project and month is summed."""
        pid = _make_project(db_session, "PFD-REV-04")
        uid1 = _make_unit_for_project(db_session, pid, "PFD-R04-U01")
        uid2 = _make_unit_for_project(db_session, pid, "PFD-R04-U02")
        _seed_revenue_fact(db_session, pid, uid1, "2026-07", 15_000.0)
        _seed_revenue_fact(db_session, pid, uid2, "2026-07", 25_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_revenue_trend(pid)

        assert len(result) == 1
        assert result[0].value == pytest.approx(40_000.0)


# ---------------------------------------------------------------------------
# Test 3 — Collections trend aggregation by project
# ---------------------------------------------------------------------------


class TestProjectCollectionsTrend:
    """Tests for ProjectFinancialDashboardService.get_project_collections_trend()."""

    def test_empty_project_returns_empty_trend(self, db_session: Session):
        pid = _make_project(db_session, "PFD-COL-00")
        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_collections_trend(pid)

        assert result == []

    def test_single_month_entry_returned(self, db_session: Session):
        pid = _make_project(db_session, "PFD-COL-01")
        _seed_collections_fact(db_session, pid, "2026-04", 60_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_collections_trend(pid)

        assert len(result) == 1
        assert isinstance(result[0], ProjectFinancialTrendEntry)
        assert result[0].period == "2026-04"
        assert result[0].value == pytest.approx(60_000.0)

    def test_multiple_months_ordered_ascending(self, db_session: Session):
        pid = _make_project(db_session, "PFD-COL-02")
        _seed_collections_fact(db_session, pid, "2026-06", 30_000.0)
        _seed_collections_fact(db_session, pid, "2026-04", 10_000.0)
        _seed_collections_fact(db_session, pid, "2026-05", 20_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_collections_trend(pid)

        periods = [e.period for e in result]
        assert periods == sorted(periods)

    def test_collections_trend_scoped_to_project(self, db_session: Session):
        """Collections trend returns only the target project's rows."""
        pid1 = _make_project(db_session, "PFD-COL-03A")
        pid2 = _make_project(db_session, "PFD-COL-03B")
        _seed_collections_fact(db_session, pid1, "2026-07", 15_000.0)
        _seed_collections_fact(db_session, pid2, "2026-07", 99_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_collections_trend(pid1)

        assert len(result) == 1
        assert result[0].value == pytest.approx(15_000.0)


# ---------------------------------------------------------------------------
# Test 4 — Receivables trend retrieval by project
# ---------------------------------------------------------------------------


class TestProjectReceivablesTrend:
    """Tests for ProjectFinancialDashboardService.get_project_receivables_trend()."""

    def test_empty_project_returns_empty_trend(self, db_session: Session):
        pid = _make_project(db_session, "PFD-RCV-00")
        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_receivables_trend(pid)

        assert result == []

    def test_single_snapshot_entry_returned(self, db_session: Session):
        pid = _make_project(db_session, "PFD-RCV-01")
        snap_date = date(2026, 3, 15)
        _seed_receivables_snapshot(db_session, pid, snap_date, 75_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_receivables_trend(pid)

        assert len(result) == 1
        assert isinstance(result[0], ProjectFinancialTrendEntry)
        assert result[0].period == str(snap_date)
        assert result[0].value == pytest.approx(75_000.0)

    def test_multiple_snapshot_dates_ordered_ascending(self, db_session: Session):
        pid = _make_project(db_session, "PFD-RCV-02")
        _seed_receivables_snapshot(db_session, pid, date(2026, 5, 1), 50_000.0)
        _seed_receivables_snapshot(db_session, pid, date(2026, 3, 1), 80_000.0)
        _seed_receivables_snapshot(db_session, pid, date(2026, 4, 1), 60_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_receivables_trend(pid)

        periods = [e.period for e in result]
        assert periods == sorted(periods)

    def test_receivables_trend_scoped_to_project(self, db_session: Session):
        """Receivables trend returns only the target project's snapshots."""
        snap_date = date(2026, 6, 1)
        pid1 = _make_project(db_session, "PFD-RCV-03A")
        pid2 = _make_project(db_session, "PFD-RCV-03B")
        _seed_receivables_snapshot(db_session, pid1, snap_date, 30_000.0)
        _seed_receivables_snapshot(db_session, pid2, snap_date, 99_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_receivables_trend(pid1)

        assert len(result) == 1
        assert result[0].value == pytest.approx(30_000.0)

    def test_multiple_snapshots_per_project_all_returned(self, db_session: Session):
        """All historical snapshots for the project are returned (not just the latest)."""
        pid = _make_project(db_session, "PFD-RCV-04")
        _seed_receivables_snapshot(db_session, pid, date(2026, 1, 1), 100_000.0)
        _seed_receivables_snapshot(db_session, pid, date(2026, 2, 1), 80_000.0)
        _seed_receivables_snapshot(db_session, pid, date(2026, 3, 1), 60_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_receivables_trend(pid)

        assert len(result) == 3


# ---------------------------------------------------------------------------
# Test 5 — Master composition method
# ---------------------------------------------------------------------------


class TestProjectFinancialDashboard:
    """Tests for ProjectFinancialDashboardService.get_project_financial_dashboard()."""

    def test_returns_correct_schema_type(self, db_session: Session):
        pid = _make_project(db_session, "PFD-DASH-01")
        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_financial_dashboard(pid)

        assert isinstance(result, ProjectFinancialDashboardResponse)
        assert isinstance(result.kpis, ProjectFinancialKPIResponse)
        assert isinstance(result.revenue_trend, list)
        assert isinstance(result.collections_trend, list)
        assert isinstance(result.receivables_trend, list)

    def test_project_id_in_response(self, db_session: Session):
        pid = _make_project(db_session, "PFD-DASH-02")
        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_financial_dashboard(pid)

        assert result.project_id == pid

    def test_full_dashboard_with_populated_data(self, db_session: Session):
        """Dashboard composition returns correct values when all data is seeded."""
        pid = _make_project(db_session, "PFD-DASH-03")
        uid = _make_unit_for_project(db_session, pid, "PFD-D03-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "PFD-D03-C01", "pfddash03@test.com"
        )
        _make_installment(db_session, cid, 30_000.0, 1, date(2026, 1, 1), "paid")
        _make_installment(db_session, cid, 70_000.0, 2, date(2026, 6, 1), "pending")

        _seed_revenue_fact(db_session, pid, uid, "2026-03", 30_000.0)
        _seed_collections_fact(db_session, pid, "2026-03", 25_000.0)
        _seed_receivables_snapshot(db_session, pid, date(2026, 3, 15), 70_000.0)

        svc = ProjectFinancialDashboardService(db_session)
        result = svc.get_project_financial_dashboard(pid)

        assert result.kpis.recognized_revenue == pytest.approx(30_000.0)
        assert result.kpis.deferred_revenue == pytest.approx(70_000.0)
        assert len(result.revenue_trend) == 1
        assert len(result.collections_trend) == 1
        assert len(result.receivables_trend) == 1

    def test_project_not_found_raises_404(self, db_session: Session):
        """Dashboard raises HTTP 404 when the project does not exist."""
        from fastapi import HTTPException

        svc = ProjectFinancialDashboardService(db_session)
        with pytest.raises(HTTPException) as exc_info:
            svc.get_project_financial_dashboard("nonexistent-project-id")

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Test 6 — API endpoint auth and structure
# ---------------------------------------------------------------------------


class TestProjectFinancialDashboardEndpoint:
    """Tests for GET /finance/projects/{project_id}/dashboard."""

    def test_endpoint_rejects_unauthenticated_requests(self, unauth_client):
        """Callers with no Authorization header must be rejected."""
        response = unauth_client.get("/api/v1/finance/projects/some-id/dashboard")
        assert response.status_code in (401, 403)

    def test_endpoint_returns_404_for_unknown_project(self, auth_client):
        response = auth_client.get(
            "/api/v1/finance/projects/nonexistent-project-id/dashboard"
        )
        assert response.status_code == 404

    def test_endpoint_returns_200_for_existing_project(
        self, auth_client, db_session: Session
    ):
        pid = _make_project(db_session, "PFD-API-01")
        response = auth_client.get(f"/api/v1/finance/projects/{pid}/dashboard")
        assert response.status_code == 200

    def test_endpoint_returns_correct_schema_structure(
        self, auth_client, db_session: Session
    ):
        pid = _make_project(db_session, "PFD-API-02")
        response = auth_client.get(f"/api/v1/finance/projects/{pid}/dashboard")
        data = response.json()

        assert "project_id" in data
        assert "kpis" in data
        assert "revenue_trend" in data
        assert "collections_trend" in data
        assert "receivables_trend" in data

    def test_endpoint_kpis_contain_required_fields(
        self, auth_client, db_session: Session
    ):
        pid = _make_project(db_session, "PFD-API-03")
        response = auth_client.get(f"/api/v1/finance/projects/{pid}/dashboard")
        kpis = response.json()["kpis"]

        assert "recognized_revenue" in kpis
        assert "deferred_revenue" in kpis
        assert "receivables_exposure" in kpis
        assert "overdue_receivables" in kpis
        assert "overdue_percentage" in kpis
        assert "forecast_next_month" in kpis
        assert "collection_efficiency" in kpis

    def test_endpoint_empty_project_returns_zero_kpis(
        self, auth_client, db_session: Session
    ):
        pid = _make_project(db_session, "PFD-API-04")
        response = auth_client.get(f"/api/v1/finance/projects/{pid}/dashboard")
        kpis = response.json()["kpis"]

        assert kpis["recognized_revenue"] == 0.0
        assert kpis["deferred_revenue"] == 0.0
        assert kpis["receivables_exposure"] == 0.0
        assert kpis["overdue_receivables"] == 0.0
        assert kpis["overdue_percentage"] == 0.0
        assert kpis["forecast_next_month"] == 0.0
        assert kpis["collection_efficiency"] == 0.0

    def test_endpoint_project_id_matches_request(
        self, auth_client, db_session: Session
    ):
        pid = _make_project(db_session, "PFD-API-05")
        response = auth_client.get(f"/api/v1/finance/projects/{pid}/dashboard")
        data = response.json()

        assert data["project_id"] == pid

    def test_endpoint_returns_populated_trends_with_data(
        self, auth_client, db_session: Session
    ):
        """Seeding fact tables produces non-empty trends in the API response."""
        pid = _make_project(db_session, "PFD-API-06")
        uid = _make_unit_for_project(db_session, pid, "PFD-A06-U01")
        _seed_revenue_fact(db_session, pid, uid, "2026-03", 50_000.0)
        _seed_collections_fact(db_session, pid, "2026-03", 40_000.0)
        _seed_receivables_snapshot(db_session, pid, date(2026, 3, 15), 30_000.0)

        response = auth_client.get(f"/api/v1/finance/projects/{pid}/dashboard")
        assert response.status_code == 200

        data = response.json()
        assert len(data["revenue_trend"]) >= 1
        assert len(data["collections_trend"]) >= 1
        assert len(data["receivables_trend"]) >= 1

        kpis = data["kpis"]
        assert kpis["collection_efficiency"] == pytest.approx(0.8)

    def test_trend_entries_have_period_and_value_fields(
        self, auth_client, db_session: Session
    ):
        """Trend entries expose 'period' and 'value' fields."""
        pid = _make_project(db_session, "PFD-API-07")
        uid = _make_unit_for_project(db_session, pid, "PFD-A07-U01")
        _seed_revenue_fact(db_session, pid, uid, "2026-05", 20_000.0)

        response = auth_client.get(f"/api/v1/finance/projects/{pid}/dashboard")
        data = response.json()

        assert len(data["revenue_trend"]) == 1
        entry = data["revenue_trend"][0]
        assert "period" in entry
        assert "value" in entry
        assert entry["period"] == "2026-05"
        assert entry["value"] == pytest.approx(20_000.0)

    def test_other_projects_data_not_mixed_in(
        self, auth_client, db_session: Session
    ):
        """Dashboard only returns data scoped to the requested project_id."""
        pid1 = _make_project(db_session, "PFD-API-08A")
        pid2 = _make_project(db_session, "PFD-API-08B")
        uid1 = _make_unit_for_project(db_session, pid1, "PFD-A08A-U01")
        uid2 = _make_unit_for_project(db_session, pid2, "PFD-A08B-U01")
        _seed_revenue_fact(db_session, pid1, uid1, "2026-03", 10_000.0)
        _seed_revenue_fact(db_session, pid2, uid2, "2026-03", 99_000.0)

        response = auth_client.get(f"/api/v1/finance/projects/{pid1}/dashboard")
        data = response.json()

        assert len(data["revenue_trend"]) == 1
        assert data["revenue_trend"][0]["value"] == pytest.approx(10_000.0)
