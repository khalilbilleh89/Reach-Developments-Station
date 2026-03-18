"""
Tests for the unit dynamic attribute values module (PR-033).

Validates save / list / upsert behaviour and project-scope integrity enforcement.
"""

import pytest
from fastapi.testclient import TestClient


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-DYN"):
    """Create a full Project → Phase → Building → Floor hierarchy and return IDs."""
    project = client.post(
        "/api/v1/projects", json={"name": "Dynamic Attr Project", "code": proj_code}
    ).json()
    project_id = project["id"]

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
        json={"name": "Ground Floor", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]

    return project_id, floor_id


def _create_unit(client: TestClient, floor_id: str, unit_number: str = "101") -> str:
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": unit_number,
            "unit_type": "studio",
            "internal_area": 55.0,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_view_type_definition(client: TestClient, project_id: str) -> str:
    """Create a view_type attribute definition for the project and return its id."""
    response = client.post(
        f"/api/v1/projects/{project_id}/attribute-definitions",
        json={"key": "view_type", "label": "View Type"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_option(
    client: TestClient, project_id: str, definition_id: str, value: str, label: str
) -> str:
    """Add a selectable option to a project attribute definition."""
    response = client.post(
        f"/api/v1/projects/{project_id}/attribute-definitions/{definition_id}/options",
        json={"value": value, "label": label},
    )
    assert response.status_code == 201
    return response.json()["id"]


# ---------------------------------------------------------------------------
# List (empty state)
# ---------------------------------------------------------------------------


def test_list_dynamic_attributes_empty(client: TestClient):
    """GET /units/{id}/dynamic-attributes returns empty list when no values set."""
    _, floor_id = _create_hierarchy(client, "PRJ-DYNLIST")
    unit_id = _create_unit(client, floor_id)

    response = client.get(f"/api/v1/units/{unit_id}/dynamic-attributes")
    assert response.status_code == 200
    assert response.json() == []


def test_list_dynamic_attributes_unit_not_found(client: TestClient):
    """GET /units/{id}/dynamic-attributes with unknown unit returns 404."""
    response = client.get("/api/v1/units/no-such-unit/dynamic-attributes")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Save (valid)
# ---------------------------------------------------------------------------


def test_save_dynamic_attribute_value(client: TestClient):
    """PUT saves a project-defined attribute value for a unit."""
    project_id, floor_id = _create_hierarchy(client, "PRJ-DYNSAVE")
    unit_id = _create_unit(client, floor_id)

    definition_id = _create_view_type_definition(client, project_id)
    option_id = _create_option(client, project_id, definition_id, "sea_view", "Sea View")

    response = client.put(
        f"/api/v1/units/{unit_id}/dynamic-attributes",
        json={"attributes": [{"definition_id": definition_id, "option_id": option_id}]},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    row = data[0]
    assert row["unit_id"] == unit_id
    assert row["definition_id"] == definition_id
    assert row["option_id"] == option_id
    assert row["definition_key"] == "view_type"
    assert row["definition_label"] == "View Type"
    assert row["option_value"] == "sea_view"
    assert row["option_label"] == "Sea View"


def test_list_dynamic_attributes_after_save(client: TestClient):
    """GET returns the saved value after PUT."""
    project_id, floor_id = _create_hierarchy(client, "PRJ-DYNGET")
    unit_id = _create_unit(client, floor_id)
    definition_id = _create_view_type_definition(client, project_id)
    option_id = _create_option(client, project_id, definition_id, "marina_view", "Marina View")

    client.put(
        f"/api/v1/units/{unit_id}/dynamic-attributes",
        json={"attributes": [{"definition_id": definition_id, "option_id": option_id}]},
    )

    response = client.get(f"/api/v1/units/{unit_id}/dynamic-attributes")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["option_label"] == "Marina View"


# ---------------------------------------------------------------------------
# Upsert behaviour
# ---------------------------------------------------------------------------


def test_upsert_replaces_previous_selection(client: TestClient):
    """Saving a new option for the same definition replaces the previous selection."""
    project_id, floor_id = _create_hierarchy(client, "PRJ-DYNUPS")
    unit_id = _create_unit(client, floor_id)
    definition_id = _create_view_type_definition(client, project_id)
    opt1 = _create_option(client, project_id, definition_id, "sea_view", "Sea View")
    opt2 = _create_option(client, project_id, definition_id, "internal_view", "Internal View")

    # First save: sea_view
    client.put(
        f"/api/v1/units/{unit_id}/dynamic-attributes",
        json={"attributes": [{"definition_id": definition_id, "option_id": opt1}]},
    )

    # Second save: internal_view (should replace)
    response = client.put(
        f"/api/v1/units/{unit_id}/dynamic-attributes",
        json={"attributes": [{"definition_id": definition_id, "option_id": opt2}]},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["option_id"] == opt2
    assert data[0]["option_label"] == "Internal View"

    # GET also reflects the updated value (one row per definition)
    get_response = client.get(f"/api/v1/units/{unit_id}/dynamic-attributes")
    assert len(get_response.json()) == 1
    assert get_response.json()[0]["option_id"] == opt2


# ---------------------------------------------------------------------------
# Integrity: invalid unit
# ---------------------------------------------------------------------------


def test_save_dynamic_attribute_unit_not_found(client: TestClient):
    """PUT with unknown unit_id returns 404."""
    response = client.put(
        "/api/v1/units/no-such-unit/dynamic-attributes",
        json={"attributes": [{"definition_id": "x", "option_id": "y"}]},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Integrity: definition not found
# ---------------------------------------------------------------------------


def test_save_dynamic_attribute_definition_not_found(client: TestClient):
    """PUT with unknown definition_id returns 404."""
    _, floor_id = _create_hierarchy(client, "PRJ-DYNNODEF")
    unit_id = _create_unit(client, floor_id)

    response = client.put(
        f"/api/v1/units/{unit_id}/dynamic-attributes",
        json={"attributes": [{"definition_id": "no-such-def", "option_id": "x"}]},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Integrity: cross-project definition (different project's definition)
# ---------------------------------------------------------------------------


def test_save_dynamic_attribute_cross_project_rejected(client: TestClient):
    """PUT with definition from a different project returns 422."""
    # Project A owns the unit
    project_a_id, floor_id = _create_hierarchy(client, "PRJ-DYNPA")
    unit_id = _create_unit(client, floor_id)

    # Project B owns the definition
    project_b = client.post(
        "/api/v1/projects", json={"name": "Project B", "code": "PRJ-DYNPB"}
    ).json()
    project_b_id = project_b["id"]
    definition_b_id = _create_view_type_definition(client, project_b_id)
    option_b_id = _create_option(client, project_b_id, definition_b_id, "sea", "Sea")

    response = client.put(
        f"/api/v1/units/{unit_id}/dynamic-attributes",
        json={"attributes": [{"definition_id": definition_b_id, "option_id": option_b_id}]},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Integrity: option does not belong to definition
# ---------------------------------------------------------------------------


def test_save_dynamic_attribute_wrong_option_definition_rejected(client: TestClient):
    """PUT with option that belongs to a different definition returns 422.

    Creates two projects each with their own view_type definition.
    An option from project B's definition must be rejected when saved
    against project A's definition (option.definition_id != definition_id).
    """
    # Project A — owns the unit under test
    project_a_id, floor_id = _create_hierarchy(client, "PRJ-DYNMM-A")
    unit_id = _create_unit(client, floor_id)
    def_a_id = _create_view_type_definition(client, project_a_id)
    _create_option(client, project_a_id, def_a_id, "sea", "Sea View")

    # Project B — owns a separate view_type definition with its own option
    project_b = client.post(
        "/api/v1/projects", json={"name": "Project B Mismatch", "code": "PRJ-DYNMM-B"}
    ).json()
    project_b_id = project_b["id"]
    def_b_id = _create_view_type_definition(client, project_b_id)
    opt_b_id = _create_option(client, project_b_id, def_b_id, "marina", "Marina View")

    # Attempt: save using definition_A but option from definition_B → 422
    response = client.put(
        f"/api/v1/units/{unit_id}/dynamic-attributes",
        json={"attributes": [{"definition_id": def_a_id, "option_id": opt_b_id}]},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Integrity: option not found
# ---------------------------------------------------------------------------


def test_save_dynamic_attribute_option_not_found(client: TestClient):
    """PUT with unknown option_id returns 404."""
    project_id, floor_id = _create_hierarchy(client, "PRJ-DYNNOOPT")
    unit_id = _create_unit(client, floor_id)
    definition_id = _create_view_type_definition(client, project_id)

    response = client.put(
        f"/api/v1/units/{unit_id}/dynamic-attributes",
        json={"attributes": [{"definition_id": definition_id, "option_id": "no-such-opt"}]},
    )
    assert response.status_code == 404
