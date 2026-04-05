"""
Tests for the Strategy Execution Outcome module (PR-V7-10).

Validates:
  POST /api/v1/execution-triggers/{id}/outcome
    - HTTP contract (201, 401, 404, 422)
    - Response schema shape — all required fields present
    - Outcome recorded with correct values
    - Outcome recorded for in_progress trigger
    - Outcome recorded for completed trigger
    - 422 when trigger is in 'triggered' state (not eligible)
    - 422 when trigger is 'cancelled' (not eligible)
    - 404 when trigger not found
    - Prior outcome superseded on re-recording
    - 401 when JWT sub missing

  GET /api/v1/projects/{id}/strategy-execution-outcome
    - HTTP contract (200, 404, auth required)
    - Returns project_id, trigger context, outcome_eligible flag
    - outcome_eligible True when trigger is in_progress or completed
    - outcome_eligible False when trigger is triggered
    - outcome_eligible False when no trigger exists
    - Returns null latest_outcome when none recorded
    - Returns latest outcome when recorded

  GET /api/v1/portfolio/execution-outcomes
    - HTTP contract (200, auth required)
    - Returns outcome result counts
    - Returns awaiting_outcome_count for completed triggers without outcomes
    - Returns recent_outcomes list

  Pure unit tests (no DB/HTTP):
    - compare_intended_vs_realized: exact_match
    - compare_intended_vs_realized: minor_variance (price)
    - compare_intended_vs_realized: major_variance (price)
    - compare_intended_vs_realized: major_variance (phase)
    - compare_intended_vs_realized: major_variance (release strategy)
    - compare_intended_vs_realized: no_comparable_strategy (no snapshot metrics)
    - compare_intended_vs_realized: execution_quality mapping
    - compare_intended_vs_realized: has_material_divergence
"""

import pytest
from fastapi.testclient import TestClient

from app.modules.strategy_execution_outcome.service import compare_intended_vs_realized
from app.modules.auth.security import get_current_user_payload
from app.main import app


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

_STRATEGY_SNAPSHOT = {
    "recommended_strategy": "maintain",
    "best_irr": 0.15,
    "risk_score": "medium",
}

_EXECUTION_PACKAGE_SNAPSHOT_WITH_METRICS = {
    "execution_readiness": "ready_for_review",
    "supporting_metrics": {
        "price_adjustment_pct": 5.0,
        "phase_delay_months": 2,
        "release_strategy": "maintain",
    },
    "actions": [{"step_number": 1, "action_type": "simulation_review"}],
}

_EXECUTION_PACKAGE_SNAPSHOT_NO_METRICS = {
    "execution_readiness": "ready_for_review",
    "actions": [{"step_number": 1, "action_type": "simulation_review"}],
}

_RECORD_OUTCOME_BODY = {
    "outcome_result": "matched_strategy",
    "actual_price_adjustment_pct": 5.0,
    "actual_phase_delay_months": 2.0,
    "actual_release_strategy": "maintain",
    "execution_summary": "All actions completed as planned.",
    "outcome_notes": "No deviations observed.",
}


