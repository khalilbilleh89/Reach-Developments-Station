"""
tests/architecture/test_api_surface_stability.py

PR-F1: API Surface Stability Tests.

Ensures all domain routers remain stable and the OpenAPI schema is
consistent with the platform's canonical architecture:

  1. All routes begin with /api/v1.
  2. OpenAPI schema loads successfully.
  3. All expected domain tags exist.
  4. No duplicate (method, path) pairs exist.
  5. Core domain route prefixes are present and registered.

These tests provide a regression safety net against accidental route
renames, prefix changes, or schema generation failures.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app, _API_PREFIX

# ---------------------------------------------------------------------------
# Constants — canonical domain configuration
# ---------------------------------------------------------------------------

# Eight core domains required by the platform architecture.
CORE_DOMAIN_TAGS = {
    "Projects",
    "Pricing",
    "Sales",
    "Payment Plans",
    "Finance",
    "Registry",
    "Construction",
    "Settings",
}

# Canonical route prefix for each core domain.
CORE_DOMAIN_PREFIXES = {
    "Projects": f"{_API_PREFIX}/projects",
    "Pricing": f"{_API_PREFIX}/pricing",
    "Sales": f"{_API_PREFIX}/sales",
    "Payment Plans": f"{_API_PREFIX}/payment-plans",
    "Finance": f"{_API_PREFIX}/finance",
    "Registry": f"{_API_PREFIX}/registry",
    "Construction": f"{_API_PREFIX}/construction",
    "Settings": f"{_API_PREFIX}/settings",
}


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def openapi_schema():
    """Generate and return the OpenAPI schema for the application."""
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200, (
        f"OpenAPI schema generation failed with status {response.status_code}"
    )
    return response.json()


# ---------------------------------------------------------------------------
# Test class: API prefix enforcement
# ---------------------------------------------------------------------------


class TestApiPrefixEnforcement:
    """All documented routes must use the /api/v1 prefix."""

    def test_api_v1_prefix_is_configured(self):
        """`_API_PREFIX` exported from app.main must equal '/api/v1'."""
        assert _API_PREFIX == "/api/v1", (
            f"Expected API prefix '/api/v1', found '{_API_PREFIX}'"
        )

    def test_all_schema_routes_start_with_api_v1(self, openapi_schema):
        """Every path in the OpenAPI schema must start with /api/v1.

        Health routes (/health) are intentionally outside the versioned prefix
        and are explicitly excluded from this check.
        """
        paths = openapi_schema.get("paths", {})
        violations = [
            path
            for path in paths
            if not path.startswith(_API_PREFIX) and not path.startswith("/health")
        ]
        assert not violations, (
            f"Routes found outside '{_API_PREFIX}' namespace:\n"
            + "\n".join(f"  {p}" for p in sorted(violations))
        )


# ---------------------------------------------------------------------------
# Test class: OpenAPI schema validity
# ---------------------------------------------------------------------------


class TestOpenApiSchemaValidity:
    """The OpenAPI schema must be structurally valid and complete."""

    def test_openapi_schema_has_required_top_level_keys(self, openapi_schema):
        """Schema must contain 'openapi', 'info', and 'paths' keys."""
        for key in ("openapi", "info", "paths"):
            assert key in openapi_schema, (
                f"Required top-level key '{key}' missing from OpenAPI schema"
            )

    def test_openapi_schema_has_paths(self, openapi_schema):
        """OpenAPI schema must contain at least one documented path."""
        assert openapi_schema.get("paths"), "OpenAPI schema has no documented paths"

    def test_openapi_schema_info_has_title(self, openapi_schema):
        """OpenAPI info block must have a non-empty title."""
        info = openapi_schema.get("info", {})
        assert info.get("title"), "OpenAPI schema info block is missing a title"

    def test_openapi_schema_loads_via_endpoint(self):
        """GET /openapi.json must return 200 with valid JSON."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert isinstance(schema, dict)
        assert "paths" in schema


# ---------------------------------------------------------------------------
# Test class: domain tag coverage
# ---------------------------------------------------------------------------


class TestDomainTagCoverage:
    """All 8 core domain tags must appear in the OpenAPI schema."""

    def _collect_all_tags(self, openapi_schema: dict) -> set:
        """Collect all tags from both the top-level tags list and route operations."""
        tags: set = set()
        # Top-level tag declarations
        for tag_obj in openapi_schema.get("tags", []):
            if isinstance(tag_obj, dict) and "name" in tag_obj:
                tags.add(tag_obj["name"])
        # Tags referenced by individual operations
        for path_item in openapi_schema.get("paths", {}).values():
            for operation in path_item.values():
                if isinstance(operation, dict):
                    tags.update(operation.get("tags", []))
        return tags

    def test_all_core_domain_tags_present(self, openapi_schema):
        """Each of the 8 core domain tags must appear in the OpenAPI schema."""
        all_tags = self._collect_all_tags(openapi_schema)
        missing = CORE_DOMAIN_TAGS - all_tags
        assert not missing, (
            f"Core domain tags missing from OpenAPI schema: {sorted(missing)}\n"
            f"Found tags: {sorted(all_tags)}"
        )

    def test_no_unexpected_core_tag_absence(self, openapi_schema):
        """Each expected core domain tag must have at least one associated route."""
        all_tags = self._collect_all_tags(openapi_schema)
        for tag in CORE_DOMAIN_TAGS:
            assert tag in all_tags, (
                f"Core domain tag '{tag}' is absent from the OpenAPI schema"
            )


# ---------------------------------------------------------------------------
# Test class: route prefix coverage
# ---------------------------------------------------------------------------


class TestDomainRoutePresence:
    """Each core domain must expose at least one route under its canonical prefix."""

    def test_all_core_domain_prefixes_have_routes(self, openapi_schema):
        """Each core domain prefix must match at least one path in the schema."""
        schema_paths = set(openapi_schema.get("paths", {}).keys())
        missing = []
        for domain, prefix in CORE_DOMAIN_PREFIXES.items():
            matches = [p for p in schema_paths if p.startswith(prefix)]
            if not matches:
                missing.append(f"{domain} (expected prefix: '{prefix}')")
        assert not missing, (
            "Core domains have no routes in OpenAPI schema:\n"
            + "\n".join(f"  {m}" for m in missing)
        )


# ---------------------------------------------------------------------------
# Test class: no duplicate routes
# ---------------------------------------------------------------------------


class TestNoDuplicateRoutes:
    """No two routes may share the same HTTP method and path combination."""

    def test_no_duplicate_method_path_pairs(self):
        """Scan all registered routes for (method, path) duplicates."""
        from fastapi.routing import APIRoute

        seen: dict[tuple, str] = {}
        duplicates: list[str] = []

        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            for method in route.methods or []:
                key = (method.upper(), route.path)
                if key in seen:
                    duplicates.append(
                        f"{method.upper()} {route.path} (registered more than once)"
                    )
                else:
                    seen[key] = route.path

        assert not duplicates, (
            "Duplicate (method, path) pairs detected:\n"
            + "\n".join(f"  {d}" for d in duplicates)
        )

    def test_no_duplicate_paths_in_openapi(self, openapi_schema):
        """Every path in the OpenAPI schema must be unique."""
        paths = list(openapi_schema.get("paths", {}).keys())
        seen: set[str] = set()
        duplicates = []
        for path in paths:
            if path in seen:
                duplicates.append(path)
            seen.add(path)
        assert not duplicates, (
            f"Duplicate paths in OpenAPI schema: {duplicates}"
        )
