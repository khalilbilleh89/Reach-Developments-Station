"""
Tests for the revenue recognition engine and service layer.

Validates recognition logic covering:
  - contract with zero payments
  - partial payment recognition
  - full payment recognition
  - overpayment edge case (clamped to contract total)
  - project revenue aggregation across multiple contracts
  - portfolio overview aggregation
  - 404 handling for missing contracts and projects
"""

import pytest
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.finance.revenue_recognition import (
    ContractRevenueData,
    calculate_contract_revenue_recognition,
)
from app.modules.finance.service import RevenueRecognitionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_rr_seq: dict[str, int] = {}


def _make_project(db_session: Session, code: str) -> str:
    from app.modules.projects.models import Project

    project = Project(name=f"Rev Rec Project {code}", code=code)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


def _make_unit(db_session: Session, project_id: str, unit_number: str) -> str:
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _rr_seq.get(project_id, 0) + 1
    _rr_seq[project_id] = seq

    phase = Phase(project_id=project_id, name=f"Phase {seq}", sequence=seq)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"BLK-{unit_number}")
    db_session.add(building)
    db_session.flush()

    floor = Floor(
        building_id=building.id, name="Floor 1", code="FL-01", sequence_number=1
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
    status: str = "pending",
) -> None:
    from app.modules.sales.models import ContractPaymentSchedule

    line = ContractPaymentSchedule(
        contract_id=contract_id,
        installment_number=installment_number,
        due_date=date(2030, 1, 1),
        amount=amount,
        status=status,
    )
    db_session.add(line)
    db_session.commit()


# ---------------------------------------------------------------------------
# Unit tests — pure calculation engine (no DB)
# ---------------------------------------------------------------------------


class TestCalculateContractRevenueRecognition:
    """Tests for the pure calculation function; no DB access."""

    def test_zero_payments(self):
        data = ContractRevenueData(
            contract_id="c-001", contract_total=100_000.0, paid_amount=0.0
        )
        result = calculate_contract_revenue_recognition(data)
        assert result.contract_id == "c-001"
        assert result.contract_total == 100_000.0
        assert result.recognized_revenue == 0.0
        assert result.deferred_revenue == 100_000.0
        assert result.recognition_percentage == 0.0

    def test_partial_payment(self):
        data = ContractRevenueData(
            contract_id="c-002", contract_total=100_000.0, paid_amount=30_000.0
        )
        result = calculate_contract_revenue_recognition(data)
        assert result.recognized_revenue == 30_000.0
        assert result.deferred_revenue == 70_000.0
        assert result.recognition_percentage == pytest.approx(30.0)

    def test_full_payment(self):
        data = ContractRevenueData(
            contract_id="c-003", contract_total=100_000.0, paid_amount=100_000.0
        )
        result = calculate_contract_revenue_recognition(data)
        assert result.recognized_revenue == 100_000.0
        assert result.deferred_revenue == 0.0
        assert result.recognition_percentage == pytest.approx(100.0)

    def test_overpayment_clamped(self):
        """Recognized revenue must not exceed contract total."""
        data = ContractRevenueData(
            contract_id="c-004", contract_total=100_000.0, paid_amount=110_000.0
        )
        result = calculate_contract_revenue_recognition(data)
        assert result.recognized_revenue == 100_000.0
        assert result.deferred_revenue == 0.0
        assert result.recognition_percentage == pytest.approx(100.0)

    def test_zero_contract_total(self):
        """Zero-value contracts return 0.0 recognition percentage (no division)."""
        data = ContractRevenueData(
            contract_id="c-005", contract_total=0.0, paid_amount=0.0
        )
        result = calculate_contract_revenue_recognition(data)
        assert result.recognized_revenue == 0.0
        assert result.deferred_revenue == 0.0
        assert result.recognition_percentage == 0.0

    def test_recognized_plus_deferred_equals_total(self):
        """Invariant: recognized + deferred == contract_total."""
        for paid in [0, 25_000, 50_000, 75_000, 100_000, 120_000]:
            data = ContractRevenueData(
                contract_id="c-inv",
                contract_total=100_000.0,
                paid_amount=float(paid),
            )
            result = calculate_contract_revenue_recognition(data)
            assert (
                pytest.approx(result.recognized_revenue + result.deferred_revenue)
                == result.contract_total
            )


# ---------------------------------------------------------------------------
# Integration tests — RevenueRecognitionService with SQLite DB
# ---------------------------------------------------------------------------