def _create_project(
    client: TestClient, code: str = "OUT-001", name: str = "Outcome Project"
) -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_approval(
    client: TestClient,
    project_id: str,
    execution_package_snapshot: dict | None = None,
) -> dict:
    pkg = execution_package_snapshot or _EXECUTION_PACKAGE_SNAPSHOT_WITH_METRICS
    resp = client.post(
        f"/api/v1/projects/{project_id}/strategy-approval",
        json={
            "strategy_snapshot": _STRATEGY_SNAPSHOT,
            "execution_package_snapshot": pkg,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _approve(client: TestClient, approval_id: str) -> dict:
    resp = client.post(f"/api/v1/approvals/{approval_id}/approve")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _create_trigger(client: TestClient, project_id: str) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/strategy-execution-trigger"
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _setup_approved_project(
    client: TestClient,
    code: str = "OUT-001",
    name: str = "Outcome Project",
    execution_package_snapshot: dict | None = None,
) -> tuple[str, dict]:
    """Create a project + approved strategy. Returns (project_id, approval_dict)."""
    project_id = _create_project(client, code=code, name=name)
    approval = _create_approval(
        client, project_id, execution_package_snapshot=execution_package_snapshot
    )
    _approve(client, approval["id"])
    return project_id, approval


def _setup_trigger_in_progress(
    client: TestClient,
    code: str = "OUT-001",
    name: str = "Outcome Project",
) -> tuple[str, dict]:
    """Returns (project_id, trigger_dict) with trigger in in_progress state."""
    project_id, _ = _setup_approved_project(client, code=code, name=name)
    trigger = _create_trigger(client, project_id)
    client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
    trigger_data = client.get(
        f"/api/v1/projects/{project_id}/strategy-execution-trigger"
    ).json()
    return project_id, trigger_data


def _setup_trigger_completed(
    client: TestClient,
    code: str = "OUT-001",
    name: str = "Outcome Project",
) -> tuple[str, dict]:
    """Returns (project_id, trigger_dict) with trigger in completed state."""
    project_id, _ = _setup_approved_project(client, code=code, name=name)
    trigger = _create_trigger(client, project_id)
    client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
    client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
    trigger_data = client.get(
        f"/api/v1/projects/{project_id}/strategy-execution-trigger"
    ).json()
    return project_id, trigger_data


# ---------------------------------------------------------------------------
# POST /execution-triggers/{id}/outcome
# ---------------------------------------------------------------------------


class TestRecordExecutionOutcome:
    def test_record_outcome_returns_201(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="RO-001")
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        assert resp.status_code == 201

    def test_record_for_completed_trigger_returns_201(
        self, client: TestClient
    ) -> None:
        _, trigger = _setup_trigger_completed(client, code="RO-002")
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        assert resp.status_code == 201

    def test_response_schema_shape(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="RO-003")
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        data = resp.json()
        assert "id" in data
        assert "project_id" in data
        assert "execution_trigger_id" in data
        assert "approval_id" in data
        assert "status" in data
        assert "outcome_result" in data
        assert "actual_price_adjustment_pct" in data
        assert "actual_phase_delay_months" in data
        assert "actual_release_strategy" in data
        assert "execution_summary" in data
        assert "outcome_notes" in data
        assert "recorded_by_user_id" in data
        assert "recorded_at" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "comparison" in data
        assert "has_material_divergence" in data

    def test_comparison_block_shape(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="RO-004")
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        cmp = resp.json()["comparison"]
        assert "intended_price_adjustment_pct" in cmp
        assert "actual_price_adjustment_pct" in cmp
        assert "intended_phase_delay_months" in cmp
        assert "actual_phase_delay_months" in cmp
        assert "intended_release_strategy" in cmp
        assert "actual_release_strategy" in cmp
        assert "match_status" in cmp
        assert "divergence_summary" in cmp
        assert "execution_quality" in cmp
        assert "has_material_divergence" in cmp

    def test_outcome_result_stored(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="RO-005")
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json={**_RECORD_OUTCOME_BODY, "outcome_result": "partially_matched"},
        )
        assert resp.json()["outcome_result"] == "partially_matched"

    def test_actual_values_stored(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="RO-006")
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        data = resp.json()
        assert data["actual_price_adjustment_pct"] == 5.0
        assert data["actual_phase_delay_months"] == 2.0
        assert data["actual_release_strategy"] == "maintain"

    def test_recorded_by_from_jwt(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="RO-007")
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        assert resp.json()["recorded_by_user_id"] == "test-user"

    def test_trigger_id_populated(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="RO-008")
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        assert resp.json()["execution_trigger_id"] == trigger["id"]

    def test_status_is_recorded(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="RO-009")
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        assert resp.json()["status"] == "recorded"

    def test_422_when_trigger_is_triggered_state(self, client: TestClient) -> None:
        project_id, _ = _setup_approved_project(client, code="RO-010")
        trigger = _create_trigger(client, project_id)
        # Trigger is in 'triggered' state — not eligible
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        assert resp.status_code == 422

    def test_422_when_trigger_is_cancelled(self, client: TestClient) -> None:
        project_id, _ = _setup_approved_project(client, code="RO-011")
        trigger = _create_trigger(client, project_id)
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Not needed"},
        )
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        assert resp.status_code == 422

    def test_404_when_trigger_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/execution-triggers/nonexistent-id/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        assert resp.status_code == 404

    def test_re_recording_supersedes_prior_outcome(
        self, client: TestClient
    ) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="RO-012")
        # First recording
        resp1 = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        assert resp1.status_code == 201
        first_id = resp1.json()["id"]

        # Second recording — supersedes the first
        resp2 = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json={**_RECORD_OUTCOME_BODY, "outcome_result": "diverged"},
        )
        assert resp2.status_code == 201
        second_id = resp2.json()["id"]

        # The two records must have different IDs
        assert first_id != second_id

        # The new record is the active one (status=recorded)
        assert resp2.json()["status"] == "recorded"

    def test_project_outcome_reflects_latest_after_re_recording(
        self, client: TestClient
    ) -> None:
        project_id, trigger = _setup_trigger_in_progress(client, code="RO-013")
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json={**_RECORD_OUTCOME_BODY, "outcome_result": "partially_matched"},
        )
        project_resp = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-outcome"
        )
        assert project_resp.status_code == 200
        latest = project_resp.json()["latest_outcome"]
        assert latest is not None
        assert latest["outcome_result"] == "partially_matched"

    def test_401_when_jwt_sub_missing(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="RO-014")
        previous_override = app.dependency_overrides.get(get_current_user_payload)
        app.dependency_overrides[get_current_user_payload] = lambda: {
            "roles": ["admin"]
        }
        try:
            resp = client.post(
                f"/api/v1/execution-triggers/{trigger['id']}/outcome",
                json=_RECORD_OUTCOME_BODY,
            )
            assert resp.status_code == 401
        finally:
            if previous_override is None:
                app.dependency_overrides.pop(get_current_user_payload, None)
            else:
                app.dependency_overrides[get_current_user_payload] = previous_override

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post(
            "/api/v1/execution-triggers/some-id/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /projects/{id}/strategy-execution-outcome
# ---------------------------------------------------------------------------


class TestGetProjectExecutionOutcome:
    def test_returns_200(self, client: TestClient) -> None:
        project_id, _ = _setup_approved_project(client, code="PO-001")
        resp = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-outcome"
        )
        assert resp.status_code == 200

    def test_response_schema_shape(self, client: TestClient) -> None:
        project_id, _ = _setup_approved_project(client, code="PO-002")
        data = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-outcome"
        ).json()
        assert "project_id" in data
        assert "execution_trigger_id" in data
        assert "trigger_status" in data
        assert "outcome_eligible" in data
        assert "latest_outcome" in data

    def test_no_trigger_returns_null_trigger_context(
        self, client: TestClient
    ) -> None:
        project_id, _ = _setup_approved_project(client, code="PO-003")
        data = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-outcome"
        ).json()
        assert data["execution_trigger_id"] is None
        assert data["trigger_status"] is None
        assert data["outcome_eligible"] is False
        assert data["latest_outcome"] is None

    def test_outcome_eligible_false_for_triggered_state(
        self, client: TestClient
    ) -> None:
        project_id, _ = _setup_approved_project(client, code="PO-004")
        trigger = _create_trigger(client, project_id)
        assert trigger["status"] == "triggered"
        data = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-outcome"
        ).json()
        assert data["outcome_eligible"] is False

    def test_outcome_eligible_true_for_in_progress(
        self, client: TestClient
    ) -> None:
        project_id, trigger = _setup_trigger_in_progress(client, code="PO-005")
        data = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-outcome"
        ).json()
        assert data["outcome_eligible"] is True

    def test_outcome_eligible_true_for_completed(
        self, client: TestClient
    ) -> None:
        project_id, trigger = _setup_trigger_completed(client, code="PO-006")
        data = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-outcome"
        ).json()
        assert data["outcome_eligible"] is True

    def test_outcome_eligible_false_for_cancelled(
        self, client: TestClient
    ) -> None:
        project_id, _ = _setup_approved_project(client, code="PO-007")
        trigger = _create_trigger(client, project_id)
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "No longer needed"},
        )
        data = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-outcome"
        ).json()
        assert data["outcome_eligible"] is False

    def test_latest_outcome_null_when_not_recorded(
        self, client: TestClient
    ) -> None:
        project_id, trigger = _setup_trigger_in_progress(client, code="PO-008")
        data = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-outcome"
        ).json()
        assert data["latest_outcome"] is None

    def test_latest_outcome_populated_after_recording(
        self, client: TestClient
    ) -> None:
        project_id, trigger = _setup_trigger_in_progress(client, code="PO-009")
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        data = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-outcome"
        ).json()
        assert data["latest_outcome"] is not None
        assert data["latest_outcome"]["outcome_result"] == "matched_strategy"

    def test_trigger_status_reflected(self, client: TestClient) -> None:
        project_id, trigger = _setup_trigger_in_progress(client, code="PO-010")
        data = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-outcome"
        ).json()
        assert data["trigger_status"] == "in_progress"

    def test_404_when_project_not_found(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/projects/nonexistent-id/strategy-execution-outcome"
        )
        assert resp.status_code == 404

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get(
            "/api/v1/projects/some-id/strategy-execution-outcome"
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /portfolio/execution-outcomes
# ---------------------------------------------------------------------------


class TestGetPortfolioExecutionOutcomes:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/v1/portfolio/execution-outcomes")
        assert resp.status_code == 200

    def test_response_schema_shape(self, client: TestClient) -> None:
        data = client.get("/api/v1/portfolio/execution-outcomes").json()
        assert "matched_strategy_count" in data
        assert "partially_matched_count" in data
        assert "diverged_count" in data
        assert "cancelled_execution_count" in data
        assert "insufficient_data_count" in data
        assert "awaiting_outcome_count" in data
        assert "recent_outcomes" in data
        assert "awaiting_outcome_projects" in data

    def test_counts_start_at_zero(self, client: TestClient) -> None:
        data = client.get("/api/v1/portfolio/execution-outcomes").json()
        assert data["matched_strategy_count"] == 0
        assert data["partially_matched_count"] == 0
        assert data["diverged_count"] == 0
        assert data["cancelled_execution_count"] == 0
        assert data["insufficient_data_count"] == 0
        assert data["awaiting_outcome_count"] == 0
        assert data["recent_outcomes"] == []
        assert data["awaiting_outcome_projects"] == []

    def test_matched_strategy_count_increments(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="PORT-001")
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json={**_RECORD_OUTCOME_BODY, "outcome_result": "matched_strategy"},
        )
        data = client.get("/api/v1/portfolio/execution-outcomes").json()
        assert data["matched_strategy_count"] == 1

    def test_diverged_count_increments(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="PORT-002")
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json={**_RECORD_OUTCOME_BODY, "outcome_result": "diverged"},
        )
        data = client.get("/api/v1/portfolio/execution-outcomes").json()
        assert data["diverged_count"] == 1

    def test_awaiting_outcome_count_for_completed_trigger(
        self, client: TestClient
    ) -> None:
        _setup_trigger_completed(client, code="PORT-003")
        data = client.get("/api/v1/portfolio/execution-outcomes").json()
        assert data["awaiting_outcome_count"] == 1

    def test_awaiting_count_decrements_after_recording(
        self, client: TestClient
    ) -> None:
        _, trigger = _setup_trigger_completed(client, code="PORT-004")
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        data = client.get("/api/v1/portfolio/execution-outcomes").json()
        assert data["awaiting_outcome_count"] == 0

    def test_recent_outcomes_populated(self, client: TestClient) -> None:
        _, trigger = _setup_trigger_in_progress(client, code="PORT-005")
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/outcome",
            json=_RECORD_OUTCOME_BODY,
        )
        data = client.get("/api/v1/portfolio/execution-outcomes").json()
        assert len(data["recent_outcomes"]) == 1
        entry = data["recent_outcomes"][0]
        assert "project_id" in entry
        assert "project_name" in entry
        assert "outcome" in entry
        assert "comparison" in entry["outcome"]

    def test_awaiting_outcome_projects_listed(self, client: TestClient) -> None:
        _setup_trigger_completed(client, code="PORT-006", name="Awaiting Project")
        data = client.get("/api/v1/portfolio/execution-outcomes").json()
        assert len(data["awaiting_outcome_projects"]) == 1
        entry = data["awaiting_outcome_projects"][0]
        assert "project_id" in entry
        assert "project_name" in entry
        assert "trigger_id" in entry

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get("/api/v1/portfolio/execution-outcomes")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Pure unit tests — compare_intended_vs_realized (no DB/HTTP)
# ---------------------------------------------------------------------------


