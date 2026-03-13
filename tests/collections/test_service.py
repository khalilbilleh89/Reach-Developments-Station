"""
Tests for the collections service layer.

Validates receipt recording, overpayment rejection, and receivable status
derivation in real estate payment workflows.
"""

import pytest
from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.collections.schemas import PaymentReceiptCreate
from app.modules.collections.service import CollectionsService
from app.modules.payment_plans.schemas import (
    PaymentPlanGenerateRequest,
    PaymentPlanTemplateCreate,
)
from app.modules.payment_plans.service import PaymentPlanService
from app.shared.enums.finance import (
    InstallmentFrequency,
    PaymentMethod,
    ReceivableStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_unit(db: Session, project_code: str = "PRJ-COL-SVC") -> str:
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit

    project = Project(name="Collections Service Project", code=project_code)
    db.add(project)
    db.flush()

    phase = Phase(project_id=project.id, name="Phase 1", sequence=1)
    db.add(phase)
    db.flush()

    building = Building(phase_id=phase.id, name="Block A", code="BLK-A")
    db.add(building)
    db.flush()

    floor = Floor(building_id=building.id, level=1)
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
    project_code: str = "PRJ-COL-SVC",
    contract_price: float = 200_000.0,
) -> str:
    from app.modules.sales.models import Buyer, SalesContract

    unit_id = _make_unit(db, project_code)

    buyer = Buyer(
        full_name="Collections Buyer",
        email=f"col-{project_code}@test.com",
        phone="+1",
    )
    db.add(buyer)
    db.flush()

    contract = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer.id,
        contract_number=f"CNT-{project_code}-001",
        contract_date=date(2026, 1, 1),
        contract_price=contract_price,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract.id


def _make_schedule(
    db: Session,
    contract_id: str,
    down_payment_percent: float = 10.0,
    number_of_installments: int = 3,
    start_date: date = date(2026, 1, 1),
) -> list:
    """Create a payment plan template + generate schedule. Returns schedule items."""
    pp_svc = PaymentPlanService(db)
    template = pp_svc.create_template(
        PaymentPlanTemplateCreate(
            name="Col Test Plan",
            down_payment_percent=down_payment_percent,
            number_of_installments=number_of_installments,
            installment_frequency=InstallmentFrequency.MONTHLY,
        )
    )
    result = pp_svc.generate_schedule_for_contract(
        PaymentPlanGenerateRequest(
            contract_id=contract_id,
            template_id=template.id,
            start_date=start_date,
        )
    )
    return result.items


# ---------------------------------------------------------------------------
# Receipt recording — valid cases
# ---------------------------------------------------------------------------


def test_record_valid_receipt(db_session: Session):
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-REC-VALID")
    schedule = _make_schedule(db_session, contract_id)
    first_line = schedule[0]

    receipt = svc.record_receipt(
        PaymentReceiptCreate(
            contract_id=contract_id,
            payment_schedule_id=first_line.id,
            receipt_date=date(2026, 1, 10),
            amount_received=first_line.due_amount,
        )
    )

    assert receipt.id
    assert receipt.contract_id == contract_id
    assert receipt.payment_schedule_id == first_line.id
    assert receipt.amount_received == pytest.approx(first_line.due_amount)
    assert receipt.status.value == "recorded"


def test_record_receipt_with_payment_method(db_session: Session):
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-REC-MTH")
    schedule = _make_schedule(db_session, contract_id)
    first_line = schedule[0]

    receipt = svc.record_receipt(
        PaymentReceiptCreate(
            contract_id=contract_id,
            payment_schedule_id=first_line.id,
            receipt_date=date(2026, 1, 15),
            amount_received=first_line.due_amount,
            payment_method=PaymentMethod.BANK_TRANSFER,
            reference_number="REF-2026-001",
            notes="Test payment",
        )
    )
    assert receipt.payment_method == PaymentMethod.BANK_TRANSFER
    assert receipt.reference_number == "REF-2026-001"


def test_partial_payment_allowed(db_session: Session):
    """Partial receipts are allowed as long as total does not exceed due amount."""
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-PARTIAL")
    schedule = _make_schedule(db_session, contract_id)
    first_line = schedule[0]
    partial = round(first_line.due_amount / 2, 2)

    receipt = svc.record_receipt(
        PaymentReceiptCreate(
            contract_id=contract_id,
            payment_schedule_id=first_line.id,
            receipt_date=date(2026, 1, 5),
            amount_received=partial,
        )
    )
    assert receipt.amount_received == pytest.approx(partial)


