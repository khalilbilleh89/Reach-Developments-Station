"""
Tests for concept option promotion structural scaffolding.

Validates that promotion creates the full Project → Phase → Building →
Floor → Unit hierarchy and that the response accurately reports the
counts of generated records.

PR-CONCEPT-056
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str) -> str:
    resp = client.post("/api/v1/projects", json={"name": f"Structure Project {code}", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_promotable_option(
    client: TestClient,
    project_id: str,
    *,
    building_count: int = 2,
    floor_count: int = 4,
    mix_lines: list[dict] | None = None,
    name: str = "Structural Option",
) -> dict:
    """Create a concept option fully prepared for promotion with custom program data."""
    resp = client.post(
        "/api/v1/concept-options",
        json={
            "name": name,
            "project_id": project_id,
            "status": "active",
            "gross_floor_area": 10000.0,
            "building_count": building_count,
            "floor_count": floor_count,
        },
    )
    assert resp.status_code == 201
    option = resp.json()

    lines = mix_lines or [
        {"unit_type": "2BR", "units_count": 40, "avg_internal_area": 90.0, "avg_sellable_area": 95.0},
        {"unit_type": "1BR", "units_count": 30, "avg_internal_area": 65.0, "avg_sellable_area": 70.0},
        {"unit_type": "studio", "units_count": 20, "avg_internal_area": 45.0, "avg_sellable_area": 48.0},
    ]
    for line in lines:
        r = client.post(f"/api/v1/concept-options/{option['id']}/unit-mix", json=line)
        assert r.status_code == 201

    return option


# ---------------------------------------------------------------------------
# Promotion creates phase
# ---------------------------------------------------------------------------


def test_promotion_creates_phase(client: TestClient):
    """Promotion must create exactly one phase under the target project."""
    project_id = _create_project(client, "PS-PHASE-001")
    option = _create_promotable_option(client, project_id)

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201
    data = resp.json()

    phase_resp = client.get(f"/api/v1/phases/{data['promoted_phase_id']}")
    assert phase_resp.status_code == 200
    phase = phase_resp.json()
    assert phase["project_id"] == project_id
    assert phase["status"] == "planned"


# ---------------------------------------------------------------------------
# Promotion creates buildings
# ---------------------------------------------------------------------------


def test_promotion_creates_correct_building_count(client: TestClient):
    """Promotion must create exactly building_count buildings under the phase."""
    project_id = _create_project(client, "PS-BLDG-001")
    option = _create_promotable_option(client, project_id, building_count=3, floor_count=2)

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["buildings_created"] == 3

    phase_id = data["promoted_phase_id"]
    buildings_resp = client.get(f"/api/v1/buildings?phase_id={phase_id}")
    assert buildings_resp.status_code == 200
    buildings = buildings_resp.json()
    assert buildings["total"] == 3


def test_promotion_building_names_use_letter_sequence(client: TestClient):
    """Buildings must be named 'Building A', 'Building B', etc."""
    project_id = _create_project(client, "PS-BLDG-002")
    option = _create_promotable_option(client, project_id, building_count=3, floor_count=1)

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201
    phase_id = resp.json()["promoted_phase_id"]

    buildings_resp = client.get(f"/api/v1/buildings?phase_id={phase_id}")
    names = {b["name"] for b in buildings_resp.json()["items"]}
    assert names == {"Building A", "Building B", "Building C"}


def test_promotion_single_building(client: TestClient):
    """Single-building promotion creates one building named 'Building A'."""
    project_id = _create_project(client, "PS-BLDG-003")
    option = _create_promotable_option(client, project_id, building_count=1, floor_count=3)

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["buildings_created"] == 1

    phase_id = data["promoted_phase_id"]
    buildings_resp = client.get(f"/api/v1/buildings?phase_id={phase_id}")
    items = buildings_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Building A"


# ---------------------------------------------------------------------------
# Promotion creates floors
# ---------------------------------------------------------------------------


def test_promotion_creates_correct_floor_count(client: TestClient):
    """floors_created must equal building_count × floor_count."""
    project_id = _create_project(client, "PS-FLOOR-001")
    option = _create_promotable_option(client, project_id, building_count=2, floor_count=5)

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["floors_created"] == 10  # 2 buildings × 5 floors


def test_promotion_floors_per_building(client: TestClient):
    """Each building must contain exactly floor_count floors."""
    project_id = _create_project(client, "PS-FLOOR-002")
    option = _create_promotable_option(client, project_id, building_count=2, floor_count=3)

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201
    phase_id = resp.json()["promoted_phase_id"]

    buildings_resp = client.get(f"/api/v1/buildings?phase_id={phase_id}")
    for building in buildings_resp.json()["items"]:
        floors_resp = client.get(f"/api/v1/buildings/{building['id']}/floors")
        assert floors_resp.status_code == 200
        assert floors_resp.json()["total"] == 3


def test_promotion_floor_sequence_numbers(client: TestClient):
    """Floors must have sequence numbers 1, 2, … floor_count within each building."""
    project_id = _create_project(client, "PS-FLOOR-003")
    option = _create_promotable_option(client, project_id, building_count=1, floor_count=4)

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201
    phase_id = resp.json()["promoted_phase_id"]

    buildings_resp = client.get(f"/api/v1/buildings?phase_id={phase_id}")
    building_id = buildings_resp.json()["items"][0]["id"]

    floors_resp = client.get(f"/api/v1/buildings/{building_id}/floors")
    sequences = sorted(f["sequence_number"] for f in floors_resp.json()["items"])
    assert sequences == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Promotion creates units
# ---------------------------------------------------------------------------


def test_promotion_creates_correct_unit_count(client: TestClient):
    """units_created must equal the sum of all mix_line.units_count values."""
    project_id = _create_project(client, "PS-UNIT-001")
    option = _create_promotable_option(
        client,
        project_id,
        building_count=2,
        floor_count=3,
        mix_lines=[
            {"unit_type": "2BR", "units_count": 40, "avg_internal_area": 90.0},
            {"unit_type": "1BR", "units_count": 30, "avg_internal_area": 65.0},
            {"unit_type": "studio", "units_count": 20, "avg_internal_area": 45.0},
        ],
    )

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["units_created"] == 90  # 40 + 30 + 20


def test_promotion_single_mix_line_units(client: TestClient):
    """Single mix line — all units created, all with correct unit_type."""
    project_id = _create_project(client, "PS-UNIT-002")
    option = _create_promotable_option(
        client,
        project_id,
        building_count=1,
        floor_count=2,
        mix_lines=[{"unit_type": "penthouse", "units_count": 4, "avg_internal_area": 200.0}],
    )

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["units_created"] == 4

    project_units_resp = client.get(f"/api/v1/units?project_id={project_id}")
    assert project_units_resp.status_code == 200
    units = project_units_resp.json()["items"]
    assert len(units) == 4
    assert all(u["unit_type"] == "penthouse" for u in units)


def test_promotion_units_distributed_across_floors(client: TestClient):
    """Units must be spread across all floors — no floor should hoard all units."""
    project_id = _create_project(client, "PS-UNIT-003")
    option = _create_promotable_option(
        client,
        project_id,
        building_count=1,
        floor_count=4,
        mix_lines=[{"unit_type": "1BR", "units_count": 8, "avg_internal_area": 65.0}],
    )

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201
    phase_id = resp.json()["promoted_phase_id"]

    buildings_resp = client.get(f"/api/v1/buildings?phase_id={phase_id}")
    building_id = buildings_resp.json()["items"][0]["id"]
    floors_resp = client.get(f"/api/v1/buildings/{building_id}/floors")

    for floor in floors_resp.json()["items"]:
        units_resp = client.get(f"/api/v1/units?floor_id={floor['id']}")
        assert units_resp.status_code == 200
        # Each floor must have at least 1 unit (8 units / 4 floors = 2 per floor)
        assert units_resp.json()["total"] >= 1


def test_promotion_units_have_available_status(client: TestClient):
    """All generated units must have inventory_status 'available'."""
    project_id = _create_project(client, "PS-UNIT-004")
    option = _create_promotable_option(
        client,
        project_id,
        building_count=1,
        floor_count=1,
        mix_lines=[{"unit_type": "studio", "units_count": 5, "avg_internal_area": 45.0}],
    )

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201

    units_resp = client.get(f"/api/v1/units?project_id={project_id}")
    units = units_resp.json()["items"]
    assert all(u["status"] == "available" for u in units)


# ---------------------------------------------------------------------------
# Promotion safeguards (beyond the existing guards already tested in test_api.py)
# ---------------------------------------------------------------------------


def test_promotion_fails_when_unit_mix_missing(client: TestClient):
    """Promotion must fail when no unit mix lines are defined."""
    project_id = _create_project(client, "PS-GUARD-001")
    resp = client.post(
        "/api/v1/concept-options",
        json={
            "name": "No Mix",
            "project_id": project_id,
            "status": "active",
            "building_count": 2,
            "floor_count": 5,
        },
    )
    assert resp.status_code == 201
    option_id = resp.json()["id"]

    promo_resp = client.post(f"/api/v1/concept-options/{option_id}/promote", json={})
    assert promo_resp.status_code == 422
    body = promo_resp.json()
    assert body.get("code") == "VALIDATION_ERROR"
    assert "unit mix lines" in body.get("details", {}).get("missing_fields", [])


def test_promotion_fails_when_building_count_zero(client: TestClient):
    """Promotion must fail when building_count is not set (zero/None)."""
    project_id = _create_project(client, "PS-GUARD-002")
    resp = client.post(
        "/api/v1/concept-options",
        json={
            "name": "No Buildings",
            "project_id": project_id,
            "status": "active",
            "floor_count": 5,
        },
    )
    assert resp.status_code == 201
    option_id = resp.json()["id"]
    client.post(
        f"/api/v1/concept-options/{option_id}/unit-mix",
        json={"unit_type": "1BR", "units_count": 10},
    )

    promo_resp = client.post(f"/api/v1/concept-options/{option_id}/promote", json={})
    assert promo_resp.status_code == 422
    body = promo_resp.json()
    assert body.get("code") == "VALIDATION_ERROR"
    assert "building_count" in body.get("details", {}).get("missing_fields", [])


def test_promotion_fails_when_floor_count_zero(client: TestClient):
    """Promotion must fail when floor_count is not set (zero/None)."""
    project_id = _create_project(client, "PS-GUARD-003")
    resp = client.post(
        "/api/v1/concept-options",
        json={
            "name": "No Floors",
            "project_id": project_id,
            "status": "active",
            "building_count": 2,
        },
    )
    assert resp.status_code == 201
    option_id = resp.json()["id"]
    client.post(
        f"/api/v1/concept-options/{option_id}/unit-mix",
        json={"unit_type": "1BR", "units_count": 10},
    )

    promo_resp = client.post(f"/api/v1/concept-options/{option_id}/promote", json={})
    assert promo_resp.status_code == 422
    body = promo_resp.json()
    assert body.get("code") == "VALIDATION_ERROR"
    assert "floor_count" in body.get("details", {}).get("missing_fields", [])


def test_promotion_scaffolding_counts_match_program(client: TestClient):
    """Response counts must match the concept program dimensions exactly."""
    project_id = _create_project(client, "PS-COUNT-001")
    option = _create_promotable_option(
        client,
        project_id,
        building_count=4,
        floor_count=6,
        mix_lines=[
            {"unit_type": "2BR", "units_count": 48, "avg_internal_area": 90.0},
            {"unit_type": "1BR", "units_count": 36, "avg_internal_area": 65.0},
        ],
    )

    resp = client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})
    assert resp.status_code == 201
    data = resp.json()

    assert data["buildings_created"] == 4
    assert data["floors_created"] == 24   # 4 × 6
    assert data["units_created"] == 84    # 48 + 36
