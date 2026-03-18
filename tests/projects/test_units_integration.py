"""
Tests for the Projects ↔ Units integration boundary (PR-A3).

Validates:
- project-scoped unit listing (GET /units?project_id=)
- unit counts in project KPI summary match real inventory
- cross-project unit leakage is impossible
- units are always attached through the canonical floor hierarchy
- project summary unit status breakdown is correct
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


def _create_unit(
    client: TestClient,
    floor_id: str,
    unit_number: str,
    status: str = "available",
) -> str:
    resp = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": unit_number,
            "unit_type": "studio",
            "internal_area": 50.0,
            "status": status,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _build_full_hierarchy(client: TestClient, proj_code: str) -> tuple[str, str]:
    """Create a full Project → Phase → Building → Floor hierarchy.

    Returns (project_id, floor_id).
    """
    project_id = _create_project(client, proj_code)
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Block A", "BLK-A")
    floor_id = _create_floor(client, building_id, "Ground Floor", "FL-01", sequence_number=1)
    return project_id, floor_id


# ---------------------------------------------------------------------------
# project_id filter on GET /units
# ---------------------------------------------------------------------------


def test_list_units_by_project_id_returns_only_project_units(client: TestClient):
    """GET /units?project_id=X returns only units belonging to project X."""
    project_a_id, floor_a_id = _build_full_hierarchy(client, "INT-PA")
    project_b_id, floor_b_id = _build_full_hierarchy(client, "INT-PB")

    unit_a1 = _create_unit(client, floor_a_id, "A-101")
    unit_a2 = _create_unit(client, floor_a_id, "A-102")
    _create_unit(client, floor_b_id, "B-101")

    resp = client.get(f"/api/v1/units?project_id={project_a_id}")
    assert resp.status_code == 200
    data = resp.json()
    returned_ids = {u["id"] for u in data["items"]}
    assert returned_ids == {unit_a1, unit_a2}
    assert data["total"] == 2


def test_list_units_by_project_id_returns_empty_when_no_units(client: TestClient):
    """GET /units?project_id=X returns empty list when project has no units."""
    project_id = _create_project(client, "INT-EMPTY")
    resp = client.get(f"/api/v1/units?project_id={project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_units_by_project_id_returns_empty_for_unknown_project(client: TestClient):
    """GET /units?project_id=nonexistent returns empty list (no 404)."""
    resp = client.get("/api/v1/units?project_id=nonexistent-project")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_units_cross_project_isolation(client: TestClient):
    """Units from project A must never appear in project B's filtered list."""
    project_a_id, floor_a_id = _build_full_hierarchy(client, "INT-ISO-A")
    project_b_id, floor_b_id = _build_full_hierarchy(client, "INT-ISO-B")

    _create_unit(client, floor_a_id, "A-001")
    unit_b = _create_unit(client, floor_b_id, "B-001")

    resp = client.get(f"/api/v1/units?project_id={project_b_id}")
    assert resp.status_code == 200
    ids = {u["id"] for u in resp.json()["items"]}
    assert unit_b in ids
    # Units from project A must not bleed into project B's results
    resp_a = client.get(f"/api/v1/units?project_id={project_a_id}")
    units_a = {u["id"] for u in resp_a.json()["items"]}
    assert units_a.isdisjoint(ids), "Units from project A leaked into project B list"


def test_list_units_by_project_spans_multiple_phases(client: TestClient):
    """GET /units?project_id=X returns units across multiple phases."""
    project_id = _create_project(client, "INT-MULTI-PHASE")
    phase1_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    phase2_id = _create_phase(client, project_id, "Phase 2", sequence=2)

    bld1_id = _create_building(client, phase1_id, "Block 1", "BLK-1")
    bld2_id = _create_building(client, phase2_id, "Block 2", "BLK-2")

    fl1_id = _create_floor(client, bld1_id, "Floor 1", "FL-01", sequence_number=1)
    fl2_id = _create_floor(client, bld2_id, "Floor 1", "FL-01", sequence_number=1)

    u1 = _create_unit(client, fl1_id, "101")
    u2 = _create_unit(client, fl2_id, "101")

    resp = client.get(f"/api/v1/units?project_id={project_id}")
    assert resp.status_code == 200
    ids = {u["id"] for u in resp.json()["items"]}
    assert {u1, u2} == ids
    assert resp.json()["total"] == 2


