"""
Tests for the feasibility construction cost context endpoint (PR-V6-10).

Validates:
  - 404 on missing feasibility run
  - run with no linked project → safe null response with explanatory note
  - run linked to project with no cost records → safe null response
  - run linked to project with cost records but no assumptions → partial response
  - run with both cost records and assumptions → variance fields populated correctly
  - variance is recorded − assumed (transparent arithmetic only)
  - no mutation of feasibility or construction records
"""

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_ASSUMPTIONS = {
    "sellable_area_sqm": 1000.0,
    "avg_sale_price_per_sqm": 3000.0,
    "construction_cost_per_sqm": 800.0,
    "soft_cost_ratio": 0.10,
    "finance_cost_ratio": 0.05,
    "sales_cost_ratio": 0.03,
    "development_period_months": 24,
}


def _create_project(client: TestClient, code: str) -> str:
    resp = client.post("/api/v1/projects", json={"name": "Test Project", "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_run(client: TestClient, project_id: str | None = None) -> str:
    payload: dict = {"scenario_name": "Test Run"}
    if project_id:
        payload["project_id"] = project_id
    resp = client.post("/api/v1/feasibility/runs", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _add_assumptions(client: TestClient, run_id: str, overrides: dict | None = None) -> None:
    payload = dict(_VALID_ASSUMPTIONS)
    if overrides:
        payload.update(overrides)
    resp = client.post(f"/api/v1/feasibility/runs/{run_id}/assumptions", json=payload)
    assert resp.status_code == 201, resp.text


def _create_cost_record(
    client: TestClient,
    project_id: str,
    amount: float = 500_000.0,
    title: str = "Site Clearance",
) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json={
            "title": title,
            "cost_category": "hard_cost",
            "cost_source": "estimate",
            "cost_stage": "construction",
            "amount": amount,
            "currency": "AED",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


_ENDPOINT = "/api/v1/feasibility/runs/{run_id}/construction-cost-context"


# ---------------------------------------------------------------------------
# 404 behaviour
# ---------------------------------------------------------------------------


def test_missing_run_returns_404(client: TestClient) -> None:
    resp = client.get(_ENDPOINT.format(run_id="nonexistent-run"))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# No linked project
# ---------------------------------------------------------------------------


def test_no_linked_project_returns_safe_response(client: TestClient) -> None:
    run_id = _create_run(client)

    resp = client.get(_ENDPOINT.format(run_id=run_id))
    assert resp.status_code == 200

    data = resp.json()
    assert data["feasibility_run_id"] == run_id
    assert data["project_id"] is None
    assert data["has_cost_records"] is False
    assert data["active_record_count"] == 0
    assert data["recorded_construction_cost_total"] is None
    assert data["by_category"] is None
    assert data["by_stage"] is None
    assert data["assumed_construction_cost"] is None
    assert data["variance_amount"] is None
    assert data["variance_pct"] is None
    assert "note" in data
    assert len(data["note"]) > 0


# ---------------------------------------------------------------------------
# Project with no cost records
# ---------------------------------------------------------------------------


def test_project_with_no_cost_records_returns_safe_response(client: TestClient) -> None:
    project_id = _create_project(client, "PRJ-NOCC")
    run_id = _create_run(client, project_id=project_id)
    _add_assumptions(client, run_id)

    resp = client.get(_ENDPOINT.format(run_id=run_id))
    assert resp.status_code == 200

    data = resp.json()
    assert data["project_id"] == project_id
    assert data["has_cost_records"] is False
    assert data["active_record_count"] == 0
    assert data["recorded_construction_cost_total"] is None
    assert data["by_category"] is None
    assert data["by_stage"] is None
    # Assumed cost is available from assumptions
    assert data["assumed_construction_cost"] == pytest.approx(
        _VALID_ASSUMPTIONS["construction_cost_per_sqm"] * _VALID_ASSUMPTIONS["sellable_area_sqm"]
    )
    # No recorded side → variance is null
    assert data["variance_amount"] is None
    assert data["variance_pct"] is None
    assert "note" in data


# ---------------------------------------------------------------------------
# Cost records exist but no assumptions
# ---------------------------------------------------------------------------


def test_cost_records_without_assumptions_returns_partial_response(client: TestClient) -> None:
    project_id = _create_project(client, "PRJ-CRNOA")
    run_id = _create_run(client, project_id=project_id)
    _create_cost_record(client, project_id, amount=750_000.0)

    # No assumptions added
    resp = client.get(_ENDPOINT.format(run_id=run_id))
    assert resp.status_code == 200

    data = resp.json()
    assert data["project_id"] == project_id
    assert data["has_cost_records"] is True
    assert data["active_record_count"] == 1
    assert float(data["recorded_construction_cost_total"]) == pytest.approx(750_000.0)
    assert data["assumed_construction_cost"] is None
    assert data["variance_amount"] is None
    assert data["variance_pct"] is None
    assert "note" in data


# ---------------------------------------------------------------------------
# Both sides present — variance fields populated correctly
# ---------------------------------------------------------------------------


def test_both_sides_present_variance_correct(client: TestClient) -> None:
    """
    assumptions: construction_cost_per_sqm=800, sellable_area_sqm=1000
    → assumed_construction_cost = 800_000

    recorded: 900_000
    → variance_amount = 900_000 − 800_000 = 100_000
    → variance_pct = 100_000 / 800_000 = 0.125
    """
    project_id = _create_project(client, "PRJ-BOTH")
    run_id = _create_run(client, project_id=project_id)
    _add_assumptions(
        client,
        run_id,
        overrides={"construction_cost_per_sqm": 800.0, "sellable_area_sqm": 1000.0},
    )
    _create_cost_record(client, project_id, amount=900_000.0)

    resp = client.get(_ENDPOINT.format(run_id=run_id))
    assert resp.status_code == 200

    data = resp.json()
    assert data["has_cost_records"] is True
    assert data["active_record_count"] == 1
    assert float(data["recorded_construction_cost_total"]) == pytest.approx(900_000.0)
    assert data["assumed_construction_cost"] == pytest.approx(800_000.0)
    assert float(data["variance_amount"]) == pytest.approx(100_000.0)
    assert data["variance_pct"] == pytest.approx(0.125)
    assert "note" in data


def test_both_sides_present_negative_variance(client: TestClient) -> None:
    """Variance is negative when recorded < assumed."""
    project_id = _create_project(client, "PRJ-NEGVAR")
    run_id = _create_run(client, project_id=project_id)
    _add_assumptions(
        client,
        run_id,
        overrides={"construction_cost_per_sqm": 1000.0, "sellable_area_sqm": 1000.0},
    )
    _create_cost_record(client, project_id, amount=600_000.0)

    resp = client.get(_ENDPOINT.format(run_id=run_id))
    assert resp.status_code == 200

    data = resp.json()
    assert float(data["variance_amount"]) == pytest.approx(-400_000.0)
    assert data["variance_pct"] == pytest.approx(-0.40)


def test_multiple_cost_records_sum_correctly(client: TestClient) -> None:
    """grand_total sums all active records."""
    project_id = _create_project(client, "PRJ-MULTI")
    run_id = _create_run(client, project_id=project_id)
    _add_assumptions(
        client,
        run_id,
        overrides={"construction_cost_per_sqm": 500.0, "sellable_area_sqm": 2000.0},
    )
    _create_cost_record(client, project_id, amount=400_000.0, title="Foundation")
    _create_cost_record(client, project_id, amount=300_000.0, title="Structure")
    _create_cost_record(client, project_id, amount=300_000.0, title="Finishing")

    resp = client.get(_ENDPOINT.format(run_id=run_id))
    assert resp.status_code == 200

    data = resp.json()
    # 400k + 300k + 300k = 1_000_000 recorded
    assert float(data["recorded_construction_cost_total"]) == pytest.approx(1_000_000.0)
    # assumed = 500 * 2000 = 1_000_000
    assert data["assumed_construction_cost"] == pytest.approx(1_000_000.0)
    assert float(data["variance_amount"]) == pytest.approx(0.0)


def test_archived_records_excluded_from_total(client: TestClient) -> None:
    """Only active cost records are included in the recorded total."""
    project_id = _create_project(client, "PRJ-ARCH")
    run_id = _create_run(client, project_id=project_id)
    _add_assumptions(client, run_id)

    active_record = _create_cost_record(client, project_id, amount=500_000.0, title="Active")
    archived_record = _create_cost_record(client, project_id, amount=200_000.0, title="Archived")

    # Archive the second record
    client.post(f"/api/v1/construction-cost-records/{archived_record['id']}/archive")

    resp = client.get(_ENDPOINT.format(run_id=run_id))
    assert resp.status_code == 200

    data = resp.json()
    # Only the active record should contribute
    assert data["active_record_count"] == 1
    assert float(data["recorded_construction_cost_total"]) == pytest.approx(500_000.0)


# ---------------------------------------------------------------------------
# No source record mutation
# ---------------------------------------------------------------------------


def test_endpoint_does_not_mutate_feasibility_run(client: TestClient) -> None:
    project_id = _create_project(client, "PRJ-NOMUT")
    run_id = _create_run(client, project_id=project_id)
    _add_assumptions(client, run_id)
    _create_cost_record(client, project_id, amount=800_000.0)

    # Capture pre-call state
    run_before = client.get(f"/api/v1/feasibility/runs/{run_id}").json()
    assumptions_before = client.get(f"/api/v1/feasibility/runs/{run_id}/assumptions").json()

    # Call context endpoint
    client.get(_ENDPOINT.format(run_id=run_id))

    # Verify run and assumptions are unchanged
    run_after = client.get(f"/api/v1/feasibility/runs/{run_id}").json()
    assumptions_after = client.get(f"/api/v1/feasibility/runs/{run_id}/assumptions").json()

    assert run_before["updated_at"] == run_after["updated_at"]
    assert assumptions_before["updated_at"] == assumptions_after["updated_at"]


def test_endpoint_does_not_mutate_construction_cost_records(client: TestClient) -> None:
    project_id = _create_project(client, "PRJ-NOMUT2")
    run_id = _create_run(client, project_id=project_id)
    record = _create_cost_record(client, project_id, amount=600_000.0)
    record_id = record["id"]

    # Call context endpoint
    client.get(_ENDPOINT.format(run_id=run_id))

    # Verify cost record is unchanged
    record_after = client.get(f"/api/v1/construction-cost-records/{record_id}").json()
    assert float(record_after["amount"]) == pytest.approx(600_000.0)
    assert record_after["is_active"] is True


# ---------------------------------------------------------------------------
# Response contract shape
# ---------------------------------------------------------------------------


def test_response_contract_shape(client: TestClient) -> None:
    project_id = _create_project(client, "PRJ-SHAPE")
    run_id = _create_run(client, project_id=project_id)
    _add_assumptions(client, run_id)
    _create_cost_record(client, project_id, amount=800_000.0)

    resp = client.get(_ENDPOINT.format(run_id=run_id))
    assert resp.status_code == 200

    data = resp.json()
    required_keys = {
        "feasibility_run_id",
        "project_id",
        "has_cost_records",
        "active_record_count",
        "recorded_construction_cost_total",
        "by_category",
        "by_stage",
        "assumed_construction_cost",
        "variance_amount",
        "variance_pct",
        "note",
    }
    assert required_keys.issubset(data.keys())


def test_grouped_totals_match_grand_total(client: TestClient) -> None:
    """by_category values should sum to the grand_total."""
    project_id = _create_project(client, "PRJ-GRP")
    run_id = _create_run(client, project_id=project_id)
    _create_cost_record(
        client, project_id, amount=400_000.0, title="Hard 1"
    )  # hard_cost by default
    # Add a soft_cost record
    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json={
            "title": "Soft Cost Item",
            "cost_category": "soft_cost",
            "cost_source": "estimate",
            "cost_stage": "design",
            "amount": 100_000.0,
            "currency": "AED",
        },
    )
    assert resp.status_code == 201

    resp = client.get(_ENDPOINT.format(run_id=run_id))
    assert resp.status_code == 200

    data = resp.json()
    assert data["has_cost_records"] is True
    by_category = data["by_category"]
    assert by_category is not None
    category_sum = sum(float(v) for v in by_category.values())
    assert category_sum == pytest.approx(float(data["recorded_construction_cost_total"]))
