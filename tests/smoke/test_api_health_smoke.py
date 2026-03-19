"""
Smoke test: API Health

Validates that all critical platform endpoints are reachable and return
expected status codes.

Checks:
  /health
  /openapi.json
  /api/v1/projects
  /api/v1/pricing
  /api/v1/sales
  /api/v1/registry
  /api/v1/construction
  /api/v1/settings
"""

import pytest
from fastapi.testclient import TestClient


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_health_endpoint_responds(client: TestClient):
    """/health must return 200 with status ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_openapi_schema_valid(client: TestClient):
    """/openapi.json must return 200 and a valid OpenAPI object."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "openapi" in schema
    assert "paths" in schema
    assert "info" in schema


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/projects",
        "/api/v1/pricing/project/nonexistent-project",
        "/api/v1/sales/buyers",
        "/api/v1/registry/cases",
        "/api/v1/construction/scopes",
        "/api/v1/settings/pricing-policies",
    ],
)
def test_api_list_endpoints_respond(client: TestClient, url: str):
    """All major list endpoints must return a non-5xx response."""
    resp = client.get(url)
    assert resp.status_code < 500, (
        f"Endpoint {url} returned unexpected server error {resp.status_code}"
    )


def test_projects_list_endpoint_schema(client: TestClient):
    """/api/v1/projects must return a paginated list with items and total."""
    resp = client.get("/api/v1/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_sales_buyers_list_schema(client: TestClient):
    """/api/v1/sales/buyers must return a paginated list."""
    resp = client.get("/api/v1/sales/buyers")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_construction_scopes_list_schema(client: TestClient):
    """/api/v1/construction/scopes must return a paginated list."""
    resp = client.get("/api/v1/construction/scopes")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_settings_pricing_policies_list_schema(client: TestClient):
    """/api/v1/settings/pricing-policies must return a paginated list."""
    resp = client.get("/api/v1/settings/pricing-policies")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
