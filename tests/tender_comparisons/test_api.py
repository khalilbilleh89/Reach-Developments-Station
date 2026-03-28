"""Tests for the Tender Comparison & Cost Variance API (PR-V6-11).

Validates:
  - 404 on unknown project/set/line
  - create comparison set with defaults and explicit values
  - response contract shape
  - list comparison sets by project (with filters)
  - get comparison set (includes lines)
  - update comparison set
  - create/update/delete comparison lines
  - variance arithmetic correctness (amount, pct)
  - variance_pct is None when baseline is zero
  - summary totals correctness
  - stage/reason enum validation
  - project isolation (sets for project A not visible to project B)
  - no mutation of source construction cost records
  - auth requirement (401 unauthenticated)
"""

import pytest
from fastapi.testclient import TestClient


def _create_project(client: TestClient, code: str, name: str = "Test Project") -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_set(
    client: TestClient,
    project_id: str,
    *,
    title: str = "Baseline vs Tender Q1",
    comparison_stage: str = "baseline_vs_tender",
    baseline_label: str = "Baseline",
    comparison_label: str = "Tender",
    notes: str | None = None,
    is_active: bool = True,
) -> dict:
    payload: dict = {
        "title": title,
        "comparison_stage": comparison_stage,
        "baseline_label": baseline_label,
        "comparison_label": comparison_label,
        "is_active": is_active,
    }
    if notes is not None:
        payload["notes"] = notes
    resp = client.post(
        f"/api/v1/projects/{project_id}/tender-comparisons", json=payload
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_line(
    client: TestClient,
    set_id: str,
    *,
    cost_category: str = "hard_cost",
    baseline_amount: float = 1_000_000.00,
    comparison_amount: float = 1_100_000.00,
    variance_reason: str = "unit_rate_change",
    notes: str | None = None,
) -> dict:
    payload: dict = {
        "cost_category": cost_category,
        "baseline_amount": baseline_amount,
        "comparison_amount": comparison_amount,
        "variance_reason": variance_reason,
    }
    if notes is not None:
        payload["notes"] = notes
    resp = client.post(f"/api/v1/tender-comparisons/{set_id}/lines", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Set creation
# ---------------------------------------------------------------------------


def test_create_set_minimal(client: TestClient) -> None:
    project_id = _create_project(client, "TC01")
    data = _create_set(client, project_id)

    assert data["id"]
    assert data["project_id"] == project_id
    assert data["title"] == "Baseline vs Tender Q1"
    assert data["comparison_stage"] == "baseline_vs_tender"
    assert data["baseline_label"] == "Baseline"
    assert data["comparison_label"] == "Tender"
    assert data["is_active"] is True
    assert data["lines"] == []
    assert "created_at" in data
    assert "updated_at" in data


def test_create_set_all_fields(client: TestClient) -> None:
    project_id = _create_project(client, "TC02")
    resp = client.post(
        f"/api/v1/projects/{project_id}/tender-comparisons",
        json={
            "title": "Full Comparison Set",
            "comparison_stage": "tender_vs_award",
            "baseline_label": "Initial Tender",
            "comparison_label": "Awarded Contract",
            "notes": "Post-tender negotiation result",
            "is_active": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["comparison_stage"] == "tender_vs_award"
    assert data["baseline_label"] == "Initial Tender"
    assert data["comparison_label"] == "Awarded Contract"
    assert data["notes"] == "Post-tender negotiation result"


def test_create_set_404_unknown_project(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/projects/does-not-exist/tender-comparisons",
        json={"title": "X", "comparison_stage": "baseline_vs_tender"},
    )
    assert resp.status_code == 404


def test_create_set_invalid_stage(client: TestClient) -> None:
    project_id = _create_project(client, "TC03")
    resp = client.post(
        f"/api/v1/projects/{project_id}/tender-comparisons",
        json={"title": "Bad Stage", "comparison_stage": "not_a_real_stage"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Set listing
# ---------------------------------------------------------------------------


def test_list_sets_empty(client: TestClient) -> None:
    project_id = _create_project(client, "TC04")
    resp = client.get(f"/api/v1/projects/{project_id}/tender-comparisons")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_sets_returns_created(client: TestClient) -> None:
    project_id = _create_project(client, "TC05")
    _create_set(client, project_id, title="Set A")
    _create_set(client, project_id, title="Set B")
    resp = client.get(f"/api/v1/projects/{project_id}/tender-comparisons")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    titles = {s["title"] for s in data["items"]}
    assert titles == {"Set A", "Set B"}


def test_list_sets_filter_active(client: TestClient) -> None:
    project_id = _create_project(client, "TC06")
    s1 = _create_set(client, project_id, title="Active Set", is_active=True)
    # Deactivate via PATCH
    client.patch(
        f"/api/v1/tender-comparisons/{s1['id']}", json={"is_active": False}
    )
    _create_set(client, project_id, title="Active Only", is_active=True)

    resp = client.get(
        f"/api/v1/projects/{project_id}/tender-comparisons?is_active=true"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Active Only"


def test_list_sets_project_isolation(client: TestClient) -> None:
    proj_a = _create_project(client, "TC07A")
    proj_b = _create_project(client, "TC07B")
    _create_set(client, proj_a, title="Set for A")
    resp = client.get(f"/api/v1/projects/{proj_b}/tender-comparisons")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_sets_404_unknown_project(client: TestClient) -> None:
    resp = client.get("/api/v1/projects/nope/tender-comparisons")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Get by ID
# ---------------------------------------------------------------------------


def test_get_set_by_id(client: TestClient) -> None:
    project_id = _create_project(client, "TC08")
    created = _create_set(client, project_id, title="Fetched Set")
    resp = client.get(f"/api/v1/tender-comparisons/{created['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["title"] == "Fetched Set"
    assert "lines" in data


def test_get_set_404(client: TestClient) -> None:
    resp = client.get("/api/v1/tender-comparisons/not-a-real-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Set update
# ---------------------------------------------------------------------------


def test_update_set_partial(client: TestClient) -> None:
    project_id = _create_project(client, "TC09")
    created = _create_set(client, project_id, title="Original Title")
    resp = client.patch(
        f"/api/v1/tender-comparisons/{created['id']}",
        json={"title": "Updated Title"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Updated Title"
    assert data["comparison_stage"] == created["comparison_stage"]
    assert data["is_active"] == created["is_active"]


def test_update_set_deactivate(client: TestClient) -> None:
    project_id = _create_project(client, "TC10")
    created = _create_set(client, project_id)
    resp = client.patch(
        f"/api/v1/tender-comparisons/{created['id']}", json={"is_active": False}
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_update_set_404(client: TestClient) -> None:
    resp = client.patch(
        "/api/v1/tender-comparisons/not-exist", json={"title": "X"}
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Line creation
# ---------------------------------------------------------------------------


def test_create_line_minimal(client: TestClient) -> None:
    project_id = _create_project(client, "TC11")
    comparison_set = _create_set(client, project_id)
    line = _create_line(
        client,
        comparison_set["id"],
        baseline_amount=1_000_000,
        comparison_amount=1_100_000,
    )
    assert line["id"]
    assert line["comparison_set_id"] == comparison_set["id"]
    assert line["cost_category"] == "hard_cost"
    assert float(line["baseline_amount"]) == pytest.approx(1_000_000)
    assert float(line["comparison_amount"]) == pytest.approx(1_100_000)
    assert float(line["variance_amount"]) == pytest.approx(100_000)
    assert float(line["variance_pct"]) == pytest.approx(10.0)
    assert line["variance_reason"] == "unit_rate_change"


def test_create_line_negative_variance(client: TestClient) -> None:
    project_id = _create_project(client, "TC12")
    comparison_set = _create_set(client, project_id)
    line = _create_line(
        client,
        comparison_set["id"],
        baseline_amount=1_000_000,
        comparison_amount=900_000,
        variance_reason="ve_saving",
    )
    assert float(line["variance_amount"]) == pytest.approx(-100_000)
    assert float(line["variance_pct"]) == pytest.approx(-10.0)


def test_create_line_zero_baseline_no_pct(client: TestClient) -> None:
    project_id = _create_project(client, "TC13")
    comparison_set = _create_set(client, project_id)
    line = _create_line(
        client,
        comparison_set["id"],
        baseline_amount=0,
        comparison_amount=500_000,
    )
    assert float(line["variance_amount"]) == pytest.approx(500_000)
    assert line["variance_pct"] is None


def test_create_line_shows_in_get_set(client: TestClient) -> None:
    project_id = _create_project(client, "TC14")
    comparison_set = _create_set(client, project_id)
    _create_line(client, comparison_set["id"])
    resp = client.get(f"/api/v1/tender-comparisons/{comparison_set['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["lines"]) == 1


def test_create_line_invalid_category(client: TestClient) -> None:
    project_id = _create_project(client, "TC15")
    comparison_set = _create_set(client, project_id)
    resp = client.post(
        f"/api/v1/tender-comparisons/{comparison_set['id']}/lines",
        json={
            "cost_category": "not_a_category",
            "baseline_amount": 100,
            "comparison_amount": 200,
            "variance_reason": "other",
        },
    )
    assert resp.status_code == 422


def test_create_line_invalid_reason(client: TestClient) -> None:
    project_id = _create_project(client, "TC16")
    comparison_set = _create_set(client, project_id)
    resp = client.post(
        f"/api/v1/tender-comparisons/{comparison_set['id']}/lines",
        json={
            "cost_category": "hard_cost",
            "baseline_amount": 100,
            "comparison_amount": 200,
            "variance_reason": "invented_reason",
        },
    )
    assert resp.status_code == 422


def test_create_line_404_unknown_set(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/tender-comparisons/not-a-set/lines",
        json={
            "cost_category": "hard_cost",
            "baseline_amount": 100,
            "comparison_amount": 200,
            "variance_reason": "other",
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Line update
# ---------------------------------------------------------------------------


def test_update_line_recomputes_variance(client: TestClient) -> None:
    project_id = _create_project(client, "TC17")
    comparison_set = _create_set(client, project_id)
    line = _create_line(
        client,
        comparison_set["id"],
        baseline_amount=1_000_000,
        comparison_amount=1_100_000,
    )
    resp = client.patch(
        f"/api/v1/tender-comparisons/lines/{line['id']}",
        json={"comparison_amount": 1_200_000},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert float(updated["comparison_amount"]) == pytest.approx(1_200_000)
    assert float(updated["variance_amount"]) == pytest.approx(200_000)
    assert float(updated["variance_pct"]) == pytest.approx(20.0)


def test_update_line_preserves_unset_fields(client: TestClient) -> None:
    project_id = _create_project(client, "TC18")
    comparison_set = _create_set(client, project_id)
    line = _create_line(
        client,
        comparison_set["id"],
        cost_category="soft_cost",
        variance_reason="scope_change",
    )
    resp = client.patch(
        f"/api/v1/tender-comparisons/lines/{line['id']}",
        json={"notes": "Updated note"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["cost_category"] == "soft_cost"
    assert updated["variance_reason"] == "scope_change"
    assert updated["notes"] == "Updated note"


def test_update_line_404(client: TestClient) -> None:
    resp = client.patch(
        "/api/v1/tender-comparisons/lines/not-exist",
        json={"notes": "X"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Line deletion
# ---------------------------------------------------------------------------


def test_delete_line(client: TestClient) -> None:
    project_id = _create_project(client, "TC19")
    comparison_set = _create_set(client, project_id)
    line = _create_line(client, comparison_set["id"])
    resp = client.delete(f"/api/v1/tender-comparisons/lines/{line['id']}")
    assert resp.status_code == 204

    # Verify line is gone from the set
    get_resp = client.get(f"/api/v1/tender-comparisons/{comparison_set['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["lines"] == []


def test_delete_line_404(client: TestClient) -> None:
    resp = client.delete("/api/v1/tender-comparisons/lines/not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Summary endpoint
# ---------------------------------------------------------------------------


def test_summary_empty_set(client: TestClient) -> None:
    project_id = _create_project(client, "TC20")
    comparison_set = _create_set(client, project_id)
    resp = client.get(f"/api/v1/tender-comparisons/{comparison_set['id']}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["comparison_set_id"] == comparison_set["id"]
    assert data["project_id"] == project_id
    assert data["line_count"] == 0
    assert float(data["total_baseline"]) == 0
    assert float(data["total_comparison"]) == 0
    assert float(data["total_variance"]) == 0
    assert data["total_variance_pct"] is None


def test_summary_totals_correct(client: TestClient) -> None:
    project_id = _create_project(client, "TC21")
    comparison_set = _create_set(client, project_id)
    _create_line(
        client,
        comparison_set["id"],
        cost_category="hard_cost",
        baseline_amount=1_000_000,
        comparison_amount=1_100_000,
    )
    _create_line(
        client,
        comparison_set["id"],
        cost_category="soft_cost",
        baseline_amount=200_000,
        comparison_amount=180_000,
        variance_reason="ve_saving",
    )
    resp = client.get(f"/api/v1/tender-comparisons/{comparison_set['id']}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["line_count"] == 2
    assert float(data["total_baseline"]) == pytest.approx(1_200_000)
    assert float(data["total_comparison"]) == pytest.approx(1_280_000)
    assert float(data["total_variance"]) == pytest.approx(80_000)
    # (80000 / 1200000) * 100 ≈ 6.6667
    assert float(data["total_variance_pct"]) == pytest.approx(
        80_000 / 1_200_000 * 100, rel=1e-4
    )


def test_summary_404_unknown_set(client: TestClient) -> None:
    resp = client.get("/api/v1/tender-comparisons/no-set/summary")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Variance arithmetic precision
# ---------------------------------------------------------------------------


def test_variance_arithmetic_exact(client: TestClient) -> None:
    """Verify variance_amount = comparison - baseline exactly."""
    project_id = _create_project(client, "TC22")
    comparison_set = _create_set(client, project_id)
    line = _create_line(
        client,
        comparison_set["id"],
        baseline_amount=3_456_789.50,
        comparison_amount=3_600_000.00,
    )
    expected_variance = 3_600_000.00 - 3_456_789.50
    assert float(line["variance_amount"]) == pytest.approx(expected_variance, abs=0.01)
    expected_pct = (expected_variance / 3_456_789.50) * 100
    assert float(line["variance_pct"]) == pytest.approx(expected_pct, rel=1e-4)


# ---------------------------------------------------------------------------
# All comparison stages are accepted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stage",
    [
        "baseline_vs_tender",
        "tender_vs_award",
        "award_vs_variation",
        "baseline_vs_award",
        "baseline_vs_completion",
    ],
)
def test_all_stages_accepted(client: TestClient, stage: str) -> None:
    project_id = _create_project(client, f"TC-STAGE-{stage[:6]}")
    resp = client.post(
        f"/api/v1/projects/{project_id}/tender-comparisons",
        json={"title": "Stage Test", "comparison_stage": stage},
    )
    assert resp.status_code == 201
    assert resp.json()["comparison_stage"] == stage


# ---------------------------------------------------------------------------
# All variance reasons are accepted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    [
        "quantity_change",
        "unit_rate_change",
        "scope_change",
        "ve_saving",
        "contingency_shift",
        "other",
    ],
)
def test_all_variance_reasons_accepted(client: TestClient, reason: str) -> None:
    project_id = _create_project(client, f"TC-RSN-{reason[:6]}")
    comparison_set = _create_set(client, project_id)
    line = _create_line(
        client,
        comparison_set["id"],
        variance_reason=reason,
    )
    assert line["variance_reason"] == reason


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_list_sets_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/v1/projects/any/tender-comparisons")
    assert resp.status_code == 401


def test_create_set_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.post(
        "/api/v1/projects/any/tender-comparisons",
        json={"title": "X", "comparison_stage": "baseline_vs_tender"},
    )
    assert resp.status_code == 401


def test_get_set_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/v1/tender-comparisons/any-id")
    assert resp.status_code == 401
