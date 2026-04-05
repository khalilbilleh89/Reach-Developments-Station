"""
Tests for the portfolio financial summary service and API endpoint.

Validates:
  - portfolio revenue aggregation
  - receivable totals and overdue percentage calculation
  - forecast_next_month extraction
  - per-project breakdown (recognized_revenue, receivables_exposure, collection_rate)
  - GET /finance/portfolio/summary API endpoint schema

Edge cases:
  - no projects in system (empty portfolio)
  - projects with no contracts
  - partially paid contracts
  - all receivables current (overdue_pct == 0)
  - all receivables overdue (overdue_pct == 100)
"""

import pytest
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.modules.finance.date_utils import next_month_key
from app.modules.finance.portfolio_summary_service import (
    PortfolioSummaryService,
    _next_month_key,
)
from app.modules.finance.schemas import (
    PortfolioFinancialSummaryResponse,
    ProjectFinancialSummaryEntry,
)


# ---------------------------------------------------------------------------
# Helper functions — reused across test classes
# ---------------------------------------------------------------------------

_ps_seq: dict[str, int] = {}


def _make_project(db_session: Session, code: str) -> str:
    from app.modules.projects.models import Project

    project = Project(name=f"Portfolio Summary Project {code}", code=code)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


def _make_unit(db_session: Session, project_id: str, unit_number: str) -> str:
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _ps_seq.get(project_id, 0) + 1
    _ps_seq[project_id] = seq

    phase = Phase(project_id=project_id, name=f"Phase {seq}", sequence=seq)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"PS-BLK-{unit_number}")
    db_session.add(building)
    db_session.flush()

    floor = Floor(
        building_id=building.id,
        name="Floor 1",
        code="PS-FL-01",
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
# Unit tests — _next_month_key helper
# ---------------------------------------------------------------------------


class TestNextMonthKey:
    def test_format_is_yyyy_mm(self):
        key = _next_month_key()
        assert len(key) == 7
        assert key[4] == "-"
        year, month = key.split("-")
        assert year.isdigit()
        assert month.isdigit()
        assert 1 <= int(month) <= 12

    def test_december_wraps_to_january(self, monkeypatch):
        import app.modules.finance.date_utils as du

        monkeypatch.setattr(
            du,
            "date",
            type("MockDate", (), {"today": staticmethod(lambda: date(2026, 12, 15))}),
        )  # type: ignore[arg-type]
        key = next_month_key()
        assert key == "2027-01"

    def test_non_december_increments(self, monkeypatch):
        import app.modules.finance.date_utils as du

        monkeypatch.setattr(
            du,
            "date",
            type("MockDate", (), {"today": staticmethod(lambda: date(2026, 5, 10))}),
        )  # type: ignore[arg-type]
        key = next_month_key()
        assert key == "2026-06"


# ---------------------------------------------------------------------------
# Integration tests — PortfolioSummaryService with SQLite DB
# ---------------------------------------------------------------------------


class TestPortfolioSummaryServiceEmpty:
    """Tests for empty portfolio (no contracts, no projects with data)."""

    def test_empty_portfolio_returns_zeros(self, db_session: Session):
        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert isinstance(result, PortfolioFinancialSummaryResponse)
        assert result.total_revenue_recognized == {}
        assert result.total_deferred_revenue == {}
        assert result.total_receivables == {}
        assert result.overdue_receivables == {}
        assert result.overdue_receivables_pct == 0.0
        assert result.forecast_next_month == {}
        assert result.project_count == 0
        assert result.project_summaries == []
        assert result.currencies == []

    def test_project_with_no_contracts_not_in_summaries(self, db_session: Session):
        """A project with no contracts should not appear in project_summaries."""
        _make_project(db_session, "PS-EMPTY-01")
        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()
        assert result.project_summaries == []


class TestPortfolioRevenueSummary:
    """Tests for total revenue recognition aggregation."""

    def test_single_project_no_payments(self, db_session: Session):
        pid = _make_project(db_session, "PS-REV-01")
        uid = _make_unit(db_session, pid, "PS-R01-U01")
        cid = _make_contract(db_session, uid, 200_000.0, "PS-REV-C001", "r01@test.com")
        _make_installment(db_session, cid, 100_000.0, 1, date(2027, 1, 1), "pending")
        _make_installment(db_session, cid, 100_000.0, 2, date(2027, 2, 1), "pending")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert result.total_revenue_recognized.get("AED", 0.0) == pytest.approx(0.0)
        assert result.total_deferred_revenue.get("AED", 0.0) == pytest.approx(200_000.0)

    def test_single_project_partial_payment(self, db_session: Session):
        pid = _make_project(db_session, "PS-REV-02")
        uid = _make_unit(db_session, pid, "PS-R02-U01")
        cid = _make_contract(db_session, uid, 200_000.0, "PS-REV-C002", "r02@test.com")
        _make_installment(db_session, cid, 100_000.0, 1, date(2026, 1, 1), "paid")
        _make_installment(db_session, cid, 100_000.0, 2, date(2027, 3, 1), "pending")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert result.total_revenue_recognized.get("AED", 0.0) == pytest.approx(100_000.0)
        assert result.total_deferred_revenue.get("AED", 0.0) == pytest.approx(100_000.0)

    def test_multi_project_revenue_aggregation(self, db_session: Session):
        pid1 = _make_project(db_session, "PS-REV-03")
        uid1 = _make_unit(db_session, pid1, "PS-R03-U01")
        cid1 = _make_contract(
            db_session, uid1, 300_000.0, "PS-REV-C003", "r03a@test.com"
        )
        _make_installment(db_session, cid1, 150_000.0, 1, date(2026, 1, 1), "paid")
        _make_installment(db_session, cid1, 150_000.0, 2, date(2027, 1, 1), "pending")

        pid2 = _make_project(db_session, "PS-REV-04")
        uid2 = _make_unit(db_session, pid2, "PS-R04-U01")
        cid2 = _make_contract(
            db_session, uid2, 400_000.0, "PS-REV-C004", "r04@test.com"
        )
        _make_installment(db_session, cid2, 200_000.0, 1, date(2026, 2, 1), "paid")
        _make_installment(db_session, cid2, 200_000.0, 2, date(2027, 2, 1), "pending")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert result.total_revenue_recognized.get("AED", 0.0) == pytest.approx(350_000.0)
        assert result.total_deferred_revenue.get("AED", 0.0) == pytest.approx(350_000.0)


class TestPortfolioReceivables:
    """Tests for total and overdue receivables computation."""

    def test_all_current_receivables(self, db_session: Session):
        """Installments due in the future — overdue_pct should be 0."""
        pid = _make_project(db_session, "PS-RCV-01")
        uid = _make_unit(db_session, pid, "PS-RCV01-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "PS-RCV-C001", "rcv01@test.com"
        )
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid, 100_000.0, 1, future, "pending")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert result.total_receivables.get("AED", 0.0) == pytest.approx(100_000.0)
        assert result.overdue_receivables.get("AED", 0.0) == pytest.approx(0.0)
        assert result.overdue_receivables_pct == pytest.approx(0.0)

    def test_all_overdue_receivables(self, db_session: Session):
        """All installments past due — overdue_pct should be 100."""
        pid = _make_project(db_session, "PS-RCV-02")
        uid = _make_unit(db_session, pid, "PS-RCV02-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "PS-RCV-C002", "rcv02@test.com"
        )
        past = date.today() - timedelta(days=60)
        _make_installment(db_session, cid, 100_000.0, 1, past, "overdue")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert result.total_receivables.get("AED", 0.0) == pytest.approx(100_000.0)
        assert result.overdue_receivables.get("AED", 0.0) == pytest.approx(100_000.0)
        assert result.overdue_receivables_pct == pytest.approx(100.0)

    def test_mixed_current_and_overdue(self, db_session: Session):
        pid = _make_project(db_session, "PS-RCV-03")
        uid = _make_unit(db_session, pid, "PS-RCV03-U01")
        cid = _make_contract(
            db_session, uid, 200_000.0, "PS-RCV-C003", "rcv03@test.com"
        )
        future = date.today() + timedelta(days=30)
        past = date.today() - timedelta(days=45)
        _make_installment(db_session, cid, 100_000.0, 1, future, "pending")
        _make_installment(db_session, cid, 100_000.0, 2, past, "overdue")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert result.total_receivables.get("AED", 0.0) == pytest.approx(200_000.0)
        assert result.overdue_receivables.get("AED", 0.0) == pytest.approx(100_000.0)
        assert result.overdue_receivables_pct == pytest.approx(50.0)

    def test_paid_cancelled_excluded_from_receivables(self, db_session: Session):
        """PAID and CANCELLED installments must not appear in receivables."""
        pid = _make_project(db_session, "PS-RCV-04")
        uid = _make_unit(db_session, pid, "PS-RCV04-U01")
        cid = _make_contract(
            db_session, uid, 300_000.0, "PS-RCV-C004", "rcv04@test.com"
        )
        past = date.today() - timedelta(days=10)
        _make_installment(db_session, cid, 100_000.0, 1, past, "paid")
        _make_installment(db_session, cid, 100_000.0, 2, past, "cancelled")
        future = date.today() + timedelta(days=10)
        _make_installment(db_session, cid, 100_000.0, 3, future, "pending")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert result.total_receivables.get("AED", 0.0) == pytest.approx(100_000.0)


