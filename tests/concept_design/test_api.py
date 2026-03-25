"""
Tests for the Concept Design API endpoints.

Validates HTTP behaviour, request/response contracts, and full workflow
including unit-mix addition, summary computation, and concept option promotion.

PR-CONCEPT-052, PR-CONCEPT-054
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

    # opt_b: 92 units, sellable=9460 (50*80 + 42*130 = 4000 + 5460 = 9460)
    client.post(f"/api/v1/concept-options/{opt_b['id']}/unit-mix",
                json={"unit_type": "1BR", "units_count": 50, "avg_sellable_area": 80.0})
    client.post(f"/api/v1/concept-options/{opt_b['id']}/unit-mix",
                json={"unit_type": "2BR", "units_count": 42, "avg_sellable_area": 130.0})

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


# ---------------------------------------------------------------------------
# Promotion endpoint — PR-CONCEPT-054
# ---------------------------------------------------------------------------

def _create_promotable_option(
    client: TestClient,
    project_id: str,
    *,
    name: str = "Promotable Option",
    status: str = "active",
) -> dict:
    """Create a concept option with full structural data ready for promotion."""
    option = _create_option(
        client,
        name=name,
        project_id=project_id,
        status=status,
        gross_floor_area=12000.0,
    )
    # Patch building/floor counts
    resp = client.patch(
        f"/api/v1/concept-options/{option['id']}",
        json={"building_count": 2, "floor_count": 8},
    )
    assert resp.status_code == 200
    option = resp.json()

    # Add a unit-mix line
    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/unit-mix",
        json={"unit_type": "1BR", "units_count": 50, "avg_sellable_area": 75.0},
    )
    assert resp.status_code == 201
    return option


def test_promote_concept_option_success(client: TestClient):
    """POST /{id}/promote — happy path returns 201 with promotion response."""
    project_id = _create_project(client, "PRJ-PROMO-001")
    option = _create_promotable_option(client, project_id)

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote",
        json={},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["concept_option_id"] == option["id"]
    assert data["promoted_project_id"] == project_id
    assert "promoted_phase_id" in data
    assert data["promoted_phase_name"].startswith("Phase 1")
    assert "promoted_at" in data
    # Scaffolding counts (building_count=2, floor_count=8, units_count=50)
    assert data["buildings_created"] == 2
    assert data["floors_created"] == 16  # 2 buildings × 8 floors
    assert data["units_created"] == 50


def test_promote_sets_is_promoted_flag(client: TestClient):
    """After promotion the concept option should have is_promoted=True."""
    project_id = _create_project(client, "PRJ-PROMO-002")
    option = _create_promotable_option(client, project_id)

    client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})

    resp = client.get(f"/api/v1/concept-options/{option['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_promoted"] is True
    assert data["promoted_project_id"] == project_id
    assert data["promoted_at"] is not None


def test_promote_with_target_project_id(client: TestClient):
    """Promotion with target_project_id on an unlinked option."""
    project_id = _create_project(client, "PRJ-PROMO-003")
    # Create option without project link
    option = _create_option(client, name="Unlinked Option")
    # Add structural data
    client.patch(
        f"/api/v1/concept-options/{option['id']}",
        json={"building_count": 1, "floor_count": 5},
    )
    client.post(
        f"/api/v1/concept-options/{option['id']}/unit-mix",
        json={"unit_type": "2BR", "units_count": 30, "avg_sellable_area": 100.0},
    )

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote",
        json={"target_project_id": project_id},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["promoted_project_id"] == project_id


def test_promote_with_custom_phase_name(client: TestClient):
    """Promotion with a custom phase_name should use that name."""
    project_id = _create_project(client, "PRJ-PROMO-004")
    option = _create_promotable_option(client, project_id, name="Design A")

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote",
        json={"phase_name": "Concept Delivery Phase"},
    )
    assert resp.status_code == 201
    assert resp.json()["promoted_phase_name"] == "Concept Delivery Phase"


def test_promote_with_promotion_notes(client: TestClient):
    """Promotion notes should be stored and returned."""
    project_id = _create_project(client, "PRJ-PROMO-005")
    option = _create_promotable_option(client, project_id)

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote",
        json={"promotion_notes": "Board approved on 2026-03-24."},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["promotion_notes"] == "Board approved on 2026-03-24."

    # Notes should also be stored on the option
    option_resp = client.get(f"/api/v1/concept-options/{option['id']}")
    assert option_resp.json()["promotion_notes"] == "Board approved on 2026-03-24."


def test_promote_already_promoted_returns_409(client: TestClient):
    """Promoting an already-promoted option should return 409 Conflict."""
    project_id = _create_project(client, "PRJ-PROMO-006")
    option = _create_promotable_option(client, project_id)

    client.post(f"/api/v1/concept-options/{option['id']}/promote", json={})

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote", json={}
    )
    assert resp.status_code == 409


def test_promote_archived_option_returns_422(client: TestClient):
    """Promoting an archived option should return 422."""
    project_id = _create_project(client, "PRJ-PROMO-007")
    option = _create_promotable_option(client, project_id, status="draft")
    client.patch(
        f"/api/v1/concept-options/{option['id']}", json={"status": "archived"}
    )

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote", json={}
    )
    assert resp.status_code == 422


def test_promote_option_missing_building_count_returns_422(client: TestClient):
    """Promoting without building_count should return 422."""
    project_id = _create_project(client, "PRJ-PROMO-008")
    option = _create_option(client, name="No Building Count", project_id=project_id)
    # Only floor_count, no building_count
    client.patch(f"/api/v1/concept-options/{option['id']}", json={"floor_count": 5})
    client.post(
        f"/api/v1/concept-options/{option['id']}/unit-mix",
        json={"unit_type": "1BR", "units_count": 10},
    )

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote", json={}
    )
    assert resp.status_code == 422


def test_promote_option_missing_floor_count_returns_422(client: TestClient):
    """Promoting without floor_count should return 422."""
    project_id = _create_project(client, "PRJ-PROMO-009")
    option = _create_option(client, name="No Floor Count", project_id=project_id)
    client.patch(f"/api/v1/concept-options/{option['id']}", json={"building_count": 2})
    client.post(
        f"/api/v1/concept-options/{option['id']}/unit-mix",
        json={"unit_type": "1BR", "units_count": 10},
    )

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote", json={}
    )
    assert resp.status_code == 422


def test_promote_option_missing_mix_lines_returns_422(client: TestClient):
    """Promoting without unit mix lines should return 422."""
    project_id = _create_project(client, "PRJ-PROMO-010")
    option = _create_option(client, name="No Mix Lines", project_id=project_id)
    client.patch(
        f"/api/v1/concept-options/{option['id']}",
        json={"building_count": 2, "floor_count": 5},
    )

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote", json={}
    )
    assert resp.status_code == 422


def test_promote_option_no_project_no_target_returns_422(client: TestClient):
    """Promoting without project link and no target_project_id should return 422."""
    option = _create_option(client, name="Unlinked No Target")
    client.patch(
        f"/api/v1/concept-options/{option['id']}",
        json={"building_count": 1, "floor_count": 4},
    )
    client.post(
        f"/api/v1/concept-options/{option['id']}/unit-mix",
        json={"unit_type": "1BR", "units_count": 20},
    )

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote", json={}
    )
    assert resp.status_code == 422


def test_promote_not_found_returns_404(client: TestClient):
    """Promoting a non-existent option should return 404."""
    resp = client.post(
        "/api/v1/concept-options/no-such-id/promote",
        json={},
    )
    assert resp.status_code == 404


def test_promote_with_unknown_target_project_id_returns_404(client: TestClient):
    """Promoting with a non-existent target_project_id should return 404."""
    option = _create_option(client, name="No Valid Project")
    client.patch(
        f"/api/v1/concept-options/{option['id']}",
        json={"building_count": 1, "floor_count": 3},
    )
    client.post(
        f"/api/v1/concept-options/{option['id']}/unit-mix",
        json={"unit_type": "1BR", "units_count": 10},
    )

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote",
        json={"target_project_id": "no-such-project"},
    )
    assert resp.status_code == 404


def test_promote_creates_phase_under_project(client: TestClient):
    """Promotion must create a phase that is retrievable via the phases API."""
    project_id = _create_project(client, "PRJ-PROMO-011")
    option = _create_promotable_option(client, project_id, name="Phase Check Option")

    promo_resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote", json={}
    )
    assert promo_resp.status_code == 201
    phase_id = promo_resp.json()["promoted_phase_id"]

    phase_resp = client.get(f"/api/v1/phases/{phase_id}")
    assert phase_resp.status_code == 200
    phase_data = phase_resp.json()
    assert phase_data["project_id"] == project_id
    assert phase_data["sequence"] == 1
    assert phase_data["status"] == "planned"


def test_promote_conflicting_project_ids_returns_422(client: TestClient):
    """Supplying a target_project_id that differs from the option's project_id returns 422."""
    project_id = _create_project(client, "PRJ-PROMO-012")
    other_project_id = _create_project(client, "PRJ-PROMO-012B")
    option = _create_promotable_option(client, project_id)

    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote",
        json={"target_project_id": other_project_id},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == "VALIDATION_ERROR"


def test_promote_uses_max_sequence_not_count(client: TestClient):
    """Phase sequence is max+1, not count+1 (safe with non-dense sequences)."""
    project_id = _create_project(client, "PRJ-PROMO-013")

    # Create 3 phases with sequences 1, 2, 5 (non-dense: 3 and 4 are absent)
    for seq, name in [(1, "Phase 1"), (2, "Phase 2"), (5, "Phase 5")]:
        resp = client.post(
            "/api/v1/phases",
            json={
                "project_id": project_id,
                "name": name,
                "sequence": seq,
            },
        )
        assert resp.status_code == 201

    option = _create_promotable_option(client, project_id, name="Post-Gap Option")

    promo_resp = client.post(
        f"/api/v1/concept-options/{option['id']}/promote", json={}
    )
    assert promo_resp.status_code == 201

    # Phase should be sequence 6 (max 5 + 1), not sequence 4 (count 3 + 1)
    phase_id = promo_resp.json()["promoted_phase_id"]
    phase_resp = client.get(f"/api/v1/phases/{phase_id}")
    assert phase_resp.status_code == 200
    assert phase_resp.json()["sequence"] == 6
