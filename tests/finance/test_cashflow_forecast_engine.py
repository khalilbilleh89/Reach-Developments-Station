"""
Tests for the cashflow forecasting engine and service layer.

Validates:
  - correct monthly grouping of installment amounts
  - correct project-level forecast aggregation
  - correct portfolio-level forecast aggregation
  - handling of multiple projects
  - contracts with no future installments
  - partially paid installments (only outstanding count)
  - overdue installments included
  - paid/cancelled installments excluded
  - 404 handling for missing projects
"""

import pytest
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.finance.cashflow_forecast_engine import (
    InstallmentLine,
    build_portfolio_forecast,
    build_project_forecast,
)
from app.modules.finance.cashflow_service import CashflowForecastService


# ---------------------------------------------------------------------------
# Unit tests — pure calculation engine (no DB)
# ---------------------------------------------------------------------------


class TestBuildProjectForecast:
    """Tests for build_project_forecast — no DB, pure calculations."""

    def test_empty_installments_returns_zero(self):
        result = build_project_forecast("proj-1", [])
        assert result.project_id == "proj-1"
        assert result.total_expected == 0.0
        assert result.monthly_entries == []

    def test_single_installment_single_month(self):
        lines = [
            InstallmentLine(
                contract_id="c-001",
                project_id="proj-1",
                due_date=date(2026, 5, 15),
                amount=100_000.0,
                status="pending",
            )
        ]
        result = build_project_forecast("proj-1", lines)
        assert result.total_expected == pytest.approx(100_000.0)
        assert len(result.monthly_entries) == 1
        assert result.monthly_entries[0].month == "2026-05"
        assert result.monthly_entries[0].expected_collections == pytest.approx(
            100_000.0
        )
        assert result.monthly_entries[0].installment_count == 1

    def test_multiple_installments_same_month(self):
        lines = [
            InstallmentLine("c-001", "proj-1", date(2026, 6, 1), 50_000.0, "pending"),
            InstallmentLine("c-001", "proj-1", date(2026, 6, 15), 70_000.0, "pending"),
        ]
        result = build_project_forecast("proj-1", lines)
        assert len(result.monthly_entries) == 1
        assert result.monthly_entries[0].month == "2026-06"
        assert result.monthly_entries[0].expected_collections == pytest.approx(
            120_000.0
        )
        assert result.monthly_entries[0].installment_count == 2

    def test_installments_spread_across_months(self):
        lines = [
            InstallmentLine("c-001", "proj-1", date(2026, 5, 1), 200_000.0, "pending"),
            InstallmentLine("c-001", "proj-1", date(2026, 6, 1), 300_000.0, "pending"),
            InstallmentLine("c-001", "proj-1", date(2026, 7, 1), 150_000.0, "overdue"),
        ]
        result = build_project_forecast("proj-1", lines)
        assert len(result.monthly_entries) == 3
        months = [e.month for e in result.monthly_entries]
        assert months == ["2026-05", "2026-06", "2026-07"]
        assert result.total_expected == pytest.approx(650_000.0)

    def test_monthly_entries_sorted_ascending(self):
        lines = [
            InstallmentLine("c-001", "proj-1", date(2027, 1, 1), 100.0, "pending"),
            InstallmentLine("c-001", "proj-1", date(2026, 3, 1), 200.0, "pending"),
            InstallmentLine("c-001", "proj-1", date(2026, 11, 1), 300.0, "pending"),
        ]
        result = build_project_forecast("proj-1", lines)
        months = [e.month for e in result.monthly_entries]
        assert months == sorted(months), "Monthly entries should be sorted ascending"

    def test_overdue_installments_included(self):
        """OVERDUE installments must be included in the forecast."""
        lines = [
            InstallmentLine("c-001", "proj-1", date(2025, 12, 1), 80_000.0, "overdue"),
        ]
        result = build_project_forecast("proj-1", lines)
        assert result.total_expected == pytest.approx(80_000.0)

    def test_total_expected_equals_sum_of_monthly(self):
        lines = [
            InstallmentLine("c-001", "proj-1", date(2026, 5, 1), 100_000.0, "pending"),
            InstallmentLine("c-001", "proj-1", date(2026, 6, 1), 200_000.0, "pending"),
        ]
        result = build_project_forecast("proj-1", lines)
        assert result.total_expected == pytest.approx(
            sum(e.expected_collections for e in result.monthly_entries)
        )

    def test_multiple_contracts_same_month(self):
        lines = [
            InstallmentLine("c-001", "proj-1", date(2026, 9, 1), 150_000.0, "pending"),
            InstallmentLine("c-002", "proj-1", date(2026, 9, 15), 250_000.0, "pending"),
        ]
        result = build_project_forecast("proj-1", lines)
        assert len(result.monthly_entries) == 1
        assert result.monthly_entries[0].expected_collections == pytest.approx(
            400_000.0
        )
        assert result.monthly_entries[0].installment_count == 2


