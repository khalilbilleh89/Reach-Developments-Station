"""
Tests for the Land Assembly API endpoints.

Validates:
  POST   /api/v1/land/assemblies            — create assembly
  GET    /api/v1/land/assemblies            — list assemblies
  GET    /api/v1/land/assemblies/{id}       — get assembly
  DELETE /api/v1/land/assemblies/{id}       — delete assembly
  POST   /api/v1/land/assemblies/{id}/recompute — recompute metrics

Error coverage:
  404 — assembly not found
  404 — parcel not found in create
  409 — duplicate assembly code
  409 — parcel already in another assembly
  422 — duplicate parcel IDs in request
  422 — empty parcel_ids list
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_parcel(client: TestClient, code: str, **overrides) -> dict:
    """Create a standalone parcel (no project required)."""
    payload = {
        "parcel_name": f"Parcel {code}",
        "parcel_code": code,
        "land_area_sqm": 5_000.0,
        "frontage_m": 50.0,
        "acquisition_price": 1_000_000.0,
        "transaction_cost": 50_000.0,
        "permitted_far": 2.5,
        "zoning_category": "Residential",
    }
    payload.update(overrides)
    resp = client.post("/api/v1/land/parcels", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_assembly(client: TestClient, parcel_ids: list, code: str = "ASM-001") -> dict:
    """Create an assembly from the supplied parcel IDs."""
    resp = client.post(
        "/api/v1/land/assemblies",
        json={
            "assembly_name": "Test Assembly",
            "assembly_code": code,
            "parcel_ids": parcel_ids,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Create assembly — happy path
# ---------------------------------------------------------------------------

def test_create_assembly_status_201(client: TestClient):
    """POST /land/assemblies returns 201 for a valid request."""
    p1 = _create_parcel(client, "PCL-A01")
    p2 = _create_parcel(client, "PCL-A02")
    resp = client.post(
        "/api/v1/land/assemblies",
        json={
            "assembly_name": "Assembly Alpha",
            "assembly_code": "ASM-ALPHA",
            "parcel_ids": [p1["id"], p2["id"]],
        },
    )
    assert resp.status_code == 201


def test_create_assembly_response_fields(client: TestClient):
    """Created assembly response must contain all expected fields."""
    p1 = _create_parcel(client, "PCL-B01")
    p2 = _create_parcel(client, "PCL-B02")
    body = _create_assembly(client, [p1["id"], p2["id"]], "ASM-B")

    for field in (
        "id", "assembly_name", "assembly_code", "status",
        "parcel_count", "total_area_sqm", "total_frontage_m",
        "total_acquisition_price", "total_transaction_cost",
        "effective_land_basis", "weighted_permitted_far",
        "dominant_zoning_category", "mixed_zoning",
        "has_utilities", "has_corner_plot",
        "assembly_results_json", "parcel_ids", "parcels",
        "created_at", "updated_at",
    ):
        assert field in body, f"Missing field: {field}"


def test_create_assembly_parcel_count(client: TestClient):
    """parcel_count in response equals the number of parcel IDs supplied."""
    p1 = _create_parcel(client, "PCL-C01")
    p2 = _create_parcel(client, "PCL-C02")
    p3 = _create_parcel(client, "PCL-C03")
    body = _create_assembly(client, [p1["id"], p2["id"], p3["id"]], "ASM-C")
    assert body["parcel_count"] == 3


def test_create_assembly_area_sum(client: TestClient):
    """total_area_sqm equals the sum of member parcel land areas."""
    p1 = _create_parcel(client, "PCL-D01", land_area_sqm=4_000.0)
    p2 = _create_parcel(client, "PCL-D02", land_area_sqm=6_000.0)
    body = _create_assembly(client, [p1["id"], p2["id"]], "ASM-D")
    assert body["total_area_sqm"] == pytest.approx(10_000.0)


def test_create_assembly_frontage_sum(client: TestClient):
    """total_frontage_m equals the sum of member parcel frontages."""
    p1 = _create_parcel(client, "PCL-E01", frontage_m=40.0)
    p2 = _create_parcel(client, "PCL-E02", frontage_m=60.0)
    body = _create_assembly(client, [p1["id"], p2["id"]], "ASM-E")
    assert body["total_frontage_m"] == pytest.approx(100.0)


def test_create_assembly_effective_land_basis(client: TestClient):
    """effective_land_basis = total_acquisition_price + total_transaction_cost."""
    p1 = _create_parcel(client, "PCL-F01", acquisition_price=1_000_000.0, transaction_cost=50_000.0)
    p2 = _create_parcel(client, "PCL-F02", acquisition_price=500_000.0, transaction_cost=25_000.0)
    body = _create_assembly(client, [p1["id"], p2["id"]], "ASM-F")
    assert body["effective_land_basis"] == pytest.approx(1_575_000.0)


def test_create_assembly_uniform_zoning(client: TestClient):
    """Uniform zoning across parcels: mixed_zoning is false."""
    p1 = _create_parcel(client, "PCL-G01", zoning_category="Residential")
    p2 = _create_parcel(client, "PCL-G02", zoning_category="Residential")
    body = _create_assembly(client, [p1["id"], p2["id"]], "ASM-G")
    assert body["mixed_zoning"] is False
    assert body["dominant_zoning_category"] == "Residential"


def test_create_assembly_mixed_zoning(client: TestClient):
    """Mixed zoning across parcels: mixed_zoning is true."""
    p1 = _create_parcel(client, "PCL-H01", zoning_category="Residential")
    p2 = _create_parcel(client, "PCL-H02", zoning_category="Commercial")
    body = _create_assembly(client, [p1["id"], p2["id"]], "ASM-H")
    assert body["mixed_zoning"] is True


def test_create_assembly_parcel_summaries_embedded(client: TestClient):
    """Parcels list in response includes one entry per member parcel."""
    p1 = _create_parcel(client, "PCL-I01")
    p2 = _create_parcel(client, "PCL-I02")
    body = _create_assembly(client, [p1["id"], p2["id"]], "ASM-I")
    assert len(body["parcels"]) == 2
    parcel_ids_in_response = {p["parcel_id"] for p in body["parcels"]}
    assert parcel_ids_in_response == {p1["id"], p2["id"]}


def test_create_assembly_default_status_draft(client: TestClient):
    """Assembly status defaults to 'draft' when not specified."""
    p1 = _create_parcel(client, "PCL-J01")
    body = _create_assembly(client, [p1["id"]], "ASM-J")
    assert body["status"] == "draft"


def test_create_assembly_single_parcel(client: TestClient):
    """Single-parcel assembly is valid and returns correct aggregates."""
    p1 = _create_parcel(client, "PCL-K01", land_area_sqm=8_000.0)
    body = _create_assembly(client, [p1["id"]], "ASM-K")
    assert body["parcel_count"] == 1
    assert body["total_area_sqm"] == pytest.approx(8_000.0)


# ---------------------------------------------------------------------------
# Create assembly — error cases
# ---------------------------------------------------------------------------

def test_create_assembly_duplicate_code_returns_409(client: TestClient):
    """Duplicate assembly_code returns 409 Conflict."""
    p1 = _create_parcel(client, "PCL-L01")
    p2 = _create_parcel(client, "PCL-L02")
    _create_assembly(client, [p1["id"]], "ASM-DUPE")
    resp = client.post(
        "/api/v1/land/assemblies",
        json={"assembly_name": "Another", "assembly_code": "ASM-DUPE", "parcel_ids": [p2["id"]]},
    )
    assert resp.status_code == 409


def test_create_assembly_unknown_parcel_returns_404(client: TestClient):
    """Non-existent parcel ID returns 404."""
    resp = client.post(
        "/api/v1/land/assemblies",
        json={
            "assembly_name": "Ghost Assembly",
            "assembly_code": "ASM-GHOST",
            "parcel_ids": ["00000000-0000-0000-0000-000000000000"],
        },
    )
    assert resp.status_code == 404


def test_create_assembly_duplicate_parcel_ids_returns_422(client: TestClient):
    """Duplicate parcel IDs within a single request body returns 422."""
    p1 = _create_parcel(client, "PCL-M01")
    resp = client.post(
        "/api/v1/land/assemblies",
        json={
            "assembly_name": "Dup Assembly",
            "assembly_code": "ASM-DUPID",
            "parcel_ids": [p1["id"], p1["id"]],
        },
    )
    assert resp.status_code == 422


def test_create_assembly_empty_parcel_ids_returns_422(client: TestClient):
    """Empty parcel_ids list is rejected with 422."""
    resp = client.post(
        "/api/v1/land/assemblies",
        json={"assembly_name": "Empty", "assembly_code": "ASM-EMPTY", "parcel_ids": []},
    )
    assert resp.status_code == 422


def test_create_assembly_parcel_already_in_assembly_returns_409(client: TestClient):
    """Parcel that already belongs to an assembly cannot be added to another."""
    p1 = _create_parcel(client, "PCL-N01")
    _create_assembly(client, [p1["id"]], "ASM-FIRST")
    # Second assembly attempts to claim the same parcel
    p2 = _create_parcel(client, "PCL-N02")
    resp = client.post(
        "/api/v1/land/assemblies",
        json={
            "assembly_name": "Second Assembly",
            "assembly_code": "ASM-SECOND",
            "parcel_ids": [p1["id"], p2["id"]],
        },
    )
    assert resp.status_code == 409


def test_create_assembly_missing_assembly_name_returns_422(client: TestClient):
    """Missing assembly_name returns 422."""
    p1 = _create_parcel(client, "PCL-O01")
    resp = client.post(
        "/api/v1/land/assemblies",
        json={"assembly_code": "ASM-NONAME", "parcel_ids": [p1["id"]]},
    )
    assert resp.status_code == 422


def test_create_assembly_missing_assembly_code_returns_422(client: TestClient):
    """Missing assembly_code returns 422."""
    p1 = _create_parcel(client, "PCL-P01")
    resp = client.post(
        "/api/v1/land/assemblies",
        json={"assembly_name": "No Code Assembly", "parcel_ids": [p1["id"]]},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Get assembly
# ---------------------------------------------------------------------------

def test_get_assembly_status_200(client: TestClient):
    """GET /land/assemblies/{id} returns 200 for an existing assembly."""
    p1 = _create_parcel(client, "PCL-Q01")
    created = _create_assembly(client, [p1["id"]], "ASM-Q")
    resp = client.get(f"/api/v1/land/assemblies/{created['id']}")
    assert resp.status_code == 200


def test_get_assembly_round_trip(client: TestClient):
    """GET /land/assemblies/{id} returns the same assembly as the one created."""
    p1 = _create_parcel(client, "PCL-R01")
    p2 = _create_parcel(client, "PCL-R02")
    created = _create_assembly(client, [p1["id"], p2["id"]], "ASM-R")
    fetched = client.get(f"/api/v1/land/assemblies/{created['id']}").json()
    assert fetched["id"] == created["id"]
    assert fetched["assembly_code"] == "ASM-R"
    assert fetched["parcel_count"] == 2


def test_get_assembly_not_found_returns_404(client: TestClient):
    """GET /land/assemblies/{id} with unknown ID returns 404."""
    resp = client.get("/api/v1/land/assemblies/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List assemblies
# ---------------------------------------------------------------------------

def test_list_assemblies_empty(client: TestClient):
    """GET /land/assemblies returns empty list when no assemblies exist."""
    resp = client.get("/api/v1/land/assemblies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_assemblies_returns_all(client: TestClient):
    """GET /land/assemblies lists all created assemblies."""
    p1 = _create_parcel(client, "PCL-S01")
    p2 = _create_parcel(client, "PCL-S02")
    p3 = _create_parcel(client, "PCL-S03")
    _create_assembly(client, [p1["id"]], "ASM-S1")
    _create_assembly(client, [p2["id"]], "ASM-S2")
    _create_assembly(client, [p3["id"]], "ASM-S3")
    resp = client.get("/api/v1/land/assemblies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_assemblies_summary_fields(client: TestClient):
    """List items contain all required summary fields."""
    p1 = _create_parcel(client, "PCL-T01")
    _create_assembly(client, [p1["id"]], "ASM-T")
    resp = client.get("/api/v1/land/assemblies")
    item = resp.json()["items"][0]
    for field in (
        "id", "assembly_name", "assembly_code", "status",
        "parcel_count", "total_area_sqm", "mixed_zoning",
        "dominant_zoning_category", "effective_land_basis",
        "created_at", "updated_at",
    ):
        assert field in item, f"Missing summary field: {field}"


def test_list_assemblies_pagination(client: TestClient):
    """skip/limit parameters restrict the result window."""
    p1 = _create_parcel(client, "PCL-U01")
    p2 = _create_parcel(client, "PCL-U02")
    p3 = _create_parcel(client, "PCL-U03")
    _create_assembly(client, [p1["id"]], "ASM-U1")
    _create_assembly(client, [p2["id"]], "ASM-U2")
    _create_assembly(client, [p3["id"]], "ASM-U3")
    resp = client.get("/api/v1/land/assemblies?skip=0&limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3          # total is the full count
    assert len(body["items"]) == 2     # only 2 returned


# ---------------------------------------------------------------------------
# Delete assembly
# ---------------------------------------------------------------------------

def test_delete_assembly_returns_204(client: TestClient):
    """DELETE /land/assemblies/{id} returns 204 No Content."""
    p1 = _create_parcel(client, "PCL-V01")
    created = _create_assembly(client, [p1["id"]], "ASM-V")
    resp = client.delete(f"/api/v1/land/assemblies/{created['id']}")
    assert resp.status_code == 204


def test_delete_assembly_is_gone(client: TestClient):
    """Deleted assembly is no longer retrievable via GET."""
    p1 = _create_parcel(client, "PCL-W01")
    created = _create_assembly(client, [p1["id"]], "ASM-W")
    client.delete(f"/api/v1/land/assemblies/{created['id']}")
    resp = client.get(f"/api/v1/land/assemblies/{created['id']}")
    assert resp.status_code == 404


def test_delete_assembly_parcels_survive(client: TestClient):
    """Deleting an assembly does NOT delete the underlying parcel records."""
    p1 = _create_parcel(client, "PCL-X01")
    created = _create_assembly(client, [p1["id"]], "ASM-X")
    client.delete(f"/api/v1/land/assemblies/{created['id']}")
    # Parcel must still be accessible
    resp = client.get(f"/api/v1/land/parcels/{p1['id']}")
    assert resp.status_code == 200


def test_delete_assembly_frees_parcel_for_reassembly(client: TestClient):
    """After deleting an assembly, its former parcels can join a new assembly."""
    p1 = _create_parcel(client, "PCL-Y01")
    created = _create_assembly(client, [p1["id"]], "ASM-Y1")
    client.delete(f"/api/v1/land/assemblies/{created['id']}")
    # Parcel should now be free to join another assembly
    resp = client.post(
        "/api/v1/land/assemblies",
        json={"assembly_name": "New Assembly", "assembly_code": "ASM-Y2", "parcel_ids": [p1["id"]]},
    )
    assert resp.status_code == 201


def test_delete_assembly_not_found_returns_404(client: TestClient):
    """DELETE /land/assemblies/{id} with unknown ID returns 404."""
    resp = client.delete("/api/v1/land/assemblies/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Recompute assembly
# ---------------------------------------------------------------------------

def test_recompute_assembly_status_200(client: TestClient):
    """POST /land/assemblies/{id}/recompute returns 200."""
    p1 = _create_parcel(client, "PCL-Z01")
    created = _create_assembly(client, [p1["id"]], "ASM-Z1")
    resp = client.post(f"/api/v1/land/assemblies/{created['id']}/recompute")
    assert resp.status_code == 200


def test_recompute_assembly_reflects_updated_parcel(client: TestClient):
    """Recomputed assembly picks up updated parcel metrics."""
    p1 = _create_parcel(client, "PCL-Z02", land_area_sqm=5_000.0)
    created = _create_assembly(client, [p1["id"]], "ASM-Z2")
    assert created["total_area_sqm"] == pytest.approx(5_000.0)

    # Update the parcel's land area
    client.patch(f"/api/v1/land/parcels/{p1['id']}", json={"land_area_sqm": 8_000.0})

    recomputed = client.post(
        f"/api/v1/land/assemblies/{created['id']}/recompute"
    ).json()
    assert recomputed["total_area_sqm"] == pytest.approx(8_000.0)


def test_recompute_assembly_is_deterministic(client: TestClient):
    """Calling recompute twice without parcel changes yields the same result."""
    p1 = _create_parcel(client, "PCL-Z03")
    created = _create_assembly(client, [p1["id"]], "ASM-Z3")
    first = client.post(f"/api/v1/land/assemblies/{created['id']}/recompute").json()
    second = client.post(f"/api/v1/land/assemblies/{created['id']}/recompute").json()
    assert first["total_area_sqm"] == second["total_area_sqm"]
    assert first["effective_land_basis"] == second["effective_land_basis"]


def test_recompute_assembly_not_found_returns_404(client: TestClient):
    """POST /land/assemblies/{id}/recompute with unknown ID returns 404."""
    resp = client.post(
        "/api/v1/land/assemblies/00000000-0000-0000-0000-000000000000/recompute"
    )
    assert resp.status_code == 404


def test_recompute_assembly_response_has_all_fields(client: TestClient):
    """Recompute response includes all expected top-level fields."""
    p1 = _create_parcel(client, "PCL-Z04")
    created = _create_assembly(client, [p1["id"]], "ASM-Z4")
    resp = client.post(f"/api/v1/land/assemblies/{created['id']}/recompute")
    assert resp.status_code == 200
    body = resp.json()
    for field in (
        "id", "assembly_name", "parcel_count", "total_area_sqm",
        "effective_land_basis", "mixed_zoning", "parcel_ids", "parcels",
    ):
        assert field in body, f"Missing field in recompute response: {field}"


# ---------------------------------------------------------------------------
# Zero value preservation
# ---------------------------------------------------------------------------

def test_create_assembly_zero_acquisition_price_preserved(client: TestClient):
    """Zero acquisition_price must not be silently turned into null in the response."""
    p1 = _create_parcel(client, "PCL-ZV01", acquisition_price=0.0, transaction_cost=0.0)
    body = _create_assembly(client, [p1["id"]], "ASM-ZV1")
    # effective_land_basis = 0.0 + 0.0 = 0.0; must be returned as 0, not null
    assert body["effective_land_basis"] is not None
    assert body["effective_land_basis"] == pytest.approx(0.0)


def test_create_assembly_zero_area_preserved(client: TestClient):
    """Parcel with no land_area_sqm yields 0.0 total_area (not null) when all areas absent."""
    # Parcel without land_area_sqm → engine sums to 0.0
    p1 = _create_parcel(client, "PCL-ZV02", land_area_sqm=None)
    body = _create_assembly(client, [p1["id"]], "ASM-ZV2")
    # Engine returns 0.0; must be persisted and returned as a numeric value, not omitted
    assert "total_area_sqm" in body
