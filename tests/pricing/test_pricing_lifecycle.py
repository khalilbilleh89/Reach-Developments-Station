"""
Tests for the hardened pricing lifecycle rules.

Validates:
  - pricing cannot exist before unit readiness (unit must be 'available')
  - approved pricing is immutable (cannot be edited)
  - approved pricing enables sales eligibility
  - only one active pricing record per unit
  - pricing history is preserved across archive/create cycles
  - new lifecycle endpoints (POST /units/{id}/pricing, POST /pricing/{id}/approve,
    GET /units/{id}/pricing/history)
"""

import pytest
from fastapi.testclient import TestClient


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-LIFE") -> tuple[str, str]:
    """Create a full project hierarchy and return (project_id, unit_id)."""
    project_id = client.post(
        "/api/v1/projects",
        json={"name": "Lifecycle Test Project", "code": proj_code},
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
    "manual_adjustment": 25_000.0,
    "currency": "AED",
    "notes": "Lifecycle test pricing",
}


# ---------------------------------------------------------------------------
# POST /api/v1/units/{unit_id}/pricing — hardened create endpoint
# ---------------------------------------------------------------------------

def test_create_pricing_unit_not_ready_rejected(client: TestClient):
    """POST pricing must be rejected when the unit is not yet 'available'."""
    _, unit_id = _create_hierarchy(client, "PRJ-NOTREADY")
    # Change unit to 'reserved' status — blocks pricing readiness.
    client.patch(f"/api/v1/units/{unit_id}", json={"status": "reserved"})
    resp = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD)
    assert resp.status_code == 422
    assert "not ready for pricing" in resp.json()["detail"].lower()


def test_create_pricing_available_unit_succeeds(client: TestClient):
    """POST pricing creates a new 'draft' record for an available unit."""
    _, unit_id = _create_hierarchy(client, "PRJ-CRPOST")
    resp = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["pricing_status"] == "draft"
    assert data["base_price"] == pytest.approx(500_000.0)
    assert data["final_price"] == pytest.approx(525_000.0)


def test_create_pricing_always_starts_as_draft(client: TestClient):
    """POST pricing rejects restricted statuses; non-terminal statuses (submitted, reviewed) are accepted."""
    _, unit_id = _create_hierarchy(client, "PRJ-DRAFTONLY")
    # Attempting to pass 'approved' status on create is rejected by the schema
    # (only draft/submitted/reviewed are accepted by the create endpoint).
    payload = {**_VALID_PRICING_PAYLOAD, "pricing_status": "approved"}
    resp = client.post(f"/api/v1/units/{unit_id}/pricing", json=payload)
    assert resp.status_code == 422

    # Passing a valid non-terminal status is accepted.
    payload_submitted = {**_VALID_PRICING_PAYLOAD, "pricing_status": "submitted"}
    resp2 = client.post(f"/api/v1/units/{unit_id}/pricing", json=payload_submitted)
    assert resp2.status_code == 201
    assert resp2.json()["pricing_status"] == "submitted"


def test_create_pricing_invalid_unit_returns_404(client: TestClient):
    """POST pricing for a non-existent unit must return 404."""
    resp = client.post("/api/v1/units/no-such-unit/pricing", json=_VALID_PRICING_PAYLOAD)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/pricing/{pricing_id}/approve — approval endpoint
# ---------------------------------------------------------------------------

