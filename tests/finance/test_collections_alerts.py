"""
Tests for collections alerts engine, service, and API.

Validates:
  - alert severity classification (7/30/90 day thresholds)
  - alert generation from overdue installments
  - duplicate prevention
  - alert resolution
  - receipt matching (exact, partial, multi-installment, unmatched)
  - API endpoints for alerts and receipt matching
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.collections.collections_alert_engine import (
    AlertCandidate,
    InstallmentSnapshot,
    classify_alert_severity,
    generate_overdue_alerts,
)
from app.modules.collections.receipt_matching_service import (
    InstallmentObligation,
    ReceiptMatchResult,
    allocate_multi_installment_payment,
    apply_partial_payment,
    detect_unmatched_payment,
    match_payment_to_installments,
)
from app.modules.finance.service import CollectionsAlertService, ReceiptMatchingService
from app.shared.enums.finance import AlertSeverity, AlertType, MatchStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_alert_seq: dict[str, int] = {}


def _make_project(db_session: Session, code: str) -> str:
    from app.modules.projects.models import Project

    project = Project(name=f"Alert Project {code}", code=code)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


def _make_unit(db_session: Session, project_id: str, unit_number: str) -> str:
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _alert_seq.get(project_id, 0) + 1
    _alert_seq[project_id] = seq

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

    buyer = Buyer(full_name="Alert Buyer", email=email, phone="+9620000001")
    db_session.add(buyer)
    db_session.flush()

    contract = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer.id,
        contract_number=contract_number,
        contract_date=date(2026, 1, 1),
        contract_price=contract_price,
        status="active",
    )
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)
    return contract.id


def _make_installment(
    db_session: Session,
    contract_id: str,
    installment_number: int,
    due_date: date,
    amount: float,
    status: str = "pending",
) -> str:
    from app.modules.sales.models import ContractPaymentSchedule

    inst = ContractPaymentSchedule(
        contract_id=contract_id,
        installment_number=installment_number,
        due_date=due_date,
        amount=amount,
        status=status,
    )
    db_session.add(inst)
    db_session.commit()
    db_session.refresh(inst)
    return inst.id


# ---------------------------------------------------------------------------
# Unit tests — classify_alert_severity
# ---------------------------------------------------------------------------


class TestClassifyAlertSeverity:
    def test_not_yet_overdue_returns_none(self):
        assert classify_alert_severity(0) is None
        assert classify_alert_severity(-5) is None

    def test_less_than_threshold_returns_none(self):
        assert classify_alert_severity(6) is None

    def test_exactly_7_days_returns_warning(self):
        assert classify_alert_severity(7) is AlertSeverity.WARNING

    def test_between_7_and_30_returns_warning(self):
        assert classify_alert_severity(15) is AlertSeverity.WARNING
        assert classify_alert_severity(29) is AlertSeverity.WARNING

    def test_exactly_30_days_returns_critical(self):
        assert classify_alert_severity(30) is AlertSeverity.CRITICAL

    def test_between_30_and_90_returns_critical(self):
        assert classify_alert_severity(45) is AlertSeverity.CRITICAL
        assert classify_alert_severity(89) is AlertSeverity.CRITICAL

    def test_exactly_90_days_returns_high_risk(self):
        assert classify_alert_severity(90) is AlertSeverity.HIGH_RISK

    def test_above_90_days_returns_high_risk(self):
        assert classify_alert_severity(120) is AlertSeverity.HIGH_RISK
        assert classify_alert_severity(365) is AlertSeverity.HIGH_RISK


# ---------------------------------------------------------------------------
# Unit tests — generate_overdue_alerts
# ---------------------------------------------------------------------------


class TestGenerateOverdueAlerts:
    def _make_snapshot(
        self, contract_id: str, inst_id: str, days_overdue: int, balance: float = 1000.0
    ) -> InstallmentSnapshot:
        due_date = date.today() - timedelta(days=days_overdue)
        return InstallmentSnapshot(
            id=inst_id,
            contract_id=contract_id,
            due_date=due_date,
            outstanding_balance=balance,
        )

    def test_no_installments_returns_empty(self):
        result = generate_overdue_alerts([], date.today())
        assert result == []

    def test_current_installment_not_alerted(self):
        snap = InstallmentSnapshot(
            id="inst-1",
            contract_id="c-1",
            due_date=date.today() + timedelta(days=5),
            outstanding_balance=1000.0,
        )
        result = generate_overdue_alerts([snap], date.today())
        assert result == []

    def test_6_days_overdue_not_alerted(self):
        snap = self._make_snapshot("c-1", "inst-1", days_overdue=6)
        result = generate_overdue_alerts([snap], date.today())
        assert result == []

    def test_7_days_overdue_generates_warning(self):
        snap = self._make_snapshot("c-1", "inst-1", days_overdue=7)
        result = generate_overdue_alerts([snap], date.today())
        assert len(result) == 1
        assert result[0].severity is AlertSeverity.WARNING
        assert result[0].alert_type is AlertType.OVERDUE_7_DAYS

    def test_30_days_overdue_generates_critical(self):
        snap = self._make_snapshot("c-1", "inst-1", days_overdue=30)
        result = generate_overdue_alerts([snap], date.today())
        assert len(result) == 1
        assert result[0].severity is AlertSeverity.CRITICAL
        assert result[0].alert_type is AlertType.OVERDUE_30_DAYS

    def test_90_days_overdue_generates_high_risk(self):
        snap = self._make_snapshot("c-1", "inst-1", days_overdue=90)
        result = generate_overdue_alerts([snap], date.today())
        assert len(result) == 1
        assert result[0].severity is AlertSeverity.HIGH_RISK
        assert result[0].alert_type is AlertType.OVERDUE_90_DAYS

    def test_multiple_installments(self):
        snaps = [
            self._make_snapshot("c-1", "inst-1", days_overdue=5),   # no alert
            self._make_snapshot("c-1", "inst-2", days_overdue=10),  # warning
            self._make_snapshot("c-1", "inst-3", days_overdue=45),  # critical
            self._make_snapshot("c-1", "inst-4", days_overdue=100), # high risk
        ]
        result = generate_overdue_alerts(snaps, date.today())
        assert len(result) == 3
        severities = {r.severity for r in result}
        assert severities == {AlertSeverity.WARNING, AlertSeverity.CRITICAL, AlertSeverity.HIGH_RISK}

    def test_candidate_carries_correct_balance(self):
        snap = self._make_snapshot("c-2", "inst-99", days_overdue=30, balance=55_000.0)
        result = generate_overdue_alerts([snap], date.today())
        assert result[0].outstanding_balance == pytest.approx(55_000.0)
        assert result[0].contract_id == "c-2"
        assert result[0].installment_id == "inst-99"


# ---------------------------------------------------------------------------
# Unit tests — receipt matching engine
# ---------------------------------------------------------------------------


class TestMatchPaymentToInstallments:
    def _inst(self, id_: str, num: int, amount: float) -> InstallmentObligation:
        return InstallmentObligation(
            id=id_, installment_number=num, outstanding_amount=amount
        )

    def test_zero_payment_returns_unmatched(self):
        inst = self._inst("i-1", 1, 1000.0)
        result = match_payment_to_installments(0.0, [inst])
        assert result.strategy is MatchStrategy.UNMATCHED
        assert result.matched_installment_ids == []

    def test_no_installments_returns_unmatched(self):
        result = match_payment_to_installments(500.0, [])
        assert result.strategy is MatchStrategy.UNMATCHED

    def test_exact_match(self):
        inst = self._inst("i-1", 1, 1000.0)
        result = match_payment_to_installments(1000.0, [inst])
        assert result.strategy is MatchStrategy.EXACT
        assert result.matched_installment_ids == ["i-1"]
        assert result.allocated_amounts["i-1"] == pytest.approx(1000.0)
        assert result.unallocated_amount == pytest.approx(0.0)

    def test_partial_payment(self):
        inst = self._inst("i-1", 1, 1000.0)
        result = match_payment_to_installments(300.0, [inst])
        assert result.strategy is MatchStrategy.PARTIAL
        assert result.matched_installment_ids == ["i-1"]
        assert result.allocated_amounts["i-1"] == pytest.approx(300.0)
        assert result.unallocated_amount == pytest.approx(0.0)

    def test_multi_installment_exact_coverage(self):
        insts = [
            self._inst("i-1", 1, 500.0),
            self._inst("i-2", 2, 500.0),
        ]
        result = match_payment_to_installments(1000.0, insts)
        assert result.strategy is MatchStrategy.MULTI_INSTALLMENT
        assert set(result.matched_installment_ids) == {"i-1", "i-2"}
        assert result.unallocated_amount == pytest.approx(0.0)

    def test_multi_installment_with_remainder(self):
        insts = [
            self._inst("i-1", 1, 500.0),
            self._inst("i-2", 2, 500.0),
            self._inst("i-3", 3, 500.0),
        ]
        # Pay 1200 — covers first two fully, 200 partial on third
        result = match_payment_to_installments(1200.0, insts)
        assert result.strategy is MatchStrategy.MULTI_INSTALLMENT
        assert "i-1" in result.matched_installment_ids
        assert "i-2" in result.matched_installment_ids
        assert "i-3" in result.matched_installment_ids
        assert result.allocated_amounts["i-3"] == pytest.approx(200.0)
        assert result.unallocated_amount == pytest.approx(0.0)

    def test_payment_larger_than_all_installments(self):
        insts = [self._inst("i-1", 1, 100.0)]
        result = match_payment_to_installments(150.0, insts)
        assert result.unallocated_amount == pytest.approx(50.0)

    def test_apply_partial_payment(self):
        inst = self._inst("i-1", 1, 1000.0)
        result = apply_partial_payment(250.0, inst)
        assert result.strategy is MatchStrategy.PARTIAL
        assert result.allocated_amounts["i-1"] == pytest.approx(250.0)

    def test_detect_unmatched_payment(self):
        result = detect_unmatched_payment(750.0)
        assert result.strategy is MatchStrategy.UNMATCHED
        assert result.unallocated_amount == pytest.approx(750.0)


# ---------------------------------------------------------------------------
# Service-layer tests — CollectionsAlertService
# ---------------------------------------------------------------------------


class TestCollectionsAlertService:
    def test_no_installments_generates_no_alerts(self, db_session: Session):
        svc = CollectionsAlertService(db_session)
        result = svc.generate_alerts()
        assert result.total == 0

    def test_generates_warning_alert_for_7_day_overdue(self, db_session: Session):
        pid = _make_project(db_session, "ALT-SVC-01")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-ALT-01", "alt01@test.com")
        overdue_date = date.today() - timedelta(days=10)
        _make_installment(db_session, cid, 1, overdue_date, 25_000.0, status="overdue")

        svc = CollectionsAlertService(db_session)
        result = svc.generate_alerts()

        assert result.total >= 1
        alert = next(a for a in result.items if a.contract_id == cid)
        assert alert.severity == AlertSeverity.WARNING.value

    def test_generates_critical_alert_for_30_day_overdue(self, db_session: Session):
        pid = _make_project(db_session, "ALT-SVC-02")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-ALT-02", "alt02@test.com")
        overdue_date = date.today() - timedelta(days=35)
        _make_installment(db_session, cid, 1, overdue_date, 25_000.0, status="overdue")

        svc = CollectionsAlertService(db_session)
        result = svc.generate_alerts()

        assert result.total >= 1
        alert = next(a for a in result.items if a.contract_id == cid)
        assert alert.severity == AlertSeverity.CRITICAL.value

    def test_generates_high_risk_alert_for_90_day_overdue(self, db_session: Session):
        pid = _make_project(db_session, "ALT-SVC-03")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-ALT-03", "alt03@test.com")
        overdue_date = date.today() - timedelta(days=95)
        _make_installment(db_session, cid, 1, overdue_date, 25_000.0, status="overdue")

        svc = CollectionsAlertService(db_session)
        result = svc.generate_alerts()

        assert result.total >= 1
        alert = next(a for a in result.items if a.contract_id == cid)
        assert alert.severity == AlertSeverity.HIGH_RISK.value

    def test_duplicate_alert_prevention(self, db_session: Session):
        pid = _make_project(db_session, "ALT-SVC-04")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-ALT-04", "alt04@test.com")
        overdue_date = date.today() - timedelta(days=10)
        _make_installment(db_session, cid, 1, overdue_date, 25_000.0, status="overdue")

        svc = CollectionsAlertService(db_session)
        first = svc.generate_alerts()
        first_count = first.total
        # Run again — should not create duplicates.
        second = svc.generate_alerts()
        assert second.total == first_count

    def test_resolve_alert(self, db_session: Session):
        pid = _make_project(db_session, "ALT-SVC-05")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-ALT-05", "alt05@test.com")
        overdue_date = date.today() - timedelta(days=10)
        _make_installment(db_session, cid, 1, overdue_date, 25_000.0, status="overdue")

        svc = CollectionsAlertService(db_session)
        generated = svc.generate_alerts()
        alert = next(a for a in generated.items if a.contract_id == cid)

        resolved = svc.resolve_alert(alert.alert_id, notes="Settled by buyer")
        assert resolved.resolved_at is not None
        assert resolved.notes == "Settled by buyer"

    def test_resolve_nonexistent_alert_raises_404(self, db_session: Session):
        svc = CollectionsAlertService(db_session)
        with pytest.raises(HTTPException) as exc_info:
            svc.resolve_alert("no-such-id")
        assert exc_info.value.status_code == 404

    def test_resolve_already_resolved_alert_raises_422(self, db_session: Session):
        pid = _make_project(db_session, "ALT-SVC-06")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-ALT-06", "alt06@test.com")
        overdue_date = date.today() - timedelta(days=10)
        _make_installment(db_session, cid, 1, overdue_date, 25_000.0, status="overdue")

        svc = CollectionsAlertService(db_session)
        generated = svc.generate_alerts()
        alert = next(a for a in generated.items if a.contract_id == cid)
        svc.resolve_alert(alert.alert_id)

        with pytest.raises(HTTPException) as exc_info:
            svc.resolve_alert(alert.alert_id)
        assert exc_info.value.status_code == 422

    def test_severity_filter(self, db_session: Session):
        svc = CollectionsAlertService(db_session)
        result = svc.get_overdue_alerts(severity="warning")
        for alert in result.items:
            assert alert.severity == "warning"


# ---------------------------------------------------------------------------
# Service-layer tests — ReceiptMatchingService
# ---------------------------------------------------------------------------


class TestReceiptMatchingService:
    def test_invalid_contract_raises_404(self, db_session: Session):
        from app.modules.finance.schemas import MatchReceiptRequest

        svc = ReceiptMatchingService(db_session)
        with pytest.raises(HTTPException) as exc_info:
            svc.match_payment(
                MatchReceiptRequest(contract_id="no-such-contract", payment_amount=500.0)
            )
        assert exc_info.value.status_code == 404

    def test_exact_match_returns_exact_strategy(self, db_session: Session):
        from app.modules.finance.schemas import MatchReceiptRequest

        pid = _make_project(db_session, "MTC-SVC-01")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-MTC-01", "mtc01@test.com")
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid, 1, future, 25_000.0, status="pending")

        svc = ReceiptMatchingService(db_session)
        result = svc.match_payment(
            MatchReceiptRequest(contract_id=cid, payment_amount=25_000.0)
        )
        assert result.strategy == MatchStrategy.EXACT.value
        assert len(result.matched_installment_ids) == 1
        assert result.unallocated_amount == pytest.approx(0.0)

    def test_partial_payment_strategy(self, db_session: Session):
        from app.modules.finance.schemas import MatchReceiptRequest

        pid = _make_project(db_session, "MTC-SVC-02")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-MTC-02", "mtc02@test.com")
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid, 1, future, 25_000.0, status="pending")

        svc = ReceiptMatchingService(db_session)
        result = svc.match_payment(
            MatchReceiptRequest(contract_id=cid, payment_amount=10_000.0)
        )
        assert result.strategy == MatchStrategy.PARTIAL.value

    def test_multi_installment_strategy(self, db_session: Session):
        from app.modules.finance.schemas import MatchReceiptRequest

        pid = _make_project(db_session, "MTC-SVC-03")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-MTC-03", "mtc03@test.com")
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid, 1, future, 25_000.0, status="pending")
        _make_installment(db_session, cid, 2, future + timedelta(days=30), 25_000.0, status="pending")

        svc = ReceiptMatchingService(db_session)
        result = svc.match_payment(
            MatchReceiptRequest(contract_id=cid, payment_amount=50_000.0)
        )
        assert result.strategy == MatchStrategy.MULTI_INSTALLMENT.value
        assert len(result.matched_installment_ids) == 2

    def test_no_outstanding_returns_unmatched(self, db_session: Session):
        from app.modules.finance.schemas import MatchReceiptRequest

        pid = _make_project(db_session, "MTC-SVC-04")
        uid = _make_unit(db_session, pid, "101")
        cid = _make_contract(db_session, uid, 100_000.0, "CNT-MTC-04", "mtc04@test.com")
        # No installments — nothing to match.

        svc = ReceiptMatchingService(db_session)
        result = svc.match_payment(
            MatchReceiptRequest(contract_id=cid, payment_amount=500.0)
        )
        assert result.strategy == MatchStrategy.UNMATCHED.value


# ---------------------------------------------------------------------------
# API tests — via TestClient
# ---------------------------------------------------------------------------


def _api_create_hierarchy(client: TestClient, proj_code: str) -> str:
    """Create a project hierarchy and return unit_id."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "Alert API Project", "code": proj_code}
    ).json()["id"]
    phase_id = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    ).json()["id"]
    building_id = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    ).json()["id"]
    floor_id = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]
    unit_id = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 100.0,
        },
    ).json()["id"]
    return unit_id


