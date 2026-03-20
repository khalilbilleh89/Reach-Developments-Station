"""
Tests for the project lifecycle phase engine.

Validates lifecycle progression rules:
  - Phases are ordered by sequence.
  - Cannot activate a phase if a prior phase is not completed.
  - Cannot regress a completed phase without explicit reopen.
  - Lifecycle advancement marks phase as completed and activates next.
  - get_project_lifecycle returns ordered phases with correct current markers.
"""

import pytest
from fastapi.testclient import TestClient


def _create_project(client: TestClient, code: str = "LC-001") -> str:
    resp = client.post("/api/v1/projects", json={"name": "Lifecycle Project", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_phase(
    client: TestClient,
    project_id: str,
    name: str,
    sequence: int,
    phase_type: str | None = None,
    status: str = "planned",
) -> dict:
    payload: dict = {"name": name, "sequence": sequence, "status": status}
    if phase_type:
        payload["phase_type"] = phase_type
    resp = client.post(f"/api/v1/projects/{project_id}/phases", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Phase type field ────────────────────────────────────────────────────────

def test_phase_type_is_persisted(client: TestClient):
    """Phase type (concept/design/...) must be stored and returned."""
    project_id = _create_project(client, "PT-001")
    phase = _create_phase(client, project_id, "Concept Phase", 1, phase_type="concept")
    assert phase["phase_type"] == "concept"


def test_phase_type_defaults_to_null(client: TestClient):
    """Phase type is optional — must default to null if not provided."""
    project_id = _create_project(client, "PT-002")
    phase = _create_phase(client, project_id, "Generic Phase", 1)
    assert phase["phase_type"] is None


def test_phase_type_invalid_value_rejected(client: TestClient):
    """Invalid phase_type value must be rejected with 422."""
    project_id = _create_project(client, "PT-003")
    resp = client.post(
        f"/api/v1/projects/{project_id}/phases",
        json={"name": "Bad Type Phase", "sequence": 1, "phase_type": "unknown_type"},
    )
    assert resp.status_code == 422


def test_all_canonical_phase_types_accepted(client: TestClient):
    """All six canonical lifecycle phase types must be accepted."""
    project_id = _create_project(client, "PT-004")
    canonical_types = ["concept", "design", "approvals", "construction", "sales", "handover"]
    for seq, pt in enumerate(canonical_types, start=1):
        phase = _create_phase(client, project_id, pt.capitalize(), seq, phase_type=pt)
        assert phase["phase_type"] == pt


# ── Lifecycle ordering ──────────────────────────────────────────────────────

def test_lifecycle_phases_ordered_by_sequence(client: TestClient):
    """GET /projects/{id}/lifecycle must return phases sorted by sequence."""
    project_id = _create_project(client, "LO-001")
    _create_phase(client, project_id, "Construction", 3, phase_type="construction")
    _create_phase(client, project_id, "Concept", 1, phase_type="concept")
    _create_phase(client, project_id, "Design", 2, phase_type="design")

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle")
    assert resp.status_code == 200
    phases = resp.json()["phases"]
    sequences = [p["sequence"] for p in phases]
    assert sequences == sorted(sequences)


def test_lifecycle_identifies_current_active_phase(client: TestClient):
    """The active phase must be flagged as is_current=True in the lifecycle response."""
    project_id = _create_project(client, "LO-002")
    _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="completed")
    _create_phase(client, project_id, "Design", 2, phase_type="design", status="active")
    _create_phase(client, project_id, "Approvals", 3, phase_type="approvals")

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_phase_type"] == "design"
    assert data["current_sequence"] == 2

    current = [p for p in data["phases"] if p["is_current"]]
    assert len(current) == 1
    assert current[0]["phase_type"] == "design"


def test_lifecycle_no_current_when_all_planned(client: TestClient):
    """When no phase is active, current_phase_type and current_sequence must be null."""
    project_id = _create_project(client, "LO-003")
    _create_phase(client, project_id, "Concept", 1, phase_type="concept")
    _create_phase(client, project_id, "Design", 2, phase_type="design")

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_phase_type"] is None
    assert data["current_sequence"] is None
    assert all(not p["is_current"] for p in data["phases"])


# ── Lifecycle activation rules ──────────────────────────────────────────────

def test_cannot_activate_phase_when_prior_phase_not_completed(client: TestClient):
    """Activating a phase must fail (422) if the preceding phase is not completed."""
    project_id = _create_project(client, "LR-001")
    _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="planned")
    phase2 = _create_phase(client, project_id, "Design", 2, phase_type="design")

    resp = client.patch(
        f"/api/v1/phases/{phase2['id']}",
        json={"status": "active"},
    )
    assert resp.status_code == 422
    assert "sequence" in resp.json()["detail"].lower() or "preceding" in resp.json()["detail"].lower()


def test_can_activate_phase_when_no_prior_phase(client: TestClient):
    """The first phase (no predecessor) can be activated freely."""
    project_id = _create_project(client, "LR-002")
    phase1 = _create_phase(client, project_id, "Concept", 1, phase_type="concept")

    resp = client.patch(f"/api/v1/phases/{phase1['id']}", json={"status": "active"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_can_activate_phase_when_prior_phase_completed(client: TestClient):
    """A phase can be activated when its predecessor is completed."""
    project_id = _create_project(client, "LR-003")
    _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="completed")
    phase2 = _create_phase(client, project_id, "Design", 2, phase_type="design")

    resp = client.patch(f"/api/v1/phases/{phase2['id']}", json={"status": "active"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


# ── Backward movement rules ─────────────────────────────────────────────────

def test_cannot_revert_completed_phase_via_patch(client: TestClient):
    """PATCH must reject reverting a completed phase back to planned or active."""
    project_id = _create_project(client, "BR-001")
    phase = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="completed")

    for target_status in ("planned", "active"):
        resp = client.patch(f"/api/v1/phases/{phase['id']}", json={"status": target_status})
        assert resp.status_code == 422, f"Expected 422 when reverting to '{target_status}'"


def test_reopen_endpoint_allows_reverting_completed_phase(client: TestClient):
    """POST /phases/{id}/reopen must allow reverting a completed phase to active."""
    project_id = _create_project(client, "BR-002")
    phase = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="completed")

    resp = client.post(f"/api/v1/phases/{phase['id']}/reopen")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_reopen_non_completed_phase_rejected(client: TestClient):
    """POST /phases/{id}/reopen on a non-completed phase must return 422."""
    project_id = _create_project(client, "BR-003")
    phase = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="planned")

    resp = client.post(f"/api/v1/phases/{phase['id']}/reopen")
    assert resp.status_code == 422


# ── Lifecycle advancement ───────────────────────────────────────────────────

def test_advance_marks_phase_completed_and_activates_next(client: TestClient):
    """POST /phases/{id}/advance must complete current and activate next."""
    project_id = _create_project(client, "ADV-001")
    phase1 = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="active")
    phase2 = _create_phase(client, project_id, "Design", 2, phase_type="design")

    resp = client.post(f"/api/v1/phases/{phase1['id']}/advance")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # Next phase should now be active
    get_resp = client.get(f"/api/v1/phases/{phase2['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "active"


def test_advance_last_phase_marks_completed_only(client: TestClient):
    """Advancing the last phase in a project simply marks it as completed."""
    project_id = _create_project(client, "ADV-002")
    phase1 = _create_phase(client, project_id, "Handover", 1, phase_type="handover", status="active")

    resp = client.post(f"/api/v1/phases/{phase1['id']}/advance")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_advance_non_active_phase_rejected(client: TestClient):
    """POST /phases/{id}/advance on a planned phase must return 422."""
    project_id = _create_project(client, "ADV-003")
    phase1 = _create_phase(client, project_id, "Concept", 1, phase_type="concept")

    resp = client.post(f"/api/v1/phases/{phase1['id']}/advance")
    assert resp.status_code == 422


def test_advance_already_completed_phase_rejected(client: TestClient):
    """POST /phases/{id}/advance on a completed phase must return 422."""
    project_id = _create_project(client, "ADV-004")
    phase1 = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="completed")

    resp = client.post(f"/api/v1/phases/{phase1['id']}/advance")
    assert resp.status_code == 422


