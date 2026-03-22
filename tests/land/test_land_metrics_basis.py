"""
tests/land/test_land_metrics_basis.py

Integration tests for the Land Metrics & Basis Engine (PR-LAND-002).

Validates that:
  - LandParcelResponse includes computed basis metrics
  - Effective land basis (including transaction costs) is computed correctly
  - Buildable / sellable price-per-sqm metrics are conditionally populated
  - Null-safe behavior when inputs are incomplete
  - API endpoints return metrics on create / get / update
  - Asking price vs effective basis distinction is preserved
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_parcel(client: TestClient, *, code: str = "PCL-M001", **extra) -> dict:
    body = {"parcel_name": "Metrics Test Parcel", "parcel_code": code}
    body.update(extra)
    resp = client.post("/api/v1/land/parcels", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Always-computable metrics
# ---------------------------------------------------------------------------


def test_parcel_with_acquisition_price_returns_effective_basis(client: TestClient):
    """effective_land_basis = acquisition_price + transaction_cost."""
    # acquisition_price=5_000_000, transaction_cost=250_000 → effective=5_250_000
    parcel = _create_parcel(
        client,
        code="PCL-MB-001",
        land_area_sqm=1000.0,
        acquisition_price=5_000_000.0,
        transaction_cost=250_000.0,
    )
    assert parcel["effective_land_basis"] == pytest.approx(5_250_000.0)


def test_parcel_without_transaction_cost_effective_basis_equals_acquisition(client: TestClient):
    """When transaction_cost is absent, effective_land_basis equals acquisition_price."""
    parcel = _create_parcel(
        client,
        code="PCL-MB-002",
        land_area_sqm=1000.0,
        acquisition_price=5_000_000.0,
    )
    assert parcel["effective_land_basis"] == pytest.approx(5_000_000.0)


def test_parcel_without_acquisition_price_has_null_metrics(client: TestClient):
    """When acquisition_price is absent, all computed metrics must be null."""
    parcel = _create_parcel(
        client,
        code="PCL-MB-003",
        land_area_sqm=1000.0,
    )
    assert parcel["effective_land_basis"] is None
    assert parcel["gross_land_price_per_sqm"] is None
    assert parcel["effective_land_price_per_gross_sqm"] is None
    assert parcel["effective_land_price_per_buildable_sqm"] is None
    assert parcel["effective_land_price_per_sellable_sqm"] is None


def test_gross_land_price_per_sqm_computed_correctly(client: TestClient):
    """gross_land_price_per_sqm = acquisition_price / land_area_sqm."""
    # 5_000_000 / 1000 = 5000
    parcel = _create_parcel(
        client,
        code="PCL-MB-004",
        land_area_sqm=1000.0,
        acquisition_price=5_000_000.0,
    )
    assert parcel["gross_land_price_per_sqm"] == pytest.approx(5_000.0)


def test_effective_land_price_per_gross_sqm_includes_transaction_cost(client: TestClient):
    """effective_land_price_per_gross_sqm uses effective basis, not just acquisition price."""
    # effective_basis = 5_000_000 + 500_000 = 5_500_000
    # 5_500_000 / 1000 = 5500
    parcel = _create_parcel(
        client,
        code="PCL-MB-005",
        land_area_sqm=1000.0,
        acquisition_price=5_000_000.0,
        transaction_cost=500_000.0,
    )
    assert parcel["gross_land_price_per_sqm"] == pytest.approx(5_000.0)
    assert parcel["effective_land_price_per_gross_sqm"] == pytest.approx(5_500.0)


def test_gross_price_per_sqm_null_when_no_land_area(client: TestClient):
    """gross_land_price_per_sqm is null when land_area_sqm is absent."""
    parcel = _create_parcel(
        client,
        code="PCL-MB-006",
        acquisition_price=5_000_000.0,
    )
    assert parcel["gross_land_price_per_sqm"] is None
    assert parcel["effective_land_price_per_gross_sqm"] is None


# ---------------------------------------------------------------------------
# Conditionally computable: buildable / sellable sqm
# ---------------------------------------------------------------------------


def test_buildable_basis_computed_when_buildable_area_provided(client: TestClient):
    """effective_land_price_per_buildable_sqm is populated when buildable_area_sqm > 0."""
    # effective_basis = 5_000_000 + 500_000 = 5_500_000
    # 5_500_000 / 2500 = 2200
    parcel = _create_parcel(
        client,
        code="PCL-MB-007",
        land_area_sqm=1000.0,
        buildable_area_sqm=2500.0,
        acquisition_price=5_000_000.0,
        transaction_cost=500_000.0,
    )
    assert parcel["effective_land_price_per_buildable_sqm"] == pytest.approx(2_200.0)


def test_buildable_basis_null_when_buildable_area_absent(client: TestClient):
    """effective_land_price_per_buildable_sqm is null when buildable_area_sqm is absent."""
    parcel = _create_parcel(
        client,
        code="PCL-MB-008",
        land_area_sqm=1000.0,
        acquisition_price=5_000_000.0,
    )
    assert parcel["effective_land_price_per_buildable_sqm"] is None


def test_sellable_basis_computed_when_sellable_area_provided(client: TestClient):
    """effective_land_price_per_sellable_sqm is populated when sellable_area_sqm > 0."""
    # effective_basis = 5_000_000 (no transaction cost)
    # 5_000_000 / 2000 = 2500
    parcel = _create_parcel(
        client,
        code="PCL-MB-009",
        land_area_sqm=1000.0,
        buildable_area_sqm=2500.0,
        sellable_area_sqm=2000.0,
        acquisition_price=5_000_000.0,
    )
    assert parcel["effective_land_price_per_sellable_sqm"] == pytest.approx(2_500.0)


def test_sellable_basis_null_when_sellable_area_absent(client: TestClient):
    """effective_land_price_per_sellable_sqm is null when sellable_area_sqm is absent."""
    parcel = _create_parcel(
        client,
        code="PCL-MB-010",
        land_area_sqm=1000.0,
        buildable_area_sqm=2500.0,
        acquisition_price=5_000_000.0,
    )
    assert parcel["effective_land_price_per_sellable_sqm"] is None


# ---------------------------------------------------------------------------
# Transaction cost materially changes effective basis
# ---------------------------------------------------------------------------


def test_transaction_cost_materially_changes_effective_basis(client: TestClient):
    """A 10 % transaction cost significantly impacts the effective land basis."""
    # Without transaction cost
    parcel_no_tc = _create_parcel(
        client,
        code="PCL-MB-011",
        land_area_sqm=1000.0,
        acquisition_price=10_000_000.0,
        transaction_cost=0.0,
    )
    # With 10 % transaction cost
    parcel_with_tc = _create_parcel(
        client,
        code="PCL-MB-012",
        land_area_sqm=1000.0,
        acquisition_price=10_000_000.0,
        transaction_cost=1_000_000.0,
    )
    assert parcel_with_tc["effective_land_basis"] > parcel_no_tc["effective_land_basis"]
    assert parcel_with_tc["effective_land_price_per_gross_sqm"] > parcel_no_tc["effective_land_price_per_gross_sqm"]


# ---------------------------------------------------------------------------
# Asking price vs effective basis distinction
# ---------------------------------------------------------------------------


def test_asking_price_and_effective_basis_are_distinct_concepts(client: TestClient):
    """asking_price_per_sqm is a stored input; effective basis is derived output.

    These must never be conflated. Asking price is what the seller wants;
    effective land basis is what the developer actually pays (acquisition + costs).
    """
    # asking 6000/sqm but actual acquisition at 5000/sqm with 500K transaction cost
    parcel = _create_parcel(
        client,
        code="PCL-MB-013",
        land_area_sqm=1000.0,
        acquisition_price=5_000_000.0,
        transaction_cost=500_000.0,
        asking_price_per_sqm=6_000.0,
    )
    assert parcel["asking_price_per_sqm"] == pytest.approx(6_000.0)
    assert parcel["gross_land_price_per_sqm"] == pytest.approx(5_000.0)
    assert parcel["effective_land_price_per_gross_sqm"] == pytest.approx(5_500.0)
    # effective basis should differ from asking price
    assert parcel["effective_land_price_per_gross_sqm"] != parcel["asking_price_per_sqm"]


# ---------------------------------------------------------------------------
# Metrics on GET, PATCH, and list endpoints
# ---------------------------------------------------------------------------


def test_get_parcel_returns_computed_metrics(client: TestClient):
    """GET /land/parcels/{id} must return computed basis metrics."""
    parcel = _create_parcel(
        client,
        code="PCL-MB-014",
        land_area_sqm=1000.0,
        acquisition_price=5_000_000.0,
        transaction_cost=250_000.0,
    )
    parcel_id = parcel["id"]

    resp = client.get(f"/api/v1/land/parcels/{parcel_id}")
    assert resp.status_code == 200
    body = resp.json()

    assert body["effective_land_basis"] == pytest.approx(5_250_000.0)
    assert body["gross_land_price_per_sqm"] == pytest.approx(5_000.0)
    assert body["effective_land_price_per_gross_sqm"] == pytest.approx(5_250.0)


def test_update_parcel_recalculates_metrics(client: TestClient):
    """PATCH /land/parcels/{id} must return recalculated metrics reflecting new inputs."""
    parcel = _create_parcel(
        client,
        code="PCL-MB-015",
        land_area_sqm=1000.0,
        acquisition_price=5_000_000.0,
    )
    parcel_id = parcel["id"]

    # Initial effective basis = 5_000_000 (no transaction cost)
    assert parcel["effective_land_basis"] == pytest.approx(5_000_000.0)

    # Update: add transaction_cost
    resp = client.patch(
        f"/api/v1/land/parcels/{parcel_id}",
        json={"transaction_cost": 500_000.0},
    )
    assert resp.status_code == 200
    updated = resp.json()

    # Effective basis must now reflect the transaction cost
    assert updated["effective_land_basis"] == pytest.approx(5_500_000.0)
    assert updated["effective_land_price_per_gross_sqm"] == pytest.approx(5_500.0)


def test_list_parcels_includes_metrics(client: TestClient):
    """GET /land/parcels must include computed metrics in list items."""
    parcel = _create_parcel(
        client,
        code="PCL-MB-016",
        land_area_sqm=1000.0,
        acquisition_price=5_000_000.0,
        transaction_cost=250_000.0,
    )
    parcel_id = parcel["id"]

    resp = client.get("/api/v1/land/parcels")
    assert resp.status_code == 200
    items = resp.json()["items"]

    matching = [p for p in items if p["id"] == parcel_id]
    assert len(matching) == 1
    assert matching[0]["effective_land_basis"] == pytest.approx(5_250_000.0)
    assert matching[0]["gross_land_price_per_sqm"] == pytest.approx(5_000.0)


# ---------------------------------------------------------------------------
# Full metric set: parcel with buildable and sellable areas
# ---------------------------------------------------------------------------


def test_full_metric_set_with_all_areas(client: TestClient):
    """A parcel with all area inputs gets the complete basis metric set."""
    # land=1000, acquisition=5M, transaction=500K, buildable=2500, sellable=2000
    parcel = _create_parcel(
        client,
        code="PCL-MB-017",
        land_area_sqm=1000.0,
        buildable_area_sqm=2500.0,
        sellable_area_sqm=2000.0,
        acquisition_price=5_000_000.0,
        transaction_cost=500_000.0,
    )

    assert parcel["effective_land_basis"] == pytest.approx(5_500_000.0)
    assert parcel["gross_land_price_per_sqm"] == pytest.approx(5_000.0)  # acq/land
    assert parcel["effective_land_price_per_gross_sqm"] == pytest.approx(5_500.0)  # eff/land
    assert parcel["effective_land_price_per_buildable_sqm"] == pytest.approx(2_200.0)  # eff/buildable
    assert parcel["effective_land_price_per_sellable_sqm"] == pytest.approx(2_750.0)  # eff/sellable


# ---------------------------------------------------------------------------
# RLV / supported acquisition price from engine valuation
# ---------------------------------------------------------------------------


def test_supported_acquisition_price_null_without_valuation(client: TestClient):
    """supported_acquisition_price is null when no engine valuation has been run."""
    parcel = _create_parcel(
        client,
        code="PCL-MB-018",
        land_area_sqm=1000.0,
        acquisition_price=5_000_000.0,
    )
    assert parcel["supported_acquisition_price"] is None
    assert parcel["residual_land_value"] is None
    assert parcel["margin_impact"] is None


def test_supported_acquisition_price_populated_after_engine_valuation(client: TestClient):
    """supported_acquisition_price is populated after running the valuation engine."""
    parcel = _create_parcel(
        client,
        code="PCL-MB-019",
        land_area_sqm=1000.0,
        acquisition_price=5_000_000.0,
    )
    parcel_id = parcel["id"]

    # Run valuation engine
    resp = client.post(
        f"/api/v1/land/parcels/{parcel_id}/valuation",
        json={
            "scenario_name": "Base",
            "gdv": 20_000_000.0,
            "construction_cost": 12_000_000.0,
            "soft_cost_percentage": 0.05,
            "developer_margin_target": 0.20,
            "sellable_area_sqm": 2000.0,
        },
    )
    assert resp.status_code == 201

    # Get parcel detail — should now include RLV metrics
    detail = client.get(f"/api/v1/land/parcels/{parcel_id}").json()
    assert detail["supported_acquisition_price"] is not None
    assert detail["residual_land_value"] is not None
    assert detail["margin_impact"] is not None
