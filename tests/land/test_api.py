"""
Tests for the land underwriting module.

Validates create / list / update behaviour for parcels, assumptions, and valuations.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ConflictError
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
    assert "PCL-DUP-STANDALONE" in resp2.json()["message"]


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
        with pytest.raises(ConflictError) as exc_info:
            service.create_parcel(data)
    assert "PCL-RACE" in exc_info.value.message


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
    assert project_a_id in response.json()["message"]


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
    assert "PCL-CODE-CONFLICT" in response.json()["message"]


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

# ---------------------------------------------------------------------------
# Patch semantics tests (PR-LAND-003)
# ---------------------------------------------------------------------------

def test_patch_preserves_omitted_fields(client: TestClient):
    """PATCH with partial payload must not nullify fields that were not included."""
    project_id = _create_project(client, code="PRJ-PATCH-001")
    parcel = _create_parcel(client, project_id, code="PCL-PATCH-001")
    parcel_id = parcel["id"]

    # Set extra fields on creation via another PATCH
    setup = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={
            "country": "UAE",
            "acquisition_price": 5_000_000.0,
            "transaction_cost": 200_000.0,
            "zoning_category": "Residential",
        },
    )
    assert setup.status_code == 200

    # Now patch only the asking price — other fields must survive
    response = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={"asking_price_per_sqm": 5500.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["asking_price_per_sqm"] == 5500.0
    # Fields not in the patch payload are preserved
    assert body["country"] == "UAE"
    assert body["acquisition_price"] == 5_000_000.0
    assert body["transaction_cost"] == 200_000.0
    assert body["zoning_category"] == "Residential"
    assert body["city"] == "Dubai"


def test_patch_returns_computed_metrics(client: TestClient):
    """PATCH response must include recalculated basis metrics when acquisition_price is set."""
    project_id = _create_project(client, code="PRJ-PATCH-002")
    parcel = _create_parcel(client, project_id, code="PCL-PATCH-002")
    parcel_id = parcel["id"]

    response = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={
            "acquisition_price": 5_000_000.0,
            "transaction_cost": 200_000.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    # effective_land_basis = acquisition_price + transaction_cost
    assert body["effective_land_basis"] == pytest.approx(5_200_000.0)
    # gross_land_price_per_sqm = acquisition_price / land_area_sqm = 5_000_000 / 10_000
    assert body["gross_land_price_per_sqm"] == pytest.approx(500.0)


def test_patch_cadastral_fields(client: TestClient):
    """PATCH should persist cadastral reference fields correctly."""
    project_id = _create_project(client, code="PRJ-PATCH-003")
    parcel = _create_parcel(client, project_id, code="PCL-PATCH-003")
    parcel_id = parcel["id"]

    response = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={
            "plot_number": "1234-A",
            "cadastral_id": "CAD-9999",
            "title_reference": "TD-2024-001",
            "municipality": "Dubai Municipality",
            "submarket": "JVC",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plot_number"] == "1234-A"
    assert body["cadastral_id"] == "CAD-9999"
    assert body["title_reference"] == "TD-2024-001"
    assert body["municipality"] == "Dubai Municipality"
    assert body["submarket"] == "JVC"


def test_patch_physical_fields(client: TestClient):
    """PATCH should update buildable and sellable area fields."""
    project_id = _create_project(client, code="PRJ-PATCH-004")
    parcel = _create_parcel(client, project_id, code="PCL-PATCH-004")
    parcel_id = parcel["id"]

    response = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={
            "buildable_area_sqm": 25000.0,
            "sellable_area_sqm": 20000.0,
            "front_setback_m": 5.0,
            "side_setback_m": 3.0,
            "rear_setback_m": 3.0,
            "max_floors": 12,
            "corner_plot": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["buildable_area_sqm"] == 25000.0
    assert body["sellable_area_sqm"] == 20000.0
    assert body["front_setback_m"] == 5.0
    assert body["side_setback_m"] == 3.0
    assert body["rear_setback_m"] == 3.0
    assert body["max_floors"] == 12
    assert body["corner_plot"] is True


def test_patch_computed_metrics_with_buildable_area(client: TestClient):
    """When acquisition_price and buildable_area_sqm are both set, per-buildable metric is returned."""
    project_id = _create_project(client, code="PRJ-PATCH-005")
    parcel = _create_parcel(client, project_id, code="PCL-PATCH-005")
    parcel_id = parcel["id"]

    response = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={
            "acquisition_price": 5_000_000.0,
            "transaction_cost": 0.0,
            "buildable_area_sqm": 25000.0,
            "sellable_area_sqm": 20000.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    # effective_land_price_per_buildable_sqm = 5_000_000 / 25_000 = 200
    assert body["effective_land_price_per_buildable_sqm"] == pytest.approx(200.0)
    # effective_land_price_per_sellable_sqm = 5_000_000 / 20_000 = 250
    assert body["effective_land_price_per_sellable_sqm"] == pytest.approx(250.0)


def test_patch_invalid_payload_rejected(client: TestClient):
    """PATCH with negative acquisition_price should be rejected with 422."""
    project_id = _create_project(client, code="PRJ-PATCH-006")
    parcel = _create_parcel(client, project_id, code="PCL-PATCH-006")
    parcel_id = parcel["id"]

    response = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={"acquisition_price": -1000.0},
    )
    assert response.status_code == 422


def test_patch_nonexistent_parcel_returns_404(client: TestClient):
    """PATCH on a non-existent parcel ID should return 404."""
    response = client.patch(
        "/api/v1/land/parcels/nonexistent-uuid",
        json={"city": "Abu Dhabi"},
    )
    assert response.status_code == 404


def test_get_parcel_includes_computed_metrics(client: TestClient):
    """GET /api/v1/land/parcels/{id} must include computed metrics when acquisition_price is set."""
    project_id = _create_project(client, code="PRJ-GET-001")
    parcel = _create_parcel(client, project_id, code="PCL-GET-001")
    parcel_id = parcel["id"]

    # Set acquisition price
    client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={"acquisition_price": 10_000_000.0, "transaction_cost": 400_000.0},
    )

    response = client.get(f"/api/v1/land/parcels/{parcel_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["effective_land_basis"] == pytest.approx(10_400_000.0)
    assert body["gross_land_price_per_sqm"] is not None


def test_workflow_broker_updates_asking_price(client: TestClient):
    """Simulate broker updating asking price only — other fields must be preserved."""
    project_id = _create_project(client, code="PRJ-WF-001")
    # Initial parcel with full data
    resp = client.post(
        "/api/v1/land/parcels",
        json={
            "project_id": project_id,
            "parcel_name": "Downtown Site",
            "parcel_code": "PCL-WF-001",
            "city": "Dubai",
            "country": "UAE",
            "land_area_sqm": 8000.0,
            "acquisition_price": 6_000_000.0,
            "transaction_cost": 240_000.0,
            "zoning_category": "Mixed-Use",
            "asking_price_per_sqm": 750.0,
        },
    )
    assert resp.status_code == 201
    parcel_id = resp.json()["id"]

    # Broker revises the asking price
    patch_resp = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={"asking_price_per_sqm": 820.0},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["asking_price_per_sqm"] == 820.0
    # All other fields unchanged
    assert body["city"] == "Dubai"
    assert body["country"] == "UAE"
    assert body["acquisition_price"] == 6_000_000.0
    assert body["transaction_cost"] == 240_000.0
    assert body["zoning_category"] == "Mixed-Use"
    # Computed metrics still present
    assert body["effective_land_basis"] == pytest.approx(6_240_000.0)


def test_workflow_legal_adds_cadastral_id(client: TestClient):
    """Legal team adds cadastral_id after initial intake without disturbing other data."""
    project_id = _create_project(client, code="PRJ-WF-002")
    resp = client.post(
        "/api/v1/land/parcels",
        json={
            "project_id": project_id,
            "parcel_name": "Pending Title Site",
            "parcel_code": "PCL-WF-002",
            "city": "Abu Dhabi",
            "land_area_sqm": 5000.0,
            "acquisition_price": 3_000_000.0,
        },
    )
    assert resp.status_code == 201
    parcel_id = resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={"cadastral_id": "CAD-ABU-12345", "title_reference": "TD-2024-ABD-001"},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["cadastral_id"] == "CAD-ABU-12345"
    assert body["title_reference"] == "TD-2024-ABD-001"
    # Original fields preserved
    assert body["city"] == "Abu Dhabi"
    assert body["acquisition_price"] == 3_000_000.0
    # Computed metrics still present
    assert body["effective_land_basis"] == pytest.approx(3_000_000.0)


def test_workflow_planner_adds_buildable_area(client: TestClient):
    """Planner adds buildable area — new per-buildable metric should appear after patch."""
    project_id = _create_project(client, code="PRJ-WF-003")
    resp = client.post(
        "/api/v1/land/parcels",
        json={
            "project_id": project_id,
            "parcel_name": "Development Site",
            "parcel_code": "PCL-WF-003",
            "city": "Sharjah",
            "land_area_sqm": 12000.0,
            "acquisition_price": 4_800_000.0,
        },
    )
    assert resp.status_code == 201
    parcel_id = resp.json()["id"]

    # Before: no buildable area → per-buildable metric is null
    get_resp = client.get(f"/api/v1/land/parcels/{parcel_id}")
    assert get_resp.json()["effective_land_price_per_buildable_sqm"] is None

    # Planner provides buildable area
    patch_resp = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={"buildable_area_sqm": 30000.0},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    # effective_land_price_per_buildable_sqm = 4_800_000 / 30_000 = 160
    assert body["effective_land_price_per_buildable_sqm"] == pytest.approx(160.0)


def test_workflow_sparse_parcel_remains_editable(client: TestClient):
    """A parcel created with only required fields (sparse) must be patchable without errors."""
    # Standalone parcel — no project, minimal fields
    resp = client.post(
        "/api/v1/land/parcels",
        json={"parcel_name": "Sparse Site", "parcel_code": "PCL-SPARSE-001"},
    )
    assert resp.status_code == 201
    parcel_id = resp.json()["id"]

    # Should be fully editable
    patch_resp = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={
            "city": "Ajman",
            "land_area_sqm": 3000.0,
            "zoning_category": "Industrial",
            "status": "under_review",
        },
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["city"] == "Ajman"
    assert body["land_area_sqm"] == 3000.0
    assert body["status"] == "under_review"
    # Computed metrics null because no acquisition_price yet
    assert body["effective_land_basis"] is None
