"""
Tests for the sales_exceptions API endpoints.

Validates HTTP behaviour, request/response contracts, business rules,
and project-level analytics.
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _create_hierarchy(client: TestClient, proj_code: str) -> tuple[str, str]:
    """Create Project → Phase → Building → Floor → Unit; return (project_id, unit_id)."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "SE Project", "code": proj_code}
    ).json()["id"]
    phase_id = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    ).json()["id"]
    building_id = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": f"BLK-{proj_code}"},
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
    return project_id, unit_id


def _create_buyer(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Test Buyer", "email": email, "phone": "+9620000001"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_contract(
    client: TestClient, unit_id: str, buyer_id: str, contract_number: str
) -> str:
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": "2026-03-01",
            "contract_price": 220_000.0,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _make_exception(
    client: TestClient,
    project_id: str,
    unit_id: str,
    *,
    base_price: float = 220_000.0,
    requested_price: float = 205_000.0,
    exception_type: str = "discount",
    sale_contract_id: str | None = None,
) -> dict:
    payload: dict = {
        "project_id": project_id,
        "unit_id": unit_id,
        "exception_type": exception_type,
        "base_price": base_price,
        "requested_price": requested_price,
    }
    if sale_contract_id is not None:
        payload["sale_contract_id"] = sale_contract_id
    resp = client.post("/api/v1/sales-exceptions", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Create tests
# ---------------------------------------------------------------------------

def test_create_exception_basic(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-C1")
    data = _make_exception(client, project_id, unit_id)

    assert data["project_id"] == project_id
    assert data["unit_id"] == unit_id
    assert data["exception_type"] == "discount"
    assert data["approval_status"] == "pending"
    assert data["base_price"] == pytest.approx(220_000.0)
    assert data["requested_price"] == pytest.approx(205_000.0)
    # Derived fields must be calculated server-side
    assert data["discount_amount"] == pytest.approx(15_000.0, abs=0.01)
    # 0.0682 = round(15_000 / 220_000, 4) stored as Numeric(8,4) — approx 6.82%
    assert data["discount_percentage"] == pytest.approx(0.0682, abs=1e-4)


def test_create_exception_requested_above_base_returns_422(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-C2")
    resp = client.post(
        "/api/v1/sales-exceptions",
        json={
            "project_id": project_id,
            "unit_id": unit_id,
            "exception_type": "discount",
            "base_price": 200_000.0,
            "requested_price": 210_000.0,  # above base
        },
    )
    assert resp.status_code == 422


def test_create_exception_exceeds_max_discount_returns_422(client: TestClient):
    """A discount > 30% must be rejected."""
    project_id, unit_id = _create_hierarchy(client, "SE-C3")
    resp = client.post(
        "/api/v1/sales-exceptions",
        json={
            "project_id": project_id,
            "unit_id": unit_id,
            "exception_type": "discount",
            "base_price": 200_000.0,
            "requested_price": 100_000.0,  # 50% discount
        },
    )
    assert resp.status_code == 422


def test_create_exception_invalid_unit_returns_404(client: TestClient):
    project_id, _ = _create_hierarchy(client, "SE-C4")
    resp = client.post(
        "/api/v1/sales-exceptions",
        json={
            "project_id": project_id,
            "unit_id": "non-existent-unit",
            "exception_type": "incentive_package",
            "base_price": 200_000.0,
            "requested_price": 195_000.0,
        },
    )
    assert resp.status_code == 404


def test_create_exception_invalid_project_returns_404(client: TestClient):
    _, unit_id = _create_hierarchy(client, "SE-C5")
    resp = client.post(
        "/api/v1/sales-exceptions",
        json={
            "project_id": "non-existent-project",
            "unit_id": unit_id,
            "exception_type": "discount",
            "base_price": 200_000.0,
            "requested_price": 195_000.0,
        },
    )
    assert resp.status_code == 404


def test_create_exception_unit_not_in_project_returns_422(client: TestClient):
    """Unit from a different project must be rejected (hierarchy integrity)."""
    project_a_id, _ = _create_hierarchy(client, "SE-HA")
    project_b_id, unit_b_id = _create_hierarchy(client, "SE-HB")

    resp = client.post(
        "/api/v1/sales-exceptions",
        json={
            "project_id": project_a_id,
            "unit_id": unit_b_id,  # belongs to project B, not A
            "exception_type": "discount",
            "base_price": 200_000.0,
            "requested_price": 195_000.0,
        },
    )
    assert resp.status_code == 422


def test_create_exception_with_valid_contract(client: TestClient):
    """sale_contract_id pointing to the correct unit must be accepted."""
    project_id, unit_id = _create_hierarchy(client, "SE-CV")
    buyer_id = _create_buyer(client, "cv@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-CV-001")

    data = _make_exception(
        client, project_id, unit_id, sale_contract_id=contract_id
    )
    assert data["sale_contract_id"] == contract_id


def test_create_exception_contract_not_found_returns_404(client: TestClient):
    """Non-existent sale_contract_id must return 404."""
    project_id, unit_id = _create_hierarchy(client, "SE-CNF")
    resp = client.post(
        "/api/v1/sales-exceptions",
        json={
            "project_id": project_id,
            "unit_id": unit_id,
            "exception_type": "discount",
            "base_price": 200_000.0,
            "requested_price": 195_000.0,
            "sale_contract_id": "no-such-contract",
        },
    )
    assert resp.status_code == 404


def test_create_exception_contract_unit_mismatch_returns_422(client: TestClient):
    """sale_contract_id linked to a different unit must be rejected."""
    project_id, unit_a_id = _create_hierarchy(client, "SE-CM-A")
    _, unit_b_id = _create_hierarchy(client, "SE-CM-B")
    buyer_id = _create_buyer(client, "cm@example.com")
    # contract belongs to unit_a
    contract_id = _create_contract(client, unit_a_id, buyer_id, "CNT-CM-001")

    resp = client.post(
        "/api/v1/sales-exceptions",
        json={
            "project_id": project_id,
            "unit_id": unit_b_id,  # different unit
            "exception_type": "discount",
            "base_price": 200_000.0,
            "requested_price": 195_000.0,
            "sale_contract_id": contract_id,
        },
    )
    assert resp.status_code == 422


def test_create_exception_all_types(client: TestClient):
    """All valid ExceptionType values should be accepted."""
    project_id, unit_id = _create_hierarchy(client, "SE-CT")
    for exc_type in ("discount", "price_override", "incentive_package",
                     "payment_concession", "marketing_promo"):
        resp = client.post(
            "/api/v1/sales-exceptions",
            json={
                "project_id": project_id,
                "unit_id": unit_id,
                "exception_type": exc_type,
                "base_price": 200_000.0,
                "requested_price": 195_000.0,
            },
        )
        assert resp.status_code == 201, f"Failed for type '{exc_type}': {resp.text}"


# ---------------------------------------------------------------------------
# Read tests
# ---------------------------------------------------------------------------

def test_get_exception(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-G1")
    exc = _make_exception(client, project_id, unit_id)
    resp = client.get(f"/api/v1/sales-exceptions/{exc['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == exc["id"]


def test_get_exception_not_found(client: TestClient):
    resp = client.get("/api/v1/sales-exceptions/no-such-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update tests
# ---------------------------------------------------------------------------

def test_update_pending_exception(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-U1")
    exc = _make_exception(client, project_id, unit_id)

    resp = client.patch(
        f"/api/v1/sales-exceptions/{exc['id']}",
        json={"notes": "Updated note", "incentive_value": 5000.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["notes"] == "Updated note"
    assert data["incentive_value"] == pytest.approx(5000.0)


def test_update_approved_exception_returns_409(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-U2")
    exc = _make_exception(client, project_id, unit_id)
    # Approve it first
    client.post(f"/api/v1/sales-exceptions/{exc['id']}/approve", json={})

    resp = client.patch(
        f"/api/v1/sales-exceptions/{exc['id']}",
        json={"notes": "Trying to change"},
    )
    assert resp.status_code == 409


def test_update_cannot_change_sale_contract_id(client: TestClient):
    """sale_contract_id must not be updatable via PATCH."""
    project_id, unit_id = _create_hierarchy(client, "SE-UNC")
    exc = _make_exception(client, project_id, unit_id)

    resp = client.patch(
        f"/api/v1/sales-exceptions/{exc['id']}",
        json={"sale_contract_id": "some-contract-id"},
    )
    # Field is stripped from schema — the response must still have the original
    # (None) sale_contract_id; any non-null value passed is silently ignored.
    assert resp.status_code == 200
    assert resp.json()["sale_contract_id"] is None


# ---------------------------------------------------------------------------
# Approve / Reject tests
# ---------------------------------------------------------------------------

def test_approve_exception(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-A1")
    exc = _make_exception(client, project_id, unit_id)

    resp = client.post(
        f"/api/v1/sales-exceptions/{exc['id']}/approve",
        json={"approved_by": "Manager A"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["approval_status"] == "approved"
    assert data["approved_by"] == "Manager A"
    assert data["approved_at"] is not None


def test_reject_exception(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-R1")
    exc = _make_exception(client, project_id, unit_id)

    resp = client.post(
        f"/api/v1/sales-exceptions/{exc['id']}/reject",
        json={"approved_by": "Manager B", "notes": "Margin too thin"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["approval_status"] == "rejected"
    assert data["notes"] == "Margin too thin"


def test_approve_already_approved_returns_409(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-A2")
    exc = _make_exception(client, project_id, unit_id)
    client.post(f"/api/v1/sales-exceptions/{exc['id']}/approve", json={})

    resp = client.post(f"/api/v1/sales-exceptions/{exc['id']}/approve", json={})
    assert resp.status_code == 409


def test_approve_already_rejected_returns_409(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-A3")
    exc = _make_exception(client, project_id, unit_id)
    client.post(f"/api/v1/sales-exceptions/{exc['id']}/reject", json={})

    resp = client.post(f"/api/v1/sales-exceptions/{exc['id']}/approve", json={})
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Project list and summary tests (new URL structure)
# ---------------------------------------------------------------------------

def test_list_project_exceptions(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-L1")
    _make_exception(client, project_id, unit_id)
    _make_exception(client, project_id, unit_id, requested_price=210_000.0)

    resp = client.get(f"/api/v1/sales-exceptions/projects/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_project_exceptions_not_found(client: TestClient):
    resp = client.get("/api/v1/sales-exceptions/projects/no-such-project")
    assert resp.status_code == 404


def test_project_summary_empty(client: TestClient):
    project_id, _ = _create_hierarchy(client, "SE-S0")
    resp = client.get(f"/api/v1/sales-exceptions/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_exceptions"] == 0
    assert data["total_discount_amount"] == pytest.approx(0.0)
    assert data["total_incentive_value"] == pytest.approx(0.0)


def test_project_summary_counts_and_sums(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-S1")
    exc1 = _make_exception(client, project_id, unit_id)
    exc2 = _make_exception(client, project_id, unit_id, requested_price=210_000.0)

    # Approve exc1, reject exc2
    client.post(f"/api/v1/sales-exceptions/{exc1['id']}/approve", json={})
    client.post(f"/api/v1/sales-exceptions/{exc2['id']}/reject", json={})

    resp = client.get(f"/api/v1/sales-exceptions/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_exceptions"] == 2
    assert data["approved_exceptions"] == 1
    assert data["rejected_exceptions"] == 1
    assert data["pending_exceptions"] == 0
    # Only approved exception's discount counts
    assert data["total_discount_amount"] == pytest.approx(15_000.0, abs=0.01)


def test_project_summary_not_found(client: TestClient):
    resp = client.get("/api/v1/sales-exceptions/projects/no-such-project/summary")
    assert resp.status_code == 404
