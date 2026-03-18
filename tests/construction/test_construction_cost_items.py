"""
Tests for the Construction Cost Tracking module (PR-C4).

Validates the full vertical slice:
  - CRUD lifecycle for ConstructionCostItem
  - 404 on unknown scope / item
  - non-negative amount validation
  - at-least-one-nonzero amount validation
  - cost_category / cost_type enum validation
  - scope isolation (items from one scope don't bleed into another)
  - category filtering
  - derived variance correctness
  - cascade delete when parent scope is deleted
  - scope cost summary totals and per-category breakdown
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


# ── Helper factories ──────────────────────────────────────────────────────────


def _create_project(client: TestClient, code: str = "COST-P01") -> str:
    resp = client.post("/api/v1/projects", json={"name": f"Project {code}", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_scope(client: TestClient, project_id: str, name: str = "Cost Scope") -> dict:
    resp = client.post(
        "/api/v1/construction/scopes",
        json={"project_id": project_id, "name": name},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_cost_item(
    client: TestClient,
    scope_id: str,
    *,
    cost_category: str = "materials",
    cost_type: str = "budget",
    description: str = "Steel reinforcement",
    budget_amount: float = 10000.00,
    committed_amount: float = 0.00,
    actual_amount: float = 0.00,
    vendor_name: str | None = None,
    currency: str = "AED",
) -> dict:
    payload: dict = {
        "cost_category": cost_category,
        "cost_type": cost_type,
        "description": description,
        "budget_amount": budget_amount,
        "committed_amount": committed_amount,
        "actual_amount": actual_amount,
        "currency": currency,
    }
    if vendor_name is not None:
        payload["vendor_name"] = vendor_name
    resp = client.post(
        f"/api/v1/construction/scopes/{scope_id}/cost-items",
        json=payload,
    )
    assert resp.status_code == 201
    return resp.json()


# ── Create cost item ──────────────────────────────────────────────────────────


def test_create_cost_item_success(client: TestClient):
    project_id = _create_project(client, "COST-P01")
    scope = _create_scope(client, project_id)
    item = _create_cost_item(client, scope["id"], budget_amount=5000.00)

    assert item["scope_id"] == scope["id"]
    assert item["cost_category"] == "materials"
    assert item["cost_type"] == "budget"
    assert item["description"] == "Steel reinforcement"
    assert Decimal(str(item["budget_amount"])) == Decimal("5000.00")
    assert Decimal(str(item["committed_amount"])) == Decimal("0.00")
    assert Decimal(str(item["actual_amount"])) == Decimal("0.00")
    assert "id" in item
    assert "created_at" in item
    assert "updated_at" in item


def test_create_cost_item_with_all_amounts(client: TestClient):
    project_id = _create_project(client, "COST-P02")
    scope = _create_scope(client, project_id)
    item = _create_cost_item(
        client,
        scope["id"],
        budget_amount=20000.00,
        committed_amount=18000.00,
        actual_amount=15000.00,
        vendor_name="ABC Supplies",
        cost_category="labor",
        cost_type="actual",
    )
    assert item["vendor_name"] == "ABC Supplies"
    assert Decimal(str(item["budget_amount"])) == Decimal("20000.00")
    assert Decimal(str(item["committed_amount"])) == Decimal("18000.00")
    assert Decimal(str(item["actual_amount"])) == Decimal("15000.00")


def test_create_cost_item_returns_variance(client: TestClient):
    project_id = _create_project(client, "COST-P03")
    scope = _create_scope(client, project_id)
    item = _create_cost_item(
        client,
        scope["id"],
        budget_amount=10000.00,
        committed_amount=9000.00,
        actual_amount=11000.00,
    )
    # variance_to_budget = actual - budget = 11000 - 10000 = 1000
    assert Decimal(str(item["variance_to_budget"])) == Decimal("1000.00")
    # variance_to_commitment = actual - committed = 11000 - 9000 = 2000
    assert Decimal(str(item["variance_to_commitment"])) == Decimal("2000.00")


def test_create_cost_item_unknown_scope_returns_404(client: TestClient):
    resp = client.post(
        "/api/v1/construction/scopes/does-not-exist/cost-items",
        json={
            "cost_category": "materials",
            "cost_type": "budget",
            "description": "Test",
            "budget_amount": 1000.00,
        },
    )
    assert resp.status_code == 404


# ── Validation ────────────────────────────────────────────────────────────────


def test_create_cost_item_negative_budget_rejected(client: TestClient):
    project_id = _create_project(client, "COST-P04")
    scope = _create_scope(client, project_id)
    resp = client.post(
        f"/api/v1/construction/scopes/{scope['id']}/cost-items",
        json={
            "cost_category": "materials",
            "cost_type": "budget",
            "description": "Bad amount",
            "budget_amount": -500.00,
        },
    )
    assert resp.status_code == 422


def test_create_cost_item_negative_actual_rejected(client: TestClient):
    project_id = _create_project(client, "COST-P05")
    scope = _create_scope(client, project_id)
    resp = client.post(
        f"/api/v1/construction/scopes/{scope['id']}/cost-items",
        json={
            "cost_category": "labor",
            "cost_type": "actual",
            "description": "Negative actual",
            "budget_amount": 1000.00,
            "actual_amount": -100.00,
        },
    )
    assert resp.status_code == 422


def test_create_cost_item_all_zeros_rejected(client: TestClient):
    project_id = _create_project(client, "COST-P06")
    scope = _create_scope(client, project_id)
    resp = client.post(
        f"/api/v1/construction/scopes/{scope['id']}/cost-items",
        json={
            "cost_category": "materials",
            "cost_type": "budget",
            "description": "All zero",
            "budget_amount": 0,
            "committed_amount": 0,
            "actual_amount": 0,
        },
    )
    assert resp.status_code == 422


def test_create_cost_item_invalid_category_rejected(client: TestClient):
    project_id = _create_project(client, "COST-P07")
    scope = _create_scope(client, project_id)
    resp = client.post(
        f"/api/v1/construction/scopes/{scope['id']}/cost-items",
        json={
            "cost_category": "invalid_category",
            "cost_type": "budget",
            "description": "Bad category",
            "budget_amount": 1000.00,
        },
    )
    assert resp.status_code == 422


def test_create_cost_item_invalid_type_rejected(client: TestClient):
    project_id = _create_project(client, "COST-P08")
    scope = _create_scope(client, project_id)
    resp = client.post(
        f"/api/v1/construction/scopes/{scope['id']}/cost-items",
        json={
            "cost_category": "materials",
            "cost_type": "wrong_type",
            "description": "Bad type",
            "budget_amount": 1000.00,
        },
    )
    assert resp.status_code == 422


def test_create_cost_item_missing_description_rejected(client: TestClient):
    project_id = _create_project(client, "COST-P09")
    scope = _create_scope(client, project_id)
    resp = client.post(
        f"/api/v1/construction/scopes/{scope['id']}/cost-items",
        json={
            "cost_category": "materials",
            "cost_type": "budget",
            "budget_amount": 1000.00,
        },
    )
    assert resp.status_code == 422


# ── List cost items ───────────────────────────────────────────────────────────


def test_list_cost_items(client: TestClient):
    project_id = _create_project(client, "COST-P10")
    scope = _create_scope(client, project_id)
    _create_cost_item(client, scope["id"], description="Item 1", budget_amount=1000.00)
    _create_cost_item(
        client, scope["id"], description="Item 2", cost_category="labor", budget_amount=2000.00
    )

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/cost-items")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_cost_items_scope_isolation(client: TestClient):
    p1 = _create_project(client, "COST-P11")
    p2 = _create_project(client, "COST-P12")
    s1 = _create_scope(client, p1, "Scope A")
    s2 = _create_scope(client, p2, "Scope B")
    _create_cost_item(client, s1["id"], description="S1 Item", budget_amount=1000.00)
    _create_cost_item(client, s2["id"], description="S2 Item", budget_amount=2000.00)

    resp = client.get(f"/api/v1/construction/scopes/{s1['id']}/cost-items")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["description"] == "S1 Item"


def test_list_cost_items_category_filter(client: TestClient):
    project_id = _create_project(client, "COST-P13")
    scope = _create_scope(client, project_id)
    _create_cost_item(client, scope["id"], cost_category="materials", description="M1", budget_amount=1000.00)
    _create_cost_item(client, scope["id"], cost_category="labor", description="L1", budget_amount=2000.00)
    _create_cost_item(client, scope["id"], cost_category="materials", description="M2", budget_amount=3000.00)

    resp = client.get(
        f"/api/v1/construction/scopes/{scope['id']}/cost-items?category=materials"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert item["cost_category"] == "materials"


def test_list_cost_items_unknown_scope_returns_404(client: TestClient):
    resp = client.get("/api/v1/construction/scopes/does-not-exist/cost-items")
    assert resp.status_code == 404


# ── Get cost item ─────────────────────────────────────────────────────────────


def test_get_cost_item(client: TestClient):
    project_id = _create_project(client, "COST-P14")
    scope = _create_scope(client, project_id)
    created = _create_cost_item(client, scope["id"], budget_amount=7500.00)

    resp = client.get(f"/api/v1/construction/cost-items/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_cost_item_not_found(client: TestClient):
    resp = client.get("/api/v1/construction/cost-items/does-not-exist")
    assert resp.status_code == 404


# ── Update cost item ──────────────────────────────────────────────────────────


def test_update_cost_item(client: TestClient):
    project_id = _create_project(client, "COST-P15")
    scope = _create_scope(client, project_id)
    created = _create_cost_item(
        client, scope["id"], budget_amount=10000.00, actual_amount=0.00
    )

    resp = client.patch(
        f"/api/v1/construction/cost-items/{created['id']}",
        json={"actual_amount": 8500.00, "vendor_name": "Delta Build"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert Decimal(str(updated["actual_amount"])) == Decimal("8500.00")
    assert updated["vendor_name"] == "Delta Build"
    # variance_to_budget = 8500 - 10000 = -1500
    assert Decimal(str(updated["variance_to_budget"])) == Decimal("-1500.00")


def test_update_cost_item_negative_amount_rejected(client: TestClient):
    project_id = _create_project(client, "COST-P16")
    scope = _create_scope(client, project_id)
    created = _create_cost_item(client, scope["id"], budget_amount=5000.00)

    resp = client.patch(
        f"/api/v1/construction/cost-items/{created['id']}",
        json={"budget_amount": -100.00},
    )
    assert resp.status_code == 422


def test_update_cost_item_not_found(client: TestClient):
    resp = client.patch(
        "/api/v1/construction/cost-items/does-not-exist",
        json={"actual_amount": 500.00},
    )
    assert resp.status_code == 404


# ── Delete cost item ──────────────────────────────────────────────────────────


def test_delete_cost_item(client: TestClient):
    project_id = _create_project(client, "COST-P17")
    scope = _create_scope(client, project_id)
    created = _create_cost_item(client, scope["id"], budget_amount=3000.00)

    resp = client.delete(f"/api/v1/construction/cost-items/{created['id']}")
    assert resp.status_code == 204

    get_resp = client.get(f"/api/v1/construction/cost-items/{created['id']}")
    assert get_resp.status_code == 404


def test_delete_cost_item_not_found(client: TestClient):
    resp = client.delete("/api/v1/construction/cost-items/does-not-exist")
    assert resp.status_code == 404


# ── Cascade delete ────────────────────────────────────────────────────────────


def test_cascade_delete_scope_removes_cost_items(client: TestClient):
    project_id = _create_project(client, "COST-P18")
    scope = _create_scope(client, project_id)
    item = _create_cost_item(client, scope["id"], budget_amount=5000.00)

    # Delete the scope
    del_resp = client.delete(f"/api/v1/construction/scopes/{scope['id']}")
    assert del_resp.status_code == 204

    # Cost item should now be gone too
    get_resp = client.get(f"/api/v1/construction/cost-items/{item['id']}")
    assert get_resp.status_code == 404


# ── Cost summary ──────────────────────────────────────────────────────────────


def test_cost_summary_empty_scope(client: TestClient):
    project_id = _create_project(client, "COST-P19")
    scope = _create_scope(client, project_id)

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/cost-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] == scope["id"]
    assert Decimal(str(data["total_budget"])) == Decimal("0.00")
    assert Decimal(str(data["total_committed"])) == Decimal("0.00")
    assert Decimal(str(data["total_actual"])) == Decimal("0.00")
    assert Decimal(str(data["total_variance_to_budget"])) == Decimal("0.00")
    assert Decimal(str(data["total_variance_to_commitment"])) == Decimal("0.00")
    assert data["by_category"] == {}


def test_cost_summary_totals(client: TestClient):
    project_id = _create_project(client, "COST-P20")
    scope = _create_scope(client, project_id)

    # materials: budget=10000, committed=9000, actual=8500
    _create_cost_item(
        client,
        scope["id"],
        cost_category="materials",
        cost_type="budget",
        description="Steel",
        budget_amount=10000.00,
        committed_amount=9000.00,
        actual_amount=8500.00,
    )
    # labor: budget=5000, committed=4800, actual=5200
    _create_cost_item(
        client,
        scope["id"],
        cost_category="labor",
        cost_type="actual",
        description="Site workers",
        budget_amount=5000.00,
        committed_amount=4800.00,
        actual_amount=5200.00,
    )

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/cost-summary")
    assert resp.status_code == 200
    data = resp.json()

    assert Decimal(str(data["total_budget"])) == Decimal("15000.00")
    assert Decimal(str(data["total_committed"])) == Decimal("13800.00")
    assert Decimal(str(data["total_actual"])) == Decimal("13700.00")
    # variance_to_budget = 13700 - 15000 = -1300
    assert Decimal(str(data["total_variance_to_budget"])) == Decimal("-1300.00")
    # variance_to_commitment = 13700 - 13800 = -100
    assert Decimal(str(data["total_variance_to_commitment"])) == Decimal("-100.00")


def test_cost_summary_by_category(client: TestClient):
    project_id = _create_project(client, "COST-P21")
    scope = _create_scope(client, project_id)

    _create_cost_item(
        client,
        scope["id"],
        cost_category="equipment",
        cost_type="budget",
        description="Crane rental",
        budget_amount=20000.00,
        committed_amount=18000.00,
        actual_amount=19000.00,
    )
    _create_cost_item(
        client,
        scope["id"],
        cost_category="permits",
        cost_type="budget",
        description="Building permits",
        budget_amount=3000.00,
        committed_amount=3000.00,
        actual_amount=3000.00,
    )

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/cost-summary")
    assert resp.status_code == 200
    data = resp.json()

    assert "equipment" in data["by_category"]
    assert "permits" in data["by_category"]

    eq = data["by_category"]["equipment"]
    assert eq["budget"] == pytest.approx(20000.00)
    assert eq["committed"] == pytest.approx(18000.00)
    assert eq["actual"] == pytest.approx(19000.00)
    assert eq["variance_to_budget"] == pytest.approx(-1000.00)
    assert eq["variance_to_commitment"] == pytest.approx(1000.00)

    pm = data["by_category"]["permits"]
    assert pm["budget"] == pytest.approx(3000.00)
    assert pm["variance_to_budget"] == pytest.approx(0.00)


def test_cost_summary_unknown_scope_returns_404(client: TestClient):
    resp = client.get("/api/v1/construction/scopes/does-not-exist/cost-summary")
    assert resp.status_code == 404


def test_cost_summary_scope_isolation(client: TestClient):
    """Summary for scope A must not include items from scope B."""
    p1 = _create_project(client, "COST-P22")
    p2 = _create_project(client, "COST-P23")
    s1 = _create_scope(client, p1, "Scope A")
    s2 = _create_scope(client, p2, "Scope B")

    _create_cost_item(client, s1["id"], budget_amount=10000.00, description="S1 item")
    _create_cost_item(client, s2["id"], budget_amount=50000.00, description="S2 item")

    resp = client.get(f"/api/v1/construction/scopes/{s1['id']}/cost-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(str(data["total_budget"])) == Decimal("10000.00")


# ── Multiple category values ──────────────────────────────────────────────────


def test_all_valid_cost_categories_accepted(client: TestClient):
    project_id = _create_project(client, "COST-P24")
    scope = _create_scope(client, project_id)
    categories = [
        "materials",
        "labor",
        "equipment",
        "subcontractor",
        "consultant",
        "permits",
        "utilities",
        "site_overheads",
        "other",
    ]
    for i, cat in enumerate(categories):
        resp = client.post(
            f"/api/v1/construction/scopes/{scope['id']}/cost-items",
            json={
                "cost_category": cat,
                "cost_type": "budget",
                "description": f"{cat} item",
                "budget_amount": (i + 1) * 1000.0,
            },
        )
        assert resp.status_code == 201, f"Failed for category: {cat}"


def test_all_valid_cost_types_accepted(client: TestClient):
    project_id = _create_project(client, "COST-P25")
    scope = _create_scope(client, project_id)
    for cost_type, amount_field in [
        ("budget", "budget_amount"),
        ("commitment", "committed_amount"),
        ("actual", "actual_amount"),
    ]:
        resp = client.post(
            f"/api/v1/construction/scopes/{scope['id']}/cost-items",
            json={
                "cost_category": "other",
                "cost_type": cost_type,
                "description": f"{cost_type} line",
                amount_field: 5000.0,
            },
        )
        assert resp.status_code == 201, f"Failed for cost_type: {cost_type}"
