"""
Tests for unit status transition rules and pricing adapter.

Validates:
  - Valid/invalid status transitions via the service layer
  - status_rules module directly (unit-level)
  - Unit pricing endpoint behavior (GET/PUT /units/{id}/pricing)
  - UnitPricingAdapter directly (get_active_price, get_pricing_status)
"""

import pytest
from decimal import Decimal
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
    detail = response.json()["message"]
    assert "available" in detail
    assert "reserved" in detail


def test_api_terminal_state_error_message_has_no_further_transitions(
    client: TestClient,
):
    """422 from a terminal state should say 'No further transitions allowed'."""
    _, floor_id = _create_hierarchy(client, "PRJ-SR8")
    unit_id = _create_unit(client, floor_id)

    # Advance to terminal state
    client.patch(f"/api/v1/units/{unit_id}", json={"status": "reserved"})
    client.patch(f"/api/v1/units/{unit_id}", json={"status": "under_contract"})
    client.patch(f"/api/v1/units/{unit_id}", json={"status": "registered"})

    response = client.patch(f"/api/v1/units/{unit_id}", json={"status": "available"})
    assert response.status_code == 422
    detail = response.json()["message"]
    assert "No further transitions allowed" in detail
    assert "none" not in detail


# ---------------------------------------------------------------------------
# Unit pricing endpoints — API integration tests
# ---------------------------------------------------------------------------


def test_unit_pricing_endpoint_returns_404_when_no_pricing_record(client: TestClient):
    """GET /units/{id}/pricing returns 404 when no pricing record exists."""
    _, floor_id = _create_hierarchy(client, "PRJ-PA1")
    unit_id = _create_unit(client, floor_id)

    response = client.get(f"/api/v1/units/{unit_id}/pricing")
    assert response.status_code == 404


def test_unit_pricing_endpoint_returns_final_price_after_record_created(
    client: TestClient,
):
    """PUT then GET /units/{id}/pricing returns the stored final_price."""
    _, floor_id = _create_hierarchy(client, "PRJ-PA2")
    unit_id = _create_unit(client, floor_id)

    save_resp = client.put(
        f"/api/v1/units/{unit_id}/pricing",
        json={"base_price": 500000.0, "manual_adjustment": 10000.0},
    )
    assert save_resp.status_code == 200
    assert float(save_resp.json()["final_price"]) == 510000.0

    get_resp = client.get(f"/api/v1/units/{unit_id}/pricing")
    assert get_resp.status_code == 200
    assert float(get_resp.json()["final_price"]) == 510000.0
    assert get_resp.json()["pricing_status"] == "draft"


def test_unit_pricing_endpoint_returns_404_for_unknown_unit(client: TestClient):
    """GET /units/{id}/pricing for an unknown unit returns 404."""
    response = client.get("/api/v1/units/no-such-unit/pricing")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# UnitPricingAdapter — direct adapter tests
# ---------------------------------------------------------------------------


def _build_unit_via_api(client: TestClient, proj_code: str) -> str:
    """Create a full hierarchy + unit via API and return the unit id."""
    _, floor_id = _create_hierarchy(client, proj_code)
    return _create_unit(client, floor_id)


def test_adapter_get_active_price_returns_none_when_no_record(db_session):
    """UnitPricingAdapter.get_active_price() returns None when no record exists."""
    from app.modules.units.pricing_adapter import UnitPricingAdapter

    adapter = UnitPricingAdapter(db_session)
    assert adapter.get_active_price("nonexistent-unit") is None


def test_adapter_get_pricing_status_returns_none_when_no_record(db_session):
    """UnitPricingAdapter.get_pricing_status() returns None when no record exists."""
    from app.modules.units.pricing_adapter import UnitPricingAdapter

    adapter = UnitPricingAdapter(db_session)
    assert adapter.get_pricing_status("nonexistent-unit") is None


def test_adapter_get_active_price_returns_decimal_after_record_created(
    client: TestClient, db_session
):
    """UnitPricingAdapter.get_active_price() returns a Decimal equal to final_price."""
    from app.modules.units.pricing_adapter import UnitPricingAdapter

    unit_id = _build_unit_via_api(client, "PRJ-ADP3")
    client.put(
        f"/api/v1/units/{unit_id}/pricing",
        json={"base_price": 750000.0, "manual_adjustment": -25000.0},
    )

    adapter = UnitPricingAdapter(db_session)
    price = adapter.get_active_price(unit_id)
    assert price is not None
    assert isinstance(price, Decimal)
    assert price == Decimal("725000.00")


def test_adapter_get_pricing_status_returns_draft_by_default(
    client: TestClient, db_session
):
    """UnitPricingAdapter.get_pricing_status() returns 'draft' for a new record."""
    from app.modules.units.pricing_adapter import UnitPricingAdapter

    unit_id = _build_unit_via_api(client, "PRJ-ADP4")
    client.put(
        f"/api/v1/units/{unit_id}/pricing",
        json={"base_price": 300000.0},
    )

    adapter = UnitPricingAdapter(db_session)
    assert adapter.get_pricing_status(unit_id) == "draft"


def test_adapter_single_db_query_for_both_fields(client: TestClient, db_session):
    """Each public method calls _get_record exactly once (not twice).

    Verifies that _get_record is the centralised repository call path so
    a future caller retrieving both fields in sequence only pays for two
    round-trips at most (one per method), never four.
    """
    from unittest.mock import patch

    from app.modules.units.pricing_adapter import UnitPricingAdapter

    unit_id = _build_unit_via_api(client, "PRJ-ADP5")
    pricing_resp = client.put(
        f"/api/v1/units/{unit_id}/pricing",
        json={"base_price": 1000000.0},
    )
    pricing_id = pricing_resp.json()["id"]
    client.post(
        f"/api/v1/pricing/{pricing_id}/approve",
        json={"approved_by": "test.manager"},
    )

    adapter = UnitPricingAdapter(db_session)

    with patch.object(
        adapter, "_get_record", wraps=adapter._get_record
    ) as mock_get_record:
        price = adapter.get_active_price(unit_id)
        assert mock_get_record.call_count == 1

    with patch.object(
        adapter, "_get_record", wraps=adapter._get_record
    ) as mock_get_record:
        pricing_status = adapter.get_pricing_status(unit_id)
        assert mock_get_record.call_count == 1

    assert price == Decimal("1000000.00")
    assert pricing_status == "approved"
