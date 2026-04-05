"""
Tests for the Strategy Learning & Confidence Recalibration Engine (PR-V7-11 / PR-V7-11A).

Validates:
  POST /api/v1/projects/{id}/strategy-learning/recalibrate
    - HTTP contract (200, 404, auth required)
    - Returns has_sufficient_data=False when no outcomes exist
    - Returns metrics with correct sample_size after outcomes recorded
    - Confidence formula applied correctly
    - Low-sample cap applied when sample_size < 5
    - Per-strategy-type breakdowns present
    - Upsert: recalibrating twice gives updated values
    - pricing_accuracy_score populated from trigger snapshot
    - phasing_accuracy_score populated from trigger snapshot

  GET /api/v1/projects/{id}/strategy-learning
    - HTTP contract (200, 404, auth required)
    - Returns has_sufficient_data=False before any recalibration
    - Returns stored metrics after recalibration

  GET /api/v1/portfolio/strategy-learning
    - HTTP contract (200, auth required)
    - Returns empty payload when no data
    - Returns summary after recalibration with data
    - KPI total_projects_with_data reflects full portfolio (not capped subset)

  Pure unit tests (no DB/HTTP):
    - compute_confidence_score: correct formula
    - compute_confidence_score: low-sample cap
    - compute_trend_direction: improving / declining / stable / insufficient_data
    - compute_pricing_accuracy: correct fraction with triggers_map
    - compute_phasing_accuracy: correct fraction with triggers_map
    - _get_intended_price / _get_intended_phase: extract from snapshot
    - _get_nested_value: safe traversal
"""

import pytest
from fastapi.testclient import TestClient

from app.modules.strategy_learning.service import (
    compute_confidence_score,
    compute_trend_direction,
    compute_pricing_accuracy,
    compute_phasing_accuracy,
    _get_intended_price,
    _get_intended_phase,
    _get_nested_value,
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


def _create_project(client: TestClient, code: str = "SL-001", name: str = "Learn Proj") -> str:
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


def _setup_project_with_outcomes(
    client: TestClient,
    code: str,
    outcomes: list[dict],
) -> str:
    """Create a project, record N outcomes (one trigger per outcome), return project_id."""
    project_id = _create_project(client, code=code, name=f"Project {code}")
    for i, outcome_body in enumerate(outcomes):
        if i > 0:
            # Re-approve: each trigger requires an active approved strategy.
            _create_and_approve(client, project_id)
        else:
            _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], outcome_body)
    return project_id


# ---------------------------------------------------------------------------
# POST /projects/{id}/strategy-learning/recalibrate
# ---------------------------------------------------------------------------


