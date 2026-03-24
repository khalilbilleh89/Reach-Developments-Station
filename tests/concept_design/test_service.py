"""
Tests for the Concept Design service comparison workflow.

Uses in-memory SQLite via the shared ``db_session`` fixture.

PR-CONCEPT-053
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str) -> str:
    resp = client.post(
        "/api/v1/projects", json={"name": f"Test Project {code}", "code": code}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_scenario(client: TestClient, project_id: str, name: str = "Scenario A") -> str:
    resp = client.post(
        "/api/v1/scenarios",
        json={"project_id": project_id, "name": name},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_option(
    client: TestClient,
    *,
    name: str,
    project_id: str | None = None,
    scenario_id: str | None = None,
    gross_floor_area: float | None = None,
    building_count: int | None = None,
    floor_count: int | None = None,
) -> dict:
    payload: dict = {"name": name, "status": "draft"}
    if project_id:
        payload["project_id"] = project_id
    if scenario_id:
        payload["scenario_id"] = scenario_id
    if gross_floor_area is not None:
        payload["gross_floor_area"] = gross_floor_area
    if building_count is not None:
        payload["building_count"] = building_count
    if floor_count is not None:
        payload["floor_count"] = floor_count
    resp = client.post("/api/v1/concept-options", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _add_mix_line(
    client: TestClient,
    option_id: str,
    unit_type: str,
    units_count: int,
    avg_sellable_area: float | None = None,
) -> None:
    payload: dict = {"unit_type": unit_type, "units_count": units_count}
    if avg_sellable_area is not None:
        payload["avg_sellable_area"] = avg_sellable_area
    resp = client.post(f"/api/v1/concept-options/{option_id}/unit-mix", json=payload)
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# compare by project_id
# ---------------------------------------------------------------------------


def test_compare_by_project_id_basic(client: TestClient):
    project_id = _create_project(client, "SVC-CMP-001")
    opt_a = _create_option(client, name="Option A", project_id=project_id, gross_floor_area=12000.0)
    opt_b = _create_option(client, name="Option B", project_id=project_id, gross_floor_area=11000.0)

    _add_mix_line(client, opt_a["id"], "1BR", 60, 75.0)
    _add_mix_line(client, opt_a["id"], "2BR", 40, 115.0)  # sellable = 9100

    _add_mix_line(client, opt_b["id"], "1BR", 50, 80.0)
    _add_mix_line(client, opt_b["id"], "2BR", 42, 120.0)  # sellable = 4000+5040 = 9040

    resp = client.get(f"/api/v1/concept-options/compare?project_id={project_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["comparison_basis"] == "project"
    assert data["option_count"] == 2
    assert len(data["rows"]) == 2
    # opt_a has higher sellable area (9100 > 9040)
    assert data["best_sellable_area_option_id"] == opt_a["id"]
    assert data["best_unit_count_option_id"] == opt_a["id"]


def test_compare_by_project_id_summary_correctness(client: TestClient):
    project_id = _create_project(client, "SVC-CMP-002")
    opt = _create_option(client, name="Single", project_id=project_id, gross_floor_area=10000.0)
    _add_mix_line(client, opt["id"], "Studio", 20, 50.0)

    resp = client.get(f"/api/v1/concept-options/compare?project_id={project_id}")
    assert resp.status_code == 200
    data = resp.json()
    row = data["rows"][0]

    assert row["unit_count"] == 20
    assert abs(row["sellable_area"] - 1000.0) < 0.01
    assert abs(row["efficiency_ratio"] - 0.1) < 0.001
    assert row["is_best_sellable_area"] is True
    assert row["is_best_unit_count"] is True
    assert row["unit_count_delta_vs_best"] == 0


# ---------------------------------------------------------------------------
# compare by scenario_id
# ---------------------------------------------------------------------------


def test_compare_by_scenario_id_basic(client: TestClient):
    project_id = _create_project(client, "SVC-CMP-003")
    scenario_id = _create_scenario(client, project_id)

    opt_a = _create_option(client, name="Scheme X", scenario_id=scenario_id, gross_floor_area=8000.0)
    opt_b = _create_option(client, name="Scheme Y", scenario_id=scenario_id, gross_floor_area=9000.0)

    _add_mix_line(client, opt_a["id"], "1BR", 40, 80.0)
    _add_mix_line(client, opt_b["id"], "1BR", 80, 80.0)

    resp = client.get(f"/api/v1/concept-options/compare?scenario_id={scenario_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["comparison_basis"] == "scenario"
    assert data["option_count"] == 2
    assert data["best_unit_count_option_id"] == opt_b["id"]


# ---------------------------------------------------------------------------
# Invalid parameter combinations → 422
# ---------------------------------------------------------------------------


def test_compare_both_params_returns_422(client: TestClient):
    project_id = _create_project(client, "SVC-CMP-004")
    resp = client.get(
        f"/api/v1/concept-options/compare?project_id={project_id}&scenario_id=some-id"
    )
    assert resp.status_code == 422


def test_compare_no_params_returns_422(client: TestClient):
    resp = client.get("/api/v1/concept-options/compare")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Zero-option result (basis exists but no options)
# ---------------------------------------------------------------------------


def test_compare_zero_options_returns_empty_result(client: TestClient):
    project_id = _create_project(client, "SVC-CMP-005")
    resp = client.get(f"/api/v1/concept-options/compare?project_id={project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["option_count"] == 0
    assert data["rows"] == []
    assert data["best_sellable_area_option_id"] is None
    assert data["best_efficiency_option_id"] is None
    assert data["best_unit_count_option_id"] is None


# ---------------------------------------------------------------------------
# Multi-option summary correctness
# ---------------------------------------------------------------------------


def test_compare_multi_option_deltas(client: TestClient):
    """Delta values should reflect difference from best option."""
    project_id = _create_project(client, "SVC-CMP-006")
    opt_a = _create_option(client, name="A", project_id=project_id, gross_floor_area=12000.0)
    opt_b = _create_option(client, name="B", project_id=project_id, gross_floor_area=12000.0)
    opt_c = _create_option(client, name="C", project_id=project_id, gross_floor_area=12000.0)

    # A: 100 units, sellable = 9100
    _add_mix_line(client, opt_a["id"], "1BR", 60, 75.0)
    _add_mix_line(client, opt_a["id"], "2BR", 40, 115.0)
    # B: 92 units, sellable = 9460
    _add_mix_line(client, opt_b["id"], "1BR", 50, 80.0)
    _add_mix_line(client, opt_b["id"], "2BR", 42, 130.0)  # 50*80 + 42*130 = 4000 + 5460 = 9460
    # C: 84 units, sellable ~8500
    _add_mix_line(client, opt_c["id"], "1BR", 84, 101.19)  # ~8500

    resp = client.get(f"/api/v1/concept-options/compare?project_id={project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["option_count"] == 3

    rows_by_name = {r["name"]: r for r in data["rows"]}

    # Best sellable should be B (9460)
    best_id = data["best_sellable_area_option_id"]
    assert best_id == opt_b["id"]

    # delta for B should be 0
    assert abs(rows_by_name["B"]["sellable_area_delta_vs_best"]) < 0.01
    # delta for A and C should be negative
    assert rows_by_name["A"]["sellable_area_delta_vs_best"] < 0
    assert rows_by_name["C"]["sellable_area_delta_vs_best"] < 0
