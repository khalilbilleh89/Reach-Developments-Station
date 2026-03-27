"""
Tests for the Feasibility Feedback API.

Validates:
  - Endpoint HTTP contract (200 on valid project, 404 on missing project)
  - Response schema shape
  - Feedback derivation: no-units project (null-safe)
  - Feedback derivation: units with no sales
  - Feedback derivation: low sell-through → needs_attention
  - Feedback derivation: very low sell-through → at_risk
  - Feedback derivation: overdue receivables → at_risk
  - Feedback derivation: good sell-through + no overdue → on_track
  - Feasibility lineage surfacing
  - Source record immutability (no mutation during feedback read)
  - Auth requirement (401 when unauthenticated)
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Hierarchy / data helpers
# ---------------------------------------------------------------------------


def _create_project(
    client: TestClient, code: str = "PRJ-FF", name: str = "Feedback Project"
) -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_unit(
    client: TestClient,
    proj_code: str = "PRJ-FF",
    unit_number: str = "101",
    proj_name: str = "Feedback Project",
) -> tuple[str, str]:
    """Create full hierarchy and return (project_id, unit_id)."""
    project_id = _create_project(client, proj_code, proj_name)
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    assert phase_resp.status_code == 201, phase_resp.text
    phase_id = phase_resp.json()["id"]

    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    )
    assert building_resp.status_code == 201, building_resp.text
    building_id = building_resp.json()["id"]

    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    )
    assert floor_resp.status_code == 201, floor_resp.text
    floor_id = floor_resp.json()["id"]

    unit_resp = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": unit_number,
            "unit_type": "studio",
            "internal_area": 100.0,
        },
    )
    assert unit_resp.status_code == 201, unit_resp.text
    unit_id = unit_resp.json()["id"]
    return project_id, unit_id


def _create_buyer(client: TestClient, email: str = "buyer@feedback.com") -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Feedback Buyer", "email": email, "phone": "+971500000099"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_contract(
    client: TestClient,
    unit_id: str,
    buyer_id: str,
    contract_number: str = "CNT-FF-001",
    price: float = 500_000.0,
) -> str:
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": str(date.today()),
            "contract_price": price,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# 404 — missing project
# ---------------------------------------------------------------------------


def test_feedback_returns_404_for_missing_project(client: TestClient):
    """GET /api/v1/projects/{id}/feasibility-feedback → 404 when project absent."""
    resp = client.get("/api/v1/projects/nonexistent-project-id/feasibility-feedback")
    assert resp.status_code == 404
    assert "not found" in resp.json()["message"].lower()


# ---------------------------------------------------------------------------
# 401 — unauthenticated request
# ---------------------------------------------------------------------------


def test_feedback_requires_authentication(unauth_client: TestClient):
    """Endpoint must reject unauthenticated requests with 401/403."""
    resp = unauth_client.get("/api/v1/projects/some-id/feasibility-feedback")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Null-safe: project exists but has no units
# ---------------------------------------------------------------------------


def test_feedback_no_units_returns_null_safe_response(client: TestClient):
    """Project with no units must return null-safe feedback (no error)."""
    project_id = _create_project(client, "PRJ-NOUNITS", "No-Units Project")
    resp = client.get(f"/api/v1/projects/{project_id}/feasibility-feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["feedback_status"] is None
    assert data["absorption"]["total_units"] == 0
    assert data["absorption"]["sold_units"] == 0
    assert data["absorption"]["sell_through_pct"] is None
    assert "no units" in data["feedback_notes"].lower()


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


def test_feedback_response_shape(client: TestClient):
    """Response must include all required top-level and nested fields."""
    project_id = _create_project(client, "PRJ-SHAPE", "Shape Project")
    resp = client.get(f"/api/v1/projects/{project_id}/feasibility-feedback")
    assert resp.status_code == 200
    data = resp.json()

    # Top-level keys
    for key in (
        "project_id",
        "project_name",
        "project_code",
        "project_status",
        "absorption",
        "collections",
        "feedback_status",
        "feedback_notes",
        "latest_feasibility_run_id",
        "latest_scenario_id",
        "feasibility_lineage_note",
        "feedback_thresholds",
    ):
        assert key in data, f"Missing top-level key: {key}"

    # Absorption keys
    for key in (
        "total_units",
        "sold_units",
        "reserved_units",
        "available_units",
        "sell_through_pct",
        "contracted_revenue",
    ):
        assert key in data["absorption"], f"Missing absorption key: {key}"

    # Collections keys
    for key in (
        "collected_cash",
        "outstanding_balance",
        "overdue_receivable_count",
        "overdue_balance",
        "collection_rate_pct",
    ):
        assert key in data["collections"], f"Missing collections key: {key}"

    # Thresholds must be exposed
    thresholds = data["feedback_thresholds"]
    assert "at_risk_sell_through_pct" in thresholds
    assert "needs_attention_sell_through_pct" in thresholds


# ---------------------------------------------------------------------------
# Units present, no sales → at_risk (sell-through = 0 % < 20 %)
# ---------------------------------------------------------------------------


def test_feedback_units_no_sales_is_at_risk(client: TestClient):
    """Project with units but no sales has 0% sell-through → at_risk."""
    project_id, _unit_id = _create_unit(
        client, "PRJ-NOSALES", "101", "No-Sales Project"
    )
    resp = client.get(f"/api/v1/projects/{project_id}/feasibility-feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["absorption"]["total_units"] == 1
    assert data["absorption"]["sold_units"] == 0
    assert data["absorption"]["sell_through_pct"] == 0.0
    assert data["feedback_status"] == "at_risk"


# ---------------------------------------------------------------------------
# Low sell-through (> 0 % but < 20 %) → at_risk
# ---------------------------------------------------------------------------


def test_feedback_very_low_sell_through_is_at_risk(client: TestClient):
    """5 units, 0 sold → sell-through = 0.0% → at_risk."""
    project_id = _create_project(client, "PRJ-ATRISK", "At-Risk Project")
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    phase_id = phase_resp.json()["id"]
    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    )
    building_id = building_resp.json()["id"]
    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    )
    floor_id = floor_resp.json()["id"]

    # Create 5 units, sell none
    for i in range(1, 6):
        client.post(
            "/api/v1/units",
            json={
                "floor_id": floor_id,
                "unit_number": str(i),
                "unit_type": "studio",
                "internal_area": 80.0,
            },
        )

    resp = client.get(f"/api/v1/projects/{project_id}/feasibility-feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["absorption"]["total_units"] == 5
    assert data["absorption"]["sold_units"] == 0
    assert data["feedback_status"] == "at_risk"


# ---------------------------------------------------------------------------
# Moderate sell-through (20 %–49 %) → needs_attention
# ---------------------------------------------------------------------------


def test_feedback_low_sell_through_needs_attention(client: TestClient, db_session):
    """Project with 1 of 4 units sold (25%) → needs_attention."""
    from app.modules.units.models import Unit as UnitModel

    project_id = _create_project(client, "PRJ-NEEDSATTN", "Needs-Attention Project")
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    phase_id = phase_resp.json()["id"]
    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    )
    building_id = building_resp.json()["id"]
    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    )
    floor_id = floor_resp.json()["id"]

    # Create 4 units
    unit_ids = []
    for i in range(1, 5):
        u = client.post(
            "/api/v1/units",
            json={
                "floor_id": floor_id,
                "unit_number": str(i),
                "unit_type": "studio",
                "internal_area": 80.0,
            },
        )
        unit_ids.append(u.json()["id"])

    # Set 1 unit to "under_contract" directly to represent a sold unit
    unit = db_session.query(UnitModel).filter(UnitModel.id == unit_ids[0]).first()
    unit.status = "under_contract"
    db_session.commit()

    resp = client.get(f"/api/v1/projects/{project_id}/feasibility-feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["absorption"]["total_units"] == 4
    assert data["absorption"]["sold_units"] == 1
    assert data["absorption"]["sell_through_pct"] == 25.0
    assert data["feedback_status"] == "needs_attention"


# ---------------------------------------------------------------------------
# Good sell-through, no overdue → on_track
# ---------------------------------------------------------------------------


def test_feedback_good_sell_through_on_track(client: TestClient, db_session):
    """Project with 2 of 2 units sold (100%) → on_track."""
    from app.modules.units.models import Unit as UnitModel

    project_id = _create_project(client, "PRJ-ONTRACK", "On-Track Project")
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    phase_id = phase_resp.json()["id"]
    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    )
    building_id = building_resp.json()["id"]
    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    )
    floor_id = floor_resp.json()["id"]

    # Create 2 units
    unit_ids = []
    for i in range(1, 3):
        u = client.post(
            "/api/v1/units",
            json={
                "floor_id": floor_id,
                "unit_number": str(i),
                "unit_type": "studio",
                "internal_area": 80.0,
            },
        )
        unit_ids.append(u.json()["id"])

    # Set both units to "under_contract" to represent fully sold project
    for uid in unit_ids:
        unit = db_session.query(UnitModel).filter(UnitModel.id == uid).first()
        unit.status = "under_contract"
    db_session.commit()

    resp = client.get(f"/api/v1/projects/{project_id}/feasibility-feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["absorption"]["total_units"] == 2
    assert data["absorption"]["sold_units"] == 2
    assert data["absorption"]["sell_through_pct"] == 100.0
    assert data["feedback_status"] == "on_track"


# ---------------------------------------------------------------------------
# Overdue receivables → at_risk regardless of sell-through
# ---------------------------------------------------------------------------


def test_feedback_overdue_receivables_is_at_risk(client: TestClient):
    """Project with overdue receivables must be at_risk even if sell-through is high."""
    project_id = _create_project(client, "PRJ-OVERDUE", "Overdue Project")
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    phase_id = phase_resp.json()["id"]
    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    )
    building_id = building_resp.json()["id"]
    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    )
    floor_id = floor_resp.json()["id"]

    unit_resp = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "1",
            "unit_type": "studio",
            "internal_area": 80.0,
        },
    )
    unit_id = unit_resp.json()["id"]
    buyer_id = _create_buyer(client, "buyer@overdue.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-OVD-001", 600_000.0)

    # Create a payment plan with a start date well in the past so the
    # installment due_date is already overdue when receivables are generated.
    plan_resp = client.post(
        "/api/v1/payment-plans",
        json={
            "contract_id": contract_id,
            "plan_name": "Overdue Test Plan",
            "number_of_installments": 1,
            "start_date": "2024-01-01",
        },
    )
    assert plan_resp.status_code == 201, plan_resp.text

    # Generate receivables — the single installment due 2024-01-01 will be overdue.
    gen_resp = client.post(f"/api/v1/contracts/{contract_id}/receivables/generate")
    assert gen_resp.status_code == 201, gen_resp.text
    assert gen_resp.json()["generated"] >= 1

    resp = client.get(f"/api/v1/projects/{project_id}/feasibility-feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["collections"]["overdue_receivable_count"] >= 1
    assert data["feedback_status"] == "at_risk"
    assert "overdue" in data["feedback_notes"].lower()


# ---------------------------------------------------------------------------
# Source record immutability
# ---------------------------------------------------------------------------


def test_feedback_does_not_mutate_source_records(client: TestClient):
    """Fetching feedback must not alter any project or unit records."""
    project_id, unit_id = _create_unit(client, "PRJ-IMMUT", "101", "Immutable Project")

    # Capture unit status before feedback call
    unit_before = client.get(f"/api/v1/units/{unit_id}").json()

    resp = client.get(f"/api/v1/projects/{project_id}/feasibility-feedback")
    assert resp.status_code == 200

    # Verify unit status unchanged
    unit_after = client.get(f"/api/v1/units/{unit_id}").json()
    assert unit_before["status"] == unit_after["status"]


# ---------------------------------------------------------------------------
# Feasibility lineage surfacing
# ---------------------------------------------------------------------------


def test_feedback_no_feasibility_run_lineage_note(client: TestClient):
    """Project without feasibility runs must surface the correct lineage note."""
    project_id = _create_project(client, "PRJ-NOFEAS", "No-Feasibility Project")
    resp = client.get(f"/api/v1/projects/{project_id}/feasibility-feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["latest_feasibility_run_id"] is None
    assert data["latest_scenario_id"] is None
    assert "no feasibility run" in data["feasibility_lineage_note"].lower()


def test_feedback_with_feasibility_run_surfaces_lineage(client: TestClient):
    """Project with a feasibility run must surface run_id and lineage note."""
    project_id = _create_project(client, "PRJ-HASFEAS", "Has-Feasibility Project")

    # Create a feasibility run linked to the project
    feas_resp = client.post(
        "/api/v1/feasibility/runs",
        json={
            "project_id": project_id,
            "scenario_name": "Base Case",
            "scenario_type": "base",
        },
    )
    assert feas_resp.status_code == 201, feas_resp.text
    run_id = feas_resp.json()["id"]

    resp = client.get(f"/api/v1/projects/{project_id}/feasibility-feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["latest_feasibility_run_id"] == run_id
    assert "linked to feasibility run" in data["feasibility_lineage_note"].lower()


# ---------------------------------------------------------------------------
# Project identity fields
# ---------------------------------------------------------------------------


def test_feedback_returns_correct_project_fields(client: TestClient):
    """Response must include correct project_id, name, code, and status."""
    project_id = _create_project(client, "PRJ-FIELDS", "Fields Project")
    resp = client.get(f"/api/v1/projects/{project_id}/feasibility-feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["project_name"] == "Fields Project"
    assert data["project_code"] == "PRJ-FIELDS"
    assert data["project_status"] is not None
