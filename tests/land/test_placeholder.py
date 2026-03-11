"""
Tests for the land underwriting module.

Validates create / list / update behaviour for parcels, assumptions, and valuations.
"""

import pytest
from fastapi.testclient import TestClient


def _create_project(client: TestClient, code: str = "PRJ-LAND") -> str:
    resp = client.post("/api/v1/projects", json={"name": "Land Test Project", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_parcel(client: TestClient, project_id: str, code: str = "PCL-001") -> dict:
    resp = client.post(
        "/api/v1/land/parcels",
        json={
            "project_id": project_id,
            "parcel_name": "Test Parcel",
            "parcel_code": code,
            "city": "Dubai",
            "land_area_sqm": 10000.0,
            "permitted_far": 2.5,
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Parcel tests
# ---------------------------------------------------------------------------

def test_parcel_create(client: TestClient):
    """POST /api/v1/land/parcels should create and return a land parcel."""
    project_id = _create_project(client)
    data = _create_parcel(client, project_id)
    assert data["project_id"] == project_id
    assert data["parcel_code"] == "PCL-001"
    assert data["status"] == "draft"
    assert data["city"] == "Dubai"
    assert "id" in data
    assert "created_at" in data


def test_parcel_list(client: TestClient):
    """GET /api/v1/land/parcels should return all parcels, filtered by project."""
    project_id = _create_project(client)
    _create_parcel(client, project_id, code="PCL-001")
    _create_parcel(client, project_id, code="PCL-002")
    response = client.get(f"/api/v1/land/parcels?project_id={project_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


def test_parcel_list_no_filter(client: TestClient):
    """GET /api/v1/land/parcels without filter should return all parcels."""
    project_id = _create_project(client)
    _create_parcel(client, project_id)
    response = client.get("/api/v1/land/parcels")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


def test_parcel_update(client: TestClient):
    """PATCH /api/v1/land/parcels/{id} should update parcel fields."""
    project_id = _create_project(client)
    parcel = _create_parcel(client, project_id)
    parcel_id = parcel["id"]
    response = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={"status": "under_review", "city": "Abu Dhabi"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "under_review"
    assert body["city"] == "Abu Dhabi"


def test_invalid_project(client: TestClient):
    """POST /api/v1/land/parcels with non-existent project_id should return 404."""
    response = client.post(
        "/api/v1/land/parcels",
        json={"project_id": "no-such-project", "parcel_name": "X", "parcel_code": "X-001"},
    )
    assert response.status_code == 404


def test_parcel_duplicate_code_in_project(client: TestClient):
    """Duplicate parcel_code within the same project should return 409."""
    project_id = _create_project(client)
    _create_parcel(client, project_id, code="PCL-DUP")
    response = client.post(
        "/api/v1/land/parcels",
        json={"project_id": project_id, "parcel_name": "Dupe", "parcel_code": "PCL-DUP"},
    )
    assert response.status_code == 409


def test_parcel_not_found(client: TestClient):
    """GET /api/v1/land/parcels/{id} with unknown id should return 404."""
    response = client.get("/api/v1/land/parcels/no-such-parcel")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Assumptions tests
# ---------------------------------------------------------------------------

def test_assumptions_create(client: TestClient):
    """POST /api/v1/land/parcels/{id}/assumptions should create assumptions."""
    project_id = _create_project(client)
    parcel = _create_parcel(client, project_id)
    parcel_id = parcel["id"]
    response = client.post(
        f"/api/v1/land/parcels/{parcel_id}/assumptions",
        json={"target_use": "residential", "expected_sellable_ratio": 0.75},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["parcel_id"] == parcel_id
    assert body["target_use"] == "residential"
    assert body["expected_sellable_ratio"] == pytest.approx(0.75)


def test_assumptions_derived_calculations(client: TestClient):
    """Creating assumptions should auto-compute buildable and sellable areas."""
    project_id = _create_project(client)
    # land_area=10000, FAR=2.5 → buildable=25000; sellable_ratio=0.8 → sellable=20000
    parcel = _create_parcel(client, project_id)
    parcel_id = parcel["id"]
    response = client.post(
        f"/api/v1/land/parcels/{parcel_id}/assumptions",
        json={"expected_sellable_ratio": 0.8},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["expected_buildable_area_sqm"] == pytest.approx(25000.0, rel=1e-3)
    assert body["expected_sellable_area_sqm"] == pytest.approx(20000.0, rel=1e-3)


def test_assumptions_fetch(client: TestClient):
    """GET /api/v1/land/parcels/{id}/assumptions should return assumptions list."""
    project_id = _create_project(client)
    parcel = _create_parcel(client, project_id)
    parcel_id = parcel["id"]
    client.post(
        f"/api/v1/land/parcels/{parcel_id}/assumptions",
        json={"target_use": "commercial"},
    )
    response = client.get(f"/api/v1/land/parcels/{parcel_id}/assumptions")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1


def test_assumptions_invalid_parcel(client: TestClient):
    """POST assumptions for non-existent parcel should return 404."""
    response = client.post(
        "/api/v1/land/parcels/no-such-parcel/assumptions",
        json={"target_use": "residential"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Valuation tests
# ---------------------------------------------------------------------------

def test_valuation_create(client: TestClient):
    """POST /api/v1/land/parcels/{id}/valuations should create a valuation."""
    project_id = _create_project(client)
    parcel = _create_parcel(client, project_id)
    parcel_id = parcel["id"]
    # Add assumptions first so sellable area is available
    client.post(
        f"/api/v1/land/parcels/{parcel_id}/assumptions",
        json={"expected_sellable_ratio": 0.75},
    )
    response = client.post(
        f"/api/v1/land/parcels/{parcel_id}/valuations",
        json={
            "scenario_name": "Base Scenario",
            "scenario_type": "base",
            "assumed_sale_price_per_sqm": 5000.0,
            "assumed_cost_per_sqm": 3000.0,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["parcel_id"] == parcel_id
    assert body["scenario_name"] == "Base Scenario"
    assert body["scenario_type"] == "base"


def test_multiple_scenarios(client: TestClient):
    """Multiple valuation scenarios can be created for the same parcel."""
    project_id = _create_project(client)
    parcel = _create_parcel(client, project_id)
    parcel_id = parcel["id"]
    client.post(
        f"/api/v1/land/parcels/{parcel_id}/assumptions",
        json={"expected_sellable_ratio": 0.75},
    )
    for scenario_type, name in [("base", "Base"), ("upside", "Upside"), ("downside", "Downside")]:
        resp = client.post(
            f"/api/v1/land/parcels/{parcel_id}/valuations",
            json={"scenario_name": name, "scenario_type": scenario_type},
        )
        assert resp.status_code == 201

    response = client.get(f"/api/v1/land/parcels/{parcel_id}/valuations")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3


def test_residual_value_calculation(client: TestClient):
    """Residual land value should be computed correctly from assumptions and prices."""
    project_id = _create_project(client)
    # land=10000 sqm, FAR=2.5 → buildable=25000; sellable_ratio=0.8 → sellable=20000
    parcel = _create_parcel(client, project_id)
    parcel_id = parcel["id"]
    client.post(
        f"/api/v1/land/parcels/{parcel_id}/assumptions",
        json={"expected_sellable_ratio": 0.8},
    )
    response = client.post(
        f"/api/v1/land/parcels/{parcel_id}/valuations",
        json={
            "scenario_name": "Test Valuation",
            "scenario_type": "base",
            "assumed_sale_price_per_sqm": 5000.0,
            "assumed_cost_per_sqm": 3000.0,
        },
    )
    assert response.status_code == 201
    body = response.json()
    # GDV = 20000 * 5000 = 100_000_000
    # Cost = 20000 * 3000 = 60_000_000
    # RLV = 100_000_000 - 60_000_000 = 40_000_000
    # RLV/sqm = 40_000_000 / 10000 = 4000
    assert body["expected_gdv"] == pytest.approx(100_000_000.0, rel=1e-3)
    assert body["expected_cost"] == pytest.approx(60_000_000.0, rel=1e-3)
    assert body["residual_land_value"] == pytest.approx(40_000_000.0, rel=1e-3)
    assert body["land_value_per_sqm"] == pytest.approx(4000.0, rel=1e-3)


def test_valuation_invalid_parcel(client: TestClient):
    """POST valuation for non-existent parcel should return 404."""
    response = client.post(
        "/api/v1/land/parcels/no-such-parcel/valuations",
        json={"scenario_name": "X", "scenario_type": "base"},
    )
    assert response.status_code == 404

