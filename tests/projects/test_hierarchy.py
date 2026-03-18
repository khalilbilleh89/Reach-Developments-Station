"""
Tests for project hierarchy domain stabilization (PR-A1).

Validates:
- hierarchy traversal endpoint correctness
- phase ordering preserved (by sequence)
- building ordering deterministic (by name)
- floor ordering preserved (by sequence_number)
- cross-project building assignment rejected
- project deletion cascade (orphan cleanup after phase deletion)
- project attribute definition scoping across projects
"""

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str, name: str = "Test Project") -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_phase(client: TestClient, project_id: str, name: str, sequence: int) -> str:
    resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": name, "sequence": sequence},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_building(client: TestClient, phase_id: str, name: str, code: str) -> str:
    resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": name, "code": code},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_floor(
    client: TestClient, building_id: str, name: str, code: str, sequence_number: int
) -> str:
    resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": name, "code": code, "sequence_number": sequence_number},
    )
    assert resp.status_code == 201
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
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Hierarchy traversal
# ---------------------------------------------------------------------------


def test_hierarchy_empty_project(client: TestClient):
    """GET /hierarchy on a project with no phases returns empty phases list."""
    project_id = _create_project(client, "PRJ-HIER-EMPTY")
    resp = client.get(f"/api/v1/projects/{project_id}/hierarchy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["phases"] == []


def test_hierarchy_project_not_found(client: TestClient):
    """GET /hierarchy on a non-existent project returns 404."""
    resp = client.get("/api/v1/projects/nonexistent-id/hierarchy")
    assert resp.status_code == 404


def test_hierarchy_full_structure(client: TestClient):
    """GET /hierarchy returns correct nested structure for a full project."""
    project_id = _create_project(client, "PRJ-HIER-FULL")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Block A", "BLK-A")
    floor_id = _create_floor(client, building_id, "Ground Floor", "FL-00", sequence_number=1)
    _create_unit(client, floor_id, "101")
    _create_unit(client, floor_id, "102")

    resp = client.get(f"/api/v1/projects/{project_id}/hierarchy")
    assert resp.status_code == 200
    data = resp.json()

    assert data["project_id"] == project_id
    assert len(data["phases"]) == 1

    phase = data["phases"][0]
    assert phase["phase_id"] == phase_id
    assert phase["name"] == "Phase 1"
    assert phase["sequence"] == 1
    assert len(phase["buildings"]) == 1

    building = phase["buildings"][0]
    assert building["building_id"] == building_id
    assert building["name"] == "Block A"
    assert len(building["floors"]) == 1

    floor = building["floors"][0]
    assert floor["floor_id"] == floor_id
    assert floor["sequence_number"] == 1
    assert floor["unit_count"] == 2


def test_hierarchy_unit_counts_per_floor(client: TestClient):
    """Unit counts in hierarchy are accurate per floor."""
    project_id = _create_project(client, "PRJ-HIER-CNT")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Tower", "TWR")
    floor1_id = _create_floor(client, building_id, "Floor 1", "FL-01", sequence_number=1)
    floor2_id = _create_floor(client, building_id, "Floor 2", "FL-02", sequence_number=2)
    _create_unit(client, floor1_id, "101")
    _create_unit(client, floor1_id, "102")
    _create_unit(client, floor1_id, "103")
    _create_unit(client, floor2_id, "201")

    resp = client.get(f"/api/v1/projects/{project_id}/hierarchy")
    assert resp.status_code == 200
    floors = resp.json()["phases"][0]["buildings"][0]["floors"]
    counts = {f["floor_id"]: f["unit_count"] for f in floors}
    assert counts[floor1_id] == 3
    assert counts[floor2_id] == 1


def test_hierarchy_empty_building_appears(client: TestClient):
    """A building with no floors still appears in the hierarchy."""
    project_id = _create_project(client, "PRJ-HIER-NOBLD")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Empty Block", "BLK-EMPTY")

    resp = client.get(f"/api/v1/projects/{project_id}/hierarchy")
    assert resp.status_code == 200
    buildings = resp.json()["phases"][0]["buildings"]
    assert len(buildings) == 1
    assert buildings[0]["building_id"] == building_id
    assert buildings[0]["floors"] == []


# ---------------------------------------------------------------------------
# Phase ordering
# ---------------------------------------------------------------------------


def test_phase_list_ordered_by_sequence(client: TestClient):
    """Phases are returned in ascending sequence order regardless of creation order."""
    project_id = _create_project(client, "PRJ-PHASE-ORD")
    _create_phase(client, project_id, "Phase 3", sequence=3)
    _create_phase(client, project_id, "Phase 1", sequence=1)
    _create_phase(client, project_id, "Phase 2", sequence=2)

    resp = client.get(f"/api/v1/projects/{project_id}/phases")
    assert resp.status_code == 200
    items = resp.json()["items"]
    sequences = [p["sequence"] for p in items]
    assert sequences == sorted(sequences)


def test_hierarchy_phases_ordered_by_sequence(client: TestClient):
    """Hierarchy endpoint returns phases in ascending sequence order."""
    project_id = _create_project(client, "PRJ-HIER-ORD")
    _create_phase(client, project_id, "Phase C", sequence=3)
    _create_phase(client, project_id, "Phase A", sequence=1)
    _create_phase(client, project_id, "Phase B", sequence=2)

    resp = client.get(f"/api/v1/projects/{project_id}/hierarchy")
    assert resp.status_code == 200
    sequences = [p["sequence"] for p in resp.json()["phases"]]
    assert sequences == [1, 2, 3]


# ---------------------------------------------------------------------------
# Building ordering
# ---------------------------------------------------------------------------


def test_building_list_ordered_by_name(client: TestClient):
    """Buildings are returned in alphabetical name order."""
    project_id = _create_project(client, "PRJ-BLD-ORD")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    _create_building(client, phase_id, "Charlie Block", "BLK-C")
    _create_building(client, phase_id, "Alpha Block", "BLK-A")
    _create_building(client, phase_id, "Bravo Block", "BLK-B")

    resp = client.get(f"/api/v1/phases/{phase_id}/buildings")
    assert resp.status_code == 200
    names = [b["name"] for b in resp.json()["items"]]
    assert names == sorted(names)


def test_hierarchy_buildings_ordered_by_name(client: TestClient):
    """Hierarchy endpoint returns buildings in alphabetical name order within each phase."""
    project_id = _create_project(client, "PRJ-HIER-BLD-ORD")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    _create_building(client, phase_id, "Zeta Tower", "BLK-Z")
    _create_building(client, phase_id, "Alpha Tower", "BLK-A")

    resp = client.get(f"/api/v1/projects/{project_id}/hierarchy")
    assert resp.status_code == 200
    names = [b["name"] for b in resp.json()["phases"][0]["buildings"]]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# Floor ordering
# ---------------------------------------------------------------------------


def test_floor_list_ordered_by_sequence_number(client: TestClient):
    """Floors are returned in ascending sequence_number order."""
    project_id = _create_project(client, "PRJ-FLR-ORD")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Tower", "TWR")
    _create_floor(client, building_id, "Floor 3", "FL-03", sequence_number=3)
    _create_floor(client, building_id, "Floor 1", "FL-01", sequence_number=1)
    _create_floor(client, building_id, "Floor 2", "FL-02", sequence_number=2)

    resp = client.get(f"/api/v1/buildings/{building_id}/floors")
    assert resp.status_code == 200
    seq_numbers = [f["sequence_number"] for f in resp.json()["items"]]
    assert seq_numbers == sorted(seq_numbers)


def test_hierarchy_floors_ordered_by_sequence_number(client: TestClient):
    """Hierarchy endpoint returns floors in ascending sequence_number order."""
    project_id = _create_project(client, "PRJ-HIER-FLR-ORD")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Tower", "TWR")
    _create_floor(client, building_id, "Floor 5", "FL-05", sequence_number=5)
    _create_floor(client, building_id, "Floor 1", "FL-01", sequence_number=1)
    _create_floor(client, building_id, "Floor 3", "FL-03", sequence_number=3)

    resp = client.get(f"/api/v1/projects/{project_id}/hierarchy")
    assert resp.status_code == 200
    seq_numbers = [
        f["sequence_number"]
        for f in resp.json()["phases"][0]["buildings"][0]["floors"]
    ]
    assert seq_numbers == sorted(seq_numbers)


# ---------------------------------------------------------------------------
# Cross-project protection
# ---------------------------------------------------------------------------


def test_building_belongs_to_correct_project(client: TestClient):
    """A building must be attached to a phase that belongs to the same project."""
    project_a_id = _create_project(client, "PRJ-CROSS-A")
    project_b_id = _create_project(client, "PRJ-CROSS-B")

    phase_a_id = _create_phase(client, project_a_id, "Phase A", sequence=1)
    _create_phase(client, project_b_id, "Phase B", sequence=1)
    building_a_id = _create_building(client, phase_a_id, "Block A", "BLK-A")

    # The building in project A's phase must NOT appear in project B's hierarchy
    resp_b = client.get(f"/api/v1/projects/{project_b_id}/hierarchy")
    assert resp_b.status_code == 200
    phase_b = resp_b.json()["phases"][0]
    building_ids_in_b = [bld["building_id"] for bld in phase_b["buildings"]]
    assert building_a_id not in building_ids_in_b


def test_floor_belongs_to_correct_building(client: TestClient):
    """A floor must be attached to its own building; it must not appear under another."""
    project_id = _create_project(client, "PRJ-FLOOR-SCOPE")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_a_id = _create_building(client, phase_id, "Block A", "BLK-A")
    building_b_id = _create_building(client, phase_id, "Block B", "BLK-B")
    floor_a_id = _create_floor(client, building_a_id, "Floor 1", "FL-01", sequence_number=1)

    resp = client.get(f"/api/v1/projects/{project_id}/hierarchy")
    assert resp.status_code == 200
    buildings = {
        b["building_id"]: b
        for b in resp.json()["phases"][0]["buildings"]
    }
    # Floor A only in building A
    assert any(f["floor_id"] == floor_a_id for f in buildings[building_a_id]["floors"])
    assert not any(f["floor_id"] == floor_a_id for f in buildings[building_b_id]["floors"])


def test_phase_cannot_use_foreign_project_id(client: TestClient):
    """Creating a phase with a nonexistent project_id returns 404."""
    resp = client.post(
        "/api/v1/phases",
        json={"project_id": "nonexistent-project", "name": "Ghost Phase", "sequence": 1},
    )
    assert resp.status_code == 404


def test_building_cannot_use_foreign_phase_id(client: TestClient):
    """Creating a building with a nonexistent phase_id returns 404."""
    resp = client.post(
        "/api/v1/phases/nonexistent-phase/buildings",
        json={"name": "Ghost Building", "code": "GHOST"},
    )
    assert resp.status_code == 404


def test_floor_cannot_use_foreign_building_id(client: TestClient):
    """Creating a floor with a nonexistent building_id returns 404."""
    resp = client.post(
        "/api/v1/buildings/nonexistent-building/floors",
        json={"name": "Ghost Floor", "code": "FL-GHOST", "sequence_number": 1},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Project deletion cascade
# ---------------------------------------------------------------------------


def test_delete_phase_cascades_to_buildings_and_floors(client: TestClient):
    """Deleting a phase removes its buildings and floors (cascade integrity)."""
    project_id = _create_project(client, "PRJ-CASCADE-PH")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Block A", "BLK-A")
    floor_id = _create_floor(client, building_id, "Floor 1", "FL-01", sequence_number=1)

    # Verify all exist
    assert client.get(f"/api/v1/phases/{phase_id}").status_code == 200
    assert client.get(f"/api/v1/buildings/{building_id}").status_code == 200
    assert client.get(f"/api/v1/floors/{floor_id}").status_code == 200

    # Delete phase
    del_resp = client.delete(f"/api/v1/phases/{phase_id}")
    assert del_resp.status_code == 204

    # Building and floor must be gone (cascade)
    assert client.get(f"/api/v1/buildings/{building_id}").status_code == 404
    assert client.get(f"/api/v1/floors/{floor_id}").status_code == 404


def test_delete_building_cascades_to_floors_and_units(client: TestClient):
    """Deleting a building removes its floors and units (cascade integrity)."""
    project_id = _create_project(client, "PRJ-CASCADE-BLD")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Block A", "BLK-A")
    floor_id = _create_floor(client, building_id, "Floor 1", "FL-01", sequence_number=1)
    unit_id = _create_unit(client, floor_id, "101")

    assert client.get(f"/api/v1/units/{unit_id}").status_code == 200

    del_resp = client.delete(f"/api/v1/buildings/{building_id}")
    assert del_resp.status_code == 204

    assert client.get(f"/api/v1/floors/{floor_id}").status_code == 404
    assert client.get(f"/api/v1/units/{unit_id}").status_code == 404


def test_delete_project_with_phases_blocked(client: TestClient):
    """Deleting a project that has phases returns 409 (protected delete)."""
    project_id = _create_project(client, "PRJ-DEL-GUARD")
    _create_phase(client, project_id, "Phase 1", sequence=1)

    resp = client.delete(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 409


def test_delete_project_after_all_phases_removed(client: TestClient):
    """A project can be deleted once all its phases have been removed."""
    project_id = _create_project(client, "PRJ-DEL-CLEAN")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)

    # First deletion blocked
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 409

    # Remove the phase, then project deletion succeeds
    assert client.delete(f"/api/v1/phases/{phase_id}").status_code == 204
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404


# ---------------------------------------------------------------------------
# Project attribute scoping
# ---------------------------------------------------------------------------


def test_attribute_definitions_are_project_scoped(client: TestClient):
    """Attribute definitions created for project A must not appear under project B."""
    project_a_id = _create_project(client, "PRJ-ATTR-A")
    project_b_id = _create_project(client, "PRJ-ATTR-B")

    client.post(
        f"/api/v1/projects/{project_a_id}/attribute-definitions",
        json={"key": "view_type", "label": "View Type"},
    )

    resp = client.get(f"/api/v1/projects/{project_b_id}/attribute-definitions")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_same_attribute_key_allowed_across_projects(client: TestClient):
    """Two projects may each define the same attribute key independently."""
    project_a_id = _create_project(client, "PRJ-ATTR-SAME-A")
    project_b_id = _create_project(client, "PRJ-ATTR-SAME-B")

    resp_a = client.post(
        f"/api/v1/projects/{project_a_id}/attribute-definitions",
        json={"key": "view_type", "label": "View A"},
    )
    assert resp_a.status_code == 201

    resp_b = client.post(
        f"/api/v1/projects/{project_b_id}/attribute-definitions",
        json={"key": "view_type", "label": "View B"},
    )
    assert resp_b.status_code == 201


# ---------------------------------------------------------------------------
# Tie-breaker ordering (unfiltered endpoints)
# ---------------------------------------------------------------------------


def test_phases_same_sequence_across_projects_deterministic(client: TestClient):
    """Unfiltered phase list is deterministic even when multiple phases share the same sequence.

    Two phases from different projects both at sequence=1 must appear in a stable,
    reproducible order (project_id, then id as tie-breakers).
    """
    project_a_id = _create_project(client, "PRJ-TIE-PH-A")
    project_b_id = _create_project(client, "PRJ-TIE-PH-B")
    phase_a_id = _create_phase(client, project_a_id, "Phase 1", sequence=1)
    phase_b_id = _create_phase(client, project_b_id, "Phase 1", sequence=1)

    resp = client.get("/api/v1/phases")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["items"]]

    # Both phases are present and their relative order is stable (a second call
    # must return the same order).
    assert phase_a_id in ids
    assert phase_b_id in ids

    resp2 = client.get("/api/v1/phases")
    assert resp2.json()["items"] == resp.json()["items"]


def test_buildings_same_name_across_phases_deterministic(client: TestClient):
    """Unfiltered building list is deterministic even when multiple buildings share the same name.

    Two buildings in different phases both named 'Block A' must appear in a stable,
    reproducible order (phase_id, then id as tie-breakers).
    """
    project_id = _create_project(client, "PRJ-TIE-BLD")
    phase_a_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    phase_b_id = _create_phase(client, project_id, "Phase 2", sequence=2)
    building_a_id = _create_building(client, phase_a_id, "Block A", "BLK-A1")
    building_b_id = _create_building(client, phase_b_id, "Block A", "BLK-A2")

    resp = client.get("/api/v1/buildings")
    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()["items"]]

    # Both buildings are present and their relative order is stable.
    assert building_a_id in ids
    assert building_b_id in ids

    resp2 = client.get("/api/v1/buildings")
    assert resp2.json()["items"] == resp.json()["items"]
