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
        f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-A"}
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


# ---------------------------------------------------------------------------
# Hardening tests: duplicate generation, safe regeneration, plan type, allocation
# ---------------------------------------------------------------------------


def test_generate_returns_409_if_schedule_already_exists(client: TestClient):
    """Second call to generate for the same contract must return 409."""
    contract_id = _create_contract(
        client, "PRJ-DUP-API", 500_000.0, "CNT-DUP-001", "dup@test.com"
    )
    template_id = _create_template(client)

    payload = {
        "contract_id": contract_id,
        "template_id": template_id,
        "start_date": "2026-01-01",
    }
    first = client.post("/api/v1/payment-plans/generate", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/payment-plans/generate", json=payload)
    assert second.status_code == 409
    detail = second.json()["detail"].lower()
    assert "already" in detail or "regenerate" in detail


def test_create_template_unsupported_plan_type_returns_422(client: TestClient):
    """Creating a template with an unsupported plan type must return 422."""
    payload = {**_TEMPLATE_PAYLOAD, "plan_type": "milestone"}
    resp = client.post("/api/v1/payment-plans/templates", json=payload)
    assert resp.status_code == 422


def test_create_template_post_handover_plan_type_returns_422(client: TestClient):
    """post_handover plan type is not yet implemented — must return 422."""
    payload = {**_TEMPLATE_PAYLOAD, "plan_type": "post_handover"}
    resp = client.post("/api/v1/payment-plans/templates", json=payload)
    assert resp.status_code == 422


def test_create_template_custom_plan_type_returns_422(client: TestClient):
    """custom plan type is not yet implemented — must return 422."""
    payload = {**_TEMPLATE_PAYLOAD, "plan_type": "custom"}
    resp = client.post("/api/v1/payment-plans/templates", json=payload)
    assert resp.status_code == 422


def test_update_template_unsupported_plan_type_returns_422(client: TestClient):
    """Patching plan_type to an unsupported value must return 422."""
    template_id = _create_template(client)
    resp = client.patch(
        f"/api/v1/payment-plans/templates/{template_id}",
        json={"plan_type": "milestone"},
    )
    assert resp.status_code == 422


def test_update_template_invalid_allocation_both_fields_returns_422(client: TestClient):
    """Both percent fields in the PATCH payload totalling > 100 must return 422."""
    template_id = _create_template(client)
    resp = client.patch(
        f"/api/v1/payment-plans/templates/{template_id}",
        json={"down_payment_percent": 70.0, "handover_percent": 40.0},
    )
    assert resp.status_code == 422


def test_update_template_invalid_merged_allocation_returns_422(client: TestClient):
    """Updating only handover when existing down_payment pushes total > 100 must return 422."""
    # Create template with 70% down payment
    template_id = _create_template(
        client,
        {
            "name": "High Down API",
            "down_payment_percent": 70.0,
            "number_of_installments": 6,
            "installment_frequency": "monthly",
        },
    )
    # Patch handover to 40%; merged total = 70 + 40 = 110 → invalid
    resp = client.patch(
        f"/api/v1/payment-plans/templates/{template_id}",
        json={"handover_percent": 40.0},
    )
    assert resp.status_code == 422


def test_regenerate_preserves_schedule_on_invalid_template(client: TestClient):
    """If regeneration fails, the original schedule must remain intact."""
    contract_id = _create_contract(
        client, "PRJ-SAFE-API", 500_000.0, "CNT-SAFE-001", "safe@test.com"
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
    original = client.get(f"/api/v1/payment-plans/contracts/{contract_id}/schedule").json()
    original_total = original["total"]

    # Attempt regeneration with a non-existent template → 404
    resp = client.post(
        f"/api/v1/payment-plans/contracts/{contract_id}/regenerate",
        json={
            "contract_id": contract_id,
            "template_id": "no-such-template",
        },
    )
    assert resp.status_code == 404

    # Original schedule must still be intact
    after = client.get(f"/api/v1/payment-plans/contracts/{contract_id}/schedule").json()
    assert after["total"] == original_total
    assert abs(after["total_due"] - 500_000.0) < 0.02


# ---------------------------------------------------------------------------
# PR029 — simplified payment plan creation endpoint tests
# ---------------------------------------------------------------------------


def test_create_payment_plan_returns_201(client: TestClient):
    """POST /payment-plans creates a plan and returns 201."""
    contract_id = _create_contract(
        client, "PRJ-PP029-A", 600_000.0, "CNT-PP029-A1", "pp029a@test.com"
    )
    resp = client.post(
        "/api/v1/payment-plans",
        json={
            "contract_id": contract_id,
            "plan_name": "Standard 12-Month",
            "number_of_installments": 12,
            "start_date": "2026-01-01",
            "installment_frequency": "monthly",
            "down_payment_percent": 0.0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["contract_id"] == contract_id
    assert data["plan_name"] == "Standard 12-Month"
    assert data["total_installments"] == 12
    assert abs(data["total_due"] - 600_000.0) < 0.02


def test_create_payment_plan_duplicate_returns_409(client: TestClient):
    """Creating a second plan for the same contract returns 409."""
    contract_id = _create_contract(
        client, "PRJ-PP029-B", 500_000.0, "CNT-PP029-B1", "pp029b@test.com"
    )
    payload = {
        "contract_id": contract_id,
        "plan_name": "Plan A",
        "number_of_installments": 6,
        "start_date": "2026-01-01",
        "installment_frequency": "monthly",
    }
    client.post("/api/v1/payment-plans", json=payload)
    resp = client.post("/api/v1/payment-plans", json=payload)
    assert resp.status_code == 409


def test_create_payment_plan_contract_not_found(client: TestClient):
    """Creating a plan for a non-existent contract returns 404."""
    resp = client.post(
        "/api/v1/payment-plans",
        json={
            "contract_id": "no-such-contract",
            "plan_name": "Ghost Plan",
            "number_of_installments": 6,
            "start_date": "2026-01-01",
            "installment_frequency": "monthly",
        },
    )
    assert resp.status_code == 404


def test_get_payment_plan_item_by_id(client: TestClient):
    """GET /payment-plans/{id} returns a single schedule item."""
    contract_id = _create_contract(
        client, "PRJ-PP029-C", 300_000.0, "CNT-PP029-C1", "pp029c@test.com"
    )
    created = client.post(
        "/api/v1/payment-plans",
        json={
            "contract_id": contract_id,
            "plan_name": "3-Month Plan",
            "number_of_installments": 3,
            "start_date": "2026-01-01",
            "installment_frequency": "monthly",
        },
    ).json()
    item_id = created["installments"][0]["id"]

    resp = client.get(f"/api/v1/payment-plans/{item_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == item_id
    assert data["contract_id"] == contract_id


def test_get_payment_plan_item_not_found(client: TestClient):
    """GET /payment-plans/{id} returns 404 for unknown IDs."""
    resp = client.get("/api/v1/payment-plans/no-such-id")
    assert resp.status_code == 404


def test_get_contract_payment_plan_endpoint(client: TestClient):
    """GET /payment-plans/contracts/{id}/payment-plan returns plan response."""
    contract_id = _create_contract(
        client, "PRJ-PP029-D", 480_000.0, "CNT-PP029-D1", "pp029d@test.com"
    )
    client.post(
        "/api/v1/payment-plans",
        json={
            "contract_id": contract_id,
            "plan_name": "48-Month Plan",
            "number_of_installments": 48,
            "start_date": "2026-01-01",
            "installment_frequency": "monthly",
        },
    )
    resp = client.get(f"/api/v1/payment-plans/contracts/{contract_id}/payment-plan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contract_id"] == contract_id
    assert data["total_installments"] == 48
    assert abs(data["total_due"] - 480_000.0) < 0.02


def test_get_contract_payment_plan_not_found(client: TestClient):
    """GET /payment-plans/contracts/{id}/payment-plan returns 404 when no plan exists."""
    contract_id = _create_contract(
        client, "PRJ-PP029-E", 300_000.0, "CNT-PP029-E1", "pp029e@test.com"
    )
    resp = client.get(f"/api/v1/payment-plans/contracts/{contract_id}/payment-plan")
    assert resp.status_code == 404


def test_list_contract_installments_endpoint(client: TestClient):
    """GET /payment-plans/contracts/{id}/installments returns schedule list."""
    contract_id = _create_contract(
        client, "PRJ-PP029-F", 360_000.0, "CNT-PP029-F1", "pp029f@test.com"
    )
    client.post(
        "/api/v1/payment-plans",
        json={
            "contract_id": contract_id,
            "plan_name": "36-Month Plan",
            "number_of_installments": 36,
            "start_date": "2026-03-01",
            "installment_frequency": "monthly",
        },
    )
    resp = client.get(f"/api/v1/payment-plans/contracts/{contract_id}/installments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contract_id"] == contract_id
    assert data["total"] == 36
    assert abs(data["total_due"] - 360_000.0) < 0.02
