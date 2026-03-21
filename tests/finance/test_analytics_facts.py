"""
Tests for the analytics fact layer service and API endpoint.

Validates:
  - Revenue fact generation (monthly grouping, project association)
  - Collections fact generation (payments aggregated by month)
  - Receivable snapshot generation (bucket totals correct)
  - Analytics rebuild endpoint (returns success, facts created)

Edge cases:
  - Empty portfolio (no contracts, no installments)
  - Projects with no paid installments
  - Multiple projects / units in the same month
"""

import pytest
from datetime import date, datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.modules.finance.analytics_service import AnalyticsService
from app.modules.finance.models import (
    FactCollections,
    FactReceivablesSnapshot,
    FactRevenue,
)
from app.modules.finance.schemas import AnalyticsRebuildResponse


# ---------------------------------------------------------------------------
# Helper functions — reused across test classes
# ---------------------------------------------------------------------------

_af_seq: dict[str, int] = {}


def _make_project(db_session: Session, code: str) -> str:
    from app.modules.projects.models import Project

    project = Project(name=f"Analytics Fact Project {code}", code=code)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


def _make_unit(db_session: Session, project_id: str, unit_number: str) -> str:
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _af_seq.get(project_id, 0) + 1
    _af_seq[project_id] = seq

    phase = Phase(project_id=project_id, name=f"Phase {seq}", sequence=seq)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"AF-BLK-{unit_number}")
    db_session.add(building)
    db_session.flush()

    floor = Floor(
        building_id=building.id,
        name="Floor 1",
        code=f"AF-FL-{unit_number}",
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
    paid_at: datetime | None = None,
) -> str:
    from app.modules.sales.models import ContractPaymentSchedule

    line = ContractPaymentSchedule(
        contract_id=contract_id,
        installment_number=installment_number,
        due_date=due_date,
        amount=amount,
        status=status,
        paid_at=paid_at,
    )
    db_session.add(line)
    db_session.commit()
    db_session.refresh(line)
    return line.id


# ---------------------------------------------------------------------------
# Test 1 — Revenue fact generation
# ---------------------------------------------------------------------------


