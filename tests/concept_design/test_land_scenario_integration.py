"""
Tests for PR-CONCEPT-060: Land & Scenario Integration for Concept Design.
PR-CONCEPT-060A: Hardening — persistence, error on missing parcel, and UI gating.

Covers:
  - Concept option inherits land constraints (site_area, far_limit, density_limit)
    from the linked scenario's land parcel
  - far_limit and density_limit are persisted (not left NULL) when inherited
  - ValidationError is raised when scenario.land_id references a missing LandParcel
  - Validation uses scenario-inherited FAR, not manually entered FAR
  - concept_override_far_limit takes priority over inherited land FAR
  - concept_override_density_limit takes priority over inherited land density

PR-CONCEPT-060, PR-CONCEPT-060A
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_land_parcel(
    client: TestClient,
    *,
    parcel_name: str = "Test Plot",
    parcel_code: str = "LP-060-001",
    land_area_sqm: float | None = 5000.0,
    permitted_far: float | None = 2.5,
    density_ratio: float | None = 120.0,
    zoning_category: str | None = "Residential",
) -> dict:
    payload: dict = {
        "parcel_name": parcel_name,
        "parcel_code": parcel_code,
    }
    if land_area_sqm is not None:
        payload["land_area_sqm"] = land_area_sqm
    if permitted_far is not None:
        payload["permitted_far"] = permitted_far
    if density_ratio is not None:
        payload["density_ratio"] = density_ratio
    if zoning_category is not None:
        payload["zoning_category"] = zoning_category

    resp = client.post("/api/v1/land/parcels", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_scenario(
    client: TestClient,
    *,
    name: str = "Integration Scenario",
    land_id: str | None = None,
) -> dict:
    payload: dict = {"name": name}
    if land_id is not None:
        payload["land_id"] = land_id
    resp = client.post("/api/v1/scenarios", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_concept_option(
    client: TestClient,
    payload: dict,
    *,
    expected_status: int = 201,
) -> dict:
    resp = client.post("/api/v1/concept-options", json=payload)
    assert resp.status_code == expected_status, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# test_concept_inherits_land_constraints
# ---------------------------------------------------------------------------


class TestConceptInheritsLandConstraints:
    """Concept option created with a scenario_id whose scenario has a land_id
    should automatically inherit site_area, far_limit, and density_limit from
    the linked land parcel."""

    def test_inherits_site_area_from_land_parcel(self, client: TestClient):
        """site_area is populated from land_area_sqm when not supplied by caller."""
        parcel = _create_land_parcel(client, land_area_sqm=6000.0)
        scenario = _create_scenario(client, land_id=parcel["id"])

        option = _create_concept_option(
            client, {"name": "Inherit Site Area", "scenario_id": scenario["id"]}
        )

        assert option["site_area"] == pytest.approx(6000.0)
        assert option["land_id"] == parcel["id"]
        assert option["scenario_id"] == scenario["id"]

    def test_inherits_far_limit_from_land_parcel(self, client: TestClient):
        """far_limit is populated from land.permitted_far when not supplied by caller."""
        parcel = _create_land_parcel(client, permitted_far=2.5, parcel_code="LP-FAR-01")
        scenario = _create_scenario(client, name="FAR Scenario", land_id=parcel["id"])

        option = _create_concept_option(
            client, {"name": "Inherit FAR", "scenario_id": scenario["id"]}
        )

        assert option["land_id"] == parcel["id"]
        assert option["far_limit"] == pytest.approx(2.5)

    def test_inherits_density_limit_from_land_parcel(self, client: TestClient):
        """density_limit is populated from land.density_ratio when not supplied by caller."""
        parcel = _create_land_parcel(
            client, density_ratio=80.0, parcel_code="LP-DENS-01"
        )
        scenario = _create_scenario(client, name="Density Scenario", land_id=parcel["id"])

        option = _create_concept_option(
            client, {"name": "Inherit Density", "scenario_id": scenario["id"]}
        )

        assert option["land_id"] == parcel["id"]
        assert option["density_limit"] == pytest.approx(80.0)

    def test_no_inheritance_when_scenario_has_no_land(self, client: TestClient):
        """When scenario has no land_id, no land constraints are inherited."""
        scenario = _create_scenario(client, name="No Land Scenario", land_id=None)

        option = _create_concept_option(
            client, {"name": "No Inherit", "scenario_id": scenario["id"]}
        )

        assert option["land_id"] is None
        # site_area should remain None since no land was provided
        assert option["site_area"] is None

    def test_no_inheritance_without_scenario(self, client: TestClient):
        """When no scenario_id is supplied, land_id remains None."""
        option = _create_concept_option(client, {"name": "No Scenario"})

        assert option["land_id"] is None
        assert option["site_area"] is None

    def test_caller_supplied_site_area_not_overwritten(self, client: TestClient):
        """Caller-supplied site_area takes precedence over land_area_sqm."""
        parcel = _create_land_parcel(
            client, land_area_sqm=6000.0, parcel_code="LP-SITE-02"
        )
        scenario = _create_scenario(client, name="Site Override Scenario", land_id=parcel["id"])

        option = _create_concept_option(
            client,
            {
                "name": "Explicit Site Area",
                "scenario_id": scenario["id"],
                "site_area": 3000.0,
            },
        )

        # Caller's value should be preserved
        assert option["site_area"] == pytest.approx(3000.0)
        assert option["land_id"] == parcel["id"]

    def test_land_id_included_in_response(self, client: TestClient):
        """land_id is present in the concept option response payload."""
        parcel = _create_land_parcel(client, parcel_code="LP-RESP-01")
        scenario = _create_scenario(client, name="Response Scenario", land_id=parcel["id"])

        option = _create_concept_option(
            client, {"name": "Response Check", "scenario_id": scenario["id"]}
        )

        assert "land_id" in option
        assert option["land_id"] == parcel["id"]

    def test_all_constraints_persisted_on_create(self, client: TestClient):
        """site_area, far_limit, and density_limit are all persisted (not NULL)
        when inherited from a land parcel at creation time."""
        parcel = _create_land_parcel(
            client,
            land_area_sqm=4500.0,
            permitted_far=3.0,
            density_ratio=90.0,
            parcel_code="LP-ALL-01",
        )
        scenario = _create_scenario(client, name="All Constraints Scenario", land_id=parcel["id"])

        option = _create_concept_option(
            client, {"name": "All Constraints", "scenario_id": scenario["id"]}
        )

        assert option["site_area"] == pytest.approx(4500.0)
        assert option["far_limit"] == pytest.approx(3.0)
        assert option["density_limit"] == pytest.approx(90.0)
        assert option["land_id"] == parcel["id"]


# ---------------------------------------------------------------------------
# test_missing_land_parcel_raises_error
# ---------------------------------------------------------------------------


class TestMissingLandParcelRaisesError:
    """When scenario.land_id is set but the referenced LandParcel is missing,
    concept creation must raise a ValidationError (not silently fall back)."""

    def test_create_raises_422_when_land_parcel_missing(
        self, client: TestClient, db_session: Session
    ):
        """Concept creation is rejected when scenario references a non-existent land parcel."""
        from app.modules.scenario.models import Scenario

        # Create a scenario without land then directly set a bogus land_id
        scenario_data = _create_scenario(client, name="Broken Land Scenario", land_id=None)
        scenario_row = db_session.query(Scenario).filter(
            Scenario.id == scenario_data["id"]
        ).first()
        assert scenario_row is not None
        scenario_row.land_id = "non-existent-land-parcel-id"
        db_session.commit()

        resp = client.post(
            "/api/v1/concept-options",
            json={"name": "Should Fail", "scenario_id": scenario_data["id"]},
        )
        assert resp.status_code == 422
        body = resp.json()
        # The service raises ValidationError with a message that includes "land parcel"
        assert "land parcel" in body["message"].lower()
        assert body["details"]["land_id"] == "non-existent-land-parcel-id"


# ---------------------------------------------------------------------------
# test_validation_uses_scenario_far
# ---------------------------------------------------------------------------


class TestValidationUsesScenarioFar:
    """Validation should use the FAR inherited from the scenario's land parcel,
    not just the manually entered far_limit."""

    def test_validation_blocked_by_inherited_far(self, client: TestClient):
        """Creating a concept option that violates the inherited land FAR is rejected."""
        # land FAR = 2.5 → max GFA = 5000 * 2.5 = 12500
        parcel = _create_land_parcel(
            client,
            land_area_sqm=5000.0,
            permitted_far=2.5,
            parcel_code="LP-VALFAR-01",
        )
        scenario = _create_scenario(client, name="FAR Validate Scenario", land_id=parcel["id"])

        # gross_floor_area = 15000 > 5000 * 2.5 = 12500 → should be blocked
        _create_concept_option(
            client,
            {
                "name": "FAR Violation",
                "scenario_id": scenario["id"],
                "gross_floor_area": 15000.0,
            },
            expected_status=422,
        )

    def test_validation_passes_within_inherited_far(self, client: TestClient):
        """A concept within the inherited FAR limit is accepted."""
        parcel = _create_land_parcel(
            client,
            land_area_sqm=5000.0,
            permitted_far=2.5,
            parcel_code="LP-VALFAR-02",
        )
        scenario = _create_scenario(client, name="FAR Pass Scenario", land_id=parcel["id"])

        # gross_floor_area = 10000 ≤ 5000 * 2.5 = 12500 → should pass
        option = _create_concept_option(
            client,
            {
                "name": "FAR Valid",
                "scenario_id": scenario["id"],
                "gross_floor_area": 10000.0,
            },
        )

        assert option["name"] == "FAR Valid"

    def test_manually_entered_far_used_when_no_land(self, client: TestClient):
        """When no scenario/land, manually entered far_limit is used for validation."""
        # no scenario — use manual far_limit = 2.0; GFA = 15000 > 5000 * 2.0 = 10000
        _create_concept_option(
            client,
            {
                "name": "Manual FAR Violation",
                "site_area": 5000.0,
                "gross_floor_area": 15000.0,
                "far_limit": 2.0,
            },
            expected_status=422,
        )


# ---------------------------------------------------------------------------
# test_override_far_limit
# ---------------------------------------------------------------------------


class TestOverrideFarLimit:
    """concept_override_far_limit takes priority over the inherited land FAR."""

    def test_override_allows_higher_far_than_land(self, client: TestClient):
        """When concept_override_far_limit > land.permitted_far, override wins."""
        # land FAR = 2.5 → max GFA (no override) = 5000 * 2.5 = 12500
        # override FAR = 4.0 → max GFA with override = 5000 * 4.0 = 20000
        parcel = _create_land_parcel(
            client,
            land_area_sqm=5000.0,
            permitted_far=2.5,
            parcel_code="LP-OVER-FAR-01",
        )
        scenario = _create_scenario(client, name="Override FAR Scenario", land_id=parcel["id"])

        # GFA = 15000 > 12500 (would be blocked by land FAR) but ≤ 20000 (override)
        option = _create_concept_option(
            client,
            {
                "name": "Override FAR High",
                "scenario_id": scenario["id"],
                "gross_floor_area": 15000.0,
                "concept_override_far_limit": 4.0,
            },
        )

        assert option["concept_override_far_limit"] == pytest.approx(4.0)

    def test_override_blocks_when_still_exceeded(self, client: TestClient):
        """Even with override, GFA above the override FAR is rejected."""
        parcel = _create_land_parcel(
            client,
            land_area_sqm=5000.0,
            permitted_far=2.5,
            parcel_code="LP-OVER-FAR-02",
        )
        scenario = _create_scenario(client, name="Override FAR Block", land_id=parcel["id"])

        # override FAR = 3.0 → max GFA = 5000 * 3.0 = 15000; GFA = 20000 → blocked
        _create_concept_option(
            client,
            {
                "name": "Override FAR Exceeded",
                "scenario_id": scenario["id"],
                "gross_floor_area": 20000.0,
                "concept_override_far_limit": 3.0,
            },
            expected_status=422,
        )

    def test_override_stored_on_response(self, client: TestClient):
        """concept_override_far_limit is persisted and returned in the response."""
        option = _create_concept_option(
            client,
            {
                "name": "Store Override FAR",
                "site_area": 5000.0,
                "concept_override_far_limit": 3.5,
            },
        )

        assert option["concept_override_far_limit"] == pytest.approx(3.5)

    def test_no_override_returns_null(self, client: TestClient):
        """concept_override_far_limit is null when not supplied."""
        option = _create_concept_option(client, {"name": "No Override"})

        assert option["concept_override_far_limit"] is None

    def test_override_without_scenario_uses_manual_far(self, client: TestClient):
        """Without a scenario, override takes priority over manual far_limit."""
        # override = 3.0; manual = 2.0 → effective = 3.0 (override wins)
        # GFA = 12000 > 5000 * 2.0 (would fail manual) but ≤ 5000 * 3.0 → passes
        option = _create_concept_option(
            client,
            {
                "name": "Override Beats Manual",
                "site_area": 5000.0,
                "gross_floor_area": 12000.0,
                "far_limit": 2.0,
                "concept_override_far_limit": 3.0,
            },
        )
        assert option["concept_override_far_limit"] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# test_override_density_limit
# ---------------------------------------------------------------------------


class TestOverrideDensityLimit:
    """concept_override_density_limit takes priority over the inherited land density."""

    def test_override_allows_higher_density_than_land(self, client: TestClient):
        """When concept_override_density_limit > land.density_ratio, override wins."""
        # land density = 50 dph; site = 5000 sqm = 0.5 ha → max = 25 units
        # override = 120 dph → max = 60 units
        parcel = _create_land_parcel(
            client,
            land_area_sqm=5000.0,
            density_ratio=50.0,
            permitted_far=None,
            parcel_code="LP-OVER-DENS-01",
        )
        scenario = _create_scenario(
            client, name="Override Density Scenario", land_id=parcel["id"]
        )

        # We can't directly test unit density on concept create (no mix lines at create).
        # Test that the override is persisted and returned.
        option = _create_concept_option(
            client,
            {
                "name": "Override Density High",
                "scenario_id": scenario["id"],
                "concept_override_density_limit": 120.0,
            },
        )

        assert option["concept_override_density_limit"] == pytest.approx(120.0)
        assert option["land_id"] == parcel["id"]

    def test_override_density_stored_on_response(self, client: TestClient):
        """concept_override_density_limit is persisted and returned in the response."""
        option = _create_concept_option(
            client,
            {
                "name": "Store Override Density",
                "site_area": 5000.0,
                "concept_override_density_limit": 90.0,
            },
        )

        assert option["concept_override_density_limit"] == pytest.approx(90.0)

    def test_no_override_density_returns_null(self, client: TestClient):
        """concept_override_density_limit is null when not supplied."""
        option = _create_concept_option(client, {"name": "No Density Override"})

        assert option["concept_override_density_limit"] is None

    def test_override_density_via_patch(self, client: TestClient):
        """concept_override_density_limit can be set via PATCH."""
        option = _create_concept_option(client, {"name": "Patch Density Override"})

        patch_resp = client.patch(
            f"/api/v1/concept-options/{option['id']}",
            json={"concept_override_density_limit": 75.0},
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["concept_override_density_limit"] == pytest.approx(75.0)

    def test_override_far_via_patch(self, client: TestClient):
        """concept_override_far_limit can be set via PATCH."""
        option = _create_concept_option(client, {"name": "Patch FAR Override"})

        patch_resp = client.patch(
            f"/api/v1/concept-options/{option['id']}",
            json={"concept_override_far_limit": 3.0},
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["concept_override_far_limit"] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Summary response includes land integration fields
# ---------------------------------------------------------------------------


class TestSummaryIncludesLandFields:
    """Summary endpoint exposes land_id and override fields."""

    def test_summary_includes_land_id(self, client: TestClient):
        parcel = _create_land_parcel(
            client, land_area_sqm=4000.0, parcel_code="LP-SUM-01"
        )
        scenario = _create_scenario(client, name="Summary Scenario", land_id=parcel["id"])
        option = _create_concept_option(
            client, {"name": "Summary Test", "scenario_id": scenario["id"]}
        )

        summary_resp = client.get(f"/api/v1/concept-options/{option['id']}/summary")
        assert summary_resp.status_code == 200
        summary = summary_resp.json()

        assert summary["land_id"] == parcel["id"]
        assert summary["concept_override_far_limit"] is None
        assert summary["concept_override_density_limit"] is None

    def test_summary_shows_override_values(self, client: TestClient):
        option = _create_concept_option(
            client,
            {
                "name": "Override Summary",
                "concept_override_far_limit": 3.5,
                "concept_override_density_limit": 100.0,
            },
        )

        summary_resp = client.get(f"/api/v1/concept-options/{option['id']}/summary")
        assert summary_resp.status_code == 200
        summary = summary_resp.json()

        assert summary["concept_override_far_limit"] == pytest.approx(3.5)
        assert summary["concept_override_density_limit"] == pytest.approx(100.0)
