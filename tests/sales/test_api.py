"""
Tests for the sales API endpoints.

Validates HTTP behaviour, request/response contracts, and full sales workflows.
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-SAPI") -> tuple[str, str]:
    """Create a full project hierarchy and return (project_id, unit_id)."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "Sales Project", "code": proj_code}
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
    return project_id, unit_id


_PRICING_PAYLOAD = {
    "base_price_per_sqm": 5000.0,
    "floor_premium": 0.0,
    "view_premium": 0.0,
    "corner_premium": 0.0,
    "size_adjustment": 0.0,
    "custom_adjustment": 0.0,
}

_BUYER_PAYLOAD = {"full_name": "Jane Doe", "email": "jane@example.com", "phone": "+9620000001"}

_RESERVATION_DATES = {"reservation_date": "2026-03-13", "expiry_date": "2026-04-13"}


def _create_buyer(client: TestClient, email: str = "jane@example.com") -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Jane Doe", "email": email, "phone": "+9620000001"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_priced_unit(client: TestClient, proj_code: str = "PRJ-SAPI") -> tuple[str, str]:
    """Return (project_id, unit_id) with pricing set."""
    project_id, unit_id = _create_hierarchy(client, proj_code)
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_PRICING_PAYLOAD)
    return project_id, unit_id


# ---------------------------------------------------------------------------
# Buyer endpoint tests
# ---------------------------------------------------------------------------