class TestPortfolioForecastNextMonth:
    """Tests for next-month cashflow forecast extraction."""

    def test_installment_due_next_month_captured(self, db_session: Session):
        pid = _make_project(db_session, "PS-FCT-01")
        uid = _make_unit(db_session, pid, "PS-FCT01-U01")
        cid = _make_contract(
            db_session, uid, 500_000.0, "PS-FCT-C001", "fct01@test.com"
        )
        today = date.today()
        if today.month == 12:
            next_month_date = date(today.year + 1, 1, 15)
        else:
            next_month_date = date(today.year, today.month + 1, 15)

        _make_installment(db_session, cid, 500_000.0, 1, next_month_date, "pending")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert result.forecast_next_month.get("AED", 0.0) == pytest.approx(500_000.0)

    def test_no_next_month_installments_returns_zero(self, db_session: Session):
        """When no installments fall in next month, forecast_next_month is empty."""
        pid = _make_project(db_session, "PS-FCT-02")
        uid = _make_unit(db_session, pid, "PS-FCT02-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "PS-FCT-C002", "fct02@test.com"
        )
        # Installment scheduled in the same month next year — explicitly not next month
        today = date.today()
        far_future = date(today.year + 1, today.month, 15)
        _make_installment(db_session, cid, 100_000.0, 1, far_future, "pending")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert sum(result.forecast_next_month.values()) == pytest.approx(0.0)


