"""
Tests for the receivables REST API endpoints.
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hierarchy(db: Session, project_code: str) -> str:
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit

    project = Project(name="API Receivables Project", code=project_code)
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


def _make_contract(db: Session, project_code: str, number: str = "001") -> str:
    from app.modules.sales.models import Buyer, SalesContract

    unit_id = _make_hierarchy(db, project_code)
    buyer = Buyer(
        full_name="API Buyer",
        email=f"api-rcv-{project_code}-{number}@test.com",
        phone="+1",
    )
    db.add(buyer)
    db.flush()

    contract = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer.id,
        contract_number=f"CNT-API-{project_code}-{number}",
        contract_date=date(2026, 1, 1),
        contract_price=300_000.0,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract.id


def _add_installments(db: Session, contract_id: str, count: int = 3) -> None:
    from app.modules.payment_plans.models import PaymentSchedule

    for i in range(1, count + 1):
        inst = PaymentSchedule(
            contract_id=contract_id,
            installment_number=i,
            due_date=date(2099, i if i <= 12 else 12, 1),
            due_amount=100_000.0,
            status="pending",
        )
        db.add(inst)
    db.commit()


# ---------------------------------------------------------------------------
# POST /api/v1/contracts/{contract_id}/receivables/generate
# ---------------------------------------------------------------------------


def test_generate_receivables_returns_201(client: TestClient, db_session: Session):
    contract_id = _make_contract(db_session, "API-RCV-01")
    _add_installments(db_session, contract_id, count=3)

    resp = client.post(
        f"/api/v1/contracts/{contract_id}/receivables/generate"
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["generated"] == 3
    assert data["contract_id"] == contract_id
    assert len(data["items"]) == 3


def test_generate_receivables_409_on_duplicate(client: TestClient, db_session: Session):
    contract_id = _make_contract(db_session, "API-RCV-02")
    _add_installments(db_session, contract_id, count=2)

    client.post(f"/api/v1/contracts/{contract_id}/receivables/generate")
    resp = client.post(f"/api/v1/contracts/{contract_id}/receivables/generate")
    assert resp.status_code == 409


def test_generate_receivables_404_missing_contract(client: TestClient, db_session: Session):
    resp = client.post("/api/v1/contracts/missing-contract/receivables/generate")
    assert resp.status_code == 404


def test_generate_receivables_404_no_installments(client: TestClient, db_session: Session):
    contract_id = _make_contract(db_session, "API-RCV-03")
    # No installments added

    resp = client.post(f"/api/v1/contracts/{contract_id}/receivables/generate")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/contracts/{contract_id}/receivables
# ---------------------------------------------------------------------------


def test_list_contract_receivables_returns_200(client: TestClient, db_session: Session):
    contract_id = _make_contract(db_session, "API-RCV-04")
    _add_installments(db_session, contract_id, count=2)

    client.post(f"/api/v1/contracts/{contract_id}/receivables/generate")
    resp = client.get(f"/api/v1/contracts/{contract_id}/receivables")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_contract_receivables_empty_before_generation(
    client: TestClient, db_session: Session
):
    contract_id = _make_contract(db_session, "API-RCV-05")
    resp = client.get(f"/api/v1/contracts/{contract_id}/receivables")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


# ---------------------------------------------------------------------------
# GET /api/v1/receivables/{receivable_id}
# ---------------------------------------------------------------------------


def test_get_receivable_returns_200(client: TestClient, db_session: Session):
    contract_id = _make_contract(db_session, "API-RCV-06")
    _add_installments(db_session, contract_id, count=1)

    gen_resp = client.post(
        f"/api/v1/contracts/{contract_id}/receivables/generate"
    )
    receivable_id = gen_resp.json()["items"][0]["id"]

    resp = client.get(f"/api/v1/receivables/{receivable_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == receivable_id
    assert data["contract_id"] == contract_id


def test_get_receivable_404_for_missing(client: TestClient, db_session: Session):
    resp = client.get("/api/v1/receivables/non-existent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/receivables/{receivable_id}
# ---------------------------------------------------------------------------


def test_patch_receivable_updates_amount_paid(client: TestClient, db_session: Session):
    contract_id = _make_contract(db_session, "API-RCV-07")
    _add_installments(db_session, contract_id, count=1)

    gen_resp = client.post(
        f"/api/v1/contracts/{contract_id}/receivables/generate"
    )
    receivable_id = gen_resp.json()["items"][0]["id"]

    resp = client.patch(
        f"/api/v1/receivables/{receivable_id}",
        json={"amount_paid": 50_000.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["amount_paid"] == pytest.approx(50_000.0)
    assert data["balance_due"] == pytest.approx(50_000.0)
    assert data["status"] == "partially_paid"


def test_patch_receivable_422_on_overpayment(client: TestClient, db_session: Session):
    contract_id = _make_contract(db_session, "API-RCV-08")
    _add_installments(db_session, contract_id, count=1)

    gen_resp = client.post(
        f"/api/v1/contracts/{contract_id}/receivables/generate"
    )
    receivable_id = gen_resp.json()["items"][0]["id"]

    resp = client.patch(
        f"/api/v1/receivables/{receivable_id}",
        json={"amount_paid": 500_000.0},
    )
    assert resp.status_code == 422
