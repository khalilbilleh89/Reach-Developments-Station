"""
tests/architecture/test_frontend_integration_surface.py

PR-F1: Frontend Integration Surface Tests.

Validates the frontend/backend integration contract to prevent drift:

  1. Frontend API wrappers exist for all 8 core domains.
  2. No calls to deprecated /registration/* routes in any wrapper.
  3. All critical API endpoints exist in the OpenAPI schema.
  4. Registry page uses the live API (not static demo data).
  5. Settings page is documented as intentional demo where applicable.
  6. Type definition files exist for every domain wrapper.

These are static-analysis and schema-inspection tests.
They do not start an external server.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, _API_PREFIX

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[2]
FRONTEND_LIB_DIR = _REPO_ROOT / "frontend" / "src" / "lib"
FRONTEND_APP_DIR = _REPO_ROOT / "frontend" / "src" / "app"

# ---------------------------------------------------------------------------
# Canonical wrapper and type files for all 8 core domains
# ---------------------------------------------------------------------------

REQUIRED_DOMAIN_API_WRAPPERS = [
    "projects-api.ts",
    "sales-api.ts",
    "payment-plans-api.ts",
    "finance-dashboard-api.ts",
    "construction-api.ts",
    "registry-api.ts",
    "settings-api.ts",
]

REQUIRED_DOMAIN_TYPE_FILES = [
    "projects-types.ts",
    "sales-types.ts",
    "payment-plans-types.ts",
    "finance-dashboard-types.ts",
    "construction-types.ts",
    "registry-types.ts",
    "settings-types.ts",
]

# Deprecated paths that must not appear in any frontend API wrapper
FORBIDDEN_LEGACY_PATHS = [
    r"/registration/cases",
    r"/registration/projects",
    r"api/v1/registration/",
]

# Critical (method, path) pairs that must exist in the OpenAPI schema
CRITICAL_ENDPOINT_PAIRS = [
    # Projects domain
    ("GET", f"{_API_PREFIX}/projects"),
    ("POST", f"{_API_PREFIX}/projects"),
    ("GET", f"{_API_PREFIX}/projects/{{project_id}}"),
    ("PATCH", f"{_API_PREFIX}/projects/{{project_id}}"),
    ("GET", f"{_API_PREFIX}/projects/{{project_id}}/summary"),
    # Sales domain
    ("GET", f"{_API_PREFIX}/sales/contracts"),
    ("POST", f"{_API_PREFIX}/sales/contracts"),
    ("GET", f"{_API_PREFIX}/sales/contracts/{{contract_id}}"),
    ("POST", f"{_API_PREFIX}/sales/buyers"),
    ("GET", f"{_API_PREFIX}/sales/buyers/{{buyer_id}}"),
    # Payment Plans domain
    ("POST", f"{_API_PREFIX}/payment-plans"),
    ("GET", f"{_API_PREFIX}/payment-plans/contracts/{{contract_id}}/schedule"),
    ("GET", f"{_API_PREFIX}/payment-plans/contracts/{{contract_id}}/installments"),
    # Finance domain
    ("GET", f"{_API_PREFIX}/finance/projects/{{project_id}}/summary"),
    # Registry domain (canonical /registry/* — NOT /registration/*)
    ("POST", f"{_API_PREFIX}/registry/cases"),
    ("GET", f"{_API_PREFIX}/registry/cases/{{case_id}}"),
    ("GET", f"{_API_PREFIX}/registry/projects/{{project_id}}/cases"),
    ("GET", f"{_API_PREFIX}/registry/projects/{{project_id}}/summary"),
    ("GET", f"{_API_PREFIX}/registry/cases/{{case_id}}/milestones"),
    ("GET", f"{_API_PREFIX}/registry/cases/{{case_id}}/documents"),
    # Construction domain
    ("GET", f"{_API_PREFIX}/construction/scopes"),
    ("POST", f"{_API_PREFIX}/construction/scopes"),
    ("POST", f"{_API_PREFIX}/construction/milestones"),
    ("POST", f"{_API_PREFIX}/construction/milestones/{{milestone_id}}/progress-updates"),
    ("GET", f"{_API_PREFIX}/construction/projects/{{project_id}}/dashboard"),
    # Settings domain
    ("GET", f"{_API_PREFIX}/settings/pricing-policies"),
    ("POST", f"{_API_PREFIX}/settings/pricing-policies"),
    ("GET", f"{_API_PREFIX}/settings/commission-policies"),
    ("POST", f"{_API_PREFIX}/settings/commission-policies"),
    ("GET", f"{_API_PREFIX}/settings/project-templates"),
    ("POST", f"{_API_PREFIX}/settings/project-templates"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_lib_file(filename: str) -> str:
    """Return the text of a frontend lib file (empty string if not found)."""
    path = FRONTEND_LIB_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_page_file(relative_path: str) -> str:
    """Return the text of a frontend app page (empty string if not found)."""
    path = FRONTEND_APP_DIR / relative_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


# ---------------------------------------------------------------------------
# Shared OpenAPI fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def openapi_schema():
    """Return the OpenAPI schema from the FastAPI application."""
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200, "OpenAPI schema failed to generate"
    return response.json()


# ---------------------------------------------------------------------------
# Test class: required frontend files exist
# ---------------------------------------------------------------------------


class TestRequiredFrontendFilesExist:
    """All domain API wrapper and type definition files must be present."""

    def test_all_domain_api_wrappers_exist(self):
        """Every domain must have an API wrapper file in frontend/src/lib/."""
        missing = [f for f in REQUIRED_DOMAIN_API_WRAPPERS if not (FRONTEND_LIB_DIR / f).exists()]
        assert not missing, (
            "Missing domain API wrapper files in frontend/src/lib/:\n"
            + "\n".join(f"  {f}" for f in missing)
        )

    def test_all_domain_type_files_exist(self):
        """Every domain must have a TypeScript type definition file in frontend/src/lib/."""
        missing = [f for f in REQUIRED_DOMAIN_TYPE_FILES if not (FRONTEND_LIB_DIR / f).exists()]
        assert not missing, (
            "Missing domain type definition files in frontend/src/lib/:\n"
            + "\n".join(f"  {f}" for f in missing)
        )

    def test_api_client_base_exists(self):
        """Base HTTP client (api-client.ts) must exist in frontend/src/lib/."""
        assert (FRONTEND_LIB_DIR / "api-client.ts").exists(), (
            "frontend/src/lib/api-client.ts is missing — the base HTTP client is required."
        )


# ---------------------------------------------------------------------------
# Test class: no deprecated /registration/* routes in wrappers
# ---------------------------------------------------------------------------


class TestNoDeprecatedRegistrationRoutes:
    """Frontend wrappers must use /registry/* canonical routes, not /registration/*."""

    def test_registry_wrapper_free_of_deprecated_paths(self):
        """registry-api.ts must not contain /registration/* paths."""
        content = _read_lib_file("registry-api.ts")
        assert content, "registry-api.ts is missing or empty"
        for pattern in FORBIDDEN_LEGACY_PATHS:
            assert not re.search(pattern, content), (
                f"registry-api.ts contains deprecated path pattern '{pattern}'. "
                "Use /registry/* canonical routes instead."
            )

    def test_all_wrappers_free_of_deprecated_registration_paths(self):
        """No domain API wrapper should call /registration/* routes."""
        violations = []
        for api_file in REQUIRED_DOMAIN_API_WRAPPERS:
            content = _read_lib_file(api_file)
            if not content:
                continue
            for pattern in FORBIDDEN_LEGACY_PATHS:
                if re.search(pattern, content):
                    violations.append(f"{api_file}: found deprecated pattern '{pattern}'")
        assert not violations, (
            "Deprecated /registration/* paths found in frontend wrappers:\n"
            + "\n".join(f"  {v}" for v in violations)
        )


# ---------------------------------------------------------------------------
# Test class: all critical endpoints exist in OpenAPI schema
# ---------------------------------------------------------------------------


class TestCriticalEndpointsInSchema:
    """All critical API endpoint (method, path) pairs must be in the OpenAPI schema."""

    def test_all_critical_endpoints_present(self, openapi_schema):
        """Every (method, path) pair listed in CRITICAL_ENDPOINT_PAIRS must exist."""
        schema_paths = openapi_schema.get("paths", {})
        missing = []
        for method, path in CRITICAL_ENDPOINT_PAIRS:
            if path not in schema_paths:
                missing.append(f"{method} {path}  [path absent from schema]")
                continue
            path_item = schema_paths[path]
            if method.lower() not in path_item:
                missing.append(f"{method} {path}  [method not found for this path]")

        assert not missing, (
            "Critical API endpoints missing from OpenAPI schema:\n"
            + "\n".join(f"  {m}" for m in missing)
        )

    def test_registry_canonical_paths_in_schema(self, openapi_schema):
        """Canonical /registry/* paths must be in the OpenAPI schema (not /registration/*)."""
        schema_paths = openapi_schema.get("paths", {})
        required = [
            f"{_API_PREFIX}/registry/cases",
            f"{_API_PREFIX}/registry/cases/{{case_id}}",
            f"{_API_PREFIX}/registry/projects/{{project_id}}/cases",
            f"{_API_PREFIX}/registry/projects/{{project_id}}/summary",
        ]
        missing = [p for p in required if p not in schema_paths]
        assert not missing, (
            "Canonical /registry/* paths missing from OpenAPI schema:\n"
            + "\n".join(f"  {p}" for p in missing)
        )


# ---------------------------------------------------------------------------
# Test class: registry wrapper calls canonical /registry/* routes
# ---------------------------------------------------------------------------


class TestRegistryWrapperUsesCanonicalRoutes:
    """registry-api.ts must call /registry/* routes."""

    def test_registry_wrapper_calls_registry_cases(self):
        """registry-api.ts must contain /registry/cases."""
        content = _read_lib_file("registry-api.ts")
        assert content, "registry-api.ts is missing or empty"
        assert "/registry/cases" in content, (
            "registry-api.ts does not reference /registry/cases — "
            "it must call the canonical backend route."
        )

    def test_registry_wrapper_calls_project_scoped_endpoint(self):
        """registry-api.ts must contain /registry/projects/ (project-scoped listing)."""
        content = _read_lib_file("registry-api.ts")
        assert content, "registry-api.ts is missing or empty"
        assert "/registry/projects/" in content, (
            "registry-api.ts does not wrap the project-scoped /registry/projects/ endpoint."
        )


# ---------------------------------------------------------------------------
# Test class: registry page uses live API
# ---------------------------------------------------------------------------


class TestRegistryPageUsesLiveApi:
    """The registry page must call the live backend API, not static demo data."""

    def test_registry_page_imports_registry_api(self):
        """(protected)/registry/page.tsx must import from registry-api.ts."""
        content = _read_page_file("(protected)/registry/page.tsx")
        assert content, "(protected)/registry/page.tsx not found"
        assert "registry-api" in content, (
            "Registry page does not import from registry-api.ts. "
            "It should call the live /registry/* backend endpoints."
        )

    def test_registry_page_does_not_use_demo_registry_cases(self):
        """(protected)/registry/page.tsx must not reference demoRegistryCases."""
        content = _read_page_file("(protected)/registry/page.tsx")
        assert content, "(protected)/registry/page.tsx not found"
        assert "demoRegistryCases" not in content, (
            "Registry page still uses demoRegistryCases from demo-data.ts. "
            "Registry backend is fully implemented — use registry-api.ts instead."
        )


# ---------------------------------------------------------------------------
# Test class: settings page documents demo sections
# ---------------------------------------------------------------------------


class TestSettingsPageDocumentsDemoSections:
    """Settings page must document which sections use demo vs. live data."""

    def test_settings_page_has_intentional_demo_annotation(self):
        """(protected)/settings/page.tsx must annotate intentional demo sections."""
        content = _read_page_file("(protected)/settings/page.tsx")
        assert content, "(protected)/settings/page.tsx not found"
        has_annotation = (
            "INTENTIONAL DEMO" in content
            or "intentional" in content.lower()
            or "demo" in content.lower()
        )
        assert has_annotation, (
            "Settings page has no annotation documenting demo vs. live data sections. "
            "Add a comment clarifying which sections are intentional demo data."
        )


# ---------------------------------------------------------------------------
# Test class: construction wrapper completeness
# ---------------------------------------------------------------------------


class TestConstructionWrapperCompleteness:
    """construction-api.ts must cover progress updates and the dashboard endpoint."""

    def test_construction_wrapper_includes_progress_updates(self):
        """construction-api.ts must wrap the progress-updates endpoints."""
        content = _read_lib_file("construction-api.ts")
        assert content, "construction-api.ts is missing or empty"
        assert "progress-updates" in content, (
            "construction-api.ts does not wrap progress-update endpoints."
        )

    def test_construction_wrapper_includes_dashboard(self):
        """construction-api.ts must wrap the project dashboard endpoint."""
        content = _read_lib_file("construction-api.ts")
        assert content, "construction-api.ts is missing or empty"
        assert "/construction/projects/" in content, (
            "construction-api.ts does not wrap the /construction/projects/ dashboard endpoint."
        )


# ---------------------------------------------------------------------------
# Test class: settings wrapper completeness
# ---------------------------------------------------------------------------


class TestSettingsWrapperCompleteness:
    """settings-api.ts must expose wrappers for all three settings resources."""

    def test_settings_wraps_pricing_policies(self):
        """settings-api.ts must wrap /settings/pricing-policies."""
        content = _read_lib_file("settings-api.ts")
        assert content, "settings-api.ts is missing or empty"
        assert "/settings/pricing-policies" in content, (
            "settings-api.ts does not wrap /settings/pricing-policies."
        )

    def test_settings_wraps_commission_policies(self):
        """settings-api.ts must wrap /settings/commission-policies."""
        content = _read_lib_file("settings-api.ts")
        assert content, "settings-api.ts is missing or empty"
        assert "/settings/commission-policies" in content, (
            "settings-api.ts does not wrap /settings/commission-policies."
        )

    def test_settings_wraps_project_templates(self):
        """settings-api.ts must wrap /settings/project-templates."""
        content = _read_lib_file("settings-api.ts")
        assert content, "settings-api.ts is missing or empty"
        assert "/settings/project-templates" in content, (
            "settings-api.ts does not wrap /settings/project-templates."
        )