def test_create_buyer(client: TestClient):
    resp = client.post("/api/v1/sales/buyers", json=_BUYER_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "Jane Doe"
    assert data["email"] == "jane@example.com"
    assert "id" in data


def test_get_buyer(client: TestClient):
    buyer_id = _create_buyer(client)
    resp = client.get(f"/api/v1/sales/buyers/{buyer_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == buyer_id


def test_get_buyer_not_found(client: TestClient):
    resp = client.get("/api/v1/sales/buyers/no-such-buyer")
    assert resp.status_code == 404


def test_list_buyers(client: TestClient):
    _create_buyer(client, "a@example.com")
    _create_buyer(client, "b@example.com")
    resp = client.get("/api/v1/sales/buyers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


# ---------------------------------------------------------------------------
# Reservation endpoint tests
# ---------------------------------------------------------------------------

def test_create_reservation(client: TestClient):
    _, unit_id = _create_priced_unit(client, "PRJ-CRES")
    buyer_id = _create_buyer(client, "cres@example.com")

    resp = client.post(
        "/api/v1/sales/reservations",
        json={"unit_id": unit_id, "buyer_id": buyer_id, **_RESERVATION_DATES},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["buyer_id"] == buyer_id
    assert data["status"] == "active"


def test_create_reservation_no_pricing_returns_422(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-NOPRICE")
    buyer_id = _create_buyer(client, "noprice@example.com")

    resp = client.post(
        "/api/v1/sales/reservations",
        json={"unit_id": unit_id, "buyer_id": buyer_id, **_RESERVATION_DATES},
    )
    assert resp.status_code == 422


def test_duplicate_active_reservation_returns_409(client: TestClient):
    _, unit_id = _create_priced_unit(client, "PRJ-DUPRES")
    buyer_id = _create_buyer(client, "dupres@example.com")

    client.post(
        "/api/v1/sales/reservations",
        json={"unit_id": unit_id, "buyer_id": buyer_id, **_RESERVATION_DATES},
    )
    resp = client.post(
        "/api/v1/sales/reservations",
        json={"unit_id": unit_id, "buyer_id": buyer_id, **_RESERVATION_DATES},
    )
    assert resp.status_code == 409


def test_get_reservation(client: TestClient):
    _, unit_id = _create_priced_unit(client, "PRJ-GRES")
    buyer_id = _create_buyer(client, "gres@example.com")

    res_id = client.post(
        "/api/v1/sales/reservations",
        json={"unit_id": unit_id, "buyer_id": buyer_id, **_RESERVATION_DATES},
    ).json()["id"]

    resp = client.get(f"/api/v1/sales/reservations/{res_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == res_id


def test_get_reservation_not_found(client: TestClient):
    resp = client.get("/api/v1/sales/reservations/no-such-reservation")
    assert resp.status_code == 404


def test_list_reservations(client: TestClient):
    _, unit_id = _create_priced_unit(client, "PRJ-LRES")
    buyer_id = _create_buyer(client, "lres@example.com")

    client.post(
        "/api/v1/sales/reservations",
        json={"unit_id": unit_id, "buyer_id": buyer_id, **_RESERVATION_DATES},
    )
    resp = client.get("/api/v1/sales/reservations")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_update_reservation(client: TestClient):
    _, unit_id = _create_priced_unit(client, "PRJ-URES")
    buyer_id = _create_buyer(client, "ures@example.com")

    res_id = client.post(
        "/api/v1/sales/reservations",
        json={"unit_id": unit_id, "buyer_id": buyer_id, **_RESERVATION_DATES},
    ).json()["id"]

    resp = client.patch(
        f"/api/v1/sales/reservations/{res_id}",
        json={"expiry_date": "2026-05-01"},
    )
    assert resp.status_code == 200
    assert resp.json()["expiry_date"] == "2026-05-01"


def test_reservation_date_fields_are_iso_strings_in_response(client: TestClient):
    """Date fields must serialize as ISO date strings (YYYY-MM-DD) in JSON responses."""
    _, unit_id = _create_priced_unit(client, "PRJ-RDSER")
    buyer_id = _create_buyer(client, "rdser@example.com")

    resp = client.post(
        "/api/v1/sales/reservations",
        json={"unit_id": unit_id, "buyer_id": buyer_id, **_RESERVATION_DATES},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["reservation_date"] == "2026-03-13"
    assert data["expiry_date"] == "2026-04-13"


def test_reservation_invalid_date_range_returns_422(client: TestClient):
    """expiry_date before reservation_date must be rejected with 422."""
    _, unit_id = _create_priced_unit(client, "PRJ-INVDT")
    buyer_id = _create_buyer(client, "invdt@example.com")

    resp = client.post(
        "/api/v1/sales/reservations",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "reservation_date": "2026-04-01",
            "expiry_date": "2026-03-01",  # before reservation_date
        },
    )
    assert resp.status_code == 422


def test_cancel_reservation(client: TestClient):
    _, unit_id = _create_priced_unit(client, "PRJ-CXRES")
    buyer_id = _create_buyer(client, "cxres@example.com")

    res_id = client.post(
        "/api/v1/sales/reservations",
        json={"unit_id": unit_id, "buyer_id": buyer_id, **_RESERVATION_DATES},
    ).json()["id"]

    resp = client.post(f"/api/v1/sales/reservations/{res_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Contract endpoint tests
# ---------------------------------------------------------------------------

def test_create_contract(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-CC")
    buyer_id = _create_buyer(client, "cc@example.com")

    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": "CNT-CC-001",
            "contract_date": "2026-03-13",
            "contract_price": 500_000.0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["contract_price"] == pytest.approx(500_000.0)
    assert data["status"] == "draft"
    # contract_date must serialize as ISO date string
    assert data["contract_date"] == "2026-03-13"


def test_create_contract_invalid_unit_returns_404(client: TestClient):
    buyer_id = _create_buyer(client, "cnounit@example.com")
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": "no-such-unit",
            "buyer_id": buyer_id,
            "contract_number": "CNT-NOUNIT",
            "contract_date": "2026-03-13",
            "contract_price": 500_000.0,
        },
    )
    assert resp.status_code == 404


def test_create_contract_invalid_buyer_returns_404(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-CNOBUY")
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": "no-such-buyer",
            "contract_number": "CNT-NOBUY",
            "contract_date": "2026-03-13",
            "contract_price": 500_000.0,
        },
    )
    assert resp.status_code == 404


def test_duplicate_active_contract_returns_409(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-DCCONT")
    buyer_id = _create_buyer(client, "dccont@example.com")

    client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": "CNT-DC-001",
            "contract_date": "2026-03-13",
            "contract_price": 500_000.0,
        },
    )
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": "CNT-DC-002",
            "contract_date": "2026-03-14",
            "contract_price": 500_000.0,
        },
    )
    assert resp.status_code == 409
    # Error message must mention the actual blocking statuses
    detail = resp.json()["detail"].lower()
    assert "draft" in detail or "active" in detail


def test_get_contract(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-GC")
    buyer_id = _create_buyer(client, "gc@example.com")

    contract_id = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": "CNT-GC-001",
            "contract_date": "2026-03-13",
            "contract_price": 300_000.0,
        },
    ).json()["id"]

    resp = client.get(f"/api/v1/sales/contracts/{contract_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == contract_id


def test_get_contract_not_found(client: TestClient):
    resp = client.get("/api/v1/sales/contracts/no-such-contract")
    assert resp.status_code == 404


def test_list_contracts(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-LC")
    buyer_id = _create_buyer(client, "lc@example.com")

    client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": "CNT-LC-001",
            "contract_date": "2026-03-13",
            "contract_price": 300_000.0,
        },
    )
    resp = client.get("/api/v1/sales/contracts")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_update_contract(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-UC")
    buyer_id = _create_buyer(client, "uc@example.com")

    contract_id = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": "CNT-UC-001",
            "contract_date": "2026-03-13",
            "contract_price": 300_000.0,
        },
    ).json()["id"]

    resp = client.patch(
        f"/api/v1/sales/contracts/{contract_id}",
        json={"contract_price": 350_000.0},
    )
    assert resp.status_code == 200
    assert resp.json()["contract_price"] == pytest.approx(350_000.0)


def test_cancel_contract(client: TestClient):
    _, unit_id = _create_hierarchy(client, "PRJ-CXC")
    buyer_id = _create_buyer(client, "cxc@example.com")

    contract_id = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": "CNT-CXC-001",
            "contract_date": "2026-03-13",
            "contract_price": 300_000.0,
        },
    ).json()["id"]

    resp = client.post(f"/api/v1/sales/contracts/{contract_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_convert_reservation_to_contract(client: TestClient):
    _, unit_id = _create_priced_unit(client, "PRJ-CONVAPI")
    buyer_id = _create_buyer(client, "convapi@example.com")

    res_id = client.post(
        "/api/v1/sales/reservations",
        json={"unit_id": unit_id, "buyer_id": buyer_id, **_RESERVATION_DATES},
    ).json()["id"]

    resp = client.post(
        f"/api/v1/sales/reservations/{res_id}/convert-to-contract",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "reservation_id": res_id,
            "contract_number": "CNT-CONV-001",
            "contract_date": "2026-03-13",
            "contract_price": 500_000.0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["reservation_id"] == res_id
    assert data["contract_price"] == pytest.approx(500_000.0)

    # Reservation should be converted
    res_resp = client.get(f"/api/v1/sales/reservations/{res_id}")
    assert res_resp.json()["status"] == "converted"
