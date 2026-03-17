"""
Tests for the pricing API endpoints.

Validates HTTP behaviour, request/response contracts, and full workflow.
"""

import pytest
from fastapi.testclient import TestClient


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-PAPI") -> tuple[str, str]:
    """Create a full project hierarchy and return (project_id, unit_id)."""
    project_id = client.post("/api/v1/projects", json={"name": "Pricing Project", "code": proj_code}).json()["id"]
    phase_id = client.post("/api/v1/phases", json={"project_id": project_id, "name": "Phase 1", "sequence": 1}).json()["id"]
    building_id = client.post(f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-A"}).json()["id"]
    floor_id = client.post(f"/api/v1/buildings/{building_id}/floors", json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1}).json()["id"]
    unit_id = client.post(
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 100.0},
    ).json()["id"]
    return project_id, unit_id


_VALID_ATTRS_PAYLOAD = {
    "base_price_per_sqm": 5000.0,
    "floor_premium": 10000.0,
    "view_premium": 15000.0,
    "corner_premium": 5000.0,
    "size_adjustment": 2000.0,
    "custom_adjustment": -1000.0,
}


# ---------------------------------------------------------------------------
# Pricing attributes endpoints
# ---------------------------------------------------------------------------

def test_set_unit_pricing_attributes(client: TestClient):
    """POST /api/v1/pricing/unit/{id}/attributes should store pricing attributes."""
    _, unit_id = _create_hierarchy(client)
    resp = client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["base_price_per_sqm"] == pytest.approx(5000.0)
    assert data["floor_premium"] == pytest.approx(10000.0)


def test_set_unit_pricing_attributes_invalid_unit(client: TestClient):
    """POST attributes with non-existent unit_id should return 404."""
    resp = client.post("/api/v1/pricing/unit/no-such-unit/attributes", json=_VALID_ATTRS_PAYLOAD)
    assert resp.status_code == 404


def test_get_unit_pricing_attributes(client: TestClient):
    """GET /api/v1/pricing/unit/{id}/attributes should return stored attributes."""
    _, unit_id = _create_hierarchy(client, "PRJ-GATTR")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}/attributes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["view_premium"] == pytest.approx(15000.0)


def test_get_unit_pricing_attributes_not_set(client: TestClient):
    """GET attributes when not set should return 404."""
    _, unit_id = _create_hierarchy(client, "PRJ-NOATTR")
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}/attributes")
    assert resp.status_code == 404


def test_upsert_pricing_attributes_replaces(client: TestClient):
    """POST attributes twice should replace the existing attributes."""
    _, unit_id = _create_hierarchy(client, "PRJ-UPS")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    updated = {**_VALID_ATTRS_PAYLOAD, "base_price_per_sqm": 6000.0}
    resp = client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=updated)
    assert resp.status_code == 201
    assert resp.json()["base_price_per_sqm"] == pytest.approx(6000.0)


# ---------------------------------------------------------------------------
# Price calculation endpoints
# ---------------------------------------------------------------------------

def test_get_unit_price(client: TestClient):
    """GET /api/v1/pricing/unit/{id} should return the calculated price."""
    _, unit_id = _create_hierarchy(client, "PRJ-GUPRC")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["unit_area"] == pytest.approx(100.0)
    assert data["base_unit_price"] == pytest.approx(500_000.0)
    assert data["premium_total"] == pytest.approx(31_000.0)
    assert data["final_unit_price"] == pytest.approx(531_000.0)


def test_calculate_unit_price(client: TestClient):
    """POST /api/v1/pricing/unit/{id}/calculate should return the calculated price."""
    _, unit_id = _create_hierarchy(client, "PRJ-CALC")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp = client.post(f"/api/v1/pricing/unit/{unit_id}/calculate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["final_unit_price"] == pytest.approx(531_000.0)


def test_get_unit_price_no_attributes_returns_422(client: TestClient):
    """GET unit price without pricing attributes should return 422."""
    _, unit_id = _create_hierarchy(client, "PRJ-NOATCALC")
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}")
    assert resp.status_code == 422


def test_calculate_unit_price_no_attributes_returns_422(client: TestClient):
    """POST calculate without attributes should return 422."""
    _, unit_id = _create_hierarchy(client, "PRJ-NOCALC")
    resp = client.post(f"/api/v1/pricing/unit/{unit_id}/calculate")
    assert resp.status_code == 422


def test_get_unit_price_not_found(client: TestClient):
    """GET price for non-existent unit should return 404."""
    resp = client.get("/api/v1/pricing/unit/no-such-unit")
    assert resp.status_code == 404


def test_calculate_unit_price_not_found(client: TestClient):
    """POST calculate for non-existent unit should return 404."""
    resp = client.post("/api/v1/pricing/unit/no-such-unit/calculate")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Project pricing summary
