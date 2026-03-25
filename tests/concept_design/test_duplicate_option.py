"""
Tests for the Concept Design option-duplication endpoint.

POST /api/v1/concept-options/{id}/duplicate

Test cases:
  - duplicate draft concept → 200, new option created
  - duplicate active concept → 200, new option created
  - unit mix lines copied to new option
  - promoted concept duplication allowed, is_promoted=False on copy
  - archived concept duplication rejected → 409
  - not found → 404
  - copy naming: first copy → "(Copy)", second → "(Copy 2)"

PR-CONCEPT-058
"""

from httpx import Response
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_project(client: TestClient, code: str = "PRJ-DUP01") -> str:
    resp = client.post(
        "/api/v1/projects", json={"name": f"Duplicate Test Project {code}", "code": code}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_option(
    client: TestClient,
    *,
    name: str = "Option To Duplicate",
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


def _add_mix_line(
    client: TestClient,
    option_id: str,
    unit_type: str = "studio",
    units_count: int = 5,
) -> dict:
    resp = client.post(
        f"/api/v1/concept-options/{option_id}/unit-mix",
        json={"unit_type": unit_type, "units_count": units_count},
    )
    assert resp.status_code == 201
    return resp.json()


def _duplicate(client: TestClient, option_id: str) -> Response:
    return client.post(f"/api/v1/concept-options/{option_id}/duplicate")


def _promote_option(client: TestClient, option_id: str, project_id: str) -> dict:
    resp = client.post(
        f"/api/v1/concept-options/{option_id}/promote",
        json={"target_project_id": project_id},
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Basic duplication
# ---------------------------------------------------------------------------

def test_duplicate_draft_concept_option(client: TestClient):
    """POST /concept-options/{id}/duplicate on a draft concept → 200, new option."""
    option = _create_option(client, name="Draft Concept", status="draft")
    resp = _duplicate(client, option["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] != option["id"]
    assert body["name"] == "Draft Concept (Copy)"
    assert body["status"] == "draft"


def test_duplicate_active_concept_option(client: TestClient):
    """POST .../duplicate on an active concept → 200, new option."""
    option = _create_option(client, name="Active Concept", status="active")
    resp = _duplicate(client, option["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Active Concept (Copy)"
    assert body["status"] == "active"


def test_duplicate_creates_new_record(client: TestClient):
    """After duplication both the original and the copy must be retrievable."""
    option = _create_option(client, name="New Record Check")
    copy_resp = _duplicate(client, option["id"])
    assert copy_resp.status_code == 200
    copy_id = copy_resp.json()["id"]

    get_original = client.get(f"/api/v1/concept-options/{option['id']}")
    get_copy = client.get(f"/api/v1/concept-options/{copy_id}")
    assert get_original.status_code == 200
    assert get_copy.status_code == 200


def test_duplicate_copies_physical_fields(client: TestClient):
    """The duplicate should carry over site_area, gfa, building_count, floor_count."""
    resp = client.post(
        "/api/v1/concept-options",
        json={
            "name": "Physical Fields",
            "status": "draft",
            "site_area": 1000.0,
            "gross_floor_area": 5000.0,
            "building_count": 3,
            "floor_count": 8,
        },
    )
    assert resp.status_code == 201
    option = resp.json()

    dup = _duplicate(client, option["id"])
    assert dup.status_code == 200
    body = dup.json()
    assert body["site_area"] == option["site_area"]
    assert body["gross_floor_area"] == option["gross_floor_area"]
    assert body["building_count"] == option["building_count"]
    assert body["floor_count"] == option["floor_count"]


# ---------------------------------------------------------------------------
# Unit mix copy
# ---------------------------------------------------------------------------

def test_duplicate_copies_unit_mix_lines(client: TestClient):
    """Unit mix lines from the original must be duplicated to the copy."""
    option = _create_option(client, name="Mix Copy")
    _add_mix_line(client, option["id"], unit_type="studio", units_count=10)
    _add_mix_line(client, option["id"], unit_type="1br", units_count=20)

    copy_resp = _duplicate(client, option["id"])
    assert copy_resp.status_code == 200
    copy_id = copy_resp.json()["id"]

    # Verify via summary (which includes mix lines)
    summary = client.get(f"/api/v1/concept-options/{copy_id}/summary")
    assert summary.status_code == 200
    mix_lines = summary.json()["mix_lines"]
    assert len(mix_lines) == 2


def test_duplicate_original_mix_unchanged(client: TestClient):
    """Duplicating must not alter the original option's unit mix lines."""
    option = _create_option(client, name="Original Untouched")
    _add_mix_line(client, option["id"], unit_type="studio", units_count=5)

    _duplicate(client, option["id"])

    summary = client.get(f"/api/v1/concept-options/{option['id']}/summary")
    assert summary.status_code == 200
    assert len(summary.json()["mix_lines"]) == 1


def test_duplicate_without_mix_lines(client: TestClient):
    """Duplicating a concept with no mix lines should succeed with an empty mix."""
    option = _create_option(client, name="No Mix")
    copy_resp = _duplicate(client, option["id"])
    assert copy_resp.status_code == 200
    copy_id = copy_resp.json()["id"]

    summary = client.get(f"/api/v1/concept-options/{copy_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["mix_lines"] == []


# ---------------------------------------------------------------------------
# Promoted concept duplication
# ---------------------------------------------------------------------------

def test_duplicate_promoted_concept_is_allowed(client: TestClient):
    """Promoted concepts can be duplicated."""
    project_id = _create_project(client, "PRJ-DUP-P01")
    option = _create_option(
        client,
        name="Promoted For Copy",
        status="active",
        project_id=project_id,
        building_count=1,
        floor_count=2,
    )
    _add_mix_line(client, option["id"])
    _promote_option(client, option["id"], project_id)

    copy_resp = _duplicate(client, option["id"])
    assert copy_resp.status_code == 200


def test_duplicate_promoted_copy_is_not_promoted(client: TestClient):
    """The copy of a promoted concept must have is_promoted=False."""
    project_id = _create_project(client, "PRJ-DUP-P02")
    option = _create_option(
        client,
        name="Promoted Copy Check",
        status="active",
        project_id=project_id,
        building_count=1,
        floor_count=2,
    )
    _add_mix_line(client, option["id"])
    _promote_option(client, option["id"], project_id)

    copy_resp = _duplicate(client, option["id"])
    assert copy_resp.status_code == 200
    body = copy_resp.json()
    assert body["is_promoted"] is False
    assert body["promoted_at"] is None
    assert body["promoted_project_id"] is None


# ---------------------------------------------------------------------------
# Forbidden duplication — archived concept
# ---------------------------------------------------------------------------

def test_duplicate_archived_concept_is_rejected(client: TestClient):
    """Archived concepts cannot be duplicated → 409 Conflict."""
    option = _create_option(client, name="Archived Option", status="archived")
    resp = _duplicate(client, option["id"])
    assert resp.status_code == 409
    assert resp.json().get("code") == "CONFLICT"


def test_archived_original_unchanged_after_rejection(client: TestClient):
    """After a rejected duplication the original archived option must still exist."""
    option = _create_option(client, name="Archived Unchanged", status="archived")
    _duplicate(client, option["id"])
    get_resp = client.get(f"/api/v1/concept-options/{option['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "archived"


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------

def test_duplicate_concept_option_not_found(client: TestClient):
    """POST .../duplicate with unknown id → 404."""
    resp = _duplicate(client, "no-such-id")
    assert resp.status_code == 404
    assert resp.json().get("code") == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Copy naming convention
# ---------------------------------------------------------------------------

def test_first_copy_name_has_copy_suffix(client: TestClient):
    """First duplicate → '<original> (Copy)'."""
    option = _create_option(client, name="Naming Test")
    copy = _duplicate(client, option["id"])
    assert copy.status_code == 200
    assert copy.json()["name"] == "Naming Test (Copy)"


def test_second_copy_name_has_copy_2_suffix(client: TestClient):
    """Second duplicate of same name → '<original> (Copy 2)'."""
    option = _create_option(client, name="Naming Test 2")
    first_copy = _duplicate(client, option["id"])
    assert first_copy.status_code == 200
    assert first_copy.json()["name"] == "Naming Test 2 (Copy)"

    second_copy = _duplicate(client, option["id"])
    assert second_copy.status_code == 200
    assert second_copy.json()["name"] == "Naming Test 2 (Copy 2)"


def test_third_copy_name_increments(client: TestClient):
    """Third duplicate → '<original> (Copy 3)'."""
    option = _create_option(client, name="Naming Test 3")
    _duplicate(client, option["id"])  # Copy
    _duplicate(client, option["id"])  # Copy 2
    third = _duplicate(client, option["id"])
    assert third.status_code == 200
    assert third.json()["name"] == "Naming Test 3 (Copy 3)"
