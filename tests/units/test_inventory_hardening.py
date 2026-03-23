"""
Tests for Unit Inventory Engine Hardening (PR-11).

Validates:
  - Hierarchy validation (floor → building → phase chain)
  - Dimension sanity checks (gross_area, livable_area consistency)
  - Unit readiness endpoint (GET /units/{id}/readiness)
  - Status-based inventory filtering (GET /units?status=...)
  - Building-scoped inventory filtering (GET /units?building_id=...)
  - assert_unit_ready_for_pricing / assert_unit_ready_for_sales logic
  - status_rules.allowed_next_state helper
"""

import pytest
from fastapi.testclient import TestClient

from app.modules.units.status_rules import allowed_next_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-IH"):
    """Create a minimal project → phase → building → floor hierarchy.

    Returns (project_id, building_id, floor_id).
    """
    project_id = client.post(
        "/api/v1/projects", json={"name": "Hardening Project", "code": proj_code}
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
    return project_id, building_id, floor_id


def _create_unit(client: TestClient, floor_id: str, unit_number: str = "101", **extra) -> str:
    payload = {
        "floor_id": floor_id,
        "unit_number": unit_number,
        "unit_type": "studio",
        "internal_area": 55.0,
        **extra,
    }
    response = client.post("/api/v1/units", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ---------------------------------------------------------------------------
# status_rules.allowed_next_state — unit tests
# ---------------------------------------------------------------------------


def test_allowed_next_state_from_available():
    assert allowed_next_state("available") == "reserved"


def test_allowed_next_state_from_reserved():
    assert allowed_next_state("reserved") == "under_contract"


def test_allowed_next_state_from_under_contract():
    assert allowed_next_state("under_contract") == "registered"


def test_allowed_next_state_from_registered_is_none():
    assert allowed_next_state("registered") is None


def test_allowed_next_state_unknown_status_returns_none():
    assert allowed_next_state("unknown_state") is None


# ---------------------------------------------------------------------------
# Hierarchy validation
# ---------------------------------------------------------------------------


def test_create_unit_invalid_floor_returns_404(client: TestClient):
    """Creating a unit with a non-existent floor_id returns 404."""
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": "no-such-floor",
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 55.0,
        },
    )
    assert response.status_code == 404


def test_create_unit_valid_hierarchy_succeeds(client: TestClient):
    """Creating a unit under a valid floor/building/phase chain succeeds."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-H1")
    unit_id = _create_unit(client, floor_id)
    assert unit_id


# ---------------------------------------------------------------------------
# Dimension validation
# ---------------------------------------------------------------------------


def test_create_unit_gross_area_less_than_internal_area_rejected(client: TestClient):
    """gross_area < internal_area must be rejected with 422."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-D1")
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "D01",
            "unit_type": "studio",
            "internal_area": 80.0,
            "gross_area": 60.0,  # invalid: < internal_area
        },
    )
    assert response.status_code == 422


def test_create_unit_gross_area_equals_internal_area_accepted(client: TestClient):
    """gross_area == internal_area is accepted."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-D2")
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "D02",
            "unit_type": "studio",
            "internal_area": 80.0,
            "gross_area": 80.0,
        },
    )
    assert response.status_code == 201


def test_create_unit_gross_area_greater_than_internal_area_accepted(client: TestClient):
    """gross_area > internal_area is the normal case and is accepted."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-D3")
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "D03",
            "unit_type": "studio",
            "internal_area": 80.0,
            "gross_area": 95.0,
        },
    )
    assert response.status_code == 201


def test_create_unit_livable_area_exceeds_internal_area_rejected(client: TestClient):
    """livable_area > internal_area must be rejected with 422."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-D4")
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "D04",
            "unit_type": "studio",
            "internal_area": 50.0,
            "livable_area": 70.0,  # invalid: > internal_area
        },
    )
    assert response.status_code == 422


def test_create_unit_livable_area_equals_internal_area_accepted(client: TestClient):
    """livable_area == internal_area is accepted."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-D5")
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "D05",
            "unit_type": "studio",
            "internal_area": 50.0,
            "livable_area": 50.0,
        },
    )
    assert response.status_code == 201


