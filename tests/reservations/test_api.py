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


def test_update_reservation_clear_notes(client: TestClient):
    """Sending notes=null explicitly clears the field."""
    _, unit_id = _create_hierarchy(client, "PRJ-CLRN")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    # Set notes first
    client.patch(f"/api/v1/reservations/{res_id}", json={"notes": "initial"})
    # Then clear with explicit null
    resp = client.patch(f"/api/v1/reservations/{res_id}", json={"notes": None})
    assert resp.status_code == 200
    assert resp.json()["notes"] is None


def test_update_reservation_non_active_returns_409(client: TestClient):
    """PATCH on a cancelled reservation must return 409."""
    _, unit_id = _create_hierarchy(client, "PRJ-UPDNA")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    client.post(f"/api/v1/reservations/{res_id}/cancel")
    resp = client.patch(f"/api/v1/reservations/{res_id}", json={"notes": "should fail"})
    assert resp.status_code == 409


def test_update_reservation_not_found_returns_404(client: TestClient):
    resp = client.patch("/api/v1/reservations/no-such-id", json={"notes": "x"})
    assert resp.status_code == 404


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


def test_cancel_already_cancelled_returns_422(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-DBLCAN")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    client.post(f"/api/v1/reservations/{res_id}/cancel")
    resp = client.post(f"/api/v1/reservations/{res_id}/cancel")
    assert resp.status_code == 422


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


# ---------------------------------------------------------------------------
# PATCH /reservations/{id}/status — state machine endpoint
# ---------------------------------------------------------------------------


def test_status_transition_active_to_cancelled(client: TestClient):
    """ACTIVE → CANCELLED via PATCH /status returns 200."""
    _, unit_id = _create_hierarchy(client, "PRJ-ST-AC")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    resp = client.patch(
        f"/api/v1/reservations/{res_id}/status", json={"status": "cancelled"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_status_transition_active_to_expired(client: TestClient):
    """ACTIVE → EXPIRED via PATCH /status returns 200."""
    _, unit_id = _create_hierarchy(client, "PRJ-ST-AE")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    resp = client.patch(
        f"/api/v1/reservations/{res_id}/status", json={"status": "expired"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "expired"


def test_status_transition_active_to_converted(client: TestClient):
    """ACTIVE → CONVERTED via PATCH /status returns 200."""
    _, unit_id = _create_hierarchy(client, "PRJ-ST-ACV")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    resp = client.patch(
        f"/api/v1/reservations/{res_id}/status", json={"status": "converted"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "converted"


def test_status_transition_expired_to_cancelled(client: TestClient):
    """EXPIRED → CANCELLED via PATCH /status returns 200."""
    _, unit_id = _create_hierarchy(client, "PRJ-ST-EC")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    client.patch(f"/api/v1/reservations/{res_id}/status", json={"status": "expired"})
    resp = client.patch(
        f"/api/v1/reservations/{res_id}/status", json={"status": "cancelled"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_invalid_transition_cancelled_to_active_returns_422(client: TestClient):
    """CANCELLED → ACTIVE is invalid (terminal state); PATCH /status returns 422."""
    _, unit_id = _create_hierarchy(client, "PRJ-INV-DCV")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    client.patch(f"/api/v1/reservations/{res_id}/status", json={"status": "cancelled"})
    resp = client.patch(
        f"/api/v1/reservations/{res_id}/status", json={"status": "active"}
    )
    assert resp.status_code == 422


def test_invalid_transition_converted_to_cancelled_returns_422(client: TestClient):
    """CONVERTED → CANCELLED is invalid (terminal state); PATCH /status returns 422."""
    _, unit_id = _create_hierarchy(client, "PRJ-INV-CVC")

    res_id = client.post(
        "/api/v1/reservations", json={"unit_id": unit_id, **_PAYLOAD}
    ).json()["id"]

    client.patch(f"/api/v1/reservations/{res_id}/status", json={"status": "converted"})
    resp = client.patch(
        f"/api/v1/reservations/{res_id}/status", json={"status": "cancelled"}
    )
    assert resp.status_code == 422


def test_status_transition_not_found_returns_404(client: TestClient):
    """PATCH /status on a non-existent reservation returns 404."""
    resp = client.patch(
        "/api/v1/reservations/no-such-id/status", json={"status": "cancelled"}
    )
    assert resp.status_code == 404
