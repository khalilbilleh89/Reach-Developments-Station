"""
Dedicated pure-engine tests for the Concept Design validation module.

Validates the deterministic violation logic and violation structure produced by
the pure validation functions — no database or HTTP layer involved.

Coverage
--------
FAR rule
  - valid: at limit, below limit
  - invalid: GFA exceeds limit
  - skip: site_area absent, gross_floor_area absent, far_limit absent
  - skip: site_area zero, far_limit zero
  - violation structure: rule, message, details keys and values

Efficiency rule
  - valid: exactly 100 %, below 100 %
  - invalid: sellable > gfa
  - skip: sellable absent, gfa absent, gfa zero
  - violation structure: rule, message, details keys and values

Density rule
  - valid: at limit, below limit
  - invalid: unit_count exceeds limit
  - skip: unit_count absent, site_area absent, density_limit absent
  - skip: site_area zero, density_limit zero
  - violation structure: rule, message, details keys and values

run_zoning_validation
  - no violations when all inputs valid
  - FAR-only violation
  - efficiency-only violation
  - density-only violation
  - all three violations simultaneously
  - no violations when all inputs absent (nothing to check)
  - returned list is in declaration order: FAR → efficiency → density

PR-CONCEPT-061
"""

from __future__ import annotations

import pytest

from app.modules.concept_design.validation import (
    ConceptZoningViolation,
    run_zoning_validation,
    validate_density_rule,
    validate_efficiency_rule,
    validate_far_rule,
)


# ===========================================================================
# FAR rule — pure engine
# ===========================================================================


class TestFarRuleValid:
    def test_at_exact_limit_passes(self):
        # GFA == site_area * far_limit → exactly at limit, no violation
        assert validate_far_rule(5000.0, 10000.0, 2.0) is None

    def test_below_limit_passes(self):
        assert validate_far_rule(5000.0, 8000.0, 2.0) is None

    def test_far_limit_of_1_at_exact_gfa_passes(self):
        # FAR 1.0: GFA must not exceed site_area
        assert validate_far_rule(3000.0, 3000.0, 1.0) is None


class TestFarRuleViolation:
    def test_gfa_exceeds_limit_returns_violation(self):
        # max = 5000 * 2.0 = 10000; GFA = 12000 > 10000
        violation = validate_far_rule(5000.0, 12000.0, 2.0)
        assert violation is not None

    def test_violation_has_correct_rule_name(self):
        violation = validate_far_rule(5000.0, 12000.0, 2.0)
        assert violation.rule == "FAR_EXCEEDED"

    def test_violation_message_contains_gfa(self):
        violation = validate_far_rule(5000.0, 12000.0, 2.0)
        assert "12,000" in violation.message

    def test_violation_message_contains_max_gfa(self):
        violation = validate_far_rule(5000.0, 12000.0, 2.0)
        assert "10,000" in violation.message

    def test_violation_details_contains_required_keys(self):
        violation = validate_far_rule(5000.0, 12000.0, 2.0)
        assert "gross_floor_area" in violation.details
        assert "site_area" in violation.details
        assert "far_limit" in violation.details
        assert "max_permitted_gfa" in violation.details

    def test_violation_details_max_permitted_gfa_value(self):
        violation = validate_far_rule(5000.0, 12000.0, 2.0)
        assert violation.details["max_permitted_gfa"] == pytest.approx(10000.0)

    def test_violation_details_preserves_input_values(self):
        violation = validate_far_rule(5000.0, 12000.0, 2.0)
        assert violation.details["gross_floor_area"] == pytest.approx(12000.0)
        assert violation.details["site_area"] == pytest.approx(5000.0)
        assert violation.details["far_limit"] == pytest.approx(2.0)

    def test_violation_is_dataclass_instance(self):
        violation = validate_far_rule(5000.0, 12000.0, 2.0)
        assert isinstance(violation, ConceptZoningViolation)


class TestFarRuleSkips:
    def test_skipped_when_site_area_absent(self):
        assert validate_far_rule(None, 12000.0, 2.0) is None

    def test_skipped_when_gfa_absent(self):
        assert validate_far_rule(5000.0, None, 2.0) is None

    def test_skipped_when_far_limit_absent(self):
        assert validate_far_rule(5000.0, 12000.0, None) is None

    def test_skipped_when_site_area_zero(self):
        assert validate_far_rule(0.0, 12000.0, 2.0) is None

    def test_skipped_when_far_limit_zero(self):
        assert validate_far_rule(5000.0, 12000.0, 0.0) is None

    def test_skipped_when_all_absent(self):
        assert validate_far_rule(None, None, None) is None