# ---------------------------------------------------------------------------
# Unit must only attach to a floor (hierarchy enforcement)
# ---------------------------------------------------------------------------


def test_unit_creation_requires_valid_floor(client: TestClient):
    """Creating a unit with a nonexistent floor_id returns 404."""
    resp = client.post(
        "/api/v1/units",
        json={
            "floor_id": "nonexistent-floor",
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 50.0,
        },
    )
    assert resp.status_code == 404


def test_unit_cannot_be_attached_directly_without_floor(client: TestClient):
    """Unit creation payload must always include a floor_id."""
    resp = client.post(
        "/api/v1/units",
        json={
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 50.0,
        },
    )
    assert resp.status_code == 422


def test_unit_number_unique_per_floor_not_per_project(client: TestClient):
    """The same unit_number may exist on two different floors in the same project."""
    project_id = _create_project(client, "INT-UNIQ")
    phase_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    building_id = _create_building(client, phase_id, "Block A", "BLK-A")
    fl1_id = _create_floor(client, building_id, "Floor 1", "FL-01", sequence_number=1)
    fl2_id = _create_floor(client, building_id, "Floor 2", "FL-02", sequence_number=2)

    # Same unit_number on different floors is allowed
    resp1 = client.post(
        "/api/v1/units",
        json={"floor_id": fl1_id, "unit_number": "101", "unit_type": "studio", "internal_area": 50.0},
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        "/api/v1/units",
        json={"floor_id": fl2_id, "unit_number": "101", "unit_type": "studio", "internal_area": 50.0},
    )
    assert resp2.status_code == 201


def test_unit_number_unique_constraint_within_floor(client: TestClient):
    """Duplicate unit_number within the same floor returns 409."""
    _, floor_id = _build_full_hierarchy(client, "INT-DUPNUM")
    _create_unit(client, floor_id, "101")

    resp = client.post(
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 60.0},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Project KPI summary — unit inventory counts
# ---------------------------------------------------------------------------


def test_summary_unit_counts_zero_when_no_units(client: TestClient):
    """Summary unit KPIs are all zero for a project with no units."""
    project_id = _create_project(client, "INT-KPI-ZERO")
    resp = client.get(f"/api/v1/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_units"] == 0
    assert data["available_units"] == 0
    assert data["reserved_units"] == 0
    assert data["under_contract_units"] == 0
    assert data["registered_units"] == 0


def test_summary_unit_counts_match_actual_inventory(client: TestClient):
    """Summary unit KPIs reflect the true count of units created under the project."""
    project_id, floor_id = _build_full_hierarchy(client, "INT-KPI-CNT")

    _create_unit(client, floor_id, "101")
    _create_unit(client, floor_id, "102")
    _create_unit(client, floor_id, "103")

    resp = client.get(f"/api/v1/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_units"] == 3
    assert data["available_units"] == 3


def test_summary_unit_status_breakdown_correct(client: TestClient):
    """Summary unit KPI status breakdown reflects actual unit statuses."""
    project_id, floor_id = _build_full_hierarchy(client, "INT-KPI-STATUS")

    u1 = _create_unit(client, floor_id, "101", status="available")
    u2 = _create_unit(client, floor_id, "102", status="available")

    # Advance unit statuses
    client.patch(f"/api/v1/units/{u1}", json={"status": "reserved"})
    client.patch(f"/api/v1/units/{u2}", json={"status": "reserved"})
    client.patch(f"/api/v1/units/{u2}", json={"status": "under_contract"})

    _create_unit(client, floor_id, "103", status="available")

    resp = client.get(f"/api/v1/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_units"] == 3
    assert data["available_units"] == 1
    assert data["reserved_units"] == 1
    assert data["under_contract_units"] == 1
    assert data["registered_units"] == 0


