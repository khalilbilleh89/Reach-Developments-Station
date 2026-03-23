"""
Tests for the Land Parcel Aggregation Engine.

Validates individual calculation rules and the full ``aggregate_parcels``
function across common developer assembly scenarios:

- area / frontage sum
- acquisition price / transaction cost sum
- effective land basis calculation
- area-weighted permitted FAR
- zoning category analysis (uniform, mixed, absent)
- infrastructure flags (utilities, corner plot)
- empty parcel list rejection
- duplicate detection (responsibility of caller — engine trusts inputs)
- single-parcel assembly
- recomputation stability (deterministic outputs)
"""

import pytest

from app.modules.land.aggregation_engine import (
    AssemblyAggregationResult,
    ParcelMetrics,
    aggregate_parcels,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _parcel(**overrides) -> ParcelMetrics:
    """Return a ParcelMetrics with sensible defaults, accepting field overrides."""
    defaults = dict(
        parcel_id="parcel-001",
        land_area_sqm=5_000.0,
        frontage_m=50.0,
        acquisition_price=1_000_000.0,
        transaction_cost=50_000.0,
        permitted_far=2.5,
        zoning_category="Residential",
        utilities_available=False,
        corner_plot=False,
    )
    defaults.update(overrides)
    return ParcelMetrics(**defaults)


def _two_parcels() -> list:
    """Return two standard parcels with distinct IDs."""
    return [
        _parcel(parcel_id="p-001"),
        _parcel(parcel_id="p-002", land_area_sqm=3_000.0, frontage_m=30.0),
    ]


# ---------------------------------------------------------------------------
# Empty parcel list
# ---------------------------------------------------------------------------

def test_empty_parcel_list_raises():
    """aggregate_parcels raises ValueError when the list is empty."""
    with pytest.raises(ValueError, match="at least one parcel"):
        aggregate_parcels([])


# ---------------------------------------------------------------------------
# Single-parcel assembly
# ---------------------------------------------------------------------------

def test_single_parcel_area():
    """Single parcel: total_area_sqm equals the parcel's land_area_sqm."""
    result = aggregate_parcels([_parcel(parcel_id="p-001", land_area_sqm=10_000.0)])
    assert result.total_area_sqm == pytest.approx(10_000.0)


def test_single_parcel_count():
    """Single parcel: parcel_count is 1."""
    result = aggregate_parcels([_parcel(parcel_id="p-001")])
    assert result.parcel_count == 1


def test_single_parcel_no_mixed_zoning():
    """Single parcel with a zoning category: mixed_zoning is False."""
    result = aggregate_parcels([_parcel(parcel_id="p-001", zoning_category="Commercial")])
    assert result.mixed_zoning is False
    assert result.dominant_zoning_category == "Commercial"


# ---------------------------------------------------------------------------
# Area / frontage summation
# ---------------------------------------------------------------------------

def test_area_sum():
    """Total area equals the sum of individual parcel land areas."""
    parcels = [
        _parcel(parcel_id="p-001", land_area_sqm=5_000.0),
        _parcel(parcel_id="p-002", land_area_sqm=3_000.0),
        _parcel(parcel_id="p-003", land_area_sqm=2_000.0),
    ]
    result = aggregate_parcels(parcels)
    assert result.total_area_sqm == pytest.approx(10_000.0)


def test_frontage_sum():
    """Total frontage equals the sum of individual parcel frontages."""
    parcels = [
        _parcel(parcel_id="p-001", frontage_m=50.0),
        _parcel(parcel_id="p-002", frontage_m=30.0),
    ]
    result = aggregate_parcels(parcels)
    assert result.total_frontage_m == pytest.approx(80.0)


def test_area_sum_excludes_none():
    """Parcels with land_area_sqm=None are excluded from the area sum."""
    parcels = [
        _parcel(parcel_id="p-001", land_area_sqm=5_000.0),
        _parcel(parcel_id="p-002", land_area_sqm=None),
    ]
    result = aggregate_parcels(parcels)
    assert result.total_area_sqm == pytest.approx(5_000.0)


def test_frontage_sum_excludes_none():
    """Parcels with frontage_m=None are excluded from the frontage sum."""
    parcels = [
        _parcel(parcel_id="p-001", frontage_m=50.0),
        _parcel(parcel_id="p-002", frontage_m=None),
    ]
    result = aggregate_parcels(parcels)
    assert result.total_frontage_m == pytest.approx(50.0)


def test_parcel_count():
    """parcel_count matches the length of the input list."""
    parcels = _two_parcels()
    result = aggregate_parcels(parcels)
    assert result.parcel_count == 2


# ---------------------------------------------------------------------------
# Acquisition economics
# ---------------------------------------------------------------------------

def test_acquisition_price_sum():
    """total_acquisition_price equals the sum across parcels."""
    parcels = [
        _parcel(parcel_id="p-001", acquisition_price=1_000_000.0),
        _parcel(parcel_id="p-002", acquisition_price=500_000.0),
    ]
    result = aggregate_parcels(parcels)
    assert result.total_acquisition_price == pytest.approx(1_500_000.0)


def test_transaction_cost_sum():
    """total_transaction_cost equals the sum across parcels."""
    parcels = [
        _parcel(parcel_id="p-001", transaction_cost=50_000.0),
        _parcel(parcel_id="p-002", transaction_cost=25_000.0),
    ]
    result = aggregate_parcels(parcels)
    assert result.total_transaction_cost == pytest.approx(75_000.0)


def test_effective_land_basis():
    """effective_land_basis = total_acquisition_price + total_transaction_cost."""
    parcels = [
        _parcel(parcel_id="p-001", acquisition_price=1_000_000.0, transaction_cost=50_000.0),
        _parcel(parcel_id="p-002", acquisition_price=500_000.0, transaction_cost=25_000.0),
    ]
    result = aggregate_parcels(parcels)
    assert result.effective_land_basis == pytest.approx(1_575_000.0)


def test_effective_land_basis_no_prices():
    """effective_land_basis is 0.0 when all price fields are None."""
    parcels = [
        _parcel(parcel_id="p-001", acquisition_price=None, transaction_cost=None),
    ]
    result = aggregate_parcels(parcels)
    assert result.effective_land_basis == pytest.approx(0.0)
    assert result.total_acquisition_price == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Area-weighted permitted FAR
# ---------------------------------------------------------------------------

def test_weighted_far_equal_areas():
    """Equal-area parcels produce a simple arithmetic average FAR."""
    parcels = [
        _parcel(parcel_id="p-001", land_area_sqm=1_000.0, permitted_far=2.0),
        _parcel(parcel_id="p-002", land_area_sqm=1_000.0, permitted_far=4.0),
    ]
    result = aggregate_parcels(parcels)
    assert result.weighted_permitted_far == pytest.approx(3.0)


def test_weighted_far_unequal_areas():
    """Weighted FAR is biased toward the larger parcel's FAR."""
    parcels = [
        _parcel(parcel_id="p-001", land_area_sqm=3_000.0, permitted_far=2.0),
        _parcel(parcel_id="p-002", land_area_sqm=1_000.0, permitted_far=4.0),
        # Expected: (3000*2 + 1000*4) / 4000 = 10000/4000 = 2.5
    ]
    result = aggregate_parcels(parcels)
    assert result.weighted_permitted_far == pytest.approx(2.5)


def test_weighted_far_none_when_no_far():
    """weighted_permitted_far is None when no parcels have a permitted_far."""
    parcels = [
        _parcel(parcel_id="p-001", permitted_far=None),
        _parcel(parcel_id="p-002", permitted_far=None),
    ]
    result = aggregate_parcels(parcels)
    assert result.weighted_permitted_far is None


def test_weighted_far_none_when_no_area():
    """weighted_permitted_far is None when parcel has FAR but no land_area."""
    parcels = [
        _parcel(parcel_id="p-001", land_area_sqm=None, permitted_far=3.0),
    ]
    result = aggregate_parcels(parcels)
    assert result.weighted_permitted_far is None


# ---------------------------------------------------------------------------
# Zoning category analysis
# ---------------------------------------------------------------------------

def test_uniform_zoning_no_mix():
    """All parcels share the same zoning category: mixed_zoning is False."""
    parcels = [
        _parcel(parcel_id="p-001", zoning_category="Residential"),
        _parcel(parcel_id="p-002", zoning_category="Residential"),
    ]
    result = aggregate_parcels(parcels)
    assert result.mixed_zoning is False
    assert result.dominant_zoning_category == "Residential"


def test_mixed_zoning_detected():
    """Parcels with different zoning categories: mixed_zoning is True."""
    parcels = [
        _parcel(parcel_id="p-001", zoning_category="Residential"),
        _parcel(parcel_id="p-002", zoning_category="Commercial"),
    ]
    result = aggregate_parcels(parcels)
    assert result.mixed_zoning is True


def test_mixed_zoning_dominant_category():
    """dominant_zoning_category is the most frequent category in a mixed assembly."""
    parcels = [
        _parcel(parcel_id="p-001", zoning_category="Residential"),
        _parcel(parcel_id="p-002", zoning_category="Residential"),
        _parcel(parcel_id="p-003", zoning_category="Commercial"),
    ]
    result = aggregate_parcels(parcels)
    assert result.mixed_zoning is True
    assert result.dominant_zoning_category == "Residential"


def test_zoning_category_counts():
    """zoning_category_counts maps each category to its occurrence count."""
    parcels = [
        _parcel(parcel_id="p-001", zoning_category="Residential"),
        _parcel(parcel_id="p-002", zoning_category="Residential"),
        _parcel(parcel_id="p-003", zoning_category="Industrial"),
    ]
    result = aggregate_parcels(parcels)
    assert result.zoning_category_counts == {"Residential": 2, "Industrial": 1}


def test_no_zoning_category_null_dominant():
    """When no parcel has a zoning category, dominant is None and counts are empty."""
    parcels = [
        _parcel(parcel_id="p-001", zoning_category=None),
        _parcel(parcel_id="p-002", zoning_category=None),
    ]
    result = aggregate_parcels(parcels)
    assert result.dominant_zoning_category is None
    assert result.mixed_zoning is False
    assert result.zoning_category_counts == {}


# ---------------------------------------------------------------------------
# Infrastructure / shared flags
# ---------------------------------------------------------------------------

def test_has_utilities_true_when_any_parcel_has_utilities():
    """has_utilities is True when at least one parcel has utilities_available=True."""
    parcels = [
        _parcel(parcel_id="p-001", utilities_available=False),
        _parcel(parcel_id="p-002", utilities_available=True),
    ]
    result = aggregate_parcels(parcels)
    assert result.has_utilities is True


def test_has_utilities_false_when_none_have_utilities():
    """has_utilities is False when no parcel has utilities_available=True."""
    parcels = [
        _parcel(parcel_id="p-001", utilities_available=False),
        _parcel(parcel_id="p-002", utilities_available=False),
    ]
    result = aggregate_parcels(parcels)
    assert result.has_utilities is False


def test_has_corner_plot_true_when_any_is_corner():
    """has_corner_plot is True when at least one parcel is a corner plot."""
    parcels = [
        _parcel(parcel_id="p-001", corner_plot=False),
        _parcel(parcel_id="p-002", corner_plot=True),
    ]
    result = aggregate_parcels(parcels)
    assert result.has_corner_plot is True


def test_has_corner_plot_false_when_none_are_corner():
    """has_corner_plot is False when no parcel is a corner plot."""
    parcels = [
        _parcel(parcel_id="p-001", corner_plot=False),
    ]
    result = aggregate_parcels(parcels)
    assert result.has_corner_plot is False


# ---------------------------------------------------------------------------
# Determinism (recomputation stability)
# ---------------------------------------------------------------------------

def test_recomputation_is_deterministic():
    """Calling aggregate_parcels twice with the same inputs produces identical outputs."""
    parcels = [
        _parcel(parcel_id="p-001", land_area_sqm=5_000.0, permitted_far=2.5),
        _parcel(parcel_id="p-002", land_area_sqm=3_000.0, permitted_far=3.0),
    ]
    result_1 = aggregate_parcels(parcels)
    result_2 = aggregate_parcels(parcels)
    assert result_1 == result_2


def test_recomputation_reflects_changed_values():
    """Updated parcel metrics produce different aggregate outputs."""
    original = [_parcel(parcel_id="p-001", land_area_sqm=5_000.0)]
    updated = [_parcel(parcel_id="p-001", land_area_sqm=8_000.0)]
    result_1 = aggregate_parcels(original)
    result_2 = aggregate_parcels(updated)
    assert result_2.total_area_sqm > result_1.total_area_sqm


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

def test_returns_assembly_aggregation_result():
    """aggregate_parcels always returns an AssemblyAggregationResult instance."""
    result = aggregate_parcels([_parcel(parcel_id="p-001")])
    assert isinstance(result, AssemblyAggregationResult)


# ---------------------------------------------------------------------------
# Three-parcel comprehensive scenario
# ---------------------------------------------------------------------------

def test_three_parcel_assembly_full_metrics():
    """End-to-end scenario with three diverse parcels."""
    parcels = [
        ParcelMetrics(
            parcel_id="p-001",
            land_area_sqm=4_000.0,
            frontage_m=40.0,
            acquisition_price=800_000.0,
            transaction_cost=40_000.0,
            permitted_far=3.0,
            zoning_category="Residential",
            utilities_available=True,
            corner_plot=False,
        ),
        ParcelMetrics(
            parcel_id="p-002",
            land_area_sqm=3_000.0,
            frontage_m=30.0,
            acquisition_price=600_000.0,
            transaction_cost=30_000.0,
            permitted_far=3.0,
            zoning_category="Residential",
            utilities_available=False,
            corner_plot=True,
        ),
        ParcelMetrics(
            parcel_id="p-003",
            land_area_sqm=3_000.0,
            frontage_m=30.0,
            acquisition_price=700_000.0,
            transaction_cost=35_000.0,
            permitted_far=2.0,
            zoning_category="Mixed-Use",
            utilities_available=False,
            corner_plot=False,
        ),
    ]
    result = aggregate_parcels(parcels)

    assert result.parcel_count == 3
    assert result.total_area_sqm == pytest.approx(10_000.0)
    assert result.total_frontage_m == pytest.approx(100.0)
    assert result.total_acquisition_price == pytest.approx(2_100_000.0)
    assert result.total_transaction_cost == pytest.approx(105_000.0)
    assert result.effective_land_basis == pytest.approx(2_205_000.0)
    # Weighted FAR: (4000*3 + 3000*3 + 3000*2) / 10000 = (12000+9000+6000)/10000 = 2.7
    assert result.weighted_permitted_far == pytest.approx(2.7)
    assert result.mixed_zoning is True
    assert result.dominant_zoning_category == "Residential"
    assert result.has_utilities is True
    assert result.has_corner_plot is True
    assert result.zoning_category_counts == {"Residential": 2, "Mixed-Use": 1}
