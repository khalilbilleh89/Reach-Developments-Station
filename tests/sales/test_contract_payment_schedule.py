"""
Tests for the contract payment schedule engine.

PR-16: ContractPaymentService — schedule generation, payment recording,
overdue marking, and edge cases.
"""

import pytest
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.pricing.schemas import UnitPricingAttributesCreate
from app.modules.sales.schemas import (
    BuyerCreate,
    ContractPaymentRecordRequest,
    ReservationCreate,
    SalesContractCreate,
)
from app.modules.sales.service import ContractPaymentService, SalesService
from app.shared.enums.sales import ContractPaymentStatus, ContractStatus, ReservationStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_unit(db: Session, project_code: str = "PRJ-CPS") -> str:
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit

    project = Project(name="CPS Project", code=project_code)
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


def _set_pricing(db: Session, unit_id: str) -> None:
    from app.modules.pricing.service import PricingService

    PricingService(db).set_pricing_attributes(
        unit_id,
        UnitPricingAttributesCreate(
            base_price_per_sqm=5000.0,
            floor_premium=0.0,
            view_premium=0.0,
            corner_premium=0.0,
            size_adjustment=0.0,
            custom_adjustment=0.0,
        ),
    )


def _make_buyer(db: Session, email: str = "buyer@cps.com") -> str:
    svc = SalesService(db)
    return svc.create_buyer(
        BuyerCreate(full_name="CPS Buyer", email=email, phone="+9620000099")
    ).id


_CONTRACT_DATE = date(2026, 3, 13)
_CONTRACT_PRICE = 400_000.0


def _create_active_contract(
    db: Session,
    project_code: str = "PRJ-CPS",
    email: str = "buyer@cps.com",
) -> str:
    """Create a full sales workflow and activate the contract. Returns contract_id."""
    unit_id = _make_unit(db, project_code)
    _set_pricing(db, unit_id)
    buyer_id = _make_buyer(db, email)
    svc = SalesService(db)

    # Create reservation and convert it to a contract
    res = svc.create_reservation(
        ReservationCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            reservation_date=_CONTRACT_DATE,
            expiry_date=_CONTRACT_DATE + timedelta(days=30),
        )
    )
    contract = svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            reservation_id=res.id,
            contract_number=f"CNT-{project_code}",
            contract_date=_CONTRACT_DATE,
            contract_price=_CONTRACT_PRICE,
        )
    )
    svc.activate_contract(contract.id)
    return contract.id


# ---------------------------------------------------------------------------
# Schedule generation on contract activation
# ---------------------------------------------------------------------------


def test_activate_contract_generates_schedule(db_session: Session):
    """Activating a contract must auto-generate 4 default installments."""
    contract_id = _create_active_contract(db_session)
    svc = ContractPaymentService(db_session)
    result = svc.list_schedule(contract_id)

    assert result.total == 4
    assert len(result.items) == 4


def test_schedule_installment_numbers_are_sequential(db_session: Session):
    """Installment numbers must run 1, 2, 3, 4."""
    contract_id = _create_active_contract(db_session, "PRJ-SEQ", "seq@cps.com")
    svc = ContractPaymentService(db_session)
    items = svc.list_schedule(contract_id).items

    assert [i.installment_number for i in items] == [1, 2, 3, 4]


def test_schedule_total_matches_contract_price(db_session: Session):
    """Sum of all installment amounts must equal the contract price."""
    contract_id = _create_active_contract(db_session, "PRJ-TOT", "tot@cps.com")
    svc = ContractPaymentService(db_session)
    items = svc.list_schedule(contract_id).items

    total = sum(i.amount for i in items)
    assert abs(total - _CONTRACT_PRICE) < 0.02  # allow minor rounding


