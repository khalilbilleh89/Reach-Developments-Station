"""
Tests for application health endpoints.

Validates the /health, /health/live, and /health/ready endpoints
introduced in PR-INFRA-031.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    """GET /health should return HTTP 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "reach_developments"
    assert "timestamp" in data


def test_health_live_returns_alive():
    """GET /health/live should return HTTP 200 with status alive."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == "reach_developments"
    assert "timestamp" in data


def test_health_ready_reachable():
    """GET /health/ready should return HTTP 200 when the database is reachable."""
    with patch("app.api.health.is_database_reachable", return_value=True):
        response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert data["service"] == "reach_developments"
    assert "timestamp" in data


def test_health_ready_unreachable():
    """GET /health/ready should return HTTP 503 when the database is not reachable."""
    with patch("app.api.health.is_database_reachable", return_value=False):
        response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["database"] == "unreachable"

