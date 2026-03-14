"""
Tests for the finance summary service layer.

Validates financial aggregation logic including:
  - contract value aggregation
  - collections aggregation
  - receivable calculation
  - collection ratio calculation
  - edge cases: project with no contracts, no receipts
"""

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.finance.service import FinanceSummaryService


# ---------------------------------------------------------------------------
# Helpers — build project hierarchy and financial fixtures in-memory
# ---------------------------------------------------------------------------


def _make_project(db: Session, code: str = "PRJ-FIN-SVC") -> str:
    from app.modules.projects.models import Project

    project = Project(name="Finance Service Project", code=code)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project.id


# Sequence counter to avoid phase unique constraint violations when multiple
# units are created under the same project.
_phase_seq: dict[str, int] = {}


def _make_unit(
    db: Session,
    project_id: str,
    unit_number: str = "101",
    status: str = "available",
) -> str:
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _phase_seq.get(project_id, 0) + 1
    _phase_seq[project_id] = seq

    phase = Phase(project_id=project_id, name=f"Phase {seq}", sequence=seq)
    db.add(phase)
    db.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"BLK-{unit_number}")
    db.add(building)
    db.flush()

    floor = Floor(building_id=building.id, level=1)
    db.add(floor)
    db.flush()

    unit = Unit(
        floor_id=floor.id,
        unit_number=unit_number,
        unit_type="studio",
        internal_area=100.0,
        status=status,
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit.id


def _make_contract(
    db: Session,
    unit_id: str,
    contract_price: float,
    contract_number: str = "CNT-001",
    email: str = "buyer@test.com",
) -> str:
    from app.modules.sales.models import Buyer, SalesContract
    from datetime import date

    buyer = Buyer(full_name="Test Buyer", email=email, phone="+9620000001")
    db.add(buyer)
    db.flush()

    contract = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer.id,
        contract_number=contract_number,
        contract_date=date(2026, 1, 1),
        contract_price=contract_price,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract.id


def _make_schedule_line(
    db: Session,
    contract_id: str,
    due_amount: float,
    installment_number: int = 1,
) -> str:
    from app.modules.payment_plans.models import PaymentSchedule
    from datetime import date

    line = PaymentSchedule(
        contract_id=contract_id,
        installment_number=installment_number,
        due_date=date(2030, 1, 1),
        due_amount=due_amount,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line.id


def _make_receipt(
    db: Session,
    contract_id: str,
    payment_schedule_id: str,
    amount_received: float,
) -> None:
    from app.modules.collections.models import PaymentReceipt
    from datetime import date

    receipt = PaymentReceipt(
        contract_id=contract_id,
        payment_schedule_id=payment_schedule_id,
        receipt_date=date(2026, 2, 1),
        amount_received=amount_received,
    )
    db.add(receipt)
    db.commit()


# ---------------------------------------------------------------------------
# Project existence validation
# ---------------------------------------------------------------------------


def test_get_project_summary_raises_404_for_missing_project(db_session: Session):
    service = FinanceSummaryService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.get_project_summary("no-such-project")
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Empty project (no units, no contracts, no receipts)
# ---------------------------------------------------------------------------


def test_get_project_summary_empty_project(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-EMPTY")
    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.project_id == project_id
    assert summary.total_units == 0
    assert summary.units_sold == 0
    assert summary.units_available == 0
    assert summary.total_contract_value == 0.0
    assert summary.total_collected == 0.0
    assert summary.total_receivable == 0.0
    assert summary.collection_ratio == 0.0
    assert summary.average_unit_price == 0.0


# ---------------------------------------------------------------------------
# Unit counts
# ---------------------------------------------------------------------------


def test_unit_counts_available_and_sold(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-CNT")

    # One available unit, one under_contract unit (sold)
    _make_unit(db_session, project_id, unit_number="101", status="available")
    _make_unit(db_session, project_id, unit_number="102", status="under_contract")

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.total_units == 2
    assert summary.units_available == 1
    assert summary.units_sold == 1


def test_registered_units_counted_as_sold(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-REG")
    _make_unit(db_session, project_id, unit_number="201", status="registered")

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.units_sold == 1
    assert summary.units_available == 0


# ---------------------------------------------------------------------------
# Contract value aggregation
# ---------------------------------------------------------------------------


def test_total_contract_value_single_contract(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-CV1")
    unit_id = _make_unit(db_session, project_id)
    _make_contract(db_session, unit_id, 500_000.0)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.total_contract_value == pytest.approx(500_000.0)


def test_total_contract_value_multiple_contracts(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-CV2")
    unit1_id = _make_unit(db_session, project_id, unit_number="101")
    unit2_id = _make_unit(db_session, project_id, unit_number="102")
    _make_contract(db_session, unit1_id, 300_000.0, "CNT-001", "b1@test.com")
    _make_contract(db_session, unit2_id, 200_000.0, "CNT-002", "b2@test.com")

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.total_contract_value == pytest.approx(500_000.0)


def test_no_contracts_gives_zero_contract_value(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-NCV")
    _make_unit(db_session, project_id)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.total_contract_value == 0.0


# ---------------------------------------------------------------------------
# Collections aggregation
# ---------------------------------------------------------------------------


def test_total_collected_single_receipt(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-COL1")
    unit_id = _make_unit(db_session, project_id)
    contract_id = _make_contract(db_session, unit_id, 100_000.0)
    schedule_id = _make_schedule_line(db_session, contract_id, 100_000.0)
    _make_receipt(db_session, contract_id, schedule_id, 25_000.0)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.total_collected == pytest.approx(25_000.0)


def test_total_collected_multiple_receipts(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-COL2")
    unit_id = _make_unit(db_session, project_id)
    contract_id = _make_contract(db_session, unit_id, 100_000.0)
    schedule_id = _make_schedule_line(db_session, contract_id, 100_000.0)
    _make_receipt(db_session, contract_id, schedule_id, 10_000.0)
    _make_receipt(db_session, contract_id, schedule_id, 15_000.0)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.total_collected == pytest.approx(25_000.0)


def test_no_receipts_gives_zero_collected(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-NOCOL")
    unit_id = _make_unit(db_session, project_id)
    _make_contract(db_session, unit_id, 100_000.0)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.total_collected == 0.0


# ---------------------------------------------------------------------------
# Receivable calculation
# ---------------------------------------------------------------------------


def test_total_receivable_equals_contract_minus_collected(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-RCV")
    unit_id = _make_unit(db_session, project_id)
    contract_id = _make_contract(db_session, unit_id, 200_000.0)
    schedule_id = _make_schedule_line(db_session, contract_id, 200_000.0)
    _make_receipt(db_session, contract_id, schedule_id, 50_000.0)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.total_receivable == pytest.approx(150_000.0)


def test_total_receivable_zero_when_fully_collected(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-RCVZ")
    unit_id = _make_unit(db_session, project_id)
    contract_id = _make_contract(db_session, unit_id, 100_000.0)
    schedule_id = _make_schedule_line(db_session, contract_id, 100_000.0)
    _make_receipt(db_session, contract_id, schedule_id, 100_000.0)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.total_receivable == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Collection ratio calculation
# ---------------------------------------------------------------------------


def test_collection_ratio_correct(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-RAT")
    unit_id = _make_unit(db_session, project_id)
    contract_id = _make_contract(db_session, unit_id, 200_000.0)
    schedule_id = _make_schedule_line(db_session, contract_id, 200_000.0)
    _make_receipt(db_session, contract_id, schedule_id, 50_000.0)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.collection_ratio == pytest.approx(0.25)


def test_collection_ratio_zero_when_no_contracts(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-RAT0")

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.collection_ratio == 0.0


def test_collection_ratio_one_when_fully_collected(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-RATF")
    unit_id = _make_unit(db_session, project_id)
    contract_id = _make_contract(db_session, unit_id, 100_000.0)
    schedule_id = _make_schedule_line(db_session, contract_id, 100_000.0)
    _make_receipt(db_session, contract_id, schedule_id, 100_000.0)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.collection_ratio == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Average unit price
# ---------------------------------------------------------------------------


def test_average_unit_price_with_contracts(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-AVG")
    unit1_id = _make_unit(db_session, project_id, unit_number="101")
    unit2_id = _make_unit(db_session, project_id, unit_number="102")
    _make_contract(db_session, unit1_id, 300_000.0, "CNT-A01", "a1@test.com")
    _make_contract(db_session, unit2_id, 100_000.0, "CNT-A02", "a2@test.com")

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.average_unit_price == pytest.approx(200_000.0)


def test_average_unit_price_zero_with_no_contracts(db_session: Session):
    project_id = _make_project(db_session, "PRJ-FIN-AVGZ")
    _make_unit(db_session, project_id)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.average_unit_price == 0.0


# ---------------------------------------------------------------------------
# Over-collection safety (clamping)
# ---------------------------------------------------------------------------


def test_total_receivable_clamped_to_zero_on_over_collection(db_session: Session):
    """When total_collected exceeds total_contract_value, total_receivable is 0."""
    project_id = _make_project(db_session, "PRJ-FIN-OVR1")
    unit_id = _make_unit(db_session, project_id)
    contract_id = _make_contract(db_session, unit_id, 100_000.0)
    schedule_id = _make_schedule_line(db_session, contract_id, 110_000.0)
    # Record more than the contract value (simulating adjusted/dirty data)
    _make_receipt(db_session, contract_id, schedule_id, 110_000.0)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.total_receivable == 0.0


def test_collection_ratio_clamped_to_one_on_over_collection(db_session: Session):
    """When total_collected > total_contract_value, collection_ratio does not exceed 1.0."""
    project_id = _make_project(db_session, "PRJ-FIN-OVR2")
    unit_id = _make_unit(db_session, project_id)
    contract_id = _make_contract(db_session, unit_id, 100_000.0)
    schedule_id = _make_schedule_line(db_session, contract_id, 120_000.0)
    _make_receipt(db_session, contract_id, schedule_id, 120_000.0)

    service = FinanceSummaryService(db_session)
    summary = service.get_project_summary(project_id)

    assert summary.collection_ratio <= 1.0
    assert summary.total_receivable >= 0.0
