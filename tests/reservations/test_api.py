"""
Tests for the reservations API endpoints.

Validates HTTP behaviour and request/response contracts for:
  POST   /api/v1/reservations
  GET    /api/v1/reservations/{reservation_id}
  PATCH  /api/v1/reservations/{reservation_id}
  POST   /api/v1/reservations/{reservation_id}/cancel
  POST   /api/v1/reservations/{reservation_id}/convert
  GET    /api/v1/projects/{project_id}/reservations
"""

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-RAPI") -> tuple[str, str]:
    """Create a full project hierarchy; return (project_id, unit_id)."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "Reservation Project", "code": proj_code}
    ).json()["id"]
    phase_id = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
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
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 80.0},
    ).json()["id"]
    return project_id, unit_id


_PAYLOAD = {
    "customer_name": "Alice Smith",
    "customer_phone": "+971501234567",
    "customer_email": "alice@example.com",
    "reservation_price": 750_000.0,
    "reservation_fee": 5_000.0,
    "currency": "AED",
}


# ---------------------------------------------------------------------------
# Create reservation
# ---------------------------------------------------------------------------


def test_create_reservation(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-CRES")

    resp = client.post("/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD})

    assert resp.status_code == 201
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["customer_name"] == "Alice Smith"
    assert data["status"] == "active"
    assert "id" in data


def test_create_reservation_invalid_unit_returns_404(client: TestClient):
    resp = client.post("/api/v1/reservations", json={"unit_id": "no-such-unit", **_PAYLOAD})
    assert resp.status_code == 404


def test_double_reservation_blocked_returns_409(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-DUPAPI")

    client.post("/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD})
    resp = client.post("/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD})

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Get reservation
# ---------------------------------------------------------------------------


def test_get_reservation(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-GRESAPI")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    resp = client.get(f"/api/v1/reservations/{res_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == res_id


def test_get_reservation_not_found(client: TestClient):
    resp = client.get("/api/v1/reservations/no-such-reservation")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update reservation
# ---------------------------------------------------------------------------


def test_update_reservation_notes(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-UPDN")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    resp = client.patch(
        f"/api/v1/reservations/{res_id}",
        json={"notes": "VIP buyer — priority hold"},
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "VIP buyer — priority hold"


# ---------------------------------------------------------------------------
# Cancel reservation
# ---------------------------------------------------------------------------


def test_cancel_reservation(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-CANRAPI")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    resp = client.post(f"/api/v1/reservations/{res_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_already_cancelled_returns_409(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-DBLCAN")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    client.post(f"/api/v1/reservations/{res_id}/cancel")
    resp = client.post(f"/api/v1/reservations/{res_id}/cancel")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Convert reservation
# ---------------------------------------------------------------------------


def test_convert_reservation(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-CONVAPI")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    resp = client.post(f"/api/v1/reservations/{res_id}/convert")
    assert resp.status_code == 200
    assert resp.json()["status"] == "converted"


# ---------------------------------------------------------------------------
# List by project
# ---------------------------------------------------------------------------


def test_list_project_reservations(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-LISTAPI")

    client.post("/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD})

    resp = client.get(f"/api/v1/projects/{project_id}/reservations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["unit_id"] == unit_id


def test_list_project_reservations_empty_project(client: TestClient):
    project_id, _ = _create_hierarchy(client, "PRJ-EMPTLST")

    resp = client.get(f"/api/v1/projects/{project_id}/reservations")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
