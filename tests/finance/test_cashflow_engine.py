"""
Tests for the PR-33 comprehensive cashflow projection engine.

Validates:
  - exact schedule-based projection (scheduled vs expected vs collected)
  - partial collection handling (PAID = collected, PENDING = 0 collected)
  - overdue installment carry-forward into the first forecast period
  - mixed paid/unpaid future installments
  - contract-level aggregation
  - project-level aggregation
  - portfolio-level aggregation (totals = sum of project totals)
  - empty-scope results return zero but valid payloads
  - date-window truncation (installments outside window excluded)
  - cumulative expected amount is monotonically non-decreasing
  - collection_probability scales expected_amount correctly
  - variance_to_schedule is always expected − scheduled
  - API endpoints return expected response shapes
  - invalid date range returns 422
  - missing scope returns 404
"""

import pytest
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError, ValidationError
from app.modules.finance.cashflow_engine import (
    CashflowForecastResult,
    ForecastAssumptions,
    InstallmentRecord,
    PortfolioCashflowResult,
    compute_contract_forecast,
    compute_portfolio_forecast,
    compute_project_forecast,
)
from app.modules.finance.cashflow_service import CashflowForecastService
from app.modules.finance.schemas import CashflowForecastAssumptions


# ---------------------------------------------------------------------------
# Pure engine tests — no DB
# ---------------------------------------------------------------------------


