"""
Tests for project attribute definitions and options (PR-REDS-032).

Validates:
  - create attribute definition
  - reject duplicate definition key for same project
  - add options to definition
  - reject duplicate option values/labels within one definition
  - list definitions with nested options
  - update/deactivate definition and option
  - 404 on invalid project/definition/option IDs
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str = "PROJ-001") -> str:
    """Create a project and return its id."""
    resp = client.post("/api/v1/projects", json={"name": "Test Project", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_definition(
    client: TestClient,
    project_id: str,
    key: str = "view_type",
    label: str = "View Type",
) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/attribute-definitions",
        json={"key": key, "label": label},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_option(
    client: TestClient,
    project_id: str,
    definition_id: str,
    value: str = "sea_view",
    label: str = "Sea View",
) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/attribute-definitions/{definition_id}/options",
        json={"value": value, "label": label},
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Definition creation
# ---------------------------------------------------------------------------


def test_create_attribute_definition(client: TestClient):
    """POST /projects/{id}/attribute-definitions creates a definition."""
    project_id = _create_project(client)
    data = _create_definition(client, project_id)

    assert data["key"] == "view_type"
    assert data["label"] == "View Type"
    assert data["input_type"] == "select"
    assert data["is_active"] is True
    assert data["project_id"] == project_id
    assert "id" in data
    assert data["options"] == []


def test_create_definition_invalid_key_rejected(client: TestClient):
    """POST /projects/{id}/attribute-definitions rejects unsupported keys (422)."""
    project_id = _create_project(client)
    resp = client.post(
        f"/api/v1/projects/{project_id}/attribute-definitions",
        json={"key": "unsupported_key", "label": "Bad Key"},
    )
    assert resp.status_code == 422


def test_create_definition_duplicate_key_rejected(client: TestClient):
    """A second definition with the same key for the same project returns 409."""
    project_id = _create_project(client)
    _create_definition(client, project_id)

    resp = client.post(
        f"/api/v1/projects/{project_id}/attribute-definitions",
        json={"key": "view_type", "label": "View Type Duplicate"},
    )
    assert resp.status_code == 409


def test_create_definition_same_key_different_projects_allowed(client: TestClient):
    """The same definition key can exist on different projects."""
    p1 = _create_project(client, "PROJ-A01")
    p2 = _create_project(client, "PROJ-B01")
    _create_definition(client, p1)
    resp = client.post(
        f"/api/v1/projects/{p2}/attribute-definitions",
        json={"key": "view_type", "label": "View Type"},
    )
    assert resp.status_code == 201


def test_create_definition_project_not_found(client: TestClient):
    """Creating a definition for a non-existent project returns 404."""
    resp = client.post(
        "/api/v1/projects/nonexistent-id/attribute-definitions",
        json={"key": "view_type", "label": "View Type"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List definitions
# ---------------------------------------------------------------------------


def test_list_attribute_definitions_empty(client: TestClient):
    """GET /projects/{id}/attribute-definitions returns empty list initially."""
    project_id = _create_project(client)
    resp = client.get(f"/api/v1/projects/{project_id}/attribute-definitions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_attribute_definitions_with_options(client: TestClient):
    """Definitions returned include their nested options."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)
    _create_option(client, project_id, defn["id"], "sea_view", "Sea View")
    _create_option(client, project_id, defn["id"], "park_view", "Park View")

    resp = client.get(f"/api/v1/projects/{project_id}/attribute-definitions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    options = body["items"][0]["options"]
    assert len(options) == 2


def test_list_definitions_project_not_found(client: TestClient):
    """Listing definitions for a non-existent project returns 404."""
    resp = client.get("/api/v1/projects/nonexistent-id/attribute-definitions")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update definition
# ---------------------------------------------------------------------------


def test_update_definition_label(client: TestClient):
    """PATCH /projects/{id}/attribute-definitions/{def_id} updates label."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)

    resp = client.patch(
        f"/api/v1/projects/{project_id}/attribute-definitions/{defn['id']}",
        json={"label": "Updated View Type Label"},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Updated View Type Label"


def test_deactivate_definition(client: TestClient):
    """PATCH with is_active=false deactivates a definition."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)

    resp = client.patch(
        f"/api/v1/projects/{project_id}/attribute-definitions/{defn['id']}",
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_update_definition_not_found(client: TestClient):
    """Updating a non-existent definition returns 404."""
    project_id = _create_project(client)
    resp = client.patch(
        f"/api/v1/projects/{project_id}/attribute-definitions/nonexistent-def",
        json={"label": "X"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Option creation
# ---------------------------------------------------------------------------


def test_create_option(client: TestClient):
    """POST /projects/{id}/attribute-definitions/{def_id}/options creates an option."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)
    option = _create_option(client, project_id, defn["id"])

    assert option["value"] == "sea_view"
    assert option["label"] == "Sea View"
    assert option["sort_order"] == 0
    assert option["is_active"] is True
    assert option["definition_id"] == defn["id"]


def test_create_option_duplicate_value_rejected(client: TestClient):
    """Duplicate option value within same definition returns 409."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)
    _create_option(client, project_id, defn["id"], "sea_view", "Sea View")

    resp = client.post(
        f"/api/v1/projects/{project_id}/attribute-definitions/{defn['id']}/options",
        json={"value": "sea_view", "label": "Sea View Different Label"},
    )
    assert resp.status_code == 409


def test_create_option_duplicate_label_rejected(client: TestClient):
    """Duplicate option label within same definition returns 409."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)
    _create_option(client, project_id, defn["id"], "sea_view", "Sea View")

    resp = client.post(
        f"/api/v1/projects/{project_id}/attribute-definitions/{defn['id']}/options",
        json={"value": "sea_view_alt", "label": "Sea View"},
    )
    assert resp.status_code == 409


def test_create_option_definition_not_found(client: TestClient):
    """Creating an option for a non-existent definition returns 404."""
    project_id = _create_project(client)
    resp = client.post(
        f"/api/v1/projects/{project_id}/attribute-definitions/nonexistent-def/options",
        json={"value": "sea_view", "label": "Sea View"},
    )
    assert resp.status_code == 404


def test_create_option_sort_order(client: TestClient):
    """Options respect the sort_order field."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)

    resp = client.post(
        f"/api/v1/projects/{project_id}/attribute-definitions/{defn['id']}/options",
        json={"value": "marina_view", "label": "Marina View", "sort_order": 5},
    )
    assert resp.status_code == 201
    assert resp.json()["sort_order"] == 5


# ---------------------------------------------------------------------------
# Update option
# ---------------------------------------------------------------------------


def test_update_option_label(client: TestClient):
    """PATCH updates option label."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)
    option = _create_option(client, project_id, defn["id"])

    resp = client.patch(
        f"/api/v1/projects/{project_id}/attribute-definitions/{defn['id']}/options/{option['id']}",
        json={"label": "Sea View (Updated)"},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Sea View (Updated)"


def test_deactivate_option(client: TestClient):
    """PATCH with is_active=false deactivates an option."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)
    option = _create_option(client, project_id, defn["id"])

    resp = client.patch(
        f"/api/v1/projects/{project_id}/attribute-definitions/{defn['id']}/options/{option['id']}",
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_update_option_duplicate_label_rejected(client: TestClient):
    """Updating an option to a label already used in same definition returns 409."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)
    opt1 = _create_option(client, project_id, defn["id"], "sea_view", "Sea View")
    opt2 = _create_option(client, project_id, defn["id"], "marina_view", "Marina View")

    resp = client.patch(
        f"/api/v1/projects/{project_id}/attribute-definitions/{defn['id']}/options/{opt2['id']}",
        json={"label": "Sea View"},
    )
    assert resp.status_code == 409


def test_update_option_same_label_no_conflict(client: TestClient):
    """Updating an option to its own current label should not conflict."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)
    option = _create_option(client, project_id, defn["id"], "sea_view", "Sea View")

    resp = client.patch(
        f"/api/v1/projects/{project_id}/attribute-definitions/{defn['id']}/options/{option['id']}",
        json={"label": "Sea View", "sort_order": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["sort_order"] == 3


def test_update_option_not_found(client: TestClient):
    """Updating a non-existent option returns 404."""
    project_id = _create_project(client)
    defn = _create_definition(client, project_id)

    resp = client.patch(
        f"/api/v1/projects/{project_id}/attribute-definitions/{defn['id']}/options/nonexistent-opt",
        json={"label": "X"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Definition belongs to correct project (cross-project isolation)
# ---------------------------------------------------------------------------


def test_definition_isolation_across_projects(client: TestClient):
    """A definition from project A is not accessible via project B's endpoints."""
    p1 = _create_project(client, "PROJ-ISO1")
    p2 = _create_project(client, "PROJ-ISO2")
    defn = _create_definition(client, p1)

    # Trying to update p1's definition via p2 should 404
    resp = client.patch(
        f"/api/v1/projects/{p2}/attribute-definitions/{defn['id']}",
        json={"label": "Should Fail"},
    )
    assert resp.status_code == 404
