"""
Smoke test: Finance Summary

Verifies that the finance module correctly aggregates project-level financials.

Flow:
  Create project → create unit → create contract → query finance summary

Assertions:
  - Finance module responds with correct project_id
  - No finance write paths exist (only read endpoints)
  - Aggregate values reflect created contracts
"""

from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_unit(client: TestClient, proj_code: str) -> dict:
    """Create the minimal hierarchy and return project_id and unit_id."""
    project_id = client.post(
        "/api/v1/projects",
        json={"name": "Finance Smoke Project", "code": proj_code},
    ).json()["id"]
    phase_id = client.post(
        f"/api/v1/projects/{project_id}/phases",
        json={"name": "Phase 1", "sequence": 1},
    ).json()["id"]
    building_id = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    ).json()["id"]
    floor_id = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]
    unit_id = client.post(
        f"/api/v1/floors/{floor_id}/units",
        json={"unit_number": "101", "unit_type": "studio", "internal_area": 95.0},
    ).json()["id"]
    return {"project_id": project_id, "unit_id": unit_id}


def _create_contract(
    client: TestClient, unit_id: str, contract_price: float, contract_number: str
) -> str:
    buyer_id = client.post(
        "/api/v1/sales/buyers",
        json={
            "full_name": "Finance Buyer",
            "email": f"{contract_number}@example.com",
            "phone": "+9710000003",
        },
    ).json()["id"]
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": "2026-01-15",
            "contract_price": contract_price,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_finance_summary_returns_correct_project_id(client: TestClient):
    """Finance summary endpoint returns the queried project_id."""
    ids = _build_unit(client, "SMKF-001")
    summary = client.get(
        f"/api/v1/finance/projects/{ids['project_id']}/summary"
    ).json()

    assert summary["project_id"] == ids["project_id"]


def test_finance_summary_aggregates_contract_value(client: TestClient):
    """total_contract_value reflects the created sales contract."""
    ids = _build_unit(client, "SMKF-002")
    contract_price = 750_000.0
    _create_contract(client, ids["unit_id"], contract_price, "CNT-SMKF-B1")

    summary = client.get(
        f"/api/v1/finance/projects/{ids['project_id']}/summary"
    ).json()

    assert summary["total_contract_value"] == contract_price
    assert summary["total_units"] >= 1


def test_finance_summary_no_write_paths(client: TestClient):
    """Finance module exposes no write (POST/PUT/PATCH/DELETE) endpoints."""
    ids = _build_unit(client, "SMKF-003")

    # POST to finance summary must return 405 (method not allowed)
    resp = client.post(
        f"/api/v1/finance/projects/{ids['project_id']}/summary", json={}
    )
    assert resp.status_code == 405


def test_finance_summary_empty_project(client: TestClient):
    """Finance summary for a project with no contracts returns zero aggregates."""
    project_id = client.post(
        "/api/v1/projects",
        json={"name": "Empty Finance Project", "code": "SMKF-004"},
    ).json()["id"]

    summary = client.get(f"/api/v1/finance/projects/{project_id}/summary").json()

    assert summary["project_id"] == project_id
    assert summary["total_units"] == 0
    assert summary["total_contract_value"] == 0
    assert summary["units_sold"] == 0