def test_update_unit_gross_area_less_than_internal_area_rejected(client: TestClient):
    """PATCH with gross_area < current internal_area must be rejected."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-D6")
    unit_id = _create_unit(client, floor_id, "D06", internal_area=80.0)

    response = client.patch(
        f"/api/v1/units/{unit_id}",
        json={"internal_area": 80.0, "gross_area": 40.0},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Unit readiness endpoint
# ---------------------------------------------------------------------------


def test_unit_readiness_available_unit_ready_for_pricing(client: TestClient):
    """Available unit with no pricing record is ready for pricing but not sales."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-R1")
    unit_id = _create_unit(client, floor_id)

    response = client.get(f"/api/v1/units/{unit_id}/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["unit_id"] == unit_id
    assert data["is_ready_for_pricing"] is True
    assert data["pricing_blocking_reasons"] == []


def test_unit_readiness_available_no_approved_pricing_not_ready_for_sales(client: TestClient):
    """Available unit without approved pricing is not ready for sales."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-R2")
    unit_id = _create_unit(client, floor_id)

    response = client.get(f"/api/v1/units/{unit_id}/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["is_ready_for_sales"] is False
    assert len(data["sales_blocking_reasons"]) > 0


def test_unit_readiness_available_with_approved_pricing_ready_for_sales(client: TestClient):
    """Available unit with approved pricing record is ready for sales."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-R3")
    unit_id = _create_unit(client, floor_id)

    # Create a pricing record then approve it via the governed endpoint.
    pricing_resp = client.put(
        f"/api/v1/units/{unit_id}/pricing",
        json={"base_price": 500000.0},
    )
    assert pricing_resp.status_code == 200, pricing_resp.text
    pricing_id = pricing_resp.json()["id"]
    approve_resp = client.post(
        f"/api/v1/pricing/{pricing_id}/approve",
        json={"approved_by": "manager@example.com"},
    )
    assert approve_resp.status_code == 200, approve_resp.text

    response = client.get(f"/api/v1/units/{unit_id}/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["is_ready_for_pricing"] is True
    assert data["is_ready_for_sales"] is True
    assert data["pricing_blocking_reasons"] == []
    assert data["sales_blocking_reasons"] == []


def test_unit_readiness_draft_pricing_not_ready_for_sales(client: TestClient):
    """Unit with draft pricing is not ready for sales."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-R4")
    unit_id = _create_unit(client, floor_id)

    pricing_resp = client.put(
        f"/api/v1/units/{unit_id}/pricing",
        json={"base_price": 400000.0, "pricing_status": "draft"},
    )
    assert pricing_resp.status_code == 200, pricing_resp.text

    response = client.get(f"/api/v1/units/{unit_id}/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["is_ready_for_sales"] is False
    assert any("draft" in reason for reason in data["sales_blocking_reasons"])


def test_unit_readiness_reserved_unit_not_ready_for_pricing(client: TestClient):
    """Reserved unit is not ready for pricing (status gate)."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-R5")
    unit_id = _create_unit(client, floor_id)

    # Advance to reserved status
    client.patch(f"/api/v1/units/{unit_id}", json={"status": "reserved"})

    response = client.get(f"/api/v1/units/{unit_id}/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["is_ready_for_pricing"] is False
    assert data["is_ready_for_sales"] is False
    assert len(data["pricing_blocking_reasons"]) > 0
    assert any("reserved" in reason for reason in data["pricing_blocking_reasons"])


def test_unit_readiness_not_found_returns_404(client: TestClient):
    """GET /units/{id}/readiness for unknown unit returns 404."""
    response = client.get("/api/v1/units/no-such-unit/readiness")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Inventory filtering by status
# ---------------------------------------------------------------------------


def test_list_units_filtered_by_status(client: TestClient):
    """GET /units?status=available returns only available units."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-S1")
    unit_id_1 = _create_unit(client, floor_id, "S01")
    unit_id_2 = _create_unit(client, floor_id, "S02")

    # Advance second unit to reserved
    client.patch(f"/api/v1/units/{unit_id_2}", json={"status": "reserved"})

    response = client.get(f"/api/v1/units?floor_id={floor_id}&status=available")
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    assert unit_id_1 in ids
    assert unit_id_2 not in ids


def test_list_units_filtered_by_status_reserved(client: TestClient):
    """GET /units?status=reserved returns only reserved units."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-S2")
    unit_id_1 = _create_unit(client, floor_id, "S11")
    unit_id_2 = _create_unit(client, floor_id, "S12")

    client.patch(f"/api/v1/units/{unit_id_2}", json={"status": "reserved"})

    response = client.get(f"/api/v1/units?floor_id={floor_id}&status=reserved")
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    assert unit_id_2 in ids
    assert unit_id_1 not in ids