class TestBuildPortfolioForecast:
    """Tests for build_portfolio_forecast — no DB, pure calculations."""

    def test_empty_portfolio_returns_zero(self):
        result = build_portfolio_forecast({})
        assert result.total_expected == 0.0
        assert result.monthly_entries == []
        assert result.project_forecasts == []

    def test_single_project(self):
        project_installments = {
            "proj-1": [
                InstallmentLine(
                    "c-001", "proj-1", date(2026, 5, 1), 500_000.0, "pending"
                )
            ]
        }
        result = build_portfolio_forecast(project_installments)
        assert result.total_expected == pytest.approx(500_000.0)
        assert len(result.project_forecasts) == 1
        assert result.project_forecasts[0].project_id == "proj-1"

    def test_multiple_projects_same_month_merged(self):
        """Multiple projects with overlapping months should be merged in portfolio."""
        project_installments = {
            "proj-1": [
                InstallmentLine(
                    "c-001", "proj-1", date(2026, 7, 1), 300_000.0, "pending"
                )
            ],
            "proj-2": [
                InstallmentLine(
                    "c-002", "proj-2", date(2026, 7, 15), 200_000.0, "pending"
                )
            ],
        }
        result = build_portfolio_forecast(project_installments)
        assert result.total_expected == pytest.approx(500_000.0)
        assert len(result.monthly_entries) == 1
        assert result.monthly_entries[0].month == "2026-07"
        assert result.monthly_entries[0].expected_collections == pytest.approx(
            500_000.0
        )
        assert result.monthly_entries[0].installment_count == 2

    def test_multiple_projects_different_months(self):
        project_installments = {
            "proj-1": [
                InstallmentLine(
                    "c-001", "proj-1", date(2026, 5, 1), 100_000.0, "pending"
                )
            ],
            "proj-2": [
                InstallmentLine(
                    "c-002", "proj-2", date(2026, 8, 1), 400_000.0, "pending"
                )
            ],
        }
        result = build_portfolio_forecast(project_installments)
        assert result.total_expected == pytest.approx(500_000.0)
        assert len(result.monthly_entries) == 2
        months = [e.month for e in result.monthly_entries]
        assert "2026-05" in months
        assert "2026-08" in months

    def test_portfolio_total_equals_sum_of_project_totals(self):
        project_installments = {
            "proj-1": [
                InstallmentLine(
                    "c-001", "proj-1", date(2026, 5, 1), 100_000.0, "pending"
                ),
                InstallmentLine(
                    "c-001", "proj-1", date(2026, 6, 1), 200_000.0, "pending"
                ),
            ],
            "proj-2": [
                InstallmentLine(
                    "c-002", "proj-2", date(2026, 5, 15), 150_000.0, "overdue"
                ),
            ],
        }
        result = build_portfolio_forecast(project_installments)
        project_sum = sum(pf.total_expected for pf in result.project_forecasts)
        assert result.total_expected == pytest.approx(project_sum)


# ---------------------------------------------------------------------------
# Helpers — DB-backed tests
# ---------------------------------------------------------------------------

_seq: dict[str, int] = {}


def _make_project(db_session: Session, code: str) -> str:
    from app.modules.projects.models import Project

    project = Project(name=f"Cashflow Project {code}", code=code)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


