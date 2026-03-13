"""
Tests for the payment plans API endpoints.

Validates HTTP behaviour, request/response contracts, and full workflows.
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-PP-API") -> str:
    """Create a full project hierarchy and return unit_id."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "PP API Project", "code": proj_code}
    ).json()["id"]
    phase_id = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    ).json()["id"]
    building_id = client.post(
        "/api/v1/buildings", json={"phase_id": phase_id, "name": "Block A", "code": "BLK-A"}
    ).json()["id"]
    floor_id = client.post(
        "/api/v1/floors", json={"building_id": building_id, "level": 1}
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


def _create_buyer(client: TestClient, email: str = "ppbuyer@example.com") -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "PP Buyer", "email": email, "phone": "+9620000001"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_contract(
    client: TestClient,
    proj_code: str = "PRJ-PP-API",
    contract_price: float = 500_000.0,
    contract_number: str = "CNT-PP-001",
    email: str = "ppbuyer@example.com",
) -> str:
    unit_id = _create_hierarchy(client, proj_code)
    buyer_id = _create_buyer(client, email)
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


_TEMPLATE_PAYLOAD = {
    "name": "Standard 12M",
    "plan_type": "standard_installments",
    "down_payment_percent": 10.0,
    "number_of_installments": 12,
    "installment_frequency": "monthly",
}


def _create_template(client: TestClient, payload: dict = None) -> str:
    resp = client.post("/api/v1/payment-plans/templates", json=payload or _TEMPLATE_PAYLOAD)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Template endpoint tests
# ---------------------------------------------------------------------------


def test_create_template(client: TestClient):
    resp = client.post("/api/v1/payment-plans/templates", json=_TEMPLATE_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Standard 12M"
    assert data["plan_type"] == "standard_installments"
    assert data["down_payment_percent"] == pytest.approx(10.0)
    assert data["number_of_installments"] == 12
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


def test_create_template_with_handover(client: TestClient):
    payload = {**_TEMPLATE_PAYLOAD, "handover_percent": 5.0}
    resp = client.post("/api/v1/payment-plans/templates", json=payload)
    assert resp.status_code == 201
    assert resp.json()["handover_percent"] == pytest.approx(5.0)


def test_create_template_invalid_allocation_returns_422(client: TestClient):
    """down_payment + handover > 100 must be rejected."""
    payload = {**_TEMPLATE_PAYLOAD, "down_payment_percent": 60.0, "handover_percent": 50.0}
    resp = client.post("/api/v1/payment-plans/templates", json=payload)
    assert resp.status_code == 422


def test_create_template_negative_installments_returns_422(client: TestClient):
    payload = {**_TEMPLATE_PAYLOAD, "number_of_installments": 0}
    resp = client.post("/api/v1/payment-plans/templates", json=payload)
    assert resp.status_code == 422


def test_get_template(client: TestClient):
    template_id = _create_template(client)
    resp = client.get(f"/api/v1/payment-plans/templates/{template_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == template_id


def test_get_template_not_found(client: TestClient):
    resp = client.get("/api/v1/payment-plans/templates/no-such-template")
    assert resp.status_code == 404


def test_list_templates(client: TestClient):
    _create_template(client, {**_TEMPLATE_PAYLOAD, "name": "Plan A"})
    _create_template(client, {**_TEMPLATE_PAYLOAD, "name": "Plan B"})
    resp = client.get("/api/v1/payment-plans/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_templates_empty(client: TestClient):
    resp = client.get("/api/v1/payment-plans/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_update_template(client: TestClient):
    template_id = _create_template(client)
    resp = client.patch(
        f"/api/v1/payment-plans/templates/{template_id}",
        json={"name": "Renamed Plan"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Plan"


def test_update_template_deactivate(client: TestClient):
    template_id = _create_template(client)
    resp = client.patch(
        f"/api/v1/payment-plans/templates/{template_id}",
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_update_template_not_found(client: TestClient):
    resp = client.patch(
        "/api/v1/payment-plans/templates/no-such",
        json={"name": "X"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Schedule generation endpoint tests
# ---------------------------------------------------------------------------


def test_generate_schedule(client: TestClient):
    contract_id = _create_contract(client, "PRJ-GENSCHED", 500_000.0, "CNT-GS-001", "gs@test.com")
    template_id = _create_template(client)

    resp = client.post(
        "/api/v1/payment-plans/generate",
        json={
            "contract_id": contract_id,
            "template_id": template_id,
            "start_date": "2026-01-01",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["contract_id"] == contract_id
    assert data["total"] > 0
    assert abs(data["total_due"] - 500_000.0) < 0.02


def test_generate_schedule_total_due_equals_contract_price(client: TestClient):
    contract_id = _create_contract(
        client, "PRJ-TOTDUE", 333_333.33, "CNT-TD-001", "td@test.com"
    )
    template_id = _create_template(
        client,
        {
            "name": "Odd Plan",
            "down_payment_percent": 10.0,
            "number_of_installments": 7,
            "installment_frequency": "monthly",
        },
    )

    resp = client.post(
        "/api/v1/payment-plans/generate",
        json={
            "contract_id": contract_id,
            "template_id": template_id,
            "start_date": "2026-01-01",
        },
    )
    assert resp.status_code == 201
    assert abs(resp.json()["total_due"] - 333_333.33) < 0.02


def test_generate_schedule_contract_not_found(client: TestClient):
    template_id = _create_template(client)
    resp = client.post(
        "/api/v1/payment-plans/generate",
        json={"contract_id": "no-such-contract", "template_id": template_id},
    )
    assert resp.status_code == 404


def test_generate_schedule_template_not_found(client: TestClient):
    contract_id = _create_contract(client, "PRJ-TNFAPI", 500_000.0, "CNT-TNF-001", "tnf@test.com")
    resp = client.post(
        "/api/v1/payment-plans/generate",
        json={"contract_id": contract_id, "template_id": "no-such-template"},
    )
    assert resp.status_code == 404


def test_generate_schedule_inactive_template_rejected(client: TestClient):
    contract_id = _create_contract(
        client, "PRJ-INACT2", 500_000.0, "CNT-IA-001", "ia@test.com"
    )
    template_id = _create_template(client)
    client.patch(
        f"/api/v1/payment-plans/templates/{template_id}", json={"is_active": False}
    )
    resp = client.post(
        "/api/v1/payment-plans/generate",
        json={"contract_id": contract_id, "template_id": template_id},
    )
    assert resp.status_code == 422


def test_generate_schedule_response_has_due_date_and_amount_fields(client: TestClient):
    contract_id = _create_contract(
        client, "PRJ-FIELDS", 500_000.0, "CNT-FLD-001", "fld@test.com"
    )
    template_id = _create_template(client)
    resp = client.post(
        "/api/v1/payment-plans/generate",
        json={
            "contract_id": contract_id,
            "template_id": template_id,
            "start_date": "2026-01-01",
        },
    )
    assert resp.status_code == 201
    item = resp.json()["items"][0]
    assert "due_date" in item
    assert "due_amount" in item
    assert "installment_number" in item
    assert "status" in item
    assert item["status"] == "pending"


# ---------------------------------------------------------------------------
# Schedule retrieval endpoint tests
# ---------------------------------------------------------------------------


def test_get_schedule_for_contract(client: TestClient):
    contract_id = _create_contract(
        client, "PRJ-GSCHED", 500_000.0, "CNT-GS2-001", "gs2@test.com"
    )
    template_id = _create_template(client)
    client.post(
        "/api/v1/payment-plans/generate",
        json={
            "contract_id": contract_id,
            "template_id": template_id,
            "start_date": "2026-01-01",
        },
    )

    resp = client.get(f"/api/v1/payment-plans/contracts/{contract_id}/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contract_id"] == contract_id
    assert data["total"] > 0
    assert abs(data["total_due"] - 500_000.0) < 0.02


def test_get_schedule_contract_not_found(client: TestClient):
    resp = client.get("/api/v1/payment-plans/contracts/no-such-contract/schedule")
    assert resp.status_code == 404


def test_get_schedule_empty_before_generation(client: TestClient):
    contract_id = _create_contract(
        client, "PRJ-EMPTY", 500_000.0, "CNT-EMPTY-001", "empty@test.com"
    )
    resp = client.get(f"/api/v1/payment-plans/contracts/{contract_id}/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


# ---------------------------------------------------------------------------
# Regeneration endpoint tests
# ---------------------------------------------------------------------------


def test_regenerate_schedule(client: TestClient):
    contract_id = _create_contract(
        client, "PRJ-REGEN2", 500_000.0, "CNT-RGN-001", "rgn@test.com"
    )
    template_id = _create_template(client)

    client.post(
        "/api/v1/payment-plans/generate",
        json={
            "contract_id": contract_id,
            "template_id": template_id,
            "start_date": "2026-01-01",
        },
    )

    resp = client.post(
        f"/api/v1/payment-plans/contracts/{contract_id}/regenerate",
        json={
            "contract_id": contract_id,
            "template_id": template_id,
            "start_date": "2026-06-01",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["contract_id"] == contract_id
    # First line (down payment) must start on new start_date
    assert data["items"][0]["due_date"] == "2026-06-01"
    assert abs(data["total_due"] - 500_000.0) < 0.02


def test_regenerate_schedule_mismatched_contract_id_returns_400(client: TestClient):
    contract_id = _create_contract(
        client, "PRJ-MISMATCH", 500_000.0, "CNT-MIS-001", "mis@test.com"
    )
    template_id = _create_template(client)

    resp = client.post(
        f"/api/v1/payment-plans/contracts/{contract_id}/regenerate",
        json={
            "contract_id": "different-id",
            "template_id": template_id,
        },
    )
    assert resp.status_code == 400
