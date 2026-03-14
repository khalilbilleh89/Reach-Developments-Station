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
        "/api/v1/buildings",
        json={"phase_id": phase_id, "name": "Block A", "code": f"BLK-{proj_code}"},
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


def _make_exception(
    client: TestClient,
    project_id: str,
    unit_id: str,
    *,
    base_price: float = 220_000.0,
    requested_price: float = 205_000.0,
    exception_type: str = "discount",
) -> dict:
    resp = client.post(
        "/api/v1/sales-exceptions",
        json={
            "project_id": project_id,
            "unit_id": unit_id,
            "exception_type": exception_type,
            "base_price": base_price,
            "requested_price": requested_price,
        },
    )
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
# Project list and summary tests
# ---------------------------------------------------------------------------

def test_list_project_exceptions(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "SE-L1")
    _make_exception(client, project_id, unit_id)
    _make_exception(client, project_id, unit_id, requested_price=210_000.0)

    resp = client.get(f"/api/v1/projects/{project_id}/sales-exceptions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_project_exceptions_not_found(client: TestClient):
    resp = client.get("/api/v1/projects/no-such-project/sales-exceptions")
    assert resp.status_code == 404


def test_project_summary_empty(client: TestClient):
    project_id, _ = _create_hierarchy(client, "SE-S0")
    resp = client.get(f"/api/v1/projects/{project_id}/sales-exceptions/summary")
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

    resp = client.get(f"/api/v1/projects/{project_id}/sales-exceptions/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_exceptions"] == 2
    assert data["approved_exceptions"] == 1
    assert data["rejected_exceptions"] == 1
    assert data["pending_exceptions"] == 0
    # Only approved exception's discount counts
    assert data["total_discount_amount"] == pytest.approx(15_000.0, abs=0.01)


def test_project_summary_not_found(client: TestClient):
    resp = client.get("/api/v1/projects/no-such-project/sales-exceptions/summary")
    assert resp.status_code == 404
