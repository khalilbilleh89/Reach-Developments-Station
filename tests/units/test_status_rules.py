"""
Tests for unit status transition rules and pricing adapter.

Validates:
  - Valid/invalid status transitions via the service layer
  - status_rules module directly (unit-level)
  - UnitPricingAdapter reads active price and pricing status
"""

import pytest
from fastapi.testclient import TestClient

from app.modules.units.status_rules import assert_valid_transition, is_valid_transition


# ---------------------------------------------------------------------------
# status_rules module — unit tests
# ---------------------------------------------------------------------------


def test_valid_transition_available_to_reserved():
    assert is_valid_transition("available", "reserved") is True


def test_valid_transition_reserved_to_under_contract():
    assert is_valid_transition("reserved", "under_contract") is True


def test_valid_transition_under_contract_to_registered():
    assert is_valid_transition("under_contract", "registered") is True


def test_no_op_transition_is_valid():
    """Same → same is always valid (idempotent)."""
    for state in ("available", "reserved", "under_contract", "registered"):
        assert is_valid_transition(state, state) is True


def test_invalid_transition_skip_step():
    """Skipping a step is not allowed."""
    assert is_valid_transition("available", "under_contract") is False
    assert is_valid_transition("available", "registered") is False
    assert is_valid_transition("reserved", "registered") is False


def test_invalid_transition_backwards():
    """Backwards movement is not allowed."""
    assert is_valid_transition("reserved", "available") is False
    assert is_valid_transition("under_contract", "reserved") is False
    assert is_valid_transition("registered", "under_contract") is False


def test_assert_valid_transition_raises_on_invalid():
    with pytest.raises(ValueError, match="Invalid status transition"):
        assert_valid_transition("available", "under_contract")


def test_assert_valid_transition_passes_on_valid():
    # Should not raise
    assert_valid_transition("available", "reserved")
    assert_valid_transition("reserved", "under_contract")
    assert_valid_transition("under_contract", "registered")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-SR"):
    project_id = client.post(
        "/api/v1/projects", json={"name": "Status Rules Project", "code": proj_code}
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
    return project_id, floor_id


def _create_unit(client: TestClient, floor_id: str, unit_number: str = "101") -> str:
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": unit_number,
            "unit_type": "studio",
            "internal_area": 55.0,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


# ---------------------------------------------------------------------------
# Status transition via the API
# ---------------------------------------------------------------------------


def test_api_valid_transition_available_to_reserved(client: TestClient):
    """PATCH status available → reserved is accepted."""
    _, floor_id = _create_hierarchy(client, "PRJ-SR1")
    unit_id = _create_unit(client, floor_id)

    response = client.patch(f"/api/v1/units/{unit_id}", json={"status": "reserved"})
    assert response.status_code == 200
    assert response.json()["status"] == "reserved"


def test_api_valid_transition_reserved_to_under_contract(client: TestClient):
    """PATCH status reserved → under_contract is accepted."""
    _, floor_id = _create_hierarchy(client, "PRJ-SR2")
    unit_id = _create_unit(client, floor_id)

    client.patch(f"/api/v1/units/{unit_id}", json={"status": "reserved"})
    response = client.patch(
        f"/api/v1/units/{unit_id}", json={"status": "under_contract"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "under_contract"


def test_api_valid_transition_under_contract_to_registered(client: TestClient):
    """PATCH status under_contract → registered is accepted."""
    _, floor_id = _create_hierarchy(client, "PRJ-SR3")
    unit_id = _create_unit(client, floor_id)

    client.patch(f"/api/v1/units/{unit_id}", json={"status": "reserved"})
    client.patch(f"/api/v1/units/{unit_id}", json={"status": "under_contract"})
    response = client.patch(f"/api/v1/units/{unit_id}", json={"status": "registered"})
    assert response.status_code == 200
    assert response.json()["status"] == "registered"


def test_api_no_op_status_transition_is_accepted(client: TestClient):
    """PATCH with the same status is a no-op and returns 200."""
    _, floor_id = _create_hierarchy(client, "PRJ-SR4")
    unit_id = _create_unit(client, floor_id)

    response = client.patch(f"/api/v1/units/{unit_id}", json={"status": "available"})
    assert response.status_code == 200
    assert response.json()["status"] == "available"


def test_api_invalid_transition_skip_step_rejected(client: TestClient):
    """PATCH status available → under_contract (skipping reserved) returns 422."""
    _, floor_id = _create_hierarchy(client, "PRJ-SR5")
    unit_id = _create_unit(client, floor_id)

    response = client.patch(
        f"/api/v1/units/{unit_id}", json={"status": "under_contract"}
    )
    assert response.status_code == 422


def test_api_invalid_transition_backwards_rejected(client: TestClient):
    """PATCH status reserved → available (backwards) returns 422."""
    _, floor_id = _create_hierarchy(client, "PRJ-SR6")
    unit_id = _create_unit(client, floor_id)

    client.patch(f"/api/v1/units/{unit_id}", json={"status": "reserved"})
    response = client.patch(f"/api/v1/units/{unit_id}", json={"status": "available"})
    assert response.status_code == 422


def test_api_invalid_transition_error_message_describes_allowed(client: TestClient):
    """422 response detail should mention the allowed next state."""
    _, floor_id = _create_hierarchy(client, "PRJ-SR7")
    unit_id = _create_unit(client, floor_id)

    response = client.patch(f"/api/v1/units/{unit_id}", json={"status": "registered"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "available" in detail
    assert "reserved" in detail


# ---------------------------------------------------------------------------
# UnitPricingAdapter — via service layer integration
# ---------------------------------------------------------------------------


def test_pricing_adapter_returns_none_when_no_pricing_record(client: TestClient):
    """Adapter returns None when the unit has no pricing record."""
    _, floor_id = _create_hierarchy(client, "PRJ-PA1")
    unit_id = _create_unit(client, floor_id)

    # No pricing record exists — GET /pricing should 404
    response = client.get(f"/api/v1/units/{unit_id}/pricing")
    assert response.status_code == 404


def test_pricing_adapter_returns_final_price_after_record_created(client: TestClient):
    """Adapter returns the final_price after a pricing record is saved."""
    _, floor_id = _create_hierarchy(client, "PRJ-PA2")
    unit_id = _create_unit(client, floor_id)

    # Save a pricing record
    save_resp = client.put(
        f"/api/v1/units/{unit_id}/pricing",
        json={"base_price": 500000.0, "manual_adjustment": 10000.0},
    )
    assert save_resp.status_code == 200
    assert float(save_resp.json()["final_price"]) == 510000.0

    # Retrieve via GET to confirm persistence
    get_resp = client.get(f"/api/v1/units/{unit_id}/pricing")
    assert get_resp.status_code == 200
    assert float(get_resp.json()["final_price"]) == 510000.0
    assert get_resp.json()["pricing_status"] == "draft"


def test_pricing_adapter_returns_none_for_unknown_unit(client: TestClient):
    """GET /pricing for unknown unit returns 404 (adapter returns None)."""
    response = client.get("/api/v1/units/no-such-unit/pricing")
    assert response.status_code == 404