class TestProjectFinancialSummaryEntries:
    """Tests for per-project financial breakdown."""

    def test_project_entry_fields(self, db_session: Session):
        pid = _make_project(db_session, "PS-PROJ-01")
        uid = _make_unit(db_session, pid, "PS-PROJ01-U01")
        cid = _make_contract(
            db_session, uid, 200_000.0, "PS-PROJ-C001", "proj01@test.com"
        )
        past = date.today() - timedelta(days=5)
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid, 100_000.0, 1, past, "paid")
        _make_installment(db_session, cid, 100_000.0, 2, future, "pending")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert len(result.project_summaries) == 1
        entry = result.project_summaries[0]
        assert isinstance(entry, ProjectFinancialSummaryEntry)
        assert entry.project_id == pid
        assert entry.recognized_revenue == pytest.approx(100_000.0)
        assert entry.receivables_exposure == pytest.approx(100_000.0)
        assert entry.collection_rate == pytest.approx(0.5)

    def test_multi_project_entries(self, db_session: Session):
        pid1 = _make_project(db_session, "PS-PROJ-02")
        uid1 = _make_unit(db_session, pid1, "PS-PROJ02-U01")
        cid1 = _make_contract(
            db_session, uid1, 100_000.0, "PS-PROJ-C002", "proj02a@test.com"
        )
        _make_installment(
            db_session, cid1, 100_000.0, 1, date.today() - timedelta(days=5), "paid"
        )

        pid2 = _make_project(db_session, "PS-PROJ-03")
        uid2 = _make_unit(db_session, pid2, "PS-PROJ03-U01")
        cid2 = _make_contract(
            db_session, uid2, 300_000.0, "PS-PROJ-C003", "proj03@test.com"
        )
        _make_installment(
            db_session,
            cid2,
            300_000.0,
            1,
            date.today() + timedelta(days=30),
            "pending",
        )

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        pids = {e.project_id for e in result.project_summaries}
        assert pid1 in pids
        assert pid2 in pids

        proj1 = next(e for e in result.project_summaries if e.project_id == pid1)
        assert proj1.collection_rate == pytest.approx(1.0)
        assert proj1.recognized_revenue == pytest.approx(100_000.0)
        assert proj1.receivables_exposure == pytest.approx(0.0)

        proj2 = next(e for e in result.project_summaries if e.project_id == pid2)
        assert proj2.collection_rate == pytest.approx(0.0)
        assert proj2.recognized_revenue == pytest.approx(0.0)
        assert proj2.receivables_exposure == pytest.approx(300_000.0)

    def test_project_no_outstanding_has_zero_receivables(self, db_session: Session):
        """Fully paid project — receivables_exposure should be 0."""
        pid = _make_project(db_session, "PS-PROJ-04")
        uid = _make_unit(db_session, pid, "PS-PROJ04-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "PS-PROJ-C004", "proj04@test.com"
        )
        _make_installment(db_session, cid, 100_000.0, 1, date(2026, 1, 1), "paid")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        entry = next((e for e in result.project_summaries if e.project_id == pid), None)
        assert entry is not None
        assert entry.receivables_exposure == pytest.approx(0.0)
        assert entry.collection_rate == pytest.approx(1.0)

    def test_per_contract_clamp_prevents_overpayment_masking_underpayment(
        self, db_session: Session
    ):
        """Per-contract clamping must be applied before summing project totals.

        Scenario:
          Contract A: price = 100k, paid = 150k  (overpaid)
          Contract B: price = 100k, paid = 0      (unpaid)

        Incorrect aggregate-then-clamp logic:
          total_price = 200k, total_paid = 150k → recognized = 150k  ✗

        Correct per-contract-then-sum logic:
          Contract A: min(150k, 100k) = 100k recognized
          Contract B: min(0,    100k) = 0    recognized
          Project total recognized    = 100k  ✓
        """
        pid = _make_project(db_session, "PS-PROJ-05")

        # Contract A — overpaid (150k paid on a 100k contract)
        uid_a = _make_unit(db_session, pid, "PS-PROJ05-UA")
        cid_a = _make_contract(
            db_session, uid_a, 100_000.0, "PS-PROJ-C005A", "proj05a@test.com"
        )
        _make_installment(db_session, cid_a, 150_000.0, 1, date(2026, 1, 1), "paid")

        # Contract B — unpaid (0 paid on a 100k contract)
        uid_b = _make_unit(db_session, pid, "PS-PROJ05-UB")
        cid_b = _make_contract(
            db_session, uid_b, 100_000.0, "PS-PROJ-C005B", "proj05b@test.com"
        )
        _make_installment(
            db_session,
            cid_b,
            100_000.0,
            1,
            date.today() + timedelta(days=30),
            "pending",
        )

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        entry = next((e for e in result.project_summaries if e.project_id == pid), None)
        assert entry is not None
        # Per-contract clamped sum: 100k (A clamped) + 0 (B unpaid) = 100k
        assert entry.recognized_revenue == pytest.approx(100_000.0)
        # Total contract value = 200k, recognized = 100k → rate = 0.5
        assert entry.collection_rate == pytest.approx(0.5)
        # Contract B still has 100k outstanding
        assert entry.receivables_exposure == pytest.approx(100_000.0)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestPortfolioSummaryApiEndpoint:
    def test_endpoint_returns_200_empty_portfolio(self, client):
        response = client.get("/api/v1/finance/portfolio/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_revenue_recognized" in data
        assert "total_deferred_revenue" in data
        assert "total_receivables" in data
        assert "overdue_receivables" in data
        assert "overdue_receivables_pct" in data
        assert "forecast_next_month" in data
        assert "project_count" in data
        assert "project_summaries" in data

    def test_endpoint_project_summaries_is_list(self, client):
        response = client.get("/api/v1/finance/portfolio/summary")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["project_summaries"], list)

    def test_endpoint_with_data(self, client, db_session: Session):
        pid = _make_project(db_session, "PS-API-01")
        uid = _make_unit(db_session, pid, "PS-API01-U01")
        cid = _make_contract(
            db_session, uid, 100_000.0, "PS-API-C001", "api01@test.com"
        )
        _make_installment(db_session, cid, 50_000.0, 1, date(2026, 1, 1), "paid")
        _make_installment(
            db_session,
            cid,
            50_000.0,
            2,
            date.today() + timedelta(days=30),
            "pending",
        )

        response = client.get("/api/v1/finance/portfolio/summary")
        assert response.status_code == 200
        data = response.json()
        # Monetary totals are now grouped by currency
        assert isinstance(data["total_revenue_recognized"], dict)
        assert data["total_revenue_recognized"].get("AED", 0.0) == pytest.approx(50_000.0)
        assert isinstance(data["total_receivables"], dict)
        assert data["total_receivables"].get("AED", 0.0) == pytest.approx(50_000.0)
        assert len(data["project_summaries"]) >= 1

        proj_entry = next(
            (e for e in data["project_summaries"] if e["project_id"] == pid), None
        )
        assert proj_entry is not None
        assert proj_entry["recognized_revenue"] == pytest.approx(50_000.0)
        assert proj_entry["receivables_exposure"] == pytest.approx(50_000.0)
        assert proj_entry["collection_rate"] == pytest.approx(0.5)

    def test_endpoint_overdue_pct_field_present(self, client):
        response = client.get("/api/v1/finance/portfolio/summary")
        assert response.status_code == 200
        data = response.json()
        assert 0.0 <= data["overdue_receivables_pct"] <= 100.0