def test_full_lifecycle_progression(client: TestClient):
    """Full concept→design→approvals→construction→sales→handover progression."""
    project_id = _create_project(client, "ADV-005")
    lifecycle_phases = ["concept", "design", "approvals", "construction", "sales", "handover"]
    created = [
        _create_phase(client, project_id, pt.capitalize(), seq + 1, phase_type=pt)
        for seq, pt in enumerate(lifecycle_phases)
    ]

    # Activate the first phase
    client.patch(f"/api/v1/phases/{created[0]['id']}", json={"status": "active"})

    # Advance through each phase
    for i in range(len(lifecycle_phases) - 1):
        resp = client.post(f"/api/v1/phases/{created[i]['id']}/advance")
        assert resp.status_code == 200, f"Failed to advance phase {i + 1}"
        assert resp.json()["status"] == "completed"

        next_phase = client.get(f"/api/v1/phases/{created[i + 1]['id']}")
        assert next_phase.json()["status"] == "active"

    # Advance final phase
    resp = client.post(f"/api/v1/phases/{created[-1]['id']}/advance")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # Verify lifecycle shows no current phase (all completed)
    lifecycle = client.get(f"/api/v1/projects/{project_id}/lifecycle")
    assert lifecycle.status_code == 200
    data = lifecycle.json()
    assert data["current_phase_type"] is None
    assert all(p["status"] == "completed" for p in data["phases"])