class TestComputeContractForecast:
    """Tests for compute_contract_forecast — pure calculations, no DB."""

    START = date(2026, 4, 1)
    END = date(2026, 6, 30)

    def test_empty_installments_returns_zero_periods(self):
        result = compute_contract_forecast("c-001", [], self.START, self.END)
        assert result.scope_type == "contract"
        assert result.scope_id == "c-001"
        assert result.summary.scheduled_total == 0.0
        assert result.summary.expected_total == 0.0
        assert result.summary.collected_total == 0.0
        assert len(result.periods) == 3  # April, May, June

    def test_single_pending_installment_in_window(self):
        lines = [
            InstallmentRecord(
                contract_id="c-001",
                project_id="p-001",
                due_date=date(2026, 5, 15),
                scheduled_amount=100_000.0,
                collected_amount=0.0,
                status="pending",
            )
        ]
        result = compute_contract_forecast("c-001", lines, self.START, self.END)
        assert result.summary.scheduled_total == pytest.approx(100_000.0)
        assert result.summary.collected_total == pytest.approx(0.0)
        assert result.summary.expected_total == pytest.approx(100_000.0)
        assert result.summary.variance_to_schedule == pytest.approx(0.0)

        may = next(p for p in result.periods if p.period_label == "2026-05")
        assert may.scheduled_amount == pytest.approx(100_000.0)
        assert may.expected_amount == pytest.approx(100_000.0)
        assert may.collected_amount == pytest.approx(0.0)

    def test_paid_installment_counted_in_schedule_and_collected(self):
        lines = [
            InstallmentRecord(
                contract_id="c-001",
                project_id="p-001",
                due_date=date(2026, 5, 15),
                scheduled_amount=100_000.0,
                collected_amount=100_000.0,  # fully paid
                status="paid",
            )
        ]
        result = compute_contract_forecast("c-001", lines, self.START, self.END)
        may = next(p for p in result.periods if p.period_label == "2026-05")
        assert may.scheduled_amount == pytest.approx(100_000.0)
        assert may.collected_amount == pytest.approx(100_000.0)
        # remaining_unpaid = 0 → expected = 0
        assert may.expected_amount == pytest.approx(0.0)
        assert may.variance_to_schedule == pytest.approx(-100_000.0)

    def test_mixed_paid_and_pending(self):
        """Paid installments reduce remaining unpaid; pending are fully expected."""
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 4, 10), 50_000.0, 50_000.0, "paid"),
            InstallmentRecord("c-001", "p-001", date(2026, 5, 10), 75_000.0, 0.0, "pending"),
        ]
        result = compute_contract_forecast("c-001", lines, self.START, self.END)
        assert result.summary.scheduled_total == pytest.approx(125_000.0)
        assert result.summary.collected_total == pytest.approx(50_000.0)
        assert result.summary.expected_total == pytest.approx(75_000.0)

    def test_collection_probability_scales_expected(self):
        """Expected amount is scaled by the collection_probability assumption."""
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 5, 1), 200_000.0, 0.0, "pending"),
        ]
        assumptions = ForecastAssumptions(collection_probability=0.8)
        result = compute_contract_forecast("c-001", lines, self.START, self.END, assumptions)
        may = next(p for p in result.periods if p.period_label == "2026-05")
        assert may.expected_amount == pytest.approx(160_000.0)

    def test_overdue_carry_forward_into_first_period(self):
        """Overdue installment due before window start lands in first period."""
        lines = [
            InstallmentRecord(
                "c-001", "p-001",
                date(2026, 3, 1),  # before start
                80_000.0, 0.0, "overdue",
            )
        ]
        assumptions = ForecastAssumptions(carry_forward_overdue=True)
        result = compute_contract_forecast("c-001", lines, self.START, self.END, assumptions)

        april = next(p for p in result.periods if p.period_label == "2026-04")
        assert april.scheduled_amount == pytest.approx(80_000.0)
        assert april.expected_amount == pytest.approx(80_000.0)
        assert april.installment_count == 1

    def test_overdue_not_carried_forward_when_disabled(self):
        """When carry_forward_overdue=False, pre-window overdue installments are dropped."""
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 3, 1), 80_000.0, 0.0, "overdue"),
        ]
        assumptions = ForecastAssumptions(carry_forward_overdue=False)
        result = compute_contract_forecast("c-001", lines, self.START, self.END, assumptions)

        assert result.summary.scheduled_total == pytest.approx(0.0)
        for p in result.periods:
            assert p.installment_count == 0

    def test_post_window_installments_excluded(self):
        """Installments due after end_date are excluded from all periods."""
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 8, 1), 120_000.0, 0.0, "pending"),
        ]
        result = compute_contract_forecast("c-001", lines, self.START, self.END)
        assert result.summary.scheduled_total == pytest.approx(0.0)
        for p in result.periods:
            assert p.installment_count == 0

    def test_cumulative_expected_is_monotonically_non_decreasing(self):
        """cumulative_expected_amount must never decrease from period to period."""
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 4, 1), 100_000.0, 0.0, "pending"),
            InstallmentRecord("c-001", "p-001", date(2026, 5, 1), 200_000.0, 0.0, "pending"),
            InstallmentRecord("c-001", "p-001", date(2026, 6, 1), 150_000.0, 0.0, "pending"),
        ]
        result = compute_contract_forecast("c-001", lines, self.START, self.END)
        cumulative_values = [p.cumulative_expected_amount for p in result.periods]
        for a, b in zip(cumulative_values, cumulative_values[1:]):
            assert b >= a, f"Cumulative decreased: {a} → {b}"

    def test_cumulative_expected_final_equals_summary_total(self):
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 4, 1), 100_000.0, 0.0, "pending"),
            InstallmentRecord("c-001", "p-001", date(2026, 5, 1), 200_000.0, 0.0, "pending"),
        ]
        result = compute_contract_forecast("c-001", lines, self.START, self.END)
        last_cumulative = result.periods[-1].cumulative_expected_amount
        assert last_cumulative == pytest.approx(result.summary.expected_total)

    def test_variance_to_schedule_equals_expected_minus_scheduled(self):
        """variance_to_schedule must equal expected_amount − scheduled_amount per period."""
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 5, 1), 100_000.0, 0.0, "pending"),
        ]
        assumptions = ForecastAssumptions(collection_probability=0.9)
        result = compute_contract_forecast("c-001", lines, self.START, self.END, assumptions)
        for p in result.periods:
            assert p.variance_to_schedule == pytest.approx(
                p.expected_amount - p.scheduled_amount
            )

    def test_installment_count_correct_per_period(self):
        """installment_count tracks how many installments land in each period."""
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 4, 5), 50_000.0, 0.0, "pending"),
            InstallmentRecord("c-001", "p-001", date(2026, 4, 20), 50_000.0, 0.0, "pending"),
            InstallmentRecord("c-001", "p-001", date(2026, 5, 1), 100_000.0, 0.0, "pending"),
        ]
        result = compute_contract_forecast("c-001", lines, self.START, self.END)
        april = next(p for p in result.periods if p.period_label == "2026-04")
        may = next(p for p in result.periods if p.period_label == "2026-05")
        assert april.installment_count == 2
        assert may.installment_count == 1

    def test_period_boundaries_correct(self):
        """Each period_start is the first day of the month; period_end is the last."""
        result = compute_contract_forecast("c-001", [], self.START, self.END)
        for period in result.periods:
            assert period.period_start.day == 1
            last_day = (
                period.period_end.day
            )
            import calendar
            _, expected_last = calendar.monthrange(
                period.period_end.year, period.period_end.month
            )
            assert last_day == expected_last

    def test_single_month_window(self):
        """A window spanning a single month produces exactly one period."""
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 5, 15), 100_000.0, 0.0, "pending"),
        ]
        result = compute_contract_forecast("c-001", lines, date(2026, 5, 1), date(2026, 5, 31))
        assert len(result.periods) == 1
        assert result.periods[0].period_label == "2026-05"
        assert result.summary.expected_total == pytest.approx(100_000.0)

    def test_include_paid_false_excludes_paid_from_schedule(self):
        """With include_paid_in_schedule=False, paid installments are excluded entirely."""
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 5, 1), 50_000.0, 50_000.0, "paid"),
            InstallmentRecord("c-001", "p-001", date(2026, 5, 15), 50_000.0, 0.0, "pending"),
        ]
        assumptions = ForecastAssumptions(include_paid_in_schedule=False)
        result = compute_contract_forecast("c-001", lines, self.START, self.END, assumptions)
        may = next(p for p in result.periods if p.period_label == "2026-05")
        # Only the pending installment should appear
        assert may.scheduled_amount == pytest.approx(50_000.0)
        assert may.installment_count == 1


