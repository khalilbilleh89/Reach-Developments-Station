"""
Tests for the feasibility run lifecycle lineage endpoint.

GET /api/v1/feasibility/runs/{run_id}/lineage

Test cases:
  - manual run (no lineage) returns partial lineage safely
  - seeded run shows source_concept_option_id in lineage
  - run with reverse-seeded concepts shows them in the list
  - project_id appears in lineage when linked
  - multiple reverse-seeded concepts listed
  - non-existent run_id returns 404
  - full chain: concept → run → concept

PR-CONCEPT-065
"""

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _create_concept(
    client: TestClient,
    *,
    name: str = "Lineage Concept",
    status: str = "draft",
) -> dict:
    resp = client.post("/api/v1/concept-options", json={"name": name, "status": status})
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
    resp = client.post("/api/v1/projects", json={"name": name, "code": "FLP-001"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _get_lineage(client: TestClient, run_id: str):
    return client.get(f"/api/v1/feasibility/runs/{run_id}/lineage")


# ---------------------------------------------------------------------------
# Core lineage endpoint tests
# ---------------------------------------------------------------------------

def test_lineage_manual_run_no_upstream_no_downstream(client: TestClient):
    """Manual run: source_concept_option_id is None, downstream list is empty."""
    run = _create_feasibility_run(client, scenario_name="Manual Run")
    resp = _get_lineage(client, run["id"])
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["record_type"] == "feasibility_run"
    assert data["record_id"] == run["id"]
    assert data["source_concept_option_id"] is None
    assert data["reverse_seeded_concept_options"] == []


def test_lineage_response_shape(client: TestClient):
    """Lineage response includes all required fields."""
    run = _create_feasibility_run(client)
    resp = _get_lineage(client, run["id"])
    assert resp.status_code == 200
    data = resp.json()
    assert "record_type" in data
    assert "record_id" in data
    assert "source_concept_option_id" in data
    assert "reverse_seeded_concept_options" in data
    assert "project_id" in data


def test_lineage_seeded_run_shows_source_concept(client: TestClient):
    """Run seeded from a concept reports source_concept_option_id in lineage."""
    option = _create_concept(client, name="Source Concept")
    seed = _seed_feasibility(client, option["id"])
    run_id = seed["feasibility_run_id"]

    resp = _get_lineage(client, run_id)
    assert resp.status_code == 200
    assert resp.json()["source_concept_option_id"] == option["id"]


def test_lineage_run_with_reverse_seeded_concepts(client: TestClient):
    """Run that generated a concept option lists it in reverse_seeded_concept_options."""
    run = _create_feasibility_run(client, scenario_name="Seeder Run")
    seed_resp = _create_concept_from_run(client, run["id"])
    concept_id = seed_resp["concept_option_id"]

    resp = _get_lineage(client, run["id"])
    assert resp.status_code == 200
    assert concept_id in resp.json()["reverse_seeded_concept_options"]


def test_lineage_multiple_reverse_seeded_concepts(client: TestClient):
    """Multiple concept options reverse-seeded from the same run all appear."""
    run = _create_feasibility_run(client, scenario_name="Multi Seed Run")
    seed1 = _create_concept_from_run(client, run["id"])
    seed2 = _create_concept_from_run(client, run["id"])

    resp = _get_lineage(client, run["id"])
    assert resp.status_code == 200
    downstream = resp.json()["reverse_seeded_concept_options"]
    assert seed1["concept_option_id"] in downstream
    assert seed2["concept_option_id"] in downstream


def test_lineage_includes_project_id_when_linked(client: TestClient):
    """project_id appears in lineage when run is linked to a project."""
    project = _create_project(client, name="Linked Project")
    run = _create_feasibility_run(client, project_id=project["id"])

    resp = _get_lineage(client, run["id"])
    assert resp.status_code == 200
    assert resp.json()["project_id"] == project["id"]


def test_lineage_project_id_none_when_unlinked(client: TestClient):
    """project_id is None in lineage for unlinked runs."""
    run = _create_feasibility_run(client)
    resp = _get_lineage(client, run["id"])
    assert resp.status_code == 200
    assert resp.json()["project_id"] is None


def test_lineage_non_existent_run_returns_404(client: TestClient):
    """Non-existent run_id → 404."""
    resp = _get_lineage(client, "non-existent-run-id")
    assert resp.status_code == 404


def test_lineage_full_chain_concept_to_run_to_concept(client: TestClient):
    """Full lifecycle chain: concept → seeded run → reverse-seeded concept."""
    # Create original concept → seed feasibility run
    original_concept = _create_concept(client, name="Origin Concept")
    seed = _seed_feasibility(client, original_concept["id"])
    run_id = seed["feasibility_run_id"]

    # Reverse-seed a concept from the run
    reverse = _create_concept_from_run(client, run_id)

    resp = _get_lineage(client, run_id)
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_concept_option_id"] == original_concept["id"]
    assert reverse["concept_option_id"] in data["reverse_seeded_concept_options"]


def test_lineage_record_type_is_feasibility_run(client: TestClient):
    """record_type is always 'feasibility_run'."""
    run = _create_feasibility_run(client)
    resp = _get_lineage(client, run["id"])
    assert resp.json()["record_type"] == "feasibility_run"


def test_lineage_record_id_matches_queried_id(client: TestClient):
    """record_id matches the queried run ID."""
    run = _create_feasibility_run(client)
    resp = _get_lineage(client, run["id"])
    assert resp.json()["record_id"] == run["id"]