class TestBuildRevenueFact:
    """Tests for AnalyticsService.build_revenue_fact()."""

    def test_empty_portfolio_creates_no_revenue_facts(self, db_session: Session):
        svc = AnalyticsService(db_session)
        count = svc.build_revenue_fact()

        assert count == 0
        assert db_session.query(FactRevenue).count() == 0

    def test_no_paid_installments_creates_no_revenue_facts(self, db_session: Session):
        pid = _make_project(db_session, "AF-REV-01")
        uid = _make_unit(db_session, pid, "AF-R01-U01")
        cid = _make_contract(db_session, uid, 100_000.0, "AF-REV-C001", "rev01@test.com")
        _make_installment(db_session, cid, 50_000.0, 1, date(2027, 3, 1), "pending")

        svc = AnalyticsService(db_session)
        count = svc.build_revenue_fact()

        assert count == 0
        assert db_session.query(FactRevenue).count() == 0

    def test_single_paid_installment_creates_one_revenue_fact(self, db_session: Session):
        pid = _make_project(db_session, "AF-REV-02")
        uid = _make_unit(db_session, pid, "AF-R02-U01")
        cid = _make_contract(db_session, uid, 100_000.0, "AF-REV-C002", "rev02@test.com")
        paid_at = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        _make_installment(db_session, cid, 50_000.0, 1, date(2026, 3, 1), "paid", paid_at)

        svc = AnalyticsService(db_session)
        count = svc.build_revenue_fact()

        assert count == 1
        facts = db_session.query(FactRevenue).all()
        assert len(facts) == 1
        fact = facts[0]
        assert fact.project_id == pid
        assert fact.unit_id == uid
        assert fact.month == "2026-03"
        assert float(fact.recognized_revenue) == pytest.approx(50_000.0)
        assert float(fact.contract_value) == pytest.approx(100_000.0)

    def test_revenue_facts_grouped_by_month(self, db_session: Session):
        """Installments paid in different months produce separate revenue facts."""
        pid = _make_project(db_session, "AF-REV-03")
        uid = _make_unit(db_session, pid, "AF-R03-U01")
        cid = _make_contract(db_session, uid, 120_000.0, "AF-REV-C003", "rev03@test.com")

        _make_installment(
            db_session, cid, 40_000.0, 1, date(2026, 3, 1), "paid",
            datetime(2026, 3, 10, tzinfo=timezone.utc),
        )
        _make_installment(
            db_session, cid, 40_000.0, 2, date(2026, 4, 1), "paid",
            datetime(2026, 4, 10, tzinfo=timezone.utc),
        )
        _make_installment(
            db_session, cid, 40_000.0, 3, date(2026, 5, 1), "paid",
            datetime(2026, 5, 10, tzinfo=timezone.utc),
        )

        svc = AnalyticsService(db_session)
        count = svc.build_revenue_fact()

        assert count == 3
        facts = db_session.query(FactRevenue).order_by(FactRevenue.month).all()
        months = [f.month for f in facts]
        assert months == ["2026-03", "2026-04", "2026-05"]

    def test_revenue_facts_grouped_within_same_month(self, db_session: Session):
        """Multiple paid installments in the same month are aggregated into one fact."""
        pid = _make_project(db_session, "AF-REV-04")
        uid = _make_unit(db_session, pid, "AF-R04-U01")
        cid = _make_contract(db_session, uid, 120_000.0, "AF-REV-C004", "rev04@test.com")

        _make_installment(
            db_session, cid, 30_000.0, 1, date(2026, 3, 5), "paid",
            datetime(2026, 3, 5, tzinfo=timezone.utc),
        )
        _make_installment(
            db_session, cid, 30_000.0, 2, date(2026, 3, 20), "paid",
            datetime(2026, 3, 20, tzinfo=timezone.utc),
        )

        svc = AnalyticsService(db_session)
        count = svc.build_revenue_fact()

        assert count == 1
        facts = db_session.query(FactRevenue).all()
        assert len(facts) == 1
        assert float(facts[0].recognized_revenue) == pytest.approx(60_000.0)

    def test_revenue_facts_correct_project_association(self, db_session: Session):
        """Revenue facts are correctly associated with the right project."""
        pid1 = _make_project(db_session, "AF-REV-05A")
        pid2 = _make_project(db_session, "AF-REV-05B")
        uid1 = _make_unit(db_session, pid1, "AF-R05A-U01")
        uid2 = _make_unit(db_session, pid2, "AF-R05B-U01")
        cid1 = _make_contract(db_session, uid1, 80_000.0, "AF-REV-C005A", "rev05a@test.com")
        cid2 = _make_contract(db_session, uid2, 90_000.0, "AF-REV-C005B", "rev05b@test.com")

        paid_at = datetime(2026, 6, 15, tzinfo=timezone.utc)
        _make_installment(db_session, cid1, 40_000.0, 1, date(2026, 6, 1), "paid", paid_at)
        _make_installment(db_session, cid2, 45_000.0, 1, date(2026, 6, 1), "paid", paid_at)

        svc = AnalyticsService(db_session)
        count = svc.build_revenue_fact()

        assert count == 2
        project_ids = {f.project_id for f in db_session.query(FactRevenue).all()}
        assert pid1 in project_ids
        assert pid2 in project_ids

    def test_rebuild_clears_previous_revenue_facts(self, db_session: Session):
        """Calling build_revenue_fact() twice replaces existing facts."""
        pid = _make_project(db_session, "AF-REV-06")
        uid = _make_unit(db_session, pid, "AF-R06-U01")
        cid = _make_contract(db_session, uid, 100_000.0, "AF-REV-C006", "rev06@test.com")
        paid_at = datetime(2026, 3, 15, tzinfo=timezone.utc)
        _make_installment(db_session, cid, 50_000.0, 1, date(2026, 3, 1), "paid", paid_at)

        svc = AnalyticsService(db_session)
        svc.build_revenue_fact()
        svc.build_revenue_fact()

        assert db_session.query(FactRevenue).count() == 1


# ---------------------------------------------------------------------------
# Test 2 — Collections fact generation
# ---------------------------------------------------------------------------


