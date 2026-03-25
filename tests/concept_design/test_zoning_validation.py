"""
Tests for PR-CONCEPT-059: FAR, Zoning & Density Validation.

Covers:
  - Pure validation engine (unit tests, no DB)
  - API: create blocked when FAR violated
  - API: update blocked when FAR violated
  - API: promote blocked when FAR / efficiency / density violated
  - API: valid concepts still save and promote without interference

PR-CONCEPT-059
"""

import pytest
from fastapi.testclient import TestClient

from app.modules.concept_design.validation import (
    ConceptZoningViolation,
    run_zoning_validation,
    validate_density_rule,
    validate_efficiency_rule,
    validate_far_rule,
)


# ===========================================================================
# Pure engine tests — no database required
# ===========================================================================


class TestFarRule:
    def test_passes_when_gfa_equals_max(self):
        # GFA == site_area * far_limit → exactly at limit, should pass
        assert validate_far_rule(5000.0, 10000.0, 2.0) is None

    def test_passes_when_gfa_below_max(self):
        assert validate_far_rule(5000.0, 8000.0, 2.0) is None

    def test_fails_when_gfa_exceeds_max(self):
        # max = 5000 * 2.0 = 10000; GFA = 15000 → violation
        violation = validate_far_rule(5000.0, 15000.0, 2.0)
        assert violation is not None
        assert violation.rule == "FAR_EXCEEDED"
        assert "15,000" in violation.message
        assert "10,000" in violation.message
        assert violation.details["max_permitted_gfa"] == 10000.0

    def test_skipped_when_site_area_absent(self):
        assert validate_far_rule(None, 15000.0, 2.0) is None

    def test_skipped_when_gfa_absent(self):
        assert validate_far_rule(5000.0, None, 2.0) is None

    def test_skipped_when_far_limit_absent(self):
        assert validate_far_rule(5000.0, 15000.0, None) is None

    def test_skipped_when_site_area_zero(self):
        assert validate_far_rule(0.0, 15000.0, 2.0) is None

    def test_skipped_when_far_limit_zero(self):
        assert validate_far_rule(5000.0, 15000.0, 0.0) is None


class TestEfficiencyRule:
    def test_passes_at_exactly_100_pct(self):
        # sellable == gfa → efficiency == 1.0, still valid
        assert validate_efficiency_rule(10000.0, 10000.0) is None

    def test_passes_below_100_pct(self):
        assert validate_efficiency_rule(7500.0, 10000.0) is None

    def test_fails_when_sellable_exceeds_gfa(self):
        violation = validate_efficiency_rule(12000.0, 10000.0)
        assert violation is not None
        assert violation.rule == "EFFICIENCY_IMPOSSIBLE"
        assert "12,000" in violation.message
        assert "10,000" in violation.message
        assert violation.details["efficiency_ratio"] == pytest.approx(1.2, rel=1e-4)

    def test_skipped_when_sellable_absent(self):
        assert validate_efficiency_rule(None, 10000.0) is None

    def test_skipped_when_gfa_absent(self):
        assert validate_efficiency_rule(7500.0, None) is None

    def test_skipped_when_gfa_zero(self):
        assert validate_efficiency_rule(7500.0, 0.0) is None


class TestDensityRule:
    def test_passes_at_exactly_limit(self):
        # site_area = 10000 sqm = 1 ha; density = 50 dph → max = 50
        assert validate_density_rule(50, 10000.0, 50.0) is None

    def test_passes_below_limit(self):
        assert validate_density_rule(40, 10000.0, 50.0) is None

    def test_fails_when_unit_count_exceeds_limit(self):
        # site_area = 5000 sqm = 0.5 ha; density = 50 dph → max = 25
        violation = validate_density_rule(30, 5000.0, 50.0)
        assert violation is not None
        assert violation.rule == "DENSITY_EXCEEDED"
        assert "30" in violation.message
        assert "25" in violation.message
        assert violation.details["unit_count"] == 30
        assert violation.details["max_permitted_units"] == 25.0

    def test_skipped_when_unit_count_absent(self):
        assert validate_density_rule(None, 5000.0, 50.0) is None

    def test_skipped_when_site_area_absent(self):
        assert validate_density_rule(30, None, 50.0) is None

    def test_skipped_when_density_limit_absent(self):
        assert validate_density_rule(30, 5000.0, None) is None

    def test_skipped_when_site_area_zero(self):
        assert validate_density_rule(30, 0.0, 50.0) is None

    def test_skipped_when_density_limit_zero(self):
        assert validate_density_rule(30, 5000.0, 0.0) is None


