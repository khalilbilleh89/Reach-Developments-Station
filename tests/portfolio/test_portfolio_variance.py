"""
Tests for the Portfolio Cost Variance Roll-Up API (PR-V6-12).

Validates:
  - GET /api/v1/portfolio/cost-variance requires authentication
  - Empty state when no active comparison sets exist
  - Summary totals correctness
  - Per-project variance card accuracy
  - Variance status label correctness (overrun/saving/neutral)
  - Project ordering: variance_amount descending
  - Top overrun / top saving grouping
  - No mutation of source tender comparison records
  - Multi-project aggregation correctness
  - Missing comparison data flag for projects without sets
  - Major overrun / major saving flags
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Hierarchy / data helpers
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str, name: str = "Variance Project") -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_set(
    client: TestClient,
    project_id: str,
    *,
    title: str = "Baseline vs Tender",
    comparison_stage: str = "baseline_vs_tender",
    is_active: bool = True,
) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/tender-comparisons",
        json={
            "title": title,
            "comparison_stage": comparison_stage,
            "is_active": is_active,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_line(
    client: TestClient,
    set_id: str,
    *,
    baseline_amount: float,
    comparison_amount: float,
    cost_category: str = "hard_cost",
    variance_reason: str = "unit_rate_change",
) -> dict:
    resp = client.post(
        f"/api/v1/tender-comparisons/{set_id}/lines",
        json={
            "cost_category": cost_category,
            "baseline_amount": baseline_amount,
            "comparison_amount": comparison_amount,
            "variance_reason": variance_reason,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Auth requirement
# ---------------------------------------------------------------------------


def test_cost_variance_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Empty state — no comparison sets at all
# ---------------------------------------------------------------------------


def test_cost_variance_empty_state(client: TestClient) -> None:
    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    # Summary is all zeros — monetary totals are now grouped dicts
    summary = data["summary"]
    assert summary["projects_with_comparison_sets"] == 0
    assert summary["total_baseline_amount"] == {}
    assert summary["total_comparison_amount"] == {}
    assert summary["total_variance_amount"] == {}
    assert summary["total_variance_pct"] is None

    # Lists are empty
    assert data["projects"] == []
    assert data["top_overruns"] == []
    assert data["top_savings"] == []


# ---------------------------------------------------------------------------
# Summary totals correctness
# ---------------------------------------------------------------------------


def test_cost_variance_summary_totals(client: TestClient) -> None:
    """Summary totals aggregate correctly from a single active set."""
    project_id = _create_project(client, "PV01", "Variance Project 1")
    comparison_set = _create_set(client, project_id)
    set_id = comparison_set["id"]

    # Baseline 1,000,000 | Comparison 1,100,000 → variance +100,000
    _create_line(client, set_id, baseline_amount=1_000_000.0, comparison_amount=1_100_000.0)

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    # Monetary totals are now grouped by currency
    summary = data["summary"]
    assert summary["projects_with_comparison_sets"] == 1
    assert summary["total_baseline_amount"].get("AED", 0.0) == 1_000_000.0
    assert summary["total_comparison_amount"].get("AED", 0.0) == 1_100_000.0
    assert summary["total_variance_amount"].get("AED", 0.0) == 100_000.0
    # variance_pct = (100000 / 1000000) * 100 = 10.0 (single-currency)
    assert summary["total_variance_pct"] == pytest.approx(10.0, rel=1e-3)


def test_cost_variance_summary_saving(client: TestClient) -> None:
    """Summary reflects net saving when comparison < baseline."""
    project_id = _create_project(client, "PV02", "Variance Project 2")
    comparison_set = _create_set(client, project_id)
    set_id = comparison_set["id"]

    # Baseline 2,000,000 | Comparison 1,800,000 → variance -200,000
    _create_line(client, set_id, baseline_amount=2_000_000.0, comparison_amount=1_800_000.0)

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    summary = data["summary"]
    assert summary["total_variance_amount"].get("AED", 0.0) == pytest.approx(-200_000.0, rel=1e-3)
    # variance_pct = (-200000 / 2000000) * 100 = -10.0 (single-currency)
    assert summary["total_variance_pct"] == pytest.approx(-10.0, rel=1e-3)


def test_cost_variance_summary_zero_baseline(client: TestClient) -> None:
    """variance_pct is None when baseline total is zero."""
    project_id = _create_project(client, "PV03", "Variance Project 3")
    comparison_set = _create_set(client, project_id)
    set_id = comparison_set["id"]

    # Baseline 0 | Comparison 500,000 → variance_pct is None
    _create_line(client, set_id, baseline_amount=0.0, comparison_amount=500_000.0)

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    assert data["summary"]["total_variance_pct"] is None


# ---------------------------------------------------------------------------
# Inactive sets are excluded from the roll-up
# ---------------------------------------------------------------------------


def test_cost_variance_excludes_inactive_sets(client: TestClient) -> None:
    """Inactive comparison sets must not contribute to the roll-up totals."""
    project_id = _create_project(client, "PV04", "Variance Project 4")

    # Active set with a line
    active_set = _create_set(client, project_id, title="Active Set", is_active=True)
    _create_line(
        client, active_set["id"],
        baseline_amount=500_000.0, comparison_amount=550_000.0,
    )

    # Inactive set with a line — must be excluded
    inactive_set = _create_set(
        client, project_id, title="Inactive Set", is_active=False
    )
    _create_line(
        client, inactive_set["id"],
        baseline_amount=1_000_000.0, comparison_amount=2_000_000.0,
    )

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    # Only active set should contribute — check via grouped AED key
    assert data["summary"]["total_baseline_amount"].get("AED", 0.0) == pytest.approx(500_000.0, rel=1e-3)
    assert data["summary"]["total_comparison_amount"].get("AED", 0.0) == pytest.approx(550_000.0, rel=1e-3)
    assert data["summary"]["total_variance_amount"].get("AED", 0.0) == pytest.approx(50_000.0, rel=1e-3)


# ---------------------------------------------------------------------------
# Per-project variance card correctness
# ---------------------------------------------------------------------------


def test_cost_variance_project_card(client: TestClient) -> None:
    """Per-project card has correct amounts and variance_status."""
    project_id = _create_project(client, "PV05", "Overrun Project")
    comparison_set = _create_set(client, project_id)
    set_id = comparison_set["id"]

    _create_line(client, set_id, baseline_amount=1_000_000.0, comparison_amount=1_200_000.0)
    _create_line(client, set_id, baseline_amount=500_000.0, comparison_amount=600_000.0)

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    # Find the card for this project
    cards = data["projects"]
    card = next((c for c in cards if c["project_id"] == project_id), None)
    assert card is not None

    assert card["project_name"] == "Overrun Project"
    assert card["comparison_set_count"] == 1
    assert card["latest_comparison_stage"] == "baseline_vs_tender"
    assert card["baseline_total"] == pytest.approx(1_500_000.0, rel=1e-3)
    assert card["comparison_total"] == pytest.approx(1_800_000.0, rel=1e-3)
    assert card["variance_amount"] == pytest.approx(300_000.0, rel=1e-3)
    # variance_pct = (300000 / 1500000) * 100 = 20.0
    assert card["variance_pct"] == pytest.approx(20.0, rel=1e-2)
    assert card["variance_status"] == "overrun"


def test_cost_variance_project_card_saving(client: TestClient) -> None:
    """Project card has variance_status 'saving' for negative variance."""
    project_id = _create_project(client, "PV06", "Saving Project")
    comparison_set = _create_set(client, project_id)
    set_id = comparison_set["id"]

    _create_line(client, set_id, baseline_amount=1_000_000.0, comparison_amount=900_000.0)

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    cards = data["projects"]
    card = next((c for c in cards if c["project_id"] == project_id), None)
    assert card is not None
    assert card["variance_amount"] == pytest.approx(-100_000.0, rel=1e-3)
    assert card["variance_status"] == "saving"


def test_cost_variance_project_card_neutral(client: TestClient) -> None:
    """Project card has variance_status 'neutral' when baseline == comparison."""
    project_id = _create_project(client, "PV07", "Neutral Project")
    comparison_set = _create_set(client, project_id)
    set_id = comparison_set["id"]

    _create_line(client, set_id, baseline_amount=1_000_000.0, comparison_amount=1_000_000.0)

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    cards = data["projects"]
    card = next((c for c in cards if c["project_id"] == project_id), None)
    assert card is not None
    assert card["variance_amount"] == pytest.approx(0.0, abs=1e-2)
    assert card["variance_status"] == "neutral"


# ---------------------------------------------------------------------------
# Multi-project aggregation and ordering
# ---------------------------------------------------------------------------


def test_cost_variance_multi_project_ordering(client: TestClient) -> None:
    """Projects are ordered by variance_amount descending (largest overrun first)."""
    # Project A: +300,000
    project_a = _create_project(client, "PV08A", "High Overrun")
    set_a = _create_set(client, project_a, title="Set A")
    _create_line(client, set_a["id"], baseline_amount=1_000_000.0, comparison_amount=1_300_000.0)

    # Project B: +100,000
    project_b = _create_project(client, "PV08B", "Low Overrun")
    set_b = _create_set(client, project_b, title="Set B")
    _create_line(client, set_b["id"], baseline_amount=1_000_000.0, comparison_amount=1_100_000.0)

    # Project C: -200,000 (saving)
    project_c = _create_project(client, "PV08C", "Big Saving")
    set_c = _create_set(client, project_c, title="Set C")
    _create_line(client, set_c["id"], baseline_amount=1_000_000.0, comparison_amount=800_000.0)

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    cards = data["projects"]
    # Filter to just our test projects to avoid interference from other tests
    our_ids = {project_a, project_b, project_c}
    our_cards = [c for c in cards if c["project_id"] in our_ids]
    assert len(our_cards) == 3

    # Ordered by variance_amount descending: A (+300k), B (+100k), C (-200k)
    assert our_cards[0]["project_id"] == project_a
    assert our_cards[1]["project_id"] == project_b
    assert our_cards[2]["project_id"] == project_c


def test_cost_variance_top_overruns(client: TestClient) -> None:
    """top_overruns contains only projects with positive variance_amount."""
    project_a = _create_project(client, "PV09A", "Overrun A")
    set_a = _create_set(client, project_a, title="Set A")
    _create_line(client, set_a["id"], baseline_amount=1_000_000.0, comparison_amount=1_500_000.0)

    project_b = _create_project(client, "PV09B", "Saving B")
    set_b = _create_set(client, project_b, title="Set B")
    _create_line(client, set_b["id"], baseline_amount=1_000_000.0, comparison_amount=800_000.0)

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    overrun_ids = {c["project_id"] for c in data["top_overruns"]}
    assert project_a in overrun_ids
    assert project_b not in overrun_ids


def test_cost_variance_top_savings(client: TestClient) -> None:
    """top_savings contains only projects with negative variance_amount."""
    project_a = _create_project(client, "PV10A", "Overrun X")
    set_a = _create_set(client, project_a, title="Set A")
    _create_line(client, set_a["id"], baseline_amount=1_000_000.0, comparison_amount=1_200_000.0)

    project_b = _create_project(client, "PV10B", "Saving X")
    set_b = _create_set(client, project_b, title="Set B")
    _create_line(client, set_b["id"], baseline_amount=1_000_000.0, comparison_amount=700_000.0)

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    savings_ids = {c["project_id"] for c in data["top_savings"]}
    assert project_b in savings_ids
    assert project_a not in savings_ids


def test_cost_variance_multi_project_totals(client: TestClient) -> None:
    """Portfolio summary totals aggregate correctly across multiple projects."""
    project_a = _create_project(client, "PV11A", "Proj A Totals")
    set_a = _create_set(client, project_a, title="Set A")
    _create_line(client, set_a["id"], baseline_amount=1_000_000.0, comparison_amount=1_100_000.0)

    project_b = _create_project(client, "PV11B", "Proj B Totals")
    set_b = _create_set(client, project_b, title="Set B")
    _create_line(client, set_b["id"], baseline_amount=500_000.0, comparison_amount=450_000.0)

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    # Total baseline = 1,500,000 | Total comparison = 1,550,000 | variance = +50,000
    # (may include data from other tests, so check only the two projects' contribution)
    cards = data["projects"]
    our_ids = {project_a, project_b}
    our_cards = [c for c in cards if c["project_id"] in our_ids]

    total_baseline = sum(c["baseline_total"] for c in our_cards)
    total_comparison = sum(c["comparison_total"] for c in our_cards)
    total_variance = sum(c["variance_amount"] for c in our_cards)

    assert total_baseline == pytest.approx(1_500_000.0, rel=1e-3)
    assert total_comparison == pytest.approx(1_550_000.0, rel=1e-3)
    assert total_variance == pytest.approx(50_000.0, rel=1e-3)


# ---------------------------------------------------------------------------
# Source record immutability
# ---------------------------------------------------------------------------


def test_cost_variance_does_not_mutate_source_sets(client: TestClient) -> None:
    """Fetching cost-variance must not alter source comparison sets."""
    project_id = _create_project(client, "PV12", "Immutable Project")
    comparison_set = _create_set(client, project_id)
    set_id = comparison_set["id"]
    _create_line(client, set_id, baseline_amount=1_000_000.0, comparison_amount=1_100_000.0)

    # Fetch portfolio variance
    client.get("/api/v1/portfolio/cost-variance")

    # Fetch the source set — must be unchanged
    after_resp = client.get(f"/api/v1/tender-comparisons/{set_id}")
    assert after_resp.status_code == 200
    after = after_resp.json()
    assert after["id"] == set_id
    assert after["is_active"] is True
    assert len(after["lines"]) == 1


# ---------------------------------------------------------------------------
# Response contract shape
# ---------------------------------------------------------------------------


def test_cost_variance_response_contract(client: TestClient) -> None:
    """Response always contains required top-level keys."""
    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    assert "summary" in data
    assert "projects" in data
    assert "top_overruns" in data
    assert "top_savings" in data
    assert "flags" in data

    summary = data["summary"]
    assert "projects_with_comparison_sets" in summary
    assert "total_baseline_amount" in summary
    assert "total_comparison_amount" in summary
    assert "total_variance_amount" in summary
    assert "total_variance_pct" in summary

# ---------------------------------------------------------------------------
# Flag coverage — missing_comparison_data, major_overrun, major_saving
# ---------------------------------------------------------------------------


def test_flag_missing_comparison_data_project_with_no_sets(client: TestClient) -> None:
    """Projects with no active comparison sets produce a missing_comparison_data flag."""
    project_id = _create_project(client, "PVF01", "No Sets Project")
    # Do NOT create any comparison sets for this project

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    flag_types = [f["flag_type"] for f in data["flags"]]
    assert "missing_comparison_data" in flag_types

    missing_flags = [f for f in data["flags"] if f["flag_type"] == "missing_comparison_data"]
    project_ids_in_flags = [f["affected_project_id"] for f in missing_flags]
    assert project_id in project_ids_in_flags


def test_flag_missing_comparison_data_only_inactive_sets(client: TestClient) -> None:
    """Projects with only inactive comparison sets also produce missing_comparison_data."""
    project_id = _create_project(client, "PVF02", "Only Inactive Sets")
    inactive_set = _create_set(client, project_id, title="Inactive", is_active=False)
    _create_line(
        client, inactive_set["id"],
        baseline_amount=1_000_000.0, comparison_amount=1_200_000.0,
    )

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    flag_types = [f["flag_type"] for f in data["flags"]]
    assert "missing_comparison_data" in flag_types

    missing_flags = [f for f in data["flags"] if f["flag_type"] == "missing_comparison_data"]
    project_ids_in_flags = [f["affected_project_id"] for f in missing_flags]
    assert project_id in project_ids_in_flags


def test_flag_major_overrun_above_threshold(client: TestClient) -> None:
    """Project with variance_pct > 10% produces a major_overrun flag."""
    project_id = _create_project(client, "PVF03", "Major Overrun Project")
    comparison_set = _create_set(client, project_id)
    # +150,000 on 1,000,000 baseline = +15% → above 10% threshold
    _create_line(
        client, comparison_set["id"],
        baseline_amount=1_000_000.0, comparison_amount=1_150_000.0,
    )

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    major_overrun_flags = [f for f in data["flags"] if f["flag_type"] == "major_overrun"]
    affected_ids = [f["affected_project_id"] for f in major_overrun_flags]
    assert project_id in affected_ids


def test_flag_major_saving_below_threshold(client: TestClient) -> None:
    """Project with variance_pct < -10% produces a major_saving flag."""
    project_id = _create_project(client, "PVF04", "Major Saving Project")
    comparison_set = _create_set(client, project_id)
    # -150,000 on 1,000,000 baseline = -15% → below -10% threshold
    _create_line(
        client, comparison_set["id"],
        baseline_amount=1_000_000.0, comparison_amount=850_000.0,
    )

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    major_saving_flags = [f for f in data["flags"] if f["flag_type"] == "major_saving"]
    affected_ids = [f["affected_project_id"] for f in major_saving_flags]
    assert project_id in affected_ids


def test_flag_no_major_overrun_at_exact_threshold(client: TestClient) -> None:
    """Project with variance_pct exactly 10% does NOT produce a major_overrun flag (strict >)."""
    project_id = _create_project(client, "PVF05", "Exactly 10% Overrun")
    comparison_set = _create_set(client, project_id)
    # +100,000 on 1,000,000 baseline = exactly 10.00%
    _create_line(
        client, comparison_set["id"],
        baseline_amount=1_000_000.0, comparison_amount=1_100_000.0,
    )

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    major_overrun_flags = [f for f in data["flags"] if f["flag_type"] == "major_overrun"]
    affected_ids = [f["affected_project_id"] for f in major_overrun_flags]
    # Exactly at threshold must NOT trigger flag (threshold is strictly >)
    assert project_id not in affected_ids


def test_flag_no_major_saving_at_exact_threshold(client: TestClient) -> None:
    """Project with variance_pct exactly -10% does NOT produce a major_saving flag (strict <)."""
    project_id = _create_project(client, "PVF06", "Exactly -10% Saving")
    comparison_set = _create_set(client, project_id)
    # -100,000 on 1,000,000 baseline = exactly -10.00%
    _create_line(
        client, comparison_set["id"],
        baseline_amount=1_000_000.0, comparison_amount=900_000.0,
    )

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    major_saving_flags = [f for f in data["flags"] if f["flag_type"] == "major_saving"]
    affected_ids = [f["affected_project_id"] for f in major_saving_flags]
    # Exactly at threshold must NOT trigger flag (threshold is strictly <)
    assert project_id not in affected_ids


def test_flag_no_overrun_or_saving_below_threshold(client: TestClient) -> None:
    """Project with 5% overrun produces neither major_overrun nor major_saving flag."""
    project_id = _create_project(client, "PVF07", "Small Overrun")
    comparison_set = _create_set(client, project_id)
    # +50,000 on 1,000,000 baseline = 5% — below 10% threshold
    _create_line(
        client, comparison_set["id"],
        baseline_amount=1_000_000.0, comparison_amount=1_050_000.0,
    )

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    overrun_ids = [f["affected_project_id"] for f in data["flags"] if f["flag_type"] == "major_overrun"]
    saving_ids = [f["affected_project_id"] for f in data["flags"] if f["flag_type"] == "major_saving"]
    assert project_id not in overrun_ids
    assert project_id not in saving_ids


def test_flag_zero_baseline_does_not_produce_overrun_or_saving_flags(
    client: TestClient,
) -> None:
    """Project with zero baseline (variance_pct = None) produces no overrun/saving flag."""
    project_id = _create_project(client, "PVF08", "Zero Baseline Project")
    comparison_set = _create_set(client, project_id)
    # Baseline 0 → variance_pct is None → no threshold comparison possible
    _create_line(
        client, comparison_set["id"],
        baseline_amount=0.0, comparison_amount=500_000.0,
    )

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    overrun_ids = [f["affected_project_id"] for f in data["flags"] if f["flag_type"] == "major_overrun"]
    saving_ids = [f["affected_project_id"] for f in data["flags"] if f["flag_type"] == "major_saving"]
    assert project_id not in overrun_ids
    assert project_id not in saving_ids


# ---------------------------------------------------------------------------
# Latest comparison stage — correctness of SQL-level aggregation
# ---------------------------------------------------------------------------


def test_latest_comparison_stage_reflects_newest_set(client: TestClient) -> None:
    """latest_comparison_stage returns the stage of the most recently created active set."""
    project_id = _create_project(client, "PVS01", "Stage Test Project")

    # Create an earlier set with one stage
    _create_set(client, project_id, title="Old Set", comparison_stage="baseline_vs_tender")
    # Create a newer set with a different stage
    _create_set(client, project_id, title="New Set", comparison_stage="tender_vs_award")

    resp = client.get("/api/v1/portfolio/cost-variance")
    assert resp.status_code == 200
    data = resp.json()

    cards = data["projects"]
    card = next((c for c in cards if c["project_id"] == project_id), None)
    assert card is not None
    # Most recent active set has stage tender_vs_award
    assert card["latest_comparison_stage"] == "tender_vs_award"
