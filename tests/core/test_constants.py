"""
tests.core.test_constants

Validates that the unified domain constants layer (app/core/constants/)
imports cleanly, exposes the expected values, and does not alter the
serialised API values that existing modules depend on.
"""

import importlib

# ---------------------------------------------------------------------------
# Import smoke tests — each sub-module must import without error
# ---------------------------------------------------------------------------


def test_constants_package_imports():
    """The top-level constants package must import cleanly."""
    import app.core.constants  # noqa: F401


def test_constants_common_imports():
    mod = importlib.import_module("app.core.constants.common")
    assert hasattr(mod, "STATUS_DRAFT")
    assert hasattr(mod, "STATUS_APPROVED")
    assert hasattr(mod, "STATUS_ARCHIVED")
    assert hasattr(mod, "DEFAULT_PAGE_SKIP")
    assert hasattr(mod, "DEFAULT_PAGE_LIMIT")


def test_constants_currency_imports():
    mod = importlib.import_module("app.core.constants.currency")
    assert hasattr(mod, "CURRENCY_AED")
    assert hasattr(mod, "CURRENCY_JOD")
    assert hasattr(mod, "CURRENCY_USD")
    assert hasattr(mod, "SUPPORTED_CURRENCIES")
    assert hasattr(mod, "DEFAULT_CURRENCY")


def test_constants_units_imports():
    mod = importlib.import_module("app.core.constants.units")
    assert hasattr(mod, "UNIT_SQM")
    assert hasattr(mod, "UNIT_MONTHS")
    assert hasattr(mod, "UNIT_YEARS")


def test_constants_feasibility_imports():
    mod = importlib.import_module("app.core.constants.feasibility")
    assert hasattr(mod, "FeasibilityViabilityStatus")
    assert hasattr(mod, "FeasibilityRiskLevel")
    assert hasattr(mod, "FeasibilityDecision")
    assert hasattr(mod, "FeasibilityScenarioType")


def test_constants_scenario_imports():
    mod = importlib.import_module("app.core.constants.scenario")
    assert hasattr(mod, "ScenarioStatus")
    assert hasattr(mod, "ScenarioSourceType")
    assert hasattr(mod, "VALID_STATUSES")
    assert hasattr(mod, "VALID_SOURCE_TYPES")


def test_constants_land_imports():
    mod = importlib.import_module("app.core.constants.land")
    assert hasattr(mod, "LandParcelStatus")
    assert hasattr(mod, "LandScenarioType")


# ---------------------------------------------------------------------------
# No circular imports when importing all sub-modules together
# ---------------------------------------------------------------------------


def test_no_circular_imports():
    """All constants sub-modules must be importable in one shot."""
    from app.core.constants import common, currency, feasibility, land, scenario, units  # noqa: F401


# ---------------------------------------------------------------------------
# Common constants — value correctness
# ---------------------------------------------------------------------------


class TestCommonConstants:
    def test_status_values(self):
        from app.core.constants.common import STATUS_APPROVED, STATUS_ARCHIVED, STATUS_DRAFT

        assert STATUS_DRAFT == "draft"
        assert STATUS_APPROVED == "approved"
        assert STATUS_ARCHIVED == "archived"

    def test_pagination_defaults(self):
        from app.core.constants.common import DEFAULT_PAGE_LIMIT, DEFAULT_PAGE_SKIP

        assert DEFAULT_PAGE_SKIP == 0
        assert DEFAULT_PAGE_LIMIT == 100

    def test_sort_directions(self):
        from app.core.constants.common import SORT_ASC, SORT_DESC

        assert SORT_ASC == "asc"
        assert SORT_DESC == "desc"


# ---------------------------------------------------------------------------
# Currency constants — value correctness
# ---------------------------------------------------------------------------


class TestCurrencyConstants:
    def test_currency_codes(self):
        from app.core.constants.currency import CURRENCY_AED, CURRENCY_JOD, CURRENCY_USD

        assert CURRENCY_AED == "AED"
        assert CURRENCY_JOD == "JOD"
        assert CURRENCY_USD == "USD"

    def test_default_currency(self):
        from app.core.constants.currency import CURRENCY_AED, DEFAULT_CURRENCY

        assert DEFAULT_CURRENCY == CURRENCY_AED
        assert DEFAULT_CURRENCY == "AED"

    def test_supported_currencies(self):
        from app.core.constants.currency import CURRENCY_AED, CURRENCY_JOD, CURRENCY_USD, SUPPORTED_CURRENCIES

        assert isinstance(SUPPORTED_CURRENCIES, list)
        assert CURRENCY_AED in SUPPORTED_CURRENCIES
        assert CURRENCY_JOD in SUPPORTED_CURRENCIES
        assert CURRENCY_USD in SUPPORTED_CURRENCIES


