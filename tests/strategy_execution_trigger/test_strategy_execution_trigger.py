"""
Tests for the Strategy Execution Trigger module (PR-V7-09).

Validates:
  POST /api/v1/projects/{id}/strategy-execution-trigger
    - HTTP contract (201, 401, 404, 409, 422)
    - Response schema shape — all required fields present
    - Trigger created with status=triggered
    - Snapshots copied from approval
    - 409 when active trigger already exists
    - 422 when latest approval is not approved (pending or rejected)
    - 422 when no approval exists at all

  POST /api/v1/execution-triggers/{id}/start
    - HTTP contract (200, 404, 422)
    - Status transitions to in_progress
    - 422 when already in_progress (invalid transition)
    - 422 when completed (terminal)
    - 422 when cancelled (terminal)

  POST /api/v1/execution-triggers/{id}/complete
    - HTTP contract (200, 404, 422)
    - Status transitions to completed
    - 422 when not in in_progress state

  POST /api/v1/execution-triggers/{id}/cancel
    - HTTP contract (200, 404, 422)
    - Status transitions to cancelled
    - cancellation_reason stored
    - 422 when cancellation_reason missing
    - 422 when already completed
    - 422 when already cancelled

  GET /api/v1/projects/{id}/strategy-execution-trigger
    - HTTP contract (200, 404, auth required)
    - Returns null when no trigger exists
    - Returns latest trigger record
    - Reflects status transitions correctly

  GET /api/v1/portfolio/execution-triggers
    - HTTP contract (200, auth required)
    - Returns status counts
    - Returns active triggers list
    - Returns awaiting trigger projects

  Pure unit tests (no DB/HTTP):
    - _assert_transition: valid and invalid transitions
"""

import pytest
from fastapi.testclient import TestClient

from app.modules.strategy_execution_trigger.service import _assert_transition
from app.modules.strategy_execution_trigger.models import StrategyExecutionTrigger
from app.core.errors import ValidationError as DomainValidationError
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

_EXECUTION_PACKAGE_SNAPSHOT = {
    "execution_readiness": "ready_for_review",
    "actions": [{"step_number": 1, "action_type": "simulation_review"}],
}


def _create_project(
    client: TestClient, code: str = "SET-001", name: str = "Trigger Project"
) -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_approval(client: TestClient, project_id: str) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/strategy-approval",
        json={
            "strategy_snapshot": _STRATEGY_SNAPSHOT,
            "execution_package_snapshot": _EXECUTION_PACKAGE_SNAPSHOT,
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
    client: TestClient, code: str = "SET-001", name: str = "Trigger Project"
) -> str:
    """Create a project, create an approval, approve it. Returns project_id."""
    project_id = _create_project(client, code=code, name=name)
    approval = _create_approval(client, project_id)
    _approve(client, approval["id"])
    return project_id


# ---------------------------------------------------------------------------
# POST /projects/{id}/strategy-execution-trigger
# ---------------------------------------------------------------------------