def _api_create_contract(
    client: TestClient,
    proj_code: str,
    email: str,
    contract_number: str = "CNT-API-001",
) -> str:
    unit_id = _api_create_hierarchy(client, proj_code)
    buyer_id = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Alert Buyer", "email": email, "phone": "+9620000001"},
    ).json()["id"]
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": "2026-01-01",
            "contract_price": 100_000.0,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_get_collections_alerts_returns_empty_initially(client: TestClient):
    resp = client.get("/api/v1/finance/collections/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 0


def test_generate_alerts_returns_201(client: TestClient):
    resp = client.post("/api/v1/finance/collections/alerts/generate")
    assert resp.status_code == 201
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_resolve_alert_returns_200(client: TestClient, db_session: Session):
    """Create an alert directly in DB, then resolve it via API."""
    from datetime import datetime, timezone

    from app.modules.collections.models import CollectionsAlert

    pid = _make_project(db_session, "ALT-API-RES")
    uid = _make_unit(db_session, pid, "101")
    cid = _make_contract(db_session, uid, 100_000.0, "CNT-API-RES", "apiresol@test.com")
    overdue_date = date.today() - timedelta(days=10)
    iid = _make_installment(db_session, cid, 1, overdue_date, 25_000.0, status="overdue")

    alert = CollectionsAlert(
        contract_id=cid,
        installment_id=iid,
        alert_type="overdue_7_days",
        severity="warning",
        days_overdue=10,
        outstanding_balance=25_000.0,
    )
    db_session.add(alert)
    db_session.commit()

    resp = client.post(
        f"/api/v1/finance/collections/alerts/{alert.id}/resolve",
        json={"notes": "Resolved by test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolved_at"] is not None
    assert data["notes"] == "Resolved by test"


def test_resolve_nonexistent_alert_returns_404(client: TestClient):
    resp = client.post(
        "/api/v1/finance/collections/alerts/no-such-id/resolve",
        json={},
    )
    assert resp.status_code == 404


def test_match_receipt_exact_match(client: TestClient, db_session: Session):
    pid = _make_project(db_session, "MTC-API-EX")
    uid = _make_unit(db_session, pid, "101")
    cid = _make_contract(db_session, uid, 100_000.0, "CNT-MTC-API-EX", "mtcapiex@test.com")
    future = date.today() + timedelta(days=30)
    _make_installment(db_session, cid, 1, future, 25_000.0, status="pending")

    resp = client.post(
        "/api/v1/finance/payments/match-receipt",
        json={"contract_id": cid, "payment_amount": 25_000.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy"] == "exact"
    assert data["contract_id"] == cid
    assert len(data["matched_installment_ids"]) == 1
    assert data["unallocated_amount"] == pytest.approx(0.0)


def test_match_receipt_invalid_contract_returns_404(client: TestClient):
    resp = client.post(
        "/api/v1/finance/payments/match-receipt",
        json={"contract_id": "no-such-contract", "payment_amount": 500.0},
    )
    assert resp.status_code == 404


def test_match_receipt_zero_amount_returns_422(client: TestClient):
    resp = client.post(
        "/api/v1/finance/payments/match-receipt",
        json={"contract_id": "some-contract", "payment_amount": 0.0},
    )
    assert resp.status_code == 422


def test_get_alerts_severity_filter(client: TestClient):
    resp = client.get("/api/v1/finance/collections/alerts?severity=warning")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["severity"] == "warning"


# ---------------------------------------------------------------------------
# PR-19A hardening tests
# ---------------------------------------------------------------------------


def test_resolve_alert_with_empty_string_note_clears_notes(
    client: TestClient, db_session: Session
):
    """resolve_alert accepts empty string — notes should be set to '' not skipped."""
    from app.modules.collections.models import CollectionsAlert

    pid = _make_project(db_session, "ALT-19A-EMPTY")
    uid = _make_unit(db_session, pid, "101")
    cid = _make_contract(db_session, uid, 100_000.0, "CNT-19A-EMPTY", "empty@test.com")
    overdue_date = date.today() - timedelta(days=10)
    iid = _make_installment(db_session, cid, 1, overdue_date, 5_000.0, status="overdue")

    alert = CollectionsAlert(
        contract_id=cid,
        installment_id=iid,
        alert_type="overdue_7_days",
        severity="warning",
        days_overdue=10,
        outstanding_balance=5_000.0,
        notes="original note",
    )
    db_session.add(alert)
    db_session.commit()

    resp = client.post(
        f"/api/v1/finance/collections/alerts/{alert.id}/resolve",
        json={"notes": ""},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Empty string notes should be accepted (not skipped).
    assert data["notes"] == ""
    assert data["resolved_at"] is not None


def test_resolve_alert_note_none_preserves_existing_notes(
    client: TestClient, db_session: Session
):
    """Passing notes=None should leave existing notes unchanged."""
    from app.modules.collections.models import CollectionsAlert

    pid = _make_project(db_session, "ALT-19A-NONE")
    uid = _make_unit(db_session, pid, "101")
    cid = _make_contract(db_session, uid, 100_000.0, "CNT-19A-NONE", "nonenotes@test.com")
    overdue_date = date.today() - timedelta(days=10)
    iid = _make_installment(db_session, cid, 1, overdue_date, 5_000.0, status="overdue")

    alert = CollectionsAlert(
        contract_id=cid,
        installment_id=iid,
        alert_type="overdue_7_days",
        severity="warning",
        days_overdue=10,
        outstanding_balance=5_000.0,
        notes="keep this note",
    )
    db_session.add(alert)
    db_session.commit()

    resp = client.post(
        f"/api/v1/finance/collections/alerts/{alert.id}/resolve",
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()
    # notes=None means don't change; original note must be preserved.
    assert data["notes"] == "keep this note"


def test_alert_response_timestamps_are_iso_strings(
    client: TestClient, db_session: Session
):
    """created_at and resolved_at must serialize to ISO-format strings."""
    from app.modules.collections.models import CollectionsAlert

    pid = _make_project(db_session, "ALT-19A-TS")
    uid = _make_unit(db_session, pid, "101")
    cid = _make_contract(db_session, uid, 100_000.0, "CNT-19A-TS", "ts@test.com")
    overdue_date = date.today() - timedelta(days=10)
    iid = _make_installment(db_session, cid, 1, overdue_date, 5_000.0, status="overdue")

    alert = CollectionsAlert(
        contract_id=cid,
        installment_id=iid,
        alert_type="overdue_7_days",
        severity="warning",
        days_overdue=10,
        outstanding_balance=5_000.0,
    )
    db_session.add(alert)
    db_session.commit()

    # created_at must be a string (ISO format) in the JSON response.
    resp = client.get("/api/v1/finance/collections/alerts")
    assert resp.status_code == 200
    items = resp.json()["items"]
    matching = [i for i in items if i["alert_id"] == alert.id]
    assert len(matching) == 1
    item = matching[0]
    # Must be a parseable ISO datetime string.
    from datetime import datetime

    datetime.fromisoformat(item["created_at"])
    assert item["resolved_at"] is None


def test_invalid_severity_filter_returns_422(client: TestClient):
    """An invalid severity value must be rejected at the API level."""
    resp = client.get("/api/v1/finance/collections/alerts?severity=invalid_severity")
    assert resp.status_code == 422


def test_surplus_payment_uses_multi_installment_strategy():
    """When payment exceeds all installments, strategy should not be PARTIAL."""
    from app.modules.collections.receipt_matching_service import (
        InstallmentObligation,
        MatchStrategy,
        match_payment_to_installments,
    )

    inst = InstallmentObligation(id="i-1", installment_number=1, outstanding_amount=100.0)
    result = match_payment_to_installments(150.0, [inst])
    # 50 unallocated — must be MULTI_INSTALLMENT, not PARTIAL.
    assert result.strategy is MatchStrategy.MULTI_INSTALLMENT
    assert result.unallocated_amount == pytest.approx(50.0)