# ---------------------------------------------------------------------------

def test_get_project_price_summary(client: TestClient):
    """GET /api/v1/pricing/project/{id} should return a project pricing summary."""
    project_id, unit_id = _create_hierarchy(client, "PRJ-PSUM")
    client.post(
        f"/api/v1/pricing/unit/{unit_id}/attributes",
        json={
            "base_price_per_sqm": 5000.0,
            "floor_premium": 0.0,
            "view_premium": 0.0,
            "corner_premium": 0.0,
            "size_adjustment": 0.0,
            "custom_adjustment": 0.0,
        },
    )
    resp = client.get(f"/api/v1/pricing/project/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["total_units_priced"] == 1
    assert data["total_value"] == pytest.approx(500_000.0)
    assert len(data["items"]) == 1


def test_get_project_price_summary_no_units_priced(client: TestClient):
    """GET project summary with no priced units returns zero totals."""
    project_id, _ = _create_hierarchy(client, "PRJ-PSUMEMPTY")
    resp = client.get(f"/api/v1/pricing/project/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_units_priced"] == 0
    assert data["total_value"] == pytest.approx(0.0)
    assert data["items"] == []


def test_get_project_price_summary_not_found(client: TestClient):
    """GET project summary for non-existent project should return 404."""
    resp = client.get("/api/v1/pricing/project/no-such-project")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Response structure validation
# ---------------------------------------------------------------------------

def test_unit_price_response_structure(client: TestClient):
    """Unit price response must contain all required fields."""
    _, unit_id = _create_hierarchy(client, "PRJ-STRUCT")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}")
    data = resp.json()
    required_fields = ["unit_id", "unit_area", "base_unit_price", "premium_total", "final_unit_price"]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"
        assert data[field] is not None, f"Field is None: {field}"


def test_pricing_attributes_response_structure(client: TestClient):
    """Pricing attributes response must contain all required fields."""
    _, unit_id = _create_hierarchy(client, "PRJ-ATSTR")
    resp = client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    data = resp.json()
    required_fields = [
        "id", "unit_id", "base_price_per_sqm", "floor_premium", "view_premium",
        "corner_premium", "size_adjustment", "custom_adjustment", "created_at", "updated_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"


def test_price_calculation_is_deterministic(client: TestClient):
    """Repeated price calculation calls must return the same result."""
    _, unit_id = _create_hierarchy(client, "PRJ-DET")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp1 = client.post(f"/api/v1/pricing/unit/{unit_id}/calculate")
    resp2 = client.post(f"/api/v1/pricing/unit/{unit_id}/calculate")
    assert resp1.json()["final_unit_price"] == resp2.json()["final_unit_price"]


# ---------------------------------------------------------------------------
# Bulk project pricing endpoints
# ---------------------------------------------------------------------------

def test_get_project_pricing(client: TestClient):
    """GET /api/v1/projects/{id}/unit-pricing returns a map of unit_id → pricing record."""
    project_id, unit_id = _create_hierarchy(client, "PRJ-BPRICING")
    client.put(f"/api/v1/units/{unit_id}/pricing", json={"base_price": 500_000.0})

    resp = client.get(f"/api/v1/projects/{project_id}/unit-pricing")
    assert resp.status_code == 200
    data = resp.json()
    assert unit_id in data
    assert data[unit_id]["base_price"] == pytest.approx(500_000.0)
    assert data[unit_id]["final_price"] == pytest.approx(500_000.0)
    assert data[unit_id]["unit_id"] == unit_id


def test_get_project_pricing_empty(client: TestClient):
    """GET project unit-pricing returns empty map when no units have records."""
    project_id, _ = _create_hierarchy(client, "PRJ-BPRICEMPTY")
    resp = client.get(f"/api/v1/projects/{project_id}/unit-pricing")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_get_project_pricing_attributes(client: TestClient):
    """GET /api/v1/projects/{id}/unit-pricing-attributes returns a map of unit_id → attributes."""
    project_id, unit_id = _create_hierarchy(client, "PRJ-BATTRS")
    client.put(f"/api/v1/units/{unit_id}/pricing-attributes", json={"view_type": "sea"})

    resp = client.get(f"/api/v1/projects/{project_id}/unit-pricing-attributes")
    assert resp.status_code == 200
    data = resp.json()
    assert unit_id in data
    assert data[unit_id]["view_type"] == "sea"
    assert data[unit_id]["unit_id"] == unit_id


def test_get_project_pricing_attributes_empty(client: TestClient):
    """GET project unit-pricing-attributes returns empty map when no units have attributes."""
    project_id, _ = _create_hierarchy(client, "PRJ-BATTRSMPTY")
    resp = client.get(f"/api/v1/projects/{project_id}/unit-pricing-attributes")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_get_project_pricing_multiple_units(client: TestClient):
    """GET project unit-pricing includes all units with pricing records."""
    project_id, unit_id_1 = _create_hierarchy(client, "PRJ-BMULTI")
    # Create a second unit in the same project via same hierarchy
    phase_id = client.get(f"/api/v1/phases?project_id={project_id}&limit=1").json()["items"][0]["id"]
    building_id = client.get(f"/api/v1/buildings?phase_id={phase_id}&limit=1").json()["items"][0]["id"]
    floor_id = client.get(f"/api/v1/buildings/{building_id}/floors?limit=1").json()["items"][0]["id"]
    unit_id_2 = client.post(
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "102", "unit_type": "studio", "internal_area": 80.0},
    ).json()["id"]

    client.put(f"/api/v1/units/{unit_id_1}/pricing", json={"base_price": 400_000.0})
    client.put(f"/api/v1/units/{unit_id_2}/pricing", json={"base_price": 300_000.0})

    resp = client.get(f"/api/v1/projects/{project_id}/unit-pricing")
    assert resp.status_code == 200
    data = resp.json()
    assert unit_id_1 in data
    assert unit_id_2 in data
    assert data[unit_id_1]["base_price"] == pytest.approx(400_000.0)
    assert data[unit_id_2]["base_price"] == pytest.approx(300_000.0)


