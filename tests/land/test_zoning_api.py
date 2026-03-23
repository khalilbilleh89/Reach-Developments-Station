"""
Tests for the Land Zoning API endpoint.

Validates POST /api/v1/land/zoning/evaluate:
- valid evaluation
- invalid parameters
- negative/zero area validation
- missing required fields
- setback effects visible in response
- parking and unit capacity outputs
"""

import pytest
from fastapi.testclient import TestClient


def _zoning_payload(**overrides) -> dict:
    """Return a valid zoning evaluation request payload with optional overrides."""
    base: dict = {
        "land_area": 10_000.0,
        "far": 3.5,
        "coverage_ratio": 0.6,
        "max_height_m": 45.0,
        "floor_height_m": 3.0,
        "parking_ratio": 1.2,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Valid evaluation
# ---------------------------------------------------------------------------

def test_zoning_evaluate_status_ok(client: TestClient):
    """POST /land/zoning/evaluate returns 200 for a valid request."""
    resp = client.post("/api/v1/land/zoning/evaluate", json=_zoning_payload())
    assert resp.status_code == 200


def test_zoning_evaluate_all_fields_present(client: TestClient):
    """Response must include all required output fields."""
    resp = client.post("/api/v1/land/zoning/evaluate", json=_zoning_payload())
    assert resp.status_code == 200
    body = resp.json()

    for field in (
        "max_buildable_area",
        "max_footprint_area",
        "max_floors",
        "setback_adjusted_area",
        "effective_footprint",
        "effective_buildable_area",
        "estimated_unit_capacity",
        "parking_required",
    ):
        assert field in body, f"Missing field: {field}"


def test_zoning_evaluate_correct_far_limit(client: TestClient):
    """FAR-limited scenario: effective_buildable_area == max_buildable_area.

    land_area=10000, FAR=3.5  → max_buildable = 35 000
    coverage=0.6, height=45m, floor=3m → footprint×floors = 6000×15 = 90 000
    FAR binds → effective = 35 000.
    """
    resp = client.post("/api/v1/land/zoning/evaluate", json=_zoning_payload())
    assert resp.status_code == 200
    body = resp.json()

    assert body["max_buildable_area"] == pytest.approx(35_000.0)
    assert body["max_footprint_area"] == pytest.approx(6_000.0)
    assert body["max_floors"] == 15
    assert body["effective_buildable_area"] == pytest.approx(35_000.0)


def test_zoning_evaluate_height_limited(client: TestClient):
    """Height-limited scenario: low height cap constrains effective buildable area."""
    resp = client.post(
        "/api/v1/land/zoning/evaluate",
        json=_zoning_payload(max_height_m=9.0, floor_height_m=3.0),
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["max_floors"] == 3
    # 6000 × 3 = 18 000 < 35 000 → height binds
    assert body["effective_buildable_area"] == pytest.approx(18_000.0)


def test_zoning_evaluate_coverage_limited(client: TestClient):
    """Low coverage ratio drives effective buildable area lower."""
    resp_high = client.post("/api/v1/land/zoning/evaluate", json=_zoning_payload(coverage_ratio=0.6))
    resp_low = client.post("/api/v1/land/zoning/evaluate", json=_zoning_payload(coverage_ratio=0.1))
    assert resp_high.status_code == 200
    assert resp_low.status_code == 200

    assert resp_high.json()["max_footprint_area"] > resp_low.json()["max_footprint_area"]


def test_zoning_evaluate_with_unit_size_returns_capacity(client: TestClient):
    """Providing avg_unit_size_sqm yields estimated_unit_capacity and parking."""
    payload = _zoning_payload(avg_unit_size_sqm=100.0, parking_ratio=1.2)
    resp = client.post("/api/v1/land/zoning/evaluate", json=payload)
    assert resp.status_code == 200
    body = resp.json()

    assert body["estimated_unit_capacity"] == 350
    assert body["parking_required"] == 420


def test_zoning_evaluate_without_unit_size_null_capacity(client: TestClient):
    """Without avg_unit_size_sqm, estimated_unit_capacity is null and parking is 0."""
    resp = client.post("/api/v1/land/zoning/evaluate", json=_zoning_payload())
    assert resp.status_code == 200
    body = resp.json()

    assert body["estimated_unit_capacity"] is None
    assert body["parking_required"] == 0


# ---------------------------------------------------------------------------
# Setback effects visible in response
# ---------------------------------------------------------------------------

def test_zoning_evaluate_setbacks_reduce_footprint(client: TestClient):
    """Setbacks reduce effective_footprint and effective_buildable_area.

    Using far=10 so that height×footprint is the binding constraint,
    allowing setbacks to actually reduce effective_buildable_area.
    """
    no_setback = client.post("/api/v1/land/zoning/evaluate", json=_zoning_payload(far=10.0))
    with_setback = client.post(
        "/api/v1/land/zoning/evaluate",
        json=_zoning_payload(far=10.0, setback_front=5.0, setback_side=3.0, setback_rear=5.0),
    )
    assert no_setback.status_code == 200
    assert with_setback.status_code == 200

    assert (
        with_setback.json()["effective_footprint"]
        < no_setback.json()["effective_footprint"]
    )
    assert (
        with_setback.json()["effective_buildable_area"]
        < no_setback.json()["effective_buildable_area"]
    )


def test_zoning_evaluate_setback_adjusted_area_reported(client: TestClient):
    """setback_adjusted_area is correctly computed and returned."""
    resp = client.post(
        "/api/v1/land/zoning/evaluate",
        json=_zoning_payload(setback_front=5.0, setback_side=3.0, setback_rear=5.0),
    )
    assert resp.status_code == 200
    # 100×100 plot: depth=90, width=94 → 8460
    assert resp.json()["setback_adjusted_area"] == pytest.approx(8_460.0)


# ---------------------------------------------------------------------------
# Invalid parameters
# ---------------------------------------------------------------------------

def test_zoning_evaluate_negative_land_area_rejected(client: TestClient):
    """Negative land area is rejected with 422."""
    resp = client.post(
        "/api/v1/land/zoning/evaluate",
        json=_zoning_payload(land_area=-1.0),
    )
    assert resp.status_code == 422


def test_zoning_evaluate_zero_land_area_rejected(client: TestClient):
    """Zero land area is rejected with 422."""
    resp = client.post(
        "/api/v1/land/zoning/evaluate",
        json=_zoning_payload(land_area=0.0),
    )
    assert resp.status_code == 422


def test_zoning_evaluate_zero_far_rejected(client: TestClient):
    """Zero FAR is rejected with 422."""
    resp = client.post(
        "/api/v1/land/zoning/evaluate",
        json=_zoning_payload(far=0.0),
    )
    assert resp.status_code == 422


def test_zoning_evaluate_coverage_above_one_rejected(client: TestClient):
    """Coverage ratio > 1 is rejected with 422."""
    resp = client.post(
        "/api/v1/land/zoning/evaluate",
        json=_zoning_payload(coverage_ratio=1.1),
    )
    assert resp.status_code == 422


def test_zoning_evaluate_zero_coverage_rejected(client: TestClient):
    """Zero coverage_ratio is rejected with 422."""
    resp = client.post(
        "/api/v1/land/zoning/evaluate",
        json=_zoning_payload(coverage_ratio=0.0),
    )
    assert resp.status_code == 422


def test_zoning_evaluate_negative_parking_ratio_rejected(client: TestClient):
    """Negative parking ratio is rejected with 422."""
    resp = client.post(
        "/api/v1/land/zoning/evaluate",
        json=_zoning_payload(parking_ratio=-0.5),
    )
    assert resp.status_code == 422


def test_zoning_evaluate_zero_floor_height_rejected(client: TestClient):
    """Zero floor_height_m is rejected with 422 (schema gt=0)."""
    resp = client.post(
        "/api/v1/land/zoning/evaluate",
        json=_zoning_payload(floor_height_m=0.0),
    )
    assert resp.status_code == 422


def test_zoning_evaluate_negative_unit_size_rejected(client: TestClient):
    """Negative avg_unit_size_sqm is rejected with 422."""
    resp = client.post(
        "/api/v1/land/zoning/evaluate",
        json=_zoning_payload(avg_unit_size_sqm=-50.0),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

def test_zoning_evaluate_missing_land_area(client: TestClient):
    """Missing land_area field returns 422."""
    payload = _zoning_payload()
    payload.pop("land_area")
    resp = client.post("/api/v1/land/zoning/evaluate", json=payload)
    assert resp.status_code == 422


def test_zoning_evaluate_missing_far(client: TestClient):
    """Missing far field returns 422."""
    payload = _zoning_payload()
    payload.pop("far")
    resp = client.post("/api/v1/land/zoning/evaluate", json=payload)
    assert resp.status_code == 422


def test_zoning_evaluate_missing_coverage_ratio(client: TestClient):
    """Missing coverage_ratio field returns 422."""
    payload = _zoning_payload()
    payload.pop("coverage_ratio")
    resp = client.post("/api/v1/land/zoning/evaluate", json=payload)
    assert resp.status_code == 422


def test_zoning_evaluate_missing_max_height(client: TestClient):
    """Missing max_height_m field returns 422."""
    payload = _zoning_payload()
    payload.pop("max_height_m")
    resp = client.post("/api/v1/land/zoning/evaluate", json=payload)
    assert resp.status_code == 422


def test_zoning_evaluate_missing_floor_height(client: TestClient):
    """Missing floor_height_m field returns 422."""
    payload = _zoning_payload()
    payload.pop("floor_height_m")
    resp = client.post("/api/v1/land/zoning/evaluate", json=payload)
    assert resp.status_code == 422


def test_zoning_evaluate_missing_parking_ratio(client: TestClient):
    """Missing parking_ratio field returns 422."""
    payload = _zoning_payload()
    payload.pop("parking_ratio")
    resp = client.post("/api/v1/land/zoning/evaluate", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Setback defaults to zero
# ---------------------------------------------------------------------------

def test_zoning_evaluate_setbacks_default_to_zero(client: TestClient):
    """Omitting setback fields defaults to 0 and preserves full land area."""
    payload = _zoning_payload()
    # No setback fields supplied
    resp = client.post("/api/v1/land/zoning/evaluate", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["setback_adjusted_area"] == pytest.approx(10_000.0)