def test_schedule_percentages(db_session: Session):
    """Default milestones are 10%, 20%, 40%, 30% of the contract price."""
    contract_id = _create_active_contract(db_session, "PRJ-PCT", "pct@cps.com")
    svc = ContractPaymentService(db_session)
    items = svc.list_schedule(contract_id).items

    expected = [
        round(_CONTRACT_PRICE * 0.10, 2),
        round(_CONTRACT_PRICE * 0.20, 2),
        round(_CONTRACT_PRICE * 0.40, 2),
        round(_CONTRACT_PRICE * 0.30, 2),
    ]
    for item, exp in zip(items, expected):
        assert abs(item.amount - exp) < 0.02


def test_schedule_due_dates_are_ordered(db_session: Session):
    """Due dates must be in ascending order (no regressions)."""
    contract_id = _create_active_contract(db_session, "PRJ-ORD", "ord@cps.com")
    svc = ContractPaymentService(db_session)
    items = svc.list_schedule(contract_id).items

    dates = [i.due_date for i in items]
    assert dates == sorted(dates)


def test_schedule_initial_status_is_pending(db_session: Session):
    """All newly generated installments must have PENDING status."""
    contract_id = _create_active_contract(db_session, "PRJ-STS", "sts@cps.com")
    svc = ContractPaymentService(db_session)
    items = svc.list_schedule(contract_id).items

    for item in items:
        assert item.status == ContractPaymentStatus.PENDING


# ---------------------------------------------------------------------------
# list_schedule
# ---------------------------------------------------------------------------


def test_list_schedule_contract_not_found(db_session: Session):
    svc = ContractPaymentService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.list_schedule("no-such-contract")
    assert exc_info.value.status_code == 404


def test_list_schedule_empty_when_no_schedule(db_session: Session):
    """A draft contract has no schedule yet."""
    unit_id = _make_unit(db_session, "PRJ-LST")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "lst@cps.com")
    sales_svc = SalesService(db_session)
    contract = sales_svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            contract_number="CNT-LST",
            contract_date=_CONTRACT_DATE,
            contract_price=100_000.0,
        )
    )
    svc = ContractPaymentService(db_session)
    result = svc.list_schedule(contract.id)
    assert result.total == 0
    assert result.items == []


# ---------------------------------------------------------------------------
# generate_payment_schedule (explicit API endpoint)
# ---------------------------------------------------------------------------


def test_generate_payment_schedule_creates_schedule(db_session: Session):
    """POST generate-payment-schedule creates installments for a contract."""
    unit_id = _make_unit(db_session, "PRJ-GEN")
    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "gen@cps.com")
    sales_svc = SalesService(db_session)
    contract = sales_svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            contract_number="CNT-GEN",
            contract_date=_CONTRACT_DATE,
            contract_price=200_000.0,
        )
    )
    svc = ContractPaymentService(db_session)
    result = svc.generate_payment_schedule(contract.id)
    assert result.total == 4
    total = sum(i.amount for i in result.items)
    assert abs(total - 200_000.0) < 0.02


def test_generate_payment_schedule_conflicts_when_exists(db_session: Session):
    """Generating a schedule when one already exists must return 409."""
    contract_id = _create_active_contract(db_session, "PRJ-DUP", "dup@cps.com")
    svc = ContractPaymentService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.generate_payment_schedule(contract_id)
    assert exc_info.value.status_code == 409


def test_generate_payment_schedule_contract_not_found(db_session: Session):
    svc = ContractPaymentService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.generate_payment_schedule("no-such-contract")
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# record_payment
# ---------------------------------------------------------------------------


def test_record_payment_marks_installment_paid(db_session: Session):
    contract_id = _create_active_contract(db_session, "PRJ-PAY", "pay@cps.com")
    svc = ContractPaymentService(db_session)
    result = svc.record_payment(
        contract_id,
        ContractPaymentRecordRequest(
            installment_number=1,
            payment_reference="REF-001",
        ),
    )
    assert result.status == ContractPaymentStatus.PAID
    assert result.payment_reference == "REF-001"
    assert result.paid_at is not None


