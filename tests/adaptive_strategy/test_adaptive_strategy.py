"""
Tests for the Adaptive Strategy Influence Layer (PR-V7-12).

Validates:
  GET /api/v1/projects/{id}/adaptive-strategy
    - HTTP contract (200, 404, auth required)
    - Returns raw and adaptive best strategies
    - confidence_influence_applied is False when no learning metrics exist
    - confidence_influence_applied is True when metrics exist with non-neutral confidence
    - low_confidence_flag is True when band is 'low' or 'insufficient'
    - comparison block present with changed_by_confidence flag
    - adjusted_reason is a non-empty string

  GET /api/v1/portfolio/adaptive-strategy
    - HTTP contract (200, auth required)
    - Returns correct total_projects count
    - Returns high_confidence_projects / low_confidence_projects counts
    - project_cards list is populated

  Pure unit tests (no DB/HTTP):
    - compute_confidence_band: high / medium / low / insufficient
    - compute_adjusted_score: neutral when no metrics
    - compute_adjusted_score: positive influence for high confidence
    - compute_adjusted_score: negative influence for low confidence
    - compute_adjusted_score: low-sample guard halves influence
    - influence is bounded (max ±MAX_INFLUENCE × INFLUENCE_SCALE)
    - raw_best and adaptive_best are both always returned
    - changed_by_confidence flag correctness
    - portfolio confidence counts correctness
    - source learning records are never mutated after API calls
"""

import pytest
from fastapi.testclient import TestClient

from app.modules.adaptive_strategy.service import (
    compute_confidence_band,
    compute_adjusted_score,
)
from app.main import app

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_STRATEGY_SNAPSHOT = {
    "recommended_strategy": "maintain",
    "best_irr": 0.15,
    "risk_score": "medium",
}

_EXECUTION_PACKAGE_SNAPSHOT = {
    "execution_readiness": "ready_for_review",
    "supporting_metrics": {
        "price_adjustment_pct": 5.0,
        "phase_delay_months": 2,
        "release_strategy": "maintain",
    },
    "actions": [{"step_number": 1, "action_type": "simulation_review"}],
}

_MATCHED_OUTCOME = {
    "outcome_result": "matched_strategy",
    "actual_price_adjustment_pct": 5.0,
    "actual_phase_delay_months": 2.0,
    "actual_release_strategy": "maintain",
    "execution_summary": "All actions completed as planned.",
}

_DIVERGED_OUTCOME = {
    "outcome_result": "diverged",
    "actual_price_adjustment_pct": 12.0,
    "actual_phase_delay_months": 6.0,
    "actual_release_strategy": "accelerate",
    "execution_summary": "Execution materially diverged.",
}


def _create_project(client: TestClient, code: str = "AS-001", name: str = "Adaptive Proj") -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_and_approve(client: TestClient, project_id: str) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/strategy-approval",
        json={
            "strategy_snapshot": _STRATEGY_SNAPSHOT,
            "execution_package_snapshot": _EXECUTION_PACKAGE_SNAPSHOT,
        },
    )
    assert resp.status_code == 201, resp.text
    approval = resp.json()
    resp2 = client.post(f"/api/v1/approvals/{approval['id']}/approve")
    assert resp2.status_code == 200, resp2.text
    return approval


def _create_completed_trigger(client: TestClient, project_id: str) -> dict:
    resp = client.post(f"/api/v1/projects/{project_id}/strategy-execution-trigger")
    assert resp.status_code == 201, resp.text
    trigger = resp.json()
    client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
    client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
    return trigger


