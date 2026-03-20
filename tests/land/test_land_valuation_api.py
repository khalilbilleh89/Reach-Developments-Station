"""
Tests for the land valuation engine API endpoint.

Validates POST /api/v1/land/parcels/{parcel_id}/valuation behaviour:
correct residual land value, negative valuation detection, margin sensitivity,
404 on unknown parcel, and persistence of results.
"""

import pytest
from fastapi.testclient import TestClient


def _create_parcel(client: TestClient, code: str = "PCL-ENG-001", project_id: str | None = None) -> str:
    payload: dict = {
        "parcel_name": "Engine Test Parcel",
        "parcel_code": code,
        "land_area_sqm": 10000.0,
        "permitted_far": 2.5,
    }
    if project_id:
        payload["project_id"] = project_id
    resp = client.post("/api/v1/land/parcels", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def _engine_payload(**overrides) -> dict:
    """Return a valid engine request payload with optional field overrides."""
    base = {
        "scenario_name": "Base Case",
        "gdv": 20_000_000.0,
        "construction_cost": 10_000_000.0,
        "soft_cost_percentage": 0.10,
        "developer_margin_target": 0.20,
        "sellable_area_sqm": 10_000.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Correct residual land value
# ---------------------------------------------------------------------------

def test_run_valuation_engine_correct_residual(client: TestClient):
    """POST /valuation should compute correct residual land value and persist it.

    GDV        = 20 000 000
    Constr.    = 10 000 000
    Soft (10%) =  1 000 000
    Total cost = 11 000 000
    Margin 20% =  4 000 000
    Land value =  5 000 000
    LV / sqm   =    500.00
    Max bid    =  5 000 000
    Residual % =      0.25
    """
    parcel_id = _create_parcel(client, code="PCL-ENG-CALC")
    resp = client.post(f"/api/v1/land/parcels/{parcel_id}/valuation", json=_engine_payload())
    assert resp.status_code == 201
    body = resp.json()

    assert body["parcel_id"] == parcel_id
    assert body["scenario_name"] == "Base Case"
    assert body["expected_gdv"] == pytest.approx(20_000_000.0, rel=1e-3)
    assert body["expected_cost"] == pytest.approx(11_000_000.0, rel=1e-3)
    assert body["residual_land_value"] == pytest.approx(5_000_000.0, rel=1e-3)
    assert body["land_value_per_sqm"] == pytest.approx(500.0, rel=1e-3)
    assert body["max_land_bid"] == pytest.approx(5_000_000.0, rel=1e-3)
    assert body["residual_margin"] == pytest.approx(0.25, rel=1e-3)
    assert body["valuation_date"] is not None
    assert body["valuation_inputs"] is not None
    assert body["id"] is not None


def test_run_valuation_engine_response_fields_present(client: TestClient):
    """Response must include all engine output fields."""
    parcel_id = _create_parcel(client, code="PCL-ENG-FIELDS")
    resp = client.post(f"/api/v1/land/parcels/{parcel_id}/valuation", json=_engine_payload())
    assert resp.status_code == 201
    body = resp.json()

    for field in ("residual_land_value", "land_value_per_sqm", "max_land_bid", "residual_margin"):
        assert field in body, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Negative valuation detection
# ---------------------------------------------------------------------------

def test_run_valuation_engine_negative_land_value(client: TestClient):
    """Engine returns negative land value when costs exceed GDV minus margin."""
    parcel_id = _create_parcel(client, code="PCL-ENG-NEG")
    # High construction cost relative to GDV → negative residual
    payload = _engine_payload(
        gdv=10_000_000.0,
        construction_cost=9_000_000.0,
        soft_cost_percentage=0.10,
        developer_margin_target=0.20,
        sellable_area_sqm=5_000.0,
    )
    resp = client.post(f"/api/v1/land/parcels/{parcel_id}/valuation", json=payload)
    assert resp.status_code == 201
    body = resp.json()

    assert body["residual_land_value"] < 0
    assert body["max_land_bid"] < 0
    assert body["residual_margin"] < 0


# ---------------------------------------------------------------------------
# Margin sensitivity
# ---------------------------------------------------------------------------

def test_run_valuation_engine_margin_sensitivity(client: TestClient):
    """Higher developer margin target yields a lower residual land value."""
    parcel_id = _create_parcel(client, code="PCL-ENG-MARGIN")

    base_resp = client.post(
        f"/api/v1/land/parcels/{parcel_id}/valuation",
        json=_engine_payload(scenario_name="Low Margin", developer_margin_target=0.10),
    )
    high_resp = client.post(
        f"/api/v1/land/parcels/{parcel_id}/valuation",
        json=_engine_payload(scenario_name="High Margin", developer_margin_target=0.30),
    )
    assert base_resp.status_code == 201
    assert high_resp.status_code == 201

    base_rlv = base_resp.json()["residual_land_value"]
    high_rlv = high_resp.json()["residual_land_value"]
    assert base_rlv > high_rlv


# ---------------------------------------------------------------------------
# 404 on unknown parcel
# ---------------------------------------------------------------------------

def test_run_valuation_engine_404_unknown_parcel(client: TestClient):
    """POST /valuation for a non-existent parcel returns 404."""
    resp = client.post(
        "/api/v1/land/parcels/no-such-parcel/valuation",
        json=_engine_payload(),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Persistence — result appears in list_valuations
# ---------------------------------------------------------------------------

def test_run_valuation_engine_result_in_list(client: TestClient):
    """Engine valuation result is persisted and appears in GET /valuations."""
    parcel_id = _create_parcel(client, code="PCL-ENG-PERSIST")
    client.post(f"/api/v1/land/parcels/{parcel_id}/valuation", json=_engine_payload(scenario_name="Persisted"))
    list_resp = client.get(f"/api/v1/land/parcels/{parcel_id}/valuations")
    assert list_resp.status_code == 200
    valuations = list_resp.json()
    names = [v["scenario_name"] for v in valuations]
    assert "Persisted" in names


# ---------------------------------------------------------------------------
# Valuation inputs snapshot
# ---------------------------------------------------------------------------

def test_run_valuation_engine_inputs_snapshot(client: TestClient):
    """valuation_inputs field stores the engine inputs used."""
    parcel_id = _create_parcel(client, code="PCL-ENG-SNAP")
    payload = _engine_payload(
        gdv=15_000_000.0,
        construction_cost=8_000_000.0,
        soft_cost_percentage=0.12,
        developer_margin_target=0.18,
        sellable_area_sqm=6_000.0,
    )
    resp = client.post(f"/api/v1/land/parcels/{parcel_id}/valuation", json=payload)
    assert resp.status_code == 201
    inputs_snap = resp.json()["valuation_inputs"]
    assert inputs_snap is not None
    assert inputs_snap["gdv"] == 15_000_000.0
    assert inputs_snap["construction_cost"] == 8_000_000.0
    assert inputs_snap["soft_cost_percentage"] == pytest.approx(0.12)
    assert inputs_snap["developer_margin_target"] == pytest.approx(0.18)
    assert inputs_snap["sellable_area_sqm"] == 6_000.0


# ---------------------------------------------------------------------------
# Standalone parcel (no project)
# ---------------------------------------------------------------------------

def test_run_valuation_engine_standalone_parcel(client: TestClient):
    """Engine endpoint works for a standalone parcel not linked to a project."""
    parcel_id = _create_parcel(client, code="PCL-ENG-SA")
    resp = client.post(f"/api/v1/land/parcels/{parcel_id}/valuation", json=_engine_payload())
    assert resp.status_code == 201
    assert resp.json()["parcel_id"] == parcel_id