# ===========================================================================
# Efficiency rule — pure engine
# ===========================================================================


class TestEfficiencyRuleValid:
    def test_exactly_100_pct_passes(self):
        assert validate_efficiency_rule(10000.0, 10000.0) is None

    def test_below_100_pct_passes(self):
        assert validate_efficiency_rule(7500.0, 10000.0) is None

    def test_nearly_100_pct_passes(self):
        assert validate_efficiency_rule(9999.99, 10000.0) is None


class TestEfficiencyRuleViolation:
    def test_sellable_exceeds_gfa_returns_violation(self):
        violation = validate_efficiency_rule(12000.0, 10000.0)
        assert violation is not None

    def test_violation_has_correct_rule_name(self):
        violation = validate_efficiency_rule(12000.0, 10000.0)
        assert violation.rule == "EFFICIENCY_IMPOSSIBLE"

    def test_violation_message_contains_sellable_area(self):
        violation = validate_efficiency_rule(12000.0, 10000.0)
        assert "12,000" in violation.message

    def test_violation_message_contains_gfa(self):
        violation = validate_efficiency_rule(12000.0, 10000.0)
        assert "10,000" in violation.message

    def test_violation_details_contains_required_keys(self):
        violation = validate_efficiency_rule(12000.0, 10000.0)
        assert "sellable_area" in violation.details
        assert "gross_floor_area" in violation.details
        assert "efficiency_ratio" in violation.details

    def test_violation_details_efficiency_ratio_value(self):
        violation = validate_efficiency_rule(12000.0, 10000.0)
        assert violation.details["efficiency_ratio"] == pytest.approx(1.2, rel=1e-4)

    def test_violation_details_preserves_input_values(self):
        violation = validate_efficiency_rule(12000.0, 10000.0)
        assert violation.details["sellable_area"] == pytest.approx(12000.0)
        assert violation.details["gross_floor_area"] == pytest.approx(10000.0)

    def test_violation_is_dataclass_instance(self):
        violation = validate_efficiency_rule(12000.0, 10000.0)
        assert isinstance(violation, ConceptZoningViolation)


class TestEfficiencyRuleSkips:
    def test_skipped_when_sellable_absent(self):
        assert validate_efficiency_rule(None, 10000.0) is None

    def test_skipped_when_gfa_absent(self):
        assert validate_efficiency_rule(7500.0, None) is None

    def test_skipped_when_gfa_zero(self):
        assert validate_efficiency_rule(7500.0, 0.0) is None

    def test_skipped_when_both_absent(self):
        assert validate_efficiency_rule(None, None) is None


# ===========================================================================
# Density rule — pure engine
# ===========================================================================


class TestDensityRuleValid:
    def test_at_exact_limit_passes(self):
        # site = 10000 sqm = 1 ha; density = 50 dph → max = 50
        assert validate_density_rule(50, 10000.0, 50.0) is None

    def test_below_limit_passes(self):
        assert validate_density_rule(40, 10000.0, 50.0) is None

    def test_single_unit_low_density_passes(self):
        # site = 1 ha; density = 10 dph → max = 10; 1 unit < 10
        assert validate_density_rule(1, 10000.0, 10.0) is None