def test_summary_unit_counts_scoped_to_project(client: TestClient):
    """Summary unit counts only include units belonging to the project, not all projects."""
    project_a_id, floor_a_id = _build_full_hierarchy(client, "INT-KPI-SCOPE-A")
    project_b_id, floor_b_id = _build_full_hierarchy(client, "INT-KPI-SCOPE-B")

    _create_unit(client, floor_a_id, "A-101")
    _create_unit(client, floor_a_id, "A-102")
    _create_unit(client, floor_b_id, "B-101")

    resp_a = client.get(f"/api/v1/projects/{project_a_id}/summary")
    assert resp_a.json()["total_units"] == 2

    resp_b = client.get(f"/api/v1/projects/{project_b_id}/summary")
    assert resp_b.json()["total_units"] == 1


def test_summary_unit_counts_span_multiple_floors_and_phases(client: TestClient):
    """Summary unit KPIs aggregate units across all floors, buildings, and phases."""
    project_id = _create_project(client, "INT-KPI-MULTI")
    phase1_id = _create_phase(client, project_id, "Phase 1", sequence=1)
    phase2_id = _create_phase(client, project_id, "Phase 2", sequence=2)

    bld1_id = _create_building(client, phase1_id, "Block 1", "BLK-1")
    bld2_id = _create_building(client, phase2_id, "Block 2", "BLK-2")

    fl1_id = _create_floor(client, bld1_id, "Floor 1", "FL-01", sequence_number=1)
    fl2_id = _create_floor(client, bld1_id, "Floor 2", "FL-02", sequence_number=2)
    fl3_id = _create_floor(client, bld2_id, "Floor 1", "FL-01", sequence_number=1)

    _create_unit(client, fl1_id, "101")
    _create_unit(client, fl1_id, "102")
    _create_unit(client, fl2_id, "201")
    _create_unit(client, fl3_id, "301")

    resp = client.get(f"/api/v1/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_units"] == 4
    assert data["available_units"] == 4


# ---------------------------------------------------------------------------
# Hierarchy unit counts vs summary unit counts consistency
# ---------------------------------------------------------------------------


def test_hierarchy_unit_count_matches_summary_total_units(client: TestClient):
    """Sum of unit_count across all hierarchy floors equals summary total_units."""
    project_id, floor_id = _build_full_hierarchy(client, "INT-CONS")

    _create_unit(client, floor_id, "101")
    _create_unit(client, floor_id, "102")
    _create_unit(client, floor_id, "103")

    # Get hierarchy and sum floor unit_counts
    hier_resp = client.get(f"/api/v1/projects/{project_id}/hierarchy")
    assert hier_resp.status_code == 200
    total_from_hierarchy = sum(
        floor["unit_count"]
        for phase in hier_resp.json()["phases"]
        for building in phase["buildings"]
        for floor in building["floors"]
    )

    summary_resp = client.get(f"/api/v1/projects/{project_id}/summary")
    assert summary_resp.status_code == 200
    total_from_summary = summary_resp.json()["total_units"]

    assert total_from_hierarchy == total_from_summary


def test_hierarchy_unit_count_matches_project_filter_total(client: TestClient):
    """Unit count from hierarchy floors equals total returned by GET /units?project_id=."""
    project_id, floor_id = _build_full_hierarchy(client, "INT-CONS2")

    _create_unit(client, floor_id, "101")
    _create_unit(client, floor_id, "102")

    hier_resp = client.get(f"/api/v1/projects/{project_id}/hierarchy")
    total_from_hierarchy = sum(
        floor["unit_count"]
        for phase in hier_resp.json()["phases"]
        for building in phase["buildings"]
        for floor in building["floors"]
    )

    units_resp = client.get(f"/api/v1/units?project_id={project_id}")
    assert total_from_hierarchy == units_resp.json()["total"]