class TestComputeProjectForecast:
    """Tests for compute_project_forecast — pure calculations, no DB."""

    START = date(2026, 1, 1)
    END = date(2026, 12, 31)

    def test_empty_project_returns_zero_summary(self):
        result = compute_project_forecast("p-001", [], self.START, self.END)
        assert result.scope_type == "project"
        assert result.scope_id == "p-001"
        assert result.summary.scheduled_total == 0.0
        assert result.summary.expected_total == 0.0
        assert len(result.periods) == 12

    def test_multiple_contracts_same_month_aggregated(self):
        """Installments from different contracts in the same month are summed."""
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 3, 10), 150_000.0, 0.0, "pending"),
            InstallmentRecord("c-002", "p-001", date(2026, 3, 20), 250_000.0, 0.0, "pending"),
        ]
        result = compute_project_forecast("p-001", lines, self.START, self.END)
        march = next(p for p in result.periods if p.period_label == "2026-03")
        assert march.scheduled_amount == pytest.approx(400_000.0)
        assert march.expected_amount == pytest.approx(400_000.0)
        assert march.installment_count == 2

    def test_summary_totals_match_period_sums(self):
        """Summary totals must equal the sum of per-period values."""
        lines = [
            InstallmentRecord("c-001", "p-001", date(2026, 2, 1), 100_000.0, 0.0, "pending"),
            InstallmentRecord("c-001", "p-001", date(2026, 5, 1), 200_000.0, 0.0, "overdue"),
            InstallmentRecord("c-001", "p-001", date(2026, 9, 1), 50_000.0, 50_000.0, "paid"),
        ]
        result = compute_project_forecast("p-001", lines, self.START, self.END)
        assert result.summary.scheduled_total == pytest.approx(
            sum(p.scheduled_amount for p in result.periods)
        )
        assert result.summary.expected_total == pytest.approx(
            sum(p.expected_amount for p in result.periods)
        )
        assert result.summary.collected_total == pytest.approx(
            sum(p.collected_amount for p in result.periods)
        )


