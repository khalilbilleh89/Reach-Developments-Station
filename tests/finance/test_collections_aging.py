"""
Tests for the collections aging engine and CollectionsAgingService.

Validates aging logic covering:
  - installment not yet due → CURRENT
  - installment due today → CURRENT (0 days overdue)
  - installment 5 days overdue → 1-30 bucket
  - installment 45 days overdue → 31-60 bucket
  - installment 70 days overdue → 61-90 bucket
  - installment 120 days overdue → 90+ bucket
  - paid installments excluded from aging
  - cancelled installments excluded from aging
  - contracts without schedules handled gracefully
  - project/portfolio aggregation
  - 404 handling for missing contracts and projects
"""

import pytest
from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.collections.aging_engine import (
    ALL_BUCKETS,
    BUCKET_1_30,
    BUCKET_31_60,
    BUCKET_61_90,
    BUCKET_90_PLUS,
    BUCKET_CURRENT,
    calculate_receivable_age,
    classify_receivable_bucket,
)
from app.modules.finance.service import CollectionsAgingService


# ---------------------------------------------------------------------------
# Helpers (shared with revenue recognition tests)
# ---------------------------------------------------------------------------

_aging_seq: dict[str, int] = {}


def _make_project(db_session: Session, code: str) -> str:
    from app.modules.projects.models import Project

    project = Project(name=f"Aging Project {code}", code=code)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


def _make_unit(db_session: Session, project_id: str, unit_number: str) -> str:
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _aging_seq.get(project_id, 0) + 1
    _aging_seq[project_id] = seq

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
# Unit tests — pure aging engine (no DB)
# ---------------------------------------------------------------------------


class TestCalculateReceivableAge:
    """Tests for the pure calculate_receivable_age function."""

    def test_future_due_date_returns_negative(self):
        ref = date(2026, 3, 1)
        due = date(2026, 4, 1)
        assert calculate_receivable_age(due, ref) < 0

    def test_due_today_returns_zero(self):
        today = date(2026, 3, 1)
        assert calculate_receivable_age(today, today) == 0

    def test_5_days_overdue(self):
        ref = date(2026, 3, 10)
        due = date(2026, 3, 5)
        assert calculate_receivable_age(due, ref) == 5

    def test_45_days_overdue(self):
        ref = date(2026, 3, 10)
        due = ref - timedelta(days=45)
        assert calculate_receivable_age(due, ref) == 45

    def test_70_days_overdue(self):
        ref = date(2026, 3, 10)
        due = ref - timedelta(days=70)
        assert calculate_receivable_age(due, ref) == 70

    def test_120_days_overdue(self):
        ref = date(2026, 3, 10)
        due = ref - timedelta(days=120)
        assert calculate_receivable_age(due, ref) == 120


class TestClassifyReceivableBucket:
    """Tests for the pure classify_receivable_bucket function."""

    def test_not_yet_due_is_current(self):
        assert classify_receivable_bucket(-5) == BUCKET_CURRENT

    def test_due_today_is_current(self):
        assert classify_receivable_bucket(0) == BUCKET_CURRENT

    def test_1_day_is_1_30(self):
        assert classify_receivable_bucket(1) == BUCKET_1_30

    def test_30_days_is_1_30(self):
        assert classify_receivable_bucket(30) == BUCKET_1_30

    def test_31_days_is_31_60(self):
        assert classify_receivable_bucket(31) == BUCKET_31_60

    def test_60_days_is_31_60(self):
        assert classify_receivable_bucket(60) == BUCKET_31_60

    def test_61_days_is_61_90(self):
        assert classify_receivable_bucket(61) == BUCKET_61_90

    def test_90_days_is_61_90(self):
        assert classify_receivable_bucket(90) == BUCKET_61_90

    def test_91_days_is_90_plus(self):
        assert classify_receivable_bucket(91) == BUCKET_90_PLUS

    def test_120_days_is_90_plus(self):
        assert classify_receivable_bucket(120) == BUCKET_90_PLUS

    def test_all_buckets_covered(self):
        """Verify all canonical bucket labels appear in the result set."""
        sample_days = [-10, 0, 5, 45, 70, 120]
        results = {classify_receivable_bucket(d) for d in sample_days}
        assert results == set(ALL_BUCKETS)


