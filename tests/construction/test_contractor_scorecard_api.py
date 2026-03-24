"""
Tests for the Contractor Scorecard API.

PR-CONSTR-045 — Contractor Scorecards & Trend Analytics

Validates:
- GET /construction/contractors/{id}/scorecard
- GET /construction/contractors/{id}/trend
- GET /construction/scopes/{id}/contractor-scorecards
- GET /construction/scopes/{id}/contractor-ranking

Error cases:
- 404 on unknown contractor / scope
- Deterministic ordering in ranking
"""

from fastapi.testclient import TestClient
import pytest


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str = "SC-001") -> str:
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


def _create_contractor(
    client: TestClient,
    code: str = "CTR-SC1",
    name: str = "Score Builders",
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
    code: str = "PKG-SC1",
    name: str = "Score Package",
    status: str = "draft",
    planned_value: float = 100000.0,
) -> dict:
    resp = client.post(
        "/api/v1/construction/packages",
        json={
            "scope_id": scope_id,
            "package_code": code,
            "package_name": name,
            "status": status,
            "planned_value": planned_value,
        },
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
        f"/api/v1/construction/packages/{package_id}/milestones/{milestone_id}"
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


def _update_milestone_cost(
    client: TestClient,
    milestone_id: str,
    planned_cost: float,
    actual_cost: float,
) -> None:
    resp = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/cost",
        json={"planned_cost": planned_cost, "actual_cost": actual_cost},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /construction/contractors/{id}/scorecard
# ---------------------------------------------------------------------------


def test_contractor_scorecard_returns_200(client: TestClient) -> None:
    project_id = _create_project(client)
    contractor = _create_contractor(client)
    resp = client.get(f"/api/v1/construction/contractors/{contractor['id']}/scorecard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contractor_id"] == contractor["id"]
    assert data["contractor_name"] == "Score Builders"
    assert data["total_milestones"] == 0
    assert data["performance_score"] == 100.0


def test_contractor_scorecard_404_on_unknown(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/contractors/nonexistent-id/scorecard")
    assert resp.status_code == 404


def test_contractor_scorecard_with_delayed_milestone(client: TestClient) -> None:
    project_id = _create_project(client, "SC-002")
    scope = _create_scope(client, project_id)
    contractor = _create_contractor(client, "CTR-SC2", "Delay Builders")
    milestone = _create_milestone(client, scope["id"])
    package = _create_package(client, scope["id"], "PKG-SC2", "Delay Pkg")
    _assign_contractor(client, package["id"], contractor["id"])
    _link_package_milestone(client, package["id"], milestone["id"])
    _update_milestone_status(client, milestone["id"], "delayed")

    resp = client.get(f"/api/v1/construction/contractors/{contractor['id']}/scorecard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_milestones"] == 1
    assert data["delayed_milestones"] == 1
    assert data["delayed_ratio"] == 1.0
    assert data["schedule_score"] == 0.0
    # cost_score should still be 100 (no cost data)
    assert data["cost_score"] == 100.0


def test_contractor_scorecard_with_cost_overrun(client: TestClient) -> None:
    project_id = _create_project(client, "SC-003")
    scope = _create_scope(client, project_id)
    contractor = _create_contractor(client, "CTR-SC3", "Cost Builders")
    milestone = _create_milestone(client, scope["id"])
    package = _create_package(client, scope["id"], "PKG-SC3", "Cost Pkg")
    _assign_contractor(client, package["id"], contractor["id"])
    _link_package_milestone(client, package["id"], milestone["id"])
    _update_milestone_cost(client, milestone["id"], planned_cost=1000.0, actual_cost=1500.0)

    resp = client.get(f"/api/v1/construction/contractors/{contractor['id']}/scorecard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["over_budget_milestones"] == 1
    assert data["overrun_ratio"] == pytest.approx(1.0)
    assert data["cost_score"] < 100.0


def test_contractor_scorecard_with_scope_filter(client: TestClient) -> None:
    """scope_id query parameter restricts scorecard to a specific scope."""
    project_id = _create_project(client, "SC-004")
    scope = _create_scope(client, project_id)
    contractor = _create_contractor(client, "CTR-SC4", "Scope Builders")
    package = _create_package(client, scope["id"], "PKG-SC4", "Scope Pkg")
    _assign_contractor(client, package["id"], contractor["id"])

    resp = client.get(
        f"/api/v1/construction/contractors/{contractor['id']}/scorecard"
        f"?scope_id={scope['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["contractor_id"] == contractor["id"]


def test_contractor_scorecard_response_fields_present(client: TestClient) -> None:
    contractor = _create_contractor(client, "CTR-SC5", "Field Builders")
    resp = client.get(f"/api/v1/construction/contractors/{contractor['id']}/scorecard")
    assert resp.status_code == 200
    data = resp.json()
    required_fields = [
        "contractor_id", "contractor_name", "total_milestones",
        "completed_milestones", "delayed_milestones",
        "on_time_milestones", "on_time_rate",
        "over_budget_milestones", "assessed_cost_milestones",
        "delayed_ratio", "overrun_ratio",
        "avg_cost_variance_percent", "active_packages", "completed_packages",
        "risk_signal_count", "schedule_score", "cost_score",
        "risk_score", "performance_score",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# GET /construction/contractors/{id}/trend
# ---------------------------------------------------------------------------


def test_contractor_trend_returns_200(client: TestClient) -> None:
    contractor = _create_contractor(client, "CTR-TR1", "Trend Builders")
    resp = client.get(f"/api/v1/construction/contractors/{contractor['id']}/trend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contractor_id"] == contractor["id"]
    assert data["trend_direction"] == "stable"
    assert data["periods_analysed"] == 0
    assert data["trend_points"] == []


def test_contractor_trend_404_on_unknown(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/contractors/nonexistent-id/trend")
    assert resp.status_code == 404


def test_contractor_trend_response_fields_present(client: TestClient) -> None:
    contractor = _create_contractor(client, "CTR-TR2", "Trend Field Builders")
    resp = client.get(f"/api/v1/construction/contractors/{contractor['id']}/trend")
    assert resp.status_code == 200
    data = resp.json()
    for field in [
        "contractor_id", "contractor_name", "trend_points",
        "trend_direction", "overall_score", "periods_analysed",
    ]:
        assert field in data, f"Missing field: {field}"


def test_contractor_trend_with_scope_filter(client: TestClient) -> None:
    project_id = _create_project(client, "TR-003")
    scope = _create_scope(client, project_id)
    contractor = _create_contractor(client, "CTR-TR3", "Scope Trend Builders")

    resp = client.get(
        f"/api/v1/construction/contractors/{contractor['id']}/trend"
        f"?scope_id={scope['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["contractor_id"] == contractor["id"]


# ---------------------------------------------------------------------------
# GET /construction/scopes/{id}/contractor-scorecards
# ---------------------------------------------------------------------------


def test_scope_contractor_scorecards_empty_scope(client: TestClient) -> None:
    project_id = _create_project(client, "SS-001")
    scope = _create_scope(client, project_id)
    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/contractor-scorecards")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] == scope["id"]
    assert data["total_contractors"] == 0
    assert data["scorecards"] == []


def test_scope_contractor_scorecards_404_on_unknown_scope(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/scopes/nonexistent-id/contractor-scorecards")
    assert resp.status_code == 404


def test_scope_contractor_scorecards_lists_assigned_contractors(
    client: TestClient,
) -> None:
    project_id = _create_project(client, "SS-002")
    scope = _create_scope(client, project_id)
    contractor = _create_contractor(client, "CTR-SS2", "Scope Scorecard Builder")
    package = _create_package(client, scope["id"], "PKG-SS2", "Scope Pkg 2")
    _assign_contractor(client, package["id"], contractor["id"])

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/contractor-scorecards")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_contractors"] == 1
    assert len(data["scorecards"]) == 1
    assert data["scorecards"][0]["contractor_id"] == contractor["id"]


def test_scope_contractor_scorecards_response_fields_present(
    client: TestClient,
) -> None:
    project_id = _create_project(client, "SS-003")
    scope = _create_scope(client, project_id)
    contractor = _create_contractor(client, "CTR-SS3", "Field Scope Builder")
    package = _create_package(client, scope["id"], "PKG-SS3", "Field Scope Pkg")
    _assign_contractor(client, package["id"], contractor["id"])

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/contractor-scorecards")
    assert resp.status_code == 200
    data = resp.json()
    assert "scope_id" in data
    assert "total_contractors" in data
    assert "scorecards" in data


# ---------------------------------------------------------------------------
# GET /construction/scopes/{id}/contractor-ranking
# ---------------------------------------------------------------------------


def test_scope_contractor_ranking_empty_scope(client: TestClient) -> None:
    project_id = _create_project(client, "SR-001")
    scope = _create_scope(client, project_id)
    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/contractor-ranking")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] == scope["id"]
    assert data["total_contractors"] == 0
    assert data["contractors"] == []


def test_scope_contractor_ranking_404_on_unknown_scope(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/scopes/nonexistent-id/contractor-ranking")
    assert resp.status_code == 404


def test_scope_contractor_ranking_single_contractor(client: TestClient) -> None:
    project_id = _create_project(client, "SR-002")
    scope = _create_scope(client, project_id)
    contractor = _create_contractor(client, "CTR-SR2", "Rank Builder")
    package = _create_package(client, scope["id"], "PKG-SR2", "Rank Pkg")
    _assign_contractor(client, package["id"], contractor["id"])

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/contractor-ranking")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_contractors"] == 1
    assert data["contractors"][0]["contractor_rank"] == 1
    assert data["contractors"][0]["contractor_id"] == contractor["id"]


def test_scope_contractor_ranking_deterministic_order(client: TestClient) -> None:
    """Contractor with no delays should rank above one with all delays."""
    project_id = _create_project(client, "SR-003")
    scope = _create_scope(client, project_id)

    good = _create_contractor(client, "CTR-SR3G", "Good Builder")
    bad = _create_contractor(client, "CTR-SR3B", "Bad Builder")

    # Good contractor: completed milestone
    pkg_good = _create_package(client, scope["id"], "PKG-SR3G", "Good Pkg", status="awarded")
    m_good = _create_milestone(client, scope["id"], sequence=1, name="Good Mile")
    _assign_contractor(client, pkg_good["id"], good["id"])
    _link_package_milestone(client, pkg_good["id"], m_good["id"])
    _update_milestone_status(client, m_good["id"], "completed")

    # Bad contractor: delayed milestone
    pkg_bad = _create_package(
        client, scope["id"], "PKG-SR3B", "Bad Pkg", status="awarded"
    )
    m_bad = _create_milestone(client, scope["id"], sequence=2, name="Bad Mile")
    _assign_contractor(client, pkg_bad["id"], bad["id"])
    _link_package_milestone(client, pkg_bad["id"], m_bad["id"])
    _update_milestone_status(client, m_bad["id"], "delayed")

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/contractor-ranking")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_contractors"] == 2
    # Good builder should rank #1 (higher score)
    ranks = {r["contractor_id"]: r["contractor_rank"] for r in data["contractors"]}
    assert ranks[good["id"]] == 1
    assert ranks[bad["id"]] == 2


def test_scope_contractor_ranking_response_fields_present(client: TestClient) -> None:
    project_id = _create_project(client, "SR-004")
    scope = _create_scope(client, project_id)
    contractor = _create_contractor(client, "CTR-SR4", "Field Rank Builder")
    package = _create_package(client, scope["id"], "PKG-SR4", "Field Rank Pkg")
    _assign_contractor(client, package["id"], contractor["id"])

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/contractor-ranking")
    assert resp.status_code == 200
    data = resp.json()
    assert "scope_id" in data
    assert "total_contractors" in data
    assert "contractors" in data

    row = data["contractors"][0]
    for field in [
        "contractor_rank", "contractor_id", "contractor_name",
        "performance_score", "schedule_score", "cost_score", "risk_score",
        "total_milestones", "delayed_ratio", "overrun_ratio",
    ]:
        assert field in row, f"Missing field: {field}"


def test_scope_contractor_ranking_repeated_calls_are_deterministic(
    client: TestClient,
) -> None:
    project_id = _create_project(client, "SR-005")
    scope = _create_scope(client, project_id)
    ctr_a = _create_contractor(client, "CTR-SR5A", "Alpha Builder")
    ctr_b = _create_contractor(client, "CTR-SR5B", "Beta Builder")
    for ctr, code in [(ctr_a, "PKG-SR5A"), (ctr_b, "PKG-SR5B")]:
        pkg = _create_package(client, scope["id"], code, f"Pkg {code}")
        _assign_contractor(client, pkg["id"], ctr["id"])

    url = f"/api/v1/construction/scopes/{scope['id']}/contractor-ranking"
    r1 = client.get(url).json()["contractors"]
    r2 = client.get(url).json()["contractors"]
    assert [r["contractor_id"] for r in r1] == [r["contractor_id"] for r in r2]