class TestRunZoningValidation:
    def test_no_violations_all_inputs_valid(self):
        violations = run_zoning_validation(
            site_area=5000.0,
            gross_floor_area=8000.0,
            far_limit=2.0,
            density_limit=50.0,
            sellable_area=7000.0,
            unit_count=20,
        )
        assert violations == []

    def test_far_violation_only(self):
        violations = run_zoning_validation(
            site_area=5000.0,
            gross_floor_area=15000.0,  # > 5000 * 2.0 = 10000
            far_limit=2.0,
            density_limit=None,
        )
        assert len(violations) == 1
        assert violations[0].rule == "FAR_EXCEEDED"

    def test_efficiency_violation_only(self):
        violations = run_zoning_validation(
            site_area=None,
            gross_floor_area=10000.0,
            far_limit=None,
            density_limit=None,
            sellable_area=12000.0,  # > gfa
        )
        assert len(violations) == 1
        assert violations[0].rule == "EFFICIENCY_IMPOSSIBLE"

    def test_density_violation_only(self):
        violations = run_zoning_validation(
            site_area=5000.0,
            gross_floor_area=None,
            far_limit=None,
            density_limit=50.0,
            unit_count=30,  # > 50 * 0.5 = 25
        )
        assert len(violations) == 1
        assert violations[0].rule == "DENSITY_EXCEEDED"

    def test_multiple_violations(self):
        violations = run_zoning_validation(
            site_area=5000.0,
            gross_floor_area=15000.0,  # exceeds FAR
            far_limit=2.0,
            density_limit=50.0,
            sellable_area=16000.0,  # > gfa (efficiency)
            unit_count=30,  # exceeds density
        )
        rules = {v.rule for v in violations}
        assert "FAR_EXCEEDED" in rules
        assert "EFFICIENCY_IMPOSSIBLE" in rules
        assert "DENSITY_EXCEEDED" in rules

    def test_no_inputs_no_violations(self):
        violations = run_zoning_validation(
            site_area=None,
            gross_floor_area=None,
            far_limit=None,
            density_limit=None,
        )
        assert violations == []


# ===========================================================================
# API-level tests — uses the test database
# ===========================================================================


def _create_project(client: TestClient, code: str) -> str:
    resp = client.post(
        "/api/v1/projects", json={"name": f"Val Project {code}", "code": code}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_option(client: TestClient, **kwargs) -> dict:
    payload = {"name": "Test Option", "status": "draft"}
    payload.update(kwargs)
    resp = client.post("/api/v1/concept-options", json=payload)
    return resp


class TestCreateWithFarValidation:
    def test_create_valid_far(self, client: TestClient):
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "Valid FAR Option",
                "site_area": 5000.0,
                "gross_floor_area": 9000.0,  # <= 5000 * 2.0 = 10000
                "far_limit": 2.0,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["far_limit"] == 2.0

    def test_create_invalid_far_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "Over FAR Option",
                "site_area": 5000.0,
                "gross_floor_area": 15000.0,  # > 5000 * 2.0 = 10000
                "far_limit": 2.0,
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "VALIDATION_ERROR"
        violations = body["details"]["violations"]
        assert any(v["rule"] == "FAR_EXCEEDED" for v in violations)

    def test_create_without_far_limit_skips_far_check(self, client: TestClient):
        # No far_limit → rule is skipped even if GFA looks high
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "No FAR Limit",
                "site_area": 5000.0,
                "gross_floor_area": 50000.0,
            },
        )
        assert resp.status_code == 201

    def test_create_without_site_area_skips_far_check(self, client: TestClient):
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "No Site Area",
                "gross_floor_area": 50000.0,
                "far_limit": 2.0,
            },
        )
        assert resp.status_code == 201

    def test_create_far_and_density_limit_stored(self, client: TestClient):
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "With Constraints",
                "site_area": 10000.0,
                "gross_floor_area": 15000.0,
                "far_limit": 2.0,
                "density_limit": 100.0,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["far_limit"] == 2.0
        assert data["density_limit"] == 100.0


