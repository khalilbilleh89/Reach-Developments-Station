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


def test_create_concept_option_unknown_project_id(client: TestClient):
    """POST with a non-existent project_id should return 404."""
    resp = client.post(
        "/api/v1/concept-options",
        json={"name": "Orphan Option", "project_id": "no-such-project"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("code") == "RESOURCE_NOT_FOUND"


def test_create_concept_option_unknown_scenario_id(client: TestClient):
    """POST with a non-existent scenario_id should return 404."""
    resp = client.post(
        "/api/v1/concept-options",
        json={"name": "Orphan Option", "scenario_id": "no-such-scenario"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("code") == "RESOURCE_NOT_FOUND"


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


def test_update_concept_option_null_name_rejected(client: TestClient):
    """PATCH with explicit null for 'name' should return 422."""
    option = _create_option(client, name="Stable Name")
    resp = client.patch(
        f"/api/v1/concept-options/{option['id']}",
        json={"name": None},
    )
    assert resp.status_code == 422


def test_update_concept_option_null_status_rejected(client: TestClient):
    """PATCH with explicit null for 'status' should return 422."""
    option = _create_option(client, name="Stable Status")
    resp = client.patch(
        f"/api/v1/concept-options/{option['id']}",
        json={"status": None},
    )
    assert resp.status_code == 422


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


# ---------------------------------------------------------------------------
# Comparison endpoint — PR-CONCEPT-053
# ---------------------------------------------------------------------------


def test_compare_by_project_id(client: TestClient):
    """GET /compare?project_id=... returns 200 with comparison result."""
    project_id = _create_project(client, "PRJ-CMPAPI-001")
    opt_a = _create_option(client, name="Option A", project_id=project_id, gross_floor_area=12000.0)
    opt_b = _create_option(client, name="Option B", project_id=project_id, gross_floor_area=11000.0)

    client.post(
        f"/api/v1/concept-options/{opt_a['id']}/unit-mix",
        json={"unit_type": "1BR", "units_count": 60, "avg_sellable_area": 75.0},
    )
    client.post(
        f"/api/v1/concept-options/{opt_a['id']}/unit-mix",
        json={"unit_type": "2BR", "units_count": 40, "avg_sellable_area": 115.0},
    )  # sellable = 9100
    client.post(
        f"/api/v1/concept-options/{opt_b['id']}/unit-mix",
        json={"unit_type": "1BR", "units_count": 50, "avg_sellable_area": 90.0},
    )  # sellable = 4500

    resp = client.get(f"/api/v1/concept-options/compare?project_id={project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["comparison_basis"] == "project"
    assert data["option_count"] == 2
    assert len(data["rows"]) == 2
    # opt_a has higher sellable area
    assert data["best_sellable_area_option_id"] == opt_a["id"]
    assert data["best_unit_count_option_id"] == opt_a["id"]


def test_compare_by_scenario_id(client: TestClient):
    """GET /compare?scenario_id=... returns 200 with comparison result."""
    project_id = _create_project(client, "PRJ-CMPAPI-002")
    scenario_resp = client.post(
        "/api/v1/scenarios",
        json={"project_id": project_id, "name": "Test Scenario"},
    )
    assert scenario_resp.status_code == 201
    scenario_id = scenario_resp.json()["id"]

    opt_resp = client.post(
        "/api/v1/concept-options",
        json={"name": "Scenario Opt", "scenario_id": scenario_id},
    )
    assert opt_resp.status_code == 201
    opt = opt_resp.json()

    resp = client.get(f"/api/v1/concept-options/compare?scenario_id={scenario_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["comparison_basis"] == "scenario"
    assert data["option_count"] == 1
    assert data["rows"][0]["concept_option_id"] == opt["id"]


def test_compare_neither_param_returns_422(client: TestClient):
    """GET /compare with no params returns 422."""
    resp = client.get("/api/v1/concept-options/compare")
    assert resp.status_code == 422


def test_compare_both_params_returns_422(client: TestClient):
    """GET /compare with both project_id and scenario_id returns 422."""
    project_id = _create_project(client, "PRJ-CMPAPI-003")
    resp = client.get(
        f"/api/v1/concept-options/compare?project_id={project_id}&scenario_id=some-id"
    )
    assert resp.status_code == 422


def test_compare_empty_result_when_no_options(client: TestClient):
    """GET /compare returns 200 with empty rows when project exists but has no options."""
    project_id = _create_project(client, "PRJ-CMPAPI-004")
    resp = client.get(f"/api/v1/concept-options/compare?project_id={project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["option_count"] == 0
    assert data["rows"] == []
    assert data["best_sellable_area_option_id"] is None


def test_compare_populated_result_fields(client: TestClient):
    """GET /compare populated result includes correct best-option and delta fields."""
    project_id = _create_project(client, "PRJ-CMPAPI-005")
    opt_a = _create_option(client, name="Mid Rise", project_id=project_id, gross_floor_area=12000.0)
    opt_b = _create_option(client, name="Tall Tower", project_id=project_id, gross_floor_area=14000.0)

    # opt_a: 100 units, sellable=9100
    client.post(f"/api/v1/concept-options/{opt_a['id']}/unit-mix",
                json={"unit_type": "1BR", "units_count": 60, "avg_sellable_area": 75.0})
    client.post(f"/api/v1/concept-options/{opt_a['id']}/unit-mix",
                json={"unit_type": "2BR", "units_count": 40, "avg_sellable_area": 115.0})

    # opt_b: 92 units, sellable=9600
    client.post(f"/api/v1/concept-options/{opt_b['id']}/unit-mix",
                json={"unit_type": "1BR", "units_count": 50, "avg_sellable_area": 80.0})
    client.post(f"/api/v1/concept-options/{opt_b['id']}/unit-mix",
                json={"unit_type": "2BR", "units_count": 42, "avg_sellable_area": 130.0})
    # opt_b sellable = 50*80 + 42*130 = 4000 + 5460 = 9460

    resp = client.get(f"/api/v1/concept-options/compare?project_id={project_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["option_count"] == 2
    assert data["best_unit_count_option_id"] == opt_a["id"]
    assert data["best_sellable_area_option_id"] == opt_b["id"]

    rows_by_id = {r["concept_option_id"]: r for r in data["rows"]}
    row_b = rows_by_id[opt_b["id"]]
    assert row_b["is_best_sellable_area"] is True
    assert abs(row_b["sellable_area_delta_vs_best"]) < 0.01

    row_a = rows_by_id[opt_a["id"]]
    assert row_a["is_best_sellable_area"] is False
    assert row_a["sellable_area_delta_vs_best"] < 0
    assert row_a["is_best_unit_count"] is True
