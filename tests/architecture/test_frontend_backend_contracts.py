"""
tests/architecture/test_frontend_backend_contracts.py

PR-E5: Frontend/Backend Contract Audit Tests.

Validates that:
  1. All documented frontend API wrapper paths map to real backend routes.
  2. No known legacy /registration/* paths remain in frontend wrappers.
  3. Critical pages do not reference removed domain names (e.g. registration).
  4. Critical frontend API wrapper method/path combinations are present in
     the backend OpenAPI schema for all 8 core domains.
  5. The /registry/* canonical routes are the active routes (not /registration/*).

These are lightweight static-analysis and schema-inspection tests.
They complement (not replace) smoke tests and integration tests.

All tests parse the FastAPI OpenAPI schema or scan frontend source files
without starting an external server.
"""

import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, _API_PREFIX

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRONTEND_LIB_DIR = Path(__file__).parents[2] / "frontend" / "src" / "lib"
FRONTEND_APP_DIR = Path(__file__).parents[2] / "frontend" / "src" / "app"

# Canonical frontend API wrapper files that MUST exist for contract correctness.
REQUIRED_API_WRAPPER_FILES = [
    "projects-api.ts",
    "sales-api.ts",
    "payment-plans-api.ts",
    "finance-dashboard-api.ts",
    "construction-api.ts",
    "registry-api.ts",   # PR-E5: was missing, now created
    "settings-api.ts",   # PR-E5: was missing, now created
]

# Canonical frontend type definition files that MUST exist.
REQUIRED_TYPE_FILES = [
    "projects-types.ts",
    "sales-types.ts",
    "payment-plans-types.ts",
    "finance-dashboard-types.ts",
    "construction-types.ts",
    "registry-types.ts",  # PR-E5: was missing, now created
    "settings-types.ts",  # PR-E5: was missing, now created
]

# Legacy paths that must NOT appear as primary calls in frontend wrappers.
# The registry frontend should call /registry/... not /registration/...
FORBIDDEN_LEGACY_PATTERNS = [
    r"/registration/cases",
    r"/registration/projects",
]

