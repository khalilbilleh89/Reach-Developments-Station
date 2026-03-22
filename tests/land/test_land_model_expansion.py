"""
Tests for the expanded land parcel data model (PR-LAND-001).

Validates that the new identity, physical, economic, and governance fields
are accepted on create/update and returned in the response.
"""

import pytest
from fastapi.testclient import TestClient


def _minimal_parcel(client: TestClient, code: str = "PCL-EXP-001") -> dict:
    """Create a standalone parcel with minimum required fields and return response body."""
    resp = client.post(
        "/api/v1/land/parcels",
        json={"parcel_name": "Expanded Parcel", "parcel_code": code},
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# New fields are present in response (with None defaults)
# ---------------------------------------------------------------------------

def test_expanded_fields_present_in_response(client: TestClient):
    """All new fields must appear in the parcel response, defaulting to None."""
    data = _minimal_parcel(client, "PCL-EXP-RESP")

    # Identity & cadastral reference
    assert "plot_number" in data
    assert "cadastral_id" in data
    assert "title_reference" in data
    assert "location_link" in data
    assert "municipality" in data
    assert "submarket" in data

    # Physical / dimensional attributes
    assert "buildable_area_sqm" in data
    assert "sellable_area_sqm" in data
    assert "coverage_ratio" in data
    assert "density_ratio" in data
    assert "front_setback_m" in data
    assert "side_setback_m" in data
    assert "rear_setback_m" in data
    assert "access_notes" in data
    assert "utilities_notes" in data

    # Acquisition economics
    assert "acquisition_price" in data
    assert "transaction_cost" in data
    assert "currency" in data
    assert "asking_price_per_sqm" in data
    assert "supported_price_per_sqm" in data

    # Governance / provenance
    assert "assumption_notes" in data
    assert "source_notes" in data

    # All default to None
    new_fields = [
        "plot_number", "cadastral_id", "title_reference", "location_link",
        "municipality", "submarket", "buildable_area_sqm", "sellable_area_sqm",
        "coverage_ratio", "density_ratio", "front_setback_m", "side_setback_m",
        "rear_setback_m", "access_notes", "utilities_notes", "acquisition_price",
        "transaction_cost", "currency", "asking_price_per_sqm", "supported_price_per_sqm",
        "assumption_notes", "source_notes",
    ]
    for field in new_fields:
        assert data[field] is None, f"Expected {field} to be None by default, got {data[field]}"


# ---------------------------------------------------------------------------
# Create with full expanded payload
# ---------------------------------------------------------------------------

def test_create_parcel_with_all_expanded_fields(client: TestClient):
    """POST /parcels should accept and persist all expanded fields."""
    payload = {
        "parcel_name": "Full Underwriting Parcel",
        "parcel_code": "PCL-EXP-FULL",
        # Identity & cadastral reference
        "plot_number": "PLT-123",
        "cadastral_id": "CAD-456-789",
        "title_reference": "DEED-2024-00123",
        "location_link": "https://maps.example.com/parcel/123",
        "municipality": "Dubai Municipality",
        "submarket": "Business Bay",
        # Physical attributes
        "land_area_sqm": 5000.0,
        "buildable_area_sqm": 12500.0,
        "sellable_area_sqm": 10000.0,
        "coverage_ratio": 0.40,
        "density_ratio": 2.5,
        "front_setback_m": 5.0,
        "side_setback_m": 3.0,
        "rear_setback_m": 3.0,
        "zoning_category": "Mixed Use",
        "permitted_far": 2.5,
        "max_height_m": 45.0,
        "max_floors": 15,
        "access_notes": "Direct access from main road",
        "utilities_notes": "All utilities connected",
        # Acquisition economics
        "acquisition_price": 25000000.0,
        "transaction_cost": 1250000.0,
        "currency": "AED",
        "asking_price_per_sqm": 5500.0,
        "supported_price_per_sqm": 5000.0,
        # Governance
        "assumption_notes": "Based on Q1 2024 market data",
        "source_notes": "Surveyor report ref SR-2024-001",
    }
    resp = client.post("/api/v1/land/parcels", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["plot_number"] == "PLT-123"
    assert data["cadastral_id"] == "CAD-456-789"
    assert data["title_reference"] == "DEED-2024-00123"
    assert data["location_link"] == "https://maps.example.com/parcel/123"
    assert data["municipality"] == "Dubai Municipality"
    assert data["submarket"] == "Business Bay"

    assert data["buildable_area_sqm"] == pytest.approx(12500.0)
    assert data["sellable_area_sqm"] == pytest.approx(10000.0)
    assert data["coverage_ratio"] == pytest.approx(0.40)
    assert data["density_ratio"] == pytest.approx(2.5)
    assert data["front_setback_m"] == pytest.approx(5.0)
    assert data["side_setback_m"] == pytest.approx(3.0)
    assert data["rear_setback_m"] == pytest.approx(3.0)
    assert data["access_notes"] == "Direct access from main road"
    assert data["utilities_notes"] == "All utilities connected"

    assert data["acquisition_price"] == pytest.approx(25000000.0)
    assert data["transaction_cost"] == pytest.approx(1250000.0)
    assert data["currency"] == "AED"
    assert data["asking_price_per_sqm"] == pytest.approx(5500.0)
    assert data["supported_price_per_sqm"] == pytest.approx(5000.0)

    assert data["assumption_notes"] == "Based on Q1 2024 market data"
    assert data["source_notes"] == "Surveyor report ref SR-2024-001"


# ---------------------------------------------------------------------------
# Update with new fields
# ---------------------------------------------------------------------------

def test_update_parcel_identity_fields(client: TestClient):
    """PATCH /parcels/{id} should update identity and cadastral fields."""
    data = _minimal_parcel(client, "PCL-EXP-UPD")
    parcel_id = data["id"]

    resp = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={
            "plot_number": "PLT-999",
            "cadastral_id": "CAD-001",
            "title_reference": "DEED-REF-001",
            "location_link": "https://maps.example.com/999",
            "municipality": "Sharjah",
            "submarket": "Al Nahda",
        },
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["plot_number"] == "PLT-999"
    assert updated["cadastral_id"] == "CAD-001"
    assert updated["title_reference"] == "DEED-REF-001"
    assert updated["location_link"] == "https://maps.example.com/999"
    assert updated["municipality"] == "Sharjah"
    assert updated["submarket"] == "Al Nahda"


def test_update_parcel_physical_fields(client: TestClient):
    """PATCH /parcels/{id} should update physical/dimensional fields."""
    data = _minimal_parcel(client, "PCL-EXP-PHYS")
    parcel_id = data["id"]

    resp = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={
            "buildable_area_sqm": 8000.0,
            "sellable_area_sqm": 7000.0,
            "coverage_ratio": 0.35,
            "density_ratio": 1.8,
            "front_setback_m": 4.0,
            "side_setback_m": 2.5,
            "rear_setback_m": 2.5,
            "access_notes": "Corner plot with dual access",
            "utilities_notes": "Water and electricity connected",
        },
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["buildable_area_sqm"] == pytest.approx(8000.0)
    assert updated["sellable_area_sqm"] == pytest.approx(7000.0)
    assert updated["coverage_ratio"] == pytest.approx(0.35)
    assert updated["density_ratio"] == pytest.approx(1.8)
    assert updated["front_setback_m"] == pytest.approx(4.0)
    assert updated["side_setback_m"] == pytest.approx(2.5)
    assert updated["rear_setback_m"] == pytest.approx(2.5)
    assert updated["access_notes"] == "Corner plot with dual access"
    assert updated["utilities_notes"] == "Water and electricity connected"


def test_update_parcel_economic_fields(client: TestClient):
    """PATCH /parcels/{id} should update acquisition economics fields."""
    data = _minimal_parcel(client, "PCL-EXP-ECON")
    parcel_id = data["id"]

    resp = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={
            "acquisition_price": 15000000.0,
            "transaction_cost": 750000.0,
            "currency": "USD",
            "asking_price_per_sqm": 3200.0,
            "supported_price_per_sqm": 2900.0,
        },
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["acquisition_price"] == pytest.approx(15000000.0)
    assert updated["transaction_cost"] == pytest.approx(750000.0)
    assert updated["currency"] == "USD"
    assert updated["asking_price_per_sqm"] == pytest.approx(3200.0)
    assert updated["supported_price_per_sqm"] == pytest.approx(2900.0)


def test_update_parcel_governance_fields(client: TestClient):
    """PATCH /parcels/{id} should update governance/provenance fields."""
    data = _minimal_parcel(client, "PCL-EXP-GOV")
    parcel_id = data["id"]

    resp = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={
            "assumption_notes": "FAR assumes granted variance",
            "source_notes": "Data from municipality portal Q2 2025",
        },
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["assumption_notes"] == "FAR assumes granted variance"
    assert updated["source_notes"] == "Data from municipality portal Q2 2025"


# ---------------------------------------------------------------------------
# Validation: coverage_ratio must be between 0 and 1
# ---------------------------------------------------------------------------

def test_create_parcel_invalid_coverage_ratio(client: TestClient):
    """coverage_ratio > 1 should return 422 validation error."""
    resp = client.post(
        "/api/v1/land/parcels",
        json={
            "parcel_name": "Invalid Coverage",
            "parcel_code": "PCL-INV-COV",
            "coverage_ratio": 1.5,
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Persistence: GET after create returns new fields
# ---------------------------------------------------------------------------

def test_get_parcel_returns_expanded_fields(client: TestClient):
    """GET /parcels/{id} should return all expanded fields after create."""
    payload = {
        "parcel_name": "Persistent Parcel",
        "parcel_code": "PCL-EXP-GET",
        "plot_number": "PLT-GET",
        "cadastral_id": "CAD-GET",
        "acquisition_price": 10000000.0,
        "currency": "AED",
        "coverage_ratio": 0.5,
        "assumption_notes": "Test assumption",
    }
    create_resp = client.post("/api/v1/land/parcels", json=payload)
    assert create_resp.status_code == 201
    parcel_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/v1/land/parcels/{parcel_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["plot_number"] == "PLT-GET"
    assert data["cadastral_id"] == "CAD-GET"
    assert data["acquisition_price"] == pytest.approx(10000000.0)
    assert data["currency"] == "AED"
    assert data["coverage_ratio"] == pytest.approx(0.5)
    assert data["assumption_notes"] == "Test assumption"


# ---------------------------------------------------------------------------
# List: expanded fields included in list response
# ---------------------------------------------------------------------------

def test_list_parcels_includes_expanded_fields(client: TestClient):
    """GET /parcels list response items must include expanded fields."""
    client.post(
        "/api/v1/land/parcels",
        json={
            "parcel_name": "List Parcel",
            "parcel_code": "PCL-EXP-LIST",
            "municipality": "Abu Dhabi",
            "submarket": "Corniche",
        },
    )
    resp = client.get("/api/v1/land/parcels")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    # Find our parcel
    matches = [p for p in items if p["parcel_code"] == "PCL-EXP-LIST"]
    assert len(matches) == 1
    parcel = matches[0]
    assert parcel["municipality"] == "Abu Dhabi"
    assert parcel["submarket"] == "Corniche"