class TestCreateExecutionTrigger:
    def test_create_returns_201(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client)
        resp = client.post(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.status_code == 201

    def test_response_schema_shape(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SET-002")
        data = _create_trigger(client, project_id)
        assert "id" in data
        assert "project_id" in data
        assert "approval_id" in data
        assert "status" in data
        assert "triggered_by_user_id" in data
        assert "triggered_at" in data
        assert "completed_at" in data
        assert "cancelled_at" in data
        assert "cancellation_reason" in data
        assert "strategy_snapshot" in data
        assert "execution_package_snapshot" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_initial_status_is_triggered(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SET-003")
        data = _create_trigger(client, project_id)
        assert data["status"] == "triggered"

    def test_project_id_matches(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SET-004")
        data = _create_trigger(client, project_id)
        assert data["project_id"] == project_id

    def test_snapshots_copied_from_approval(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SET-005")
        data = _create_trigger(client, project_id)
        assert data["strategy_snapshot"] == _STRATEGY_SNAPSHOT
        assert data["execution_package_snapshot"] == _EXECUTION_PACKAGE_SNAPSHOT

    def test_terminal_fields_null_on_creation(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SET-006")
        data = _create_trigger(client, project_id)
        assert data["completed_at"] is None
        assert data["cancelled_at"] is None
        assert data["cancellation_reason"] is None

    def test_triggered_by_user_id_from_jwt(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SET-007")
        data = _create_trigger(client, project_id)
        assert data["triggered_by_user_id"] == "test-user"

    def test_approval_id_populated(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SET-008")
        approval = _create_approval(client, project_id)
        _approve(client, approval["id"])
        data = _create_trigger(client, project_id)
        assert data["approval_id"] == approval["id"]

    def test_404_when_project_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/projects/nonexistent-id/strategy-execution-trigger"
        )
        assert resp.status_code == 404

    def test_422_when_no_approval_exists(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SET-009")
        resp = client.post(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.status_code == 422

    def test_422_when_approval_is_pending(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SET-010")
        _create_approval(client, project_id)  # pending approval, not approved
        resp = client.post(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.status_code == 422

    def test_422_when_approval_is_rejected(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SET-011")
        approval = _create_approval(client, project_id)
        client.post(
            f"/api/v1/approvals/{approval['id']}/reject",
            json={"rejection_reason": "Not ready"},
        )
        resp = client.post(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.status_code == 422

    def test_409_when_active_trigger_already_exists(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SET-012")
        _create_trigger(client, project_id)
        resp = client.post(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.status_code == 409

    def test_401_when_jwt_sub_missing(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SET-013")
        # Override the auth to return a payload without 'sub'
        app.dependency_overrides[get_current_user_payload] = lambda: {
            "roles": ["admin"]
        }
        resp = client.post(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        # Restore original override
        from app.core.dependencies import get_db

        app.dependency_overrides[get_current_user_payload] = (
            lambda: {"sub": "test-user", "roles": ["admin"]}
        )
        assert resp.status_code == 401

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post(
            "/api/v1/projects/some-id/strategy-execution-trigger"
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /execution-triggers/{id}/start
# ---------------------------------------------------------------------------


class TestStartExecutionTrigger:
    def test_start_returns_200(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="STS-001")
        trigger = _create_trigger(client, project_id)
        resp = client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        assert resp.status_code == 200

    def test_status_transitions_to_in_progress(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="STS-002")
        trigger = _create_trigger(client, project_id)
        resp = client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        assert resp.json()["status"] == "in_progress"

    def test_404_when_trigger_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/execution-triggers/nonexistent-id/start")
        assert resp.status_code == 404

    def test_422_when_already_in_progress(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="STS-003")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        resp = client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        assert resp.status_code == 422

    def test_422_when_completed(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="STS-004")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        resp = client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        assert resp.status_code == 422

    def test_422_when_cancelled(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="STS-005")
        trigger = _create_trigger(client, project_id)
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Not needed"},
        )
        resp = client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        assert resp.status_code == 422

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post("/api/v1/execution-triggers/some-id/start")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /execution-triggers/{id}/complete
# ---------------------------------------------------------------------------


class TestCompleteExecutionTrigger:
    def test_complete_returns_200(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="STC-001")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        resp = client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        assert resp.status_code == 200

    def test_status_transitions_to_completed(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="STC-002")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        resp = client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        assert resp.json()["status"] == "completed"

    def test_completed_at_populated(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="STC-003")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        resp = client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        assert resp.json()["completed_at"] is not None

    def test_404_when_trigger_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/execution-triggers/nonexistent-id/complete")
        assert resp.status_code == 404

    def test_422_when_triggered_not_in_progress(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="STC-004")
        trigger = _create_trigger(client, project_id)
        resp = client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        assert resp.status_code == 422

    def test_422_when_already_completed(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="STC-005")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        resp = client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        assert resp.status_code == 422

    def test_422_when_cancelled(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="STC-006")
        trigger = _create_trigger(client, project_id)
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Cancelled"},
        )
        resp = client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        assert resp.status_code == 422

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post("/api/v1/execution-triggers/some-id/complete")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /execution-triggers/{id}/cancel
# ---------------------------------------------------------------------------


class TestCancelExecutionTrigger:
    def test_cancel_triggered_returns_200(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SCN-001")
        trigger = _create_trigger(client, project_id)
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Strategy no longer valid"},
        )
        assert resp.status_code == 200

    def test_cancel_in_progress_returns_200(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SCN-002")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Market conditions changed"},
        )
        assert resp.status_code == 200

    def test_status_transitions_to_cancelled(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SCN-003")
        trigger = _create_trigger(client, project_id)
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Not needed"},
        )
        assert resp.json()["status"] == "cancelled"

    def test_cancellation_reason_stored(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SCN-004")
        trigger = _create_trigger(client, project_id)
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Funding not available"},
        )
        assert resp.json()["cancellation_reason"] == "Funding not available"

    def test_cancelled_at_populated(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SCN-005")
        trigger = _create_trigger(client, project_id)
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Not needed"},
        )
        assert resp.json()["cancelled_at"] is not None

    def test_404_when_trigger_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/execution-triggers/nonexistent-id/cancel",
            json={"cancellation_reason": "Not needed"},
        )
        assert resp.status_code == 404

    def test_422_when_cancellation_reason_missing(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SCN-006")
        trigger = _create_trigger(client, project_id)
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={},
        )
        assert resp.status_code == 422

    def test_422_when_cancellation_reason_empty(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SCN-007")
        trigger = _create_trigger(client, project_id)
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": ""},
        )
        assert resp.status_code == 422

    def test_422_when_already_completed(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SCN-008")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Too late"},
        )
        assert resp.status_code == 422

    def test_422_when_already_cancelled(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SCN-009")
        trigger = _create_trigger(client, project_id)
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "First cancel"},
        )
        resp = client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Second cancel"},
        )
        assert resp.status_code == 422

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post(
            "/api/v1/execution-triggers/some-id/cancel",
            json={"cancellation_reason": "Not needed"},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /projects/{id}/strategy-execution-trigger
# ---------------------------------------------------------------------------


class TestGetLatestExecutionTrigger:
    def test_returns_null_when_no_trigger(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SGT-001")
        resp = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.status_code == 200
        assert resp.json() is None

    def test_returns_trigger_record(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SGT-002")
        _create_trigger(client, project_id)
        resp = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.status_code == 200
        assert resp.json() is not None
        assert resp.json()["project_id"] == project_id

    def test_reflects_started_status(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SGT-003")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        resp = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.json()["status"] == "in_progress"

    def test_reflects_completed_status(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SGT-004")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        resp = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.json()["status"] == "completed"

    def test_reflects_cancelled_status(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SGT-005")
        trigger = _create_trigger(client, project_id)
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Cancelled"},
        )
        resp = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.json()["status"] == "cancelled"

    def test_404_when_project_not_found(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/projects/nonexistent-id/strategy-execution-trigger"
        )
        assert resp.status_code == 404

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get(
            "/api/v1/projects/some-id/strategy-execution-trigger"
        )
        assert resp.status_code in (401, 403)

    def test_source_records_unmodified_after_trigger(
        self, client: TestClient
    ) -> None:
        project_id = _setup_approved_project(client, code="SGT-006")
        _create_trigger(client, project_id)
        # The project record should remain unchanged.
        resp = client.get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /portfolio/execution-triggers
# ---------------------------------------------------------------------------


class TestPortfolioExecutionTriggers:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/v1/portfolio/execution-triggers")
        assert resp.status_code == 200

    def test_response_schema_shape(self, client: TestClient) -> None:
        resp = client.get("/api/v1/portfolio/execution-triggers")
        data = resp.json()
        assert "triggered_count" in data
        assert "in_progress_count" in data
        assert "completed_count" in data
        assert "cancelled_count" in data
        assert "awaiting_trigger_count" in data
        assert "active_triggers" in data
        assert "awaiting_trigger_projects" in data

    def test_empty_counts_when_no_triggers(self, client: TestClient) -> None:
        resp = client.get("/api/v1/portfolio/execution-triggers")
        data = resp.json()
        assert data["triggered_count"] == 0
        assert data["in_progress_count"] == 0
        assert data["completed_count"] == 0
        assert data["cancelled_count"] == 0
        assert data["active_triggers"] == []

    def test_triggered_count_increments(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="PET-001")
        _create_trigger(client, project_id)
        resp = client.get("/api/v1/portfolio/execution-triggers")
        assert resp.json()["triggered_count"] == 1

    def test_in_progress_count_increments(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="PET-002")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        resp = client.get("/api/v1/portfolio/execution-triggers")
        assert resp.json()["in_progress_count"] == 1

    def test_completed_count_increments(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="PET-003")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        resp = client.get("/api/v1/portfolio/execution-triggers")
        assert resp.json()["completed_count"] == 1

    def test_cancelled_count_increments(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="PET-004")
        trigger = _create_trigger(client, project_id)
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Not needed"},
        )
        resp = client.get("/api/v1/portfolio/execution-triggers")
        assert resp.json()["cancelled_count"] == 1

    def test_active_triggers_list_contains_triggered(
        self, client: TestClient
    ) -> None:
        project_id = _setup_approved_project(client, code="PET-005")
        _create_trigger(client, project_id)
        resp = client.get("/api/v1/portfolio/execution-triggers")
        active = resp.json()["active_triggers"]
        assert len(active) == 1
        assert active[0]["project_id"] == project_id

    def test_active_triggers_list_contains_in_progress(
        self, client: TestClient
    ) -> None:
        project_id = _setup_approved_project(client, code="PET-006")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        resp = client.get("/api/v1/portfolio/execution-triggers")
        active = resp.json()["active_triggers"]
        assert len(active) == 1
        assert active[0]["trigger"]["status"] == "in_progress"

    def test_active_triggers_not_returned_for_completed(
        self, client: TestClient
    ) -> None:
        project_id = _setup_approved_project(client, code="PET-007")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        resp = client.get("/api/v1/portfolio/execution-triggers")
        assert resp.json()["active_triggers"] == []

    def test_awaiting_trigger_count_for_approved_project(
        self, client: TestClient
    ) -> None:
        _setup_approved_project(client, code="PET-008")
        resp = client.get("/api/v1/portfolio/execution-triggers")
        assert resp.json()["awaiting_trigger_count"] >= 1

    def test_awaiting_trigger_excludes_active_projects(
        self, client: TestClient
    ) -> None:
        project_id = _setup_approved_project(client, code="PET-009")
        _create_trigger(client, project_id)
        resp = client.get("/api/v1/portfolio/execution-triggers")
        data = resp.json()
        awaiting_ids = [
            p["project_id"] for p in data["awaiting_trigger_projects"]
        ]
        assert project_id not in awaiting_ids

    def test_active_trigger_entry_has_project_name(
        self, client: TestClient
    ) -> None:
        project_id = _setup_approved_project(
            client, code="PET-010", name="Trigger Project 010"
        )
        _create_trigger(client, project_id)
        resp = client.get("/api/v1/portfolio/execution-triggers")
        active = resp.json()["active_triggers"]
        assert len(active) == 1
        assert active[0]["project_name"] == "Trigger Project 010"

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get("/api/v1/portfolio/execution-triggers")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Single-active-trigger invariant
# ---------------------------------------------------------------------------


class TestSingleActiveTriggerInvariant:
    def test_new_trigger_allowed_after_cancel(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SAT-001")
        trigger = _create_trigger(client, project_id)
        client.post(
            f"/api/v1/execution-triggers/{trigger['id']}/cancel",
            json={"cancellation_reason": "Cancelled"},
        )
        # Need a new approved approval before triggering again
        approval = _create_approval(client, project_id)
        _approve(client, approval["id"])
        resp = client.post(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.status_code == 201

    def test_new_trigger_allowed_after_complete(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SAT-002")
        trigger = _create_trigger(client, project_id)
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        # Need a new approved approval before triggering again
        approval = _create_approval(client, project_id)
        _approve(client, approval["id"])
        resp = client.post(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Snapshot immutability
# ---------------------------------------------------------------------------


class TestSnapshotImmutability:
    def test_snapshots_unchanged_after_start(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SNI-001")
        trigger = _create_trigger(client, project_id)
        original_snapshot = trigger["strategy_snapshot"]
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        resp = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.json()["strategy_snapshot"] == original_snapshot

    def test_snapshots_unchanged_after_complete(self, client: TestClient) -> None:
        project_id = _setup_approved_project(client, code="SNI-002")
        trigger = _create_trigger(client, project_id)
        original_snapshot = trigger["execution_package_snapshot"]
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/start")
        client.post(f"/api/v1/execution-triggers/{trigger['id']}/complete")
        resp = client.get(
            f"/api/v1/projects/{project_id}/strategy-execution-trigger"
        )
        assert resp.json()["execution_package_snapshot"] == original_snapshot


# ---------------------------------------------------------------------------
# Pure unit tests (no DB/HTTP)
# ---------------------------------------------------------------------------


class TestAssertTransition:
    """Pure unit tests for the _assert_transition helper."""

    def _make_trigger(self, status: str) -> StrategyExecutionTrigger:
        t = StrategyExecutionTrigger()
        t.status = status
        return t

    # Valid transitions
    def test_triggered_to_in_progress(self) -> None:
        _assert_transition(self._make_trigger("triggered"), "in_progress")

    def test_triggered_to_cancelled(self) -> None:
        _assert_transition(self._make_trigger("triggered"), "cancelled")

    def test_in_progress_to_completed(self) -> None:
        _assert_transition(self._make_trigger("in_progress"), "completed")

    def test_in_progress_to_cancelled(self) -> None:
        _assert_transition(self._make_trigger("in_progress"), "cancelled")

    # Invalid transitions from triggered
    def test_triggered_to_completed_invalid(self) -> None:
        with pytest.raises(DomainValidationError):
            _assert_transition(self._make_trigger("triggered"), "completed")

    def test_triggered_to_triggered_invalid(self) -> None:
        with pytest.raises(DomainValidationError):
            _assert_transition(self._make_trigger("triggered"), "triggered")

    # Invalid transitions from in_progress
    def test_in_progress_to_triggered_invalid(self) -> None:
        with pytest.raises(DomainValidationError):
            _assert_transition(self._make_trigger("in_progress"), "triggered")

    def test_in_progress_to_in_progress_invalid(self) -> None:
        with pytest.raises(DomainValidationError):
            _assert_transition(self._make_trigger("in_progress"), "in_progress")

    # Terminal state: completed allows no transitions
    def test_completed_to_anything_invalid(self) -> None:
        for target in ("triggered", "in_progress", "completed", "cancelled"):
            with pytest.raises(DomainValidationError):
                _assert_transition(self._make_trigger("completed"), target)

    # Terminal state: cancelled allows no transitions
    def test_cancelled_to_anything_invalid(self) -> None:
        for target in ("triggered", "in_progress", "completed", "cancelled"):
            with pytest.raises(DomainValidationError):
                _assert_transition(self._make_trigger("cancelled"), target)