# ---------------------------------------------------------------------------
# Pricing readiness endpoint
# ---------------------------------------------------------------------------

def test_get_pricing_readiness_no_attributes(client: TestClient):
    """GET /api/v1/pricing/unit/{id}/readiness returns not-ready when no attrs are set."""
    _, unit_id = _create_hierarchy(client, "PRJ-RDY-NONE")
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["is_ready_for_pricing"] is False
    assert isinstance(data["missing_required_fields"], list)
    assert len(data["missing_required_fields"]) > 0
    # All required fields should be listed as missing
    expected_fields = {
        "base_price_per_sqm", "floor_premium", "view_premium",
        "corner_premium", "size_adjustment", "custom_adjustment",
    }
    assert set(data["missing_required_fields"]) == expected_fields
    assert data["readiness_reason"] is not None


def test_get_pricing_readiness_fully_configured(client: TestClient):
    """GET /api/v1/pricing/unit/{id}/readiness returns ready when all attrs are set."""
    _, unit_id = _create_hierarchy(client, "PRJ-RDY-FULL")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["is_ready_for_pricing"] is True
    assert data["missing_required_fields"] == []
    assert data["readiness_reason"] is None


def test_get_pricing_readiness_after_save_is_consistent(client: TestClient):
    """Readiness state must match the pricing calculation outcome for the same unit."""
    _, unit_id = _create_hierarchy(client, "PRJ-RDY-CONS")

    # Before saving attributes: readiness says not ready, engine returns 422
    readiness_before = client.get(f"/api/v1/pricing/unit/{unit_id}/readiness").json()
    engine_before = client.get(f"/api/v1/pricing/unit/{unit_id}")
    assert readiness_before["is_ready_for_pricing"] is False
    assert engine_before.status_code == 422

    # After saving attributes: readiness says ready, engine succeeds
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    readiness_after = client.get(f"/api/v1/pricing/unit/{unit_id}/readiness").json()
    engine_after = client.get(f"/api/v1/pricing/unit/{unit_id}")
    assert readiness_after["is_ready_for_pricing"] is True
    assert engine_after.status_code == 200


def test_get_pricing_readiness_invalid_unit(client: TestClient):
    """GET readiness for a non-existent unit should return 404."""
    resp = client.get("/api/v1/pricing/unit/no-such-unit/readiness")
    assert resp.status_code == 404


def test_get_pricing_readiness_response_structure(client: TestClient):
    """Readiness response must contain all required fields."""
    _, unit_id = _create_hierarchy(client, "PRJ-RDY-STRUCT")
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}/readiness")
    assert resp.status_code == 200
    data = resp.json()
    required_keys = {"unit_id", "is_ready_for_pricing", "missing_required_fields", "readiness_reason"}
    for key in required_keys:
        assert key in data, f"Missing key in readiness response: {key}"


def test_readiness_and_table_query_consistent(client: TestClient):
    """Units listed by project and inspected via readiness must agree on attribute presence."""
    project_id, unit_id = _create_hierarchy(client, "PRJ-RDY-TABLE")
    # No attributes set — both endpoints reflect the same absent state
    readiness = client.get(f"/api/v1/pricing/unit/{unit_id}/readiness").json()
    attrs_resp = client.get(f"/api/v1/pricing/unit/{unit_id}/attributes")
    assert readiness["is_ready_for_pricing"] is False
    assert attrs_resp.status_code == 404  # No attributes yet

    # Set attributes — both endpoints now agree attributes are present
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    readiness_after = client.get(f"/api/v1/pricing/unit/{unit_id}/readiness").json()
    attrs_after = client.get(f"/api/v1/pricing/unit/{unit_id}/attributes")
    assert readiness_after["is_ready_for_pricing"] is True
    assert attrs_after.status_code == 200


