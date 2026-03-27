"""
Tests for the Project Structure Viewer API (PR-V6-08).

Validates:
  - 404 on unknown project
  - empty structure for a project with no phases
  - correct response contract shape
  - canonical nesting and ordering
  - summary counts at every level
  - sparse hierarchy handling (buildings with no floors, etc.)
  - read-only — no mutation routes exist
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str, name: str = "Test Project") -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_phase(
    client: TestClient,
    project_id: str,
    name: str,
    sequence: int,
    phase_type: str | None = None,
) -> str:
    payload: dict = {"project_id": project_id, "name": name, "sequence": sequence}
    if phase_type:
        payload["phase_type"] = phase_type
    resp = client.post("/api/v1/phases", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_building(
    client: TestClient, phase_id: str, name: str, code: str
) -> str:
    resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": name, "code": code},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_floor(
    client: TestClient,
    building_id: str,
    name: str,
    code: str,
    sequence_number: int,
    level_number: int | None = None,
) -> str:
    payload: dict = {
        "name": name,
        "code": code,
        "sequence_number": sequence_number,
    }
    if level_number is not None:
        payload["level_number"] = level_number
    resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json=payload,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_unit(client: TestClient, floor_id: str, unit_number: str) -> str:
    resp = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": unit_number,
            "unit_type": "studio",
            "internal_area": 50.0,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# 404 / missing project
# ---------------------------------------------------------------------------


def test_structure_unknown_project_returns_404(client: TestClient) -> None:
    """GET /structure on a non-existent project must return 404."""
    resp = client.get("/api/v1/projects/nonexistent-id/structure")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Empty project
# ---------------------------------------------------------------------------


def test_structure_empty_project(client: TestClient) -> None:
    """GET /structure on a project with no phases returns empty collections and zero counts."""
    project_id = _create_project(client, "PS-EMPTY")
    resp = client.get(f"/api/v1/projects/{project_id}/structure")
    assert resp.status_code == 200

    data = resp.json()
    assert data["project_id"] == project_id
    assert data["phases"] == []
    assert data["phase_count"] == 0
    assert data["building_count"] == 0
    assert data["floor_count"] == 0
    assert data["unit_count"] == 0


# ---------------------------------------------------------------------------
# Contract shape
# ---------------------------------------------------------------------------


def test_structure_response_contract_shape(client: TestClient) -> None:
    """Structure response includes all required top-level contract fields."""
    project_id = _create_project(client, "PS-CONTRACT", name="Shape Test")
    resp = client.get(f"/api/v1/projects/{project_id}/structure")
    assert resp.status_code == 200

    data = resp.json()
    required_fields = {
        "project_id",
        "project_name",
        "project_code",
        "project_status",
        "phase_count",
        "building_count",
        "floor_count",
        "unit_count",
        "phases",
    }
    assert required_fields <= set(data.keys()), (
        f"Missing fields: {required_fields - set(data.keys())}"
    )
    assert data["project_name"] == "Shape Test"
    assert data["project_code"] == "PS-CONTRACT"
    assert data["project_status"] == "pipeline"


# ---------------------------------------------------------------------------
# Full hierarchy
# ---------------------------------------------------------------------------


def test_structure_full_hierarchy(client: TestClient) -> None:
    """Full populated hierarchy is returned with correct nested structure."""
    project_id = _create_project(client, "PS-FULL")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1, phase_type="construction")
    building_id = _create_building(client, phase_id, "Block A", "BLK-A")
    floor_id = _create_floor(
        client, building_id, "Ground Floor", "FL-00", sequence_number=1, level_number=0
    )
    unit_id_1 = _create_unit(client, floor_id, "101")
    unit_id_2 = _create_unit(client, floor_id, "102")

    resp = client.get(f"/api/v1/projects/{project_id}/structure")
    assert resp.status_code == 200
    data = resp.json()

    # Top-level counts
    assert data["phase_count"] == 1
    assert data["building_count"] == 1
    assert data["floor_count"] == 1
    assert data["unit_count"] == 2

    # Phase node
    assert len(data["phases"]) == 1
    phase = data["phases"][0]
    assert phase["id"] == phase_id
    assert phase["name"] == "Phase 1"
    assert phase["sequence"] == 1
    assert phase["phase_type"] == "construction"
    assert phase["building_count"] == 1
    assert phase["floor_count"] == 1
    assert phase["unit_count"] == 2

    # Building node
    assert len(phase["buildings"]) == 1
    building = phase["buildings"][0]
    assert building["id"] == building_id
    assert building["name"] == "Block A"
    assert building["code"] == "BLK-A"
    assert building["floor_count"] == 1
    assert building["unit_count"] == 2

    # Floor node
    assert len(building["floors"]) == 1
    floor = building["floors"][0]
    assert floor["id"] == floor_id
    assert floor["name"] == "Ground Floor"
    assert floor["code"] == "FL-00"
    assert floor["sequence_number"] == 1
    assert floor["level_number"] == 0
    assert floor["unit_count"] == 2

    # Unit nodes
    assert len(floor["units"]) == 2
    unit_ids = {u["id"] for u in floor["units"]}
    assert unit_id_1 in unit_ids
    assert unit_id_2 in unit_ids
    for unit in floor["units"]:
        assert "unit_number" in unit
        assert "unit_type" in unit
        assert "status" in unit


# ---------------------------------------------------------------------------
# Summary counts
# ---------------------------------------------------------------------------


def test_structure_counts_aggregate_correctly(client: TestClient) -> None:
    """Summary counts at every level are consistent with actual child records."""
    project_id = _create_project(client, "PS-COUNTS")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Tower A", "TWR-A")
    floor1_id = _create_floor(client, building_id, "Floor 1", "FL-01", sequence_number=1)
    floor2_id = _create_floor(client, building_id, "Floor 2", "FL-02", sequence_number=2)
    _create_unit(client, floor1_id, "101")
    _create_unit(client, floor1_id, "102")
    _create_unit(client, floor1_id, "103")
    _create_unit(client, floor2_id, "201")

    resp = client.get(f"/api/v1/projects/{project_id}/structure")
    assert resp.status_code == 200
    data = resp.json()

    assert data["unit_count"] == 4
    assert data["floor_count"] == 2

    phase = data["phases"][0]
    assert phase["unit_count"] == 4
    assert phase["floor_count"] == 2

    building = phase["buildings"][0]
    assert building["unit_count"] == 4
    assert building["floor_count"] == 2

    floors = {f["id"]: f for f in building["floors"]}
    assert floors[floor1_id]["unit_count"] == 3
    assert floors[floor2_id]["unit_count"] == 1


# ---------------------------------------------------------------------------
# Sparse hierarchy — nodes with no children
# ---------------------------------------------------------------------------


def test_structure_phase_with_no_buildings(client: TestClient) -> None:
    """A phase with no buildings still appears with empty buildings list."""
    project_id = _create_project(client, "PS-SPARSE-PH")
    phase_id = _create_phase(client, project_id, "Empty Phase", sequence=1)

    resp = client.get(f"/api/v1/projects/{project_id}/structure")
    assert resp.status_code == 200
    data = resp.json()

    assert data["phase_count"] == 1
    phase = data["phases"][0]
    assert phase["id"] == phase_id
    assert phase["buildings"] == []
    assert phase["building_count"] == 0
    assert phase["floor_count"] == 0
    assert phase["unit_count"] == 0


def test_structure_building_with_no_floors(client: TestClient) -> None:
    """A building with no floors still appears with empty floors list."""
    project_id = _create_project(client, "PS-SPARSE-BLD")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Empty Block", "BLK-EMPTY")

    resp = client.get(f"/api/v1/projects/{project_id}/structure")
    assert resp.status_code == 200
    data = resp.json()

    building = data["phases"][0]["buildings"][0]
    assert building["id"] == building_id
    assert building["floors"] == []
    assert building["floor_count"] == 0
    assert building["unit_count"] == 0


def test_structure_floor_with_no_units(client: TestClient) -> None:
    """A floor with no units still appears with empty units list and zero unit_count."""
    project_id = _create_project(client, "PS-SPARSE-FLR")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Block A", "BLK-A")
    floor_id = _create_floor(client, building_id, "Empty Floor", "FL-00", sequence_number=1)

    resp = client.get(f"/api/v1/projects/{project_id}/structure")
    assert resp.status_code == 200

    data = resp.json()
    floor = data["phases"][0]["buildings"][0]["floors"][0]
    assert floor["id"] == floor_id
    assert floor["units"] == []
    assert floor["unit_count"] == 0


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


def test_structure_phases_ordered_by_sequence(client: TestClient) -> None:
    """Phases in the structure response are ordered by ascending sequence."""
    project_id = _create_project(client, "PS-ORD-PH")
    _create_phase(client, project_id, "Phase C", sequence=3)
    _create_phase(client, project_id, "Phase A", sequence=1)
    _create_phase(client, project_id, "Phase B", sequence=2)

    resp = client.get(f"/api/v1/projects/{project_id}/structure")
    assert resp.status_code == 200
    sequences = [p["sequence"] for p in resp.json()["phases"]]
    assert sequences == sorted(sequences)


def test_structure_buildings_ordered_by_name(client: TestClient) -> None:
    """Buildings within a phase are ordered alphabetically by name."""
    project_id = _create_project(client, "PS-ORD-BLD")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    _create_building(client, phase_id, "Zeta Tower", "BLK-Z")
    _create_building(client, phase_id, "Alpha Tower", "BLK-A")

    resp = client.get(f"/api/v1/projects/{project_id}/structure")
    assert resp.status_code == 200
    names = [b["name"] for b in resp.json()["phases"][0]["buildings"]]
    assert names == sorted(names)


def test_structure_floors_ordered_by_sequence_number(client: TestClient) -> None:
    """Floors within a building are ordered by ascending sequence_number."""
    project_id = _create_project(client, "PS-ORD-FLR")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Tower", "TWR")
    _create_floor(client, building_id, "Floor 5", "FL-05", sequence_number=5)
    _create_floor(client, building_id, "Floor 1", "FL-01", sequence_number=1)
    _create_floor(client, building_id, "Floor 3", "FL-03", sequence_number=3)

    resp = client.get(f"/api/v1/projects/{project_id}/structure")
    assert resp.status_code == 200
    seq_numbers = [
        f["sequence_number"]
        for f in resp.json()["phases"][0]["buildings"][0]["floors"]
    ]
    assert seq_numbers == sorted(seq_numbers)


# ---------------------------------------------------------------------------
# Multi-phase project
# ---------------------------------------------------------------------------


def test_structure_multi_phase_project(client: TestClient) -> None:
    """Multiple phases are each included with their own buildings and counts."""
    project_id = _create_project(client, "PS-MULTI-PH")
    phase1_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    phase2_id = _create_phase(client, project_id, "Phase 2", sequence=2)
    b1_id = _create_building(client, phase1_id, "Block A", "BLK-A")
    b2_id = _create_building(client, phase2_id, "Block B", "BLK-B")
    fl1_id = _create_floor(client, b1_id, "Floor 1", "FL-01", sequence_number=1)
    fl2_id = _create_floor(client, b2_id, "Floor 1", "FL-01", sequence_number=1)
    _create_unit(client, fl1_id, "101")
    _create_unit(client, fl2_id, "201")
    _create_unit(client, fl2_id, "202")

    resp = client.get(f"/api/v1/projects/{project_id}/structure")
    assert resp.status_code == 200
    data = resp.json()

    assert data["phase_count"] == 2
    assert data["building_count"] == 2
    assert data["floor_count"] == 2
    assert data["unit_count"] == 3

    phases = {p["id"]: p for p in data["phases"]}
    assert phases[phase1_id]["unit_count"] == 1
    assert phases[phase2_id]["unit_count"] == 2


# ---------------------------------------------------------------------------
# Cross-project isolation
# ---------------------------------------------------------------------------


def test_structure_cross_project_isolation(client: TestClient) -> None:
    """Structure for project B must not include phases/buildings from project A."""
    project_a_id = _create_project(client, "PS-ISO-A")
    project_b_id = _create_project(client, "PS-ISO-B")
    phase_a_id = _create_phase(client, project_a_id, "Phase A", sequence=1)
    _create_building(client, phase_a_id, "Block A", "BLK-A")

    resp = client.get(f"/api/v1/projects/{project_b_id}/structure")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_b_id
    assert data["phases"] == []


# ---------------------------------------------------------------------------
# No mutating routes
# ---------------------------------------------------------------------------


def test_structure_endpoint_is_read_only(client: TestClient) -> None:
    """POST/PATCH/DELETE on the structure endpoint must return 405 Method Not Allowed."""
    project_id = _create_project(client, "PS-READONLY")
    base_url = f"/api/v1/projects/{project_id}/structure"

    assert client.post(base_url, json={}).status_code == 405
    assert client.patch(base_url, json={}).status_code == 405
    assert client.delete(base_url).status_code == 405
