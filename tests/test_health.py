"""
Tests for application health endpoints.

Validates the /health and /health/db endpoints introduced in PR-REDS-002.
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
    assert data["service"] == "reach-developments-station"


def test_health_db_reachable():
    """GET /health/db should return HTTP 200 when the database is reachable."""
    with patch("app.main.check_db_connection", return_value=True):
        response = client.get("/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "reachable"


def test_health_db_unreachable():
    """GET /health/db should return HTTP 503 when the database is not reachable."""
    with patch("app.main.check_db_connection", return_value=False):
        response = client.get("/health/db")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["database"] == "unreachable"