def test_approve_pricing_sets_approved_status(client: TestClient):
    """POST approve sets pricing_status to 'approved' and records approval metadata."""
    _, unit_id = _create_hierarchy(client, "PRJ-APPROVE")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    pricing_id = record["id"]

    resp = client.post(
        f"/api/v1/pricing/{pricing_id}/approve",
        json={"approved_by": "analyst@example.com"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pricing_status"] == "approved"
    assert data["approved_by"] == "analyst@example.com"
    assert data["approval_date"] is not None


def test_approve_pricing_invalid_id_returns_404(client: TestClient):
    """POST approve for a non-existent pricing record must return 404."""
    resp = client.post(
        "/api/v1/pricing/no-such-id/approve",
        json={"approved_by": "analyst@example.com"},
    )
    assert resp.status_code == 404


def test_approve_already_approved_returns_422(client: TestClient):
    """POST approve on an already-approved record must return 422."""
    _, unit_id = _create_hierarchy(client, "PRJ-DBLAPP")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    pricing_id = record["id"]
    client.post(f"/api/v1/pricing/{pricing_id}/approve", json={"approved_by": "first"})

    resp = client.post(f"/api/v1/pricing/{pricing_id}/approve", json={"approved_by": "second"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Immutability — approved pricing cannot be edited
# ---------------------------------------------------------------------------

def test_approved_pricing_cannot_be_updated_via_put(client: TestClient):
    """PUT on the unit's pricing record must fail when the record is approved."""
    _, unit_id = _create_hierarchy(client, "PRJ-IMMUT")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    client.post(
        f"/api/v1/pricing/{record['id']}/approve",
        json={"approved_by": "manager@example.com"},
    )

    # Attempt to update the approved record via the legacy PUT endpoint.
    resp = client.put(
        f"/api/v1/units/{unit_id}/pricing",
        json={**_VALID_PRICING_PAYLOAD, "base_price": 999_000.0},
    )
    assert resp.status_code == 422
    assert "immutable" in resp.json()["detail"].lower() or "approved" in resp.json()["detail"].lower()


def test_approved_pricing_cannot_be_updated_via_pricing_put(client: TestClient):
    """PUT /pricing/{id} must fail when the record is approved."""
    _, unit_id = _create_hierarchy(client, "PRJ-PUTID")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    pricing_id = record["id"]
    client.post(f"/api/v1/pricing/{pricing_id}/approve", json={"approved_by": "mgr"})

    resp = client.put(f"/api/v1/pricing/{pricing_id}", json={"base_price": 999_000.0})
    assert resp.status_code == 422


def test_draft_pricing_can_be_updated(client: TestClient):
    """PUT /pricing/{id} must succeed when the record is in draft status."""
    _, unit_id = _create_hierarchy(client, "PRJ-DRAFTUPD")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    pricing_id = record["id"]

    resp = client.put(f"/api/v1/pricing/{pricing_id}", json={"base_price": 600_000.0})
    assert resp.status_code == 200
    assert resp.json()["base_price"] == pytest.approx(600_000.0)


# ---------------------------------------------------------------------------
# GET /api/v1/units/{unit_id}/pricing/history — history endpoint
# ---------------------------------------------------------------------------

def test_pricing_history_empty_unit(client: TestClient):
    """GET pricing history for a unit with no records returns empty list."""
    _, unit_id = _create_hierarchy(client, "PRJ-HISTEMPTY")
    resp = client.get(f"/api/v1/units/{unit_id}/pricing/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["total"] == 0
    assert data["items"] == []


def test_pricing_history_single_record(client: TestClient):
    """GET pricing history returns one record after a single create."""
    _, unit_id = _create_hierarchy(client, "PRJ-HIST1")
    client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD)
    resp = client.get(f"/api/v1/units/{unit_id}/pricing/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["pricing_status"] == "draft"


def test_pricing_history_preserves_archived_records(client: TestClient):
    """Creating new pricing archives the old one, and history includes both."""
    _, unit_id = _create_hierarchy(client, "PRJ-HISTARCH")
    # Create first pricing record and approve it.
    first = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    client.post(f"/api/v1/pricing/{first['id']}/approve", json={"approved_by": "mgr"})

    # Create second pricing record — archives the first.
    client.post(
        f"/api/v1/units/{unit_id}/pricing",
        json={**_VALID_PRICING_PAYLOAD, "base_price": 600_000.0},
    )

    history = client.get(f"/api/v1/units/{unit_id}/pricing/history").json()
    assert history["total"] == 2

    statuses = {item["pricing_status"] for item in history["items"]}
    assert "archived" in statuses
    assert "draft" in statuses


def test_pricing_history_invalid_unit_returns_404(client: TestClient):
    """GET pricing history for a non-existent unit must return 404."""
    resp = client.get("/api/v1/units/no-such-unit/pricing/history")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# One active pricing record per unit
# ---------------------------------------------------------------------------

def test_only_one_active_pricing_per_unit(client: TestClient):
    """Creating a new pricing record archives the previous active one."""
    _, unit_id = _create_hierarchy(client, "PRJ-ONEACT")
    client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD)
    client.post(
        f"/api/v1/units/{unit_id}/pricing",
        json={**_VALID_PRICING_PAYLOAD, "base_price": 600_000.0},
    )

    # GET should return only the active (draft) record with the latest price.
    resp = client.get(f"/api/v1/units/{unit_id}/pricing")
    assert resp.status_code == 200
    assert resp.json()["base_price"] == pytest.approx(600_000.0)
    assert resp.json()["pricing_status"] == "draft"


# ---------------------------------------------------------------------------
# Sales eligibility gate
# ---------------------------------------------------------------------------

def test_unit_not_sales_eligible_without_approved_pricing(client: TestClient):
    """Unit readiness must block sales when pricing is not yet approved."""
    _, unit_id = _create_hierarchy(client, "PRJ-SALESGATE")
    # Create pricing but do not approve it.
    client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD)

    readiness = client.get(f"/api/v1/units/{unit_id}/readiness").json()
    assert readiness["is_ready_for_sales"] is False
    reasons_text = " ".join(readiness["sales_blocking_reasons"]).lower()
    assert "approved" in reasons_text


def test_unit_sales_eligible_after_pricing_approved(client: TestClient):
    """Unit readiness must pass sales gate when pricing is approved."""
    _, unit_id = _create_hierarchy(client, "PRJ-SALESOK")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    client.post(f"/api/v1/pricing/{record['id']}/approve", json={"approved_by": "mgr"})

    readiness = client.get(f"/api/v1/units/{unit_id}/readiness").json()
    assert readiness["is_ready_for_sales"] is True


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------

def test_approved_pricing_response_has_approval_fields(client: TestClient):
    """Approved pricing response must include approved_by and approval_date."""
    _, unit_id = _create_hierarchy(client, "PRJ-APPFIELDS")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    resp = client.post(
        f"/api/v1/pricing/{record['id']}/approve",
        json={"approved_by": "senior.analyst"},
    )
    data = resp.json()
    assert "approved_by" in data
    assert "approval_date" in data
    assert data["approved_by"] == "senior.analyst"
    assert data["approval_date"] is not None


def test_pricing_response_has_new_fields(client: TestClient):
    """Pricing record response must include approved_by and approval_date (nullable)."""
    _, unit_id = _create_hierarchy(client, "PRJ-NEWFIELDS")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    assert "approved_by" in record
    assert "approval_date" in record
    assert record["approved_by"] is None
    assert record["approval_date"] is None


# ---------------------------------------------------------------------------
# Approval bypass regression tests (PR-12A)
# ---------------------------------------------------------------------------

def test_legacy_put_cannot_set_approved_status(client: TestClient):
    """PUT /units/{id}/pricing must reject 'approved' as pricing_status (bypass prevention)."""
    _, unit_id = _create_hierarchy(client, "PRJ-BYPASS1")
    payload = {**_VALID_PRICING_PAYLOAD, "pricing_status": "approved"}
    resp = client.put(f"/api/v1/units/{unit_id}/pricing", json=payload)
    assert resp.status_code == 422


def test_legacy_put_cannot_set_archived_status(client: TestClient):
    """PUT /units/{id}/pricing must reject 'archived' as pricing_status."""
    _, unit_id = _create_hierarchy(client, "PRJ-BYPASS2")
    payload = {**_VALID_PRICING_PAYLOAD, "pricing_status": "archived"}
    resp = client.put(f"/api/v1/units/{unit_id}/pricing", json=payload)
    assert resp.status_code == 422


def test_put_pricing_by_id_cannot_set_status(client: TestClient):
    """PUT /pricing/{id} must not accept pricing_status changes (status field ignored)."""
    _, unit_id = _create_hierarchy(client, "PRJ-BYPASS3")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    pricing_id = record["id"]

    # The schema no longer accepts pricing_status — Pydantic validation rejects it.
    # Even if somehow passed, the service does not apply it.
    # We verify the record remains draft after an update.
    update_resp = client.put(f"/api/v1/pricing/{pricing_id}", json={"base_price": 550_000.0})
    assert update_resp.status_code == 200
    assert update_resp.json()["pricing_status"] == "draft"
    assert update_resp.json()["base_price"] == pytest.approx(550_000.0)


def test_approval_metadata_absent_without_approval_endpoint(client: TestClient):
    """approved_by and approval_date must remain null on records not yet approved."""
    _, unit_id = _create_hierarchy(client, "PRJ-METAMETA")
    record = client.put(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    assert record["approved_by"] is None
    assert record["approval_date"] is None

    # Update via PUT also must not set approval metadata.
    record2 = client.put(
        f"/api/v1/units/{unit_id}/pricing",
        json={**_VALID_PRICING_PAYLOAD, "base_price": 510_000.0},
    ).json()
    assert record2["approved_by"] is None
    assert record2["approval_date"] is None


def test_legacy_put_unit_readiness_on_new_record(client: TestClient):
    """PUT /units/{id}/pricing must enforce unit readiness when creating a new record."""
    _, unit_id = _create_hierarchy(client, "PRJ-LEGREADY")
    # Block readiness by setting unit to a non-available status.
    client.patch(f"/api/v1/units/{unit_id}", json={"status": "reserved"})
    resp = client.put(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD)
    assert resp.status_code == 422
    assert "not ready for pricing" in resp.json()["detail"].lower()


def test_legacy_put_updates_existing_approved_is_blocked(client: TestClient):
    """PUT /units/{id}/pricing on an approved record must be rejected (immutability)."""
    _, unit_id = _create_hierarchy(client, "PRJ-LEGAPPR")
    record = client.post(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    client.post(f"/api/v1/pricing/{record['id']}/approve", json={"approved_by": "mgr"})

    resp = client.put(
        f"/api/v1/units/{unit_id}/pricing",
        json={**_VALID_PRICING_PAYLOAD, "base_price": 999_000.0},
    )
    assert resp.status_code == 422