class TestUpdateWithFarValidation:
    def test_update_triggers_far_validation_on_merged_state(self, client: TestClient):
        # Create an option with far_limit=2.0, site_area=5000
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "FAR Update Test",
                "site_area": 5000.0,
                "gross_floor_area": 5000.0,
                "far_limit": 2.0,
            },
        )
        assert resp.status_code == 201
        option_id = resp.json()["id"]

        # Now try to update gfa to a value that violates FAR
        patch_resp = client.patch(
            f"/api/v1/concept-options/{option_id}",
            json={"gross_floor_area": 15000.0},  # > 5000 * 2.0 = 10000
        )
        assert patch_resp.status_code == 422
        body = patch_resp.json()
        violations = body["details"]["violations"]
        assert any(v["rule"] == "FAR_EXCEEDED" for v in violations)

    def test_update_valid_far_succeeds(self, client: TestClient):
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "FAR Update Valid",
                "site_area": 5000.0,
                "gross_floor_area": 5000.0,
                "far_limit": 2.0,
            },
        )
        assert resp.status_code == 201
        option_id = resp.json()["id"]

        patch_resp = client.patch(
            f"/api/v1/concept-options/{option_id}",
            json={"gross_floor_area": 9500.0},  # <= 10000
        )
        assert patch_resp.status_code == 200

    def test_update_adding_far_limit_validates_against_existing_gfa(
        self, client: TestClient
    ):
        # Create with large gfa but no far_limit
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "Add FAR Limit",
                "site_area": 5000.0,
                "gross_floor_area": 15000.0,  # would violate FAR 2.0
            },
        )
        assert resp.status_code == 201
        option_id = resp.json()["id"]

        # Now set a far_limit that would be violated
        patch_resp = client.patch(
            f"/api/v1/concept-options/{option_id}",
            json={"far_limit": 2.0},
        )
        assert patch_resp.status_code == 422
        violations = patch_resp.json()["details"]["violations"]
        assert any(v["rule"] == "FAR_EXCEEDED" for v in violations)