def test_get_receipt_by_id(db_session: Session):
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-GET-RCPT")
    schedule = _make_schedule(db_session, contract_id)
    first_line = schedule[0]

    created = svc.record_receipt(
        PaymentReceiptCreate(
            contract_id=contract_id,
            payment_schedule_id=first_line.id,
            receipt_date=date(2026, 1, 5),
            amount_received=first_line.due_amount,
        )
    )
    fetched = svc.get_receipt(created.id)
    assert fetched.id == created.id


def test_get_receipt_not_found(db_session: Session):
    svc = CollectionsService(db_session)
    with pytest.raises(HTTPException) as exc:
        svc.get_receipt("no-such-receipt")
    assert exc.value.status_code == 404


def test_list_receipts_for_contract(db_session: Session):
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-LIST-RCPT")
    schedule = _make_schedule(db_session, contract_id)

    for line in schedule[:2]:
        svc.record_receipt(
            PaymentReceiptCreate(
                contract_id=contract_id,
                payment_schedule_id=line.id,
                receipt_date=date(2026, 1, 10),
                amount_received=line.due_amount,
            )
        )

    result = svc.get_receipts_for_contract(contract_id)
    assert result.total == 2
    assert result.total_received == pytest.approx(
        sum(line.due_amount for line in schedule[:2])
    )


# ---------------------------------------------------------------------------
# Receipt recording — invalid cases
# ---------------------------------------------------------------------------


def test_reject_invalid_contract(db_session: Session):
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-REJ-CNT")
    schedule = _make_schedule(db_session, contract_id)
    first_line = schedule[0]

    with pytest.raises(HTTPException) as exc:
        svc.record_receipt(
            PaymentReceiptCreate(
                contract_id="no-such-contract",
                payment_schedule_id=first_line.id,
                receipt_date=date(2026, 1, 5),
                amount_received=100.0,
            )
        )
    assert exc.value.status_code == 404


def test_reject_invalid_schedule_line(db_session: Session):
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-REJ-SCHED")
    _make_schedule(db_session, contract_id)

    with pytest.raises(HTTPException) as exc:
        svc.record_receipt(
            PaymentReceiptCreate(
                contract_id=contract_id,
                payment_schedule_id="no-such-schedule",
                receipt_date=date(2026, 1, 5),
                amount_received=100.0,
            )
        )
    assert exc.value.status_code == 404


def test_reject_schedule_belonging_to_another_contract(db_session: Session):
    svc = CollectionsService(db_session)

    contract_a = _make_contract(db_session, "PRJ-CROSS-A")
    contract_b = _make_contract(db_session, "PRJ-CROSS-B")

    schedule_a = _make_schedule(db_session, contract_a)
    _make_schedule(db_session, contract_b)

    # contract_b + schedule line from contract_a → must be rejected
    with pytest.raises(HTTPException) as exc:
        svc.record_receipt(
            PaymentReceiptCreate(
                contract_id=contract_b,
                payment_schedule_id=schedule_a[0].id,
                receipt_date=date(2026, 1, 5),
                amount_received=100.0,
            )
        )
    assert exc.value.status_code == 422
    assert "does not belong" in exc.value.detail


def test_reject_overpayment(db_session: Session):
    """Total receipts must not exceed the due amount for a schedule line."""
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-OVERPAY")
    schedule = _make_schedule(db_session, contract_id)
    first_line = schedule[0]

    # First receipt — fully settles the line
    svc.record_receipt(
        PaymentReceiptCreate(
            contract_id=contract_id,
            payment_schedule_id=first_line.id,
            receipt_date=date(2026, 1, 5),
            amount_received=first_line.due_amount,
        )
    )

    # Second receipt — would cause overpayment
    with pytest.raises(HTTPException) as exc:
        svc.record_receipt(
            PaymentReceiptCreate(
                contract_id=contract_id,
                payment_schedule_id=first_line.id,
                receipt_date=date(2026, 1, 10),
                amount_received=1.0,
            )
        )
    assert exc.value.status_code == 422
    assert "exceed" in exc.value.detail.lower() or "overpay" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# Receivables view — status derivation
