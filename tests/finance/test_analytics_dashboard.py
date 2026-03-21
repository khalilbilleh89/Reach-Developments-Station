"""
Tests for the analytics dashboard service and API endpoint.

Validates:
  - Revenue trend aggregation from fact_revenue
  - Collections trend aggregation from fact_collections
  - Receivable trend snapshot retrieval from fact_receivables_snapshot
  - Portfolio KPI calculations (total revenue, collections, receivables,
    collection efficiency)
  - API endpoint response structure for GET /finance/analytics/portfolio

Edge cases:
  - Empty fact tables return empty trends and zero KPIs
  - Multiple months aggregated correctly
  - Collection efficiency clamped to 0 when no revenue data
  - Latest snapshot date used for total_receivables KPI
"""

import pytest
from datetime import date
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.finance.analytics_dashboard_service import AnalyticsDashboardService
from app.modules.finance.models import (
    FactCollections,
    FactReceivablesSnapshot,
    FactRevenue,
)
from app.modules.finance.schemas import PortfolioAnalyticsResponse, PortfolioKPI


# ---------------------------------------------------------------------------
# Helper functions — reused across test classes
# ---------------------------------------------------------------------------

_ad_seq: dict[str, int] = {}


def _make_project(db_session: Session, code: str) -> str:
    from app.modules.projects.models import Project

    project = Project(name=f"Analytics Dashboard Project {code}", code=code)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


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


