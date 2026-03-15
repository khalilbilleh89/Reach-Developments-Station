"""
Tests for the finance summary API endpoints.

Validates HTTP behaviour, response structure, and financial totals
for the project financial summary endpoint.
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str = "PRJ-FIN-API") -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"name": "Finance API Project", "code": code},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_hierarchy(
    client: TestClient,
    project_id: str,
    unit_number: str = "101",
    building_code: str = "BLK-A",
    phase_sequence: int = 1,
) -> str:
    """Create phase → building → floor → unit under an existing project. Returns unit_id."""
    phase_id = client.post(
        "/api/v1/phases",
        json={
            "project_id": project_id,
            "name": f"Phase {phase_sequence}",
            "sequence": phase_sequence,
        },
    ).json()["id"]
    building_id = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": building_code},
    ).json()["id"]
    floor_id = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]
    unit_resp = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": unit_number,
            "unit_type": "studio",
            "internal_area": 100.0,
        },
    )
    return unit_resp.json()["id"]


def _create_contract(
    client: TestClient,
    unit_id: str,
    contract_price: float,
    contract_number: str,
    email: str,
) -> str:
    buyer_id = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Test Buyer", "email": email, "phone": "+9620000001"},
    ).json()["id"]
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": "2026-01-01",
            "contract_price": contract_price,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_schedule(client: TestClient, contract_id: str) -> list:
    template_id = client.post(
        "/api/v1/payment-plans/templates",
        json={
            "name": "Fin Test Plan",
            "down_payment_percent": 10.0,
            "number_of_installments": 3,
            "installment_frequency": "monthly",
        },
    ).json()["id"]
    resp = client.post(
        "/api/v1/payment-plans/generate",
        json={
            "contract_id": contract_id,
            "template_id": template_id,
            "start_date": "2030-01-01",
        },
    )
    assert resp.status_code == 201
    return resp.json()["items"]


def _record_receipt(
    client: TestClient,
    contract_id: str,
    schedule_id: str,
    amount: float,
) -> None:
    resp = client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": contract_id,
            "payment_schedule_id": schedule_id,
            "receipt_date": "2026-02-01",
            "amount_received": amount,
        },
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/v1/finance/projects/{project_id}/summary
# ---------------------------------------------------------------------------


def test_summary_returns_200_for_existing_project(client: TestClient):
    project_id = _create_project(client, "PRJ-FA-200")
    resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
    assert resp.status_code == 200


def test_summary_returns_404_for_missing_project(client: TestClient):
    resp = client.get("/api/v1/finance/projects/no-such-project/summary")
    assert resp.status_code == 404


def test_summary_response_structure(client: TestClient):
    """All required fields must be present in the response."""
    project_id = _create_project(client, "PRJ-FA-STRUC")
    resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()

    required_fields = {
        "project_id",
        "total_units",
        "units_sold",
        "units_available",
        "total_contract_value",
        "total_collected",
        "total_receivable",
        "collection_ratio",
        "average_unit_price",
    }
    assert required_fields.issubset(data.keys())


def test_summary_project_id_in_response(client: TestClient):
    project_id = _create_project(client, "PRJ-FA-ID")
    resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
    assert resp.json()["project_id"] == project_id


def test_summary_empty_project_all_zeros(client: TestClient):
    project_id = _create_project(client, "PRJ-FA-ZERO")
    resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
    data = resp.json()

    assert data["total_units"] == 0
    assert data["units_sold"] == 0
    assert data["units_available"] == 0
    assert data["total_contract_value"] == 0.0
    assert data["total_collected"] == 0.0
    assert data["total_receivable"] == 0.0
    assert data["collection_ratio"] == 0.0
    assert data["average_unit_price"] == 0.0


def test_summary_total_contract_value(client: TestClient):
    project_id = _create_project(client, "PRJ-FA-TCV")
    unit_id = _create_hierarchy(client, project_id)
    _create_contract(client, unit_id, 500_000.0, "CNT-FA-TCV", "tcv@test.com")

    resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
    assert resp.status_code == 200
    assert resp.json()["total_contract_value"] == pytest.approx(500_000.0)


def test_summary_total_collected(client: TestClient):
    project_id = _create_project(client, "PRJ-FA-TC")
    unit_id = _create_hierarchy(client, project_id)
    contract_id = _create_contract(
        client, unit_id, 200_000.0, "CNT-FA-TC", "tc@test.com"
    )
    schedule = _create_schedule(client, contract_id)
    _record_receipt(client, contract_id, schedule[0]["id"], schedule[0]["due_amount"])

    resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
    data = resp.json()
    assert data["total_collected"] == pytest.approx(schedule[0]["due_amount"])


def test_summary_total_receivable(client: TestClient):
    project_id = _create_project(client, "PRJ-FA-RCV")
    unit_id = _create_hierarchy(client, project_id)
    contract_id = _create_contract(
        client, unit_id, 200_000.0, "CNT-FA-RCV", "rcv@test.com"
    )
    schedule = _create_schedule(client, contract_id)
    first_due = schedule[0]["due_amount"]
    _record_receipt(client, contract_id, schedule[0]["id"], first_due)

    resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
    data = resp.json()
    expected_receivable = round(
        data["total_contract_value"] - data["total_collected"], 2
    )
    assert data["total_receivable"] == pytest.approx(expected_receivable, abs=0.02)


def test_summary_collection_ratio(client: TestClient):
    project_id = _create_project(client, "PRJ-FA-RAT")
    unit_id = _create_hierarchy(client, project_id)
    contract_id = _create_contract(
        client, unit_id, 100_000.0, "CNT-FA-RAT", "rat@test.com"
    )
    schedule = _create_schedule(client, contract_id)
    # Record first installment only — should give partial collection ratio
    _record_receipt(client, contract_id, schedule[0]["id"], schedule[0]["due_amount"])

    resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
    data = resp.json()
    assert 0.0 < data["collection_ratio"] < 1.0


def test_summary_unit_counts(client: TestClient):
    project_id = _create_project(client, "PRJ-FA-UNITS")
    # Create two units via two separate hierarchies (different building codes and phases)
    unit1_id = _create_hierarchy(
        client, project_id, unit_number="101", building_code="BLK-U1", phase_sequence=1
    )
    _create_hierarchy(
        client, project_id, unit_number="102", building_code="BLK-U2", phase_sequence=2
    )
    _create_contract(client, unit1_id, 300_000.0, "CNT-U1", "u1@test.com")

    resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
    data = resp.json()
    assert data["total_units"] == 2
    assert data["units_available"] >= 1  # at least unit2 is still available


def test_summary_multiple_contracts_aggregated(client: TestClient):
    project_id = _create_project(client, "PRJ-FA-MULTI")
    unit1_id = _create_hierarchy(
        client, project_id, unit_number="101", building_code="BLK-M1", phase_sequence=1
    )
    unit2_id = _create_hierarchy(
        client, project_id, unit_number="102", building_code="BLK-M2", phase_sequence=2
    )
    _create_contract(client, unit1_id, 300_000.0, "CNT-M01", "m1@test.com")
    _create_contract(client, unit2_id, 200_000.0, "CNT-M02", "m2@test.com")

    resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
    data = resp.json()
    assert data["total_contract_value"] == pytest.approx(500_000.0)
    assert data["average_unit_price"] == pytest.approx(250_000.0)