def test_record_payment_with_explicit_paid_at(db_session: Session):
    contract_id = _create_active_contract(db_session, "PRJ-PAT", "pat@cps.com")
    paid_ts = datetime(2026, 3, 14, 10, 0, 0, tzinfo=timezone.utc)
    svc = ContractPaymentService(db_session)
    result = svc.record_payment(
        contract_id,
        ContractPaymentRecordRequest(installment_number=1, paid_at=paid_ts),
    )
    assert result.status == ContractPaymentStatus.PAID
    assert result.paid_at is not None


def test_record_payment_duplicate_raises_409(db_session: Session):
    """Attempting to pay an already-paid installment must return 409."""
    contract_id = _create_active_contract(db_session, "PRJ-DPY", "dpy@cps.com")
    svc = ContractPaymentService(db_session)
    svc.record_payment(contract_id, ContractPaymentRecordRequest(installment_number=1))
    with pytest.raises(HTTPException) as exc_info:
        svc.record_payment(
            contract_id, ContractPaymentRecordRequest(installment_number=1)
        )
    assert exc_info.value.status_code == 409


def test_record_payment_contract_not_found(db_session: Session):
    svc = ContractPaymentService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.record_payment(
            "no-such-contract",
            ContractPaymentRecordRequest(installment_number=1),
        )
    assert exc_info.value.status_code == 404


def test_record_payment_installment_not_found(db_session: Session):
    contract_id = _create_active_contract(db_session, "PRJ-INF", "inf@cps.com")
    svc = ContractPaymentService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.record_payment(
            contract_id,
            ContractPaymentRecordRequest(installment_number=99),
        )
    assert exc_info.value.status_code == 404


def test_record_payment_cancelled_raises_409(db_session: Session):
    """A cancelled installment cannot be paid."""
    contract_id = _create_active_contract(db_session, "PRJ-CAN", "can@cps.com")
    svc = ContractPaymentService(db_session)
    # Manually cancel the first installment via direct ORM manipulation
    from app.modules.sales.repository import ContractPaymentScheduleRepository

    repo = ContractPaymentScheduleRepository(db_session)
    item = repo.get_by_contract_and_installment(contract_id, 1)
    assert item is not None
    item.status = ContractPaymentStatus.CANCELLED.value
    repo.save(item)

    with pytest.raises(HTTPException) as exc_info:
        svc.record_payment(
            contract_id, ContractPaymentRecordRequest(installment_number=1)
        )
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# mark_overdue
# ---------------------------------------------------------------------------


def test_mark_overdue_updates_past_due_installments(db_session: Session):
    """Pending installments whose due_date is before today must become OVERDUE."""
    contract_id = _create_active_contract(db_session, "PRJ-OVR", "ovr@cps.com")
    svc = ContractPaymentService(db_session)

    # Manually backdate all due_dates to make them overdue
    from app.modules.sales.repository import ContractPaymentScheduleRepository

    repo = ContractPaymentScheduleRepository(db_session)
    items = repo.list_by_contract(contract_id)
    for item in items:
        item.due_date = date(2020, 1, 1)
    db_session.commit()

    result = svc.mark_overdue(contract_id)
    for item in result.items:
        assert item.status == ContractPaymentStatus.OVERDUE


def test_mark_overdue_skips_paid_installments(db_session: Session):
    """Paid installments must not be changed to OVERDUE."""
    contract_id = _create_active_contract(db_session, "PRJ-OVP", "ovp@cps.com")
    svc = ContractPaymentService(db_session)

    # Pay first installment
    svc.record_payment(contract_id, ContractPaymentRecordRequest(installment_number=1))

    # Backdate all due_dates
    from app.modules.sales.repository import ContractPaymentScheduleRepository

    repo = ContractPaymentScheduleRepository(db_session)
    items = repo.list_by_contract(contract_id)
    for item in items:
        item.due_date = date(2020, 1, 1)
    db_session.commit()

    result = svc.mark_overdue(contract_id)
    statuses = {i.installment_number: i.status for i in result.items}
    assert statuses[1] == ContractPaymentStatus.PAID
    for n in [2, 3, 4]:
        assert statuses[n] == ContractPaymentStatus.OVERDUE