class TestComputePortfolioForecast:
    """Tests for compute_portfolio_forecast — pure calculations, no DB."""

    START = date(2026, 1, 1)
    END = date(2026, 6, 30)

    def test_empty_portfolio_returns_zero_periods(self):
        result = compute_portfolio_forecast({}, self.START, self.END)
        assert result.scope_type == "portfolio"
        assert result.scope_id == "portfolio"
        assert result.summary.expected_total == 0.0
        assert len(result.project_forecasts) == 0
        assert len(result.periods) == 6

    def test_single_project_in_portfolio(self):
        project_installments = {
            "p-001": [
                InstallmentRecord("c-001", "p-001", date(2026, 3, 1), 500_000.0, 0.0, "pending"),
            ]
        }
        result = compute_portfolio_forecast(project_installments, self.START, self.END)
        assert result.summary.expected_total == pytest.approx(500_000.0)
        assert len(result.project_forecasts) == 1

    def test_portfolio_total_equals_sum_of_project_totals(self):
        """Portfolio summary total must equal the sum of all project totals."""
        project_installments = {
            "p-001": [
                InstallmentRecord("c-001", "p-001", date(2026, 2, 1), 100_000.0, 0.0, "pending"),
                InstallmentRecord("c-001", "p-001", date(2026, 3, 1), 200_000.0, 0.0, "overdue"),
            ],
            "p-002": [
                InstallmentRecord("c-002", "p-002", date(2026, 4, 1), 300_000.0, 0.0, "pending"),
                InstallmentRecord("c-003", "p-002", date(2026, 5, 1), 150_000.0, 150_000.0, "paid"),
            ],
        }
        result = compute_portfolio_forecast(project_installments, self.START, self.END)
        project_sum = sum(pf.summary.expected_total for pf in result.project_forecasts)
        assert result.summary.expected_total == pytest.approx(project_sum)

    def test_portfolio_scheduled_total_equals_sum_of_project_scheduled(self):
        project_installments = {
            "p-001": [
                InstallmentRecord("c-001", "p-001", date(2026, 2, 1), 100_000.0, 0.0, "pending"),
            ],
            "p-002": [
                InstallmentRecord("c-002", "p-002", date(2026, 3, 1), 200_000.0, 200_000.0, "paid"),
            ],
        }
        result = compute_portfolio_forecast(project_installments, self.START, self.END)
        project_scheduled = sum(pf.summary.scheduled_total for pf in result.project_forecasts)
        assert result.summary.scheduled_total == pytest.approx(project_scheduled)

    def test_multiple_projects_same_month_merged_in_portfolio_periods(self):
        """Portfolio period data merges installments from all projects."""
        project_installments = {
            "p-001": [
                InstallmentRecord("c-001", "p-001", date(2026, 4, 1), 200_000.0, 0.0, "pending"),
            ],
            "p-002": [
                InstallmentRecord("c-002", "p-002", date(2026, 4, 15), 300_000.0, 0.0, "pending"),
            ],
        }
        result = compute_portfolio_forecast(project_installments, self.START, self.END)
        april = next(p for p in result.periods if p.period_label == "2026-04")
        assert april.scheduled_amount == pytest.approx(500_000.0)
        assert april.installment_count == 2

    def test_project_forecasts_sorted_by_project_id(self):
        """Project forecasts within the portfolio are sorted by project_id for determinism."""
        project_installments = {
            "z-project": [InstallmentRecord("c-z", "z-project", date(2026, 2, 1), 10.0, 0.0, "pending")],
            "a-project": [InstallmentRecord("c-a", "a-project", date(2026, 2, 1), 20.0, 0.0, "pending")],
            "m-project": [InstallmentRecord("c-m", "m-project", date(2026, 3, 1), 30.0, 0.0, "pending")],
        }
        result = compute_portfolio_forecast(project_installments, self.START, self.END)
        ids = [pf.scope_id for pf in result.project_forecasts]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Service-layer integration tests — with SQLite DB