class TestBuildCollectionsFact:
    """Tests for AnalyticsService.build_collections_fact()."""

    def test_empty_portfolio_creates_no_collections_facts(self, db_session: Session):
        svc = AnalyticsService(db_session)
        count = svc.build_collections_fact()

        assert count == 0
        assert db_session.query(FactCollections).count() == 0

    def test_no_paid_installments_creates_no_collections_facts(self, db_session: Session):
        pid = _make_project(db_session, "AF-COL-01")
        uid = _make_unit(db_session, pid, "AF-C01-U01")
        cid = _make_contract(db_session, uid, 100_000.0, "AF-COL-C001", "col01@test.com")
        _make_installment(db_session, cid, 50_000.0, 1, date(2027, 3, 1), "pending")

        svc = AnalyticsService(db_session)
        count = svc.build_collections_fact()

        assert count == 0

    def test_payments_aggregated_by_month(self, db_session: Session):
        """Multiple paid installments in the same month are aggregated."""
        pid = _make_project(db_session, "AF-COL-02")
        uid = _make_unit(db_session, pid, "AF-C02-U01")
        cid = _make_contract(db_session, uid, 120_000.0, "AF-COL-C002", "col02@test.com")

        _make_installment(
            db_session, cid, 30_000.0, 1, date(2026, 4, 5), "paid",
            datetime(2026, 4, 5, tzinfo=timezone.utc),
        )
        _make_installment(
            db_session, cid, 30_000.0, 2, date(2026, 4, 20), "paid",
            datetime(2026, 4, 20, tzinfo=timezone.utc),
        )

        svc = AnalyticsService(db_session)
        count = svc.build_collections_fact()

        assert count == 1
        facts = db_session.query(FactCollections).all()
        assert len(facts) == 1
        assert facts[0].month == "2026-04"
        assert float(facts[0].amount) == pytest.approx(60_000.0)

    def test_payments_across_different_months_create_separate_facts(self, db_session: Session):
        pid = _make_project(db_session, "AF-COL-03")
        uid = _make_unit(db_session, pid, "AF-C03-U01")
        cid = _make_contract(db_session, uid, 120_000.0, "AF-COL-C003", "col03@test.com")

        _make_installment(
            db_session, cid, 40_000.0, 1, date(2026, 3, 1), "paid",
            datetime(2026, 3, 15, tzinfo=timezone.utc),
        )
        _make_installment(
            db_session, cid, 40_000.0, 2, date(2026, 5, 1), "paid",
            datetime(2026, 5, 15, tzinfo=timezone.utc),
        )

        svc = AnalyticsService(db_session)
        count = svc.build_collections_fact()

        assert count == 2
        months = sorted(f.month for f in db_session.query(FactCollections).all())
        assert months == ["2026-03", "2026-05"]

    def test_collections_fact_has_correct_project_id(self, db_session: Session):
        pid = _make_project(db_session, "AF-COL-04")
        uid = _make_unit(db_session, pid, "AF-C04-U01")
        cid = _make_contract(db_session, uid, 80_000.0, "AF-COL-C004", "col04@test.com")
        _make_installment(
            db_session, cid, 40_000.0, 1, date(2026, 6, 1), "paid",
            datetime(2026, 6, 10, tzinfo=timezone.utc),
        )

        svc = AnalyticsService(db_session)
        svc.build_collections_fact()

        facts = db_session.query(FactCollections).all()
        assert facts[0].project_id == pid

    def test_rebuild_clears_previous_collections_facts(self, db_session: Session):
        pid = _make_project(db_session, "AF-COL-05")
        uid = _make_unit(db_session, pid, "AF-C05-U01")
        cid = _make_contract(db_session, uid, 80_000.0, "AF-COL-C005", "col05@test.com")
        _make_installment(
            db_session, cid, 40_000.0, 1, date(2026, 6, 1), "paid",
            datetime(2026, 6, 10, tzinfo=timezone.utc),
        )

        svc = AnalyticsService(db_session)
        svc.build_collections_fact()
        svc.build_collections_fact()

        assert db_session.query(FactCollections).count() == 1


# ---------------------------------------------------------------------------
# Test 3 — Receivable snapshot generation
# ---------------------------------------------------------------------------


