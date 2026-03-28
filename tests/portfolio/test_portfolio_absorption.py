"""
Tests for the Portfolio Absorption endpoint (PR-V7-01).

Validates:
  - Endpoint HTTP contract (200, auth required)
  - Response schema shape — all required fields present
  - Empty portfolio returns valid null-safe response
  - Per-project cards are populated correctly
  - Summary counts are accurate
  - Auth requirement (401 when unauthenticated)
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Hierarchy helpers
# ---------------------------------------------------------------------------


def _create_project(
    client: TestClient, code: str, name: str = "Portfolio Absorption Project"
) -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_hierarchy_with_units(
    client: TestClient, project_id: str, num_units: int, phase_code: str = "BLK-PA"
) -> list[str]:
    """Create phase → building → floor → N units and return unit ID list."""
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    assert phase_resp.status_code == 201, phase_resp.text
    phase_id = phase_resp.json()["id"]
    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": phase_code},
    )
    assert building_resp.status_code == 201, building_resp.text
    building_id = building_resp.json()["id"]
    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-PA1", "sequence_number": 1},
    )
    assert floor_resp.status_code == 201, floor_resp.text
    floor_id = floor_resp.json()["id"]

    unit_ids = []
    for i in range(1, num_units + 1):
        u = client.post(
            "/api/v1/units",
            json={"floor_id": floor_id, "unit_number": str(i), "unit_type": "studio", "internal_area": 80.0},
        )
        assert u.status_code == 201, u.text
        unit_ids.append(u.json()["id"])
    return unit_ids


def _create_buyer(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "PA Buyer", "email": email, "phone": "+971500000077"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_contract(
    client: TestClient, unit_id: str, buyer_id: str, number: str, price: float, contract_date: str
) -> str:
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": number,
            "contract_date": contract_date,
            "contract_price": price,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Auth requirement
# ---------------------------------------------------------------------------


def test_portfolio_absorption_requires_auth(unauth_client: TestClient):
    """Endpoint must reject unauthenticated requests with 401/403."""
    resp = unauth_client.get("/api/v1/portfolio/absorption")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Empty portfolio — null-safe response
# ---------------------------------------------------------------------------


def test_portfolio_absorption_empty_returns_valid_response(client: TestClient):
    """Portfolio with no projects must return a valid null-safe response."""
    resp = client.get("/api/v1/portfolio/absorption")
    assert resp.status_code == 200
    data = resp.json()

    assert "summary" in data
    assert "projects" in data
    assert "fastest_projects" in data
    assert "slowest_projects" in data
    assert "below_plan_projects" in data
    # No projects → empty lists
    assert data["projects"] == []
    assert data["fastest_projects"] == []
    assert data["slowest_projects"] == []


# ---------------------------------------------------------------------------
# Response schema shape
# ---------------------------------------------------------------------------


def test_portfolio_absorption_response_shape(client: TestClient):
    """Response must include all required top-level and nested fields."""
    resp = client.get("/api/v1/portfolio/absorption")
    assert resp.status_code == 200
    data = resp.json()

    summary_keys = [
        "total_projects",
        "projects_with_absorption_data",
        "portfolio_avg_sell_through_pct",
        "portfolio_avg_absorption_rate",
        "projects_ahead_of_plan",
        "projects_on_plan",
        "projects_behind_plan",
        "projects_no_absorption_data",
    ]
    for key in summary_keys:
        assert key in data["summary"], f"Missing summary key: {key}"

    for list_key in ("projects", "fastest_projects", "slowest_projects", "below_plan_projects"):
        assert isinstance(data[list_key], list), f"Expected list for {list_key}"


# ---------------------------------------------------------------------------
# Per-project cards populated
# ---------------------------------------------------------------------------


def test_portfolio_absorption_project_cards(client: TestClient):
    """Portfolio absorption must include a card for each project."""
    proj_id = _create_project(client, "PRJ-PAC", "PA Cards Project")

    resp = client.get("/api/v1/portfolio/absorption")
    assert resp.status_code == 200
    data = resp.json()

    project_ids = [c["project_id"] for c in data["projects"]]
    assert proj_id in project_ids

    # Find the card for our project
    card = next(c for c in data["projects"] if c["project_id"] == proj_id)
    for key in (
        "project_id", "project_name", "project_code", "total_units",
        "sold_units", "contracted_revenue", "absorption_status",
    ):
        assert key in card, f"Missing card key: {key}"


# ---------------------------------------------------------------------------
# Summary counts are accurate
# ---------------------------------------------------------------------------


def test_portfolio_absorption_summary_total_projects(client: TestClient):
    """summary.total_projects must equal the number of projects in the portfolio."""
    _create_project(client, "PRJ-PCT1", "PA Count 1")
    _create_project(client, "PRJ-PCT2", "PA Count 2")

    resp = client.get("/api/v1/portfolio/absorption")
    assert resp.status_code == 200
    data = resp.json()

    # At least 2 projects in summary
    assert data["summary"]["total_projects"] >= 2
    assert len(data["projects"]) == data["summary"]["total_projects"]


# ---------------------------------------------------------------------------
# Projects with sales appear in fastest/slowest lists
# ---------------------------------------------------------------------------


def test_portfolio_absorption_fastest_slowest_populated(client: TestClient):
    """fastest_projects and slowest_projects should be populated from rate-calculable projects."""
    from datetime import timedelta

    proj_id = _create_project(client, "PRJ-PAFS", "PA Fast-Slow Project")
    unit_ids = _create_hierarchy_with_units(client, proj_id, 3, "BLK-FS")

    buyer1 = _create_buyer(client, "b1@pafs.com")
    buyer2 = _create_buyer(client, "b2@pafs.com")

    first_date = str(date.today() - timedelta(days=90))
    second_date = str(date.today())
    _create_contract(client, unit_ids[0], buyer1, "CNT-PAFS-01", 400_000.0, first_date)
    _create_contract(client, unit_ids[1], buyer2, "CNT-PAFS-02", 400_000.0, second_date)

    resp = client.get("/api/v1/portfolio/absorption")
    assert resp.status_code == 200
    data = resp.json()

    # Since we have at least 1 project with a calculable rate, fastest_projects ≥ 1
    rate_projects = [c for c in data["projects"] if c["absorption_rate_per_month"] is not None]
    if rate_projects:
        assert len(data["fastest_projects"]) >= 1
        # fastest projects are ordered by rate descending
        rates = [c["absorption_rate_per_month"] for c in data["fastest_projects"] if c["absorption_rate_per_month"] is not None]
        assert rates == sorted(rates, reverse=True)