def test_mark_overdue_contract_not_found(db_session: Session):
    svc = ContractPaymentService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.mark_overdue("no-such-contract")
    assert exc_info.value.status_code == 404


def test_mark_overdue_noop_for_future_dates(db_session: Session):
    """Installments with future due_dates must remain PENDING."""
    from datetime import date as date_cls
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit

    project = Project(name="FUT Project", code="PRJ-FUT2")
    db_session.add(project)
    db_session.flush()
    phase = Phase(project_id=project.id, name="Phase 1", sequence=1)
    db_session.add(phase)
    db_session.flush()
    building = Building(phase_id=phase.id, name="Block A", code="BLK-A")
    db_session.add(building)
    db_session.flush()
    floor = Floor(building_id=building.id, name="Floor 1", code="FL-01", sequence_number=1)
    db_session.add(floor)
    db_session.flush()
    unit = Unit(floor_id=floor.id, unit_number="101", unit_type="studio", internal_area=100.0)
    db_session.add(unit)
    db_session.commit()
    db_session.refresh(unit)
    unit_id = unit.id

    _set_pricing(db_session, unit_id)
    buyer_id = _make_buyer(db_session, "fut2@cps.com")
    sales_svc = SalesService(db_session)

    # Use a future contract date so all due_dates are also future
    future_date = date_cls.today() + timedelta(days=30)
    contract = sales_svc.create_contract(
        SalesContractCreate(
            unit_id=unit_id,
            buyer_id=buyer_id,
            contract_number="CNT-FUT2",
            contract_date=future_date,
            contract_price=100_000.0,
        )
    )
    # Generate schedule manually since no reservation means no activation
    pay_svc = ContractPaymentService(db_session)
    pay_svc.generate_payment_schedule(contract.id)

    result = pay_svc.mark_overdue(contract.id)
    for item in result.items:
        assert item.status == ContractPaymentStatus.PENDING


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_activating_contract_twice_does_not_duplicate_schedule(db_session: Session):
    """Double-activating a contract (shouldn't be possible via API, but test the
    guard in _generate_default_payment_schedule) must not duplicate installments."""
    contract_id = _create_active_contract(db_session, "PRJ-DBL", "dbl@cps.com")
    svc = ContractPaymentService(db_session)

    # Attempt direct double-generation (simulates race-condition guard)
    from app.modules.sales.service import SalesService as SS
    from app.modules.sales.repository import SalesContractRepository

    repo = SalesContractRepository(db_session)
    contract = repo.get_by_id(contract_id)
    ss = SS(db_session)
    ss._generate_default_payment_schedule(contract)  # type: ignore[attr-defined]

    result = svc.list_schedule(contract_id)
    assert result.total == 4


def test_schedule_currency_defaults_to_aed(db_session: Session):
    contract_id = _create_active_contract(db_session, "PRJ-AED", "aed@cps.com")
    svc = ContractPaymentService(db_session)
    items = svc.list_schedule(contract_id).items
    for item in items:
        assert item.currency == "AED"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


