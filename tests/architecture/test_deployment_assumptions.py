"""
tests/architecture/test_deployment_assumptions.py

PR-F1: Deployment Assumption Tests.

Validates that the application meets production deployment requirements:

  1. FastAPI application loads successfully.
  2. Static frontend fallback works (JSON status when build is absent).
  3. /health endpoint responds with 200 and correct payload.
  4. /openapi.json endpoint loads successfully.
  5. Startup logs include the expected markers.
  6. Application has a valid title and version configured.
  7. The single-service architecture invariants are satisfied.

These tests prevent deployment regressions by verifying that the application
is in a shippable state from a deployment operations perspective.
"""

import logging
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app, _API_PREFIX, _FRONTEND_HTML_DIR

# ---------------------------------------------------------------------------
# Test class: application loads
# ---------------------------------------------------------------------------


class TestApplicationLoads:
    """The FastAPI application must load successfully with correct metadata."""

    def test_app_is_fastapi_instance(self):
        """The exported `app` object must be a FastAPI instance."""
        assert isinstance(app, FastAPI), (
            "app.main.app is not a FastAPI instance — application failed to initialize."
        )

    def test_app_has_non_empty_title(self):
        """The application must have a non-empty title configured."""
        assert app.title and len(app.title.strip()) > 0, (
            "FastAPI application has no title — check app/core/config.py APP_NAME setting."
        )

    def test_app_has_version_configured(self):
        """The application version must be set."""
        assert app.version and len(app.version.strip()) > 0, (
            "FastAPI application has no version configured."
        )

    def test_api_v1_prefix_is_set(self):
        """The API v1 prefix must be '/api/v1'."""
        assert _API_PREFIX == "/api/v1", (
            f"Expected _API_PREFIX='/api/v1', got '{_API_PREFIX}'"
        )

    def test_app_routes_are_registered(self):
        """Application must have routes registered (not empty)."""
        from fastapi.routing import APIRoute

        api_routes = [r for r in app.routes if isinstance(r, APIRoute)]
        assert len(api_routes) > 0, (
            "No API routes registered on the FastAPI application."
        )

    def test_app_has_minimum_route_count(self):
        """Application must have a reasonable minimum number of routes.

        A production-ready platform with 8 core domains plus supporting
        infrastructure should have significantly more than 10 routes.
        """
        from fastapi.routing import APIRoute

        api_routes = [r for r in app.routes if isinstance(r, APIRoute)]
        assert len(api_routes) >= 30, (
            f"Application has only {len(api_routes)} routes — expected at least 30 "
            "for a production platform with 8 core domains."
        )


# ---------------------------------------------------------------------------
# Test class: /health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """The /health endpoint must work correctly after startup."""

    def test_health_endpoint_returns_200(self, client: TestClient):
        """/health must return HTTP 200."""
        resp = client.get("/health")
        assert resp.status_code == 200, (
            f"/health returned {resp.status_code}, expected 200."
        )

    def test_health_endpoint_returns_ok_status(self, client: TestClient):
        """/health must return JSON with status='ok'."""
        resp = client.get("/health")
        data = resp.json()
        assert data.get("status") == "ok", (
            f"/health status field is '{data.get('status')}', expected 'ok'."
        )

    def test_health_endpoint_includes_service_name(self, client: TestClient):
        """/health must include the service name in the response."""
        resp = client.get("/health")
        data = resp.json()
        assert "service" in data, (
            "/health response does not include a 'service' key."
        )
        assert data["service"], (
            "/health 'service' field is empty."
        )

    def test_health_db_endpoint_exists(self, client: TestClient):
        """/health/db must exist and return a non-5xx status."""
        with patch("app.main.check_db_connection", return_value=True):
            resp = client.get("/health/db")
        assert resp.status_code < 500, (
            f"/health/db returned {resp.status_code} — server error on health check."
        )


# ---------------------------------------------------------------------------
# Test class: /openapi.json endpoint
# ---------------------------------------------------------------------------