# ---------------------------------------------------------------------------
# Unit constants — value correctness
# ---------------------------------------------------------------------------


class TestUnitConstants:
    def test_area_unit(self):
        from app.core.constants.units import UNIT_SQM

        assert UNIT_SQM == "sqm"

    def test_period_units(self):
        from app.core.constants.units import UNIT_MONTHS, UNIT_YEARS

        assert UNIT_MONTHS == "months"
        assert UNIT_YEARS == "years"

    def test_linear_unit(self):
        from app.core.constants.units import UNIT_METERS

        assert UNIT_METERS == "m"


# ---------------------------------------------------------------------------
# Feasibility constants — enum values must be backward-compatible
# ---------------------------------------------------------------------------


class TestFeasibilityConstants:
    def test_viability_status_values(self):
        from app.core.constants.feasibility import (
            VIABILITY_MARGINAL,
            VIABILITY_NOT_VIABLE,
            VIABILITY_VIABLE,
            FeasibilityViabilityStatus,
        )

        assert VIABILITY_VIABLE == "VIABLE"
        assert VIABILITY_MARGINAL == "MARGINAL"
        assert VIABILITY_NOT_VIABLE == "NOT_VIABLE"
        # Enum member values must match the convenience aliases
        assert FeasibilityViabilityStatus.VIABLE.value == VIABILITY_VIABLE
        assert FeasibilityViabilityStatus.MARGINAL.value == VIABILITY_MARGINAL
        assert FeasibilityViabilityStatus.NOT_VIABLE.value == VIABILITY_NOT_VIABLE

    def test_risk_level_values(self):
        from app.core.constants.feasibility import RISK_HIGH, RISK_LOW, RISK_MEDIUM, FeasibilityRiskLevel

        assert RISK_LOW == "LOW"
        assert RISK_MEDIUM == "MEDIUM"
        assert RISK_HIGH == "HIGH"
        assert FeasibilityRiskLevel.LOW.value == RISK_LOW
        assert FeasibilityRiskLevel.HIGH.value == RISK_HIGH

    def test_decision_values(self):
        from app.core.constants.feasibility import (
            DECISION_MARGINAL,
            DECISION_NOT_VIABLE,
            DECISION_VIABLE,
            FeasibilityDecision,
        )

        assert DECISION_VIABLE == "VIABLE"
        assert DECISION_MARGINAL == "MARGINAL"
        assert DECISION_NOT_VIABLE == "NOT_VIABLE"
        assert FeasibilityDecision.VIABLE.value == DECISION_VIABLE

    def test_scenario_type_values(self):
        from app.core.constants.feasibility import (
            DEFAULT_SCENARIO_TYPE,
            SCENARIO_TYPE_BASE,
            SCENARIO_TYPE_DOWNSIDE,
            SCENARIO_TYPE_INVESTOR,
            SCENARIO_TYPE_UPSIDE,
            FeasibilityScenarioType,
        )

        assert SCENARIO_TYPE_BASE == "base"
        assert SCENARIO_TYPE_UPSIDE == "upside"
        assert SCENARIO_TYPE_DOWNSIDE == "downside"
        assert SCENARIO_TYPE_INVESTOR == "investor"
        assert DEFAULT_SCENARIO_TYPE == SCENARIO_TYPE_BASE
        assert FeasibilityScenarioType.BASE.value == SCENARIO_TYPE_BASE

    def test_enums_are_reexported_from_shared(self):
        """Constants layer must re-export the same enum classes as the shared layer."""
        from app.core.constants.feasibility import (
            FeasibilityDecision as ConstDecision,
            FeasibilityRiskLevel as ConstRisk,
            FeasibilityScenarioType as ConstScenType,
            FeasibilityViabilityStatus as ConstViab,
        )
        from app.shared.enums.finance import (
            FeasibilityDecision as SharedDecision,
            FeasibilityRiskLevel as SharedRisk,
            FeasibilityScenarioType as SharedScenType,
            FeasibilityViabilityStatus as SharedViab,
        )

        assert ConstViab is SharedViab
        assert ConstRisk is SharedRisk
        assert ConstDecision is SharedDecision
        assert ConstScenType is SharedScenType


