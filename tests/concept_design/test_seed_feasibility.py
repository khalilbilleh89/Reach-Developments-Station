"""
Tests for the seed-feasibility endpoint.

POST /api/v1/concept-options/{id}/seed-feasibility

Test cases:
  - seed from draft concept with mix lines → 201, run created with lineage
  - seed from active concept with mix lines → 201, run created
  - scenario_name defaults to 'Feasibility — <option name>'
  - scenario_name overridden by request → stored on run
  - sellable_area seeded from mix lines
  - seeded_unit_count matches mix lines
  - assumptions_seeded=True when mix lines have sellable area
  - concept with no mix lines → run created, assumptions_seeded=False
  - concept with mix lines but no avg_sellable_area → run created, assumptions_seeded=False
  - archived concept → 422
  - not found concept → 404
  - feasibility run carries source_concept_option_id lineage field
  - feasibility run carries seed_source_type='concept_option'
  - scenario_id inherited from concept option

PR-CONCEPT-063
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_project(client: TestClient, code: str = "PRJ-SEED01") -> str:
    resp = client.post(
        "/api/v1/projects", json={"name": f"Seed Feasibility Project {code}", "code": code}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_option(
    client: TestClient,
    *,
    name: str = "Seed Option",
    status: str = "draft",
    project_id: str | None = None,
    scenario_id: str | None = None,
) -> dict:
    payload: dict = {"name": name, "status": status}
    if project_id is not None:
        payload["project_id"] = project_id
    if scenario_id is not None:
        payload["scenario_id"] = scenario_id
    resp = client.post("/api/v1/concept-options", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _add_mix_line(
    client: TestClient,
    option_id: str,
    unit_type: str = "studio",
    units_count: int = 10,
    avg_sellable_area: float | None = 45.0,
) -> dict:
    payload: dict = {
        "unit_type": unit_type,
        "units_count": units_count,
        "mix_percentage": 100.0,
    }
    if avg_sellable_area is not None:
        payload["avg_sellable_area"] = avg_sellable_area
    resp = client.post(f"/api/v1/concept-options/{option_id}/unit-mix", json=payload)
    assert resp.status_code == 201
    return resp.json()


_VALID_SEED_PAYLOAD = {
    "avg_sale_price_per_sqm": 5000.0,
    "construction_cost_per_sqm": 1200.0,
    "soft_cost_ratio": 0.10,
    "finance_cost_ratio": 0.05,
    "sales_cost_ratio": 0.03,
    "development_period_months": 24,
}


def _seed(client: TestClient, option_id: str, payload: dict | None = None) -> dict:
    body = dict(_VALID_SEED_PAYLOAD)
    if payload:
        body.update(payload)
    resp = client.post(f"/api/v1/concept-options/{option_id}/seed-feasibility", json=body)
    return resp


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_seed_from_draft_concept(client: TestClient):
    """POST seed-feasibility from draft concept → 201 with run created."""
    option = _create_option(client, name="Draft Seed Option")
    _add_mix_line(client, option["id"])

    resp = _seed(client, option["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert "feasibility_run_id" in data
    assert data["source_concept_option_id"] == option["id"]
    assert data["seed_source_type"] == "concept_option"


def test_seed_from_active_concept(client: TestClient):
    """POST seed-feasibility from active concept → 201."""
    option = _create_option(client, name="Active Seed Option", status="active")
    _add_mix_line(client, option["id"], units_count=5, avg_sellable_area=80.0)

    resp = _seed(client, option["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["seed_source_type"] == "concept_option"


def test_seed_default_scenario_name(client: TestClient):
    """Scenario name defaults to 'Feasibility — <option name>' when not supplied."""
    option = _create_option(client, name="My Concept")
    _add_mix_line(client, option["id"])

    resp = _seed(client, option["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["scenario_name"] == "Feasibility — My Concept"


def test_seed_custom_scenario_name(client: TestClient):
    """Custom scenario_name in request is used instead of generated default."""
    option = _create_option(client, name="Custom Name Concept")
    _add_mix_line(client, option["id"])

    resp = _seed(client, option["id"], {"scenario_name": "Q2 2026 Feasibility"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["scenario_name"] == "Q2 2026 Feasibility"


def test_seed_sellable_area_transferred(client: TestClient):
    """sellable_area from mix lines is transferred as seeded_sellable_area_sqm."""
    option = _create_option(client, name="Area Transfer Option")
    # 10 units × 50 sqm = 500 sqm sellable
    _add_mix_line(client, option["id"], units_count=10, avg_sellable_area=50.0)

    resp = _seed(client, option["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["seeded_sellable_area_sqm"] == pytest.approx(500.0)
    assert data["assumptions_seeded"] is True


def test_seed_unit_count_transferred(client: TestClient):
    """seeded_unit_count matches total units from mix lines."""
    option = _create_option(client, name="Unit Count Option")
    _add_mix_line(client, option["id"], unit_type="studio", units_count=8, avg_sellable_area=40.0)
    _add_mix_line(client, option["id"], unit_type="1br", units_count=4, avg_sellable_area=65.0)

    resp = _seed(client, option["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["seeded_unit_count"] == 12


def test_seed_multiple_mix_lines_area(client: TestClient):
    """sellable_area is summed correctly across multiple mix lines."""
    option = _create_option(client, name="Multi-Mix Option")
    # 5 × 40 = 200
    _add_mix_line(client, option["id"], unit_type="studio", units_count=5, avg_sellable_area=40.0)
    # 3 × 70 = 210
    _add_mix_line(client, option["id"], unit_type="1br", units_count=3, avg_sellable_area=70.0)

    resp = _seed(client, option["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["seeded_sellable_area_sqm"] == pytest.approx(410.0)
    assert data["seeded_unit_count"] == 8


def test_seed_no_mix_lines_assumptions_not_seeded(client: TestClient):
    """Concept with no mix lines: run created, assumptions_seeded=False."""
    option = _create_option(client, name="No Mix Option")

    resp = _seed(client, option["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["seeded_sellable_area_sqm"] is None
    assert data["seeded_unit_count"] == 0
    assert data["assumptions_seeded"] is False


def test_seed_mix_lines_without_sellable_area_not_seeded(client: TestClient):
    """Mix lines with no avg_sellable_area: assumptions_seeded=False."""
    option = _create_option(client, name="No Area Option")
    _add_mix_line(client, option["id"], units_count=5, avg_sellable_area=None)

    resp = _seed(client, option["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["seeded_sellable_area_sqm"] is None
    assert data["assumptions_seeded"] is False


def test_seed_lineage_fields_on_feasibility_run(client: TestClient):
    """Feasibility run returned via GET carries source_concept_option_id lineage."""
    option = _create_option(client, name="Lineage Option")
    _add_mix_line(client, option["id"])

    seed_resp = _seed(client, option["id"])
    assert seed_resp.status_code == 201
    run_id = seed_resp.json()["feasibility_run_id"]

    run_resp = client.get(f"/api/v1/feasibility/runs/{run_id}")
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert run_data["source_concept_option_id"] == option["id"]
    assert run_data["seed_source_type"] == "concept_option"


def test_seed_inherits_scenario_id(client: TestClient):
    """Feasibility run inherits scenario_id from concept option."""
    # Create a scenario first
    scenario_resp = client.post(
        "/api/v1/scenarios",
        json={"name": "Test Scenario", "description": "For seeding test"},
    )
    assert scenario_resp.status_code == 201
    scenario_id = scenario_resp.json()["id"]

    option = _create_option(client, name="Scenario Option", scenario_id=scenario_id)
    _add_mix_line(client, option["id"])

    seed_resp = _seed(client, option["id"])
    assert seed_resp.status_code == 201
    data = seed_resp.json()
    assert data["scenario_id"] == scenario_id

    # Also verify the run record has the scenario_id
    run_resp = client.get(f"/api/v1/feasibility/runs/{data['feasibility_run_id']}")
    assert run_resp.status_code == 200
    assert run_resp.json()["scenario_id"] == scenario_id


def test_seed_no_scenario_id_when_concept_has_none(client: TestClient):
    """Feasibility run has scenario_id=None when concept option has no scenario."""
    option = _create_option(client, name="No Scenario Option")
    _add_mix_line(client, option["id"])

    seed_resp = _seed(client, option["id"])
    assert seed_resp.status_code == 201
    data = seed_resp.json()
    assert data["scenario_id"] is None


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------

def test_seed_archived_concept_rejected(client: TestClient):
    """POST seed-feasibility on archived concept → 422."""
    option = _create_option(client, name="Archived Seed Option", status="archived")

    resp = _seed(client, option["id"])
    assert resp.status_code == 422


def test_seed_not_found_concept(client: TestClient):
    """POST seed-feasibility with non-existent concept_option_id → 404."""
    resp = _seed(client, "non-existent-concept-id")
    assert resp.status_code == 404


def test_seed_missing_required_field(client: TestClient):
    """POST seed-feasibility without required avg_sale_price_per_sqm → 422."""
    option = _create_option(client, name="Missing Field Option")
    _add_mix_line(client, option["id"])

    incomplete = {k: v for k, v in _VALID_SEED_PAYLOAD.items() if k != "avg_sale_price_per_sqm"}
    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/seed-feasibility", json=incomplete
    )
    assert resp.status_code == 422


def test_seed_default_cost_ratios_applied(client: TestClient):
    """Default cost ratios are accepted when not provided by caller."""
    option = _create_option(client, name="Default Ratios Option")
    _add_mix_line(client, option["id"])

    # Provide only required fields, let defaults handle the ratios
    minimal = {
        "avg_sale_price_per_sqm": 4000.0,
        "construction_cost_per_sqm": 1000.0,
        "development_period_months": 18,
    }
    resp = client.post(
        f"/api/v1/concept-options/{option['id']}/seed-feasibility", json=minimal
    )
    assert resp.status_code == 201


def test_seed_creates_distinct_run_each_call(client: TestClient):
    """Calling seed-feasibility twice creates two distinct feasibility runs."""
    option = _create_option(client, name="Multi Seed Option")
    _add_mix_line(client, option["id"])

    resp1 = _seed(client, option["id"])
    resp2 = _seed(client, option["id"])

    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["feasibility_run_id"] != resp2.json()["feasibility_run_id"]
