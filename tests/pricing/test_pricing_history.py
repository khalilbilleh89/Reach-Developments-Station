"""
Tests for the PR-15 Pricing History & Audit Trail.

Validates:
  - audit trail entry created on pricing record creation (INITIAL)
  - audit trail entry created on pricing update (MANUAL_UPDATE)
  - audit trail entry created on pricing approval (APPROVAL)
  - audit trail entry created on pricing override (OVERRIDE)
  - audit trail entry created when pricing is archived (ARCHIVE)
  - audit trail returns entries in chronological order
  - audit trail endpoint returns 404 for unknown pricing_id
  - full lifecycle produces correct change_type sequence
"""

import pytest
from fastapi.testclient import TestClient


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-AUDIT") -> tuple[str, str]:
    """Create a full project hierarchy and return (project_id, unit_id)."""
    project_id = client.post(
        "/api/v1/projects",
        json={"name": "Audit Trail Test Project", "code": proj_code},
    ).json()["id"]
    phase_id = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
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
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 85.0},
    ).json()["id"]
    return project_id, unit_id


_VALID_PRICING_PAYLOAD = {
    "base_price": 500_000.0,
    "manual_adjustment": 0.0,
    "currency": "AED",
    "notes": "Audit trail test pricing",
}


# ---------------------------------------------------------------------------
# GET /api/v1/pricing/{pricing_id}/audit-trail
# ---------------------------------------------------------------------------

def test_audit_trail_created_on_initial_create(client: TestClient):
    """Creating a pricing record must produce an INITIAL audit entry."""
    _, unit_id = _create_hierarchy(client, "PRJ-AT01")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    pricing_id = record["id"]

    resp = client.get(f"/api/v1/pricing/{pricing_id}/audit-trail")
    assert resp.status_code == 200

    trail = resp.json()
    assert trail["pricing_id"] == pricing_id
    assert trail["unit_id"] == unit_id
    assert trail["total"] == 1

    entry = trail["entries"][0]
    assert entry["change_type"] == "INITIAL"
    assert entry["pricing_status"] == "draft"
    assert entry["base_price"] == 500_000.0
    assert entry["manual_adjustment"] == 0.0
    assert entry["final_price"] == 500_000.0
    assert entry["currency"] == "AED"
    assert entry["actor"] is None


def test_audit_trail_approval_appends_entry(client: TestClient):
    """Approving a pricing record must append an APPROVAL audit entry."""
    _, unit_id = _create_hierarchy(client, "PRJ-AT02")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    pricing_id = record["id"]

    client.post(f"/api/v1/pricing/{pricing_id}/approve", json={"approved_by": "finance-mgr"})

    trail = client.get(f"/api/v1/pricing/{pricing_id}/audit-trail").json()
    assert trail["total"] == 2

    change_types = [e["change_type"] for e in trail["entries"]]
    assert change_types == ["INITIAL", "APPROVAL"]

    approval_entry = trail["entries"][1]
    assert approval_entry["pricing_status"] == "approved"
    assert approval_entry["actor"] == "finance-mgr"


def test_audit_trail_override_appends_entry(client: TestClient):
    """Applying a price override must append an OVERRIDE audit entry."""
    _, unit_id = _create_hierarchy(client, "PRJ-AT03")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    pricing_id = record["id"]

    override_payload = {
        "override_amount": 5_000.0,
        "override_reason": "Special discount for bulk buyer",
        "requested_by": "sales-mgr-1",
        "role": "sales_manager",
    }
    client.post(f"/api/v1/pricing/{pricing_id}/override", json=override_payload)

    trail = client.get(f"/api/v1/pricing/{pricing_id}/audit-trail").json()
    assert trail["total"] == 2

    change_types = [e["change_type"] for e in trail["entries"]]
    assert change_types == ["INITIAL", "OVERRIDE"]

    override_entry = trail["entries"][1]
    assert override_entry["change_type"] == "OVERRIDE"
    assert override_entry["manual_adjustment"] == 5_000.0
    assert override_entry["final_price"] == 505_000.0
    assert override_entry["override_reason"] == "Special discount for bulk buyer"
    assert override_entry["override_requested_by"] == "sales-mgr-1"
    assert override_entry["actor"] == "sales-mgr-1"


def test_audit_trail_manual_update_appends_entry(client: TestClient):
    """Updating a pricing record must append a MANUAL_UPDATE audit entry."""
    _, unit_id = _create_hierarchy(client, "PRJ-AT04")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    pricing_id = record["id"]

    client.put(f"/api/v1/pricing/{pricing_id}", json={"base_price": 520_000.0})

    trail = client.get(f"/api/v1/pricing/{pricing_id}/audit-trail").json()
    assert trail["total"] == 2

    change_types = [e["change_type"] for e in trail["entries"]]
    assert change_types == ["INITIAL", "MANUAL_UPDATE"]

    update_entry = trail["entries"][1]
    assert update_entry["change_type"] == "MANUAL_UPDATE"
    assert update_entry["base_price"] == 520_000.0