# ---------------------------------------------------------------------------
# Scenario constants — value correctness
# ---------------------------------------------------------------------------


class TestScenarioConstants:
    def test_status_enum_values(self):
        from app.core.constants.scenario import ScenarioStatus

        assert ScenarioStatus.DRAFT.value == "draft"
        assert ScenarioStatus.APPROVED.value == "approved"
        assert ScenarioStatus.ARCHIVED.value == "archived"

    def test_source_type_enum_values(self):
        from app.core.constants.scenario import ScenarioSourceType

        assert ScenarioSourceType.LAND.value == "land"
        assert ScenarioSourceType.FEASIBILITY.value == "feasibility"
        assert ScenarioSourceType.CONCEPT.value == "concept"
        assert ScenarioSourceType.GENERAL.value == "general"

    def test_valid_statuses_set(self):
        from app.core.constants.scenario import VALID_STATUSES

        assert "draft" in VALID_STATUSES
        assert "approved" in VALID_STATUSES
        assert "archived" in VALID_STATUSES

    def test_valid_source_types_set(self):
        from app.core.constants.scenario import VALID_SOURCE_TYPES

        assert "land" in VALID_SOURCE_TYPES
        assert "feasibility" in VALID_SOURCE_TYPES
        assert "concept" in VALID_SOURCE_TYPES
        assert "general" in VALID_SOURCE_TYPES

    def test_defaults(self):
        from app.core.constants.scenario import (
            DEFAULT_SCENARIO_SOURCE_TYPE,
            DEFAULT_SCENARIO_STATUS,
            ScenarioSourceType,
            ScenarioStatus,
        )

        assert DEFAULT_SCENARIO_STATUS == ScenarioStatus.DRAFT.value
        assert DEFAULT_SCENARIO_SOURCE_TYPE == ScenarioSourceType.FEASIBILITY.value


# ---------------------------------------------------------------------------
# Land constants — value correctness and backward-compatibility
# ---------------------------------------------------------------------------


class TestLandConstants:
    def test_parcel_status_values(self):
        from app.core.constants.land import (
            PARCEL_STATUS_APPROVED,
            PARCEL_STATUS_ARCHIVED,
            PARCEL_STATUS_DRAFT,
            PARCEL_STATUS_UNDER_REVIEW,
            LandParcelStatus,
        )

        assert PARCEL_STATUS_DRAFT == "draft"
        assert PARCEL_STATUS_UNDER_REVIEW == "under_review"
        assert PARCEL_STATUS_APPROVED == "approved"
        assert PARCEL_STATUS_ARCHIVED == "archived"
        assert LandParcelStatus.DRAFT.value == PARCEL_STATUS_DRAFT

    def test_land_scenario_type_values(self):
        from app.core.constants.land import (
            LAND_SCENARIO_BASE,
            LAND_SCENARIO_DOWNSIDE,
            LAND_SCENARIO_INVESTOR,
            LAND_SCENARIO_UPSIDE,
            LandScenarioType,
        )

        assert LAND_SCENARIO_BASE == "base"
        assert LAND_SCENARIO_UPSIDE == "upside"
        assert LAND_SCENARIO_DOWNSIDE == "downside"
        assert LAND_SCENARIO_INVESTOR == "investor"
        assert LandScenarioType.BASE.value == LAND_SCENARIO_BASE

    def test_defaults(self):
        from app.core.constants.land import (
            DEFAULT_LAND_SCENARIO_TYPE,
            DEFAULT_PARCEL_STATUS,
            LAND_SCENARIO_BASE,
            PARCEL_STATUS_DRAFT,
        )

        assert DEFAULT_PARCEL_STATUS == PARCEL_STATUS_DRAFT
        assert DEFAULT_LAND_SCENARIO_TYPE == LAND_SCENARIO_BASE

    def test_enums_are_reexported_from_shared(self):
        from app.core.constants.land import LandParcelStatus as ConstParcel, LandScenarioType as ConstScen
        from app.shared.enums.project import LandParcelStatus as SharedParcel, LandScenarioType as SharedScen

        assert ConstParcel is SharedParcel
        assert ConstScen is SharedScen
