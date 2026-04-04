"""
Tests for the receivables service layer.

Validates receivable generation, duplication protection, status derivation,
balance calculation, and payment update logic.
"""

import pytest
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.receivables.schemas import ReceivablePaymentUpdate
from app.modules.receivables.service import ReceivableService
from app.shared.enums.finance import ReceivableStatus


# ---------------------------------------------------------------------------
# Helpers — create test fixtures
# ---------------------------------------------------------------------------


def _make_hierarchy(db: Session, project_code: str = "PRJ-RCV-SVC") -> str:
    """Create project → phase → building → floor → unit; return unit_id."""
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit

    project = Project(name="Receivables Project", code=project_code)
    db.add(project)
    db.flush()

    phase = Phase(project_id=project.id, name="Phase 1", sequence=1)
    db.add(phase)
    db.flush()

    building = Building(phase_id=phase.id, name="Block A", code="BLK-A")
    db.add(building)
    db.flush()

    floor = Floor(
        building_id=building.id, name="Floor 1", code="FL-01", sequence_number=1
    )
    db.add(floor)
    db.flush()

    unit = Unit(
        floor_id=floor.id, unit_number="101", unit_type="studio", internal_area=100.0
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit.id


def _make_contract(
    db: Session,
    project_code: str = "PRJ-RCV-SVC",
    contract_price: float = 300_000.0,
    number: str = "001",
    currency: str = "AED",
) -> str:
    from app.modules.sales.models import Buyer, SalesContract

    unit_id = _make_hierarchy(db, project_code)
    buyer = Buyer(
        full_name="RCV Buyer",
        email=f"rcvb-{project_code}-{number}@test.com",
        phone="+1",
    )
    db.add(buyer)
    db.flush()

    contract = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer.id,
        contract_number=f"CNT-{project_code}-{number}",
        contract_date=date(2026, 1, 1),
        contract_price=contract_price,
        currency=currency,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract.id


def _add_installments(
    db: Session,
    contract_id: str,
    count: int = 3,
    template_id: str | None = None,
    start_date: date | None = None,
    currency: str = "AED",
) -> list[str]:
    """Create `count` PaymentSchedule rows for a contract; return installment IDs."""
    from app.modules.payment_plans.models import PaymentSchedule

    base = start_date or date(2026, 2, 1)

    installment_ids = []
    for i in range(1, count + 1):
        # Advance by (i-1) months; wrap year when month overflows December.
        month_offset = base.month + (i - 1)
        year = base.year + (month_offset - 1) // 12
        month = (month_offset - 1) % 12 + 1
        due = date(year, month, base.day)
        inst = PaymentSchedule(
            contract_id=contract_id,
            template_id=template_id,
            installment_number=i,
            due_date=due,
            due_amount=100_000.0,
            currency=currency,
            status="pending",
        )
        db.add(inst)
        db.flush()
        installment_ids.append(inst.id)
    db.commit()
    return installment_ids


# ---------------------------------------------------------------------------
# Generation tests
# ---------------------------------------------------------------------------


def test_generate_creates_one_receivable_per_installment(db_session: Session):
    contract_id = _make_contract(db_session)
    _add_installments(db_session, contract_id, count=3)

    svc = ReceivableService(db_session)
    result = svc.generate_for_contract(contract_id)

    assert result.generated == 3
    assert len(result.items) == 3
    assert result.contract_id == contract_id


def test_generate_sets_correct_amounts(db_session: Session):
    contract_id = _make_contract(db_session, number="002")
    _add_installments(db_session, contract_id, count=2)

    svc = ReceivableService(db_session)
    result = svc.generate_for_contract(contract_id)

    for item in result.items:
        assert item.amount_due == pytest.approx(100_000.0)
        assert item.amount_paid == pytest.approx(0.0)
        assert item.balance_due == pytest.approx(100_000.0)
        assert item.currency == "AED"


def test_generate_rejects_duplicate(db_session: Session):
    contract_id = _make_contract(db_session, number="003")
    _add_installments(db_session, contract_id)

    svc = ReceivableService(db_session)
    svc.generate_for_contract(contract_id)

    with pytest.raises(HTTPException) as exc_info:
        svc.generate_for_contract(contract_id)
    assert exc_info.value.status_code == 409


def test_generate_raises_404_for_missing_contract(db_session: Session):
    svc = ReceivableService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.generate_for_contract("non-existent-contract-id")
    assert exc_info.value.status_code == 404


def test_generate_raises_404_when_no_installments(db_session: Session):
    contract_id = _make_contract(db_session, number="004")
    # No installments added

    svc = ReceivableService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.generate_for_contract(contract_id)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Status derivation tests
# ---------------------------------------------------------------------------


def test_status_pending_for_future_due_date(db_session: Session):
    contract_id = _make_contract(db_session, number="010")
    _add_installments(db_session, contract_id, start_date=date(2099, 1, 1))

    svc = ReceivableService(db_session)
    result = svc.generate_for_contract(contract_id)

    assert all(item.status == ReceivableStatus.PENDING.value for item in result.items)


def test_status_overdue_for_past_due_date(db_session: Session):
    contract_id = _make_contract(db_session, number="011")
    # All installments due in the past
    _add_installments(db_session, contract_id, start_date=date(2020, 1, 1))

    svc = ReceivableService(db_session)
    result = svc.generate_for_contract(contract_id)

    assert all(item.status == ReceivableStatus.OVERDUE.value for item in result.items)


def test_derive_status_paid_when_balance_zero():
    status = ReceivableService._derive_status(
        due_date=date(2026, 1, 1),
        paid_cents=10_000_000,
        due_cents=10_000_000,
        today=date(2026, 1, 15),
    )
    assert status == ReceivableStatus.PAID.value


def test_derive_status_partially_paid():
    status = ReceivableService._derive_status(
        due_date=date(2099, 1, 1),
        paid_cents=5_000_000,
        due_cents=10_000_000,
        today=date(2026, 1, 15),
    )
    assert status == ReceivableStatus.PARTIALLY_PAID.value


def test_derive_status_overdue_partially_paid():
    status = ReceivableService._derive_status(
        due_date=date(2020, 1, 1),
        paid_cents=5_000_000,
        due_cents=10_000_000,
        today=date(2026, 1, 15),
    )
    assert status == ReceivableStatus.OVERDUE.value


def test_derive_status_due_today():
    today = date.today()
    status = ReceivableService._derive_status(
        due_date=today,
        paid_cents=0,
        due_cents=10_000_000,
        today=today,
    )
    assert status == ReceivableStatus.DUE.value


# ---------------------------------------------------------------------------
# Listing tests
# ---------------------------------------------------------------------------


def test_list_contract_receivables(db_session: Session):
    contract_id = _make_contract(db_session, number="020")
    _add_installments(db_session, contract_id, count=4)

    svc = ReceivableService(db_session)
    svc.generate_for_contract(contract_id)

    result = svc.list_contract_receivables(contract_id)
    assert result.total == 4
    assert result.total_amount_due == pytest.approx(400_000.0)
    assert result.total_balance_due == pytest.approx(400_000.0)
    assert result.total_amount_paid == pytest.approx(0.0)


def test_list_contract_receivables_raises_404_for_missing_contract(db_session: Session):
    svc = ReceivableService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.list_contract_receivables("non-existent")
    assert exc_info.value.status_code == 404


def test_list_project_receivables(db_session: Session):
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit
    from app.modules.sales.models import Buyer, SalesContract

    # Build project with two contracts
    project = Project(name="Proj Rcv Test", code="PRJ-RCV-PROJ")
    db_session.add(project)
    db_session.flush()

    phase = Phase(project_id=project.id, name="Phase 1", sequence=1)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Blk", code="BLK")
    db_session.add(building)
    db_session.flush()

    floor = Floor(
        building_id=building.id, name="FL1", code="FL1", sequence_number=1
    )
    db_session.add(floor)
    db_session.flush()

    buyer = Buyer(full_name="Buyer", email="buyer-proj@test.com", phone="+1")
    db_session.add(buyer)
    db_session.flush()

    contract_ids = []
    for i in range(2):
        unit = Unit(
            floor_id=floor.id,
            unit_number=f"U{i+1}",
            unit_type="studio",
            internal_area=80.0,
        )
        db_session.add(unit)
        db_session.flush()

        contract = SalesContract(
            unit_id=unit.id,
            buyer_id=buyer.id,
            contract_number=f"CNT-RCV-PROJ-00{i+1}",
            contract_date=date(2026, 1, 1),
            contract_price=200_000.0,
        )
        db_session.add(contract)
        db_session.flush()
        contract_ids.append(contract.id)

    db_session.commit()

    svc = ReceivableService(db_session)
    for cid in contract_ids:
        _add_installments(db_session, cid, count=2)
        svc.generate_for_contract(cid)

    result = svc.list_project_receivables(project.id)
    assert result.total == 4  # 2 contracts × 2 installments


# ---------------------------------------------------------------------------
# Payment update tests
# ---------------------------------------------------------------------------


def test_payment_update_recalculates_balance_and_status(db_session: Session):
    contract_id = _make_contract(db_session, number="030")
    _add_installments(db_session, contract_id, count=1, start_date=date(2099, 1, 1))

    svc = ReceivableService(db_session)
    gen = svc.generate_for_contract(contract_id)
    receivable_id = gen.items[0].id

    # Partial payment
    result = svc.apply_payment_update(
        receivable_id,
        ReceivablePaymentUpdate(amount_paid=50_000.0),
    )
    assert result.amount_paid == pytest.approx(50_000.0)
    assert result.balance_due == pytest.approx(50_000.0)
    assert result.status == ReceivableStatus.PARTIALLY_PAID.value


def test_payment_update_full_payment_marks_paid(db_session: Session):
    contract_id = _make_contract(db_session, number="031")
    _add_installments(db_session, contract_id, count=1, start_date=date(2099, 1, 1))

    svc = ReceivableService(db_session)
    gen = svc.generate_for_contract(contract_id)
    receivable_id = gen.items[0].id

    result = svc.apply_payment_update(
        receivable_id,
        ReceivablePaymentUpdate(amount_paid=100_000.0),
    )
    assert result.balance_due == pytest.approx(0.0)
    assert result.status == ReceivableStatus.PAID.value


def test_payment_update_rejects_overpayment(db_session: Session):
    contract_id = _make_contract(db_session, number="032")
    _add_installments(db_session, contract_id, count=1, start_date=date(2099, 1, 1))

    svc = ReceivableService(db_session)
    gen = svc.generate_for_contract(contract_id)
    receivable_id = gen.items[0].id

    with pytest.raises(HTTPException) as exc_info:
        svc.apply_payment_update(
            receivable_id,
            ReceivablePaymentUpdate(amount_paid=200_000.0),
        )
    assert exc_info.value.status_code == 422


def test_payment_update_raises_404_for_missing_receivable(db_session: Session):
    svc = ReceivableService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.apply_payment_update(
            "non-existent",
            ReceivablePaymentUpdate(amount_paid=0.0),
        )
    assert exc_info.value.status_code == 404


def test_get_receivable_raises_404_for_missing(db_session: Session):
    svc = ReceivableService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.get_receivable("non-existent")
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# PR-CURRENCY-002A: receivables inherit installment currency
# ---------------------------------------------------------------------------


def test_receivables_inherit_jod_installment_currency(db_session: Session):
    """Receivables must be denominated in JOD when installments are JOD."""
    contract_id = _make_contract(db_session, project_code="PRJ-RCV-JOD", number="j01", currency="JOD")
    _add_installments(db_session, contract_id, count=2, currency="JOD")
    svc = ReceivableService(db_session)
    result = svc.generate_for_contract(contract_id)
    for item in result.items:
        assert item.currency == "JOD", f"Expected JOD, got {item.currency!r}"


def test_receivables_inherit_usd_installment_currency(db_session: Session):
    """Receivables must be denominated in USD when installments are USD."""
    contract_id = _make_contract(db_session, project_code="PRJ-RCV-USD", number="u01", currency="USD")
    _add_installments(db_session, contract_id, count=2, currency="USD")
    svc = ReceivableService(db_session)
    result = svc.generate_for_contract(contract_id)
    for item in result.items:
        assert item.currency == "USD", f"Expected USD, got {item.currency!r}"


def test_receivables_fall_back_to_default_when_installment_currency_missing(db_session: Session):
    """Receivables fall back to DEFAULT_CURRENCY when installment has no currency attribute."""
    from app.core.constants.currency import DEFAULT_CURRENCY
    from app.modules.payment_plans.models import PaymentSchedule

    contract_id = _make_contract(db_session, project_code="PRJ-RCV-FBACK", number="fb1")
    # Create installment without explicit currency (relies on DB/ORM default)
    inst = PaymentSchedule(
        contract_id=contract_id,
        installment_number=1,
        due_date=date(2026, 3, 1),
        due_amount=50_000.0,
        status="pending",
    )
    db_session.add(inst)
    db_session.commit()

    svc = ReceivableService(db_session)
    result = svc.generate_for_contract(contract_id)
    assert result.items[0].currency == DEFAULT_CURRENCY
