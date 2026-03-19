"""
tests/architecture/test_router_consistency.py

Router consistency tests for PR-E3.

Validates that the FastAPI router layer is consistent with the domain
architecture defined in docs/00-overview/system-architecture.md:

  1. Every domain router is registered under the /api/v1 prefix.
  2. Every registered router declares at least one tag.
  3. No duplicate route paths exist in the application.
  4. The 8 core domain routers use the canonical prefix and Title Case tags.
  5. The OpenAPI schema generates successfully and includes all expected tags.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app, _API_PREFIX

# ---------------------------------------------------------------------------
# Canonical domain router configuration
# ---------------------------------------------------------------------------

# The 8 core domain routers required by PR-E3.
CORE_DOMAIN_ROUTERS = {
    "/projects": "Projects",
    "/pricing": "Pricing",
    "/sales": "Sales",
    "/payment-plans": "Payment Plans",
    "/finance": "Finance",
    "/registry": "Registry",
    "/construction": "Construction",
    "/settings": "Settings",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_all_routes():
    """Return all routes registered on the application."""
    return list(app.routes)


def _get_registered_routers():
    """Collect (prefix, tags) from all APIRouter-sourced routes."""
    from fastapi.routing import APIRoute

    seen = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            # FastAPI flattens routers into individual routes on the app.
            # Recover the router prefix from the route path and tags.
            for tag in route.tags or []:
                if tag not in seen:
                    seen[tag] = route.path
    return seen


# ---------------------------------------------------------------------------
# Test class: router prefix registration
# ---------------------------------------------------------------------------


class TestRouterPrefixRegistration:
    """Verify routers are registered under the correct API prefix."""

    def test_all_core_domain_routes_use_api_v1_prefix(self):
        """All core domain routes must start with /api/v1."""
        from fastapi.routing import APIRoute

        api_routes = [r for r in app.routes if isinstance(r, APIRoute)]
        assert api_routes, "No API routes found on the application"

        # Routes that are intentionally outside the /api/v1 namespace.
        # Health and auth endpoints are registered directly on the app.
        _EXEMPT_PREFIXES = ("/health", "/auth", "/docs", "/openapi", "/redoc")

        for route in api_routes:
            if route.include_in_schema and not route.path.startswith(_EXEMPT_PREFIXES):
                assert route.path.startswith(_API_PREFIX), (
                    f"Route '{route.path}' does not start with API prefix '{_API_PREFIX}'"
                )

    def test_core_domain_routers_have_correct_prefix(self):
        """Each core domain router must expose routes under its canonical prefix."""
        from fastapi.routing import APIRoute

        route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}

        for domain_prefix in CORE_DOMAIN_ROUTERS:
            full_prefix = _API_PREFIX + domain_prefix
            matching = [p for p in route_paths if p.startswith(full_prefix)]
            assert matching, (
                f"No routes found for core domain prefix '{full_prefix}'. "
                f"Expected at least one route under '{full_prefix}/...'."
            )

    def test_api_v1_prefix_value(self):
        """The API prefix must be /api/v1."""
        assert _API_PREFIX == "/api/v1", (
            f"Expected API prefix '/api/v1', got '{_API_PREFIX}'"
        )


# ---------------------------------------------------------------------------
# Test class: tag consistency
# ---------------------------------------------------------------------------


class TestTagConsistency:
    """Verify all domain routers declare Title Case tags."""

    def test_core_domain_routers_have_correct_tags(self):
        """Each core domain router must use its canonical Title Case tag."""
        from fastapi.routing import APIRoute

        # Build a map of prefix → tags actually found
        prefix_to_tags: dict[str, set] = {}
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            if not route.include_in_schema:
                continue
            for domain_prefix, expected_tag in CORE_DOMAIN_ROUTERS.items():
                full_prefix = _API_PREFIX + domain_prefix
                if route.path.startswith(full_prefix):
                    prefix_to_tags.setdefault(domain_prefix, set()).update(route.tags or [])

        for domain_prefix, expected_tag in CORE_DOMAIN_ROUTERS.items():
            tags = prefix_to_tags.get(domain_prefix, set())
            assert expected_tag in tags, (
                f"Domain '{domain_prefix}' routes are missing canonical tag "
                f"'{expected_tag}'. Found tags: {tags}"
            )

    def test_all_schema_routes_have_at_least_one_tag(self):
        """Every documented route must belong to at least one tag group."""
        from fastapi.routing import APIRoute

        untagged = [
            route.path
            for route in app.routes
            if isinstance(route, APIRoute) and route.include_in_schema and not route.tags
        ]
        assert not untagged, (
            f"The following routes have no tags: {untagged}"
        )


# ---------------------------------------------------------------------------
# Test class: duplicate route detection
# ---------------------------------------------------------------------------


class TestNoDuplicateRoutes:
    """Verify there are no duplicate route paths in the application."""

    def test_no_duplicate_routes(self):
        """No two routes should share the same (method, path) combination."""
        from fastapi.routing import APIRoute

        seen: dict[tuple, str] = {}
        duplicates = []

        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            for method in route.methods or []:
                key = (method.upper(), route.path)
                if key in seen:
                    duplicates.append(f"{method} {route.path} (duplicate of existing registration)")
                else:
                    seen[key] = route.path

        assert not duplicates, (
            f"Duplicate routes detected:\n" + "\n".join(duplicates)
        )


# ---------------------------------------------------------------------------
# Test class: OpenAPI schema generation
# ---------------------------------------------------------------------------


class TestOpenAPISchema:
    """Verify the OpenAPI schema generates correctly and is complete."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def openapi_schema(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200, "OpenAPI schema failed to generate"
        return response.json()

    def test_openapi_schema_loads_successfully(self, client):
        """GET /openapi.json must return 200 with a valid schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "info" in schema

    def test_all_core_domain_tags_present_in_openapi(self, openapi_schema):
        """All 8 core domain tags must appear in the OpenAPI schema."""
        schema_tags = {t["name"] for t in openapi_schema.get("tags", [])}
        # Tags can also appear implicitly via route tag references
        path_tags: set = set()
        for path_item in openapi_schema.get("paths", {}).values():
            for operation in path_item.values():
                if isinstance(operation, dict):
                    path_tags.update(operation.get("tags", []))

        all_tags = schema_tags | path_tags
        for expected_tag in CORE_DOMAIN_ROUTERS.values():
            assert expected_tag in all_tags, (
                f"Core domain tag '{expected_tag}' is missing from the OpenAPI schema. "
                f"Found tags: {all_tags}"
            )

    def test_core_domain_paths_present_in_openapi(self, openapi_schema):
        """At least one path per core domain must appear in the OpenAPI schema."""
        schema_paths = set(openapi_schema.get("paths", {}).keys())
        for domain_prefix in CORE_DOMAIN_ROUTERS:
            full_prefix = _API_PREFIX + domain_prefix
            matching = [p for p in schema_paths if p.startswith(full_prefix)]
            assert matching, (
                f"No OpenAPI paths found for domain '{domain_prefix}'. "
                f"Expected at least one path under '{full_prefix}/...'."
            )
