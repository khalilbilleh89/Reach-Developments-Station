"""
Tests for the Construction Risk Alert API.

PR-CONSTR-044 — Contractor Performance & Procurement Risk Alerts

Validates:
- GET /construction/scopes/{id}/risk-alerts
- GET /construction/scopes/{id}/procurement-risk
- GET /construction/contractors/{id}/performance

Error cases:
- 404 on unknown scope / contractor
"""

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str = "RA-001") -> str:
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
    duration_days: int = 10,
) -> dict:
    resp = client.post(
        "/api/v1/construction/milestones",
        json={
            "scope_id": scope_id,
            "name": name,
            "sequence": sequence,
            "duration_days": duration_days,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_contractor(
    client: TestClient,
    code: str = "CTR-RA1",
    name: str = "Risk Builders",
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
    code: str = "PKG-RA1",
    name: str = "Risk Package",
    status: str = "draft",
    planned_value: float = 100000.0,
    awarded_value: float | None = None,
) -> dict:
    payload: dict = {
        "scope_id": scope_id,
        "package_code": code,
        "package_name": name,
        "status": status,
        "planned_value": planned_value,
    }
    if awarded_value is not None:
        payload["awarded_value"] = awarded_value
    resp = client.post("/api/v1/construction/packages", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _update_milestone_progress(
    client: TestClient,
    milestone_id: str,
    progress_percent: int,
    actual_start_day: int = 1,
) -> None:
    resp = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/progress",
        json={"actual_start_day": actual_start_day, "progress_percent": progress_percent},
    )
    assert resp.status_code == 200


def _update_milestone_status(
    client: TestClient,
    milestone_id: str,
    new_status: str,
) -> None:
    resp = client.patch(
        f"/api/v1/construction/milestones/{milestone_id}",
        json={"status": new_status},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /construction/scopes/{id}/risk-alerts
# ---------------------------------------------------------------------------


class TestScopeRiskAlerts:
    def test_empty_scope_returns_zero_alerts(self, client: TestClient) -> None:
        pid = _create_project(client, "RA-SCP-01")
        scope = _create_scope(client, pid, "Empty Scope")
        resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/risk-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope_id"] == scope["id"]
        assert data["total_alerts"] == 0
        assert data["alerts"] == []

    def test_scope_with_unawarded_active_milestone_triggers_alert(
        self, client: TestClient
    ) -> None:
        pid = _create_project(client, "RA-SCP-02")
        scope = _create_scope(client, pid, "Active Scope")
        milestone = _create_milestone(client, scope["id"], sequence=1)
        pkg = _create_package(client, scope["id"], code="PKG-RA-02", status="draft")

        # Link milestone to package
        client.post(
            f"/api/v1/construction/packages/{pkg['id']}/milestones/{milestone['id']}"
        )

        # Update milestone to in_progress
        _update_milestone_status(client, milestone["id"], "in_progress")

        resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/risk-alerts")
        assert resp.status_code == 200
        data = resp.json()
        codes = [a["alert_code"] for a in data["alerts"]]
        assert "UNAWARDED_PACKAGE_ACTIVE_MILESTONE" in codes

    def test_scope_risk_alert_response_shape(self, client: TestClient) -> None:
        pid = _create_project(client, "RA-SCP-03")
        scope = _create_scope(client, pid, "Shape Scope")
        milestone = _create_milestone(client, scope["id"], sequence=1)
        pkg = _create_package(client, scope["id"], code="PKG-RA-03", status="tendering")
        client.post(
            f"/api/v1/construction/packages/{pkg['id']}/milestones/{milestone['id']}"
        )
        _update_milestone_status(client, milestone["id"], "in_progress")

        resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/risk-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "scope_id" in data
        assert "total_alerts" in data
        assert "alerts" in data
        if data["alerts"]:
            alert = data["alerts"][0]
            assert "alert_code" in alert
            assert "severity" in alert
            assert "scope_id" in alert
            assert "message" in alert

    def test_scope_risk_alerts_404_unknown_scope(self, client: TestClient) -> None:
        resp = client.get("/api/v1/construction/scopes/no-such-scope/risk-alerts")
        assert resp.status_code == 404

    def test_scope_with_high_uncommitted_value_triggers_alert(
        self, client: TestClient
    ) -> None:
        pid = _create_project(client, "RA-SCP-04")
        scope = _create_scope(client, pid, "Uncommitted Scope")
        # 70% uncommitted (100000 planned, 30000 awarded)
        _create_package(
            client,
            scope["id"],
            code="PKG-RA-04",
            status="awarded",
            planned_value=100000.0,
            awarded_value=30000.0,
        )
        resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/risk-alerts")
        assert resp.status_code == 200
        codes = [a["alert_code"] for a in resp.json()["alerts"]]
        assert "SCOPE_HIGH_UNCOMMITTED_VALUE" in codes

    def test_scope_total_alerts_matches_list_length(self, client: TestClient) -> None:
        pid = _create_project(client, "RA-SCP-05")
        scope = _create_scope(client, pid, "Count Scope")
        resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/risk-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_alerts"] == len(data["alerts"])


# ---------------------------------------------------------------------------
# GET /construction/scopes/{id}/procurement-risk
# ---------------------------------------------------------------------------


class TestProcurementRisk:
    def test_empty_scope_procurement_risk(self, client: TestClient) -> None:
        pid = _create_project(client, "RA-PR-01")
        scope = _create_scope(client, pid, "Procurement Scope")
        resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/procurement-risk")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope_id"] == scope["id"]
        assert data["total_packages"] == 0
        assert data["unawarded_packages"] == 0
        assert data["stalled_packages"] == 0
        assert data["cancelled_or_on_hold_packages"] == 0
        assert float(data["total_planned_value"]) == 0.0
        assert float(data["uncommitted_value"]) == 0.0

    def test_procurement_risk_counts_packages(self, client: TestClient) -> None:
        pid = _create_project(client, "RA-PR-02")
        scope = _create_scope(client, pid, "Multi Package Scope")
        _create_package(
            client, scope["id"], code="PKG-PR-1", status="draft", planned_value=50000.0
        )
        _create_package(
            client,
            scope["id"],
            code="PKG-PR-2",
            status="awarded",
            planned_value=80000.0,
            awarded_value=80000.0,
        )
        resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/procurement-risk")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_packages"] == 2
        assert data["unawarded_packages"] == 1

    def test_procurement_risk_value_totals(self, client: TestClient) -> None:
        pid = _create_project(client, "RA-PR-03")
        scope = _create_scope(client, pid, "Value Scope")
        _create_package(
            client,
            scope["id"],
            code="PKG-PR-3A",
            status="awarded",
            planned_value=100000.0,
            awarded_value=100000.0,
        )
        _create_package(
            client,
            scope["id"],
            code="PKG-PR-3B",
            status="tendering",
            planned_value=50000.0,
        )
        resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/procurement-risk")
        assert resp.status_code == 200
        data = resp.json()
        assert float(data["total_planned_value"]) == 150000.0
        assert float(data["total_awarded_value"]) == 100000.0
        assert float(data["uncommitted_value"]) == 50000.0

    def test_procurement_risk_response_shape(self, client: TestClient) -> None:
        pid = _create_project(client, "RA-PR-04")
        scope = _create_scope(client, pid, "Shape PR Scope")
        resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/procurement-risk")
        assert resp.status_code == 200
        data = resp.json()
        for field in (
            "scope_id",
            "total_packages",
            "unawarded_packages",
            "stalled_packages",
            "cancelled_or_on_hold_packages",
            "total_planned_value",
            "total_awarded_value",
            "uncommitted_value",
            "alerts",
        ):
            assert field in data

    def test_procurement_risk_404_unknown_scope(self, client: TestClient) -> None:
        resp = client.get("/api/v1/construction/scopes/no-such-scope/procurement-risk")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /construction/contractors/{id}/performance
# ---------------------------------------------------------------------------


class TestContractorPerformance:
    def test_contractor_no_packages_performance(self, client: TestClient) -> None:
        ctr = _create_contractor(client, code="CTR-PERF-1")
        resp = client.get(
            f"/api/v1/construction/contractors/{ctr['id']}/performance"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["contractor_id"] == ctr["id"]
        assert data["total_milestones"] == 0
        assert data["delayed_milestones"] == 0
        assert data["over_budget_milestones"] == 0
        assert data["delay_ratio"] is None
        assert data["overrun_ratio"] is None
        assert data["alerts"] == []

    def test_contractor_performance_response_shape(
        self, client: TestClient
    ) -> None:
        ctr = _create_contractor(client, code="CTR-PERF-2")
        resp = client.get(
            f"/api/v1/construction/contractors/{ctr['id']}/performance"
        )
        assert resp.status_code == 200
        data = resp.json()
        for field in (
            "contractor_id",
            "contractor_name",
            "total_milestones",
            "delayed_milestones",
            "over_budget_milestones",
            "delay_ratio",
            "overrun_ratio",
            "alerts",
        ):
            assert field in data

    def test_contractor_performance_with_delayed_milestones(
        self, client: TestClient
    ) -> None:
        pid = _create_project(client, "RA-CP-01")
        scope = _create_scope(client, pid, "Contractor Perf Scope")
        ctr = _create_contractor(client, code="CTR-PERF-3", name="Delay Corp")
        pkg = _create_package(
            client, scope["id"], code="PKG-CP-1", status="awarded", planned_value=50000.0
        )

        # Assign contractor
        client.post(
            f"/api/v1/construction/packages/{pkg['id']}/assign-contractor",
            json={"contractor_id": ctr["id"]},
        )

        # Create and link 2 milestones, both delayed
        m1 = _create_milestone(client, scope["id"], sequence=1, name="M1")
        m2 = _create_milestone(client, scope["id"], sequence=2, name="M2")
        client.post(
            f"/api/v1/construction/packages/{pkg['id']}/milestones/{m1['id']}"
        )
        client.post(
            f"/api/v1/construction/packages/{pkg['id']}/milestones/{m2['id']}"
        )
        _update_milestone_status(client, m1["id"], "delayed")
        _update_milestone_status(client, m2["id"], "delayed")

        resp = client.get(
            f"/api/v1/construction/contractors/{ctr['id']}/performance"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_milestones"] == 2
        assert data["delayed_milestones"] == 2
        # 100% delay ratio > 50% threshold → alert expected
        delay_alert_codes = [a["alert_code"] for a in data["alerts"]]
        assert "CONTRACTOR_HIGH_DELAY_RATIO" in delay_alert_codes

    def test_contractor_performance_404_unknown_contractor(
        self, client: TestClient
    ) -> None:
        resp = client.get(
            "/api/v1/construction/contractors/no-such-contractor/performance"
        )
        assert resp.status_code == 404

    def test_contractor_name_in_response(self, client: TestClient) -> None:
        ctr = _create_contractor(client, code="CTR-PERF-4", name="Named Builder")
        resp = client.get(
            f"/api/v1/construction/contractors/{ctr['id']}/performance"
        )
        assert resp.status_code == 200
        assert resp.json()["contractor_name"] == "Named Builder"