class TestRevenueRecognitionService:
    def test_get_contract_revenue_no_payments(self, db_session: Session):
        """Contract with zero paid installments: fully deferred."""
        pid = _make_project(db_session, "RR-SVC-01")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(
            db_session, uid, 500_000.0, "CNT-RR-01", "rr01@test.com"
        )
        # Add a pending installment (not paid)
        _make_installment(db_session, cid, 500_000.0, 1, status="pending")

        svc = RevenueRecognitionService(db_session)
        result = svc.get_contract_revenue(cid)

        assert result.contract_total == pytest.approx(500_000.0)
        assert result.recognized_revenue == 0.0
        assert result.deferred_revenue == pytest.approx(500_000.0)
        assert result.recognition_percentage == 0.0

    def test_get_contract_revenue_partial_payment(self, db_session: Session):
        """Contract with one of two installments paid."""
        pid = _make_project(db_session, "RR-SVC-02")
        uid = _make_unit(db_session, pid, "102")
        cid = _make_contract(
            db_session, uid, 100_000.0, "CNT-RR-02", "rr02@test.com"
        )
        _make_installment(db_session, cid, 30_000.0, 1, status="paid")
        _make_installment(db_session, cid, 70_000.0, 2, status="pending")

        svc = RevenueRecognitionService(db_session)
        result = svc.get_contract_revenue(cid)

        assert result.recognized_revenue == pytest.approx(30_000.0)
        assert result.deferred_revenue == pytest.approx(70_000.0)
        assert result.recognition_percentage == pytest.approx(30.0)

    def test_get_contract_revenue_full_payment(self, db_session: Session):
        """All installments paid: fully recognized."""
        pid = _make_project(db_session, "RR-SVC-03")
        uid = _make_unit(db_session, pid, "103")
        cid = _make_contract(
            db_session, uid, 200_000.0, "CNT-RR-03", "rr03@test.com"
        )
        _make_installment(db_session, cid, 100_000.0, 1, status="paid")
        _make_installment(db_session, cid, 100_000.0, 2, status="paid")

        svc = RevenueRecognitionService(db_session)
        result = svc.get_contract_revenue(cid)

        assert result.recognized_revenue == pytest.approx(200_000.0)
        assert result.deferred_revenue == 0.0
        assert result.recognition_percentage == pytest.approx(100.0)

    def test_get_contract_revenue_not_found(self, db_session: Session):
        """Missing contract raises HTTP 404."""
        svc = RevenueRecognitionService(db_session)
        with pytest.raises(HTTPException) as exc_info:
            svc.get_contract_revenue("non-existent-id")
        assert exc_info.value.status_code == 404

    def test_get_project_revenue_aggregation(self, db_session: Session):
        """Project with multiple contracts is aggregated correctly."""
        pid = _make_project(db_session, "RR-SVC-04")

        uid1 = _make_unit(db_session, pid, "201")
        cid1 = _make_contract(db_session, uid1, 100_000.0, "CNT-RR-04A", "rr04a@test.com")
        _make_installment(db_session, cid1, 50_000.0, 1, status="paid")
        _make_installment(db_session, cid1, 50_000.0, 2, status="pending")

        uid2 = _make_unit(db_session, pid, "202")
        cid2 = _make_contract(db_session, uid2, 200_000.0, "CNT-RR-04B", "rr04b@test.com")
        _make_installment(db_session, cid2, 200_000.0, 1, status="paid")

        svc = RevenueRecognitionService(db_session)
        result = svc.get_project_revenue(pid)

        assert result.project_id == pid
        assert result.contract_count == 2
        assert result.total_contract_value == pytest.approx(300_000.0)
        assert result.total_recognized_revenue == pytest.approx(250_000.0)
        assert result.total_deferred_revenue == pytest.approx(50_000.0)
        expected_pct = round(250_000 / 300_000 * 100, 4)
        assert result.overall_recognition_percentage == pytest.approx(expected_pct)

    def test_get_project_revenue_no_contracts(self, db_session: Session):
        """Project with no contracts returns zero totals."""
        pid = _make_project(db_session, "RR-SVC-05")

        svc = RevenueRecognitionService(db_session)
        result = svc.get_project_revenue(pid)

        assert result.contract_count == 0
        assert result.total_contract_value == 0.0
        assert result.total_recognized_revenue == 0.0
        assert result.total_deferred_revenue == 0.0
        assert result.overall_recognition_percentage == 0.0
        assert result.contracts == []

    def test_get_project_revenue_not_found(self, db_session: Session):
        """Missing project raises HTTP 404."""
        svc = RevenueRecognitionService(db_session)
        with pytest.raises(HTTPException) as exc_info:
            svc.get_project_revenue("non-existent-project")
        assert exc_info.value.status_code == 404

    def test_recognized_plus_deferred_equals_total_invariant(self, db_session: Session):
        """recognized + deferred == contract_total for each contract in project."""
        pid = _make_project(db_session, "RR-SVC-06")

        uid = _make_unit(db_session, pid, "301")
        cid = _make_contract(db_session, uid, 75_000.0, "CNT-RR-06", "rr06@test.com")
        _make_installment(db_session, cid, 25_000.0, 1, status="paid")
        _make_installment(db_session, cid, 25_000.0, 2, status="pending")
        _make_installment(db_session, cid, 25_000.0, 3, status="pending")

        svc = RevenueRecognitionService(db_session)
        proj_result = svc.get_project_revenue(pid)

        for c in proj_result.contracts:
            assert pytest.approx(c.recognized_revenue + c.deferred_revenue) == c.contract_total

    def test_get_total_recognized_revenue_overview(self, db_session: Session):
        """Portfolio overview aggregates across contracts."""
        pid = _make_project(db_session, "RR-SVC-07")
        uid = _make_unit(db_session, pid, "401")
        cid = _make_contract(db_session, uid, 60_000.0, "CNT-RR-07", "rr07@test.com")
        _make_installment(db_session, cid, 20_000.0, 1, status="paid")
        _make_installment(db_session, cid, 40_000.0, 2, status="pending")

        svc = RevenueRecognitionService(db_session)
        result = svc.get_total_recognized_revenue()

        # The overview includes all contracts in the database, so we just
        # verify the invariant and non-negative constraint.
        assert result.total_contract_value >= 0
        assert result.total_recognized_revenue >= 0
        assert result.total_deferred_revenue >= 0
        assert (
            pytest.approx(
                result.total_recognized_revenue + result.total_deferred_revenue
            )
            == result.total_contract_value
        )
        assert 0.0 <= result.overall_recognition_percentage <= 100.0