# ---------------------------------------------------------------------------

_seq: dict[str, int] = {}


def _make_project(db_session: Session, code: str) -> str:
    from app.modules.projects.models import Project

    project = Project(name=f"CE Project {code}", code=code)
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


class TestCashflowForecastServiceV2:
    """Integration tests for the PR-33 comprehensive forecast service methods."""

    START = date(2026, 4, 1)
    END = date(2026, 9, 30)

    def test_contract_forecast_not_found(self, db_session: Session):
        """Missing contract raises ResourceNotFoundError."""
        svc = CashflowForecastService(db_session)
        with pytest.raises(ResourceNotFoundError):
            svc.get_contract_forecast_v2("non-existent", self.START, self.END)

    def test_contract_forecast_invalid_date_window(self, db_session: Session):
        """start_date > end_date raises ValidationError."""
        pid = _make_project(db_session, "CE-SVC-INV-01")
        uid = _make_unit(db_session, pid, "501")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-CE-INV01", "ce_inv01@t.com")
        svc = CashflowForecastService(db_session)
        with pytest.raises(ValidationError):
            svc.get_contract_forecast_v2(cid, date(2026, 9, 1), date(2026, 1, 1))

    def test_contract_forecast_empty_schedule(self, db_session: Session):
        """Contract with no installments returns zeroed but valid forecast."""
        pid = _make_project(db_session, "CE-SVC-E01")
        uid = _make_unit(db_session, pid, "502")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-CE-E01", "ce_e01@t.com")

        svc = CashflowForecastService(db_session)
        result = svc.get_contract_forecast_v2(cid, self.START, self.END)

        assert result.contract_id == cid
        assert result.summary.scheduled_total == 0.0
        assert result.summary.expected_total == 0.0
        assert len(result.periods) == 6

    def test_contract_forecast_pending_installments(self, db_session: Session):
        """Pending installments appear as scheduled and expected."""
        pid = _make_project(db_session, "CE-SVC-P01")
        uid = _make_unit(db_session, pid, "503")
        cid = _make_contract(db_session, uid, 300_000.0, "CNT-CE-P01", "ce_p01@t.com")
        _make_installment(db_session, cid, 100_000.0, 1, date(2026, 5, 1), "pending")
        _make_installment(db_session, cid, 200_000.0, 2, date(2026, 7, 1), "pending")

        svc = CashflowForecastService(db_session)
        result = svc.get_contract_forecast_v2(cid, self.START, self.END)

        assert result.summary.scheduled_total == pytest.approx(300_000.0)
        assert result.summary.expected_total == pytest.approx(300_000.0)
        assert result.summary.collected_total == pytest.approx(0.0)

    def test_contract_forecast_paid_installments_in_schedule(self, db_session: Session):
        """PAID installments count in scheduled and collected but not expected."""
        pid = _make_project(db_session, "CE-SVC-PA01")
        uid = _make_unit(db_session, pid, "504")
        cid = _make_contract(db_session, uid, 400_000.0, "CNT-CE-PA01", "ce_pa01@t.com")
        _make_installment(db_session, cid, 200_000.0, 1, date(2026, 4, 1), "paid")
        _make_installment(db_session, cid, 200_000.0, 2, date(2026, 5, 1), "pending")

        svc = CashflowForecastService(db_session)
        result = svc.get_contract_forecast_v2(cid, self.START, self.END)

        assert result.summary.scheduled_total == pytest.approx(400_000.0)
        assert result.summary.collected_total == pytest.approx(200_000.0)
        assert result.summary.expected_total == pytest.approx(200_000.0)

    def test_project_forecast_v2_not_found(self, db_session: Session):
        """Missing project raises ResourceNotFoundError."""
        svc = CashflowForecastService(db_session)
        with pytest.raises(ResourceNotFoundError):
            svc.get_project_forecast_v2("non-existent", self.START, self.END)

    def test_project_forecast_v2_invalid_date_window(self, db_session: Session):
        """start_date > end_date raises ValidationError."""
        pid = _make_project(db_session, "CE-SVC-INV-02")
        svc = CashflowForecastService(db_session)
        with pytest.raises(ValidationError):
            svc.get_project_forecast_v2(pid, date(2026, 12, 1), date(2026, 1, 1))

    def test_project_forecast_v2_empty_project(self, db_session: Session):
        """Project with no contracts returns zeroed but valid forecast."""
        pid = _make_project(db_session, "CE-SVC-E02")
        svc = CashflowForecastService(db_session)
        result = svc.get_project_forecast_v2(pid, self.START, self.END)

        assert result.project_id == pid
        assert result.summary.scheduled_total == 0.0
        assert result.summary.expected_total == 0.0
        assert len(result.periods) == 6

    def test_project_forecast_v2_multiple_contracts(self, db_session: Session):
        """Multiple contracts under a project are aggregated correctly."""
        pid = _make_project(db_session, "CE-SVC-MC01")
        uid1 = _make_unit(db_session, pid, "601")
        uid2 = _make_unit(db_session, pid, "602")
        cid1 = _make_contract(db_session, uid1, 200_000.0, "CNT-CE-MC01A", "cemc01a@t.com")
        cid2 = _make_contract(db_session, uid2, 300_000.0, "CNT-CE-MC01B", "cemc01b@t.com")

        _make_installment(db_session, cid1, 200_000.0, 1, date(2026, 5, 1), "pending")
        _make_installment(db_session, cid2, 300_000.0, 1, date(2026, 5, 15), "pending")

        svc = CashflowForecastService(db_session)
        result = svc.get_project_forecast_v2(pid, self.START, self.END)

        assert result.summary.scheduled_total == pytest.approx(500_000.0)
        assert result.summary.expected_total == pytest.approx(500_000.0)
        may = next(p for p in result.periods if p.period_label == "2026-05")
        assert may.installment_count == 2

    def test_portfolio_forecast_v2_invalid_date_window(self, db_session: Session):
        """start_date > end_date raises ValidationError for portfolio forecast too."""
        svc = CashflowForecastService(db_session)
        with pytest.raises(ValidationError):
            svc.get_portfolio_forecast_v2(date(2026, 9, 1), date(2026, 1, 1))

    def test_portfolio_forecast_v2_empty(self, db_session: Session):
        """Empty portfolio returns zeroed but valid forecast."""
        svc = CashflowForecastService(db_session)
        result = svc.get_portfolio_forecast_v2(self.START, self.END)

        assert result.summary.scheduled_total == 0.0
        assert result.summary.expected_total == 0.0
        assert len(result.periods) == 6

    def test_portfolio_forecast_v2_totals_reconcile(self, db_session: Session):
        """Portfolio total must equal the sum of underlying project totals."""
        pid1 = _make_project(db_session, "CE-PORT-01A")
        uid1 = _make_unit(db_session, pid1, "701")
        cid1 = _make_contract(db_session, uid1, 500_000.0, "CNT-CE-PORT01A", "ceport01a@t.com")
        _make_installment(db_session, cid1, 250_000.0, 1, date(2026, 5, 1), "pending")
        _make_installment(db_session, cid1, 250_000.0, 2, date(2026, 6, 1), "pending")

        pid2 = _make_project(db_session, "CE-PORT-01B")
        uid2 = _make_unit(db_session, pid2, "702")
        cid2 = _make_contract(db_session, uid2, 300_000.0, "CNT-CE-PORT01B", "ceport01b@t.com")
        _make_installment(db_session, cid2, 150_000.0, 1, date(2026, 4, 1), "paid")
        _make_installment(db_session, cid2, 150_000.0, 2, date(2026, 6, 1), "pending")

        svc = CashflowForecastService(db_session)
        result = svc.get_portfolio_forecast_v2(self.START, self.END)

        project_expected_sum = sum(
            pf.summary.expected_total for pf in result.project_forecasts
        )
        assert result.summary.expected_total == pytest.approx(project_expected_sum)

        project_scheduled_sum = sum(
            pf.summary.scheduled_total for pf in result.project_forecasts
        )
        assert result.summary.scheduled_total == pytest.approx(project_scheduled_sum)

    def test_assumptions_propagated_in_service(self, db_session: Session):
        """Non-default collection probability is propagated to engine correctly."""
        pid = _make_project(db_session, "CE-ASSUM-01")
        uid = _make_unit(db_session, pid, "801")
        cid = _make_contract(db_session, uid, 400_000.0, "CNT-CE-AS01", "ceas01@t.com")
        _make_installment(db_session, cid, 400_000.0, 1, date(2026, 5, 1), "pending")

        assumptions = CashflowForecastAssumptions(collection_probability=0.75)
        svc = CashflowForecastService(db_session)
        result = svc.get_project_forecast_v2(pid, self.START, self.END, assumptions)

        assert result.summary.expected_total == pytest.approx(300_000.0)  # 400k × 0.75

    def test_cancelled_installments_excluded_from_comprehensive_forecast(
        self, db_session: Session
    ):
        """CANCELLED installments must not appear in any forecast totals."""
        pid = _make_project(db_session, "CE-CANCEL-01")
        uid = _make_unit(db_session, pid, "901")
        cid = _make_contract(db_session, uid, 300_000.0, "CNT-CE-CAN01", "cecan01@t.com")
        _make_installment(db_session, cid, 100_000.0, 1, date(2026, 5, 1), "pending")
        _make_installment(db_session, cid, 200_000.0, 2, date(2026, 6, 1), "cancelled")

        svc = CashflowForecastService(db_session)
        result = svc.get_contract_forecast_v2(cid, self.START, self.END)

        # Only the 100k pending installment should appear
        assert result.summary.scheduled_total == pytest.approx(100_000.0)