def _make_unit(db_session: Session, project_id: str, unit_number: str) -> str:
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _seq.get(project_id, 0) + 1
    _seq[project_id] = seq

    phase = Phase(project_id=project_id, name=f"Phase {seq}", sequence=seq)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"BLK-{unit_number}")
    db_session.add(building)
    db_session.flush()

    floor = Floor(
        building_id=building.id,
        name="Floor 1",
        code="FL-01",
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
# Integration tests — CashflowForecastService with SQLite DB
# ---------------------------------------------------------------------------


class TestCashflowForecastService:
    def test_project_forecast_no_installments(self, db_session: Session):
        """Project with no installments returns zero totals."""
        pid = _make_project(db_session, "CF-SVC-01")
        svc = CashflowForecastService(db_session)
        result = svc.get_project_forecast(pid)

        assert result.project_id == pid
        assert result.total_expected == 0.0
        assert result.monthly_entries == []

    def test_project_forecast_pending_installments(self, db_session: Session):
        """Pending installments are grouped correctly by month."""
        pid = _make_project(db_session, "CF-SVC-02")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 300_000.0, "CNT-CF-02", "cf02@t.com")

        _make_installment(db_session, cid, 100_000.0, 1, date(2026, 5, 1), "pending")
        _make_installment(db_session, cid, 100_000.0, 2, date(2026, 6, 1), "pending")
        _make_installment(db_session, cid, 100_000.0, 3, date(2026, 7, 1), "pending")

        svc = CashflowForecastService(db_session)
        result = svc.get_project_forecast(pid)

        assert result.total_expected == pytest.approx(300_000.0)
        assert len(result.monthly_entries) == 3
        months = [e.month for e in result.monthly_entries]
        assert months == ["2026-05", "2026-06", "2026-07"]

    def test_project_forecast_paid_installments_excluded(self, db_session: Session):
        """PAID installments must not be included in the forecast."""
        pid = _make_project(db_session, "CF-SVC-03")
        uid = _make_unit(db_session, pid, "102")
        cid = _make_contract(db_session, uid, 200_000.0, "CNT-CF-03", "cf03@t.com")

        _make_installment(db_session, cid, 100_000.0, 1, date(2026, 5, 1), "paid")
        _make_installment(db_session, cid, 100_000.0, 2, date(2026, 6, 1), "pending")

        svc = CashflowForecastService(db_session)
        result = svc.get_project_forecast(pid)

        assert result.total_expected == pytest.approx(100_000.0)
        assert len(result.monthly_entries) == 1
        assert result.monthly_entries[0].month == "2026-06"

    def test_project_forecast_cancelled_installments_excluded(
        self, db_session: Session
    ):
        """CANCELLED installments must not be included in the forecast."""
        pid = _make_project(db_session, "CF-SVC-04")
        uid = _make_unit(db_session, pid, "103")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-CF-04", "cf04@t.com")

        _make_installment(db_session, cid, 100_000.0, 1, date(2026, 8, 1), "cancelled")

        svc = CashflowForecastService(db_session)
        result = svc.get_project_forecast(pid)

        assert result.total_expected == 0.0
        assert result.monthly_entries == []

    def test_project_forecast_overdue_installments_included(self, db_session: Session):
        """OVERDUE installments must be included in the forecast."""
        pid = _make_project(db_session, "CF-SVC-05")
        uid = _make_unit(db_session, pid, "104")
        cid = _make_contract(db_session, uid, 80_000.0, "CNT-CF-05", "cf05@t.com")

        _make_installment(db_session, cid, 80_000.0, 1, date(2025, 12, 1), "overdue")

        svc = CashflowForecastService(db_session)
        result = svc.get_project_forecast(pid)

        assert result.total_expected == pytest.approx(80_000.0)
        assert len(result.monthly_entries) == 1

    def test_project_forecast_not_found(self, db_session: Session):
        """Missing project raises HTTP 404."""
        svc = CashflowForecastService(db_session)
        with pytest.raises(HTTPException) as exc_info:
            svc.get_project_forecast("non-existent-id")
        assert exc_info.value.status_code == 404

    def test_portfolio_forecast_empty(self, db_session: Session):
        """Portfolio with no outstanding installments returns zero totals."""
        svc = CashflowForecastService(db_session)
        result = svc.get_portfolio_forecast()

        assert result.total_expected == 0.0
        assert result.project_count == 0
        assert result.monthly_entries == []
        assert result.project_forecasts == []

    def test_portfolio_forecast_multiple_projects(self, db_session: Session):
        """Portfolio forecast aggregates multiple projects correctly."""
        pid1 = _make_project(db_session, "CF-SVC-07A")
        uid1 = _make_unit(db_session, pid1, "201")
        cid1 = _make_contract(db_session, uid1, 500_000.0, "CNT-CF-07A", "cf07a@t.com")
        _make_installment(db_session, cid1, 250_000.0, 1, date(2026, 9, 1), "pending")
        _make_installment(db_session, cid1, 250_000.0, 2, date(2026, 10, 1), "pending")

        pid2 = _make_project(db_session, "CF-SVC-07B")
        uid2 = _make_unit(db_session, pid2, "202")
        cid2 = _make_contract(db_session, uid2, 400_000.0, "CNT-CF-07B", "cf07b@t.com")
        _make_installment(db_session, cid2, 400_000.0, 1, date(2026, 9, 15), "pending")

        svc = CashflowForecastService(db_session)
        result = svc.get_portfolio_forecast()

        assert result.project_count == 2
        assert result.total_expected == pytest.approx(900_000.0)

        # September should merge proj1 and proj2
        sep_entry = next(
            (e for e in result.monthly_entries if e.month == "2026-09"), None
        )
        assert sep_entry is not None
        assert sep_entry.expected_collections == pytest.approx(650_000.0)
        assert sep_entry.installment_count == 2

        # October only proj1
        oct_entry = next(
            (e for e in result.monthly_entries if e.month == "2026-10"), None
        )
        assert oct_entry is not None
        assert oct_entry.expected_collections == pytest.approx(250_000.0)

    def test_portfolio_forecast_total_equals_sum_of_projects(self, db_session: Session):
        """Invariant: portfolio total equals sum of all project totals."""
        pid = _make_project(db_session, "CF-SVC-08")
        uid = _make_unit(db_session, pid, "301")
        cid = _make_contract(db_session, uid, 60_000.0, "CNT-CF-08", "cf08@t.com")
        _make_installment(db_session, cid, 20_000.0, 1, date(2026, 4, 1), "pending")
        _make_installment(db_session, cid, 20_000.0, 2, date(2026, 5, 1), "overdue")
        _make_installment(db_session, cid, 20_000.0, 3, date(2026, 6, 1), "pending")

        svc = CashflowForecastService(db_session)
        result = svc.get_portfolio_forecast()

        project_sum = sum(pf.total_expected for pf in result.project_forecasts)
        assert result.total_expected == pytest.approx(project_sum)


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


class TestCashflowForecastApi:
    def test_portfolio_forecast_endpoint_returns_200(self, client):
        resp = client.get("/api/v1/finance/cashflow/forecast")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_expected" in data
        assert "monthly_entries" in data
        assert "project_forecasts" in data
        assert "project_count" in data

    def test_project_forecast_endpoint_404_for_missing_project(self, client):
        resp = client.get("/api/v1/finance/cashflow/forecast/project/non-existent-proj")
        assert resp.status_code == 404

    def test_project_forecast_endpoint_empty_project(self, client):
        """Project with no contracts returns zero forecast."""
        # Create project via API
        resp = client.post(
            "/api/v1/projects",
            json={"name": "CF API Test", "code": "CF-API-01"},
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        resp = client.get(f"/api/v1/finance/cashflow/forecast/project/{project_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == project_id
        assert data["total_expected"] == 0.0
        assert data["monthly_entries"] == []

    def test_portfolio_forecast_structure(self, client):
        resp = client.get("/api/v1/finance/cashflow/forecast")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["total_expected"], float)
        assert isinstance(data["project_count"], int)
        assert isinstance(data["monthly_entries"], list)
        assert isinstance(data["project_forecasts"], list)
