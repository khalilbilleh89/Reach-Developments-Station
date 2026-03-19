"""
Smoke test: Sales Lifecycle

Verifies sequential creation through the commercial lifecycle:
  Project → Unit → Pricing attributes → Buyer → Reservation → Sales Contract → Payment Schedule

Assertions:
  - Contract references unit and buyer
  - Payment schedule references contract

Note: reservation and contract are created independently (no reservation_id linkage).
The test verifies that both resources are created successfully and reference the
correct unit/buyer, not that the reservation is converted on contract creation.
"""

from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_unit(client: TestClient, proj_code: str = "SMKS-001") -> str:
    """Create the full hierarchy and return the unit_id."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "Sales Smoke Project", "code": proj_code}
    ).json()["id"]
    phase_id = client.post(
        f"/api/v1/projects/{project_id}/phases",
        json={"name": "Phase 1", "sequence": 1},
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
        f"/api/v1/floors/{floor_id}/units",
        json={"unit_number": "101", "unit_type": "studio", "internal_area": 90.0},
    ).json()["id"]
    return unit_id


def _add_pricing(client: TestClient, unit_id: str) -> dict:
    resp = client.post(
        f"/api/v1/pricing/unit/{unit_id}/attributes",
        json={"base_price_per_sqm": 5000.0},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_buyer(client: TestClient, email: str = "smoke.buyer@example.com") -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Smoke Buyer", "email": email, "phone": "+9710000001"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_reservation(client: TestClient, unit_id: str, buyer_id: str) -> dict:
    resp = client.post(
        "/api/v1/sales/reservations",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "reservation_date": "2026-01-01",
            "expiry_date": "2026-03-01",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_contract(
    client: TestClient,
    unit_id: str,
    buyer_id: str,
    contract_number: str = "CNT-SMOKE-001",
) -> dict:
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": "2026-01-15",
            "contract_price": 500_000.0,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _generate_payment_schedule(client: TestClient, contract_id: str) -> dict:
    resp = client.post(
        "/api/v1/payment-plans",
        json={
            "contract_id": contract_id,
            "plan_name": "Standard 12-Month",
            "number_of_installments": 12,
            "start_date": "2026-02-01",
            "down_payment_percent": 10.0,
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_sales_lifecycle_contract_references_unit(client: TestClient):
    """Create full lifecycle; contract must reference the unit."""
    unit_id = _build_unit(client, "SMKS-001")
    buyer_id = _create_buyer(client, "smoke.a@example.com")
    contract = _create_contract(client, unit_id, buyer_id, "CNT-SMKS-A1")

    assert contract["unit_id"] == unit_id
    assert contract["buyer_id"] == buyer_id


def test_sales_lifecycle_payment_schedule_references_contract(client: TestClient):
    """Payment schedule items must all reference the contract."""
    unit_id = _build_unit(client, "SMKS-002")
    buyer_id = _create_buyer(client, "smoke.b@example.com")
    contract = _create_contract(client, unit_id, buyer_id, "CNT-SMKS-B1")

    plan = _generate_payment_schedule(client, contract["id"])

    assert plan["contract_id"] == contract["id"]
    assert plan["total_installments"] > 0
    for installment in plan["installments"]:
        assert installment["contract_id"] == contract["id"]


def test_sales_lifecycle_full_flow(client: TestClient):
    """Smoke: create unit → pricing attrs → buyer → reservation → contract → payment schedule.

    Reservation and contract are created independently; this verifies each step
    in the sequence succeeds and produces correctly-referenced records.
    """
    unit_id = _build_unit(client, "SMKS-003")
    _add_pricing(client, unit_id)
    buyer_id = _create_buyer(client, "smoke.c@example.com")
    reservation = _create_reservation(client, unit_id, buyer_id)
    contract = _create_contract(client, unit_id, buyer_id, "CNT-SMKS-C1")
    plan = _generate_payment_schedule(client, contract["id"])

    # Full chain assertions
    assert reservation["unit_id"] == unit_id
    assert reservation["buyer_id"] == buyer_id
    assert contract["unit_id"] == unit_id
    assert plan["contract_id"] == contract["id"]
    assert plan["total_installments"] >= 12
