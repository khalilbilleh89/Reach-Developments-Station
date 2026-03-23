"""
tests/core/test_health.py

Unit tests for core health-check logic and diagnostics endpoints.

PR-INFRA-031: System Health & Diagnostics Endpoints

Validates:
    - /health/live returns HTTP 200
    - /health/ready returns HTTP 200 when DB is reachable
    - /health/ready returns HTTP 503 when DB is unavailable
    - Response payloads include required fields
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.health import get_health, get_liveness, get_readiness
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests for app.core.health module
# ---------------------------------------------------------------------------


class TestGetHealth:
    """get_health() must return a correctly structured health payload."""

    def test_returns_ok_status(self):
        payload = get_health()
        assert payload["status"] == "ok"

    def test_returns_service_name(self):
        payload = get_health()
        assert payload["service"] == "reach_developments"

    def test_returns_timestamp(self):
        payload = get_health()
        assert "timestamp" in payload
        assert payload["timestamp"].endswith("Z")


class TestGetLiveness:
    """get_liveness() must return a correctly structured liveness payload."""

    def test_returns_alive_status(self):
        payload = get_liveness()
        assert payload["status"] == "alive"

    def test_returns_service_name(self):
        payload = get_liveness()
        assert payload["service"] == "reach_developments"

    def test_returns_timestamp(self):
        payload = get_liveness()
        assert "timestamp" in payload
        assert payload["timestamp"].endswith("Z")


class TestGetReadiness:
    """get_readiness() must return correct payloads for both DB states."""

    def test_ready_when_db_connected(self):
        payload = get_readiness(database_connected=True)
        assert payload["status"] == "ready"
        assert payload["database"] == "connected"

    def test_unavailable_when_db_unreachable(self):
        payload = get_readiness(database_connected=False)
        assert payload["status"] == "unavailable"
        assert payload["database"] == "unreachable"

    def test_includes_service_name(self):
        assert get_readiness(True)["service"] == "reach_developments"
        assert get_readiness(False)["service"] == "reach_developments"

    def test_includes_timestamp(self):
        assert get_readiness(True)["timestamp"].endswith("Z")
        assert get_readiness(False)["timestamp"].endswith("Z")


# ---------------------------------------------------------------------------
# Integration tests for health HTTP endpoints
# ---------------------------------------------------------------------------


class TestHealthLiveEndpoint:
    """GET /health/live must always return HTTP 200."""

    def test_returns_200(self):
        resp = client.get("/health/live")
        assert resp.status_code == 200

    def test_returns_alive_status(self):
        data = client.get("/health/live").json()
        assert data["status"] == "alive"

    def test_response_includes_service(self):
        data = client.get("/health/live").json()
        assert data["service"] == "reach_developments"

    def test_response_includes_timestamp(self):
        data = client.get("/health/live").json()
        assert "timestamp" in data


class TestHealthReadyEndpoint:
    """GET /health/ready must reflect database connectivity."""

    def test_returns_200_when_db_reachable(self):
        with patch("app.api.health.is_database_reachable", return_value=True):
            resp = client.get("/health/ready")
        assert resp.status_code == 200

    def test_returns_ready_status_when_db_reachable(self):
        with patch("app.api.health.is_database_reachable", return_value=True):
            data = client.get("/health/ready").json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"

    def test_returns_503_when_db_unavailable(self):
        with patch("app.api.health.is_database_reachable", return_value=False):
            resp = client.get("/health/ready")
        assert resp.status_code == 503

    def test_returns_unavailable_status_when_db_unreachable(self):
        with patch("app.api.health.is_database_reachable", return_value=False):
            data = client.get("/health/ready").json()
        assert data["status"] == "unavailable"
        assert data["database"] == "unreachable"

    def test_response_includes_service(self):
        with patch("app.api.health.is_database_reachable", return_value=True):
            data = client.get("/health/ready").json()
        assert data["service"] == "reach_developments"

    def test_response_includes_timestamp(self):
        with patch("app.api.health.is_database_reachable", return_value=True):
            data = client.get("/health/ready").json()
        assert "timestamp" in data