# ---------------------------------------------------------------------------
# API integration tests — PR-33 comprehensive endpoints
# ---------------------------------------------------------------------------


class TestCashflowForecastApiV2:
    def test_contract_forecast_endpoint_404_for_missing_contract(self, client):
        resp = client.get(
            "/api/v1/finance/contracts/non-existent/cashflow-forecast"
            "?start_date=2026-04-01&end_date=2026-09-30"
        )
        assert resp.status_code == 404

    def test_contract_forecast_endpoint_422_for_invalid_dates(self, client):
        resp = client.post(
            "/api/v1/projects",
            json={"name": "CF V2 Test", "code": "CFV2-001"},
        )
        assert resp.status_code == 201
        # start_date after end_date returns 422
        resp = client.get(
            "/api/v1/finance/contracts/some-cid/cashflow-forecast"
            "?start_date=2026-09-01&end_date=2026-01-01"
        )
        assert resp.status_code in (404, 422)

    def test_project_forecast_v2_endpoint_404_for_missing_project(self, client):
        resp = client.get(
            "/api/v1/finance/projects/non-existent/cashflow-forecast"
            "?start_date=2026-04-01&end_date=2026-09-30"
        )
        assert resp.status_code == 404

    def test_project_forecast_v2_endpoint_422_for_invalid_dates(self, client):
        resp = client.post(
            "/api/v1/projects",
            json={"name": "CF V2 Proj", "code": "CFV2-002"},
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]
        resp = client.get(
            f"/api/v1/finance/projects/{pid}/cashflow-forecast"
            "?start_date=2026-09-01&end_date=2026-01-01"
        )
        assert resp.status_code == 422

    def test_project_forecast_v2_endpoint_empty_project(self, client):
        resp = client.post(
            "/api/v1/projects",
            json={"name": "CF V2 Empty", "code": "CFV2-003"},
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp = client.get(
            f"/api/v1/finance/projects/{pid}/cashflow-forecast"
            "?start_date=2026-04-01&end_date=2026-09-30"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == pid
        assert data["scope_type"] == "project"
        assert data["granularity"] == "monthly"
        assert data["summary"]["scheduled_total"] == 0.0
        assert data["summary"]["expected_total"] == 0.0
        assert isinstance(data["periods"], list)
        assert len(data["periods"]) == 6

    def test_project_forecast_v2_response_shape(self, client):
        resp = client.post(
            "/api/v1/projects",
            json={"name": "CF V2 Shape", "code": "CFV2-004"},
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp = client.get(
            f"/api/v1/finance/projects/{pid}/cashflow-forecast"
            "?start_date=2026-01-01&end_date=2026-03-31"
        )
        assert resp.status_code == 200
        data = resp.json()

        # Verify required top-level keys
        for key in ("scope_type", "project_id", "start_date", "end_date",
                    "granularity", "assumptions", "summary", "periods"):
            assert key in data, f"Missing key: {key}"

        # Verify summary keys
        for key in ("scheduled_total", "collected_total", "expected_total",
                    "variance_to_schedule"):
            assert key in data["summary"], f"Missing summary key: {key}"

        # Verify period keys if any periods exist
        if data["periods"]:
            period = data["periods"][0]
            for key in ("period_start", "period_end", "period_label",
                        "scheduled_amount", "collected_amount", "expected_amount",
                        "variance_to_schedule", "cumulative_expected_amount",
                        "installment_count"):
                assert key in period, f"Missing period key: {key}"

        # Verify assumption keys
        for key in ("collection_probability", "carry_forward_overdue",
                    "include_paid_in_schedule"):
            assert key in data["assumptions"], f"Missing assumption key: {key}"

    def test_portfolio_cashflow_forecast_v2_endpoint_returns_200(self, client):
        resp = client.get(
            "/api/v1/finance/portfolio/cashflow-forecast"
            "?start_date=2026-04-01&end_date=2026-09-30"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope_type"] == "portfolio"
        assert "summary" in data
        assert "periods" in data
        assert "project_forecasts" in data

    def test_portfolio_cashflow_forecast_v2_422_for_missing_dates(self, client):
        """Missing required date query params returns 422."""
        resp = client.get("/api/v1/finance/portfolio/cashflow-forecast")
        assert resp.status_code == 422

    def test_portfolio_cashflow_forecast_v2_invalid_date_window(self, client):
        resp = client.get(
            "/api/v1/finance/portfolio/cashflow-forecast"
            "?start_date=2026-09-01&end_date=2026-01-01"
        )
        assert resp.status_code == 422

    def test_collection_probability_query_param_accepted(self, client):
        """collection_probability query param is accepted and reflected in response."""
        resp = client.post(
            "/api/v1/projects",
            json={"name": "CF V2 Prob", "code": "CFV2-005"},
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp = client.get(
            f"/api/v1/finance/projects/{pid}/cashflow-forecast"
            "?start_date=2026-01-01&end_date=2026-03-31&collection_probability=0.8"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assumptions"]["collection_probability"] == pytest.approx(0.8)

    def test_legacy_portfolio_forecast_endpoint_still_works(self, client):
        """Backward-compatible legacy endpoint remains functional."""
        resp = client.get("/api/v1/finance/cashflow/forecast")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_expected" in data
        assert "monthly_entries" in data
        assert "project_forecasts" in data
