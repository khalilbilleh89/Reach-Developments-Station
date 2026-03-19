"""
Tests for the registry/conveyancing API endpoints.

Validates HTTP behaviour, request/response contracts, and registry
workflow rules.
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-REG") -> tuple[str, str]:
    """Create a full project → unit hierarchy and return (project_id, unit_id)."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "Reg Project", "code": proj_code}
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
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 100.0,
        },
    ).json()["id"]
    return project_id, unit_id


def _create_buyer(client: TestClient, email: str = "buyer@reg.com") -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Test Buyer", "email": email, "phone": "+9620000002"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_contract(client: TestClient, unit_id: str, buyer_id: str, contract_number: str = "CNT-REG-001") -> str:
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": "2026-03-01",
            "contract_price": 500_000.0,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_case(
    client: TestClient,
    project_id: str,
    unit_id: str,
    contract_id: str,
    buyer_name: str = "Test Buyer",
) -> str:
    resp = client.post(
        "/api/v1/registry/cases",
        json={
            "project_id": project_id,
            "unit_id": unit_id,
            "sale_contract_id": contract_id,
            "buyer_name": buyer_name,
            "opened_at": "2026-03-01",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Case creation tests
# ---------------------------------------------------------------------------

def test_create_registration_case(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RC1")
    buyer_id = _create_buyer(client, "rc1@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RC1-001")

    resp = client.post(
        "/api/v1/registry/cases",
        json={
            "project_id": project_id,
            "unit_id": unit_id,
            "sale_contract_id": contract_id,
            "buyer_name": "Test Buyer",
            "opened_at": "2026-03-01",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["unit_id"] == unit_id
    assert data["sale_contract_id"] == contract_id
    assert data["status"] == "draft"
    assert "id" in data


def test_create_case_defaults_milestones_and_documents(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RC2")
    buyer_id = _create_buyer(client, "rc2@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RC2-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    # Milestones should be initialised automatically
    ms_resp = client.get(f"/api/v1/registry/cases/{case_id}/milestones")
    assert ms_resp.status_code == 200
    milestones = ms_resp.json()
    assert len(milestones) > 0
    assert milestones[0]["status"] == "pending"
    # Ordered by sequence
    sequences = [m["sequence"] for m in milestones]
    assert sequences == sorted(sequences)

    # Documents should be initialised automatically
    doc_resp = client.get(f"/api/v1/registry/cases/{case_id}/documents")
    assert doc_resp.status_code == 200
    docs = doc_resp.json()
    assert len(docs) > 0
    assert all(d["is_required"] is True for d in docs)
    assert all(d["is_received"] is False for d in docs)


def test_create_case_invalid_contract_returns_404(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RC3")
    resp = client.post(
        "/api/v1/registry/cases",
        json={
            "project_id": project_id,
            "unit_id": unit_id,
            "sale_contract_id": "no-such-contract",
            "buyer_name": "Ghost Buyer",
        },
    )
    assert resp.status_code == 404


def test_create_case_contract_unit_mismatch_returns_422(client: TestClient):
    """Contract linked to a different unit must be rejected."""
    project_id, unit_id_a = _create_hierarchy(client, "PRJ-RC4A")
    _, unit_id_b = _create_hierarchy(client, "PRJ-RC4B")
    buyer_id = _create_buyer(client, "rc4@example.com")
    # Contract is on unit_id_a
    contract_id = _create_contract(client, unit_id_a, buyer_id, "CNT-RC4-001")

    # Try to open a case referencing unit_id_b
    resp = client.post(
        "/api/v1/registry/cases",
        json={
            "project_id": project_id,
            "unit_id": unit_id_b,
            "sale_contract_id": contract_id,
            "buyer_name": "Test Buyer",
        },
    )
    assert resp.status_code == 422


def test_duplicate_active_case_per_unit_returns_409(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RC5")
    buyer_id = _create_buyer(client, "rc5@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RC5-001")
    _create_case(client, project_id, unit_id, contract_id)

    resp = client.post(
        "/api/v1/registry/cases",
        json={
            "project_id": project_id,
            "unit_id": unit_id,
            "sale_contract_id": contract_id,
            "buyer_name": "Test Buyer",
        },
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Case retrieval tests
# ---------------------------------------------------------------------------

def test_get_case(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RG1")
    buyer_id = _create_buyer(client, "rg1@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RG1-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    resp = client.get(f"/api/v1/registry/cases/{case_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == case_id


def test_get_case_not_found(client: TestClient):
    resp = client.get("/api/v1/registry/cases/no-such-case")
    assert resp.status_code == 404


def test_get_case_by_sale_contract(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RBYS")
    buyer_id = _create_buyer(client, "rbys@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RBYS-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    resp = client.get(f"/api/v1/registry/cases/by-sale/{contract_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == case_id


def test_get_case_by_sale_contract_not_found(client: TestClient):
    resp = client.get("/api/v1/registry/cases/by-sale/no-such-contract")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Project cases and summary tests
# ---------------------------------------------------------------------------

def test_list_project_cases(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RLPC")
    buyer_id = _create_buyer(client, "rlpc@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RLPC-001")
    _create_case(client, project_id, unit_id, contract_id)

    resp = client.get(f"/api/v1/registry/projects/{project_id}/cases")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_list_project_cases_not_found(client: TestClient):
    resp = client.get("/api/v1/registry/projects/no-such-project/cases")
    assert resp.status_code == 404


def test_get_project_summary(client: TestClient):
    """A unit with an open registry case is in the pipeline — not 'sold_not_registered'."""
    project_id, unit_id = _create_hierarchy(client, "PRJ-RSUMM")
    buyer_id = _create_buyer(client, "rsumm@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RSUMM-001")
    _create_case(client, project_id, unit_id, contract_id)

    resp = client.get(f"/api/v1/registry/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["total_sold_units"] == 1
    assert data["registration_cases_open"] == 1
    assert data["registration_cases_completed"] == 0
    # Unit already has an open case → it is in the pipeline, not "not registered"
    assert data["sold_not_registered"] == 0
    assert data["registration_completion_ratio"] == pytest.approx(0.0)


def test_summary_sold_no_case_counts_as_not_registered(client: TestClient):
    """A sold unit with no registry case at all must appear in sold_not_registered."""
    project_id, unit_id = _create_hierarchy(client, "PRJ-RSNO")
    buyer_id = _create_buyer(client, "rsno@example.com")
    _create_contract(client, unit_id, buyer_id, "CNT-RSNO-001")
    # No case opened

    resp = client.get(f"/api/v1/registry/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sold_units"] == 1
    assert data["registration_cases_open"] == 0
    assert data["registration_cases_completed"] == 0
    assert data["sold_not_registered"] == 1


def test_summary_completed_case_not_counted_as_not_registered(client: TestClient):
    """A sold unit with a completed case must not appear in sold_not_registered."""
    project_id, unit_id = _create_hierarchy(client, "PRJ-RSCMP")
    buyer_id = _create_buyer(client, "rscmp@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RSCMP-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    # Complete all milestones, then complete the case
    milestones = client.get(f"/api/v1/registry/cases/{case_id}/milestones").json()
    for ms in milestones:
        client.patch(
            f"/api/v1/registry/cases/{case_id}/milestones/{ms['id']}",
            json={"status": "completed"},
        )
    client.patch(
        f"/api/v1/registry/cases/{case_id}",
        json={"status": "completed"},
    )

    resp = client.get(f"/api/v1/registry/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["registration_cases_completed"] == 1
    assert data["sold_not_registered"] == 0
    assert data["registration_completion_ratio"] == pytest.approx(1.0)


def test_get_project_summary_not_found(client: TestClient):
    resp = client.get("/api/v1/registry/projects/no-such-project/summary")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Case update tests
# ---------------------------------------------------------------------------

def test_update_case_status(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RUCS")
    buyer_id = _create_buyer(client, "rucs@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RUCS-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    resp = client.patch(
        f"/api/v1/registry/cases/{case_id}",
        json={"status": "in_progress"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_update_case_notes(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RUCN")
    buyer_id = _create_buyer(client, "rucn@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RUCN-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    resp = client.patch(
        f"/api/v1/registry/cases/{case_id}",
        json={"notes": "Awaiting NOC from developer"},
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Awaiting NOC from developer"


def test_complete_case_requires_all_milestones_done(client: TestClient):
    """Transitioning to COMPLETED while milestones are pending must be rejected."""
    project_id, unit_id = _create_hierarchy(client, "PRJ-RUCC")
    buyer_id = _create_buyer(client, "rucc@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RUCC-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    resp = client.patch(
        f"/api/v1/registry/cases/{case_id}",
        json={"status": "completed"},
    )
    assert resp.status_code == 409


def test_complete_case_after_all_milestones_done(client: TestClient):
    """Completing a case after marking all milestones complete must succeed."""
    project_id, unit_id = _create_hierarchy(client, "PRJ-RUCCOK")
    buyer_id = _create_buyer(client, "ruccok@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RUCCOK-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    # Mark all milestones as completed
    milestones = client.get(f"/api/v1/registry/cases/{case_id}/milestones").json()
    for ms in milestones:
        client.patch(
            f"/api/v1/registry/cases/{case_id}/milestones/{ms['id']}",
            json={"status": "completed"},
        )

    resp = client.patch(
        f"/api/v1/registry/cases/{case_id}",
        json={"status": "completed"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_completed_case_immutable_except_notes(client: TestClient):
    """A completed case must reject status changes, only allow notes updates."""
    project_id, unit_id = _create_hierarchy(client, "PRJ-RUCIMM")
    buyer_id = _create_buyer(client, "rucimm@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RUCIMM-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    # Complete all milestones first
    milestones = client.get(f"/api/v1/registry/cases/{case_id}/milestones").json()
    for ms in milestones:
        client.patch(
            f"/api/v1/registry/cases/{case_id}/milestones/{ms['id']}",
            json={"status": "completed"},
        )

    # Complete the case
    client.patch(
        f"/api/v1/registry/cases/{case_id}",
        json={"status": "completed"},
    )

    # Attempt to change status on a completed case
    resp = client.patch(
        f"/api/v1/registry/cases/{case_id}",
        json={"status": "in_progress"},
    )
    assert resp.status_code == 409

    # Notes update must still succeed
    resp = client.patch(
        f"/api/v1/registry/cases/{case_id}",
        json={"notes": "Admin correction note"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Milestone and Document update tests
# ---------------------------------------------------------------------------

def test_update_milestone(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RMS")
    buyer_id = _create_buyer(client, "rms@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RMS-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    milestones = client.get(f"/api/v1/registry/cases/{case_id}/milestones").json()
    ms_id = milestones[0]["id"]

    resp = client.patch(
        f"/api/v1/registry/cases/{case_id}/milestones/{ms_id}",
        json={"status": "in_progress", "remarks": "Started"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "in_progress"
    assert data["remarks"] == "Started"


def test_update_milestone_not_found(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RMSF")
    buyer_id = _create_buyer(client, "rmsf@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RMSF-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    resp = client.patch(
        f"/api/v1/registry/cases/{case_id}/milestones/no-such-milestone",
        json={"status": "completed"},
    )
    assert resp.status_code == 404


def test_update_document(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RDOC")
    buyer_id = _create_buyer(client, "rdoc@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RDOC-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    docs = client.get(f"/api/v1/registry/cases/{case_id}/documents").json()
    doc_id = docs[0]["id"]

    resp = client.patch(
        f"/api/v1/registry/cases/{case_id}/documents/{doc_id}",
        json={
            "is_received": True,
            "received_at": "2026-03-10",
            "reference_number": "REF-001",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_received"] is True
    assert data["received_at"] == "2026-03-10"
    assert data["reference_number"] == "REF-001"


def test_update_document_not_found(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "PRJ-RDOCF")
    buyer_id = _create_buyer(client, "rdocf@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RDOCF-001")
    case_id = _create_case(client, project_id, unit_id, contract_id)

    resp = client.patch(
        f"/api/v1/registry/cases/{case_id}/documents/no-such-doc",
        json={"is_received": True},
    )
    assert resp.status_code == 404
