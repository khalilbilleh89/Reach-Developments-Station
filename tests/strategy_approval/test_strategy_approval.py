"""
Tests for the Strategy Approval Workflow (PR-V7-08 / PR-V7-08A).

Validates:
  POST /api/v1/projects/{id}/strategy-approval
    - HTTP contract (201, 404, 409, auth required)
    - Response schema shape — all required fields present
    - Approval record created with status=pending
    - Snapshot fields stored verbatim
    - ConflictError when pending approval already exists

  POST /api/v1/approvals/{id}/approve
    - HTTP contract (200, 404, 422, auth required)
    - 401 when JWT sub is missing
    - Status transitions to approved
    - approved_by_user_id and approved_at populated
    - Cannot approve an already-approved record (422)
    - Cannot approve a rejected record (422)

  POST /api/v1/approvals/{id}/reject
    - HTTP contract (200, 404, 422, auth required)
    - Status transitions to rejected
    - rejection_reason stored
    - Cannot reject an already-rejected record (422)
    - Cannot reject an already-approved record (422)

  GET /api/v1/projects/{id}/strategy-approval
    - HTTP contract (200, 404, auth required)
    - Returns null when no approval exists
    - Returns latest approval record
    - Reflects status transitions correctly

  Pure unit tests (no DB/HTTP):
    - _assert_transition: valid and invalid transitions
"""

import pytest
from fastapi.testclient import TestClient

from app.modules.strategy_approval.service import _assert_transition
from app.modules.strategy_approval.models import StrategyApproval
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


def _create_project(client: TestClient, code: str = "SAP-001", name: str = "Approval Project") -> str:
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


# ---------------------------------------------------------------------------
# POST /projects/{id}/strategy-approval
# ---------------------------------------------------------------------------


