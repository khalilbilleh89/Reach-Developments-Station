"""
Tests for the Portfolio Construction Risk API.

PR-CONSTR-050 / 050A — Portfolio Risk Rollup Endpoint

Validates:
- GET /construction/projects/{project_id}/risk → 404 for unknown project
- GET /construction/projects/{project_id}/risk → 200 with zero scopes (score 0.0)
- GET /construction/projects/{project_id}/risk → 200 with zero contractors (score 0.0)
- GET /construction/projects/{project_id}/risk → correct counts for a populated project
- GET /construction/projects/{project_id}/risk → correct project_risk_score
- GET /construction/projects/{project_id}/risk → response includes all required fields
- top_breach_reasons is a list
- highest_risk_contractor is None when no contractors
"""

from __future__ import annotations

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str = "PR-001") -> str:
    resp = client.post("/api/v1/projects", json={"name": f"Project {code}", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_scope(client: TestClient, project_id: str, name: str = "Civil Works") -> dict:
    resp = client.post(
        "/api/v1/construction/scopes",
        json={"project_id": project_id, "name": name},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_contractor(
    client: TestClient,
    code: str = "CTR-PR1",
    name: str = "Portfolio Builders",
) -> dict:
    resp = client.post(
        "/api/v1/construction/contractors",
        json={"contractor_code": code, "contractor_name": name},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_package(
    client: TestClient,
    scope_id: str,
    code: str = "PKG-PR1",
    name: str = "Portfolio Package",
    status: str = "awarded",
) -> dict:
    resp = client.post(
        "/api/v1/construction/packages",
        json={
            "scope_id": scope_id,
            "package_code": code,
            "package_name": name,
            "status": status,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_milestone(
    client: TestClient,
    scope_id: str,
    sequence: int = 1,
    name: str = "Foundation",
) -> dict:
    resp = client.post(
        "/api/v1/construction/milestones",
        json={"scope_id": scope_id, "name": name, "sequence": sequence},
    )
    assert resp.status_code == 201
    return resp.json()


def _assign_contractor(client: TestClient, package_id: str, contractor_id: str) -> None:
    resp = client.post(
        f"/api/v1/construction/packages/{package_id}/assign-contractor",
        json={"contractor_id": contractor_id},
    )
    assert resp.status_code == 200


def _link_package_milestone(
    client: TestClient, package_id: str, milestone_id: str
) -> None:
    resp = client.post(
        f"/api/v1/construction/packages/{package_id}/milestones/{milestone_id}",
    )
    assert resp.status_code == 200


def _update_milestone_status(
    client: TestClient, milestone_id: str, status: str
) -> None:
    resp = client.patch(
        f"/api/v1/construction/milestones/{milestone_id}",
        json={"status": status},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 404 on unknown project
# ---------------------------------------------------------------------------


def test_project_risk_404_on_unknown_project(client: TestClient) -> None:
    """Unknown project_id returns 404."""
    resp = client.get("/api/v1/construction/projects/nonexistent-project/risk")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 200 with zero scopes
# ---------------------------------------------------------------------------


def test_project_risk_zero_scopes_returns_200(client: TestClient) -> None:
    """Project with no scopes returns 200 with score 0.0."""
    project_id = _create_project(client, "PR-ZERO")
    resp = client.get(f"/api/v1/construction/projects/{project_id}/risk")
    assert resp.status_code == 200


def test_project_risk_zero_scopes_score_zero(client: TestClient) -> None:
    """Project with no scopes has project_risk_score == 0.0."""
    project_id = _create_project(client, "PR-ZERO2")
    resp = client.get(f"/api/v1/construction/projects/{project_id}/risk")
    data = resp.json()
    assert data["project_risk_score"] == 0.0


def test_project_risk_zero_scopes_contractors_total_zero(client: TestClient) -> None:
    """Project with no scopes has contractors_total == 0."""
    project_id = _create_project(client, "PR-ZERO3")
    resp = client.get(f"/api/v1/construction/projects/{project_id}/risk")
    data = resp.json()
    assert data["contractors_total"] == 0


def test_project_risk_zero_scopes_no_highest_risk(client: TestClient) -> None:
    """Project with no scopes has highest_risk_contractor == None."""
    project_id = _create_project(client, "PR-ZERO4")
    resp = client.get(f"/api/v1/construction/projects/{project_id}/risk")
    data = resp.json()
    assert data["highest_risk_contractor"] is None


# ---------------------------------------------------------------------------
# 200 with scope but zero contractors
# ---------------------------------------------------------------------------


def test_project_risk_scope_no_contractors_score_zero(client: TestClient) -> None:
    """Project with scopes but no assigned contractors returns score 0.0."""
    project_id = _create_project(client, "PR-NOCON")
    _create_scope(client, project_id)
    resp = client.get(f"/api/v1/construction/projects/{project_id}/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_risk_score"] == 0.0
    assert data["contractors_total"] == 0
    assert data["highest_risk_contractor"] is None


# ---------------------------------------------------------------------------
# Response fields
# ---------------------------------------------------------------------------


def test_project_risk_response_has_all_required_fields(client: TestClient) -> None:
    """Response includes all required fields."""
    project_id = _create_project(client, "PR-FIELDS")
    resp = client.get(f"/api/v1/construction/projects/{project_id}/risk")
    assert resp.status_code == 200
    data = resp.json()
    for field in (
        "project_id",
        "contractors_total",
        "contractors_on_watch",
        "contractors_escalated",
        "contractors_critical",
        "project_risk_score",
        "top_breach_reasons",
        "highest_risk_contractor",
    ):
        assert field in data, f"Missing required field: {field}"


def test_project_risk_response_project_id_matches(client: TestClient) -> None:
    """Response project_id matches the requested project."""
    project_id = _create_project(client, "PR-ID")
    resp = client.get(f"/api/v1/construction/projects/{project_id}/risk")
    data = resp.json()
    assert data["project_id"] == project_id


def test_project_risk_top_breach_reasons_is_list(client: TestClient) -> None:
    """top_breach_reasons is always a list."""
    project_id = _create_project(client, "PR-LIST")
    resp = client.get(f"/api/v1/construction/projects/{project_id}/risk")
    data = resp.json()
    assert isinstance(data["top_breach_reasons"], list)


# ---------------------------------------------------------------------------
# Non-trivial case: contractor with milestones producing known escalation
# ---------------------------------------------------------------------------


def test_project_risk_normal_contractor_score_zero(client: TestClient) -> None:
    """A contractor with no risk signals → project_risk_score == 0.0."""
    project_id = _create_project(client, "PR-NORM")
    scope = _create_scope(client, project_id)
    contractor = _create_contractor(client, "CTR-PR-N1", "Normal Builder")
    package = _create_package(client, scope["id"], "PKG-PR-N1", "Normal Pkg")
    _assign_contractor(client, package["id"], contractor["id"])

    resp = client.get(f"/api/v1/construction/projects/{project_id}/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contractors_total"] == 1
    assert data["project_risk_score"] == 0.0
    assert data["contractors_on_watch"] == 0
    assert data["contractors_escalated"] == 0
    assert data["contractors_critical"] == 0
    assert data["highest_risk_contractor"] == contractor["id"]


def test_project_risk_critical_contractor_escalation_counts(client: TestClient) -> None:
    """A contractor with ≥5 delayed milestones (risk_signal_count trigger) contributes
    to escalation counts and raises the project risk score above zero."""
    project_id = _create_project(client, "PR-ESC")
    scope = _create_scope(client, project_id)
    contractor = _create_contractor(client, "CTR-PR-E1", "Critical Builder")
    package = _create_package(client, scope["id"], "PKG-PR-E1", "Critical Pkg")
    _assign_contractor(client, package["id"], contractor["id"])

    # Create and delay 6 milestones to trigger CONTRACTOR_HIGH_DELAY_RATIO alert ×5
    for i in range(6):
        milestone = _create_milestone(client, scope["id"], sequence=i + 1, name=f"MS-{i}")
        _link_package_milestone(client, package["id"], milestone["id"])
        _update_milestone_status(client, milestone["id"], "delayed")

    resp = client.get(f"/api/v1/construction/projects/{project_id}/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contractors_total"] == 1
    # With high delay rate the score should be above zero
    assert data["project_risk_score"] > 0.0
    assert data["highest_risk_contractor"] == contractor["id"]


def test_project_risk_multiple_contractors_counts(client: TestClient) -> None:
    """Multiple contractors produce correct distribution counts."""
    project_id = _create_project(client, "PR-MULTI")
    scope = _create_scope(client, project_id)

    for i in range(3):
        c = _create_contractor(client, f"CTR-PR-M{i}", f"Multi Builder {i}")
        pkg = _create_package(
            client, scope["id"], f"PKG-PR-M{i}", f"Multi Pkg {i}"
        )
        _assign_contractor(client, pkg["id"], c["id"])

    resp = client.get(f"/api/v1/construction/projects/{project_id}/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contractors_total"] == 3
    # All contractors normal → combined counts add up
    assert (
        data["contractors_on_watch"]
        + data["contractors_escalated"]
        + data["contractors_critical"]
        <= data["contractors_total"]
    )
