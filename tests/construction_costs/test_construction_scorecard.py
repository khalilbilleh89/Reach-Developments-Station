"""Tests for Construction Analytics & Project Scorecard (PR-V6-14).

Validates:
  - project with approved baseline returns scorecard successfully
  - project without approved baseline returns clean incomplete-state payload
  - cost variance amount is computed correctly
  - cost variance percent is computed correctly
  - contingency pressure is computed correctly
  - cost/contingency status classification: healthy / warning / critical paths
  - overall health status is derived deterministically
  - missing data paths do not crash scorecard generation
  - project scorecard endpoint returns expected payload
  - portfolio scorecard endpoint returns aggregate summary correctly
  - unauthorized users are blocked appropriately
  - incomplete-state response is stable and explicit
  - scorecard responses remain deterministic across repeated calls
  - portfolio counts by health status are correct
  - projects missing approved baseline are surfaced correctly
  - 404 is returned for unknown project
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str, name: str = "Test Project") -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_cost_record(
    client: TestClient,
    project_id: str,
    amount: float,
    cost_category: str = "hard_cost",
    is_active: bool = True,
) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json={
            "title": f"Cost {amount}",
            "amount": amount,
            "cost_category": cost_category,
            "cost_source": "contract",
            "cost_stage": "construction",
            "is_active": is_active,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_comparison_set(
    client: TestClient,
    project_id: str,
    title: str = "Baseline vs Tender",
) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/tender-comparisons",
        json={
            "title": title,
            "comparison_stage": "baseline_vs_tender",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_comparison_line(
    client: TestClient,
    set_id: str,
    baseline_amount: float,
    comparison_amount: float,
) -> dict:
    resp = client.post(
        f"/api/v1/tender-comparisons/{set_id}/lines",
        json={
            "cost_category": "hard_cost",
            "baseline_amount": baseline_amount,
            "comparison_amount": comparison_amount,
            "variance_reason": "other",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _approve_baseline(client: TestClient, set_id: str) -> dict:
    resp = client.post(
        f"/api/v1/tender-comparisons/{set_id}/approve-baseline"
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Scorecard: no approved baseline (incomplete state)
# ---------------------------------------------------------------------------


def test_scorecard_no_baseline_returns_incomplete_state(client: TestClient) -> None:
    """Project with no approved baseline must return has_approved_baseline=False
    and overall_health_status='incomplete'."""
    project_id = _create_project(client, "SC01", "Scorecard No Baseline")

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["project_id"] == project_id
    assert data["has_approved_baseline"] is False
    assert data["approved_baseline_set_id"] is None
    assert data["approved_baseline_amount"] is None
    assert data["approved_at"] is None
    assert data["cost_variance_amount"] is None
    assert data["cost_variance_pct"] is None
    assert data["cost_status"] == "incomplete"
    assert data["contingency_status"] == "incomplete"
    assert data["overall_health_status"] == "incomplete"


def test_scorecard_incomplete_state_with_cost_records(client: TestClient) -> None:
    """Incomplete state remains stable even when cost records exist."""
    project_id = _create_project(client, "SC02", "No Baseline With Records")
    _create_cost_record(client, project_id, 500_000)

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["has_approved_baseline"] is False
    assert data["overall_health_status"] == "incomplete"
    # Current forecast should still be computed
    assert float(data["current_forecast_amount"]) == pytest.approx(500_000.0)


# ---------------------------------------------------------------------------
# Scorecard: with approved baseline
# ---------------------------------------------------------------------------


def test_scorecard_with_approved_baseline(client: TestClient) -> None:
    """Project with an approved baseline returns has_approved_baseline=True."""
    project_id = _create_project(client, "SC03", "Scorecard With Baseline")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 1_000_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["has_approved_baseline"] is True
    assert data["approved_baseline_set_id"] == comparison_set["id"]
    assert data["approved_at"] is not None
    assert float(data["approved_baseline_amount"]) == pytest.approx(1_000_000.0)


# ---------------------------------------------------------------------------
# Cost variance amount is computed correctly
# ---------------------------------------------------------------------------


def test_scorecard_cost_variance_amount_correct(client: TestClient) -> None:
    """cost_variance_amount = current_forecast - approved_baseline."""
    project_id = _create_project(client, "SC04", "Variance Amount")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 800_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])
    _create_cost_record(client, project_id, 1_200_000)

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # baseline = comparison_amount in the lines = 1,000,000
    # forecast = 1,200,000
    # variance = 200,000
    assert float(data["approved_baseline_amount"]) == pytest.approx(1_000_000.0)
    assert float(data["current_forecast_amount"]) == pytest.approx(1_200_000.0)
    assert float(data["cost_variance_amount"]) == pytest.approx(200_000.0)


# ---------------------------------------------------------------------------
# Cost variance percent is computed correctly
# ---------------------------------------------------------------------------


def test_scorecard_cost_variance_pct_correct(client: TestClient) -> None:
    """cost_variance_pct = (variance / baseline) * 100."""
    project_id = _create_project(client, "SC05", "Variance Pct")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 800_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])
    _create_cost_record(client, project_id, 1_200_000)

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # variance_pct = 200_000 / 1_000_000 * 100 = 20.0
    assert float(data["cost_variance_pct"]) == pytest.approx(20.0)


def test_scorecard_cost_variance_pct_none_when_baseline_zero(client: TestClient) -> None:
    """cost_variance_pct must be None when approved_baseline_amount is 0."""
    project_id = _create_project(client, "SC06", "Zero Baseline")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 0, 0)
    _approve_baseline(client, comparison_set["id"])

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["cost_variance_pct"] is None


# ---------------------------------------------------------------------------
# Contingency pressure is computed correctly
# ---------------------------------------------------------------------------


def test_scorecard_contingency_pressure_correct(client: TestClient) -> None:
    """contingency_pressure_pct = contingency_amount / baseline * 100."""
    project_id = _create_project(client, "SC07", "Contingency Pressure")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 800_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])

    _create_cost_record(client, project_id, 900_000, cost_category="hard_cost")
    _create_cost_record(client, project_id, 100_000, cost_category="contingency")

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert float(data["contingency_amount"]) == pytest.approx(100_000.0)
    # contingency_pressure_pct = 100_000 / 1_000_000 * 100 = 10.0
    assert float(data["contingency_pressure_pct"]) == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Status classification
# ---------------------------------------------------------------------------


def test_scorecard_healthy_when_variance_under_threshold(client: TestClient) -> None:
    """cost_status == 'healthy' when cost_variance_pct <= 5 %."""
    project_id = _create_project(client, "SC08", "Healthy Variance")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 800_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])
    _create_cost_record(client, project_id, 1_040_000)  # 4 % overrun

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["cost_status"] == "healthy"
    assert data["overall_health_status"] == "healthy"


def test_scorecard_warning_when_variance_in_warning_band(client: TestClient) -> None:
    """cost_status == 'warning' when 5% < cost_variance_pct <= 15%."""
    project_id = _create_project(client, "SC09", "Warning Variance")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 800_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])
    _create_cost_record(client, project_id, 1_100_000)  # 10 % overrun

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["cost_status"] == "warning"
    assert data["overall_health_status"] == "warning"


def test_scorecard_critical_when_variance_above_critical_threshold(
    client: TestClient,
) -> None:
    """cost_status == 'critical' when cost_variance_pct > 15%."""
    project_id = _create_project(client, "SC10", "Critical Variance")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 800_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])
    _create_cost_record(client, project_id, 1_200_000)  # 20 % overrun

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["cost_status"] == "critical"
    assert data["overall_health_status"] == "critical"


def test_scorecard_saving_is_healthy(client: TestClient) -> None:
    """Negative variance (under budget) classifies as 'healthy'."""
    project_id = _create_project(client, "SC11", "Saving Healthy")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 800_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])
    _create_cost_record(client, project_id, 900_000)  # -10 % saving

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert float(data["cost_variance_pct"]) == pytest.approx(-10.0)
    assert data["cost_status"] == "healthy"
    assert data["overall_health_status"] == "healthy"


def test_scorecard_overall_health_critical_when_contingency_critical(
    client: TestClient,
) -> None:
    """overall_health_status == 'critical' when contingency_pressure_pct > 25%."""
    project_id = _create_project(client, "SC12", "Contingency Critical")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 800_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])

    _create_cost_record(client, project_id, 700_000, cost_category="hard_cost")
    _create_cost_record(client, project_id, 300_000, cost_category="contingency")

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # contingency_pressure_pct = 300_000 / 1_000_000 * 100 = 30 %
    assert float(data["contingency_pressure_pct"]) == pytest.approx(30.0)
    assert data["contingency_status"] == "critical"
    assert data["overall_health_status"] == "critical"


# ---------------------------------------------------------------------------
# Archived records excluded from forecast
# ---------------------------------------------------------------------------


def test_scorecard_archived_records_excluded(client: TestClient) -> None:
    """Archived (is_active=False) cost records must not contribute to forecast."""
    project_id = _create_project(client, "SC13", "Archived Excluded")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 800_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])

    # Active record
    _create_cost_record(client, project_id, 1_000_000)
    # Archived record — should be excluded
    archived = _create_cost_record(client, project_id, 500_000)
    archive_resp = client.post(
        f"/api/v1/construction-cost-records/{archived['id']}/archive"
    )
    assert archive_resp.status_code == 200, archive_resp.text

    resp = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Only the active 1,000,000 record should be in forecast
    assert float(data["current_forecast_amount"]) == pytest.approx(1_000_000.0)


# ---------------------------------------------------------------------------
# Determinism — repeated calls return the same result
# ---------------------------------------------------------------------------


def test_scorecard_deterministic_across_calls(client: TestClient) -> None:
    """Scorecard must return the same result when called twice without data change."""
    project_id = _create_project(client, "SC14", "Deterministic")
    comparison_set = _create_comparison_set(client, project_id)
    _add_comparison_line(client, comparison_set["id"], 800_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])
    _create_cost_record(client, project_id, 1_100_000)

    resp1 = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")
    resp2 = client.get(f"/api/v1/projects/{project_id}/construction-scorecard")

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    data1 = resp1.json()
    data2 = resp2.json()

    assert data1["cost_status"] == data2["cost_status"]
    assert data1["overall_health_status"] == data2["overall_health_status"]
    assert data1["cost_variance_pct"] == data2["cost_variance_pct"]


# ---------------------------------------------------------------------------
# 404 for unknown project
# ---------------------------------------------------------------------------


def test_scorecard_404_unknown_project(client: TestClient) -> None:
    resp = client.get("/api/v1/projects/not-a-real-id/construction-scorecard")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth requirement
# ---------------------------------------------------------------------------


def test_scorecard_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/v1/projects/any/construction-scorecard")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Portfolio scorecard endpoint
# ---------------------------------------------------------------------------


def test_portfolio_scorecards_empty(client: TestClient) -> None:
    """Portfolio scorecard with no projects returns zero counts."""
    resp = client.get("/api/v1/portfolio/construction-scorecards")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["summary"]["total_projects_scored"] == 0
    assert data["summary"]["healthy_count"] == 0
    assert data["summary"]["warning_count"] == 0
    assert data["summary"]["critical_count"] == 0
    assert data["summary"]["incomplete_count"] == 0
    assert data["projects"] == []
    assert data["top_risk_projects"] == []
    assert data["missing_baseline_projects"] == []


def test_portfolio_scorecards_counts_by_status(client: TestClient) -> None:
    """Portfolio summary counts reflect correct health status breakdown."""
    # Project A: healthy (small overrun)
    proj_a = _create_project(client, "PORT01", "Healthy Project A")
    set_a = _create_comparison_set(client, proj_a, "Set A")
    _add_comparison_line(client, set_a["id"], 800_000, 1_000_000)
    _approve_baseline(client, set_a["id"])
    _create_cost_record(client, proj_a, 1_030_000)  # 3% → healthy

    # Project B: warning
    proj_b = _create_project(client, "PORT02", "Warning Project B")
    set_b = _create_comparison_set(client, proj_b, "Set B")
    _add_comparison_line(client, set_b["id"], 800_000, 1_000_000)
    _approve_baseline(client, set_b["id"])
    _create_cost_record(client, proj_b, 1_100_000)  # 10% → warning

    # Project C: critical
    proj_c = _create_project(client, "PORT03", "Critical Project C")
    set_c = _create_comparison_set(client, proj_c, "Set C")
    _add_comparison_line(client, set_c["id"], 800_000, 1_000_000)
    _approve_baseline(client, set_c["id"])
    _create_cost_record(client, proj_c, 1_200_000)  # 20% → critical

    # Project D: incomplete (no baseline)
    proj_d = _create_project(client, "PORT04", "Incomplete Project D")
    _create_cost_record(client, proj_d, 500_000)

    resp = client.get("/api/v1/portfolio/construction-scorecards")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    summary = data["summary"]
    assert summary["total_projects_scored"] == 4
    assert summary["healthy_count"] == 1
    assert summary["warning_count"] == 1
    assert summary["critical_count"] == 1
    assert summary["incomplete_count"] == 1
    assert summary["projects_missing_baseline"] == 1


def test_portfolio_scorecards_missing_baseline_surfaced(client: TestClient) -> None:
    """Projects without an approved baseline appear in missing_baseline_projects."""
    proj_a = _create_project(client, "PORT05", "No Baseline A")
    proj_b = _create_project(client, "PORT06", "With Baseline B")

    set_b = _create_comparison_set(client, proj_b)
    _add_comparison_line(client, set_b["id"], 500_000, 500_000)
    _approve_baseline(client, set_b["id"])

    resp = client.get("/api/v1/portfolio/construction-scorecards")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    missing_ids = {p["project_id"] for p in data["missing_baseline_projects"]}
    assert proj_a in missing_ids
    assert proj_b not in missing_ids


def test_portfolio_scorecards_top_risk_ordered(client: TestClient) -> None:
    """Top-risk projects must include critical and warning projects."""
    proj_critical = _create_project(client, "PORT07", "Critical Risk")
    set_c = _create_comparison_set(client, proj_critical)
    _add_comparison_line(client, set_c["id"], 500_000, 1_000_000)
    _approve_baseline(client, set_c["id"])
    _create_cost_record(client, proj_critical, 1_300_000)  # 30 % → critical

    proj_warning = _create_project(client, "PORT08", "Warning Risk")
    set_w = _create_comparison_set(client, proj_warning)
    _add_comparison_line(client, set_w["id"], 500_000, 1_000_000)
    _approve_baseline(client, set_w["id"])
    _create_cost_record(client, proj_warning, 1_100_000)  # 10 % → warning

    resp = client.get("/api/v1/portfolio/construction-scorecards")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    top_risk_ids = {p["project_id"] for p in data["top_risk_projects"]}
    assert proj_critical in top_risk_ids
    assert proj_warning in top_risk_ids


def test_portfolio_scorecards_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/v1/portfolio/construction-scorecards")
    assert resp.status_code == 401


def test_portfolio_scorecards_deterministic(client: TestClient) -> None:
    """Portfolio scorecard is deterministic across repeated calls."""
    proj = _create_project(client, "PORT09", "Deterministic Portfolio")
    comparison_set = _create_comparison_set(client, proj)
    _add_comparison_line(client, comparison_set["id"], 800_000, 1_000_000)
    _approve_baseline(client, comparison_set["id"])
    _create_cost_record(client, proj, 1_100_000)

    resp1 = client.get("/api/v1/portfolio/construction-scorecards")
    resp2 = client.get("/api/v1/portfolio/construction-scorecards")

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    data1 = resp1.json()
    data2 = resp2.json()

    assert data1["summary"]["warning_count"] == data2["summary"]["warning_count"]
    assert len(data1["top_risk_projects"]) == len(data2["top_risk_projects"])


def test_portfolio_scorecard_project_isolation(client: TestClient) -> None:
    """Baseline from project A must not affect scorecard of project B."""
    proj_a = _create_project(client, "PORT10A", "Project A")
    proj_b = _create_project(client, "PORT10B", "Project B")

    set_a = _create_comparison_set(client, proj_a)
    _add_comparison_line(client, set_a["id"], 800_000, 1_000_000)
    _approve_baseline(client, set_a["id"])

    resp = client.get("/api/v1/portfolio/construction-scorecards")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    proj_b_item = next(
        (p for p in data["projects"] if p["project_id"] == proj_b), None
    )
    assert proj_b_item is not None
    assert proj_b_item["has_approved_baseline"] is False
    assert proj_b_item["overall_health_status"] == "incomplete"