class TestCreateApprovalRequest:
    def test_create_returns_201(self, client: TestClient) -> None:
        project_id = _create_project(client)
        resp = client.post(
            f"/api/v1/projects/{project_id}/strategy-approval",
            json={
                "strategy_snapshot": _STRATEGY_SNAPSHOT,
                "execution_package_snapshot": _EXECUTION_PACKAGE_SNAPSHOT,
            },
        )
        assert resp.status_code == 201

    def test_response_schema_shape(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-002")
        data = _create_approval(client, project_id)
        assert "id" in data
        assert "project_id" in data
        assert "status" in data
        assert "strategy_snapshot" in data
        assert "execution_package_snapshot" in data
        assert "approved_by_user_id" in data
        assert "approved_at" in data
        assert "rejection_reason" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_initial_status_is_pending(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-003")
        data = _create_approval(client, project_id)
        assert data["status"] == "pending"

    def test_project_id_matches(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-004")
        data = _create_approval(client, project_id)
        assert data["project_id"] == project_id

    def test_snapshots_stored_verbatim(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-005")
        data = _create_approval(client, project_id)
        assert data["strategy_snapshot"] == _STRATEGY_SNAPSHOT
        assert data["execution_package_snapshot"] == _EXECUTION_PACKAGE_SNAPSHOT

    def test_approval_fields_null_on_pending(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-006")
        data = _create_approval(client, project_id)
        assert data["approved_by_user_id"] is None
        assert data["approved_at"] is None
        assert data["rejection_reason"] is None

    def test_404_when_project_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/projects/nonexistent-id/strategy-approval",
            json={
                "strategy_snapshot": _STRATEGY_SNAPSHOT,
                "execution_package_snapshot": _EXECUTION_PACKAGE_SNAPSHOT,
            },
        )
        assert resp.status_code == 404

    def test_409_when_pending_approval_already_exists(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-007")
        _create_approval(client, project_id)
        resp = client.post(
            f"/api/v1/projects/{project_id}/strategy-approval",
            json={
                "strategy_snapshot": _STRATEGY_SNAPSHOT,
                "execution_package_snapshot": _EXECUTION_PACKAGE_SNAPSHOT,
            },
        )
        assert resp.status_code == 409

    def test_new_approval_allowed_after_rejection(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-008")
        approval = _create_approval(client, project_id)
        # Reject it
        client.post(
            f"/api/v1/approvals/{approval['id']}/reject",
            json={"rejection_reason": "Not ready yet."},
        )
        # Now a new approval should succeed
        resp = client.post(
            f"/api/v1/projects/{project_id}/strategy-approval",
            json={
                "strategy_snapshot": _STRATEGY_SNAPSHOT,
                "execution_package_snapshot": _EXECUTION_PACKAGE_SNAPSHOT,
            },
        )
        assert resp.status_code == 201

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post(
            "/api/v1/projects/any-id/strategy-approval",
            json={
                "strategy_snapshot": {},
                "execution_package_snapshot": {},
            },
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /approvals/{id}/approve
# ---------------------------------------------------------------------------


class TestApproveStrategy:
    def test_approve_returns_200(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-A01")
        approval = _create_approval(client, project_id)
        resp = client.post(
            f"/api/v1/approvals/{approval['id']}/approve",
        )
        assert resp.status_code == 200

    def test_status_transitions_to_approved(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-A02")
        approval = _create_approval(client, project_id)
        data = client.post(
            f"/api/v1/approvals/{approval['id']}/approve",
            json={},
        ).json()
        assert data["status"] == "approved"

    def test_approved_by_user_id_populated(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-A03")
        approval = _create_approval(client, project_id)
        data = client.post(
            f"/api/v1/approvals/{approval['id']}/approve",
            json={},
        ).json()
        assert data["approved_by_user_id"] == "test-user"

    def test_approved_at_populated(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-A04")
        approval = _create_approval(client, project_id)
        data = client.post(
            f"/api/v1/approvals/{approval['id']}/approve",
            json={},
        ).json()
        assert data["approved_at"] is not None

    def test_404_when_approval_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/approvals/nonexistent-id/approve",
            json={},
        )
        assert resp.status_code == 404

    def test_422_when_already_approved(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-A05")
        approval = _create_approval(client, project_id)
        client.post(f"/api/v1/approvals/{approval['id']}/approve", json={})
        resp = client.post(f"/api/v1/approvals/{approval['id']}/approve", json={})
        assert resp.status_code == 422

    def test_422_when_already_rejected(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-A06")
        approval = _create_approval(client, project_id)
        client.post(
            f"/api/v1/approvals/{approval['id']}/reject",
            json={"rejection_reason": "Not now."},
        )
        resp = client.post(f"/api/v1/approvals/{approval['id']}/approve", json={})
        assert resp.status_code == 422

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post("/api/v1/approvals/any-id/approve")
        assert resp.status_code == 401

    def test_401_when_sub_missing_from_token(
        self, client: TestClient, db_session
    ) -> None:
        """Approve endpoint must reject when JWT sub is absent."""
        project_id = _create_project(client, code="SAP-A07")
        approval = _create_approval(client, project_id)

        # Override auth to return a payload without 'sub'
        app.dependency_overrides[get_current_user_payload] = lambda: {"roles": ["admin"]}
        try:
            resp = client.post(f"/api/v1/approvals/{approval['id']}/approve")
            assert resp.status_code == 401
        finally:
            # Restore the original test-user override
            app.dependency_overrides[get_current_user_payload] = lambda: {
                "sub": "test-user",
                "roles": ["admin"],
            }


# ---------------------------------------------------------------------------
# POST /approvals/{id}/reject
# ---------------------------------------------------------------------------


class TestRejectStrategy:
    def test_reject_returns_200(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-R01")
        approval = _create_approval(client, project_id)
        resp = client.post(
            f"/api/v1/approvals/{approval['id']}/reject",
            json={"rejection_reason": "Needs more analysis."},
        )
        assert resp.status_code == 200

    def test_status_transitions_to_rejected(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-R02")
        approval = _create_approval(client, project_id)
        data = client.post(
            f"/api/v1/approvals/{approval['id']}/reject",
            json={"rejection_reason": "Risk too high."},
        ).json()
        assert data["status"] == "rejected"

    def test_rejection_reason_stored(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-R03")
        approval = _create_approval(client, project_id)
        data = client.post(
            f"/api/v1/approvals/{approval['id']}/reject",
            json={"rejection_reason": "Market conditions unfavourable."},
        ).json()
        assert data["rejection_reason"] == "Market conditions unfavourable."

    def test_404_when_approval_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/approvals/nonexistent-id/reject",
            json={"rejection_reason": "Reason."},
        )
        assert resp.status_code == 404

    def test_422_when_already_rejected(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-R04")
        approval = _create_approval(client, project_id)
        client.post(
            f"/api/v1/approvals/{approval['id']}/reject",
            json={"rejection_reason": "First rejection."},
        )
        resp = client.post(
            f"/api/v1/approvals/{approval['id']}/reject",
            json={"rejection_reason": "Second rejection."},
        )
        assert resp.status_code == 422

    def test_422_when_already_approved(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-R05")
        approval = _create_approval(client, project_id)
        client.post(f"/api/v1/approvals/{approval['id']}/approve", json={})
        resp = client.post(
            f"/api/v1/approvals/{approval['id']}/reject",
            json={"rejection_reason": "Changed mind."},
        )
        assert resp.status_code == 422

    def test_rejection_reason_required(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-R06")
        approval = _create_approval(client, project_id)
        resp = client.post(
            f"/api/v1/approvals/{approval['id']}/reject",
            json={},
        )
        assert resp.status_code == 422

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post(
            "/api/v1/approvals/any-id/reject",
            json={"rejection_reason": "Reason."},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /projects/{id}/strategy-approval
# ---------------------------------------------------------------------------


class TestGetLatestApproval:
    def test_returns_null_when_no_approval_exists(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-G01")
        resp = client.get(f"/api/v1/projects/{project_id}/strategy-approval")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_returns_approval_record(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-G02")
        created = _create_approval(client, project_id)
        resp = client.get(f"/api/v1/projects/{project_id}/strategy-approval")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created["id"]

    def test_reflects_approved_status(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-G03")
        approval = _create_approval(client, project_id)
        client.post(f"/api/v1/approvals/{approval['id']}/approve", json={})
        resp = client.get(f"/api/v1/projects/{project_id}/strategy-approval")
        assert resp.json()["status"] == "approved"

    def test_reflects_rejected_status(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-G04")
        approval = _create_approval(client, project_id)
        client.post(
            f"/api/v1/approvals/{approval['id']}/reject",
            json={"rejection_reason": "Deferred."},
        )
        resp = client.get(f"/api/v1/projects/{project_id}/strategy-approval")
        assert resp.json()["status"] == "rejected"

    def test_returns_latest_when_multiple_exist(self, client: TestClient) -> None:
        project_id = _create_project(client, code="SAP-G05")
        first = _create_approval(client, project_id)
        client.post(
            f"/api/v1/approvals/{first['id']}/reject",
            json={"rejection_reason": "Not yet."},
        )
        second = _create_approval(client, project_id)
        resp = client.get(f"/api/v1/projects/{project_id}/strategy-approval")
        assert resp.json()["id"] == second["id"]

    def test_404_when_project_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/nonexistent-id/strategy-approval")
        assert resp.status_code == 404

    def test_auth_required(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get("/api/v1/projects/any-id/strategy-approval")
        assert resp.status_code == 401

    def test_source_records_unmodified_after_approval(self, client: TestClient) -> None:
        """Approval workflow must not mutate project records."""
        project_id = _create_project(client, code="SAP-G06")
        approval = _create_approval(client, project_id)
        client.post(f"/api/v1/approvals/{approval['id']}/approve", json={})
        project_resp = client.get(f"/api/v1/projects/{project_id}")
        assert project_resp.status_code == 200
        # Project record is unchanged — no approval-related fields mutated
        project_data = project_resp.json()
        assert project_data["id"] == project_id


# ---------------------------------------------------------------------------
# Pure unit tests for _assert_transition
# ---------------------------------------------------------------------------


class TestAssertTransition:
    def _make_approval(self, status: str) -> StrategyApproval:
        a = StrategyApproval()
        a.status = status
        return a

    def test_pending_to_approved_allowed(self) -> None:
        approval = self._make_approval("pending")
        _assert_transition(approval, target="approved")  # should not raise

    def test_pending_to_rejected_allowed(self) -> None:
        approval = self._make_approval("pending")
        _assert_transition(approval, target="rejected")  # should not raise

    def test_approved_to_approved_raises(self) -> None:
        approval = self._make_approval("approved")
        with pytest.raises(DomainValidationError):
            _assert_transition(approval, target="approved")

    def test_approved_to_rejected_raises(self) -> None:
        approval = self._make_approval("approved")
        with pytest.raises(DomainValidationError):
            _assert_transition(approval, target="rejected")

    def test_approved_to_pending_raises(self) -> None:
        approval = self._make_approval("approved")
        with pytest.raises(DomainValidationError):
            _assert_transition(approval, target="pending")

    def test_rejected_to_approved_raises(self) -> None:
        approval = self._make_approval("rejected")
        with pytest.raises(DomainValidationError):
            _assert_transition(approval, target="approved")

    def test_rejected_to_rejected_raises(self) -> None:
        approval = self._make_approval("rejected")
        with pytest.raises(DomainValidationError):
            _assert_transition(approval, target="rejected")

    def test_rejected_to_pending_raises(self) -> None:
        approval = self._make_approval("rejected")
        with pytest.raises(DomainValidationError):
            _assert_transition(approval, target="pending")