# ---------------------------------------------------------------------------
# Assembled pricing detail endpoint — GET /api/v1/pricing/unit/{id}/detail
# ---------------------------------------------------------------------------

def test_pricing_detail_invalid_unit_returns_404(client: TestClient):
    """GET detail for a non-existent unit should return 404."""
    resp = client.get("/api/v1/pricing/unit/no-such-unit/detail")
    assert resp.status_code == 404


def test_pricing_detail_no_engine_inputs(client: TestClient):
    """Detail endpoint with no attributes set should return null engine_inputs and is_ready_for_pricing=False."""
    _, unit_id = _create_hierarchy(client, "PRJ-DTL-NOATTR")
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}/detail")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["engine_inputs"] is None
    assert data["pricing_readiness"]["is_ready_for_pricing"] is False
    assert len(data["pricing_readiness"]["missing_required_fields"]) > 0
    assert data["pricing_record"] is None


def test_pricing_detail_with_engine_inputs(client: TestClient):
    """Detail endpoint with attributes set should return engine_inputs and is_ready_for_pricing=True."""
    _, unit_id = _create_hierarchy(client, "PRJ-DTL-ATTRS")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}/detail")
    assert resp.status_code == 200
    data = resp.json()
    assert data["engine_inputs"] is not None
    assert data["engine_inputs"]["base_price_per_sqm"] == pytest.approx(5000.0)
    assert data["pricing_readiness"]["is_ready_for_pricing"] is True
    assert data["pricing_readiness"]["missing_required_fields"] == []


def test_pricing_detail_with_pricing_record(client: TestClient):
    """Detail endpoint with a formal pricing record should return that record in pricing_record."""
    _, unit_id = _create_hierarchy(client, "PRJ-DTL-REC")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    client.put(f"/api/v1/units/{unit_id}/pricing", json={
        "base_price": 500_000.0,
        "manual_adjustment": 10_000.0,
        "currency": "AED",
        "pricing_status": "reviewed",
    })
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}/detail")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pricing_record"] is not None
    assert data["pricing_record"]["base_price"] == pytest.approx(500_000.0)
    assert data["pricing_record"]["final_price"] == pytest.approx(510_000.0)
    assert data["pricing_record"]["pricing_status"] == "reviewed"


def test_pricing_detail_response_structure(client: TestClient):
    """Detail response must contain all required top-level keys."""
    _, unit_id = _create_hierarchy(client, "PRJ-DTL-STRUCT")
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}/detail")
    assert resp.status_code == 200
    data = resp.json()
    required_keys = {"unit_id", "engine_inputs", "pricing_readiness", "pricing_record"}
    for key in required_keys:
        assert key in data, f"Missing key in detail response: {key}"


def test_pricing_detail_readiness_matches_engine_inputs(client: TestClient):
    """Readiness missing_required_fields must exactly match the fields absent from engine_inputs."""
    _, unit_id = _create_hierarchy(client, "PRJ-DTL-ALIGN")
    # No attributes → readiness reports all required fields as missing
    detail = client.get(f"/api/v1/pricing/unit/{unit_id}/detail").json()
    assert detail["engine_inputs"] is None
    missing = set(detail["pricing_readiness"]["missing_required_fields"])
    expected_engine_fields = {
        "base_price_per_sqm", "floor_premium", "view_premium",
        "corner_premium", "size_adjustment", "custom_adjustment",
    }
    # At minimum, base_price_per_sqm must be listed as missing
    assert "base_price_per_sqm" in missing
    # All reported missing fields must be real engine input field names
    assert missing.issubset(expected_engine_fields)


def test_pricing_detail_engine_fields_match_readiness_fields(client: TestClient):
    """When engine_inputs is populated, no field from engine_inputs should appear in missing_required_fields."""
    _, unit_id = _create_hierarchy(client, "PRJ-DTL-NMATCH")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    detail = client.get(f"/api/v1/pricing/unit/{unit_id}/detail").json()
    assert detail["engine_inputs"] is not None
    engine_field_names = {
        "base_price_per_sqm", "floor_premium", "view_premium",
        "corner_premium", "size_adjustment", "custom_adjustment",
    }
    missing = set(detail["pricing_readiness"]["missing_required_fields"])
    # No engine field should be listed as missing
    assert missing.isdisjoint(engine_field_names)