def _make_unit_for_project(db_session: Session, project_id: str, suffix: str) -> str:
    """Create a minimal unit fixture attached to a project via Phase/Building/Floor chain."""
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _ad_seq.get(project_id, 0) + 1
    _ad_seq[project_id] = seq

    phase = Phase(project_id=project_id, name=f"Phase {seq}", sequence=seq)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"AD-BLK-{suffix}")
    db_session.add(building)
    db_session.flush()

    floor = Floor(
        building_id=building.id,
        name="Floor 1",
        code=f"AD-FL-{suffix}",
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_client(db_session):
    """TestClient that injects the test DB session and an authenticated payload."""
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
# Test 1 — Revenue trend aggregation
# ---------------------------------------------------------------------------


class TestGetRevenueTrend:
    """Tests for AnalyticsDashboardService.get_revenue_trend()."""

    def test_empty_fact_table_returns_empty_trend(self, db_session: Session):
        svc = AnalyticsDashboardService(db_session)
        result = svc.get_revenue_trend()

        assert result == []

    def test_single_month_entry_returned(self, db_session: Session):
        pid = _make_project(db_session, "AD-REV-01")
        uid = _make_unit_for_project(db_session, pid, "AD-R01-U01")
        _seed_revenue_fact(db_session, pid, uid, "2026-03", 50_000.0)

        svc = AnalyticsDashboardService(db_session)
        result = svc.get_revenue_trend()

        assert len(result) == 1
        assert result[0].month == "2026-03"
        assert result[0].total_recognized_revenue == pytest.approx(50_000.0)

    def test_multiple_months_aggregated_and_ordered(self, db_session: Session):
        """Revenue from different months is returned in ascending month order."""
        pid = _make_project(db_session, "AD-REV-02")
        uid = _make_unit_for_project(db_session, pid, "AD-R02-U01")
        _seed_revenue_fact(db_session, pid, uid, "2026-05", 40_000.0)
        _seed_revenue_fact(db_session, pid, uid, "2026-03", 30_000.0)
        _seed_revenue_fact(db_session, pid, uid, "2026-04", 20_000.0)

        svc = AnalyticsDashboardService(db_session)
        result = svc.get_revenue_trend()

        months = [e.month for e in result]
        assert months == sorted(months), "Revenue trend must be ordered by month"
        totals = {e.month: e.total_recognized_revenue for e in result}
        assert totals["2026-03"] == pytest.approx(30_000.0)
        assert totals["2026-04"] == pytest.approx(20_000.0)
        assert totals["2026-05"] == pytest.approx(40_000.0)

    def test_multiple_projects_same_month_aggregated(self, db_session: Session):
        """Revenue from multiple projects in the same month is summed."""
        pid1 = _make_project(db_session, "AD-REV-03A")
        pid2 = _make_project(db_session, "AD-REV-03B")
        uid1 = _make_unit_for_project(db_session, pid1, "AD-R03A-U01")
        uid2 = _make_unit_for_project(db_session, pid2, "AD-R03B-U01")
        _seed_revenue_fact(db_session, pid1, uid1, "2026-06", 25_000.0)
        _seed_revenue_fact(db_session, pid2, uid2, "2026-06", 35_000.0)

        svc = AnalyticsDashboardService(db_session)
        result = svc.get_revenue_trend()

        assert len(result) == 1
        assert result[0].month == "2026-06"
        assert result[0].total_recognized_revenue == pytest.approx(60_000.0)


# ---------------------------------------------------------------------------
# Test 2 — Collections trend aggregation
# ---------------------------------------------------------------------------


class TestGetCollectionsTrend:
    """Tests for AnalyticsDashboardService.get_collections_trend()."""

    def test_empty_fact_table_returns_empty_trend(self, db_session: Session):
        svc = AnalyticsDashboardService(db_session)
        result = svc.get_collections_trend()

        assert result == []

    def test_single_month_entry_returned(self, db_session: Session):
        pid = _make_project(db_session, "AD-COL-01")
        _seed_collections_fact(db_session, pid, "2026-04", 60_000.0)

        svc = AnalyticsDashboardService(db_session)
        result = svc.get_collections_trend()

        assert len(result) == 1
        assert result[0].month == "2026-04"
        assert result[0].total_amount == pytest.approx(60_000.0)

    def test_multiple_months_ordered_ascending(self, db_session: Session):
        pid = _make_project(db_session, "AD-COL-02")
        _seed_collections_fact(db_session, pid, "2026-06", 30_000.0)
        _seed_collections_fact(db_session, pid, "2026-04", 10_000.0)
        _seed_collections_fact(db_session, pid, "2026-05", 20_000.0)

        svc = AnalyticsDashboardService(db_session)
        result = svc.get_collections_trend()

        months = [e.month for e in result]
        assert months == sorted(months), "Collections trend must be ordered by month"

    def test_multiple_projects_same_month_aggregated(self, db_session: Session):
        """Collections from multiple projects in the same month are summed."""
        pid1 = _make_project(db_session, "AD-COL-03A")
        pid2 = _make_project(db_session, "AD-COL-03B")
        _seed_collections_fact(db_session, pid1, "2026-07", 15_000.0)
        _seed_collections_fact(db_session, pid2, "2026-07", 25_000.0)

        svc = AnalyticsDashboardService(db_session)
        result = svc.get_collections_trend()

        assert len(result) == 1
        assert result[0].total_amount == pytest.approx(40_000.0)


# ---------------------------------------------------------------------------
# Test 3 — Receivable trend snapshot retrieval
# ---------------------------------------------------------------------------


class TestGetReceivablesTrend:
    """Tests for AnalyticsDashboardService.get_receivables_trend()."""

    def test_empty_fact_table_returns_empty_trend(self, db_session: Session):
        svc = AnalyticsDashboardService(db_session)
        result = svc.get_receivables_trend()

        assert result == []

    def test_single_snapshot_entry_returned(self, db_session: Session):
        pid = _make_project(db_session, "AD-REC-01")
        snap_date = date(2026, 3, 15)
        _seed_receivables_snapshot(db_session, pid, snap_date, 75_000.0)

        svc = AnalyticsDashboardService(db_session)
        result = svc.get_receivables_trend()

        assert len(result) == 1
        assert result[0].snapshot_date == str(snap_date)
        assert result[0].total_receivables == pytest.approx(75_000.0)

    def test_multiple_snapshot_dates_ordered_ascending(self, db_session: Session):
        pid = _make_project(db_session, "AD-REC-02")
        _seed_receivables_snapshot(db_session, pid, date(2026, 5, 1), 50_000.0)
        _seed_receivables_snapshot(db_session, pid, date(2026, 3, 1), 80_000.0)
        _seed_receivables_snapshot(db_session, pid, date(2026, 4, 1), 60_000.0)

        svc = AnalyticsDashboardService(db_session)
        result = svc.get_receivables_trend()

        dates = [e.snapshot_date for e in result]
        assert dates == sorted(dates), "Receivables trend must be ordered by snapshot date"

    def test_multiple_projects_same_date_aggregated(self, db_session: Session):
        """Receivables from multiple projects on the same date are summed."""
        snap_date = date(2026, 6, 1)
        pid1 = _make_project(db_session, "AD-REC-03A")
        pid2 = _make_project(db_session, "AD-REC-03B")
        _seed_receivables_snapshot(db_session, pid1, snap_date, 30_000.0)
        _seed_receivables_snapshot(db_session, pid2, snap_date, 45_000.0)

        svc = AnalyticsDashboardService(db_session)
        result = svc.get_receivables_trend()

        assert len(result) == 1
        assert result[0].total_receivables == pytest.approx(75_000.0)


# ---------------------------------------------------------------------------
# Test 4 — Portfolio KPI calculations
# ---------------------------------------------------------------------------


class TestGetPortfolioKPIs:
    """Tests for AnalyticsDashboardService.get_portfolio_kpis()."""

    def test_empty_fact_tables_return_zero_kpis(self, db_session: Session):
        svc = AnalyticsDashboardService(db_session)
        kpis = svc.get_portfolio_kpis()

        assert isinstance(kpis, PortfolioKPI)
        assert kpis.total_revenue == pytest.approx(0.0)
        assert kpis.total_collections == pytest.approx(0.0)
        assert kpis.total_receivables == pytest.approx(0.0)
        assert kpis.collection_efficiency == pytest.approx(0.0)

    def test_total_revenue_sums_all_revenue_facts(self, db_session: Session):
        pid = _make_project(db_session, "AD-KPI-01")
        uid = _make_unit_for_project(db_session, pid, "AD-K01-U01")
        _seed_revenue_fact(db_session, pid, uid, "2026-03", 30_000.0)
        _seed_revenue_fact(db_session, pid, uid, "2026-04", 20_000.0)

        svc = AnalyticsDashboardService(db_session)
        kpis = svc.get_portfolio_kpis()

        assert kpis.total_revenue == pytest.approx(50_000.0)

    def test_total_collections_sums_all_collections_facts(self, db_session: Session):
        pid = _make_project(db_session, "AD-KPI-02")
        _seed_collections_fact(db_session, pid, "2026-03", 15_000.0)
        _seed_collections_fact(db_session, pid, "2026-04", 25_000.0)

        svc = AnalyticsDashboardService(db_session)
        kpis = svc.get_portfolio_kpis()

        assert kpis.total_collections == pytest.approx(40_000.0)

    def test_total_receivables_uses_latest_snapshot(self, db_session: Session):
        """total_receivables must use the latest snapshot_date, not all history."""
        pid = _make_project(db_session, "AD-KPI-03")
        # Older snapshot: higher total.
        _seed_receivables_snapshot(db_session, pid, date(2026, 3, 1), 90_000.0)
        # Latest snapshot: this is what should be returned.
        _seed_receivables_snapshot(db_session, pid, date(2026, 4, 1), 70_000.0)

        svc = AnalyticsDashboardService(db_session)
        kpis = svc.get_portfolio_kpis()

        assert kpis.total_receivables == pytest.approx(70_000.0)

    def test_collection_efficiency_calculated_correctly(self, db_session: Session):
        """collection_efficiency = total_collections / total_revenue."""
        pid = _make_project(db_session, "AD-KPI-04")
        uid = _make_unit_for_project(db_session, pid, "AD-K04-U01")
        _seed_revenue_fact(db_session, pid, uid, "2026-03", 100_000.0)
        _seed_collections_fact(db_session, pid, "2026-03", 80_000.0)

        svc = AnalyticsDashboardService(db_session)
        kpis = svc.get_portfolio_kpis()

        assert kpis.collection_efficiency == pytest.approx(0.8)

    def test_collection_efficiency_zero_when_no_revenue(self, db_session: Session):
        """collection_efficiency is 0.0 when there is no revenue data."""
        pid = _make_project(db_session, "AD-KPI-05")
        _seed_collections_fact(db_session, pid, "2026-03", 50_000.0)

        svc = AnalyticsDashboardService(db_session)
        kpis = svc.get_portfolio_kpis()

        assert kpis.collection_efficiency == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Test 5 — API endpoint response structure
# ---------------------------------------------------------------------------


class TestPortfolioAnalyticsEndpoint:
    """Tests for GET /finance/analytics/portfolio."""

    def test_endpoint_rejects_unauthenticated_requests(self, client):
        """Callers with no Authorization header must be rejected (HTTPBearer auto_error)."""
        response = client.get("/api/v1/finance/analytics/portfolio")
        assert response.status_code == 401

    def test_endpoint_returns_200(self, auth_client):
        response = auth_client.get("/api/v1/finance/analytics/portfolio")
        assert response.status_code == 200

    def test_endpoint_returns_correct_schema_structure(self, auth_client):
        response = auth_client.get("/api/v1/finance/analytics/portfolio")
        data = response.json()

        assert "revenue_trend" in data
        assert "collections_trend" in data
        assert "receivables_trend" in data
        assert "kpis" in data

    def test_endpoint_kpis_contain_required_fields(self, auth_client):
        response = auth_client.get("/api/v1/finance/analytics/portfolio")
        kpis = response.json()["kpis"]

        assert "total_revenue" in kpis
        assert "total_collections" in kpis
        assert "total_receivables" in kpis
        assert "collection_efficiency" in kpis

    def test_endpoint_empty_portfolio_returns_zero_kpis(self, auth_client):
        response = auth_client.get("/api/v1/finance/analytics/portfolio")
        kpis = response.json()["kpis"]

        assert kpis["total_revenue"] == 0.0
        assert kpis["total_collections"] == 0.0
        assert kpis["total_receivables"] == 0.0
        assert kpis["collection_efficiency"] == 0.0

    def test_endpoint_returns_populated_trends_with_data(
        self, auth_client, db_session: Session
    ):
        """Seeding fact tables produces non-empty trends in the API response."""
        pid = _make_project(db_session, "AD-API-01")
        uid = _make_unit_for_project(db_session, pid, "AD-API01-U01")
        _seed_revenue_fact(db_session, pid, uid, "2026-03", 50_000.0)
        _seed_collections_fact(db_session, pid, "2026-03", 40_000.0)
        _seed_receivables_snapshot(db_session, pid, date(2026, 3, 15), 30_000.0)

        response = auth_client.get("/api/v1/finance/analytics/portfolio")
        assert response.status_code == 200

        data = response.json()
        assert len(data["revenue_trend"]) >= 1
        assert len(data["collections_trend"]) >= 1
        assert len(data["receivables_trend"]) >= 1

        kpis = data["kpis"]
        assert kpis["total_revenue"] == pytest.approx(50_000.0)
        assert kpis["total_collections"] == pytest.approx(40_000.0)
        assert kpis["total_receivables"] == pytest.approx(30_000.0)
        assert kpis["collection_efficiency"] == pytest.approx(0.8)