# (method, path_pattern) pairs that must exist in the backend OpenAPI schema.
# Path patterns use {param} placeholders matching the OpenAPI convention.
CRITICAL_FRONTEND_CONTRACT_PAIRS = [
    # Projects
    ("GET", "/api/v1/projects"),
    ("POST", "/api/v1/projects"),
    ("GET", "/api/v1/projects/{project_id}"),
    ("PATCH", "/api/v1/projects/{project_id}"),
    ("DELETE", "/api/v1/projects/{project_id}"),
    ("POST", "/api/v1/projects/{project_id}/archive"),
    ("GET", "/api/v1/projects/{project_id}/summary"),
    # Sales
    ("GET", "/api/v1/sales/contracts"),
    ("POST", "/api/v1/sales/contracts"),
    ("GET", "/api/v1/sales/contracts/{contract_id}"),
    ("PATCH", "/api/v1/sales/contracts/{contract_id}"),
    ("POST", "/api/v1/sales/contracts/{contract_id}/cancel"),
    ("GET", "/api/v1/sales-exceptions/projects/{project_id}"),
    # Payment Plans
    ("GET", "/api/v1/payment-plans/contracts/{contract_id}/schedule"),
    ("GET", "/api/v1/payment-plans/contracts/{contract_id}/installments"),
    ("GET", "/api/v1/payment-plans/contracts/{contract_id}/payment-plan"),
    # Finance
    ("GET", "/api/v1/finance/projects/{project_id}/summary"),
    # Registry (canonical routes — not /registration/*)
    ("POST", "/api/v1/registry/cases"),
    ("GET", "/api/v1/registry/cases/{case_id}"),
    ("PATCH", "/api/v1/registry/cases/{case_id}"),
    ("GET", "/api/v1/registry/projects/{project_id}/cases"),
    ("GET", "/api/v1/registry/projects/{project_id}/summary"),
    ("GET", "/api/v1/registry/cases/{case_id}/milestones"),
    ("PATCH", "/api/v1/registry/cases/{case_id}/milestones/{milestone_id}"),
    ("GET", "/api/v1/registry/cases/{case_id}/documents"),
    ("PATCH", "/api/v1/registry/cases/{case_id}/documents/{document_id}"),
    # Construction
    ("GET", "/api/v1/construction/scopes"),
    ("POST", "/api/v1/construction/scopes"),
    ("GET", "/api/v1/construction/scopes/{scope_id}"),
    ("PATCH", "/api/v1/construction/scopes/{scope_id}"),
    ("DELETE", "/api/v1/construction/scopes/{scope_id}"),
    ("GET", "/api/v1/construction/milestones"),
    ("POST", "/api/v1/construction/milestones"),
    ("GET", "/api/v1/construction/milestones/{milestone_id}"),
    ("PATCH", "/api/v1/construction/milestones/{milestone_id}"),
    ("DELETE", "/api/v1/construction/milestones/{milestone_id}"),
    ("POST", "/api/v1/construction/milestones/{milestone_id}/progress-updates"),
    ("GET", "/api/v1/construction/milestones/{milestone_id}/progress-updates"),
    ("GET", "/api/v1/construction/progress-updates/{update_id}"),
    ("DELETE", "/api/v1/construction/progress-updates/{update_id}"),
    ("GET", "/api/v1/construction/projects/{project_id}/dashboard"),
    ("GET", "/api/v1/construction/scopes/{scope_id}/cost-summary"),
    # Settings
    ("GET", "/api/v1/settings/pricing-policies"),
    ("POST", "/api/v1/settings/pricing-policies"),
    ("GET", "/api/v1/settings/pricing-policies/{policy_id}"),
    ("PATCH", "/api/v1/settings/pricing-policies/{policy_id}"),
    ("DELETE", "/api/v1/settings/pricing-policies/{policy_id}"),
    ("GET", "/api/v1/settings/commission-policies"),
    ("POST", "/api/v1/settings/commission-policies"),
    ("GET", "/api/v1/settings/commission-policies/{policy_id}"),
    ("PATCH", "/api/v1/settings/commission-policies/{policy_id}"),
    ("DELETE", "/api/v1/settings/commission-policies/{policy_id}"),
    ("GET", "/api/v1/settings/project-templates"),
    ("POST", "/api/v1/settings/project-templates"),
    ("GET", "/api/v1/settings/project-templates/{template_id}"),
    ("PATCH", "/api/v1/settings/project-templates/{template_id}"),
    ("DELETE", "/api/v1/settings/project-templates/{template_id}"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_frontend_file(filename: str) -> str:
    """Read a frontend lib file and return its contents."""
    path = FRONTEND_LIB_DIR / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_frontend_page(relative_path: str) -> str:
    """Read a frontend app page file and return its contents."""
    path = FRONTEND_APP_DIR / relative_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: required files exist
# ---------------------------------------------------------------------------


class TestRequiredFilesExist:
    """Every domain API wrapper and type definition file must exist."""

    def test_all_required_api_wrappers_exist(self):
        """All domain API wrapper files must be present in frontend/src/lib/."""
        missing = [
            f
            for f in REQUIRED_API_WRAPPER_FILES
            if not (FRONTEND_LIB_DIR / f).exists()
        ]
        assert not missing, (
            f"Missing API wrapper files in frontend/src/lib/:\n"
            + "\n".join(f"  {f}" for f in missing)
        )

    def test_all_required_type_files_exist(self):
        """All domain type definition files must be present in frontend/src/lib/."""
        missing = [
            f
            for f in REQUIRED_TYPE_FILES
            if not (FRONTEND_LIB_DIR / f).exists()
        ]
        assert not missing, (
            f"Missing type definition files in frontend/src/lib/:\n"
            + "\n".join(f"  {f}" for f in missing)
        )


# ---------------------------------------------------------------------------
# Tests: no legacy /registration/* paths in wrappers
# ---------------------------------------------------------------------------


class TestNoLegacyRegistrationPaths:
    """Frontend API wrappers must not call legacy /registration/* routes."""

    def test_registry_api_does_not_use_registration_prefix(self):
        """registry-api.ts must use /registry/* not /registration/*."""
        content = _read_frontend_file("registry-api.ts")
        assert content, "registry-api.ts is missing or empty"
        for pattern in FORBIDDEN_LEGACY_PATTERNS:
            assert not re.search(pattern, content), (
                f"registry-api.ts contains legacy path pattern '{pattern}'. "
                f"Use /registry/* canonical routes instead."
            )

    def test_dashboard_api_does_not_use_registration_prefix(self):
        """dashboard-api.ts must use /registry/* not /registration/*."""
        content = _read_frontend_file("dashboard-api.ts")
        assert content, "dashboard-api.ts is missing or empty"
        for pattern in FORBIDDEN_LEGACY_PATTERNS:
            assert not re.search(pattern, content), (
                f"dashboard-api.ts contains legacy path pattern '{pattern}'. "
                f"Use /registry/* canonical routes instead."
            )

    def test_finance_dashboard_api_does_not_use_registration_prefix(self):
        """finance-dashboard-api.ts must use /registry/* not /registration/*."""
        content = _read_frontend_file("finance-dashboard-api.ts")
        assert content, "finance-dashboard-api.ts is missing or empty"
        for pattern in FORBIDDEN_LEGACY_PATTERNS:
            assert not re.search(pattern, content), (
                f"finance-dashboard-api.ts contains legacy path pattern '{pattern}'. "
                f"Use /registry/* canonical routes instead."
            )

    def test_all_wrappers_free_of_legacy_registration_paths(self):
        """No frontend API wrapper should call /registration/* routes."""
        violations = []
        for api_file in REQUIRED_API_WRAPPER_FILES:
            content = _read_frontend_file(api_file)
            if not content:
                continue
            for pattern in FORBIDDEN_LEGACY_PATTERNS:
                if re.search(pattern, content):
                    violations.append(f"{api_file}: found forbidden pattern '{pattern}'")
        assert not violations, (
            "Legacy /registration/* paths found in frontend wrappers:\n"
            + "\n".join(f"  {v}" for v in violations)
        )


# ---------------------------------------------------------------------------
# Tests: backend contract correctness via OpenAPI schema
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def openapi_schema():
    """Return the OpenAPI schema from the running FastAPI application."""
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200, "OpenAPI schema failed to generate"
    return response.json()


class TestBackendContractCoverage:
    """Critical frontend-used API paths must exist as real backend routes."""

    def test_critical_contract_pairs_exist_in_openapi(self, openapi_schema):
        """All critical (method, path) pairs documented in wrappers must exist in backend."""
        schema_paths = openapi_schema.get("paths", {})
        missing = []
        for method, path in CRITICAL_FRONTEND_CONTRACT_PAIRS:
            if path not in schema_paths:
                missing.append(f"{method} {path}  [path not found in OpenAPI]")
                continue
            path_item = schema_paths[path]
            if method.lower() not in path_item:
                missing.append(f"{method} {path}  [method not found for this path]")

        assert not missing, (
            "Frontend API wrappers reference backend paths that do not exist:\n"
            + "\n".join(f"  {m}" for m in missing)
        )

    def test_registry_canonical_routes_are_in_schema(self, openapi_schema):
        """Registry canonical /registry/* paths must be in the OpenAPI schema."""
        schema_paths = openapi_schema.get("paths", {})
        required_registry_paths = [
            "/api/v1/registry/cases",
            "/api/v1/registry/cases/{case_id}",
            "/api/v1/registry/projects/{project_id}/cases",
            "/api/v1/registry/projects/{project_id}/summary",
        ]
        missing = [p for p in required_registry_paths if p not in schema_paths]
        assert not missing, (
            "Canonical registry routes missing from OpenAPI schema:\n"
            + "\n".join(f"  {p}" for p in missing)
        )

    def test_settings_routes_are_in_schema(self, openapi_schema):
        """Settings domain routes must be in the OpenAPI schema."""
        schema_paths = openapi_schema.get("paths", {})
        required_settings_paths = [
            "/api/v1/settings/pricing-policies",
            "/api/v1/settings/commission-policies",
            "/api/v1/settings/project-templates",
        ]
        missing = [p for p in required_settings_paths if p not in schema_paths]
        assert not missing, (
            "Settings routes missing from OpenAPI schema:\n"
            + "\n".join(f"  {p}" for p in missing)
        )

    def test_construction_progress_update_routes_in_schema(self, openapi_schema):
        """Construction progress update routes must be in the OpenAPI schema."""
        schema_paths = openapi_schema.get("paths", {})
        required_progress_paths = [
            "/api/v1/construction/milestones/{milestone_id}/progress-updates",
            "/api/v1/construction/progress-updates/{update_id}",
        ]
        missing = [p for p in required_progress_paths if p not in schema_paths]
        assert not missing, (
            "Construction progress-update routes missing from OpenAPI schema:\n"
            + "\n".join(f"  {p}" for p in missing)
        )


# ---------------------------------------------------------------------------
# Tests: registry wrapper uses canonical /registry/* routes
# ---------------------------------------------------------------------------


class TestRegistryWrapperContract:
    """registry-api.ts must call canonical /registry/* routes."""

    def test_registry_wrapper_calls_registry_cases(self):
        """/registry/cases must be present in registry-api.ts."""
        content = _read_frontend_file("registry-api.ts")
        assert "/registry/cases" in content, (
            "registry-api.ts does not contain /registry/cases path"
        )

    def test_registry_wrapper_calls_project_scoped_cases(self):
        """/registry/projects/... must be present in registry-api.ts."""
        content = _read_frontend_file("registry-api.ts")
        assert "/registry/projects/" in content, (
            "registry-api.ts does not contain project-scoped /registry/projects/ path"
        )

    def test_registry_wrapper_has_milestone_endpoint(self):
        """/registry/cases/.../milestones must be callable from registry-api.ts."""
        content = _read_frontend_file("registry-api.ts")
        assert "milestones" in content, (
            "registry-api.ts does not wrap the milestones endpoint"
        )

    def test_registry_wrapper_has_document_endpoint(self):
        """/registry/cases/.../documents must be callable from registry-api.ts."""
        content = _read_frontend_file("registry-api.ts")
        assert "documents" in content, (
            "registry-api.ts does not wrap the documents endpoint"
        )


# ---------------------------------------------------------------------------
# Tests: settings wrapper contract
# ---------------------------------------------------------------------------


class TestSettingsWrapperContract:
    """settings-api.ts must expose wrappers for all three settings resources."""

    def test_settings_wrapper_has_pricing_policies(self):
        """settings-api.ts must wrap /settings/pricing-policies."""
        content = _read_frontend_file("settings-api.ts")
        assert "/settings/pricing-policies" in content, (
            "settings-api.ts does not wrap /settings/pricing-policies"
        )

    def test_settings_wrapper_has_commission_policies(self):
        """settings-api.ts must wrap /settings/commission-policies."""
        content = _read_frontend_file("settings-api.ts")
        assert "/settings/commission-policies" in content, (
            "settings-api.ts does not wrap /settings/commission-policies"
        )

    def test_settings_wrapper_has_project_templates(self):
        """settings-api.ts must wrap /settings/project-templates."""
        content = _read_frontend_file("settings-api.ts")
        assert "/settings/project-templates" in content, (
            "settings-api.ts does not wrap /settings/project-templates"
        )


# ---------------------------------------------------------------------------
# Tests: construction wrapper covers progress updates
# ---------------------------------------------------------------------------


class TestConstructionWrapperContract:
    """construction-api.ts must include progress update wrappers."""

    def test_construction_wrapper_has_progress_updates(self):
        """construction-api.ts must wrap the progress-updates endpoints."""
        content = _read_frontend_file("construction-api.ts")
        assert "progress-updates" in content, (
            "construction-api.ts does not wrap construction progress-update endpoints"
        )

    def test_construction_wrapper_has_dashboard(self):
        """construction-api.ts must wrap the /construction/projects/{id}/dashboard endpoint."""
        content = _read_frontend_file("construction-api.ts")
        assert "/construction/projects/" in content, (
            "construction-api.ts does not wrap the project construction dashboard endpoint"
        )


# ---------------------------------------------------------------------------
# Tests: registry page uses live data, not demo
# ---------------------------------------------------------------------------


class TestRegistryPageIsLive:
    """Registry page must use live API data, not the static demo dataset."""

    def test_registry_page_does_not_import_demo_data(self):
        """Registry page must not import demoRegistryCases from demo-data.ts."""
        content = _read_frontend_page("(protected)/registry/page.tsx")
        assert content, "(protected)/registry/page.tsx not found"
        assert "demoRegistryCases" not in content, (
            "Registry page still imports demoRegistryCases from demo-data.ts. "
            "The registry backend is fully implemented — use registry-api.ts instead."
        )

    def test_registry_page_imports_registry_api(self):
        """Registry page must import from registry-api.ts."""
        content = _read_frontend_page("(protected)/registry/page.tsx")
        assert content, "(protected)/registry/page.tsx not found"
        assert "registry-api" in content, (
            "Registry page does not import from registry-api.ts. "
            "It should call the live /registry/* backend endpoints."
        )


# ---------------------------------------------------------------------------
# Tests: settings page is documented as intentional demo
# ---------------------------------------------------------------------------


class TestSettingsPageDocumentation:
    """Settings page must be documented as intentional demo for non-wired sections."""

    def test_settings_page_has_intentional_demo_annotation(self):
        """Settings page must document why it shows demo data."""
        content = _read_frontend_page("(protected)/settings/page.tsx")
        assert content, "(protected)/settings/page.tsx not found"
        assert "INTENTIONAL DEMO" in content or "intentional" in content.lower(), (
            "Settings page does not document that it is intentionally showing demo data. "
            "Add a comment explaining which sections are demo vs. live."
        )
