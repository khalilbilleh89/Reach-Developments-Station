"""
Tests for the Construction Contractor & Procurement Tracking API.

PR-CONSTR-043 — Contractor & Procurement Tracking

Validates:
- POST /construction/contractors
- GET  /construction/contractors
- GET  /construction/contractors/{id}
- PATCH /construction/contractors/{id}
- DELETE /construction/contractors/{id}

- POST /construction/packages
- GET  /construction/scopes/{id}/packages
- GET  /construction/packages/{id}
- PATCH /construction/packages/{id}
- DELETE /construction/packages/{id}
- POST /construction/packages/{id}/assign-contractor
- POST /construction/packages/{id}/milestones/{milestone_id}
- GET  /construction/scopes/{id}/procurement-overview

Error cases:
- 404 on unknown contractor / package / scope / milestone
- 409 on duplicate contractor code or package code within scope
- 422 on invalid payloads (negative values, missing required fields)
"""

from decimal import Decimal

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str = "PC-001") -> str:
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
        json={"scope_id": scope_id, "name": name, "sequence": sequence, "duration_days": duration_days},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_contractor(
    client: TestClient,
    code: str = "CTR-001",
    name: str = "ABC Builders",
    contractor_type: str = "main_contractor",
) -> dict:
    resp = client.post(
        "/api/v1/construction/contractors",
        json={
            "contractor_code": code,
            "contractor_name": name,
            "contractor_type": contractor_type,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_package(
    client: TestClient,
    scope_id: str,
    code: str = "PKG-001",
    name: str = "Civil Package",
    package_type: str = "civil",
    planned_value: float = 500000.0,
) -> dict:
    resp = client.post(
        "/api/v1/construction/packages",
        json={
            "scope_id": scope_id,
            "package_code": code,
            "package_name": name,
            "package_type": package_type,
            "planned_value": planned_value,
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Contractor CRUD
# ---------------------------------------------------------------------------


def test_create_contractor_success(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/construction/contractors",
        json={
            "contractor_code": "CTR-010",
            "contractor_name": "XYZ Builders",
            "contractor_type": "main_contractor",
            "contact_name": "John Smith",
            "contact_email": "john@xyz.com",
            "phone": "+971501234567",
            "status": "active",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["contractor_code"] == "CTR-010"
    assert data["contractor_name"] == "XYZ Builders"
    assert data["contractor_type"] == "main_contractor"
    assert data["contact_name"] == "John Smith"
    assert data["status"] == "active"
    assert "id" in data
    assert "created_at" in data


def test_create_contractor_duplicate_code_409(client: TestClient) -> None:
    _create_contractor(client, code="CTR-DUP")
    resp = client.post(
        "/api/v1/construction/contractors",
        json={"contractor_code": "CTR-DUP", "contractor_name": "Another Builders"},
    )
    assert resp.status_code == 409


def test_create_contractor_missing_required_fields_422(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/construction/contractors",
        json={"contractor_name": "No Code Builders"},
    )
    assert resp.status_code == 422


def test_list_contractors(client: TestClient) -> None:
    _create_contractor(client, code="CTR-L01", name="Builder A")
    _create_contractor(client, code="CTR-L02", name="Builder B")

    resp = client.get("/api/v1/construction/contractors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_contractors_pagination(client: TestClient) -> None:
    for i in range(5):
        _create_contractor(client, code=f"CTR-P{i:02d}", name=f"Builder {i}")

    resp = client.get("/api/v1/construction/contractors?skip=2&limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2


def test_get_contractor_by_id(client: TestClient) -> None:
    c = _create_contractor(client, code="CTR-G01")
    resp = client.get(f"/api/v1/construction/contractors/{c['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == c["id"]
    assert data["contractor_code"] == "CTR-G01"


def test_get_contractor_not_found_404(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/contractors/nonexistent-id")
    assert resp.status_code == 404


def test_update_contractor(client: TestClient) -> None:
    c = _create_contractor(client, code="CTR-U01", name="Old Name")

    resp = client.patch(
        f"/api/v1/construction/contractors/{c['id']}",
        json={"contractor_name": "New Name", "status": "inactive"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["contractor_name"] == "New Name"
    assert data["status"] == "inactive"
    assert data["contractor_code"] == "CTR-U01"


def test_update_contractor_not_found_404(client: TestClient) -> None:
    resp = client.patch(
        "/api/v1/construction/contractors/nonexistent-id",
        json={"contractor_name": "Ghost"},
    )
    assert resp.status_code == 404


def test_delete_contractor(client: TestClient) -> None:
    c = _create_contractor(client, code="CTR-D01")
    resp = client.delete(f"/api/v1/construction/contractors/{c['id']}")
    assert resp.status_code == 204

    get_resp = client.get(f"/api/v1/construction/contractors/{c['id']}")
    assert get_resp.status_code == 404


def test_delete_contractor_not_found_404(client: TestClient) -> None:
    resp = client.delete("/api/v1/construction/contractors/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Procurement Package CRUD
# ---------------------------------------------------------------------------


def test_create_package_success(client: TestClient) -> None:
    project_id = _create_project(client, "PC-PKG-001")
    scope = _create_scope(client, project_id)

    resp = client.post(
        "/api/v1/construction/packages",
        json={
            "scope_id": scope["id"],
            "package_code": "PKG-001",
            "package_name": "Structural Works",
            "package_type": "structural",
            "status": "draft",
            "planned_value": 1500000.00,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["scope_id"] == scope["id"]
    assert data["package_code"] == "PKG-001"
    assert data["package_name"] == "Structural Works"
    assert data["package_type"] == "structural"
    assert data["status"] == "draft"
    assert Decimal(data["planned_value"]) == Decimal("1500000.00")
    assert data["contractor_id"] is None


def test_create_package_with_contractor(client: TestClient) -> None:
    project_id = _create_project(client, "PC-PKG-002")
    scope = _create_scope(client, project_id)
    contractor = _create_contractor(client, code="CTR-PKG-002")

    resp = client.post(
        "/api/v1/construction/packages",
        json={
            "scope_id": scope["id"],
            "package_code": "PKG-002",
            "package_name": "MEP Package",
            "package_type": "mep",
            "contractor_id": contractor["id"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["contractor_id"] == contractor["id"]


def test_create_package_invalid_scope_404(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/construction/packages",
        json={
            "scope_id": "nonexistent-scope",
            "package_code": "PKG-X",
            "package_name": "Ghost Package",
        },
    )
    assert resp.status_code == 404


def test_create_package_invalid_contractor_404(client: TestClient) -> None:
    project_id = _create_project(client, "PC-PKG-003")
    scope = _create_scope(client, project_id)

    resp = client.post(
        "/api/v1/construction/packages",
        json={
            "scope_id": scope["id"],
            "package_code": "PKG-003",
            "package_name": "Bad Contractor Package",
            "contractor_id": "nonexistent-contractor",
        },
    )
    assert resp.status_code == 404


def test_create_package_duplicate_code_within_scope_409(client: TestClient) -> None:
    project_id = _create_project(client, "PC-PKG-004")
    scope = _create_scope(client, project_id)
    _create_package(client, scope["id"], code="DUP-CODE")

    resp = client.post(
        "/api/v1/construction/packages",
        json={
            "scope_id": scope["id"],
            "package_code": "DUP-CODE",
            "package_name": "Duplicate",
        },
    )
    assert resp.status_code == 409


def test_create_package_same_code_different_scope_ok(client: TestClient) -> None:
    """Same package code is allowed in different scopes."""
    project1_id = _create_project(client, "PC-PKG-005A")
    project2_id = _create_project(client, "PC-PKG-005B")
    scope1 = _create_scope(client, project1_id, name="Scope One")
    scope2 = _create_scope(client, project2_id, name="Scope Two")

    _create_package(client, scope1["id"], code="SAME-CODE")
    resp = client.post(
        "/api/v1/construction/packages",
        json={
            "scope_id": scope2["id"],
            "package_code": "SAME-CODE",
            "package_name": "Same Code Other Scope",
        },
    )
    assert resp.status_code == 201


def test_create_package_negative_value_422(client: TestClient) -> None:
    project_id = _create_project(client, "PC-PKG-006")
    scope = _create_scope(client, project_id)

    resp = client.post(
        "/api/v1/construction/packages",
        json={
            "scope_id": scope["id"],
            "package_code": "PKG-NEG",
            "package_name": "Negative Value",
            "planned_value": -100.00,
        },
    )
    assert resp.status_code == 422


def test_list_packages_for_scope(client: TestClient) -> None:
    project_id = _create_project(client, "PC-LIST-001")
    scope = _create_scope(client, project_id)

    _create_package(client, scope["id"], code="PKG-A", name="Package A")
    _create_package(client, scope["id"], code="PKG-B", name="Package B")

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/packages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_packages_scope_not_found_404(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/scopes/nonexistent-scope/packages")
    assert resp.status_code == 404


def test_get_package_by_id(client: TestClient) -> None:
    project_id = _create_project(client, "PC-GET-001")
    scope = _create_scope(client, project_id)
    pkg = _create_package(client, scope["id"], code="PKG-GET")

    resp = client.get(f"/api/v1/construction/packages/{pkg['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == pkg["id"]
    assert data["package_code"] == "PKG-GET"


def test_get_package_not_found_404(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/packages/nonexistent-id")
    assert resp.status_code == 404


def test_update_package(client: TestClient) -> None:
    project_id = _create_project(client, "PC-UPD-001")
    scope = _create_scope(client, project_id)
    pkg = _create_package(client, scope["id"], code="PKG-UPD", planned_value=100000.00)

    resp = client.patch(
        f"/api/v1/construction/packages/{pkg['id']}",
        json={"status": "tendering", "awarded_value": 95000.00},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "tendering"
    assert Decimal(data["awarded_value"]) == Decimal("95000.00")


def test_update_package_not_found_404(client: TestClient) -> None:
    resp = client.patch(
        "/api/v1/construction/packages/nonexistent-id",
        json={"status": "awarded"},
    )
    assert resp.status_code == 404


def test_delete_package(client: TestClient) -> None:
    project_id = _create_project(client, "PC-DEL-001")
    scope = _create_scope(client, project_id)
    pkg = _create_package(client, scope["id"], code="PKG-DEL")

    resp = client.delete(f"/api/v1/construction/packages/{pkg['id']}")
    assert resp.status_code == 204

    get_resp = client.get(f"/api/v1/construction/packages/{pkg['id']}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Assign contractor to package
# ---------------------------------------------------------------------------


def test_assign_contractor_to_package(client: TestClient) -> None:
    project_id = _create_project(client, "PC-ASS-001")
    scope = _create_scope(client, project_id)
    pkg = _create_package(client, scope["id"], code="PKG-ASS")
    contractor = _create_contractor(client, code="CTR-ASS")

    resp = client.post(
        f"/api/v1/construction/packages/{pkg['id']}/assign-contractor",
        json={"contractor_id": contractor["id"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["contractor_id"] == contractor["id"]


def test_assign_contractor_package_not_found_404(client: TestClient) -> None:
    contractor = _create_contractor(client, code="CTR-ASS-404")
    resp = client.post(
        "/api/v1/construction/packages/nonexistent-pkg/assign-contractor",
        json={"contractor_id": contractor["id"]},
    )
    assert resp.status_code == 404


def test_assign_contractor_not_found_404(client: TestClient) -> None:
    project_id = _create_project(client, "PC-ASS-002")
    scope = _create_scope(client, project_id)
    pkg = _create_package(client, scope["id"], code="PKG-ASS2")

    resp = client.post(
        f"/api/v1/construction/packages/{pkg['id']}/assign-contractor",
        json={"contractor_id": "nonexistent-contractor"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Link package to milestone
# ---------------------------------------------------------------------------


def test_link_package_to_milestone(client: TestClient) -> None:
    project_id = _create_project(client, "PC-LNK-001")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])
    pkg = _create_package(client, scope["id"], code="PKG-LNK")

    resp = client.post(
        f"/api/v1/construction/packages/{pkg['id']}/milestones/{milestone['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == pkg["id"]


def test_link_package_to_milestone_idempotent(client: TestClient) -> None:
    project_id = _create_project(client, "PC-LNK-002")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])
    pkg = _create_package(client, scope["id"], code="PKG-LNK2")

    client.post(f"/api/v1/construction/packages/{pkg['id']}/milestones/{milestone['id']}")
    resp = client.post(
        f"/api/v1/construction/packages/{pkg['id']}/milestones/{milestone['id']}"
    )
    assert resp.status_code == 200


def test_link_package_not_found_404(client: TestClient) -> None:
    project_id = _create_project(client, "PC-LNK-003")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    resp = client.post(
        f"/api/v1/construction/packages/nonexistent-pkg/milestones/{milestone['id']}"
    )
    assert resp.status_code == 404


def test_link_milestone_not_found_404(client: TestClient) -> None:
    project_id = _create_project(client, "PC-LNK-004")
    scope = _create_scope(client, project_id)
    pkg = _create_package(client, scope["id"], code="PKG-LNK4")

    resp = client.post(
        f"/api/v1/construction/packages/{pkg['id']}/milestones/nonexistent-milestone"
    )
    assert resp.status_code == 404


def test_link_milestone_wrong_scope_422(client: TestClient) -> None:
    project1_id = _create_project(client, "PC-LNK-005A")
    project2_id = _create_project(client, "PC-LNK-005B")
    scope1 = _create_scope(client, project1_id, name="Scope A")
    scope2 = _create_scope(client, project2_id, name="Scope B")

    milestone_in_scope2 = _create_milestone(client, scope2["id"])
    pkg_in_scope1 = _create_package(client, scope1["id"], code="PKG-LNK5")

    resp = client.post(
        f"/api/v1/construction/packages/{pkg_in_scope1['id']}/milestones/{milestone_in_scope2['id']}"
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Procurement overview
# ---------------------------------------------------------------------------


def test_procurement_overview_empty_scope(client: TestClient) -> None:
    project_id = _create_project(client, "PC-OVR-001")
    scope = _create_scope(client, project_id)

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/procurement-overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] == scope["id"]
    assert data["total_packages"] == 0
    assert Decimal(data["total_planned_value"]) == Decimal("0")
    assert Decimal(data["total_awarded_value"]) == Decimal("0")
    assert Decimal(data["uncommitted_value"]) == Decimal("0")
    assert data["packages_by_status"] == {}
    assert data["packages"] == []


def test_procurement_overview_with_packages(client: TestClient) -> None:
    project_id = _create_project(client, "PC-OVR-002")
    scope = _create_scope(client, project_id)

    _create_package(client, scope["id"], code="PKG-O1", planned_value=100000.0)
    _create_package(client, scope["id"], code="PKG-O2", planned_value=200000.0)

    # Award one package
    pkg2_resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/packages")
    packages = pkg2_resp.json()["items"]
    pkg_id = next(p["id"] for p in packages if p["package_code"] == "PKG-O2")
    client.patch(
        f"/api/v1/construction/packages/{pkg_id}",
        json={"status": "awarded", "awarded_value": 195000.0},
    )

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/procurement-overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_packages"] == 2
    assert Decimal(data["total_planned_value"]) == Decimal("300000.00")
    assert Decimal(data["total_awarded_value"]) == Decimal("195000.00")
    assert Decimal(data["uncommitted_value"]) == Decimal("105000.00")
    assert "draft" in data["packages_by_status"]
    assert "awarded" in data["packages_by_status"]


def test_procurement_overview_scope_not_found_404(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/scopes/nonexistent-scope/procurement-overview")
    assert resp.status_code == 404


def test_procurement_overview_status_counts(client: TestClient) -> None:
    project_id = _create_project(client, "PC-OVR-003")
    scope = _create_scope(client, project_id)

    _create_package(client, scope["id"], code="PKG-S1", planned_value=10000.0)
    _create_package(client, scope["id"], code="PKG-S2", planned_value=20000.0)
    _create_package(client, scope["id"], code="PKG-S3", planned_value=30000.0)

    # Get all packages and update statuses
    list_resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/packages")
    packages = list_resp.json()["items"]
    pkg_by_code = {p["package_code"]: p["id"] for p in packages}

    client.patch(
        f"/api/v1/construction/packages/{pkg_by_code['PKG-S2']}",
        json={"status": "tendering"},
    )
    client.patch(
        f"/api/v1/construction/packages/{pkg_by_code['PKG-S3']}",
        json={"status": "awarded"},
    )

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/procurement-overview")
    data = resp.json()
    assert data["packages_by_status"]["draft"] == 1
    assert data["packages_by_status"]["tendering"] == 1
    assert data["packages_by_status"]["awarded"] == 1


def test_full_procurement_workflow(client: TestClient) -> None:
    """End-to-end: create scope → contractor → package → assign → link milestone → overview."""
    project_id = _create_project(client, "PC-E2E-001")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])
    contractor = _create_contractor(client, code="CTR-E2E", name="E2E Builders")

    # Create package
    pkg = _create_package(
        client, scope["id"], code="PKG-E2E", planned_value=800000.0
    )

    # Assign contractor
    assign_resp = client.post(
        f"/api/v1/construction/packages/{pkg['id']}/assign-contractor",
        json={"contractor_id": contractor["id"]},
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["contractor_id"] == contractor["id"]

    # Link milestone
    link_resp = client.post(
        f"/api/v1/construction/packages/{pkg['id']}/milestones/{milestone['id']}"
    )
    assert link_resp.status_code == 200

    # Award package
    award_resp = client.patch(
        f"/api/v1/construction/packages/{pkg['id']}",
        json={"status": "awarded", "awarded_value": 780000.0},
    )
    assert award_resp.status_code == 200
    assert award_resp.json()["status"] == "awarded"

    # Check overview
    overview_resp = client.get(
        f"/api/v1/construction/scopes/{scope['id']}/procurement-overview"
    )
    assert overview_resp.status_code == 200
    overview = overview_resp.json()
    assert overview["total_packages"] == 1
    assert Decimal(overview["total_planned_value"]) == Decimal("800000.00")
    assert Decimal(overview["total_awarded_value"]) == Decimal("780000.00")
    assert Decimal(overview["uncommitted_value"]) == Decimal("20000.00")
    assert overview["packages_by_status"]["awarded"] == 1