class TestPromoteWithZoningValidation:
    def _create_promotable_option(
        self,
        client: TestClient,
        project_id: str,
        *,
        site_area: float = 10000.0,
        gross_floor_area: float = 10000.0,
        far_limit: float | None = None,
        density_limit: float | None = None,
        mix_lines: list | None = None,
    ) -> dict:
        payload: dict = {
            "name": "Promotable Option",
            "project_id": project_id,
            "status": "active",
            "gross_floor_area": gross_floor_area,
            "building_count": 2,
            "floor_count": 4,
            "site_area": site_area,
        }
        if far_limit is not None:
            payload["far_limit"] = far_limit
        if density_limit is not None:
            payload["density_limit"] = density_limit

        resp = client.post("/api/v1/concept-options", json=payload)
        assert resp.status_code == 201, resp.json()
        option = resp.json()

        lines = mix_lines or [
            {"unit_type": "2BR", "units_count": 20, "avg_sellable_area": 90.0},
            {"unit_type": "1BR", "units_count": 20, "avg_sellable_area": 65.0},
        ]
        for line in lines:
            r = client.post(
                f"/api/v1/concept-options/{option['id']}/unit-mix", json=line
            )
            assert r.status_code == 201
        return option

    def test_promote_valid_concept_succeeds(self, client: TestClient):
        project_id = _create_project(client, "PRV-VAL-001")
        option = self._create_promotable_option(
            client,
            project_id,
            site_area=10000.0,
            gross_floor_area=15000.0,
            far_limit=2.0,  # max = 10000 * 2 = 20000; 15000 < 20000 → ok
            density_limit=50.0,  # max = 50 * 1 = 50 units; 40 < 50 → ok
        )
        resp = client.post(
            f"/api/v1/concept-options/{option['id']}/promote", json={}
        )
        assert resp.status_code == 201

    def test_promote_blocked_when_efficiency_impossible(self, client: TestClient):
        project_id = _create_project(client, "PRV-EFF-001")
        # Create option with gfa=1000 (will be violated by mix)
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "Efficiency Block",
                "project_id": project_id,
                "status": "active",
                "gross_floor_area": 1000.0,
                "building_count": 1,
                "floor_count": 2,
            },
        )
        assert resp.status_code == 201
        option_id = resp.json()["id"]

        # Mix lines with sellable_area > gfa (1000)
        client.post(
            f"/api/v1/concept-options/{option_id}/unit-mix",
            json={"unit_type": "2BR", "units_count": 20, "avg_sellable_area": 100.0},
            # total sellable = 20 * 100 = 2000 > 1000 gfa
        )

        resp = client.post(
            f"/api/v1/concept-options/{option_id}/promote", json={}
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "VALIDATION_ERROR"
        violations = body["details"]["violations"]
        assert any(v["rule"] == "EFFICIENCY_IMPOSSIBLE" for v in violations)

    def test_promote_blocked_when_density_exceeded(self, client: TestClient):
        project_id = _create_project(client, "PRV-DEN-001")
        # site=5000sqm (0.5ha), density=20 dph → max_units=10
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "Density Block",
                "project_id": project_id,
                "status": "active",
                "site_area": 5000.0,
                "gross_floor_area": 10000.0,
                "building_count": 1,
                "floor_count": 5,
                "density_limit": 20.0,  # max = 20 * 0.5 = 10 units
            },
        )
        assert resp.status_code == 201
        option_id = resp.json()["id"]

        # Add 30 units (> 10 max)
        client.post(
            f"/api/v1/concept-options/{option_id}/unit-mix",
            json={"unit_type": "1BR", "units_count": 30, "avg_sellable_area": 60.0},
        )

        resp = client.post(
            f"/api/v1/concept-options/{option_id}/promote", json={}
        )
        assert resp.status_code == 422
        body = resp.json()
        violations = body["details"]["violations"]
        assert any(v["rule"] == "DENSITY_EXCEEDED" for v in violations)

    def test_no_partial_hierarchy_created_on_failed_promotion(
        self, client: TestClient
    ):
        project_id = _create_project(client, "PRV-NOPH-001")
        # Efficiency violation scenario: gfa=100, mix sellable=2000
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "No Partial",
                "project_id": project_id,
                "status": "active",
                "gross_floor_area": 100.0,
                "building_count": 1,
                "floor_count": 2,
            },
        )
        assert resp.status_code == 201
        option_id = resp.json()["id"]

        client.post(
            f"/api/v1/concept-options/{option_id}/unit-mix",
            json={"unit_type": "2BR", "units_count": 20, "avg_sellable_area": 100.0},
        )

        promote_resp = client.post(
            f"/api/v1/concept-options/{option_id}/promote", json={}
        )
        assert promote_resp.status_code == 422

        # Option must not be marked as promoted
        detail_resp = client.get(f"/api/v1/concept-options/{option_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["is_promoted"] is False

    def test_promote_valid_concept_without_constraints_succeeds(
        self, client: TestClient
    ):
        project_id = _create_project(client, "PRV-NOVAL-001")
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "No Constraint Option",
                "project_id": project_id,
                "status": "active",
                "gross_floor_area": 10000.0,
                "building_count": 2,
                "floor_count": 3,
            },
        )
        assert resp.status_code == 201
        option_id = resp.json()["id"]

        client.post(
            f"/api/v1/concept-options/{option_id}/unit-mix",
            json={"unit_type": "1BR", "units_count": 10, "avg_sellable_area": 65.0},
        )

        promote_resp = client.post(
            f"/api/v1/concept-options/{option_id}/promote", json={}
        )
        assert promote_resp.status_code == 201


class TestSummaryIncludesConstraintFields:
    def test_summary_returns_far_and_density_limit(self, client: TestClient):
        resp = client.post(
            "/api/v1/concept-options",
            json={
                "name": "Summary Constraints",
                "site_area": 8000.0,
                "gross_floor_area": 12000.0,
                "far_limit": 2.0,
                "density_limit": 75.0,
            },
        )
        assert resp.status_code == 201
        option_id = resp.json()["id"]

        summary_resp = client.get(f"/api/v1/concept-options/{option_id}/summary")
        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        assert summary["far_limit"] == 2.0
        assert summary["density_limit"] == 75.0

    def test_summary_returns_null_constraints_when_absent(self, client: TestClient):
        resp = client.post(
            "/api/v1/concept-options",
            json={"name": "No Constraints"},
        )
        assert resp.status_code == 201
        option_id = resp.json()["id"]

        summary_resp = client.get(f"/api/v1/concept-options/{option_id}/summary")
        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        assert summary["far_limit"] is None
        assert summary["density_limit"] is None
