"""Tests for the Approved Tender Baseline Governance API (PR-V6-13).

Validates:
  - new baseline governance fields appear in set create/list/get responses
  - approve-baseline endpoint: success, response contract
  - approving creates the approved baseline
  - approving a second comparison automatically deactivates the prior baseline
  - re-approving the same already-active baseline is idempotent
  - approving a comparison from project A does not affect project B
  - 404 on approve-baseline for unknown set
  - active-baseline endpoint: project with no baseline returns has_approved_baseline=False
  - active-baseline endpoint: returns approved baseline after approval
  - active-baseline endpoint: updates after replacement
  - active-baseline endpoint: 404 for unknown project
  - auth requirement on approve-baseline and active-baseline
  - list and get responses include baseline governance fields
  - approve-baseline returns 401 when JWT token has no sub (audit integrity)
"""

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.main import app


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


def _approve(client: TestClient, set_id: str) -> dict:
    resp = client.post(
        f"/api/v1/tender-comparisons/{set_id}/approve-baseline"
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Baseline governance fields present in responses
# ---------------------------------------------------------------------------


def test_create_set_includes_baseline_governance_fields(
    client: TestClient,
) -> None:
    project_id = _create_project(client, "BG01")
    data = _create_set(client, project_id)

    assert "is_approved_baseline" in data
    assert data["is_approved_baseline"] is False
    assert "approved_at" in data
    assert data["approved_at"] is None
    assert "approved_by_user_id" in data
    assert data["approved_by_user_id"] is None


def test_list_sets_includes_baseline_governance_fields(
    client: TestClient,
) -> None:
    project_id = _create_project(client, "BG02")
    _create_set(client, project_id)
    resp = client.get(f"/api/v1/projects/{project_id}/tender-comparisons")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert "is_approved_baseline" in item
    assert item["is_approved_baseline"] is False
    assert item["approved_at"] is None
    assert item["approved_by_user_id"] is None


def test_get_set_includes_baseline_governance_fields(
    client: TestClient,
) -> None:
    project_id = _create_project(client, "BG03")
    comparison_set = _create_set(client, project_id)
    resp = client.get(f"/api/v1/tender-comparisons/{comparison_set['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_approved_baseline" in data
    assert data["is_approved_baseline"] is False
    assert data["approved_at"] is None
    assert data["approved_by_user_id"] is None


# ---------------------------------------------------------------------------
# approve-baseline endpoint
# ---------------------------------------------------------------------------


def test_approve_baseline_success(client: TestClient) -> None:
    project_id = _create_project(client, "BG04")
    comparison_set = _create_set(client, project_id)

    data = _approve(client, comparison_set["id"])

    assert data["id"] == comparison_set["id"]
    assert data["project_id"] == project_id
    assert data["is_approved_baseline"] is True
    assert data["approved_at"] is not None
    assert data["approved_by_user_id"] == "test-user"


def test_approve_baseline_404_unknown_set(client: TestClient) -> None:
    resp = client.post("/api/v1/tender-comparisons/not-exist/approve-baseline")
    assert resp.status_code == 404


def test_approve_baseline_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.post("/api/v1/tender-comparisons/any-id/approve-baseline")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Single-active-baseline enforcement
# ---------------------------------------------------------------------------


def test_approving_second_set_deactivates_prior_baseline(
    client: TestClient,
) -> None:
    project_id = _create_project(client, "BG05")
    set1 = _create_set(client, project_id, title="Set 1")
    set2 = _create_set(client, project_id, title="Set 2")

    # Approve set1 first
    _approve(client, set1["id"])

    # Confirm set1 is baseline
    resp = client.get(f"/api/v1/tender-comparisons/{set1['id']}")
    assert resp.json()["is_approved_baseline"] is True

    # Approve set2 — should deactivate set1
    _approve(client, set2["id"])

    # set1 should no longer be the baseline
    resp1 = client.get(f"/api/v1/tender-comparisons/{set1['id']}")
    assert resp1.status_code == 200
    assert resp1.json()["is_approved_baseline"] is False
    assert resp1.json()["approved_at"] is None
    assert resp1.json()["approved_by_user_id"] is None

    # set2 should be the baseline
    resp2 = client.get(f"/api/v1/tender-comparisons/{set2['id']}")
    assert resp2.status_code == 200
    assert resp2.json()["is_approved_baseline"] is True
    assert resp2.json()["approved_at"] is not None


def test_approving_already_active_baseline_is_idempotent(
    client: TestClient,
) -> None:
    project_id = _create_project(client, "BG06")
    comparison_set = _create_set(client, project_id)

    first = _approve(client, comparison_set["id"])
    second = _approve(client, comparison_set["id"])

    assert second["is_approved_baseline"] is True
    # Approval timestamp refreshed on second call; both calls succeed
    assert second["approved_at"] is not None
    assert second["id"] == first["id"]


def test_only_one_active_baseline_after_multiple_approvals(
    client: TestClient,
) -> None:
    project_id = _create_project(client, "BG07")
    sets = [_create_set(client, project_id, title=f"Set {i}") for i in range(4)]

    for s in sets:
        _approve(client, s["id"])

    # Check final state: only the last approved is the baseline
    final_id = sets[-1]["id"]
    for s in sets:
        resp = client.get(f"/api/v1/tender-comparisons/{s['id']}")
        assert resp.status_code == 200
        data = resp.json()
        expected = s["id"] == final_id
        assert data["is_approved_baseline"] is expected, (
            f"Set {s['id']}: expected is_approved_baseline={expected}"
        )


# ---------------------------------------------------------------------------
# Project isolation
# ---------------------------------------------------------------------------


def test_approve_baseline_project_isolation(client: TestClient) -> None:
    project_a = _create_project(client, "BG08A", name="Project A")
    project_b = _create_project(client, "BG08B", name="Project B")

    set_a = _create_set(client, project_a, title="Set A")
    set_b = _create_set(client, project_b, title="Set B")

    _approve(client, set_a["id"])
    _approve(client, set_b["id"])

    # Project B's approval must not affect Project A's baseline
    resp_a = client.get(f"/api/v1/tender-comparisons/{set_a['id']}")
    assert resp_a.json()["is_approved_baseline"] is True

    resp_b = client.get(f"/api/v1/tender-comparisons/{set_b['id']}")
    assert resp_b.json()["is_approved_baseline"] is True


# ---------------------------------------------------------------------------
# active-baseline endpoint
# ---------------------------------------------------------------------------


def test_active_baseline_no_baseline_returns_false(client: TestClient) -> None:
    project_id = _create_project(client, "BG09")
    _create_set(client, project_id)

    resp = client.get(
        f"/api/v1/projects/{project_id}/tender-comparisons/active-baseline"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["has_approved_baseline"] is False
    assert data["baseline"] is None


def test_active_baseline_returns_approved_set(client: TestClient) -> None:
    project_id = _create_project(client, "BG10")
    comparison_set = _create_set(client, project_id)
    _approve(client, comparison_set["id"])

    resp = client.get(
        f"/api/v1/projects/{project_id}/tender-comparisons/active-baseline"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_approved_baseline"] is True
    assert data["baseline"] is not None
    assert data["baseline"]["id"] == comparison_set["id"]
    assert data["baseline"]["is_approved_baseline"] is True
    assert data["baseline"]["approved_at"] is not None
    assert data["baseline"]["approved_by_user_id"] == "test-user"


def test_active_baseline_updates_after_replacement(client: TestClient) -> None:
    project_id = _create_project(client, "BG11")
    set1 = _create_set(client, project_id, title="Set 1")
    set2 = _create_set(client, project_id, title="Set 2")

    _approve(client, set1["id"])
    _approve(client, set2["id"])

    resp = client.get(
        f"/api/v1/projects/{project_id}/tender-comparisons/active-baseline"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["baseline"]["id"] == set2["id"]


def test_active_baseline_404_unknown_project(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/projects/not-exist/tender-comparisons/active-baseline"
    )
    assert resp.status_code == 404


def test_active_baseline_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get(
        "/api/v1/projects/any/tender-comparisons/active-baseline"
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Historical traceability: superseded baseline fields preserved
# ---------------------------------------------------------------------------


def test_superseded_baseline_metadata_cleared(client: TestClient) -> None:
    """After replacement, the prior baseline's governance metadata is cleared.

    is_approved_baseline → False, approved_at → None, approved_by_user_id → None.
    This ensures clean historical state without retaining stale approval pointers.
    """
    project_id = _create_project(client, "BG12")
    set1 = _create_set(client, project_id, title="Original Baseline")
    set2 = _create_set(client, project_id, title="Replacement Baseline")

    _approve(client, set1["id"])
    _approve(client, set2["id"])

    resp = client.get(f"/api/v1/tender-comparisons/{set1['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_approved_baseline"] is False
    assert data["approved_at"] is None
    assert data["approved_by_user_id"] is None


# ---------------------------------------------------------------------------
# Audit integrity: missing JWT sub must be rejected
# ---------------------------------------------------------------------------


def test_approve_baseline_returns_401_when_sub_missing(db_session) -> None:
    """approve-baseline must return 401 when the JWT token has no sub.

    A token without sub would store an empty/null approved_by_user_id,
    breaking audit traceability.  The endpoint must reject the request
    before writing to the database.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_no_sub_payload():
        # Simulates a malformed JWT with roles but no sub
        return {"roles": ["admin"]}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_payload] = override_no_sub_payload
    try:
        with TestClient(app) as c:
            # First create a project and set with a valid client so we have a real set_id
            def override_valid_payload():
                return {"sub": "setup-user", "roles": ["admin"]}

            app.dependency_overrides[get_current_user_payload] = override_valid_payload
            with TestClient(app) as setup_client:
                project_id = setup_client.post(
                    "/api/v1/projects",
                    json={"name": "Audit Test", "code": "BGSUB"},
                ).json()["id"]
                comparison_set = setup_client.post(
                    f"/api/v1/projects/{project_id}/tender-comparisons",
                    json={"title": "Audit Set", "comparison_stage": "baseline_vs_tender"},
                ).json()

            # Now attempt approval with the no-sub payload
            app.dependency_overrides[get_current_user_payload] = override_no_sub_payload
            with TestClient(app) as no_sub_client:
                resp = no_sub_client.post(
                    f"/api/v1/tender-comparisons/{comparison_set['id']}/approve-baseline"
                )
            assert resp.status_code == 401, resp.text
    finally:
        app.dependency_overrides.clear()