def test_audit_trail_archive_on_supersede(client: TestClient):
    """Superseding a pricing record must append an ARCHIVE entry on the old record."""
    _, unit_id = _create_hierarchy(client, "PRJ-AT05")
    first = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    first_id = first["id"]

    # Approve first record then supersede it.
    client.post(f"/api/v1/pricing/{first_id}/approve", json={"approved_by": "mgr"})
    client.post(
        f"/api/v1/units/{unit_id}/pricing",
        json={**_VALID_PRICING_PAYLOAD, "base_price": 600_000.0},
    )

    trail = client.get(f"/api/v1/pricing/{first_id}/audit-trail").json()
    change_types = [e["change_type"] for e in trail["entries"]]
    assert "ARCHIVE" in change_types

    archive_entry = next(e for e in trail["entries"] if e["change_type"] == "ARCHIVE")
    assert archive_entry["pricing_status"] == "archived"


def test_audit_trail_entries_oldest_first(client: TestClient):
    """Audit entries must be returned in chronological order (oldest first)."""
    _, unit_id = _create_hierarchy(client, "PRJ-AT06")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    pricing_id = record["id"]

    # Apply override then approve — produces INITIAL → OVERRIDE → APPROVAL.
    client.post(
        f"/api/v1/pricing/{pricing_id}/override",
        json={
            "override_amount": 1_000.0,
            "override_reason": "Test",
            "requested_by": "sales-mgr-1",
            "role": "sales_manager",
        },
    )
    client.post(f"/api/v1/pricing/{pricing_id}/approve", json={"approved_by": "mgr"})

    trail = client.get(f"/api/v1/pricing/{pricing_id}/audit-trail").json()
    change_types = [e["change_type"] for e in trail["entries"]]
    assert change_types == ["INITIAL", "OVERRIDE", "APPROVAL"]


def test_audit_trail_not_found_returns_404(client: TestClient):
    """GET audit trail for a non-existent pricing_id must return 404."""
    resp = client.get("/api/v1/pricing/no-such-id/audit-trail")
    assert resp.status_code == 404


def test_audit_trail_response_shape(client: TestClient):
    """Audit trail response must contain all required fields."""
    _, unit_id = _create_hierarchy(client, "PRJ-AT07")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    pricing_id = record["id"]

    trail = client.get(f"/api/v1/pricing/{pricing_id}/audit-trail").json()
    assert "pricing_id" in trail
    assert "unit_id" in trail
    assert "total" in trail
    assert "entries" in trail

    entry = trail["entries"][0]
    required_fields = {
        "id", "pricing_id", "unit_id", "change_type",
        "base_price", "manual_adjustment", "final_price",
        "pricing_status", "currency", "created_at",
    }
    for field in required_fields:
        assert field in entry, f"Missing field '{field}' in audit entry"


def test_full_lifecycle_audit_trail(client: TestClient):
    """Full pricing lifecycle produces a correct change_type sequence."""
    _, unit_id = _create_hierarchy(client, "PRJ-AT08")

    # Create first pricing record → INITIAL
    first = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    first_id = first["id"]

    # Approve first record → APPROVAL
    client.post(f"/api/v1/pricing/{first_id}/approve", json={"approved_by": "finance-mgr"})

    # Supersede by creating second record → ARCHIVE on first, INITIAL on second
    second = client.post(
        f"/api/v1/units/{unit_id}/pricing",
        json={**_VALID_PRICING_PAYLOAD, "base_price": 600_000.0},
    ).json()
    second_id = second["id"]

    # Apply override on second record → OVERRIDE
    client.post(
        f"/api/v1/pricing/{second_id}/override",
        json={
            "override_amount": 3_000.0,
            "override_reason": "Negotiated concession",
            "requested_by": "sales-mgr-1",
            "role": "sales_manager",
        },
    )

    # Check first record's audit trail: INITIAL → APPROVAL → ARCHIVE
    first_trail = client.get(f"/api/v1/pricing/{first_id}/audit-trail").json()
    assert [e["change_type"] for e in first_trail["entries"]] == [
        "INITIAL", "APPROVAL", "ARCHIVE"
    ]

    # Check second record's audit trail: INITIAL → OVERRIDE
    second_trail = client.get(f"/api/v1/pricing/{second_id}/audit-trail").json()
    assert [e["change_type"] for e in second_trail["entries"]] == [
        "INITIAL", "OVERRIDE"
    ]
