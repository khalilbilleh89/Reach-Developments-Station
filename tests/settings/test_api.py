"""
Tests for the Settings domain API.

Covers CRUD for PricingPolicy, CommissionPolicy, and ProjectTemplate, as
well as governance rules:
  - Single-default invariant for pricing and commission policies
  - FK validation for project templates
  - Duplicate-name rejection (409)
  - Missing-resource handling (404)
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _create_pricing_policy(
    client: TestClient,
    name: str = "Standard Pricing",
    **kwargs,
) -> dict:
    payload = {"name": name, **kwargs}
    resp = client.post("/api/v1/settings/pricing-policies", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_commission_policy(
    client: TestClient,
    name: str = "Standard Commission",
    **kwargs,
) -> dict:
    payload = {"name": name, **kwargs}
    resp = client.post("/api/v1/settings/commission-policies", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_project_template(
    client: TestClient,
    name: str = "Default Template",
    **kwargs,
) -> dict:
    payload = {"name": name, **kwargs}
    resp = client.post("/api/v1/settings/project-templates", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ===========================================================================
# PricingPolicy CRUD
# ===========================================================================


def test_create_pricing_policy_returns_201(client: TestClient):
    data = _create_pricing_policy(client, "Policy A")
    assert data["name"] == "Policy A"
    assert data["is_default"] is False
    assert data["currency"] == "AED"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


def test_create_pricing_policy_with_all_fields(client: TestClient):
    data = _create_pricing_policy(
        client,
        name="Full Policy",
        description="Full description",
        is_default=True,
        currency="USD",
        base_markup_percent="5.50",
        balcony_price_factor="0.75",
        parking_price_mode="fixed",
        storage_price_mode="percentage",
    )
    assert data["name"] == "Full Policy"
    assert data["is_default"] is True
    assert data["currency"] == "USD"
    assert float(data["base_markup_percent"]) == pytest.approx(5.50, rel=1e-3)
    assert data["parking_price_mode"] == "fixed"
    assert data["storage_price_mode"] == "percentage"


def test_create_pricing_policy_duplicate_name_returns_409(client: TestClient):
    _create_pricing_policy(client, "Duplicate")
    resp = client.post(
        "/api/v1/settings/pricing-policies", json={"name": "Duplicate"}
    )
    assert resp.status_code == 409


def test_get_pricing_policy(client: TestClient):
    created = _create_pricing_policy(client, "Get Me")
    resp = client.get(f"/api/v1/settings/pricing-policies/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_pricing_policy_not_found_returns_404(client: TestClient):
    resp = client.get("/api/v1/settings/pricing-policies/nonexistent")
    assert resp.status_code == 404


def test_list_pricing_policies(client: TestClient):
    _create_pricing_policy(client, "P1")
    _create_pricing_policy(client, "P2")
    resp = client.get("/api/v1/settings/pricing-policies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2


def test_list_pricing_policies_filter_active(client: TestClient):
    _create_pricing_policy(client, "Active Policy", is_active=True)
    _create_pricing_policy(client, "Inactive Policy", is_active=False)
    resp = client.get("/api/v1/settings/pricing-policies?is_active=true")
    assert resp.status_code == 200
    body = resp.json()
    assert all(item["is_active"] for item in body["items"])


def test_update_pricing_policy(client: TestClient):
    created = _create_pricing_policy(client, "To Update")
    resp = client.patch(
        f"/api/v1/settings/pricing-policies/{created['id']}",
        json={"name": "Updated Name", "currency": "EUR"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["currency"] == "EUR"


def test_update_pricing_policy_not_found_returns_404(client: TestClient):
    resp = client.patch(
        "/api/v1/settings/pricing-policies/nonexistent",
        json={"name": "X"},
    )
    assert resp.status_code == 404


def test_update_pricing_policy_duplicate_name_returns_409(client: TestClient):
    _create_pricing_policy(client, "Name One")
    p2 = _create_pricing_policy(client, "Name Two")
    resp = client.patch(
        f"/api/v1/settings/pricing-policies/{p2['id']}",
        json={"name": "Name One"},
    )
    assert resp.status_code == 409


def test_delete_pricing_policy(client: TestClient):
    created = _create_pricing_policy(client, "To Delete")
    resp = client.delete(f"/api/v1/settings/pricing-policies/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/settings/pricing-policies/{created['id']}").status_code == 404


def test_delete_pricing_policy_not_found_returns_404(client: TestClient):
    resp = client.delete("/api/v1/settings/pricing-policies/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Single-default invariant — PricingPolicy
# ---------------------------------------------------------------------------


def test_pricing_policy_single_default_invariant(client: TestClient):
    """Setting is_default=True on a second policy clears the first."""
    first = _create_pricing_policy(client, "First Default", is_default=True)
    assert first["is_default"] is True

    second = _create_pricing_policy(client, "Second Default", is_default=True)
    assert second["is_default"] is True

    # First policy must no longer be the default
    refreshed = client.get(f"/api/v1/settings/pricing-policies/{first['id']}").json()
    assert refreshed["is_default"] is False


def test_pricing_policy_default_via_update(client: TestClient):
    """Updating is_default=True via PATCH also clears existing defaults."""
    first = _create_pricing_policy(client, "PP First", is_default=True)
    second = _create_pricing_policy(client, "PP Second")

    client.patch(
        f"/api/v1/settings/pricing-policies/{second['id']}",
        json={"is_default": True},
    )

    refreshed = client.get(f"/api/v1/settings/pricing-policies/{first['id']}").json()
    assert refreshed["is_default"] is False


def test_make_default_pricing_policy_endpoint(client: TestClient):
    """POST /{id}/make-default sets the policy as default and clears existing default."""
    first = _create_pricing_policy(client, "PP Make Default First", is_default=True)
    second = _create_pricing_policy(client, "PP Make Default Second")

    resp = client.post(
        f"/api/v1/settings/pricing-policies/{second['id']}/make-default"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_default"] is True
    assert resp.json()["id"] == second["id"]

    refreshed = client.get(f"/api/v1/settings/pricing-policies/{first['id']}").json()
    assert refreshed["is_default"] is False


def test_make_default_pricing_policy_endpoint_already_default(client: TestClient):
    """POST /{id}/make-default on an already-default policy is idempotent."""
    policy = _create_pricing_policy(client, "PP Already Default", is_default=True)
    resp = client.post(
        f"/api/v1/settings/pricing-policies/{policy['id']}/make-default"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_default"] is True


def test_make_default_pricing_policy_not_found_returns_404(client: TestClient):
    resp = client.post("/api/v1/settings/pricing-policies/nonexistent/make-default")
    assert resp.status_code == 404


def test_make_default_inactive_pricing_policy_returns_422(client: TestClient):
    """Promoting an inactive pricing policy to default must be rejected with 422."""
    policy = _create_pricing_policy(client, "PP Inactive Target", is_active=False)
    resp = client.post(
        f"/api/v1/settings/pricing-policies/{policy['id']}/make-default"
    )
    assert resp.status_code == 422, resp.text


def test_cannot_deactivate_default_pricing_policy(client: TestClient):
    """Attempting to set is_active=False on the default pricing policy returns 422."""
    policy = _create_pricing_policy(client, "PP Default Guard", is_default=True)
    resp = client.patch(
        f"/api/v1/settings/pricing-policies/{policy['id']}",
        json={"is_active": False},
    )
    assert resp.status_code == 422, resp.text


def test_can_deactivate_non_default_pricing_policy(client: TestClient):
    """A non-default policy can be deactivated without restriction."""
    policy = _create_pricing_policy(client, "PP Non-Default", is_active=True)
    resp = client.patch(
        f"/api/v1/settings/pricing-policies/{policy['id']}",
        json={"is_active": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False





def test_create_commission_policy_returns_201(client: TestClient):
    data = _create_commission_policy(client, "Standard Commission")
    assert data["name"] == "Standard Commission"
    assert data["is_default"] is False
    assert data["calculation_mode"] == "marginal"
    assert data["is_active"] is True
    assert "id" in data


def test_create_commission_policy_with_all_fields(client: TestClient):
    data = _create_commission_policy(
        client,
        name="Full Commission",
        description="All fields",
        is_default=True,
        pool_percent="5.50",
        calculation_mode="cumulative",
    )
    assert data["name"] == "Full Commission"
    assert data["is_default"] is True
    assert float(data["pool_percent"]) == pytest.approx(5.50, rel=1e-3)
    assert data["calculation_mode"] == "cumulative"


def test_create_commission_policy_duplicate_name_returns_409(client: TestClient):
    _create_commission_policy(client, "Dup Comm")
    resp = client.post(
        "/api/v1/settings/commission-policies", json={"name": "Dup Comm"}
    )
    assert resp.status_code == 409


def test_get_commission_policy(client: TestClient):
    created = _create_commission_policy(client, "Get Comm")
    resp = client.get(f"/api/v1/settings/commission-policies/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_commission_policy_not_found_returns_404(client: TestClient):
    resp = client.get("/api/v1/settings/commission-policies/nonexistent")
    assert resp.status_code == 404


def test_list_commission_policies(client: TestClient):
    _create_commission_policy(client, "CP1")
    _create_commission_policy(client, "CP2")
    resp = client.get("/api/v1/settings/commission-policies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2


def test_update_commission_policy(client: TestClient):
    created = _create_commission_policy(client, "Comm Update")
    resp = client.patch(
        f"/api/v1/settings/commission-policies/{created['id']}",
        json={"pool_percent": "10.00", "calculation_mode": "cumulative"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["pool_percent"]) == pytest.approx(10.0, rel=1e-3)
    assert data["calculation_mode"] == "cumulative"


def test_update_commission_policy_not_found_returns_404(client: TestClient):
    resp = client.patch(
        "/api/v1/settings/commission-policies/nonexistent",
        json={"name": "X"},
    )
    assert resp.status_code == 404


def test_delete_commission_policy(client: TestClient):
    created = _create_commission_policy(client, "Comm Delete")
    resp = client.delete(f"/api/v1/settings/commission-policies/{created['id']}")
    assert resp.status_code == 204
    assert (
        client.get(f"/api/v1/settings/commission-policies/{created['id']}").status_code
        == 404
    )


def test_delete_commission_policy_not_found_returns_404(client: TestClient):
    resp = client.delete("/api/v1/settings/commission-policies/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Single-default invariant — CommissionPolicy
# ---------------------------------------------------------------------------


def test_commission_policy_single_default_invariant(client: TestClient):
    first = _create_commission_policy(client, "CP Default 1", is_default=True)
    assert first["is_default"] is True

    second = _create_commission_policy(client, "CP Default 2", is_default=True)
    assert second["is_default"] is True

    refreshed = client.get(
        f"/api/v1/settings/commission-policies/{first['id']}"
    ).json()
    assert refreshed["is_default"] is False


def test_make_default_commission_policy_endpoint(client: TestClient):
    """POST /{id}/make-default sets the policy as default and clears existing default."""
    first = _create_commission_policy(client, "CP Make Default First", is_default=True)
    second = _create_commission_policy(client, "CP Make Default Second")

    resp = client.post(
        f"/api/v1/settings/commission-policies/{second['id']}/make-default"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_default"] is True
    assert resp.json()["id"] == second["id"]

    refreshed = client.get(
        f"/api/v1/settings/commission-policies/{first['id']}"
    ).json()
    assert refreshed["is_default"] is False


def test_make_default_commission_policy_endpoint_already_default(client: TestClient):
    """POST /{id}/make-default on an already-default policy is idempotent."""
    policy = _create_commission_policy(client, "CP Already Default", is_default=True)
    resp = client.post(
        f"/api/v1/settings/commission-policies/{policy['id']}/make-default"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_default"] is True


def test_make_default_commission_policy_not_found_returns_404(client: TestClient):
    resp = client.post(
        "/api/v1/settings/commission-policies/nonexistent/make-default"
    )
    assert resp.status_code == 404


def test_make_default_inactive_commission_policy_returns_422(client: TestClient):
    """Promoting an inactive commission policy to default must be rejected with 422."""
    policy = _create_commission_policy(client, "CP Inactive Target", is_active=False)
    resp = client.post(
        f"/api/v1/settings/commission-policies/{policy['id']}/make-default"
    )
    assert resp.status_code == 422, resp.text


def test_cannot_deactivate_default_commission_policy(client: TestClient):
    """Attempting to set is_active=False on the default commission policy returns 422."""
    policy = _create_commission_policy(client, "CP Default Guard", is_default=True)
    resp = client.patch(
        f"/api/v1/settings/commission-policies/{policy['id']}",
        json={"is_active": False},
    )
    assert resp.status_code == 422, resp.text


def test_can_deactivate_non_default_commission_policy(client: TestClient):
    """A non-default policy can be deactivated without restriction."""
    policy = _create_commission_policy(client, "CP Non-Default", is_active=True)
    resp = client.patch(
        f"/api/v1/settings/commission-policies/{policy['id']}",
        json={"is_active": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False





def test_create_project_template_returns_201(client: TestClient):
    data = _create_project_template(client, "Basic Template")
    assert data["name"] == "Basic Template"
    assert data["default_pricing_policy_id"] is None
    assert data["default_commission_policy_id"] is None
    assert data["default_currency"] == "AED"
    assert data["is_active"] is True
    assert "id" in data


def test_create_project_template_with_policy_refs(client: TestClient):
    pp = _create_pricing_policy(client, "PP For Template")
    cp = _create_commission_policy(client, "CP For Template")
    data = _create_project_template(
        client,
        name="Full Template",
        default_pricing_policy_id=pp["id"],
        default_commission_policy_id=cp["id"],
        default_currency="USD",
    )
    assert data["default_pricing_policy_id"] == pp["id"]
    assert data["default_commission_policy_id"] == cp["id"]
    assert data["default_currency"] == "USD"


def test_create_project_template_invalid_pricing_policy_returns_404(
    client: TestClient,
):
    resp = client.post(
        "/api/v1/settings/project-templates",
        json={"name": "Bad Template", "default_pricing_policy_id": "nonexistent"},
    )
    assert resp.status_code == 404


def test_create_project_template_invalid_commission_policy_returns_404(
    client: TestClient,
):
    resp = client.post(
        "/api/v1/settings/project-templates",
        json={
            "name": "Bad Template 2",
            "default_commission_policy_id": "nonexistent",
        },
    )
    assert resp.status_code == 404


def test_create_project_template_duplicate_name_returns_409(client: TestClient):
    _create_project_template(client, "Dup Template")
    resp = client.post(
        "/api/v1/settings/project-templates", json={"name": "Dup Template"}
    )
    assert resp.status_code == 409


def test_get_project_template(client: TestClient):
    created = _create_project_template(client, "Get Template")
    resp = client.get(f"/api/v1/settings/project-templates/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_project_template_not_found_returns_404(client: TestClient):
    resp = client.get("/api/v1/settings/project-templates/nonexistent")
    assert resp.status_code == 404


def test_list_project_templates(client: TestClient):
    _create_project_template(client, "T1")
    _create_project_template(client, "T2")
    resp = client.get("/api/v1/settings/project-templates")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2


def test_list_project_templates_filter_active(client: TestClient):
    _create_project_template(client, "Active Tmpl", is_active=True)
    _create_project_template(client, "Inactive Tmpl", is_active=False)
    resp = client.get("/api/v1/settings/project-templates?is_active=true")
    assert resp.status_code == 200
    body = resp.json()
    assert all(item["is_active"] for item in body["items"])


def test_update_project_template(client: TestClient):
    created = _create_project_template(client, "Tmpl Update")
    resp = client.patch(
        f"/api/v1/settings/project-templates/{created['id']}",
        json={"name": "Updated Tmpl", "default_currency": "GBP"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Tmpl"
    assert data["default_currency"] == "GBP"


def test_update_project_template_set_policy_ref(client: TestClient):
    tmpl = _create_project_template(client, "Ref Update Tmpl")
    pp = _create_pricing_policy(client, "PP Ref Update")
    resp = client.patch(
        f"/api/v1/settings/project-templates/{tmpl['id']}",
        json={"default_pricing_policy_id": pp["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["default_pricing_policy_id"] == pp["id"]


def test_update_project_template_invalid_policy_ref_returns_404(client: TestClient):
    tmpl = _create_project_template(client, "Bad Ref Tmpl")
    resp = client.patch(
        f"/api/v1/settings/project-templates/{tmpl['id']}",
        json={"default_pricing_policy_id": "nonexistent"},
    )
    assert resp.status_code == 404


def test_update_project_template_not_found_returns_404(client: TestClient):
    resp = client.patch(
        "/api/v1/settings/project-templates/nonexistent",
        json={"name": "X"},
    )
    assert resp.status_code == 404


def test_delete_project_template(client: TestClient):
    created = _create_project_template(client, "Tmpl Delete")
    resp = client.delete(f"/api/v1/settings/project-templates/{created['id']}")
    assert resp.status_code == 204
    assert (
        client.get(f"/api/v1/settings/project-templates/{created['id']}").status_code
        == 404
    )


def test_delete_project_template_not_found_returns_404(client: TestClient):
    resp = client.delete("/api/v1/settings/project-templates/nonexistent")
    assert resp.status_code == 404


# ===========================================================================
# Cross-entity: template survives independent policy deletion (Postgres SET NULL)
# ===========================================================================


def test_deleting_pricing_policy_template_remains_accessible(client: TestClient):
    """Deleting a pricing policy must not cascade-delete templates.

    The FK is defined as SET NULL in PostgreSQL.  In the SQLite test
    environment FK constraints are not enforced, so we only verify that
    the template record itself still exists after the policy is deleted.
    """
    pp = _create_pricing_policy(client, "PP To Remove")
    tmpl = _create_project_template(
        client,
        name="Tmpl With PP",
        default_pricing_policy_id=pp["id"],
    )
    assert tmpl["default_pricing_policy_id"] == pp["id"]

    # Delete the pricing policy
    del_resp = client.delete(f"/api/v1/settings/pricing-policies/{pp['id']}")
    assert del_resp.status_code == 204

    # Template record must still be accessible (no cascade delete)
    tmpl_resp = client.get(f"/api/v1/settings/project-templates/{tmpl['id']}")
    assert tmpl_resp.status_code == 200