class TestDensityRuleViolation:
    def test_unit_count_exceeds_limit_returns_violation(self):
        # site = 5000 sqm = 0.5 ha; density = 50 dph → max = 25; 30 > 25
        violation = validate_density_rule(30, 5000.0, 50.0)
        assert violation is not None

    def test_violation_has_correct_rule_name(self):
        violation = validate_density_rule(30, 5000.0, 50.0)
        assert violation.rule == "DENSITY_EXCEEDED"

    def test_violation_message_contains_unit_count(self):
        violation = validate_density_rule(30, 5000.0, 50.0)
        assert "30" in violation.message

    def test_violation_message_contains_max_units(self):
        violation = validate_density_rule(30, 5000.0, 50.0)
        # max = 50 * 0.5 = 25.00
        assert "25.00" in violation.message

    def test_violation_message_contains_density_limit(self):
        violation = validate_density_rule(30, 5000.0, 50.0)
        assert "50.00 dph" in violation.message

    def test_violation_details_contains_required_keys(self):
        violation = validate_density_rule(30, 5000.0, 50.0)
        assert "unit_count" in violation.details
        assert "site_area" in violation.details
        assert "site_area_ha" in violation.details
        assert "density_limit_dph" in violation.details
        assert "max_permitted_units" in violation.details

    def test_violation_details_unit_count_value(self):
        violation = validate_density_rule(30, 5000.0, 50.0)
        assert violation.details["unit_count"] == 30

    def test_violation_details_max_permitted_units_value(self):
        violation = validate_density_rule(30, 5000.0, 50.0)
        assert violation.details["max_permitted_units"] == pytest.approx(25.0)

    def test_violation_details_site_area_ha_value(self):
        violation = validate_density_rule(30, 5000.0, 50.0)
        assert violation.details["site_area_ha"] == pytest.approx(0.5, rel=1e-4)

    def test_violation_is_dataclass_instance(self):
        violation = validate_density_rule(30, 5000.0, 50.0)
        assert isinstance(violation, ConceptZoningViolation)


class TestDensityRuleSkips:
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

    def test_skipped_when_all_absent(self):
        assert validate_density_rule(None, None, None) is None


# ===========================================================================
# run_zoning_validation — orchestration
# ===========================================================================


class TestRunZoningValidationOrchestration:
    def test_all_inputs_valid_returns_empty_list(self):
        violations = run_zoning_validation(
            site_area=5000.0,
            gross_floor_area=8000.0,
            far_limit=2.0,
            density_limit=50.0,
            sellable_area=7000.0,
            unit_count=20,
        )
        assert violations == []

    def test_all_absent_returns_empty_list(self):
        violations = run_zoning_validation(
            site_area=None,
            gross_floor_area=None,
            far_limit=None,
            density_limit=None,
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
            sellable_area=12000.0,
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

    def test_all_three_violations_simultaneously(self):
        violations = run_zoning_validation(
            site_area=5000.0,
            gross_floor_area=15000.0,
            far_limit=2.0,
            density_limit=50.0,
            sellable_area=16000.0,
            unit_count=30,
        )
        rules = {v.rule for v in violations}
        assert "FAR_EXCEEDED" in rules
        assert "EFFICIENCY_IMPOSSIBLE" in rules
        assert "DENSITY_EXCEEDED" in rules
        assert len(violations) == 3

    def test_violations_returned_in_declaration_order(self):
        """Violation list order is: FAR → efficiency → density."""
        violations = run_zoning_validation(
            site_area=5000.0,
            gross_floor_area=15000.0,
            far_limit=2.0,
            density_limit=50.0,
            sellable_area=16000.0,
            unit_count=30,
        )
        assert violations[0].rule == "FAR_EXCEEDED"
        assert violations[1].rule == "EFFICIENCY_IMPOSSIBLE"
        assert violations[2].rule == "DENSITY_EXCEEDED"

    def test_returns_list_type(self):
        violations = run_zoning_validation(
            site_area=None,
            gross_floor_area=None,
            far_limit=None,
            density_limit=None,
        )
        assert isinstance(violations, list)

    def test_each_violation_has_rule_message_details(self):
        violations = run_zoning_validation(
            site_area=5000.0,
            gross_floor_area=15000.0,
            far_limit=2.0,
            density_limit=None,
        )
        assert len(violations) == 1
        v = violations[0]
        assert hasattr(v, "rule")
        assert hasattr(v, "message")
        assert hasattr(v, "details")
        assert isinstance(v.rule, str)
        assert isinstance(v.message, str)
        assert isinstance(v.details, dict)

    def test_partial_inputs_far_and_density_only(self):
        """When sellable_area absent, efficiency rule is skipped."""
        violations = run_zoning_validation(
            site_area=5000.0,
            gross_floor_area=15000.0,
            far_limit=2.0,
            density_limit=50.0,
            sellable_area=None,
            unit_count=30,
        )
        rules = {v.rule for v in violations}
        assert "FAR_EXCEEDED" in rules
        assert "DENSITY_EXCEEDED" in rules
        assert "EFFICIENCY_IMPOSSIBLE" not in rules
