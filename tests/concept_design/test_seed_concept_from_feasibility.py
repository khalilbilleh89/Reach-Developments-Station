"""
Tests for the reverse-seeding endpoint: create concept from feasibility run.

POST /api/v1/feasibility/runs/{run_id}/create-concept

Test cases:
  - concept option created from feasibility run → 201
  - source_feasibility_run_id lineage field persisted on concept
  - seed_source_type='feasibility_run' on response
  - concept name derived from run scenario_name
  - concept status is 'draft'
  - scenario_id inherited from feasibility run when set
  - project_id inherited from feasibility run when linked
  - scenario_id is None when run has no scenario
  - project_id is None when run is unlinked
  - multiple concept options can be created from the same run
  - missing feasibility run returns 404
  - no existing concept comparison logic regresses
  - GET concept-options returns concept with source_feasibility_run_id

PR-CONCEPT-064
"""

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_feasibility_run(
    client: TestClient,
    *,
    scenario_name: str = "Test Scenario",
    scenario_id: str | None = None,
    project_id: str | None = None,
) -> dict:
    payload: dict = {"scenario_name": scenario_name}
    if scenario_id is not None:
        payload["scenario_id"] = scenario_id
    if project_id is not None:
        payload["project_id"] = project_id
    resp = client.post("/api/v1/feasibility/runs", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_concept_from_run(client: TestClient, run_id: str):
    return client.post(f"/api/v1/feasibility/runs/{run_id}/create-concept")


def _create_scenario(client: TestClient, name: str = "Test Scenario") -> dict:
    resp = client.post("/api/v1/scenarios", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_project(client: TestClient, name: str = "Test Project") -> dict:
    resp = client.post("/api/v1/projects", json={"name": name, "code": "TEST-001"})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Core reverse-seeding tests
# ---------------------------------------------------------------------------

def test_create_concept_from_feasibility_run_returns_201(client: TestClient):
    """POST /feasibility/runs/{run_id}/create-concept → 201."""
    run = _create_feasibility_run(client, scenario_name="Downtown Run")
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201, resp.text


def test_create_concept_response_shape(client: TestClient):
    """Response includes all required lineage fields."""
    run = _create_feasibility_run(client, scenario_name="Urban Mix")
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert "concept_option_id" in data
    assert data["source_feasibility_run_id"] == run["id"]
    assert data["seed_source_type"] == "feasibility_run"


def test_concept_name_derived_from_scenario_name(client: TestClient):
    """New concept option name is derived from the run's scenario_name."""
    run = _create_feasibility_run(client, scenario_name="Marina Towers Base")
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201

    concept_id = resp.json()["concept_option_id"]
    get_resp = client.get(f"/api/v1/concept-options/{concept_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Concept — Marina Towers Base"


def test_concept_name_truncated_when_scenario_name_is_very_long(client: TestClient):
    """Concept name never exceeds 255 chars even when scenario_name is at the 255-char limit."""
    # scenario_name max is 255 in FeasibilityRunCreate; prepending "Concept — " (10 chars)
    # would push the derived name to 265, so truncation must kick in.
    long_name = "A" * 255
    run = _create_feasibility_run(client, scenario_name=long_name)
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201

    concept_id = resp.json()["concept_option_id"]
    get_resp = client.get(f"/api/v1/concept-options/{concept_id}")
    assert get_resp.status_code == 200
    actual_name = get_resp.json()["name"]
    assert len(actual_name) <= 255
    assert actual_name.startswith("Concept — ")


def test_concept_created_in_draft_status(client: TestClient):
    """Reverse-seeded concept option starts in 'draft' status."""
    run = _create_feasibility_run(client, scenario_name="Draft Test")
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201

    concept_id = resp.json()["concept_option_id"]
    get_resp = client.get(f"/api/v1/concept-options/{concept_id}")
    assert get_resp.json()["status"] == "draft"


def test_source_feasibility_run_id_persisted_on_concept(client: TestClient):
    """source_feasibility_run_id is stored on the concept option."""
    run = _create_feasibility_run(client, scenario_name="Lineage Test")
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201

    concept_id = resp.json()["concept_option_id"]
    get_resp = client.get(f"/api/v1/concept-options/{concept_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["source_feasibility_run_id"] == run["id"]


def test_scenario_id_inherited_from_run(client: TestClient):
    """scenario_id is inherited from the feasibility run."""
    scenario = _create_scenario(client, name="Shared Scenario")
    run = _create_feasibility_run(
        client,
        scenario_name="Scenario-linked Run",
        scenario_id=scenario["id"],
    )
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201

    data = resp.json()
    assert data["scenario_id"] == scenario["id"]

    concept_id = data["concept_option_id"]
    get_resp = client.get(f"/api/v1/concept-options/{concept_id}")
    assert get_resp.json()["scenario_id"] == scenario["id"]


def test_project_id_inherited_from_linked_run(client: TestClient):
    """project_id is inherited when the feasibility run is linked to a project."""
    project = _create_project(client, name="Dev Project")
    run = _create_feasibility_run(
        client,
        scenario_name="Project-linked Run",
        project_id=project["id"],
    )
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201

    data = resp.json()
    assert data["project_id"] == project["id"]

    concept_id = data["concept_option_id"]
    get_resp = client.get(f"/api/v1/concept-options/{concept_id}")
    assert get_resp.json()["project_id"] == project["id"]


def test_scenario_id_none_when_run_has_no_scenario(client: TestClient):
    """scenario_id is None when run has no associated scenario."""
    run = _create_feasibility_run(client, scenario_name="Unscoped Run")
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201
    assert resp.json()["scenario_id"] is None


def test_project_id_none_when_run_is_unlinked(client: TestClient):
    """project_id is None when run is not linked to a project."""
    run = _create_feasibility_run(client, scenario_name="Unlinked Run")
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201
    assert resp.json()["project_id"] is None


def test_missing_feasibility_run_returns_404(client: TestClient):
    """POST with a non-existent run_id → 404."""
    resp = _create_concept_from_run(client, "non-existent-run-id")
    assert resp.status_code == 404


def test_multiple_concepts_from_same_run(client: TestClient):
    """Multiple concept options can be reverse-seeded from the same run."""
    run = _create_feasibility_run(client, scenario_name="Multi Concept Run")
    resp1 = _create_concept_from_run(client, run["id"])
    resp2 = _create_concept_from_run(client, run["id"])
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    # Each creates a distinct concept option
    assert resp1.json()["concept_option_id"] != resp2.json()["concept_option_id"]
    # Both carry the same source lineage
    assert resp1.json()["source_feasibility_run_id"] == run["id"]
    assert resp2.json()["source_feasibility_run_id"] == run["id"]


def test_concept_option_appears_in_list(client: TestClient):
    """Reverse-seeded concept option appears in GET /concept-options."""
    run = _create_feasibility_run(client, scenario_name="Listed Run")
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201
    concept_id = resp.json()["concept_option_id"]

    list_resp = client.get("/api/v1/concept-options")
    assert list_resp.status_code == 200
    ids = [item["id"] for item in list_resp.json()["items"]]
    assert concept_id in ids


def test_reverse_seeded_concept_has_no_mix_lines(client: TestClient):
    """Reverse-seeded concept starts with no unit mix lines."""
    run = _create_feasibility_run(client, scenario_name="Empty Mix Run")
    resp = _create_concept_from_run(client, run["id"])
    assert resp.status_code == 201
    concept_id = resp.json()["concept_option_id"]

    summary_resp = client.get(f"/api/v1/concept-options/{concept_id}/summary")
    assert summary_resp.status_code == 200
    assert summary_resp.json()["unit_count"] == 0
    assert summary_resp.json()["mix_lines"] == []


def test_existing_concept_seeding_not_regressed(client: TestClient):
    """Forward seeding (concept → feasibility) still works correctly."""
    option_resp = client.post(
        "/api/v1/concept-options",
        json={"name": "Forward Seed Option", "status": "draft"},
    )
    assert option_resp.status_code == 201
    option_id = option_resp.json()["id"]

    seed_resp = client.post(
        f"/api/v1/concept-options/{option_id}/seed-feasibility",
        json={},
    )
    assert seed_resp.status_code == 201
    assert seed_resp.json()["source_concept_option_id"] == option_id
    assert seed_resp.json()["seed_source_type"] == "concept_option"
