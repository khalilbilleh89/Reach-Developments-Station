"""
Tests for the Scenario Engine API endpoints.

Validates HTTP behaviour, request/response contracts, lifecycle transitions,
duplication lineage, version management, approval rules, and comparison.
"""

import pytest
from fastapi.testclient import TestClient


_BASE = "/api/v1/scenarios"

_VALID_SCENARIO = {
    "name": "Base Option",
    "source_type": "feasibility",
    "notes": "Initial scenario",
}

_VALID_VERSION = {
    "title": "v1 snapshot",
    "notes": "First version",
    "assumptions_json": {"gdv": 10000000, "cost_per_sqm": 800},
    "comparison_metrics_json": {"irr": 0.18, "profit_margin": 0.22},
    "created_by": "test-user",
}


# ---------------------------------------------------------------------------
# Create scenario
# ---------------------------------------------------------------------------


def test_create_scenario(client: TestClient):
    resp = client.post(_BASE, json=_VALID_SCENARIO)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Base Option"
    assert data["status"] == "draft"
    assert data["source_type"] == "feasibility"
    assert data["is_active"] is True
    assert "id" in data


def test_create_scenario_with_project_and_land(client: TestClient):
    payload = {
        "name": "Land Option",
        "source_type": "land",
        "project_id": "proj-001",
        "land_id": "land-001",
    }
    resp = client.post(_BASE, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == "proj-001"
    assert data["land_id"] == "land-001"


def test_create_scenario_invalid_source_type(client: TestClient):
    payload = {**_VALID_SCENARIO, "source_type": "unknown_module"}
    resp = client.post(_BASE, json=payload)
    assert resp.status_code == 422


def test_create_scenario_missing_name(client: TestClient):
    resp = client.post(_BASE, json={"source_type": "feasibility"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Get scenario
# ---------------------------------------------------------------------------


def test_get_scenario(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    resp = client.get(f"{_BASE}/{scenario_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == scenario_id


def test_get_scenario_not_found(client: TestClient):
    resp = client.get(f"{_BASE}/no-such-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List scenarios
# ---------------------------------------------------------------------------


def test_list_scenarios_empty(client: TestClient):
    resp = client.get(_BASE)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_scenarios(client: TestClient):
    client.post(_BASE, json=_VALID_SCENARIO)
    client.post(_BASE, json={**_VALID_SCENARIO, "name": "Option B"})
    resp = client.get(_BASE)
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_scenarios_filter_by_source_type(client: TestClient):
    client.post(_BASE, json={"name": "Feasibility A", "source_type": "feasibility"})
    client.post(_BASE, json={"name": "Land A", "source_type": "land"})
    resp = client.get(f"{_BASE}?source_type=land")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["source_type"] == "land"


def test_list_scenarios_filter_by_project(client: TestClient):
    client.post(_BASE, json={**_VALID_SCENARIO, "name": "P1 Option", "project_id": "proj-aaa"})
    client.post(_BASE, json={**_VALID_SCENARIO, "name": "P2 Option", "project_id": "proj-bbb"})
    resp = client.get(f"{_BASE}?project_id=proj-aaa")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["project_id"] == "proj-aaa"


# ---------------------------------------------------------------------------
# Update scenario
# ---------------------------------------------------------------------------


def test_update_scenario(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    resp = client.patch(f"{_BASE}/{scenario_id}", json={"name": "Updated Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


def test_update_scenario_not_found(client: TestClient):
    resp = client.patch(f"{_BASE}/no-such-id", json={"name": "X"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Version management
# ---------------------------------------------------------------------------


def test_create_version(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    resp = client.post(f"{_BASE}/{scenario_id}/versions", json=_VALID_VERSION)
    assert resp.status_code == 201
    data = resp.json()
    assert data["scenario_id"] == scenario_id
    assert data["version_number"] == 1
    assert data["assumptions_json"]["gdv"] == 10000000
    assert data["is_approved"] is False


def test_create_multiple_versions(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    client.post(f"{_BASE}/{scenario_id}/versions", json=_VALID_VERSION)
    resp = client.post(f"{_BASE}/{scenario_id}/versions", json={**_VALID_VERSION, "title": "v2"})
    assert resp.status_code == 201
    assert resp.json()["version_number"] == 2


def test_list_versions(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    client.post(f"{_BASE}/{scenario_id}/versions", json=_VALID_VERSION)
    client.post(f"{_BASE}/{scenario_id}/versions", json={**_VALID_VERSION, "title": "v2"})
    resp = client.get(f"{_BASE}/{scenario_id}/versions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["items"][0]["version_number"] == 1


def test_get_latest_version(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    client.post(f"{_BASE}/{scenario_id}/versions", json=_VALID_VERSION)
    client.post(f"{_BASE}/{scenario_id}/versions", json={**_VALID_VERSION, "title": "v2"})
    resp = client.get(f"{_BASE}/{scenario_id}/versions/latest")
    assert resp.status_code == 200
    assert resp.json()["version_number"] == 2
    assert resp.json()["title"] == "v2"


def test_get_latest_version_no_versions(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    resp = client.get(f"{_BASE}/{scenario_id}/versions/latest")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Duplication
# ---------------------------------------------------------------------------


def test_duplicate_scenario(client: TestClient):
    source_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    client.post(f"{_BASE}/{source_id}/versions", json=_VALID_VERSION)

    resp = client.post(
        f"{_BASE}/{source_id}/duplicate",
        json={"name": "Duplicate Option", "notes": "copy"},
    )
    assert resp.status_code == 201
    dup = resp.json()
    assert dup["name"] == "Duplicate Option"
    assert dup["status"] == "draft"
    assert dup["base_scenario_id"] == source_id


def test_duplicate_scenario_copies_version(client: TestClient):
    source_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    client.post(f"{_BASE}/{source_id}/versions", json=_VALID_VERSION)

    dup_id = client.post(
        f"{_BASE}/{source_id}/duplicate",
        json={"name": "Dup"},
    ).json()["id"]

    versions_resp = client.get(f"{_BASE}/{dup_id}/versions")
    assert versions_resp.status_code == 200
    items = versions_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["assumptions_json"]["gdv"] == 10000000


def test_duplicate_scenario_not_found(client: TestClient):
    resp = client.post(f"{_BASE}/no-such/duplicate", json={"name": "X"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------


def test_approve_scenario(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    client.post(f"{_BASE}/{scenario_id}/versions", json=_VALID_VERSION)

    resp = client.post(f"{_BASE}/{scenario_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_approve_scenario_marks_latest_version(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    client.post(f"{_BASE}/{scenario_id}/versions", json=_VALID_VERSION)
    client.post(f"{_BASE}/{scenario_id}/versions", json={**_VALID_VERSION, "title": "v2"})

    client.post(f"{_BASE}/{scenario_id}/approve")

    versions = client.get(f"{_BASE}/{scenario_id}/versions").json()["items"]
    assert versions[0]["is_approved"] is False  # v1
    assert versions[1]["is_approved"] is True   # v2


def test_approve_scenario_no_versions(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    resp = client.post(f"{_BASE}/{scenario_id}/approve")
    assert resp.status_code == 422


def test_approve_archived_scenario(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    client.post(f"{_BASE}/{scenario_id}/versions", json=_VALID_VERSION)
    client.post(f"{_BASE}/{scenario_id}/archive")
    resp = client.post(f"{_BASE}/{scenario_id}/approve")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Archival
# ---------------------------------------------------------------------------


def test_archive_scenario(client: TestClient):
    scenario_id = client.post(_BASE, json=_VALID_SCENARIO).json()["id"]
    resp = client.post(f"{_BASE}/{scenario_id}/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


def test_archive_scenario_not_found(client: TestClient):
    resp = client.post(f"{_BASE}/no-such/archive")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def test_compare_scenarios(client: TestClient):
    id_a = client.post(_BASE, json={"name": "Option A", "source_type": "feasibility"}).json()["id"]
    id_b = client.post(_BASE, json={"name": "Option B", "source_type": "feasibility"}).json()["id"]

    client.post(f"{_BASE}/{id_a}/versions", json=_VALID_VERSION)
    client.post(
        f"{_BASE}/{id_b}/versions",
        json={**_VALID_VERSION, "assumptions_json": {"gdv": 9000000}},
    )

    resp = client.post(f"{_BASE}/compare", json={"scenario_ids": [id_a, id_b]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["scenarios"]) == 2
    names = {s["scenario_name"] for s in data["scenarios"]}
    assert names == {"Option A", "Option B"}


def test_compare_scenarios_missing_id(client: TestClient):
    id_a = client.post(_BASE, json={"name": "Option A", "source_type": "feasibility"}).json()["id"]
    resp = client.post(f"{_BASE}/compare", json={"scenario_ids": [id_a, "no-such-id"]})
    assert resp.status_code == 404


def test_compare_scenarios_no_versions(client: TestClient):
    id_a = client.post(_BASE, json={"name": "Option A", "source_type": "feasibility"}).json()["id"]
    id_b = client.post(_BASE, json={"name": "Option B", "source_type": "feasibility"}).json()["id"]

    resp = client.post(f"{_BASE}/compare", json={"scenario_ids": [id_a, id_b]})
    assert resp.status_code == 200
    for item in resp.json()["scenarios"]:
        assert item["latest_version_number"] is None
        assert item["assumptions_json"] is None


# ---------------------------------------------------------------------------
# Auth rejection
# ---------------------------------------------------------------------------


def test_create_scenario_unauthenticated(unauth_client: TestClient):
    resp = unauth_client.post(_BASE, json=_VALID_SCENARIO)
    assert resp.status_code in (401, 403)


def test_list_scenarios_unauthenticated(unauth_client: TestClient):
    resp = unauth_client.get(_BASE)
    assert resp.status_code in (401, 403)
