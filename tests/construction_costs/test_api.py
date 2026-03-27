"""
Tests for the Construction Cost Records API (PR-V6-09).

Validates:
  - 404 on unknown project / record
  - create record with correct field defaults
  - response contract shape
  - list records by project (with filters)
  - update record (partial)
  - archive record
  - project isolation (records for project A invisible to project B queries)
  - category / source / stage validation
  - summary endpoint totals
  - no mutation of unrelated project data
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str, name: str = "Test Project") -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_record(
    client: TestClient,
    project_id: str,
    *,
    title: str = "Site Clearance",
    cost_category: str = "hard_cost",
    cost_source: str = "estimate",
    cost_stage: str = "construction",
    amount: float = 500000.00,
    currency: str = "AED",
    effective_date: str | None = None,
    reference_number: str | None = None,
    notes: str | None = None,
) -> dict:
    payload: dict = {
        "title": title,
        "cost_category": cost_category,
        "cost_source": cost_source,
        "cost_stage": cost_stage,
        "amount": amount,
        "currency": currency,
    }
    if effective_date:
        payload["effective_date"] = effective_date
    if reference_number:
        payload["reference_number"] = reference_number
    if notes:
        payload["notes"] = notes

    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json=payload,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# 404 behaviour
# ---------------------------------------------------------------------------


def test_list_records_unknown_project_returns_404(client: TestClient) -> None:
    resp = client.get("/api/v1/projects/nonexistent/construction-cost-records")
    assert resp.status_code == 404


def test_get_record_unknown_returns_404(client: TestClient) -> None:
    resp = client.get("/api/v1/construction-cost-records/nonexistent")
    assert resp.status_code == 404


def test_create_record_unknown_project_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/projects/nonexistent/construction-cost-records",
        json={"title": "Test", "amount": 1000},
    )
    assert resp.status_code == 404


def test_update_record_unknown_returns_404(client: TestClient) -> None:
    resp = client.patch(
        "/api/v1/construction-cost-records/nonexistent",
        json={"title": "Updated"},
    )
    assert resp.status_code == 404


def test_archive_record_unknown_returns_404(client: TestClient) -> None:
    resp = client.post("/api/v1/construction-cost-records/nonexistent/archive")
    assert resp.status_code == 404


def test_summary_unknown_project_returns_404(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/projects/nonexistent/construction-cost-records/summary"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_record_minimal(client: TestClient) -> None:
    project_id = _create_project(client, "CC001")
    record = _create_record(client, project_id)

    assert record["project_id"] == project_id
    assert record["title"] == "Site Clearance"
    assert record["cost_category"] == "hard_cost"
    assert record["cost_source"] == "estimate"
    assert record["cost_stage"] == "construction"
    assert float(record["amount"]) == 500000.00
    assert record["currency"] == "AED"
    assert record["is_active"] is True
    assert record["effective_date"] is None
    assert record["reference_number"] is None
    assert "id" in record
    assert "created_at" in record
    assert "updated_at" in record


def test_create_record_all_fields(client: TestClient) -> None:
    project_id = _create_project(client, "CC002")
    record = _create_record(
        client,
        project_id,
        title="Structural Steel",
        cost_category="hard_cost",
        cost_source="contract",
        cost_stage="tender",
        amount=1_200_000.50,
        currency="AED",
        effective_date="2026-06-01",
        reference_number="REF-001",
        notes="Main structural steel package",
    )

    assert record["effective_date"] == "2026-06-01"
    assert record["reference_number"] == "REF-001"
    assert record["notes"] == "Main structural steel package"


def test_create_record_defaults(client: TestClient) -> None:
    project_id = _create_project(client, "CC003")
    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json={"title": "Contingency Reserve", "amount": 250000},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["cost_category"] == "hard_cost"
    assert data["cost_source"] == "estimate"
    assert data["cost_stage"] == "construction"
    assert data["currency"] == "AED"
    assert data["is_active"] is True


# ---------------------------------------------------------------------------
# Contract shape
# ---------------------------------------------------------------------------


def test_create_record_response_shape(client: TestClient) -> None:
    project_id = _create_project(client, "CC004")
    record = _create_record(client, project_id)

    required_keys = {
        "id",
        "project_id",
        "title",
        "cost_category",
        "cost_source",
        "cost_stage",
        "amount",
        "currency",
        "effective_date",
        "reference_number",
        "notes",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert required_keys.issubset(set(record.keys()))


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_records_empty(client: TestClient) -> None:
    project_id = _create_project(client, "CC005")
    resp = client.get(
        f"/api/v1/projects/{project_id}/construction-cost-records"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_records_returns_project_records(client: TestClient) -> None:
    project_id = _create_project(client, "CC006")
    _create_record(client, project_id, title="R1", amount=100)
    _create_record(client, project_id, title="R2", amount=200)

    resp = client.get(
        f"/api/v1/projects/{project_id}/construction-cost-records"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    titles = {r["title"] for r in data["items"]}
    assert titles == {"R1", "R2"}


def test_list_records_filter_by_is_active(client: TestClient) -> None:
    project_id = _create_project(client, "CC007")
    record = _create_record(client, project_id, title="Active")
    _create_record(client, project_id, title="Will Archive")

    # archive second record
    records_resp = client.get(
        f"/api/v1/projects/{project_id}/construction-cost-records"
    )
    all_records = records_resp.json()["items"]
    to_archive = next(r for r in all_records if r["title"] == "Will Archive")
    client.post(f"/api/v1/construction-cost-records/{to_archive['id']}/archive")

    active_resp = client.get(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        params={"is_active": "true"},
    )
    assert active_resp.status_code == 200
    active_data = active_resp.json()
    assert active_data["total"] == 1
    assert active_data["items"][0]["title"] == "Active"


def test_list_records_filter_by_category(client: TestClient) -> None:
    project_id = _create_project(client, "CC008")
    _create_record(client, project_id, title="Hard", cost_category="hard_cost")
    _create_record(client, project_id, title="Soft", cost_category="soft_cost")

    resp = client.get(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        params={"cost_category": "hard_cost"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Hard"


def test_list_records_filter_by_stage(client: TestClient) -> None:
    project_id = _create_project(client, "CC009")
    _create_record(client, project_id, title="Tender Stage", cost_stage="tender")
    _create_record(
        client, project_id, title="Construction Stage", cost_stage="construction"
    )

    resp = client.get(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        params={"cost_stage": "tender"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Tender Stage"


# ---------------------------------------------------------------------------
# Get by ID
# ---------------------------------------------------------------------------


def test_get_record_by_id(client: TestClient) -> None:
    project_id = _create_project(client, "CC010")
    created = _create_record(client, project_id, title="Specific Record")

    resp = client.get(f"/api/v1/construction-cost-records/{created['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["title"] == "Specific Record"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_record_title(client: TestClient) -> None:
    project_id = _create_project(client, "CC011")
    record = _create_record(client, project_id, title="Old Title")

    resp = client.patch(
        f"/api/v1/construction-cost-records/{record['id']}",
        json={"title": "New Title"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


def test_update_record_amount(client: TestClient) -> None:
    project_id = _create_project(client, "CC012")
    record = _create_record(client, project_id, amount=100.00)

    resp = client.patch(
        f"/api/v1/construction-cost-records/{record['id']}",
        json={"amount": 250000.00},
    )
    assert resp.status_code == 200
    assert float(resp.json()["amount"]) == 250000.00


def test_update_record_preserves_other_fields(client: TestClient) -> None:
    project_id = _create_project(client, "CC013")
    record = _create_record(
        client,
        project_id,
        title="Keep Me",
        cost_category="soft_cost",
        amount=999.00,
    )

    resp = client.patch(
        f"/api/v1/construction-cost-records/{record['id']}",
        json={"notes": "Updated note"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Keep Me"
    assert data["cost_category"] == "soft_cost"
    assert float(data["amount"]) == 999.00
    assert data["notes"] == "Updated note"


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------


def test_archive_record(client: TestClient) -> None:
    project_id = _create_project(client, "CC014")
    record = _create_record(client, project_id)

    resp = client.post(f"/api/v1/construction-cost-records/{record['id']}/archive")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_archived_record_appears_in_all_list(client: TestClient) -> None:
    project_id = _create_project(client, "CC015")
    record = _create_record(client, project_id)
    client.post(f"/api/v1/construction-cost-records/{record['id']}/archive")

    all_resp = client.get(
        f"/api/v1/projects/{project_id}/construction-cost-records"
    )
    assert all_resp.status_code == 200
    assert all_resp.json()["total"] == 1

    active_resp = client.get(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        params={"is_active": "true"},
    )
    assert active_resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# Project isolation
# ---------------------------------------------------------------------------


def test_records_are_isolated_by_project(client: TestClient) -> None:
    project_a = _create_project(client, "ISO-A")
    project_b = _create_project(client, "ISO-B")

    _create_record(client, project_a, title="Project A Cost", amount=100)
    _create_record(client, project_b, title="Project B Cost", amount=200)

    resp_a = client.get(
        f"/api/v1/projects/{project_a}/construction-cost-records"
    )
    resp_b = client.get(
        f"/api/v1/projects/{project_b}/construction-cost-records"
    )

    assert resp_a.json()["total"] == 1
    assert resp_a.json()["items"][0]["title"] == "Project A Cost"

    assert resp_b.json()["total"] == 1
    assert resp_b.json()["items"][0]["title"] == "Project B Cost"


def test_update_record_does_not_affect_other_project(client: TestClient) -> None:
    project_a = _create_project(client, "UPDA")
    project_b = _create_project(client, "UPDB")

    record_a = _create_record(client, project_a, title="A Record", amount=500)
    _create_record(client, project_b, title="B Record", amount=500)

    client.patch(
        f"/api/v1/construction-cost-records/{record_a['id']}",
        json={"amount": 9999.00},
    )

    resp_b = client.get(
        f"/api/v1/projects/{project_b}/construction-cost-records"
    )
    assert float(resp_b.json()["items"][0]["amount"]) == 500.00


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_invalid_cost_category_returns_422(client: TestClient) -> None:
    project_id = _create_project(client, "VAL001")
    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json={
            "title": "Bad",
            "amount": 100,
            "cost_category": "not_a_real_category",
        },
    )
    assert resp.status_code == 422


def test_invalid_cost_source_returns_422(client: TestClient) -> None:
    project_id = _create_project(client, "VAL002")
    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json={
            "title": "Bad",
            "amount": 100,
            "cost_source": "not_a_real_source",
        },
    )
    assert resp.status_code == 422


def test_invalid_cost_stage_returns_422(client: TestClient) -> None:
    project_id = _create_project(client, "VAL003")
    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json={
            "title": "Bad",
            "amount": 100,
            "cost_stage": "not_a_real_stage",
        },
    )
    assert resp.status_code == 422


def test_missing_title_returns_422(client: TestClient) -> None:
    project_id = _create_project(client, "VAL004")
    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json={"amount": 100},
    )
    assert resp.status_code == 422


def test_missing_amount_returns_422(client: TestClient) -> None:
    project_id = _create_project(client, "VAL005")
    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json={"title": "No Amount"},
    )
    assert resp.status_code == 422


def test_all_valid_categories_accepted(client: TestClient) -> None:
    project_id = _create_project(client, "CATALL")
    categories = [
        "hard_cost",
        "soft_cost",
        "preliminaries",
        "infrastructure",
        "contingency",
        "consultant_fee",
        "tender_adjustment",
        "variation",
    ]
    for cat in categories:
        resp = client.post(
            f"/api/v1/projects/{project_id}/construction-cost-records",
            json={"title": f"Test {cat}", "amount": 1000, "cost_category": cat},
        )
        assert resp.status_code == 201, f"Expected 201 for category '{cat}': {resp.text}"


def test_all_valid_sources_accepted(client: TestClient) -> None:
    project_id = _create_project(client, "SRCALL")
    sources = ["estimate", "tender", "contract", "variation", "actual"]
    for src in sources:
        resp = client.post(
            f"/api/v1/projects/{project_id}/construction-cost-records",
            json={"title": f"Test {src}", "amount": 1000, "cost_source": src},
        )
        assert resp.status_code == 201, f"Expected 201 for source '{src}': {resp.text}"


def test_all_valid_stages_accepted(client: TestClient) -> None:
    project_id = _create_project(client, "STGALL")
    stages = [
        "pre_design",
        "design",
        "tender",
        "construction",
        "completion",
        "post_completion",
    ]
    for stage in stages:
        resp = client.post(
            f"/api/v1/projects/{project_id}/construction-cost-records",
            json={"title": f"Test {stage}", "amount": 1000, "cost_stage": stage},
        )
        assert resp.status_code == 201, f"Expected 201 for stage '{stage}': {resp.text}"


# ---------------------------------------------------------------------------
# Summary endpoint
# ---------------------------------------------------------------------------


def test_summary_empty_project(client: TestClient) -> None:
    project_id = _create_project(client, "SUM001")
    resp = client.get(
        f"/api/v1/projects/{project_id}/construction-cost-records/summary"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["active_record_count"] == 0
    assert data["grand_total"] == "0.00"
    assert data["by_category"] == {}
    assert data["by_stage"] == {}


def test_summary_aggregates_correctly(client: TestClient) -> None:
    project_id = _create_project(client, "SUM002")
    _create_record(
        client, project_id, title="R1", cost_category="hard_cost", amount=100_000
    )
    _create_record(
        client, project_id, title="R2", cost_category="soft_cost", amount=50_000
    )
    _create_record(
        client,
        project_id,
        title="R3",
        cost_category="hard_cost",
        cost_stage="tender",
        amount=200_000,
    )

    resp = client.get(
        f"/api/v1/projects/{project_id}/construction-cost-records/summary"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_record_count"] == 3
    assert float(data["grand_total"]) == 350_000.00
    assert float(data["by_category"]["hard_cost"]) == 300_000.00
    assert float(data["by_category"]["soft_cost"]) == 50_000.00


def test_summary_excludes_archived_records(client: TestClient) -> None:
    project_id = _create_project(client, "SUM003")
    record = _create_record(
        client, project_id, title="Active Cost", amount=100_000
    )
    archived = _create_record(
        client, project_id, title="Archived Cost", amount=50_000
    )
    client.post(
        f"/api/v1/construction-cost-records/{archived['id']}/archive"
    )

    resp = client.get(
        f"/api/v1/projects/{project_id}/construction-cost-records/summary"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_record_count"] == 1
    assert float(data["grand_total"]) == 100_000.00


# ---------------------------------------------------------------------------
# Negative amount (variation / adjustment)
# ---------------------------------------------------------------------------


def test_negative_amount_allowed(client: TestClient) -> None:
    project_id = _create_project(client, "NEG001")
    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json={
            "title": "Credit Variation",
            "amount": -25000,
            "cost_category": "variation",
            "cost_source": "variation",
        },
    )
    assert resp.status_code == 201
    assert float(resp.json()["amount"]) == -25000.00


# ---------------------------------------------------------------------------
# Unauthenticated access
# ---------------------------------------------------------------------------


def test_list_records_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get(
        "/api/v1/projects/some-project/construction-cost-records"
    )
    assert resp.status_code == 401


def test_create_record_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.post(
        "/api/v1/projects/some-project/construction-cost-records",
        json={"title": "Bad", "amount": 100},
    )
    assert resp.status_code == 401
