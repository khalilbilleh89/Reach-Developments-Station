"""
Tests for the Concept Design calculation engine.

Validates pure function behaviour — no database or HTTP layer involved.

PR-CONCEPT-052
"""

import pytest

from app.modules.concept_design.engine import (
    MixLineInput,
    compute_average_unit_area,
    compute_efficiency_ratio,
    compute_sellable_area,
    compute_unit_count,
    run_concept_engine,
)


# ---------------------------------------------------------------------------
# compute_unit_count
# ---------------------------------------------------------------------------

def test_unit_count_single_line():
    lines = [MixLineInput(unit_type="1BR", units_count=50, avg_sellable_area=75.0)]
    assert compute_unit_count(lines) == 50


def test_unit_count_multiple_lines():
    lines = [
        MixLineInput(unit_type="1BR", units_count=50, avg_sellable_area=75.0),
        MixLineInput(unit_type="2BR", units_count=30, avg_sellable_area=110.0),
        MixLineInput(unit_type="3BR", units_count=20, avg_sellable_area=140.0),
    ]
    assert compute_unit_count(lines) == 100


def test_unit_count_empty():
    assert compute_unit_count([]) == 0


# ---------------------------------------------------------------------------
# compute_sellable_area
# ---------------------------------------------------------------------------

def test_sellable_area_basic():
    lines = [
        MixLineInput(unit_type="1BR", units_count=10, avg_sellable_area=80.0),
        MixLineInput(unit_type="2BR", units_count=5, avg_sellable_area=120.0),
    ]
    # 10*80 + 5*120 = 800 + 600 = 1400
    assert compute_sellable_area(lines) == pytest.approx(1400.0)


def test_sellable_area_none_when_no_avg_area():
    lines = [
        MixLineInput(unit_type="1BR", units_count=10, avg_sellable_area=None),
    ]
    assert compute_sellable_area(lines) is None


def test_sellable_area_partial_lines():
    """Lines without avg_sellable_area are skipped; result is still returned."""
    lines = [
        MixLineInput(unit_type="1BR", units_count=10, avg_sellable_area=80.0),
        MixLineInput(unit_type="2BR", units_count=5, avg_sellable_area=None),
    ]
    assert compute_sellable_area(lines) == pytest.approx(800.0)


def test_sellable_area_empty():
    assert compute_sellable_area([]) is None


# ---------------------------------------------------------------------------
# compute_efficiency_ratio
# ---------------------------------------------------------------------------

def test_efficiency_ratio_basic():
    ratio = compute_efficiency_ratio(sellable_area=800.0, gross_floor_area=1000.0)
    assert ratio == pytest.approx(0.8)


def test_efficiency_ratio_none_when_sellable_is_none():
    assert compute_efficiency_ratio(None, 1000.0) is None


def test_efficiency_ratio_none_when_gfa_is_none():
    assert compute_efficiency_ratio(800.0, None) is None


def test_efficiency_ratio_none_when_gfa_is_zero():
    assert compute_efficiency_ratio(800.0, 0.0) is None


# ---------------------------------------------------------------------------
# compute_average_unit_area
# ---------------------------------------------------------------------------

def test_average_unit_area_basic():
    avg = compute_average_unit_area(sellable_area=1000.0, unit_count=10)
    assert avg == pytest.approx(100.0)


def test_average_unit_area_none_when_sellable_is_none():
    assert compute_average_unit_area(None, 10) is None


def test_average_unit_area_none_when_count_is_zero():
    assert compute_average_unit_area(1000.0, 0) is None


# ---------------------------------------------------------------------------
# run_concept_engine — full integration
# ---------------------------------------------------------------------------

def test_run_concept_engine_full():
    lines = [
        MixLineInput(unit_type="1BR", units_count=60, avg_sellable_area=75.0),
        MixLineInput(unit_type="2BR", units_count=40, avg_sellable_area=115.0),
    ]
    # sellable = 60*75 + 40*115 = 4500 + 4600 = 9100
    # unit_count = 100
    # gfa = 12000
    # efficiency_ratio = 9100/12000 ≈ 0.7583
    # avg_unit_area = 9100/100 = 91.0
    result = run_concept_engine(mix_lines=lines, gross_floor_area=12000.0)
    assert result.unit_count == 100
    assert result.sellable_area == pytest.approx(9100.0)
    assert result.efficiency_ratio == pytest.approx(9100.0 / 12000.0)
    assert result.average_unit_area == pytest.approx(91.0)


def test_run_concept_engine_no_gfa():
    lines = [MixLineInput(unit_type="Studio", units_count=20, avg_sellable_area=50.0)]
    result = run_concept_engine(mix_lines=lines, gross_floor_area=None)
    assert result.unit_count == 20
    assert result.sellable_area == pytest.approx(1000.0)
    assert result.efficiency_ratio is None
    assert result.average_unit_area == pytest.approx(50.0)


def test_run_concept_engine_no_mix_lines():
    result = run_concept_engine(mix_lines=[], gross_floor_area=5000.0)
    assert result.unit_count == 0
    assert result.sellable_area is None
    assert result.efficiency_ratio is None
    assert result.average_unit_area is None


def test_run_concept_engine_no_sellable_area_on_lines():
    lines = [MixLineInput(unit_type="1BR", units_count=10, avg_sellable_area=None)]
    result = run_concept_engine(mix_lines=lines, gross_floor_area=5000.0)
    assert result.unit_count == 10
    assert result.sellable_area is None
    assert result.efficiency_ratio is None
    assert result.average_unit_area is None
