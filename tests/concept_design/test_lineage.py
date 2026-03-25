"""
Tests for the concept option lifecycle lineage endpoint.

GET /api/v1/concept-options/{id}/lineage

Test cases:
  - manual concept (no lineage) returns partial lineage safely
  - reverse-seeded concept shows source_feasibility_run_id in lineage
  - concept with seeded feasibility runs shows them in downstream list
  - project_id and scenario_id appear in lineage when set
  - multiple downstream feasibility runs listed
  - non-existent concept_option_id returns 404
  - lineage for concept with both upstream and downstream populated

PR-CONCEPT-065
"""

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_concept(
    client: TestClient,
    *,
    name: str = "Lineage Option",
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
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_feasibility_run(
    client: TestClient,
    *,
    scenario_name: str = "Lineage Run",
    project_id: str | None = None,
    scenario_id: str | None = None,
) -> dict:
    payload: dict = {"scenario_name": scenario_name}
    if project_id is not None:
        payload["project_id"] = project_id
    if scenario_id is not None:
        payload["scenario_id"] = scenario_id
    resp = client.post("/api/v1/feasibility/runs", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _seed_feasibility(client: TestClient, concept_id: str) -> dict:
    resp = client.post(
        f"/api/v1/concept-options/{concept_id}/seed-feasibility",
        json={},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_concept_from_run(client: TestClient, run_id: str) -> dict:
    resp = client.post(f"/api/v1/feasibility/runs/{run_id}/create-concept")
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_project(client: TestClient, name: str = "Test Project") -> dict:
    resp = client.post("/api/v1/projects", json={"name": name, "code": "LP-001"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_scenario(client: TestClient, name: str = "Test Scenario") -> dict:
    resp = client.post("/api/v1/scenarios", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _get_lineage(client: TestClient, concept_id: str):
    return client.get(f"/api/v1/concept-options/{concept_id}/lineage")


# ---------------------------------------------------------------------------
# Core lineage endpoint tests
# ---------------------------------------------------------------------------

def test_lineage_manual_concept_no_upstream_no_downstream(client: TestClient):
    """Manual concept: source_feasibility_run_id is None, downstream list is empty."""
    option = _create_concept(client, name="Manual Concept")
    resp = _get_lineage(client, option["id"])
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["record_type"] == "concept_option"
    assert data["record_id"] == option["id"]
    assert data["source_feasibility_run_id"] is None
    assert data["downstream_feasibility_runs"] == []


def test_lineage_response_shape(client: TestClient):
    """Lineage response includes all required fields."""
    option = _create_concept(client)
    resp = _get_lineage(client, option["id"])
    assert resp.status_code == 200
    data = resp.json()
    assert "record_type" in data
    assert "record_id" in data
    assert "source_feasibility_run_id" in data
    assert "downstream_feasibility_runs" in data
    assert "scenario_id" in data
    assert "project_id" in data


def test_lineage_reverse_seeded_concept_shows_source_run(client: TestClient):
    """Reverse-seeded concept reports source_feasibility_run_id in lineage."""
    run = _create_feasibility_run(client, scenario_name="Source Run")
    seed_resp = _create_concept_from_run(client, run["id"])
    concept_id = seed_resp["concept_option_id"]

    resp = _get_lineage(client, concept_id)
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_feasibility_run_id"] == run["id"]


def test_lineage_concept_with_downstream_feasibility_runs(client: TestClient):
    """Concept that seeded a feasibility run lists it in downstream_feasibility_runs."""
    option = _create_concept(client, name="Seeder Concept")
    seed = _seed_feasibility(client, option["id"])

    resp = _get_lineage(client, option["id"])
    assert resp.status_code == 200
    data = resp.json()
    assert seed["feasibility_run_id"] in data["downstream_feasibility_runs"]


def test_lineage_multiple_downstream_runs(client: TestClient):
    """Multiple feasibility runs seeded from the same concept all appear."""
    option = _create_concept(client, name="Multi-Seed Concept")
    seed1 = _seed_feasibility(client, option["id"])
    seed2 = _seed_feasibility(client, option["id"])

    resp = _get_lineage(client, option["id"])
    assert resp.status_code == 200
    downstream = resp.json()["downstream_feasibility_runs"]
    assert seed1["feasibility_run_id"] in downstream
    assert seed2["feasibility_run_id"] in downstream


def test_lineage_includes_scenario_id_when_set(client: TestClient):
    """scenario_id appears in lineage when the concept option is scenario-linked."""
    scenario = _create_scenario(client, name="Shared Scenario")
    option = _create_concept(client, scenario_id=scenario["id"])

    resp = _get_lineage(client, option["id"])
    assert resp.status_code == 200
    assert resp.json()["scenario_id"] == scenario["id"]


def test_lineage_includes_project_id_when_set(client: TestClient):
    """project_id appears in lineage when the concept option is project-linked."""
    project = _create_project(client, name="Dev Project")
    option = _create_concept(client, project_id=project["id"])

    resp = _get_lineage(client, option["id"])
    assert resp.status_code == 200
    assert resp.json()["project_id"] == project["id"]


def test_lineage_scenario_id_none_when_unlinked(client: TestClient):
    """scenario_id is None in lineage for concept options not linked to a scenario."""
    option = _create_concept(client)
    resp = _get_lineage(client, option["id"])
    assert resp.status_code == 200
    assert resp.json()["scenario_id"] is None


def test_lineage_project_id_none_when_unlinked(client: TestClient):
    """project_id is None in lineage for concept options not linked to a project."""
    option = _create_concept(client)
    resp = _get_lineage(client, option["id"])
    assert resp.status_code == 200
    assert resp.json()["project_id"] is None


def test_lineage_non_existent_concept_returns_404(client: TestClient):
    """Non-existent concept_option_id → 404."""
    resp = _get_lineage(client, "non-existent-concept-id")
    assert resp.status_code == 404


def test_lineage_full_chain_upstream_and_downstream(client: TestClient):
    """Concept with both upstream source and downstream children shows complete chain."""
    # Create original run → seed concept → seed another feasibility run
    upstream_run = _create_feasibility_run(client, scenario_name="Upstream Run")
    seed_resp = _create_concept_from_run(client, upstream_run["id"])
    concept_id = seed_resp["concept_option_id"]

    # Seed a downstream feasibility run from the concept
    downstream_seed = _seed_feasibility(client, concept_id)

    resp = _get_lineage(client, concept_id)
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_feasibility_run_id"] == upstream_run["id"]
    assert downstream_seed["feasibility_run_id"] in data["downstream_feasibility_runs"]


def test_lineage_record_type_is_concept_option(client: TestClient):
    """record_type is always 'concept_option'."""
    option = _create_concept(client)
    resp = _get_lineage(client, option["id"])
    assert resp.json()["record_type"] == "concept_option"


def test_lineage_record_id_matches_queried_id(client: TestClient):
    """record_id matches the queried concept option ID."""
    option = _create_concept(client)
    resp = _get_lineage(client, option["id"])
    assert resp.json()["record_id"] == option["id"]