# ---------------------------------------------------------------------------
# Integration tests — CollectionsAgingService with SQLite DB
# ---------------------------------------------------------------------------


class TestCollectionsAgingService:
    def test_get_contract_aging_no_installments(self, db_session: Session):
        """Contract with no payment schedule returns empty aging."""
        pid = _make_project(db_session, "AGE-SVC-01")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-AGE-01", "age01@test.com")

        svc = CollectionsAgingService(db_session)
        result = svc.get_contract_aging(cid)

        assert result.contract_id == cid
        assert result.contract_total == pytest.approx(100_000.0)
        assert result.paid_amount == 0.0
        assert result.outstanding_amount == 0.0
        assert all(b.amount == 0.0 for b in result.aging_buckets)
        assert all(b.installment_count == 0 for b in result.aging_buckets)

    def test_get_contract_aging_paid_excluded(self, db_session: Session):
        """Paid installments must not appear in aging buckets."""
        pid = _make_project(db_session, "AGE-SVC-02")
        uid = _make_unit(db_session, pid, "102")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-AGE-02", "age02@test.com")

        today = date.today()
        overdue_date = today - timedelta(days=10)
        _make_installment(db_session, cid, 60_000.0, 1, overdue_date, status="paid")
        _make_installment(db_session, cid, 40_000.0, 2, overdue_date, status="pending")

        svc = CollectionsAgingService(db_session)
        result = svc.get_contract_aging(cid)

        # Paid installment (60k) excluded; only the 40k pending appears
        assert result.paid_amount == pytest.approx(60_000.0)
        assert result.outstanding_amount == pytest.approx(40_000.0)

        bucket_map = {b.bucket: b for b in result.aging_buckets}
        assert bucket_map[BUCKET_1_30].amount == pytest.approx(40_000.0)
        assert bucket_map[BUCKET_1_30].installment_count == 1

    def test_get_contract_aging_current_bucket(self, db_session: Session):
        """Installment not yet due is classified as CURRENT."""
        pid = _make_project(db_session, "AGE-SVC-03")
        uid = _make_unit(db_session, pid, "103")
        cid = _make_contract(db_session, uid, 50_000.0, "CNT-AGE-03", "age03@test.com")

        future_date = date.today() + timedelta(days=30)
        _make_installment(db_session, cid, 50_000.0, 1, future_date, status="pending")

        svc = CollectionsAgingService(db_session)
        result = svc.get_contract_aging(cid)

        bucket_map = {b.bucket: b for b in result.aging_buckets}
        assert bucket_map[BUCKET_CURRENT].amount == pytest.approx(50_000.0)
        assert bucket_map[BUCKET_CURRENT].installment_count == 1
        assert result.outstanding_amount == pytest.approx(50_000.0)

    def test_get_contract_aging_overdue_buckets(self, db_session: Session):
        """Each overdue bucket is correctly populated."""
        pid = _make_project(db_session, "AGE-SVC-04")
        uid = _make_unit(db_session, pid, "104")
        cid = _make_contract(db_session, uid, 400_000.0, "CNT-AGE-04", "age04@test.com")

        today = date.today()
        # 5 days overdue → 1-30
        _make_installment(db_session, cid, 10_000.0, 1, today - timedelta(days=5))
        # 45 days overdue → 31-60
        _make_installment(db_session, cid, 20_000.0, 2, today - timedelta(days=45))
        # 70 days overdue → 61-90
        _make_installment(db_session, cid, 30_000.0, 3, today - timedelta(days=70))
        # 120 days overdue → 90+
        _make_installment(db_session, cid, 40_000.0, 4, today - timedelta(days=120))

        svc = CollectionsAgingService(db_session)
        result = svc.get_contract_aging(cid)

        bucket_map = {b.bucket: b for b in result.aging_buckets}
        assert bucket_map[BUCKET_1_30].amount == pytest.approx(10_000.0)
        assert bucket_map[BUCKET_31_60].amount == pytest.approx(20_000.0)
        assert bucket_map[BUCKET_61_90].amount == pytest.approx(30_000.0)
        assert bucket_map[BUCKET_90_PLUS].amount == pytest.approx(40_000.0)
        assert result.outstanding_amount == pytest.approx(100_000.0)

    def test_get_contract_aging_not_found(self, db_session: Session):
        """Missing contract raises HTTP 404."""
        svc = CollectionsAgingService(db_session)
        with pytest.raises(HTTPException) as exc_info:
            svc.get_contract_aging("non-existent-id")
        assert exc_info.value.status_code == 404

    def test_get_project_aging_no_contracts(self, db_session: Session):
        """Project with no contracts returns zero totals."""
        pid = _make_project(db_session, "AGE-SVC-05")

        svc = CollectionsAgingService(db_session)
        result = svc.get_project_aging(pid)

        assert result.project_id == pid
        assert result.total_outstanding == 0.0
        assert result.installment_count == 0
        assert all(b.amount == 0.0 for b in result.aging_buckets)

    def test_get_project_aging_aggregation(self, db_session: Session):
        """Project aging aggregates across multiple contracts."""
        pid = _make_project(db_session, "AGE-SVC-06")

        uid1 = _make_unit(db_session, pid, "201")
        cid1 = _make_contract(
            db_session, uid1, 100_000.0, "CNT-AGE-06A", "age06a@test.com"
        )
        today = date.today()
        _make_installment(db_session, cid1, 10_000.0, 1, today - timedelta(days=5))

        uid2 = _make_unit(db_session, pid, "202")
        cid2 = _make_contract(
            db_session, uid2, 200_000.0, "CNT-AGE-06B", "age06b@test.com"
        )
        _make_installment(db_session, cid2, 20_000.0, 1, today - timedelta(days=5))
        # Paid installment must not appear
        _make_installment(
            db_session, cid2, 50_000.0, 2, today - timedelta(days=50), status="paid"
        )

        svc = CollectionsAgingService(db_session)
        result = svc.get_project_aging(pid)

        assert result.project_id == pid
        assert result.total_outstanding == pytest.approx(30_000.0)
        assert result.installment_count == 2
        bucket_map = {b.bucket: b for b in result.aging_buckets}
        assert bucket_map[BUCKET_1_30].amount == pytest.approx(30_000.0)
        assert bucket_map[BUCKET_1_30].installment_count == 2

    def test_get_project_aging_not_found(self, db_session: Session):
        """Missing project raises HTTP 404."""
        svc = CollectionsAgingService(db_session)
        with pytest.raises(HTTPException) as exc_info:
            svc.get_project_aging("non-existent-project")
        assert exc_info.value.status_code == 404

    def test_get_portfolio_aging_non_negative(self, db_session: Session):
        """Portfolio aging totals are non-negative."""
        pid = _make_project(db_session, "AGE-SVC-07")
        uid = _make_unit(db_session, pid, "301")
        cid = _make_contract(db_session, uid, 80_000.0, "CNT-AGE-07", "age07@test.com")
        today = date.today()
        _make_installment(db_session, cid, 20_000.0, 1, today - timedelta(days=15))
        _make_installment(db_session, cid, 30_000.0, 2, today + timedelta(days=30))

        svc = CollectionsAgingService(db_session)
        result = svc.get_portfolio_aging()

        assert result.total_outstanding >= 0
        assert result.installment_count >= 0
        assert result.project_count >= 0
        assert all(b.amount >= 0 for b in result.aging_buckets)

    def test_get_portfolio_aging_bucket_totals_sum(self, db_session: Session):
        """Sum of all bucket amounts equals total_outstanding."""
        pid = _make_project(db_session, "AGE-SVC-08")
        uid = _make_unit(db_session, pid, "401")
        cid = _make_contract(db_session, uid, 200_000.0, "CNT-AGE-08", "age08@test.com")
        today = date.today()
        _make_installment(db_session, cid, 25_000.0, 1, today - timedelta(days=10))
        _make_installment(db_session, cid, 35_000.0, 2, today - timedelta(days=50))
        _make_installment(db_session, cid, 45_000.0, 3, today + timedelta(days=20))

        svc = CollectionsAgingService(db_session)
        result = svc.get_portfolio_aging()

        bucket_total = round(sum(b.amount for b in result.aging_buckets), 2)
        assert bucket_total == pytest.approx(result.total_outstanding)

    def test_get_contract_aging_response_has_all_buckets(self, db_session: Session):
        """ContractAgingResponse always returns all five bucket entries."""
        pid = _make_project(db_session, "AGE-SVC-09")
        uid = _make_unit(db_session, pid, "501")
        cid = _make_contract(db_session, uid, 10_000.0, "CNT-AGE-09", "age09@test.com")

        svc = CollectionsAgingService(db_session)
        result = svc.get_contract_aging(cid)

        bucket_labels = [b.bucket for b in result.aging_buckets]
        assert set(bucket_labels) == set(ALL_BUCKETS)
        assert len(result.aging_buckets) == len(ALL_BUCKETS)

    def test_cancelled_installment_excluded_from_contract_aging(
        self, db_session: Session
    ):
        """Cancelled installments must not appear in contract aging buckets."""
        pid = _make_project(db_session, "AGE-SVC-10")
        uid = _make_unit(db_session, pid, "601")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-AGE-10", "age10@test.com")

        today = date.today()
        overdue_date = today - timedelta(days=10)
        _make_installment(
            db_session, cid, 40_000.0, 1, overdue_date, status="cancelled"
        )
        _make_installment(db_session, cid, 60_000.0, 2, overdue_date, status="pending")

        svc = CollectionsAgingService(db_session)
        result = svc.get_contract_aging(cid)

        # Only the 60k pending installment should appear; the 40k cancelled is excluded.
        assert result.outstanding_amount == pytest.approx(60_000.0)
        bucket_map = {b.bucket: b for b in result.aging_buckets}
        assert bucket_map[BUCKET_1_30].amount == pytest.approx(60_000.0)
        assert bucket_map[BUCKET_1_30].installment_count == 1

    def test_cancelled_installment_excluded_from_project_aging(
        self, db_session: Session
    ):
        """Cancelled installments must not appear in project aging buckets."""
        pid = _make_project(db_session, "AGE-SVC-11")
        uid = _make_unit(db_session, pid, "701")
        cid = _make_contract(db_session, uid, 150_000.0, "CNT-AGE-11", "age11@test.com")

        today = date.today()
        overdue_date = today - timedelta(days=20)
        _make_installment(
            db_session, cid, 50_000.0, 1, overdue_date, status="cancelled"
        )
        _make_installment(db_session, cid, 100_000.0, 2, overdue_date, status="overdue")

        svc = CollectionsAgingService(db_session)
        result = svc.get_project_aging(pid)

        # Only the 100k overdue installment should contribute.
        assert result.total_outstanding == pytest.approx(100_000.0)
        assert result.installment_count == 1
        bucket_map = {b.bucket: b for b in result.aging_buckets}
        assert bucket_map[BUCKET_1_30].amount == pytest.approx(100_000.0)

    def test_cancelled_installment_excluded_from_portfolio_aging(
        self, db_session: Session
    ):
        """Cancelled installments must not appear in portfolio aging buckets."""
        pid = _make_project(db_session, "AGE-SVC-12")
        uid = _make_unit(db_session, pid, "801")
        cid = _make_contract(db_session, uid, 200_000.0, "CNT-AGE-12", "age12@test.com")

        today = date.today()
        overdue_date = today - timedelta(days=5)
        _make_installment(
            db_session, cid, 70_000.0, 1, overdue_date, status="cancelled"
        )
        _make_installment(db_session, cid, 80_000.0, 2, overdue_date, status="pending")

        svc = CollectionsAgingService(db_session)
        result = svc.get_portfolio_aging()

        # Portfolio totals must include only collectible (pending/overdue) installments.
        bucket_total = round(sum(b.amount for b in result.aging_buckets), 2)
        assert bucket_total == pytest.approx(result.total_outstanding)
        # The 80k pending should be in the 1-30 bucket; the 70k cancelled excluded.
        bucket_map = {b.bucket: b for b in result.aging_buckets}
        assert bucket_map[BUCKET_1_30].amount == pytest.approx(80_000.0)
        assert bucket_map[BUCKET_1_30].installment_count == 1
        assert result.total_outstanding == pytest.approx(80_000.0)
        assert result.project_count == 1
