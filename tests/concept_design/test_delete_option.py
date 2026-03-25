"""
Tests for the Concept Design safe-deletion endpoint.

DELETE /api/v1/concept-options/{id}

Test cases:
  - allowed deletion: draft concept → 204 No Content
  - allowed deletion: active concept → 204 No Content
  - cascade deletion: concept with unit mix lines → both deleted
  - forbidden deletion: promoted concept → 409 Conflict
  - not found: unknown id → 404

PR-CONCEPT-057
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_project(client: TestClient, code: str = "PRJ-DEL01") -> str:
    resp = client.post(
        "/api/v1/projects", json={"name": f"Delete Test Project {code}", "code": code}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_option(
    client: TestClient,
    *,
    name: str = "Option To Delete",
    status: str = "draft",
    project_id: str | None = None,
    building_count: int | None = None,
    floor_count: int | None = None,
) -> dict:
    payload: dict = {"name": name, "status": status}
    if project_id is not None:
        payload["project_id"] = project_id
    if building_count is not None:
        payload["building_count"] = building_count
    if floor_count is not None:
        payload["floor_count"] = floor_count
    resp = client.post("/api/v1/concept-options", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _add_mix_line(client: TestClient, option_id: str) -> dict:
    resp = client.post(
        f"/api/v1/concept-options/{option_id}/unit-mix",
        json={"unit_type": "studio", "units_count": 5},
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Allowed deletion — draft concept
# ---------------------------------------------------------------------------

def test_delete_draft_concept_option(client: TestClient):
    """DELETE /concept-options/{id} — draft concept should return 204."""
    option = _create_option(client, name="Draft To Delete", status="draft")
    resp = client.delete(f"/api/v1/concept-options/{option['id']}")
    assert resp.status_code == 204
    assert resp.content == b""


def test_deleted_option_is_gone(client: TestClient):
    """After deletion the concept option should no longer be retrievable."""
    option = _create_option(client, name="Gone Option")
    client.delete(f"/api/v1/concept-options/{option['id']}")
    get_resp = client.get(f"/api/v1/concept-options/{option['id']}")
    assert get_resp.status_code == 404


def test_delete_active_concept_option(client: TestClient):
    """DELETE — active (non-promoted) concept should also return 204."""
    option = _create_option(client, name="Active To Delete", status="active")
    resp = client.delete(f"/api/v1/concept-options/{option['id']}")
    assert resp.status_code == 204


def test_delete_archived_concept_option(client: TestClient):
    """DELETE — archived (non-promoted) concept should return 204."""
    option = _create_option(client, name="Archived To Delete", status="archived")
    resp = client.delete(f"/api/v1/concept-options/{option['id']}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Cascade deletion — concept + unit mix lines
# ---------------------------------------------------------------------------

def test_delete_cascades_to_unit_mix_lines(client: TestClient):
    """DELETE — deleting a concept option should remove its unit mix lines."""
    option = _create_option(client, name="Cascade Option")
    _add_mix_line(client, option["id"])
    _add_mix_line(client, option["id"])

    # Verify mix lines exist via summary
    summary_before = client.get(f"/api/v1/concept-options/{option['id']}/summary")
    assert summary_before.status_code == 200
    assert len(summary_before.json()["mix_lines"]) == 2

    # Delete the option
    del_resp = client.delete(f"/api/v1/concept-options/{option['id']}")
    assert del_resp.status_code == 204

    # Option and mix lines should be gone
    get_resp = client.get(f"/api/v1/concept-options/{option['id']}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Forbidden deletion — promoted concept
# ---------------------------------------------------------------------------

def _promote_option(client: TestClient, option_id: str, project_id: str) -> dict:
    resp = client.post(
        f"/api/v1/concept-options/{option_id}/promote",
        json={"target_project_id": project_id},
    )
    assert resp.status_code == 201
    return resp.json()


def test_delete_promoted_concept_option_is_forbidden(client: TestClient):
    """DELETE — promoted concept should return 409 Conflict."""
    project_id = _create_project(client, "PRJ-DEL-P01")
    option = _create_option(
        client,
        name="To Be Promoted",
        status="active",
        project_id=project_id,
        building_count=1,
        floor_count=2,
    )
    _add_mix_line(client, option["id"])
    _promote_option(client, option["id"], project_id)

    resp = client.delete(f"/api/v1/concept-options/{option['id']}")
    assert resp.status_code == 409
    body = resp.json()
    assert body.get("code") == "CONFLICT"


def test_delete_promoted_option_leaves_option_intact(client: TestClient):
    """After a rejected deletion attempt the promoted option must still exist."""
    project_id = _create_project(client, "PRJ-DEL-P02")
    option = _create_option(
        client,
        name="Promoted Stays",
        status="active",
        project_id=project_id,
        building_count=1,
        floor_count=2,
    )
    _add_mix_line(client, option["id"])
    _promote_option(client, option["id"], project_id)

    client.delete(f"/api/v1/concept-options/{option['id']}")

    get_resp = client.get(f"/api/v1/concept-options/{option['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["is_promoted"] is True


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------

def test_delete_concept_option_not_found(client: TestClient):
    """DELETE with unknown id should return 404."""
    resp = client.delete("/api/v1/concept-options/no-such-id")
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("code") == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Idempotency / double-delete
# ---------------------------------------------------------------------------

def test_double_delete_returns_404(client: TestClient):
    """Deleting an already-deleted option should return 404."""
    option = _create_option(client, name="Delete Twice")
    client.delete(f"/api/v1/concept-options/{option['id']}")
    resp = client.delete(f"/api/v1/concept-options/{option['id']}")
    assert resp.status_code == 404