class _TriggerStub:
    """Minimal trigger stub for unit-testing compare_intended_vs_realized."""

    def __init__(self, pkg_snapshot: dict | None) -> None:
        self.execution_package_snapshot = pkg_snapshot


class _OutcomeStub:
    """Minimal outcome stub for unit-testing compare_intended_vs_realized."""

    def __init__(self, **kwargs) -> None:
        self.actual_price_adjustment_pct = kwargs.get("actual_price_adjustment_pct")
        self.actual_phase_delay_months = kwargs.get("actual_phase_delay_months")
        self.actual_release_strategy = kwargs.get("actual_release_strategy")


def _make_trigger(pkg_snapshot: dict | None) -> _TriggerStub:
    """Build a minimal trigger stub for comparison tests."""
    return _TriggerStub(pkg_snapshot)


def _make_outcome(**kwargs) -> _OutcomeStub:
    """Build a minimal outcome stub for comparison tests."""
    return _OutcomeStub(**kwargs)


class TestCompareIntendedVsRealized:
    def test_exact_match_when_all_values_match(self) -> None:
        trigger = _make_trigger(
            {
                "supporting_metrics": {
                    "price_adjustment_pct": 5.0,
                    "phase_delay_months": 2,
                    "release_strategy": "maintain",
                }
            }
        )
        outcome = _make_outcome(
            actual_price_adjustment_pct=5.0,
            actual_phase_delay_months=2.0,
            actual_release_strategy="maintain",
        )
        result = compare_intended_vs_realized(trigger, outcome)
        assert result.match_status == "exact_match"
        assert result.execution_quality == "high"
        assert result.has_material_divergence is False

    def test_minor_variance_for_small_price_diff(self) -> None:
        trigger = _make_trigger(
            {"supporting_metrics": {"price_adjustment_pct": 5.0}}
        )
        outcome = _make_outcome(actual_price_adjustment_pct=7.0)
        result = compare_intended_vs_realized(trigger, outcome)
        assert result.match_status == "minor_variance"
        assert result.execution_quality == "medium"
        assert result.has_material_divergence is False

    def test_major_variance_for_large_price_diff(self) -> None:
        trigger = _make_trigger(
            {"supporting_metrics": {"price_adjustment_pct": 0.0}}
        )
        outcome = _make_outcome(actual_price_adjustment_pct=10.0)
        result = compare_intended_vs_realized(trigger, outcome)
        assert result.match_status == "major_variance"
        assert result.execution_quality == "low"
        assert result.has_material_divergence is True

    def test_exact_match_for_zero_phase_diff(self) -> None:
        trigger = _make_trigger(
            {"supporting_metrics": {"phase_delay_months": 3}}
        )
        outcome = _make_outcome(actual_phase_delay_months=3.0)
        result = compare_intended_vs_realized(trigger, outcome)
        assert result.match_status == "exact_match"

    def test_minor_variance_for_one_month_phase_diff(self) -> None:
        trigger = _make_trigger(
            {"supporting_metrics": {"phase_delay_months": 2}}
        )
        outcome = _make_outcome(actual_phase_delay_months=3.0)
        result = compare_intended_vs_realized(trigger, outcome)
        assert result.match_status == "minor_variance"

    def test_major_variance_for_large_phase_diff(self) -> None:
        trigger = _make_trigger(
            {"supporting_metrics": {"phase_delay_months": 1}}
        )
        outcome = _make_outcome(actual_phase_delay_months=5.0)
        result = compare_intended_vs_realized(trigger, outcome)
        assert result.match_status == "major_variance"
        assert result.has_material_divergence is True

    def test_major_variance_for_mismatched_release_strategy(self) -> None:
        trigger = _make_trigger(
            {"supporting_metrics": {"release_strategy": "hold"}}
        )
        outcome = _make_outcome(actual_release_strategy="accelerate")
        result = compare_intended_vs_realized(trigger, outcome)
        assert result.match_status == "major_variance"
        assert result.has_material_divergence is True

    def test_no_comparable_strategy_when_trigger_is_none(self) -> None:
        outcome = _make_outcome(actual_price_adjustment_pct=5.0)
        result = compare_intended_vs_realized(None, outcome)
        assert result.match_status == "no_comparable_strategy"
        assert result.execution_quality == "unknown"
        assert result.has_material_divergence is False

    def test_no_comparable_strategy_when_no_metrics_in_snapshot(self) -> None:
        trigger = _make_trigger(
            {"execution_readiness": "ready_for_review", "actions": []}
        )
        outcome = _make_outcome(actual_price_adjustment_pct=5.0)
        result = compare_intended_vs_realized(trigger, outcome)
        assert result.match_status == "no_comparable_strategy"

    def test_no_comparable_strategy_when_snapshot_is_none(self) -> None:
        trigger = _make_trigger(None)
        outcome = _make_outcome(actual_price_adjustment_pct=5.0)
        result = compare_intended_vs_realized(trigger, outcome)
        assert result.match_status == "no_comparable_strategy"

    def test_worst_case_wins_across_fields(self) -> None:
        # Price is minor, release strategy is major → overall major_variance
        trigger = _make_trigger(
            {
                "supporting_metrics": {
                    "price_adjustment_pct": 5.0,
                    "release_strategy": "hold",
                }
            }
        )
        outcome = _make_outcome(
            actual_price_adjustment_pct=7.0,  # minor
            actual_release_strategy="accelerate",  # major
        )
        result = compare_intended_vs_realized(trigger, outcome)
        assert result.match_status == "major_variance"

    def test_intended_values_extracted_from_snapshot(self) -> None:
        trigger = _make_trigger(
            {
                "supporting_metrics": {
                    "price_adjustment_pct": 8.5,
                    "phase_delay_months": 3,
                    "release_strategy": "hold",
                }
            }
        )
        outcome = _make_outcome()
        result = compare_intended_vs_realized(trigger, outcome)
        assert result.intended_price_adjustment_pct == 8.5
        assert result.intended_phase_delay_months == 3.0
        assert result.intended_release_strategy == "hold"

    def test_divergence_summary_for_exact_match(self) -> None:
        trigger = _make_trigger(
            {"supporting_metrics": {"release_strategy": "maintain"}}
        )
        outcome = _make_outcome(actual_release_strategy="maintain")
        result = compare_intended_vs_realized(trigger, outcome)
        assert "matches" in result.divergence_summary.lower()

    def test_divergence_summary_for_variance(self) -> None:
        trigger = _make_trigger(
            {"supporting_metrics": {"release_strategy": "hold"}}
        )
        outcome = _make_outcome(actual_release_strategy="accelerate")
        result = compare_intended_vs_realized(trigger, outcome)
        assert "divergence" in result.divergence_summary.lower()