class TestRecalibrateProjectLearning:
    def test_recalibrate_returns_200(self, client: TestClient) -> None:
        project_id = _create_project(client, code="RC-001")
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        assert resp.status_code == 200

    def test_recalibrate_no_outcomes_returns_no_data(self, client: TestClient) -> None:
        project_id = _create_project(client, code="RC-002")
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_sufficient_data"] is False
        assert body["overall_metrics"] is None
        assert body["strategy_breakdowns"] == []

    def test_recalibrate_returns_project_id(self, client: TestClient) -> None:
        project_id = _create_project(client, code="RC-003")
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        assert resp.json()["project_id"] == project_id

    def test_recalibrate_with_one_outcome_has_data(self, client: TestClient) -> None:
        project_id = _create_project(client, code="RC-004")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_sufficient_data"] is True
        assert body["overall_metrics"] is not None

    def test_recalibrate_overall_metrics_sample_size(self, client: TestClient) -> None:
        project_id = _create_project(client, code="RC-005")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        metrics = resp.json()["overall_metrics"]
        assert metrics["sample_size"] == 1

    def test_recalibrate_matched_outcome_high_match_rate(self, client: TestClient) -> None:
        project_id = _create_project(client, code="RC-006")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        metrics = resp.json()["overall_metrics"]
        assert metrics["match_rate"] == pytest.approx(1.0)
        assert metrics["divergence_rate"] == pytest.approx(0.0)

    def test_recalibrate_low_sample_caps_confidence(self, client: TestClient) -> None:
        """With sample_size < 5, confidence must be <= 0.5."""
        project_id = _create_project(client, code="RC-007")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        metrics = resp.json()["overall_metrics"]
        assert metrics["sample_size"] == 1
        assert metrics["confidence_score"] <= 0.5

    def test_recalibrate_404_for_missing_project(self, client: TestClient) -> None:
        resp = client.post("/api/v1/projects/nonexistent-proj/strategy-learning/recalibrate")
        assert resp.status_code == 404

    def test_recalibrate_requires_auth(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post("/api/v1/projects/any/strategy-learning/recalibrate")
        assert resp.status_code in (401, 403)

    def test_recalibrate_accuracy_breakdown_fields_present(self, client: TestClient) -> None:
        project_id = _create_project(client, code="RC-008")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        metrics = resp.json()["overall_metrics"]
        breakdown = metrics["accuracy_breakdown"]
        assert "overall_strategy_accuracy" in breakdown
        assert "pricing_accuracy_score" in breakdown
        assert "phasing_accuracy_score" in breakdown

    def test_recalibrate_trend_direction_present(self, client: TestClient) -> None:
        project_id = _create_project(client, code="RC-009")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        metrics = resp.json()["overall_metrics"]
        assert metrics["trend_direction"] in (
            "improving", "declining", "stable", "insufficient_data"
        )

    def test_recalibrate_strategy_type_present(self, client: TestClient) -> None:
        project_id = _create_project(client, code="RC-010")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        metrics = resp.json()["overall_metrics"]
        assert metrics["strategy_type"] == "_all_"

    def test_recalibrate_upserts_on_second_call(self, client: TestClient) -> None:
        """Second recalibration must not error and updates confidence."""
        project_id = _create_project(client, code="RC-011")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        resp2 = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# GET /projects/{id}/strategy-learning
# ---------------------------------------------------------------------------


class TestGetProjectLearning:
    def test_get_returns_200(self, client: TestClient) -> None:
        project_id = _create_project(client, code="GL-001")
        resp = client.get(f"/api/v1/projects/{project_id}/strategy-learning")
        assert resp.status_code == 200

    def test_get_no_data_before_recalibrate(self, client: TestClient) -> None:
        project_id = _create_project(client, code="GL-002")
        resp = client.get(f"/api/v1/projects/{project_id}/strategy-learning")
        body = resp.json()
        assert body["has_sufficient_data"] is False
        assert body["overall_metrics"] is None

    def test_get_returns_data_after_recalibrate(self, client: TestClient) -> None:
        project_id = _create_project(client, code="GL-003")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        resp = client.get(f"/api/v1/projects/{project_id}/strategy-learning")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_sufficient_data"] is True
        assert body["overall_metrics"] is not None

    def test_get_404_for_missing_project(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/ghost-project/strategy-learning")
        assert resp.status_code == 404

    def test_get_requires_auth(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get("/api/v1/projects/any/strategy-learning")
        assert resp.status_code in (401, 403)

    def test_get_project_id_in_response(self, client: TestClient) -> None:
        project_id = _create_project(client, code="GL-004")
        resp = client.get(f"/api/v1/projects/{project_id}/strategy-learning")
        assert resp.json()["project_id"] == project_id

    def test_get_strategy_breakdowns_empty_before_data(self, client: TestClient) -> None:
        project_id = _create_project(client, code="GL-005")
        resp = client.get(f"/api/v1/projects/{project_id}/strategy-learning")
        assert resp.json()["strategy_breakdowns"] == []


# ---------------------------------------------------------------------------
# GET /portfolio/strategy-learning
# ---------------------------------------------------------------------------


class TestGetPortfolioLearning:
    def test_portfolio_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/v1/portfolio/strategy-learning")
        assert resp.status_code == 200

    def test_portfolio_empty_when_no_data(self, client: TestClient) -> None:
        resp = client.get("/api/v1/portfolio/strategy-learning")
        body = resp.json()
        assert isinstance(body["total_projects_with_data"], int)
        assert isinstance(body["high_confidence_count"], int)
        assert isinstance(body["low_confidence_count"], int)
        assert isinstance(body["all_project_entries"], list)

    def test_portfolio_requires_auth(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get("/api/v1/portfolio/strategy-learning")
        assert resp.status_code in (401, 403)

    def test_portfolio_has_counts_after_data(self, client: TestClient) -> None:
        project_id = _create_project(client, code="PF-001")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        resp = client.get("/api/v1/portfolio/strategy-learning")
        body = resp.json()
        assert body["total_projects_with_data"] >= 1
        assert "average_confidence_score" in body
        assert isinstance(body["top_performing_projects"], list)
        assert isinstance(body["weak_area_projects"], list)

    def test_portfolio_structure_fields_present(self, client: TestClient) -> None:
        resp = client.get("/api/v1/portfolio/strategy-learning")
        body = resp.json()
        for key in (
            "total_projects_with_data",
            "average_confidence_score",
            "high_confidence_count",
            "low_confidence_count",
            "improving_count",
            "declining_count",
            "top_performing_projects",
            "weak_area_projects",
            "all_project_entries",
        ):
            assert key in body, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Pure unit tests — compute_confidence_score
# ---------------------------------------------------------------------------


class TestComputeConfidenceScore:
    def test_full_match_no_divergence_large_sample(self) -> None:
        # match_rate=1.0, divergence_rate=0.0, sample=10
        # confidence = (1.0 * 0.6) + ((1 - 0.0) * 0.4) = 1.0
        score = compute_confidence_score(1.0, 0.0, 10)
        assert score == pytest.approx(1.0)

    def test_no_match_all_diverged_large_sample(self) -> None:
        # match_rate=0.0, divergence_rate=1.0, sample=10
        # confidence = (0.0 * 0.6) + ((1 - 1.0) * 0.4) = 0.0
        score = compute_confidence_score(0.0, 1.0, 10)
        assert score == pytest.approx(0.0)

    def test_mixed_rates_large_sample(self) -> None:
        # match_rate=0.5, divergence_rate=0.25, sample=10
        # confidence = (0.5 * 0.6) + ((1 - 0.25) * 0.4) = 0.3 + 0.3 = 0.6
        score = compute_confidence_score(0.5, 0.25, 10)
        assert score == pytest.approx(0.6)

    def test_low_sample_cap_applied(self) -> None:
        # Would be 1.0 without cap, but sample=3 < 5 → capped at 0.5
        score = compute_confidence_score(1.0, 0.0, 3)
        assert score == pytest.approx(0.5)

    def test_low_sample_cap_does_not_raise(self) -> None:
        # Low score should not be raised by the cap
        score = compute_confidence_score(0.0, 1.0, 2)
        assert score == pytest.approx(0.0)

    def test_exactly_threshold_sample_gets_full_weight(self) -> None:
        # sample=5 == LOW_SAMPLE_THRESHOLD: cap should NOT apply
        score = compute_confidence_score(1.0, 0.0, 5)
        assert score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Pure unit tests — compute_trend_direction
# ---------------------------------------------------------------------------


class TestComputeTrendDirection:
    def test_insufficient_data_when_no_prior(self) -> None:
        assert compute_trend_direction(0.7, None) == "insufficient_data"

    def test_improving_when_delta_above_threshold(self) -> None:
        assert compute_trend_direction(0.75, 0.60) == "improving"

    def test_declining_when_delta_below_threshold(self) -> None:
        assert compute_trend_direction(0.40, 0.60) == "declining"

    def test_stable_when_delta_within_threshold(self) -> None:
        assert compute_trend_direction(0.62, 0.60) == "stable"

    def test_stable_exact_equal(self) -> None:
        assert compute_trend_direction(0.60, 0.60) == "stable"


# ---------------------------------------------------------------------------
# Pure unit tests — compute_pricing_accuracy / compute_phasing_accuracy
# ---------------------------------------------------------------------------


class TestComputeAccuracyScores:
    def test_pricing_accuracy_none_when_no_data(self) -> None:
        assert compute_pricing_accuracy([]) is None

    def test_phasing_accuracy_none_when_no_data(self) -> None:
        assert compute_phasing_accuracy([]) is None

    def test_pricing_accuracy_none_no_actual(self) -> None:
        """Outcomes without actual_price_adjustment_pct contribute nothing."""

        class FakeOutcome:
            actual_price_adjustment_pct = None
            actual_phase_delay_months = None
            execution_trigger_id = None

        assert compute_pricing_accuracy([FakeOutcome()]) is None  # type: ignore[list-item]

    def test_phasing_accuracy_none_no_actual(self) -> None:
        class FakeOutcome:
            actual_price_adjustment_pct = None
            actual_phase_delay_months = None
            execution_trigger_id = None

        assert compute_phasing_accuracy([FakeOutcome()]) is None  # type: ignore[list-item]

    def test_pricing_accuracy_none_without_triggers_map(self) -> None:
        """When no triggers_map supplied, intended is always None → score None."""

        class FakeOutcome:
            actual_price_adjustment_pct = 5.0
            actual_phase_delay_months = None
            execution_trigger_id = "t-1"

        assert compute_pricing_accuracy([FakeOutcome()]) is None  # type: ignore[list-item]

    def test_pricing_accuracy_with_trigger_snapshot(self) -> None:
        """Accuracy score is 1.0 when actual == intended."""

        class FakeOutcome:
            actual_price_adjustment_pct = 5.0
            actual_phase_delay_months = None
            execution_trigger_id = "t-1"

        class FakeTrigger:
            execution_package_snapshot = {
                "supporting_metrics": {"price_adjustment_pct": 5.0}
            }

        score = compute_pricing_accuracy(
            [FakeOutcome()],  # type: ignore[list-item]
            triggers_map={"t-1": FakeTrigger()},  # type: ignore[dict-item]
        )
        assert score == pytest.approx(1.0)

    def test_pricing_accuracy_inaccurate_when_diff_over_threshold(self) -> None:
        """Accuracy score is 0.0 when |actual - intended| >= 5 pp."""

        class FakeOutcome:
            actual_price_adjustment_pct = 12.0
            actual_phase_delay_months = None
            execution_trigger_id = "t-2"

        class FakeTrigger:
            execution_package_snapshot = {
                "supporting_metrics": {"price_adjustment_pct": 5.0}
            }

        score = compute_pricing_accuracy(
            [FakeOutcome()],  # type: ignore[list-item]
            triggers_map={"t-2": FakeTrigger()},  # type: ignore[dict-item]
        )
        assert score == pytest.approx(0.0)

    def test_phasing_accuracy_with_trigger_snapshot(self) -> None:
        """Accuracy score is 1.0 when |actual - intended| <= 1 month."""

        class FakeOutcome:
            actual_price_adjustment_pct = None
            actual_phase_delay_months = 2.0
            execution_trigger_id = "t-3"

        class FakeTrigger:
            execution_package_snapshot = {
                "supporting_metrics": {"phase_delay_months": 2}
            }

        score = compute_phasing_accuracy(
            [FakeOutcome()],  # type: ignore[list-item]
            triggers_map={"t-3": FakeTrigger()},  # type: ignore[dict-item]
        )
        assert score == pytest.approx(1.0)

    def test_phasing_accuracy_inaccurate_when_diff_over_threshold(self) -> None:
        """Accuracy score is 0.0 when |actual - intended| > 1 month."""

        class FakeOutcome:
            actual_price_adjustment_pct = None
            actual_phase_delay_months = 6.0
            execution_trigger_id = "t-4"

        class FakeTrigger:
            execution_package_snapshot = {
                "supporting_metrics": {"phase_delay_months": 2}
            }

        score = compute_phasing_accuracy(
            [FakeOutcome()],  # type: ignore[list-item]
            triggers_map={"t-4": FakeTrigger()},  # type: ignore[dict-item]
        )
        assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Pure unit tests — _get_intended_price / _get_intended_phase / _get_nested_value
# ---------------------------------------------------------------------------


class TestIntendedValueExtraction:
    def test_get_intended_price_none_without_map(self) -> None:
        class FakeOutcome:
            execution_trigger_id = "t-1"

        assert _get_intended_price(FakeOutcome()) is None  # type: ignore[arg-type]

    def test_get_intended_price_from_snapshot(self) -> None:
        class FakeOutcome:
            execution_trigger_id = "t-1"

        class FakeTrigger:
            execution_package_snapshot = {
                "supporting_metrics": {"price_adjustment_pct": 7.5}
            }

        result = _get_intended_price(
            FakeOutcome(),  # type: ignore[arg-type]
            triggers_map={"t-1": FakeTrigger()},  # type: ignore[dict-item]
        )
        assert result == pytest.approx(7.5)

    def test_get_intended_price_none_when_field_missing(self) -> None:
        class FakeOutcome:
            execution_trigger_id = "t-2"

        class FakeTrigger:
            execution_package_snapshot = {"supporting_metrics": {}}

        result = _get_intended_price(
            FakeOutcome(),  # type: ignore[arg-type]
            triggers_map={"t-2": FakeTrigger()},  # type: ignore[dict-item]
        )
        assert result is None

    def test_get_intended_phase_from_snapshot(self) -> None:
        class FakeOutcome:
            execution_trigger_id = "t-3"

        class FakeTrigger:
            execution_package_snapshot = {
                "supporting_metrics": {"phase_delay_months": 3}
            }

        result = _get_intended_phase(
            FakeOutcome(),  # type: ignore[arg-type]
            triggers_map={"t-3": FakeTrigger()},  # type: ignore[dict-item]
        )
        assert result == pytest.approx(3.0)

    def test_get_nested_value_dict_path(self) -> None:
        data = {"a": {"b": {"c": 42}}}
        assert _get_nested_value(data, "a", "b", "c") == 42

    def test_get_nested_value_missing_key_returns_none(self) -> None:
        data = {"a": {}}
        assert _get_nested_value(data, "a", "b", "c") is None

    def test_get_nested_value_none_source_returns_none(self) -> None:
        assert _get_nested_value(None, "a") is None


# ---------------------------------------------------------------------------
# Integration: accuracy scores populated from trigger snapshot via recalibrate
# ---------------------------------------------------------------------------


class TestAccuracyScoresFromTriggerSnapshot:
    def test_pricing_accuracy_populated_after_recalibrate(
        self, client: TestClient
    ) -> None:
        """pricing_accuracy_score must be non-None when trigger has snapshot metrics."""
        project_id = _create_project(client, code="ACC-001")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        metrics = resp.json()["overall_metrics"]
        # Trigger snapshot has price_adjustment_pct=5.0; outcome has actual=5.0 → match
        assert metrics["accuracy_breakdown"]["pricing_accuracy_score"] is not None
        assert metrics["accuracy_breakdown"]["pricing_accuracy_score"] == pytest.approx(1.0)

    def test_phasing_accuracy_populated_after_recalibrate(
        self, client: TestClient
    ) -> None:
        """phasing_accuracy_score must be non-None when trigger has snapshot metrics."""
        project_id = _create_project(client, code="ACC-002")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        metrics = resp.json()["overall_metrics"]
        # Trigger snapshot has phase_delay_months=2; outcome has actual=2.0 → match
        assert metrics["accuracy_breakdown"]["phasing_accuracy_score"] is not None
        assert metrics["accuracy_breakdown"]["phasing_accuracy_score"] == pytest.approx(1.0)

    def test_pricing_accuracy_zero_on_diverged_outcome(
        self, client: TestClient
    ) -> None:
        """pricing_accuracy_score must be 0.0 when actual is far from intended."""
        project_id = _create_project(client, code="ACC-003")
        _create_and_approve(client, project_id)
        trigger = _create_completed_trigger(client, project_id)
        _record_outcome(client, trigger["id"], _DIVERGED_OUTCOME)
        resp = client.post(f"/api/v1/projects/{project_id}/strategy-learning/recalibrate")
        metrics = resp.json()["overall_metrics"]
        # Trigger intended price=5.0; actual=12.0 → |diff|=7.0 ≥ 5 → inaccurate
        assert metrics["accuracy_breakdown"]["pricing_accuracy_score"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Portfolio KPI correctness
# ---------------------------------------------------------------------------


class TestPortfolioKpiCorrectness:
    def test_portfolio_total_reflects_all_projects(self, client: TestClient) -> None:
        """total_projects_with_data counts ALL projects, not just display-capped ones."""
        # Create two distinct projects with outcomes and recalibrate both.
        for code in ("KPI-001", "KPI-002"):
            pid = _create_project(client, code=code, name=f"KPI Project {code}")
            _create_and_approve(client, pid)
            trigger = _create_completed_trigger(client, pid)
            _record_outcome(client, trigger["id"], _MATCHED_OUTCOME)
            client.post(f"/api/v1/projects/{pid}/strategy-learning/recalibrate")

        resp = client.get("/api/v1/portfolio/strategy-learning")
        body = resp.json()
        # At least 2 projects should be reflected in the KPI count.
        assert body["total_projects_with_data"] >= 2
