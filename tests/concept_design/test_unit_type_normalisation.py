"""
Tests for the _normalise_unit_type() helper in concept_design.service.

Validates whitespace stripping, case-insensitive matching, alias resolution,
and the fallback-to-studio behaviour for unrecognised inputs.

PR-CONCEPT-056A
"""

import pytest

from app.modules.concept_design.service import _normalise_unit_type


# ---------------------------------------------------------------------------
# Exact canonical enum values — pass-through
# ---------------------------------------------------------------------------


def test_normalise_exact_studio():
    assert _normalise_unit_type("studio") == "studio"


def test_normalise_exact_one_bedroom():
    assert _normalise_unit_type("one_bedroom") == "one_bedroom"


def test_normalise_exact_two_bedroom():
    assert _normalise_unit_type("two_bedroom") == "two_bedroom"


def test_normalise_exact_penthouse():
    assert _normalise_unit_type("penthouse") == "penthouse"


# ---------------------------------------------------------------------------
# Case-insensitive exact match
# ---------------------------------------------------------------------------


def test_normalise_uppercase_enum_value():
    """'ONE_BEDROOM' (upper-case enum form) must resolve, not fall back to studio."""
    assert _normalise_unit_type("ONE_BEDROOM") == "one_bedroom"


def test_normalise_mixed_case_enum_value():
    """'Two_Bedroom' must resolve to the canonical form."""
    assert _normalise_unit_type("Two_Bedroom") == "two_bedroom"


def test_normalise_uppercase_studio():
    assert _normalise_unit_type("STUDIO") == "studio"


# ---------------------------------------------------------------------------
# Whitespace stripping
# ---------------------------------------------------------------------------


def test_normalise_leading_trailing_space_canonical():
    """' one_bedroom ' must strip and resolve correctly."""
    assert _normalise_unit_type(" one_bedroom ") == "one_bedroom"


def test_normalise_leading_trailing_space_alias():
    """' 1BR ' must strip, lower-case, then map via alias."""
    assert _normalise_unit_type(" 1BR ") == "one_bedroom"


def test_normalise_leading_trailing_space_studio():
    assert _normalise_unit_type(" studio ") == "studio"


# ---------------------------------------------------------------------------
# Alias shorthand resolution
# ---------------------------------------------------------------------------


def test_normalise_alias_1br():
    assert _normalise_unit_type("1BR") == "one_bedroom"


def test_normalise_alias_2br():
    assert _normalise_unit_type("2BR") == "two_bedroom"


def test_normalise_alias_3br():
    assert _normalise_unit_type("3BR") == "three_bedroom"


def test_normalise_alias_4br():
    assert _normalise_unit_type("4BR") == "four_bedroom"


def test_normalise_alias_studio_lower():
    """'studio' appears in both enum values and alias map — must return 'studio'."""
    assert _normalise_unit_type("studio") == "studio"


def test_normalise_alias_studio_mixed_case():
    """'Studio' must resolve to canonical 'studio' via lower-case path."""
    assert _normalise_unit_type("Studio") == "studio"


def test_normalise_alias_1_bedroom_space():
    assert _normalise_unit_type("1 bedroom") == "one_bedroom"


def test_normalise_alias_two_bedroom_space():
    assert _normalise_unit_type("two bedroom") == "two_bedroom"


# ---------------------------------------------------------------------------
# Fallback for unrecognised values
# ---------------------------------------------------------------------------


def test_normalise_unknown_falls_back_to_studio():
    assert _normalise_unit_type("unknown_type") == "studio"


def test_normalise_empty_string_falls_back_to_studio():
    assert _normalise_unit_type("") == "studio"


def test_normalise_whitespace_only_falls_back_to_studio():
    """Whitespace-only input strips to '' which is unrecognised → studio."""
    assert _normalise_unit_type("   ") == "studio"


def test_normalise_gibberish_falls_back_to_studio():
    assert _normalise_unit_type("XYZ-99") == "studio"
