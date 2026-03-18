"""
Tests for Construction Engineering Item lifecycle.

Validates:
  • engineering item CRUD lifecycle
  • safe partial updates (existing fields not overwritten by omitted values)
  • scope isolation (items do not bleed across scopes)
  • cascade delete from scope
"""

import pytest
from fastapi.testclient import TestClient


# ── Helper factories ─────────────────────────────────────────────────────────

def _create_project(client: TestClient, code: str = "EI-001") -> str:
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


def _create_item(
    client: TestClient,
    scope_id: str,
    title: str = "Concept Design Review",
    **kwargs,
) -> dict:
    payload = {"title": title, **kwargs}
    resp = client.post(
        f"/api/v1/construction/scopes/{scope_id}/engineering-items",
        json=payload,
    )
    assert resp.status_code == 201
    return resp.json()


# ── CRUD lifecycle ───────────────────────────────────────────────────────────

def test_create_engineering_item_lifecycle(client: TestClient):
    """Full create → read → update → delete lifecycle."""
    project_id = _create_project(client, "EI-010")
    scope = _create_scope(client, project_id)

    # Create
    item = _create_item(
        client,
        scope["id"],
        title="IFC Submission",
        consultant_name="Alpha Engineers",
        consultant_cost="12000.00",
    )
    assert item["scope_id"] == scope["id"]
    assert item["title"] == "IFC Submission"
    assert item["status"] == "pending"
    assert float(item["consultant_cost"]) == 12000.0

    # Read via list
    list_resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/engineering-items")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # Update status
    upd = client.patch(
        f"/api/v1/construction/engineering-items/{item['id']}",
        json={"status": "in_progress"},
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "in_progress"

    # Delete
    del_resp = client.delete(f"/api/v1/construction/engineering-items/{item['id']}")
    assert del_resp.status_code == 204

    # Confirm gone
    list_resp2 = client.get(f"/api/v1/construction/scopes/{scope['id']}/engineering-items")
    assert list_resp2.json()["total"] == 0


# ── Partial update safety (exclude_none) ────────────────────────────────────

def test_update_excludes_none(client: TestClient):
    """
    Partial PATCH must not overwrite existing field values with null.
    Sending only {status: 'completed'} must leave consultant_name and
    consultant_cost unchanged.
    """
    project_id = _create_project(client, "EI-020")
    scope = _create_scope(client, project_id)

    item = _create_item(
        client,
        scope["id"],
        title="Structural Coordination",
        consultant_name="XYZ Consulting",
        consultant_cost="20000.00",
        item_type="consultant",
    )
    assert item["consultant_name"] == "XYZ Consulting"
    assert float(item["consultant_cost"]) == 20000.0

    # Update only the status — omit consultant fields entirely
    upd = client.patch(
        f"/api/v1/construction/engineering-items/{item['id']}",
        json={"status": "completed"},
    )
    assert upd.status_code == 200
    data = upd.json()
    assert data["status"] == "completed"
    # Existing fields must be preserved
    assert data["consultant_name"] == "XYZ Consulting"
    assert float(data["consultant_cost"]) == 20000.0
    assert data["item_type"] == "consultant"


def test_update_preserves_title_when_omitted(client: TestClient):
    """PATCH that omits 'title' must not clear the existing title."""
    project_id = _create_project(client, "EI-021")
    scope = _create_scope(client, project_id)

    item = _create_item(client, scope["id"], title="Municipality Approval Package")

    upd = client.patch(
        f"/api/v1/construction/engineering-items/{item['id']}",
        json={"notes": "Submitted on time."},
    )
    assert upd.status_code == 200
    data = upd.json()
    assert data["title"] == "Municipality Approval Package"
    assert data["notes"] == "Submitted on time."


# ── Scope isolation ──────────────────────────────────────────────────────────

def test_engineering_items_isolated_per_scope(client: TestClient):
    """Items created in scope A must not appear in scope B."""
    p1 = _create_project(client, "EI-030")
    p2 = _create_project(client, "EI-031")
    s1 = _create_scope(client, p1, "Scope A")
    s2 = _create_scope(client, p2, "Scope B")

    _create_item(client, s1["id"], title="Item for Scope A")
    _create_item(client, s2["id"], title="Item for Scope B")

    resp_a = client.get(f"/api/v1/construction/scopes/{s1['id']}/engineering-items")
    assert resp_a.json()["total"] == 1
    assert resp_a.json()["items"][0]["scope_id"] == s1["id"]

    resp_b = client.get(f"/api/v1/construction/scopes/{s2['id']}/engineering-items")
    assert resp_b.json()["total"] == 1
    assert resp_b.json()["items"][0]["scope_id"] == s2["id"]


def test_list_engineering_items_unknown_scope_returns_404(client: TestClient):
    resp = client.get("/api/v1/construction/scopes/non-existent-scope/engineering-items")
    assert resp.status_code == 404


# ── Delete ───────────────────────────────────────────────────────────────────

def test_delete_engineering_item_removes_only_target(client: TestClient):
    """Deleting one item must not remove sibling items in the same scope."""
    project_id = _create_project(client, "EI-040")
    scope = _create_scope(client, project_id)

    item_a = _create_item(client, scope["id"], title="Item A")
    item_b = _create_item(client, scope["id"], title="Item B")

    client.delete(f"/api/v1/construction/engineering-items/{item_a['id']}")

    list_resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/engineering-items")
    assert list_resp.json()["total"] == 1
    assert list_resp.json()["items"][0]["id"] == item_b["id"]


def test_cascade_delete_scope_removes_engineering_items(client: TestClient):
    """Deleting a scope must cascade-delete its engineering items."""
    project_id = _create_project(client, "EI-041")
    scope = _create_scope(client, project_id)
    item = _create_item(client, scope["id"], title="Orphaned Item")

    del_scope = client.delete(f"/api/v1/construction/scopes/{scope['id']}")
    assert del_scope.status_code == 204

    # The item should no longer be accessible
    upd = client.patch(
        f"/api/v1/construction/engineering-items/{item['id']}",
        json={"status": "completed"},
    )
    assert upd.status_code == 404


# ── Validation ───────────────────────────────────────────────────────────────

def test_create_item_negative_cost_rejected(client: TestClient):
    project_id = _create_project(client, "EI-050")
    scope = _create_scope(client, project_id)
    resp = client.post(
        f"/api/v1/construction/scopes/{scope['id']}/engineering-items",
        json={"title": "Bad Cost", "consultant_cost": "-100.00"},
    )
    assert resp.status_code == 422


def test_update_item_negative_cost_rejected(client: TestClient):
    project_id = _create_project(client, "EI-051")
    scope = _create_scope(client, project_id)
    item = _create_item(client, scope["id"])
    resp = client.patch(
        f"/api/v1/construction/engineering-items/{item['id']}",
        json={"consultant_cost": "-50.00"},
    )
    assert resp.status_code == 422


def test_update_item_not_found_returns_404(client: TestClient):
    resp = client.patch(
        "/api/v1/construction/engineering-items/does-not-exist",
        json={"status": "completed"},
    )
    assert resp.status_code == 404


def test_delete_item_not_found_returns_404(client: TestClient):
    resp = client.delete("/api/v1/construction/engineering-items/does-not-exist")
    assert resp.status_code == 404