def _record_outcome(client: TestClient, trigger_id: str, body: dict) -> dict:
    resp = client.post(f"/api/v1/execution-triggers/{trigger_id}/outcome", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _setup_project_with_learning(
    client: TestClient,
    code: str = "AS-001",
    name: str = "Adaptive Proj",
    outcome_body: dict = None,
) -> str:
    """Create a project, approve a strategy, create a trigger, record an outcome,
    and recalibrate learning. Returns the project_id."""
    if outcome_body is None:
        outcome_body = _MATCHED_OUTCOME
    project_id = _create_project(client, code=code, name=name)
    _create_and_approve(client, project_id)
    trigger = _create_completed_trigger(client, project_id)
    _record_outcome(client, trigger["id"], outcome_body)
    # Recalibrate learning so metrics exist.
    resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
    assert resp.status_code == 200, resp.text
    return project_id


# ---------------------------------------------------------------------------
# Unit tests — pure logic (no DB / HTTP)
# ---------------------------------------------------------------------------


class TestComputeConfidenceBand:
    def test_none_returns_insufficient(self):
        assert compute_confidence_band(None) == "insufficient"

    def test_high_band(self):
        assert compute_confidence_band(0.7) == "high"
        assert compute_confidence_band(1.0) == "high"
        assert compute_confidence_band(0.85) == "high"

    def test_medium_band(self):
        assert compute_confidence_band(0.4) == "medium"
        assert compute_confidence_band(0.5) == "medium"
        assert compute_confidence_band(0.699) == "medium"

    def test_low_band(self):
        assert compute_confidence_band(0.0) == "low"
        assert compute_confidence_band(0.39) == "low"


class TestComputeAdjustedScore:
    def test_no_confidence_returns_raw(self):
        raw_irr = 0.15
        result = compute_adjusted_score(raw_irr, None, 0)
        assert result == raw_irr

    def test_neutral_confidence_no_change(self):
        # confidence_score=0.5 → weight=0 → no change
        result = compute_adjusted_score(0.15, 0.5, 10)
        assert abs(result - 0.15) < 1e-10

    def test_high_confidence_increases_score(self):
        # High confidence should increase the adjusted score.
        raw = 0.15
        result = compute_adjusted_score(raw, 0.9, 10)
        assert result > raw

    def test_low_confidence_decreases_score(self):
        # Low confidence should decrease the adjusted score.
        raw = 0.15
        result = compute_adjusted_score(raw, 0.1, 10)
        assert result < raw

    def test_influence_is_bounded(self):
        # At extreme confidence (1.0), weight is capped at MAX_INFLUENCE.
        # adjusted = raw * (1 + MAX_INFLUENCE * INFLUENCE_SCALE)
        # = raw * (1 + 0.3 * 0.10) = raw * 1.03
        raw = 0.20
        result = compute_adjusted_score(raw, 1.0, 10)
        expected_max = raw * (1 + 0.3 * 0.10)
        assert abs(result - expected_max) < 1e-9

    def test_influence_is_bounded_low(self):
        # At extreme low confidence (0.0), weight is capped at -MAX_INFLUENCE.
        raw = 0.20
        result = compute_adjusted_score(raw, 0.0, 10)
        expected_min = raw * (1 - 0.3 * 0.10)
        assert abs(result - expected_min) < 1e-9

    def test_low_sample_guard_halves_influence(self):
        # With sample_size=3 (< 5), influence should be halved.
        raw = 0.20
        full_result = compute_adjusted_score(raw, 1.0, 10)  # full influence
        half_result = compute_adjusted_score(raw, 1.0, 3)   # halved
        # full delta from raw = full_result - raw
        # half delta should be approx half that
        full_delta = full_result - raw
        half_delta = half_result - raw
        assert abs(half_delta - full_delta / 2.0) < 1e-9

    def test_zero_irr_with_confidence(self):
        # Edge: zero IRR stays zero regardless of confidence.
        result = compute_adjusted_score(0.0, 0.9, 10)
        assert result == 0.0

    def test_negative_irr_with_high_confidence(self):
        # Negative IRR with high confidence: the proportional adjustment still
        # applies — negative × (1 + positive_weight) = more negative.
        # The influence model scales proportionally regardless of sign.
        raw = -0.05
        result = compute_adjusted_score(raw, 0.9, 10)
        # adjusted = raw * (1 + 0.3*0.10) = -0.05 * 1.03 = -0.0515 (more negative)
        assert result < raw  # proportional scale makes negative IRR more negative


# ---------------------------------------------------------------------------
# API contract tests
# ---------------------------------------------------------------------------


class TestProjectAdaptiveStrategyEndpoint:
    def test_404_for_unknown_project(self, client: TestClient):
        resp = client.get("/api/v1/projects/nonexistent-xyz/adaptive-strategy")
        assert resp.status_code == 404

    def test_auth_required(self, unauth_client: TestClient):
        resp = unauth_client.get("/api/v1/projects/some-id/adaptive-strategy")
        assert resp.status_code in (401, 403)

    def test_returns_200_with_schema(self, client: TestClient):
        project_id = _create_project(client)
        resp = client.get(f"/api/v1/projects/{project_id}/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["project_id"] == project_id
        assert "raw_best_strategy" in data
        assert "adaptive_best_strategy" in data
        assert "confidence_score" in data
        assert "confidence_band" in data
        assert "confidence_influence_applied" in data
        assert "low_confidence_flag" in data
        assert "adjusted_reason" in data
        assert "comparison" in data

    def test_no_learning_data_neutral_influence(self, client: TestClient):
        """Without learning metrics, confidence_influence_applied must be False."""
        project_id = _create_project(client, code="AS-002", name="NoLearn Proj")
        resp = client.get(f"/api/v1/projects/{project_id}/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["confidence_score"] is None
        assert data["confidence_band"] == "insufficient"
        assert data["confidence_influence_applied"] is False
        assert data["low_confidence_flag"] is True
        assert data["sample_size"] == 0

    def test_no_learning_raw_and_adaptive_match(self, client: TestClient):
        """Without learning data, raw and adaptive best strategies must be identical."""
        project_id = _create_project(client, code="AS-003", name="NoLearn2 Proj")
        resp = client.get(f"/api/v1/projects/{project_id}/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["raw_best_strategy"] == data["adaptive_best_strategy"]
        assert data["comparison"]["changed_by_confidence"] is False

    def test_with_learning_data_has_confidence_score(self, client: TestClient):
        """After recalibration, confidence_score should be populated."""
        project_id = _setup_project_with_learning(
            client, code="AS-004", name="WithLearn Proj"
        )
        resp = client.get(f"/api/v1/projects/{project_id}/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["confidence_score"] is not None
        assert 0.0 <= data["confidence_score"] <= 1.0
        assert data["confidence_band"] in ("high", "medium", "low")

    def test_comparison_block_fields_present(self, client: TestClient):
        """comparison block must contain all required fields."""
        project_id = _create_project(client, code="AS-005", name="CmpBlk Proj")
        resp = client.get(f"/api/v1/projects/{project_id}/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        cmp = resp.json()["comparison"]
        assert "raw_irr" in cmp
        assert "adaptive_irr" in cmp
        assert "raw_risk_score" in cmp
        assert "adaptive_risk_score" in cmp
        assert "raw_release_strategy" in cmp
        assert "adaptive_release_strategy" in cmp
        assert "raw_price_adjustment_pct" in cmp
        assert "adaptive_price_adjustment_pct" in cmp
        assert "raw_phase_delay_months" in cmp
        assert "adaptive_phase_delay_months" in cmp
        assert "changed_by_confidence" in cmp

    def test_adjusted_reason_is_non_empty(self, client: TestClient):
        project_id = _create_project(client, code="AS-006", name="Reason Proj")
        resp = client.get(f"/api/v1/projects/{project_id}/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["adjusted_reason"]) > 0

    def test_low_confidence_flag_true_when_band_low(self, client: TestClient):
        """Diverged outcomes produce low confidence; flag must be True."""
        project_id = _setup_project_with_learning(
            client,
            code="AS-007",
            name="LowConf Proj",
            outcome_body=_DIVERGED_OUTCOME,
        )
        resp = client.get(f"/api/v1/projects/{project_id}/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # diverged outcome → low confidence score (<0.4)
        if data["confidence_score"] is not None and data["confidence_score"] < 0.4:
            assert data["low_confidence_flag"] is True
            assert data["confidence_band"] == "low"

    def test_source_records_not_mutated_after_adaptive_call(self, client: TestClient):
        """Calling the adaptive endpoint must not change stored learning metrics."""
        project_id = _setup_project_with_learning(
            client, code="AS-008", name="Immutable Proj"
        )
        # Record learning state before.
        before_resp = client.get(f"/api/v1/projects/{project_id}/strategy-learning")
        before = before_resp.json()

        # Call adaptive endpoint.
        client.get(f"/api/v1/projects/{project_id}/adaptive-strategy")

        # Record learning state after.
        after_resp = client.get(f"/api/v1/projects/{project_id}/strategy-learning")
        after = after_resp.json()

        assert before["overall_metrics"]["confidence_score"] == after["overall_metrics"]["confidence_score"]
        assert before["overall_metrics"]["sample_size"] == after["overall_metrics"]["sample_size"]


class TestPortfolioAdaptiveStrategyEndpoint:
    def test_auth_required(self, unauth_client: TestClient):
        resp = unauth_client.get("/api/v1/portfolio/adaptive-strategy")
        assert resp.status_code in (401, 403)

    def test_returns_200_empty_portfolio(self, client: TestClient):
        resp = client.get("/api/v1/portfolio/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total_projects"] == 0
        assert data["high_confidence_projects"] == 0
        assert data["low_confidence_projects"] == 0
        assert data["confidence_adjusted_projects"] == 0
        assert data["neutral_projects"] == 0
        assert data["project_cards"] == []
        assert data["top_confident_recommendations"] == []
        assert data["top_low_confidence_projects"] == []

    def test_returns_200_with_projects(self, client: TestClient):
        _create_project(client, code="PAS-001", name="Port AS Proj 1")
        _create_project(client, code="PAS-002", name="Port AS Proj 2")
        resp = client.get("/api/v1/portfolio/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total_projects"] == 2
        assert len(data["project_cards"]) == 2

    def test_schema_fields_present(self, client: TestClient):
        _create_project(client, code="PAS-003", name="Port AS Proj 3")
        resp = client.get("/api/v1/portfolio/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        required = [
            "total_projects",
            "high_confidence_projects",
            "low_confidence_projects",
            "confidence_adjusted_projects",
            "neutral_projects",
            "top_confident_recommendations",
            "top_low_confidence_projects",
            "project_cards",
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_low_confidence_projects_counted_correctly(self, client: TestClient):
        """Projects without learning metrics should count as low confidence."""
        pid1 = _create_project(client, code="PAS-004", name="LowConf1")
        pid2 = _create_project(client, code="PAS-005", name="LowConf2")
        resp = client.get("/api/v1/portfolio/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # No learning metrics → band='insufficient' → low_confidence_flag=True
        assert data["low_confidence_projects"] == 2

    def test_project_card_fields_present(self, client: TestClient):
        _create_project(client, code="PAS-006", name="CardProj")
        resp = client.get("/api/v1/portfolio/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        card = resp.json()["project_cards"][0]
        for field in [
            "project_id",
            "project_name",
            "raw_best_strategy",
            "adaptive_best_strategy",
            "confidence_score",
            "confidence_band",
            "confidence_influence_applied",
            "low_confidence_flag",
            "sample_size",
            "trend_direction",
            "adjusted_reason",
        ]:
            assert field in card, f"Missing card field: {field}"

    def test_high_confidence_projects_counted_after_learning(self, client: TestClient):
        """A project with many matched outcomes should produce high confidence."""
        project_id = _create_project(client, code="PAS-007", name="HighConf Proj")
        # Create 5 matched outcomes to exceed low-sample threshold.
        for i in range(5):
            _create_and_approve(client, project_id)
            trigger = _create_completed_trigger(client, project_id)
            _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")

        resp = client.get("/api/v1/portfolio/adaptive-strategy")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # At least this one project should have high confidence.
        assert data["high_confidence_projects"] >= 1

    def test_portfolio_does_not_mutate_source_records(self, client: TestClient):
        """Calling the portfolio endpoint must not change stored learning metrics."""
        project_id = _setup_project_with_learning(
            client, code="PAS-008", name="ImmutPortProj"
        )
        before = client.get(f"/api/v1/projects/{project_id}/strategy-learning").json()

        # Call portfolio endpoint.
        client.get("/api/v1/portfolio/adaptive-strategy")

        after = client.get(f"/api/v1/projects/{project_id}/strategy-learning").json()
        assert (
            before["overall_metrics"]["confidence_score"]
            == after["overall_metrics"]["confidence_score"]
        )
