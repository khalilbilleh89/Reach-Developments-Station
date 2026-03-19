"""
Smoke test: Registry (Conveyancing)

Verifies that a registry case can be created for a sold unit:
  Sales Contract → Registry Case → Milestones + Document Checklist

Assertions:
  - Hierarchy enforcement works (project_id must match unit's project)
  - Registry case is created successfully
  - Default milestones are initialised on case creation
  - Default document checklist is initialised on case creation
"""

from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_hierarchy(client: TestClient, proj_code: str = "SMKR-001") -> dict:
    """Create project hierarchy and return ids."""
    project_id = client.post(
        "/api/v1/projects",
        json={"name": "Registry Smoke Project", "code": proj_code},
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
        json={"unit_number": "101", "unit_type": "studio", "internal_area": 80.0},
    ).json()["id"]
    return {"project_id": project_id, "unit_id": unit_id}


def _create_buyer(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Registry Buyer", "email": email, "phone": "+9710000002"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_contract(
    client: TestClient, unit_id: str, buyer_id: str, contract_number: str
) -> dict:
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": "2026-01-15",
            "contract_price": 600_000.0,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_registry_case(
    client: TestClient, project_id: str, unit_id: str, contract_id: str
) -> dict:
    resp = client.post(
        "/api/v1/registry/cases",
        json={
            "project_id": project_id,
            "unit_id": unit_id,
            "sale_contract_id": contract_id,
            "buyer_name": "Registry Buyer",
            "jurisdiction": "Dubai",
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_registry_case_created(client: TestClient):
    """Creating a registry case returns a valid case with correct references."""
    ids = _build_hierarchy(client, "SMKR-001")
    buyer_id = _create_buyer(client, "reg.a@example.com")
    contract = _create_contract(client, ids["unit_id"], buyer_id, "CNT-SMKR-A1")
    case = _create_registry_case(
        client, ids["project_id"], ids["unit_id"], contract["id"]
    )

    assert case["project_id"] == ids["project_id"]
    assert case["unit_id"] == ids["unit_id"]
    assert case["sale_contract_id"] == contract["id"]


def test_registry_case_derives_correct_project_id(client: TestClient):
    """Server-derived project_id must equal the hierarchy's project."""
    ids = _build_hierarchy(client, "SMKR-002")
    buyer_id = _create_buyer(client, "reg.b@example.com")
    contract = _create_contract(client, ids["unit_id"], buyer_id, "CNT-SMKR-B1")
    case = _create_registry_case(
        client, ids["project_id"], ids["unit_id"], contract["id"]
    )

    # project_id is server-derived from the hierarchy; must match
    assert case["project_id"] == ids["project_id"]


def test_registry_case_milestones_created(client: TestClient):
    """Default milestones are auto-created when a registry case is opened."""
    ids = _build_hierarchy(client, "SMKR-003")
    buyer_id = _create_buyer(client, "reg.c@example.com")
    contract = _create_contract(client, ids["unit_id"], buyer_id, "CNT-SMKR-C1")
    case = _create_registry_case(
        client, ids["project_id"], ids["unit_id"], contract["id"]
    )

    milestones = client.get(f"/api/v1/registry/cases/{case['id']}/milestones").json()
    assert len(milestones) > 0


def test_registry_case_document_checklist_created(client: TestClient):
    """Default document checklist is auto-created when a registry case is opened."""
    ids = _build_hierarchy(client, "SMKR-004")
    buyer_id = _create_buyer(client, "reg.d@example.com")
    contract = _create_contract(client, ids["unit_id"], buyer_id, "CNT-SMKR-D1")
    case = _create_registry_case(
        client, ids["project_id"], ids["unit_id"], contract["id"]
    )

    documents = client.get(f"/api/v1/registry/cases/{case['id']}/documents").json()
    assert len(documents) > 0


def test_registry_hierarchy_enforcement_wrong_project_id(client: TestClient):
    """Supplying a mismatched project_id must be rejected with 422."""
    ids = _build_hierarchy(client, "SMKR-005")
    buyer_id = _create_buyer(client, "reg.e@example.com")
    contract = _create_contract(client, ids["unit_id"], buyer_id, "CNT-SMKR-E1")

    resp = client.post(
        "/api/v1/registry/cases",
        json={
            "project_id": "wrong-project-id",
            "unit_id": ids["unit_id"],
            "sale_contract_id": contract["id"],
            "buyer_name": "Registry Buyer",
        },
    )
    assert resp.status_code == 422