# ── Single active phase enforcement ────────────────────────────────────────

def test_cannot_create_second_active_phase_via_patch(client: TestClient):
    """Cannot PATCH a second phase to active when one is already active."""
    project_id = _create_project(client, "SA-001")
    _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="completed")
    _create_phase(client, project_id, "Design", 2, phase_type="design", status="active")
    phase3 = _create_phase(client, project_id, "Approvals", 3, phase_type="approvals")

    resp = client.patch(f"/api/v1/phases/{phase3['id']}", json={"status": "active"})
    assert resp.status_code == 409


def test_cannot_reopen_when_another_phase_is_active(client: TestClient):
    """Cannot reopen a completed phase when another phase is already active."""
    project_id = _create_project(client, "SA-002")
    phase1 = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="completed")
    _create_phase(client, project_id, "Design", 2, phase_type="design", status="active")

    resp = client.post(f"/api/v1/phases/{phase1['id']}/reopen")
    assert resp.status_code == 409


# ── Active phase ordering on sequence change ────────────────────────────────

def test_sequence_change_on_active_phase_enforces_prior_completion(client: TestClient):
    """Moving an active phase to a position where its new predecessor is not
    completed must be rejected with 422."""
    project_id = _create_project(client, "SC-001")
    # seq 1 = planned (NOT completed), no seq 2, seq 5 = active
    _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="planned")
    phase5 = _create_phase(client, project_id, "Approvals", 5, phase_type="approvals", status="active")

    # Move active phase to seq 2 — new predecessor (seq 1) is NOT completed; seq 2 is free
    resp = client.patch(f"/api/v1/phases/{phase5['id']}", json={"sequence": 2})
    assert resp.status_code == 422


def test_sequence_change_allowed_when_new_prior_is_completed(client: TestClient):
    """Moving an active phase to a position after a completed phase is allowed."""
    project_id = _create_project(client, "SC-002")
    _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="completed")
    # seq 3 is active; move it to seq 2 (no seq 2 exists, prior is seq 1 = completed)
    phase3 = _create_phase(client, project_id, "Design", 3, phase_type="design", status="active")

    resp = client.patch(f"/api/v1/phases/{phase3['id']}", json={"sequence": 2})
    assert resp.status_code == 200
    assert resp.json()["sequence"] == 2


# ── Advance with already-active or already-completed next phase ─────────────

def test_advance_rejects_when_next_phase_already_active(client: TestClient):
    """advance must return 409 when the next phase in sequence is already active."""
    project_id = _create_project(client, "ANP-001")
    phase1 = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="active")
    # Force next phase to active directly in DB via repo (bypasses service guards)
    # by creating it with active status
    _create_phase(client, project_id, "Design", 2, phase_type="design", status="active")

    resp = client.post(f"/api/v1/phases/{phase1['id']}/advance")
    assert resp.status_code == 409


def test_advance_rejects_when_next_phase_already_completed(client: TestClient):
    """advance must return 422 when the next phase in sequence is already completed."""
    project_id = _create_project(client, "ANP-002")
    phase1 = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="active")
    _create_phase(client, project_id, "Design", 2, phase_type="design", status="completed")

    resp = client.post(f"/api/v1/phases/{phase1['id']}/advance")
    assert resp.status_code == 422