class TestBuildReceivableSnapshot:
    """Tests for AnalyticsService.build_receivable_snapshot()."""

    def test_empty_portfolio_creates_no_snapshots(self, db_session: Session):
        svc = AnalyticsService(db_session)
        count = svc.build_receivable_snapshot()

        assert count == 0
        assert db_session.query(FactReceivablesSnapshot).count() == 0

    def test_project_with_no_receivables_creates_snapshot_with_zero_totals(
        self, db_session: Session
    ):
        _make_project(db_session, "AF-REC-01")

        svc = AnalyticsService(db_session)
        count = svc.build_receivable_snapshot()

        assert count == 1
        snap = db_session.query(FactReceivablesSnapshot).first()
        assert float(snap.total_receivables) == pytest.approx(0.0)
        assert float(snap.bucket_0_30) == pytest.approx(0.0)

    def test_current_installment_goes_into_bucket_0_30(self, db_session: Session):
        """Installments not yet due (current) go into the 0-30 bucket."""
        today = date.today()
        pid = _make_project(db_session, "AF-REC-02")
        uid = _make_unit(db_session, pid, "AF-RC02-U01")
        cid = _make_contract(db_session, uid, 100_000.0, "AF-REC-C002", "rec02@test.com")
        # Due in the future — current bucket.
        _make_installment(
            db_session, cid, 50_000.0, 1, today + timedelta(days=15), "pending"
        )

        svc = AnalyticsService(db_session)
        svc.build_receivable_snapshot()

        snap = db_session.query(FactReceivablesSnapshot).filter(
            FactReceivablesSnapshot.project_id == pid
        ).first()
        assert snap is not None
        assert float(snap.bucket_0_30) == pytest.approx(50_000.0)
        assert float(snap.total_receivables) == pytest.approx(50_000.0)

    def test_overdue_31_60_days_installment_goes_into_correct_bucket(
        self, db_session: Session
    ):
        today = date.today()
        pid = _make_project(db_session, "AF-REC-03")
        uid = _make_unit(db_session, pid, "AF-RC03-U01")
        cid = _make_contract(db_session, uid, 100_000.0, "AF-REC-C003", "rec03@test.com")
        _make_installment(
            db_session, cid, 50_000.0, 1, today - timedelta(days=45), "overdue"
        )

        svc = AnalyticsService(db_session)
        svc.build_receivable_snapshot()

        snap = db_session.query(FactReceivablesSnapshot).filter(
            FactReceivablesSnapshot.project_id == pid
        ).first()
        assert float(snap.bucket_31_60) == pytest.approx(50_000.0)

    def test_overdue_90_plus_installment_goes_into_bucket_90_plus(
        self, db_session: Session
    ):
        today = date.today()
        pid = _make_project(db_session, "AF-REC-04")
        uid = _make_unit(db_session, pid, "AF-RC04-U01")
        cid = _make_contract(db_session, uid, 200_000.0, "AF-REC-C004", "rec04@test.com")
        _make_installment(
            db_session, cid, 100_000.0, 1, today - timedelta(days=120), "overdue"
        )

        svc = AnalyticsService(db_session)
        svc.build_receivable_snapshot()

        snap = db_session.query(FactReceivablesSnapshot).filter(
            FactReceivablesSnapshot.project_id == pid
        ).first()
        assert float(snap.bucket_90_plus) == pytest.approx(100_000.0)
        assert float(snap.total_receivables) == pytest.approx(100_000.0)

    def test_bucket_totals_sum_to_total_receivables(self, db_session: Session):
        today = date.today()
        pid = _make_project(db_session, "AF-REC-05")
        uid = _make_unit(db_session, pid, "AF-RC05-U01")
        cid = _make_contract(db_session, uid, 400_000.0, "AF-REC-C005", "rec05@test.com")

        _make_installment(
            db_session, cid, 100_000.0, 1, today + timedelta(days=10), "pending"
        )
        _make_installment(
            db_session, cid, 100_000.0, 2, today - timedelta(days=45), "overdue"
        )
        _make_installment(
            db_session, cid, 100_000.0, 3, today - timedelta(days=75), "overdue"
        )
        _make_installment(
            db_session, cid, 100_000.0, 4, today - timedelta(days=120), "overdue"
        )

        svc = AnalyticsService(db_session)
        svc.build_receivable_snapshot()

        snap = db_session.query(FactReceivablesSnapshot).filter(
            FactReceivablesSnapshot.project_id == pid
        ).first()

        bucket_sum = (
            float(snap.bucket_0_30)
            + float(snap.bucket_31_60)
            + float(snap.bucket_61_90)
            + float(snap.bucket_90_plus)
        )
        assert bucket_sum == pytest.approx(float(snap.total_receivables))
        assert float(snap.total_receivables) == pytest.approx(400_000.0)

    def test_paid_installments_excluded_from_snapshot(self, db_session: Session):
        today = date.today()
        pid = _make_project(db_session, "AF-REC-06")
        uid = _make_unit(db_session, pid, "AF-RC06-U01")
        cid = _make_contract(db_session, uid, 200_000.0, "AF-REC-C006", "rec06@test.com")

        _make_installment(
            db_session, cid, 100_000.0, 1, today - timedelta(days=10), "paid",
            datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        _make_installment(
            db_session, cid, 100_000.0, 2, today + timedelta(days=30), "pending"
        )

        svc = AnalyticsService(db_session)
        svc.build_receivable_snapshot()

        snap = db_session.query(FactReceivablesSnapshot).filter(
            FactReceivablesSnapshot.project_id == pid
        ).first()
        # Only the pending installment should be included.
        assert float(snap.total_receivables) == pytest.approx(100_000.0)

    def test_snapshot_date_is_today(self, db_session: Session):
        _make_project(db_session, "AF-REC-07")

        svc = AnalyticsService(db_session)
        svc.build_receivable_snapshot()

        snap = db_session.query(FactReceivablesSnapshot).first()
        assert snap.snapshot_date == date.today()


# ---------------------------------------------------------------------------
# Test 4 — Analytics rebuild endpoint
# ---------------------------------------------------------------------------


class TestAnalyticsRebuildEndpoint:
    """Tests for POST /finance/analytics/rebuild."""

    def test_rebuild_endpoint_returns_200(self, client):
        response = client.post("/api/v1/finance/analytics/rebuild")
        assert response.status_code == 200

    def test_rebuild_endpoint_returns_analytics_rebuild_response(self, client):
        response = client.post("/api/v1/finance/analytics/rebuild")
        data = response.json()

        assert "revenue_facts_created" in data
        assert "collections_facts_created" in data
        assert "receivable_snapshots_created" in data

    def test_rebuild_endpoint_empty_portfolio_returns_zeros(self, client):
        response = client.post("/api/v1/finance/analytics/rebuild")
        data = response.json()

        assert data["revenue_facts_created"] == 0
        assert data["collections_facts_created"] == 0
        assert data["receivable_snapshots_created"] == 0

    def test_rebuild_endpoint_with_data_creates_facts(self, client, db_session: Session):
        """End-to-end: rebuild endpoint creates correct fact rows."""
        today = date.today()
        pid = _make_project(db_session, "AF-API-01")
        uid = _make_unit(db_session, pid, "AF-API01-U01")
        cid = _make_contract(db_session, uid, 120_000.0, "AF-API-C001", "api01@test.com")
        paid_at = datetime(2026, 3, 15, tzinfo=timezone.utc)
        _make_installment(db_session, cid, 60_000.0, 1, date(2026, 3, 1), "paid", paid_at)
        _make_installment(db_session, cid, 60_000.0, 2, today + timedelta(days=30), "pending")

        response = client.post("/api/v1/finance/analytics/rebuild")
        assert response.status_code == 200

        data = response.json()
        assert data["revenue_facts_created"] >= 1
        assert data["collections_facts_created"] >= 1
        assert data["receivable_snapshots_created"] >= 1


# ---------------------------------------------------------------------------
# Test 5 — Full rebuild via service
# ---------------------------------------------------------------------------


class TestRebuildFinancialAnalytics:
    """Tests for AnalyticsService.rebuild_financial_analytics()."""

    def test_rebuild_returns_analytics_rebuild_response(self, db_session: Session):
        svc = AnalyticsService(db_session)
        result = svc.rebuild_financial_analytics()

        assert isinstance(result, AnalyticsRebuildResponse)

    def test_rebuild_empty_portfolio(self, db_session: Session):
        svc = AnalyticsService(db_session)
        result = svc.rebuild_financial_analytics()

        assert result.revenue_facts_created == 0
        assert result.collections_facts_created == 0
        assert result.receivable_snapshots_created == 0

    def test_rebuild_populates_all_fact_tables(self, db_session: Session):
        today = date.today()
        pid = _make_project(db_session, "AF-FULL-01")
        uid = _make_unit(db_session, pid, "AF-FL01-U01")
        cid = _make_contract(db_session, uid, 200_000.0, "AF-FULL-C001", "full01@test.com")
        paid_at = datetime(2026, 4, 10, tzinfo=timezone.utc)
        _make_installment(db_session, cid, 100_000.0, 1, date(2026, 4, 1), "paid", paid_at)
        _make_installment(db_session, cid, 100_000.0, 2, today + timedelta(days=60), "pending")

        svc = AnalyticsService(db_session)
        result = svc.rebuild_financial_analytics()

        assert result.revenue_facts_created >= 1
        assert result.collections_facts_created >= 1
        assert result.receivable_snapshots_created >= 1
