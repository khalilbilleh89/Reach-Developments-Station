"""
Tests for the Concept Design API endpoints.

Validates HTTP behaviour, request/response contracts, and full workflow
including unit-mix addition and summary computation.

PR-CONCEPT-052
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_project(client: TestClient, code: str = "PRJ-CD01") -> str:
    resp = client.post(
        "/api/v1/projects", json={"name": f"Concept Project {code}", "code": code}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_option(
    client: TestClient,
    *,
    name: str = "Option A",
    project_id: str | None = None,
    status: str = "draft",
    gross_floor_area: float | None = None,
) -> dict:
    payload: dict = {"name": name, "status": status}
    if project_id is not None:
        payload["project_id"] = project_id
    if gross_floor_area is not None:
        payload["gross_floor_area"] = gross_floor_area
    resp = client.post("/api/v1/concept-options", json=payload)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# ConceptOption creation
# ---------------------------------------------------------------------------

def test_create_concept_option_minimal(client: TestClient):
    """POST /api/v1/concept-options — minimal payload should succeed."""
    resp = client.post("/api/v1/concept-options", json={"name": "Scheme Alpha"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Scheme Alpha"
    assert data["status"] == "draft"
    assert data["project_id"] is None
    assert "id" in data


def test_create_concept_option_with_project(client: TestClient):
    """POST — with project_id link."""
    project_id = _create_project(client, "PRJ-CD02")
    resp = client.post(
        "/api/v1/concept-options",
        json={
            "name": "Mid-Rise Scheme",
            "project_id": project_id,
            "status": "active",
            "gross_floor_area": 15000.0,
            "building_count": 3,
            "floor_count": 8,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["gross_floor_area"] == 15000.0
    assert data["building_count"] == 3


def test_create_concept_option_invalid_status(client: TestClient):
    """POST with invalid status should return 422."""
    resp = client.post(
        "/api/v1/concept-options", json={"name": "Bad", "status": "unknown"}
    )
    assert resp.status_code == 422


def test_create_concept_option_missing_name(client: TestClient):
    """POST without name should return 422."""
    resp = client.post("/api/v1/concept-options", json={"status": "draft"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Get concept option
# ---------------------------------------------------------------------------

def test_get_concept_option(client: TestClient):
    """GET /concept-options/{id} — should return the created option."""
    option = _create_option(client, name="Scheme Beta")
    resp = client.get(f"/api/v1/concept-options/{option['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == option["id"]
    assert resp.json()["name"] == "Scheme Beta"


def test_get_concept_option_not_found(client: TestClient):
    """GET with unknown id should return 404."""
    resp = client.get("/api/v1/concept-options/no-such-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List concept options
# ---------------------------------------------------------------------------

def test_list_concept_options_empty(client: TestClient):
    resp = client.get("/api/v1/concept-options")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_concept_options(client: TestClient):
    _create_option(client, name="Opt 1")
    _create_option(client, name="Opt 2")
    resp = client.get("/api/v1/concept-options")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_concept_options_filter_by_project(client: TestClient):
    project_id = _create_project(client, "PRJ-CDLIST")
    _create_option(client, name="Linked", project_id=project_id)
    _create_option(client, name="Unlinked")
    resp = client.get(f"/api/v1/concept-options?project_id={project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Linked"


# ---------------------------------------------------------------------------
# Update concept option
# ---------------------------------------------------------------------------

def test_update_concept_option(client: TestClient):
    option = _create_option(client, name="Original")
    resp = client.patch(
        f"/api/v1/concept-options/{option['id']}",
        json={"name": "Updated", "status": "active"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated"
    assert data["status"] == "active"


def test_update_concept_option_not_found(client: TestClient):
    resp = client.patch(
        "/api/v1/concept-options/no-such-id", json={"name": "x"}
    )
    assert resp.status_code == 404


def test_update_concept_option_partial(client: TestClient):
    """PATCH should only modify provided fields."""
    option = _create_option(
        client, name="Keep Name", gross_floor_area=5000.0
    )
    resp = client.patch(
        f"/api/v1/concept-options/{option['id']}",
        json={"status": "archived"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Keep Name"
    assert data["status"] == "archived"
    assert data["gross_floor_area"] == 5000.0


# ---------------------------------------------------------------------------
# Unit-mix line
# ---------------------------------------------------------------------------

def test_add_unit_mix_line(client: TestClient):
    option = _create_option(client, name="Mix Test")
    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/unit-mix",
        json={
            "unit_type": "1BR",
            "units_count": 40,
            "avg_internal_area": 70.0,
            "avg_sellable_area": 75.0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["unit_type"] == "1BR"
    assert data["units_count"] == 40
    assert data["concept_option_id"] == option["id"]


def test_add_unit_mix_line_not_found(client: TestClient):
    resp = client.post(
        "/api/v1/concept-options/no-such-id/unit-mix",
        json={"unit_type": "1BR", "units_count": 10},
    )
    assert resp.status_code == 404


def test_add_unit_mix_line_invalid_count(client: TestClient):
    option = _create_option(client, name="Mix Validation")
    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/unit-mix",
        json={"unit_type": "1BR", "units_count": 0},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Summary endpoint
# ---------------------------------------------------------------------------

def test_summary_no_mix_lines(client: TestClient):
    """Summary with no mix lines should return zero unit_count and None metrics."""
    option = _create_option(client, name="Empty Scheme", gross_floor_area=10000.0)
    resp = client.get(f"/api/v1/concept-options/{option['id']}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_count"] == 0
    assert data["sellable_area"] is None
    assert data["efficiency_ratio"] is None
    assert data["average_unit_area"] is None
    assert data["mix_lines"] == []


def test_summary_with_mix_lines(client: TestClient):
    """Summary should return correct derived metrics after adding mix lines."""
    option = _create_option(
        client, name="Full Scheme", gross_floor_area=12000.0
    )
    option_id = option["id"]

    client.post(
        f"/api/v1/concept-options/{option_id}/unit-mix",
        json={"unit_type": "1BR", "units_count": 60, "avg_sellable_area": 75.0},
    )
    client.post(
        f"/api/v1/concept-options/{option_id}/unit-mix",
        json={"unit_type": "2BR", "units_count": 40, "avg_sellable_area": 115.0},
    )

    resp = client.get(f"/api/v1/concept-options/{option_id}/summary")
    assert resp.status_code == 200
    data = resp.json()

    # unit_count = 100
    assert data["unit_count"] == 100
    # sellable_area = 60*75 + 40*115 = 4500+4600 = 9100
    assert abs(data["sellable_area"] - 9100.0) < 0.01
    # efficiency_ratio = 9100/12000
    assert abs(data["efficiency_ratio"] - 9100.0 / 12000.0) < 0.0001
    # average_unit_area = 9100/100 = 91
    assert abs(data["average_unit_area"] - 91.0) < 0.01
    assert len(data["mix_lines"]) == 2


def test_summary_not_found(client: TestClient):
    resp = client.get("/api/v1/concept-options/no-such-id/summary")
    assert resp.status_code == 404
