"""
Tests for the land underwriting module.

Validates create / list / update behaviour for parcels, assumptions, and valuations.
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.modules.land.schemas import LandParcelCreate
from app.modules.land.service import LandService


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


# ---------------------------------------------------------------------------
# Pre-project independence tests (PR-B1)
# ---------------------------------------------------------------------------

def test_parcel_create_without_project(client: TestClient):
    """POST /api/v1/land/parcels without project_id should succeed.

    Land parcels must be creatable independently before any project exists.
    This validates the Land Independence boundary required by PR-B1.
    """
    response = client.post(
        "/api/v1/land/parcels",
        json={
            "parcel_name": "Standalone Parcel",
            "parcel_code": "PCL-STANDALONE",
            "city": "Dubai",
            "land_area_sqm": 5000.0,
            "permitted_far": 2.0,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] is None
    assert data["parcel_code"] == "PCL-STANDALONE"
    assert data["status"] == "draft"
    assert data["city"] == "Dubai"
    assert "id" in data


def test_parcel_assumptions_without_project(client: TestClient):
    """Assumptions can be added to a standalone parcel (no project required)."""
    resp = client.post(
        "/api/v1/land/parcels",
        json={"parcel_name": "Pre-Project Parcel", "parcel_code": "PCL-PREPRJ"},
    )
    assert resp.status_code == 201
    parcel_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/land/parcels/{parcel_id}/assumptions",
        json={"target_use": "mixed_use", "expected_sellable_ratio": 0.7},
    )
    assert resp.status_code == 201
    assert resp.json()["parcel_id"] == parcel_id
    assert resp.json()["target_use"] == "mixed_use"


def test_parcel_valuation_without_project(client: TestClient):
    """Valuations can be created for a standalone parcel (no project required)."""
    resp = client.post(
        "/api/v1/land/parcels",
        json={
            "parcel_name": "Valuation Parcel",
            "parcel_code": "PCL-VAL",
            "land_area_sqm": 10000.0,
            "permitted_far": 2.5,
        },
    )
    assert resp.status_code == 201
    parcel_id = resp.json()["id"]

    client.post(
        f"/api/v1/land/parcels/{parcel_id}/assumptions",
        json={"expected_sellable_ratio": 0.8},
    )
    resp = client.post(
        f"/api/v1/land/parcels/{parcel_id}/valuations",
        json={
            "scenario_name": "Pre-Project Base",
            "scenario_type": "base",
            "assumed_sale_price_per_sqm": 4500.0,
            "assumed_cost_per_sqm": 2500.0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["parcel_id"] == parcel_id
    assert data["scenario_name"] == "Pre-Project Base"
    # GDV = 20000 * 4500 = 90_000_000
    assert data["expected_gdv"] is not None


def test_parcel_project_id_not_required(client: TestClient):
    """project_id must be absent from LandParcelCreate — not a required field."""
    # Sending without project_id at all must return 201, not 422
    response = client.post(
        "/api/v1/land/parcels",
        json={"parcel_name": "No Project", "parcel_code": "PCL-NOPROJ"},
    )
    assert response.status_code == 201
    assert response.json()["project_id"] is None


def test_parcel_invalid_project_still_rejected(client: TestClient):
    """If project_id is explicitly provided, it must still reference a valid project."""
    response = client.post(
        "/api/v1/land/parcels",
        json={"project_id": "nonexistent-project", "parcel_name": "X", "parcel_code": "X-001"},
    )
    assert response.status_code == 404


def test_standalone_and_project_parcels_coexist(client: TestClient):
    """Standalone parcels and project-linked parcels can both exist at the same time."""
    # Create a project-linked parcel
    project_id = _create_project(client, code="PRJ-COEXIST")
    _create_parcel(client, project_id, code="PCL-PROJ-001")

    # Create a standalone parcel with no project
    resp = client.post(
        "/api/v1/land/parcels",
        json={"parcel_name": "Standalone", "parcel_code": "PCL-STANDALONE-002"},
    )
    assert resp.status_code == 201
    assert resp.json()["project_id"] is None

    # Listing all parcels should return both
    all_resp = client.get("/api/v1/land/parcels")
    assert all_resp.status_code == 200
    assert all_resp.json()["total"] >= 2

    # Filtering by project_id should only return the project parcel
    proj_resp = client.get(f"/api/v1/land/parcels?project_id={project_id}")
    assert proj_resp.status_code == 200
    assert proj_resp.json()["total"] == 1


def test_standalone_parcel_duplicate_code_rejected(client: TestClient):
    """Duplicate parcel_code among standalone parcels (no project) should return 409."""
    resp = client.post(
        "/api/v1/land/parcels",
        json={"parcel_name": "First Standalone", "parcel_code": "PCL-DUP-STANDALONE"},
    )
    assert resp.status_code == 201

    resp2 = client.post(
        "/api/v1/land/parcels",
        json={"parcel_name": "Second Standalone", "parcel_code": "PCL-DUP-STANDALONE"},
    )
    assert resp2.status_code == 409
    assert "PCL-DUP-STANDALONE" in resp2.json()["detail"]


def test_standalone_parcel_integrity_error_maps_to_409(db_session):
    """IntegrityError from DB layer must be caught and surfaced as HTTP 409.

    Simulates the race-safe path: even when the service-layer pre-check is
    bypassed (e.g., concurrent requests), an IntegrityError raised during
    DB commit is converted to a deterministic 409 response.
    """
    service = LandService(db_session)
    data = LandParcelCreate(parcel_name="Race Parcel", parcel_code="PCL-RACE")

    with patch.object(
        service.parcel_repo,
        "create",
        side_effect=IntegrityError("duplicate", {}, Exception("unique constraint")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            service.create_parcel(data)
    assert exc_info.value.status_code == 409
    assert "PCL-RACE" in exc_info.value.detail


# ---------------------------------------------------------------------------
# DELETE endpoint tests
# ---------------------------------------------------------------------------

def test_delete_parcel_returns_204(client: TestClient):
    """DELETE /api/v1/land/parcels/{id} should return 204 with empty body."""
    project_id = _create_project(client, code="PRJ-DEL-204")
    parcel = _create_parcel(client, project_id, code="PCL-DEL-001")
    parcel_id = parcel["id"]
    response = client.delete(f"/api/v1/land/parcels/{parcel_id}")
    assert response.status_code == 204
    assert response.content == b""


def test_delete_parcel_not_found(client: TestClient):
    """DELETE /api/v1/land/parcels/{id} with unknown id should return 404."""
    response = client.delete("/api/v1/land/parcels/no-such-parcel")
    assert response.status_code == 404


def test_deleted_parcel_not_in_list(client: TestClient):
    """Deleted parcel must not appear in GET /api/v1/land/parcels."""
    project_id = _create_project(client, code="PRJ-DEL-LIST")
    parcel = _create_parcel(client, project_id, code="PCL-DEL-LIST")
    parcel_id = parcel["id"]

    client.delete(f"/api/v1/land/parcels/{parcel_id}")

    # List must no longer include the deleted parcel
    list_resp = client.get(f"/api/v1/land/parcels?project_id={project_id}")
    assert list_resp.status_code == 200
    ids = [p["id"] for p in list_resp.json()["items"]]
    assert parcel_id not in ids


def test_deleted_parcel_get_returns_404(client: TestClient):
    """GET /api/v1/land/parcels/{id} must return 404 after deletion."""
    project_id = _create_project(client, code="PRJ-DEL-GET")
    parcel = _create_parcel(client, project_id, code="PCL-DEL-GET")
    parcel_id = parcel["id"]

    client.delete(f"/api/v1/land/parcels/{parcel_id}")

    get_resp = client.get(f"/api/v1/land/parcels/{parcel_id}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# assign-to-project endpoint tests
# ---------------------------------------------------------------------------

def test_assign_parcel_to_project(client: TestClient):
    """POST /land/parcels/{id}/assign-project/{project_id} links parcel to project."""
    # Create a standalone parcel (no project)
    resp = client.post(
        "/api/v1/land/parcels",
        json={"parcel_name": "Assign Parcel", "parcel_code": "PCL-ASSIGN-001"},
    )
    assert resp.status_code == 201
    parcel_id = resp.json()["id"]
    assert resp.json()["project_id"] is None

    project_id = _create_project(client, code="PRJ-ASSIGN-001")
    assign_resp = client.post(f"/api/v1/land/parcels/{parcel_id}/assign-project/{project_id}")
    assert assign_resp.status_code == 200
    assert assign_resp.json()["project_id"] == project_id


def test_assign_parcel_404_unknown_parcel(client: TestClient):
    """assign-project returns 404 when parcel does not exist."""
    project_id = _create_project(client, code="PRJ-ASGN-404P")
    response = client.post(f"/api/v1/land/parcels/no-such-parcel/assign-project/{project_id}")
    assert response.status_code == 404


def test_assign_parcel_404_unknown_project(client: TestClient):
    """assign-project returns 404 when target project does not exist."""
    resp = client.post(
        "/api/v1/land/parcels",
        json={"parcel_name": "Orphan Parcel", "parcel_code": "PCL-ASGN-NOPROJ"},
    )
    assert resp.status_code == 201
    parcel_id = resp.json()["id"]

    response = client.post(f"/api/v1/land/parcels/{parcel_id}/assign-project/no-such-project")
    assert response.status_code == 404


def test_assign_parcel_409_already_assigned_to_different_project(client: TestClient):
    """assign-project returns 409 when parcel is already linked to a different project."""
    project_a_id = _create_project(client, code="PRJ-ASGN-A")
    project_b_id = _create_project(client, code="PRJ-ASGN-B")
    parcel = _create_parcel(client, project_a_id, code="PCL-CONFLICT-001")
    parcel_id = parcel["id"]

    response = client.post(f"/api/v1/land/parcels/{parcel_id}/assign-project/{project_b_id}")
    assert response.status_code == 409
    assert project_a_id in response.json()["detail"]


def test_assign_parcel_409_same_code_in_target_project(client: TestClient):
    """assign-project returns 409 when target project already has a parcel with the same code."""
    project_id = _create_project(client, code="PRJ-ASGN-CODE")
    # A parcel already linked to the target project with code PCL-CODE-CONFLICT
    _create_parcel(client, project_id, code="PCL-CODE-CONFLICT")

    # A standalone parcel with the same code
    resp = client.post(
        "/api/v1/land/parcels",
        json={"parcel_name": "Standalone Conflict", "parcel_code": "PCL-CODE-CONFLICT"},
    )
    assert resp.status_code == 201
    standalone_id = resp.json()["id"]

    response = client.post(f"/api/v1/land/parcels/{standalone_id}/assign-project/{project_id}")
    assert response.status_code == 409
    assert "PCL-CODE-CONFLICT" in response.json()["detail"]


def test_assign_parcel_idempotent(client: TestClient):
    """assign-project called twice with same project returns success both times."""
    project_id = _create_project(client, code="PRJ-ASGN-IDEM")
    resp = client.post(
        "/api/v1/land/parcels",
        json={"parcel_name": "Idempotent Parcel", "parcel_code": "PCL-IDEM-001"},
    )
    assert resp.status_code == 201
    parcel_id = resp.json()["id"]

    first = client.post(f"/api/v1/land/parcels/{parcel_id}/assign-project/{project_id}")
    assert first.status_code == 200
    assert first.json()["project_id"] == project_id

    second = client.post(f"/api/v1/land/parcels/{parcel_id}/assign-project/{project_id}")
    assert second.status_code == 200
    assert second.json()["project_id"] == project_id