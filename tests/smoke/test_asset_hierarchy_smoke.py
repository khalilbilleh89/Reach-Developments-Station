"""
Smoke test: Asset Hierarchy

Verifies that the full asset hierarchy can be created end-to-end:
  Project → Phase → Building → Floor → Unit

Assertions:
  - FK relationships are valid (each child references its parent)
  - Endpoints return the created resources with correct fields
"""

from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────────


def _create_project(client: TestClient, code: str = "SMKH-001") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"name": "Smoke Hierarchy Project", "code": code},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_phase(client: TestClient, project_id: str) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/phases",
        json={"name": "Phase One", "code": "PH-1", "sequence": 1},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_building(client: TestClient, phase_id: str) -> dict:
    resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Tower A", "code": "TWR-A"},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_floor(client: TestClient, building_id: str) -> dict:
    resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Ground Floor", "code": "GF", "sequence_number": 1},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_unit(client: TestClient, floor_id: str) -> dict:
    resp = client.post(
        f"/api/v1/floors/{floor_id}/units",
        json={"unit_number": "101", "unit_type": "studio", "internal_area": 85.0},
    )
    assert resp.status_code == 201
    return resp.json()


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_asset_hierarchy_full_creation(client: TestClient):
    """Create project → phase → building → floor → unit; verify FK chain."""
    project = _create_project(client)
    phase = _create_phase(client, project["id"])
    building = _create_building(client, phase["id"])
    floor = _create_floor(client, building["id"])
    unit = _create_unit(client, floor["id"])

    # FK relationships
    assert phase["project_id"] == project["id"]
    assert building["phase_id"] == phase["id"]
    assert floor["building_id"] == building["id"]
    assert unit["floor_id"] == floor["id"]


def test_asset_hierarchy_endpoints_return_created_resources(client: TestClient):
    """GET each resource after creation returns the same data."""
    project = _create_project(client, code="SMKH-002")
    phase = _create_phase(client, project["id"])
    building = _create_building(client, phase["id"])
    floor = _create_floor(client, building["id"])
    unit = _create_unit(client, floor["id"])

    # Re-fetch each resource and verify identity
    assert client.get(f"/api/v1/projects/{project['id']}").json()["id"] == project["id"]
    assert client.get(f"/api/v1/phases/{phase['id']}").json()["id"] == phase["id"]
    assert client.get(f"/api/v1/buildings/{building['id']}").json()["id"] == building["id"]
    assert client.get(f"/api/v1/floors/{floor['id']}").json()["id"] == floor["id"]
    assert client.get(f"/api/v1/units/{unit['id']}").json()["id"] == unit["id"]


def test_asset_hierarchy_list_endpoints(client: TestClient):
    """List endpoints return the created children for their parent."""
    project = _create_project(client, code="SMKH-003")
    phase = _create_phase(client, project["id"])
    building = _create_building(client, phase["id"])
    floor = _create_floor(client, building["id"])
    _create_unit(client, floor["id"])

    phases = client.get(f"/api/v1/projects/{project['id']}/phases").json()
    assert phases["total"] >= 1

    buildings = client.get(f"/api/v1/phases/{phase['id']}/buildings").json()
    assert buildings["total"] >= 1

    floors = client.get(f"/api/v1/buildings/{building['id']}/floors").json()
    assert floors["total"] >= 1

    units = client.get(f"/api/v1/floors/{floor['id']}/units").json()
    assert units["total"] >= 1