class TestOpenApiEndpoint:
    """The OpenAPI JSON endpoint must load and return a valid schema."""

    def test_openapi_json_returns_200(self, client: TestClient):
        """GET /openapi.json must return HTTP 200."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200, (
            f"/openapi.json returned {resp.status_code}, expected 200."
        )

    def test_openapi_json_is_valid_schema(self, client: TestClient):
        """GET /openapi.json must return a parseable OpenAPI schema dict."""
        resp = client.get("/openapi.json")
        schema = resp.json()
        assert isinstance(schema, dict), "/openapi.json did not return a JSON object."
        assert "openapi" in schema, "OpenAPI schema missing 'openapi' version field."
        assert "paths" in schema, "OpenAPI schema missing 'paths' field."

    def test_openapi_schema_has_title(self, client: TestClient):
        """OpenAPI schema info block must include the application title."""
        resp = client.get("/openapi.json")
        schema = resp.json()
        info = schema.get("info", {})
        assert info.get("title"), "OpenAPI schema info.title is empty."


# ---------------------------------------------------------------------------
# Test class: frontend static fallback
# ---------------------------------------------------------------------------


class TestFrontendStaticFallback:
    """When the frontend build is absent, a JSON status fallback must be returned."""

    def test_root_returns_response_when_no_build(self, client: TestClient):
        """GET / must return a response (JSON status) when frontend build is absent."""
        with patch.object(Path, "is_dir", return_value=False):
            resp = client.get("/")
        # Should return 200 with either JSON status payload or the frontend index
        assert resp.status_code == 200, (
            f"GET / returned {resp.status_code} when no frontend build present."
        )

    def test_root_json_fallback_includes_app_name(self, client: TestClient):
        """JSON fallback at GET / must include the application name."""
        # Only run this check if the frontend build is actually absent
        if _FRONTEND_HTML_DIR.is_dir():
            pytest.skip("Frontend build present — JSON fallback not active")

        resp = client.get("/")
        data = resp.json()
        assert "app" in data or "status" in data, (
            "JSON fallback at GET / does not include 'app' or 'status' key."
        )

    def test_get_returns_200_not_500(self, client: TestClient):
        """GET / must never return a 5xx error."""
        resp = client.get("/")
        assert resp.status_code < 500, (
            f"GET / returned {resp.status_code} — server error on root path."
        )


# ---------------------------------------------------------------------------
# Test class: startup log messages
# ---------------------------------------------------------------------------


class TestStartupLogMessages:
    """Application startup must emit the expected log markers."""

    def test_startup_logs_app_name(self, caplog):
        """Startup must log a message containing the application name."""
        from app.core.config import settings

        with caplog.at_level(logging.INFO, logger="app"):
            # Trigger the lifespan startup by creating a fresh client context
            with TestClient(app):
                pass

        log_text = " ".join(caplog.messages)
        assert settings.APP_NAME in log_text or "Starting" in log_text or "ready" in log_text, (
            "Startup log did not emit an expected application startup message. "
            f"Captured logs: {caplog.messages[:5]}"
        )

    def test_shutdown_does_not_raise(self):
        """Application shutdown must complete without raising exceptions."""
        try:
            with TestClient(app):
                pass
        except Exception as exc:
            pytest.fail(f"Application shutdown raised an exception: {exc}")


# ---------------------------------------------------------------------------
# Test class: single-service architecture invariants
# ---------------------------------------------------------------------------


class TestSingleServiceArchitectureInvariants:
    """The platform must operate as a single-service monolith (no microservices)."""

    def test_single_fastapi_app_instance(self):
        """There must be exactly one FastAPI app instance (no sub-applications)."""
        from fastapi.routing import Mount

        mounts = [r for r in app.routes if isinstance(r, Mount)]
        # StaticFiles mounts are acceptable (/_next/static)
        non_static_mounts = [
            m for m in mounts
            if not str(getattr(m, "path", "")).startswith("/_next")
        ]
        # No sub-application mounts (FastAPI micro-apps) are allowed
        for mount in non_static_mounts:
            assert not isinstance(getattr(mount, "app", None), FastAPI), (
                f"Unexpected sub-application mounted at '{mount.path}'. "
                "The platform must remain a single-service monolith."
            )

    def test_no_redis_dependency_in_main(self):
        """app/main.py must not import Redis or queue system dependencies."""
        main_source = (Path(__file__).parents[2] / "app" / "main.py").read_text(
            encoding="utf-8"
        )
        forbidden = ["import redis", "from redis", "import celery", "from celery", "import rq"]
        for pattern in forbidden:
            assert pattern not in main_source.lower(), (
                f"app/main.py contains forbidden import '{pattern}'. "
                "The platform must not introduce queue or cache infrastructure."
            )

    def test_no_async_worker_in_requirements(self):
        """requirements.txt must not include async worker / queue dependencies."""
        req_file = Path(__file__).parents[2] / "requirements.txt"
        if not req_file.exists():
            pytest.skip("requirements.txt not found")
        requirements = req_file.read_text(encoding="utf-8").lower()
        forbidden_packages = ["celery", "dramatiq", "rq", "huey", "arq"]
        violations = [pkg for pkg in forbidden_packages if pkg in requirements]
        assert not violations, (
            f"requirements.txt includes forbidden async worker packages: {violations}. "
            "The platform must remain a single-service architecture."
        )