# ---------------------------------------------------------------------------


def test_receivables_pending_status(db_session: Session):
    """Schedule lines with no receipts and future due dates should be pending."""
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-RECV-PEND")
    # Start date far in the future so lines won't be overdue
    _make_schedule(db_session, contract_id, start_date=date(2030, 1, 1))

    result = svc.get_receivables_for_contract(contract_id)
    assert len(result.items) > 0
    for item in result.items:
        assert item.receivable_status == ReceivableStatus.PENDING
        assert item.outstanding_amount == pytest.approx(item.due_amount)
        assert item.total_received == 0.0


def test_receivables_partially_paid_status(db_session: Session):
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-RECV-PART")
    schedule = _make_schedule(db_session, contract_id, start_date=date(2030, 1, 1))
    first_line = schedule[0]
    partial = round(first_line.due_amount / 2, 2)

    svc.record_receipt(
        PaymentReceiptCreate(
            contract_id=contract_id,
            payment_schedule_id=first_line.id,
            receipt_date=date(2026, 1, 5),
            amount_received=partial,
        )
    )

    result = svc.get_receivables_for_contract(contract_id)
    first = result.items[0]
    assert first.receivable_status == ReceivableStatus.PARTIALLY_PAID
    assert first.total_received == pytest.approx(partial)
    assert first.outstanding_amount == pytest.approx(first_line.due_amount - partial)


def test_receivables_paid_status(db_session: Session):
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-RECV-PAID")
    schedule = _make_schedule(db_session, contract_id, start_date=date(2030, 1, 1))
    first_line = schedule[0]

    svc.record_receipt(
        PaymentReceiptCreate(
            contract_id=contract_id,
            payment_schedule_id=first_line.id,
            receipt_date=date(2026, 1, 5),
            amount_received=first_line.due_amount,
        )
    )

    result = svc.get_receivables_for_contract(contract_id)
    first = result.items[0]
    assert first.receivable_status == ReceivableStatus.PAID
    assert first.outstanding_amount == pytest.approx(0.0)
    assert first.total_received == pytest.approx(first_line.due_amount)


def test_receivables_overdue_status(db_session: Session):
    """Unpaid lines with past due dates must be flagged as overdue."""
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-RECV-OVRD")
    # Use a past start date so the first installment is overdue
    past_date = date.today() - timedelta(days=30)
    _make_schedule(db_session, contract_id, start_date=past_date)

    result = svc.get_receivables_for_contract(contract_id)
    # At least the first line should be overdue
    first = result.items[0]
    assert first.receivable_status == ReceivableStatus.OVERDUE


def test_receivables_totals(db_session: Session):
    """Contract-level totals must equal the sum of line-level values."""
    svc = CollectionsService(db_session)
    contract_id = _make_contract(db_session, "PRJ-RECV-TOT", contract_price=300_000.0)
    schedule = _make_schedule(
        db_session, contract_id, start_date=date(2030, 1, 1), number_of_installments=3
    )
    # Pay first two lines fully
    for line in schedule[:2]:
        svc.record_receipt(
            PaymentReceiptCreate(
                contract_id=contract_id,
                payment_schedule_id=line.id,
                receipt_date=date(2026, 1, 10),
                amount_received=line.due_amount,
            )
        )

    result = svc.get_receivables_for_contract(contract_id)
    assert result.total_due == pytest.approx(300_000.0, abs=0.02)
    assert result.total_received == pytest.approx(
        sum(line.due_amount for line in schedule[:2]), abs=0.02
    )
    assert result.total_outstanding == pytest.approx(
        result.total_due - result.total_received, abs=0.02
    )


def test_receivables_invalid_contract(db_session: Session):
    svc = CollectionsService(db_session)
    with pytest.raises(HTTPException) as exc:
        svc.get_receivables_for_contract("no-such-contract")
    assert exc.value.status_code == 404


def test_receipts_for_contract_invalid_contract(db_session: Session):
    svc = CollectionsService(db_session)
    with pytest.raises(HTTPException) as exc:
        svc.get_receipts_for_contract("no-such-contract")
    assert exc.value.status_code == 404