def test_api_get_payment_schedule(client):
    """GET /sales/contracts/{id}/payment-schedule returns 200 with items."""
    # Create a full workflow via the API client
    project_id = client.post(
        "/api/v1/projects", json={"name": "API CPS Project", "code": "PRJ-APIC"}
    ).json()["id"]
    phase_id = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    ).json()["id"]
    building_id = client.post(
        f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-A"}
    ).json()["id"]
    floor_id = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]
    unit_id = client.post(
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 100.0},
    ).json()["id"]
    client.post(
        f"/api/v1/pricing/unit/{unit_id}/attributes",
        json={
            "base_price_per_sqm": 5000.0,
            "floor_premium": 0.0,
            "view_premium": 0.0,
            "corner_premium": 0.0,
            "size_adjustment": 0.0,
            "custom_adjustment": 0.0,
        },
    )
    buyer_id = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "API Buyer", "email": "apic@cps.com", "phone": "+9620000999"},
    ).json()["id"]
    res_id = client.post(
        "/api/v1/sales/reservations",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "reservation_date": "2026-03-13",
            "expiry_date": "2026-04-13",
        },
    ).json()["id"]
    contract_id = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "reservation_id": res_id,
            "contract_number": "CNT-APIC",
            "contract_date": "2026-03-13",
            "contract_price": 300_000.0,
        },
    ).json()["id"]
    client.post(f"/api/v1/sales/contracts/{contract_id}/activate")

    resp = client.get(f"/api/v1/sales/contracts/{contract_id}/payment-schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert len(data["items"]) == 4


def test_api_record_payment(client):
    """POST /sales/contracts/{id}/payments records a payment."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "API PAY Project", "code": "PRJ-APAY"}
    ).json()["id"]
    phase_id = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    ).json()["id"]
    building_id = client.post(
        f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-A"}
    ).json()["id"]
    floor_id = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]
    unit_id = client.post(
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 100.0},
    ).json()["id"]
    client.post(
        f"/api/v1/pricing/unit/{unit_id}/attributes",
        json={
            "base_price_per_sqm": 5000.0,
            "floor_premium": 0.0,
            "view_premium": 0.0,
            "corner_premium": 0.0,
            "size_adjustment": 0.0,
            "custom_adjustment": 0.0,
        },
    )
    buyer_id = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "API Pay Buyer", "email": "apay@cps.com", "phone": "+9620000888"},
    ).json()["id"]
    res_id = client.post(
        "/api/v1/sales/reservations",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "reservation_date": "2026-03-13",
            "expiry_date": "2026-04-13",
        },
    ).json()["id"]
    contract_id = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "reservation_id": res_id,
            "contract_number": "CNT-APAY",
            "contract_date": "2026-03-13",
            "contract_price": 400_000.0,
        },
    ).json()["id"]
    client.post(f"/api/v1/sales/contracts/{contract_id}/activate")

    resp = client.post(
        f"/api/v1/sales/contracts/{contract_id}/payments",
        json={"installment_number": 1, "payment_reference": "REF-TEST"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "paid"
    assert data["payment_reference"] == "REF-TEST"
    assert data["paid_at"] is not None


def test_api_generate_payment_schedule(client):
    """POST /sales/contracts/{id}/generate-payment-schedule creates schedule."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "API GEN Project", "code": "PRJ-AGEN"}
    ).json()["id"]
    phase_id = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    ).json()["id"]
    building_id = client.post(
        f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-A"}
    ).json()["id"]
    floor_id = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]
    unit_id = client.post(
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 100.0},
    ).json()["id"]
    client.post(
        f"/api/v1/pricing/unit/{unit_id}/attributes",
        json={
            "base_price_per_sqm": 5000.0,
            "floor_premium": 0.0,
            "view_premium": 0.0,
            "corner_premium": 0.0,
            "size_adjustment": 0.0,
            "custom_adjustment": 0.0,
        },
    )
    buyer_id = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "API Gen Buyer", "email": "agen@cps.com", "phone": "+9620000777"},
    ).json()["id"]
    contract_id = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": "CNT-AGEN",
            "contract_date": "2026-03-13",
            "contract_price": 250_000.0,
        },
    ).json()["id"]

    resp = client.post(
        f"/api/v1/sales/contracts/{contract_id}/generate-payment-schedule"
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["total"] == 4
    total = sum(i["amount"] for i in data["items"])
    assert abs(total - 250_000.0) < 0.02


def test_api_payment_schedule_not_found(client):
    resp = client.get("/api/v1/sales/contracts/no-such-id/payment-schedule")
    assert resp.status_code == 404