def test_list_units_no_status_filter_returns_all(client: TestClient):
    """GET /units without status filter returns units of all statuses."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-S3")
    unit_id_1 = _create_unit(client, floor_id, "S21")
    unit_id_2 = _create_unit(client, floor_id, "S22")
    client.patch(f"/api/v1/units/{unit_id_2}", json={"status": "reserved"})

    response = client.get(f"/api/v1/units?floor_id={floor_id}")
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    assert unit_id_1 in ids
    assert unit_id_2 in ids


# ---------------------------------------------------------------------------
# Inventory filtering by building
# ---------------------------------------------------------------------------


def test_list_units_filtered_by_building_id(client: TestClient):
    """GET /units?building_id=... returns only units in that building."""
    project_id, building_id, floor_id = _create_hierarchy(client, "PRJ-IH-B1")

    # Create a second building with its own floor and unit
    phase_resp = client.get(f"/api/v1/phases?project_id={project_id}&limit=10").json()
    phase_id = phase_resp["items"][0]["id"]
    building2_id = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block B", "code": "BLK-B"},
    ).json()["id"]
    floor2_id = client.post(
        f"/api/v1/buildings/{building2_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]

    unit_id_b1 = _create_unit(client, floor_id, "B101")
    unit_id_b2 = _create_unit(client, floor2_id, "B201")

    response = client.get(f"/api/v1/units?building_id={building_id}")
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    assert unit_id_b1 in ids
    assert unit_id_b2 not in ids


# ---------------------------------------------------------------------------
# Typed status filter — invalid enum value rejection
# ---------------------------------------------------------------------------


def test_list_units_invalid_status_filter_returns_422(client: TestClient):
    """GET /units?status=not_a_status should be rejected with 422 (typed enum filter)."""
    response = client.get("/api/v1/units?status=not_a_real_status")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Sparse-update dimension validation
# ---------------------------------------------------------------------------


def test_sparse_patch_gross_area_below_existing_internal_area_rejected(client: TestClient):
    """PATCH sending only gross_area below the existing internal_area is rejected.

    Without effective-state validation, a sparse PATCH with only gross_area
    could set gross_area < internal_area because internal_area is missing from
    the payload. With effective-state validation, the backend falls back to the
    persisted internal_area and correctly rejects the request.
    """
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-SP1")
    unit_id = _create_unit(client, floor_id, "SP01", internal_area=80.0)

    # Send only gross_area — the backend must compare it against existing internal_area=80
    response = client.patch(
        f"/api/v1/units/{unit_id}",
        json={"gross_area": 50.0},  # 50 < 80 → invalid effective state
    )
    assert response.status_code == 422
    assert "gross_area" in response.json()["message"]


def test_sparse_patch_gross_area_valid_against_existing_internal_area_accepted(client: TestClient):
    """PATCH sending only gross_area >= existing internal_area is accepted."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-SP2")
    unit_id = _create_unit(client, floor_id, "SP02", internal_area=80.0)

    response = client.patch(
        f"/api/v1/units/{unit_id}",
        json={"gross_area": 95.0},  # 95 >= 80 → valid
    )
    assert response.status_code == 200
    assert float(response.json()["gross_area"]) == 95.0


def test_sparse_patch_livable_area_above_existing_internal_area_rejected(client: TestClient):
    """PATCH sending only livable_area > existing internal_area is rejected."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-SP3")
    unit_id = _create_unit(client, floor_id, "SP03", internal_area=60.0)

    response = client.patch(
        f"/api/v1/units/{unit_id}",
        json={"livable_area": 80.0},  # 80 > 60 → invalid effective state
    )
    assert response.status_code == 422
    assert "livable_area" in response.json()["message"]


def test_sparse_patch_livable_area_valid_against_existing_internal_area_accepted(client: TestClient):
    """PATCH sending only livable_area <= existing internal_area is accepted."""
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-SP4")
    unit_id = _create_unit(client, floor_id, "SP04", internal_area=60.0)

    response = client.patch(
        f"/api/v1/units/{unit_id}",
        json={"livable_area": 55.0},  # 55 <= 60 → valid
    )
    assert response.status_code == 200
    assert float(response.json()["livable_area"]) == 55.0


def test_sparse_patch_internal_area_above_existing_gross_area_rejected(client: TestClient):
    """PATCH raising internal_area above the existing gross_area is rejected.

    The unit already has gross_area set. Raising internal_area above it
    should be caught by effective-state validation even though gross_area
    is not in the PATCH payload (effective gross_area falls back to the
    persisted value of 80, while the patched internal_area = 90 > 80).
    """
    _, _, floor_id = _create_hierarchy(client, "PRJ-IH-SP5")
    # Create unit: internal_area=60, gross_area=80
    unit_id = _create_unit(client, floor_id, "SP05", internal_area=60.0, gross_area=80.0)

    # Raise internal_area above existing gross_area=80 → gross_area(80) < internal_area(90)
    response = client.patch(
        f"/api/v1/units/{unit_id}",
        json={"internal_area": 90.0},  # 80 < 90 → gross_area < internal_area → invalid
    )
    assert response.status_code == 422
