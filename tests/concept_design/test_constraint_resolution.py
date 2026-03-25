"""
Pure unit tests for the constraint priority resolution helpers in
ConceptDesignService.

These methods contain no database logic — they are pure priority selectors.
Testing them directly protects the canonical upstream source model
introduced in PR-CONCEPT-060 and hardened in PR-CONCEPT-060A.

Priority order (both FAR and density)
--------------------------------------
1. concept_override_*  — explicit user override (wins if present)
2. land.*              — inherited from upstream land parcel
3. manual *            — manually entered on the concept option
4. all absent          — None (validation rule is skipped)

Covered scenarios
-----------------
_resolve_effective_far_limit
  - override present → override wins regardless of land/manual values
  - override absent, land present → land wins over manual
  - override absent, land absent, manual present → manual wins
  - all absent → None returned
  - override=0.0 is treated as "present" (any non-None value wins)

_resolve_effective_density_limit
  - mirrors the FAR priority logic (same four scenarios, including 0.0)

PR-CONCEPT-061
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.modules.concept_design.service import ConceptDesignService


def _service() -> ConceptDesignService:
    """Return a ConceptDesignService backed by a mock session.

    The resolution helpers do not touch the session, so a bare MagicMock
    is sufficient to satisfy the constructor.
    """
    return ConceptDesignService(db=MagicMock())


# ===========================================================================
# _resolve_effective_far_limit
# ===========================================================================


class TestResolveEffectiveFarLimit:
    def test_override_wins_over_land_and_manual(self):
        svc = _service()
        result = svc._resolve_effective_far_limit(
            override_far=4.0,
            land_far=2.5,
            manual_far=1.5,
        )
        assert result == 4.0

    def test_override_wins_when_land_absent(self):
        svc = _service()
        result = svc._resolve_effective_far_limit(
            override_far=3.0,
            land_far=None,
            manual_far=1.5,
        )
        assert result == 3.0

    def test_override_wins_when_manual_absent(self):
        svc = _service()
        result = svc._resolve_effective_far_limit(
            override_far=3.0,
            land_far=None,
            manual_far=None,
        )
        assert result == 3.0

    def test_land_wins_when_override_absent(self):
        svc = _service()
        result = svc._resolve_effective_far_limit(
            override_far=None,
            land_far=2.5,
            manual_far=1.5,
        )
        assert result == 2.5

    def test_land_wins_when_override_absent_and_manual_absent(self):
        svc = _service()
        result = svc._resolve_effective_far_limit(
            override_far=None,
            land_far=2.5,
            manual_far=None,
        )
        assert result == 2.5

    def test_manual_wins_when_override_and_land_absent(self):
        svc = _service()
        result = svc._resolve_effective_far_limit(
            override_far=None,
            land_far=None,
            manual_far=1.5,
        )
        assert result == 1.5

    def test_returns_none_when_all_absent(self):
        svc = _service()
        result = svc._resolve_effective_far_limit(
            override_far=None,
            land_far=None,
            manual_far=None,
        )
        assert result is None

    def test_override_zero_wins_over_land_and_manual(self):
        """override_far=0.0 is non-None, so it wins over land and manual values.

        The helpers use an ``is not None`` check, meaning any explicit value
        including 0.0 is treated as a present override.
        """
        svc = _service()
        result = svc._resolve_effective_far_limit(
            override_far=0.0,
            land_far=2.5,
            manual_far=1.0,
        )
        assert result == 0.0

    def test_result_preserves_float_precision(self):
        svc = _service()
        result = svc._resolve_effective_far_limit(
            override_far=None,
            land_far=2.75,
            manual_far=None,
        )
        assert result == 2.75


# ===========================================================================
# _resolve_effective_density_limit
# ===========================================================================


class TestResolveEffectiveDensityLimit:
    def test_override_wins_over_land_and_manual(self):
        svc = _service()
        result = svc._resolve_effective_density_limit(
            override_density=120.0,
            land_density=80.0,
            manual_density=50.0,
        )
        assert result == 120.0

    def test_override_wins_when_land_absent(self):
        svc = _service()
        result = svc._resolve_effective_density_limit(
            override_density=90.0,
            land_density=None,
            manual_density=50.0,
        )
        assert result == 90.0

    def test_override_wins_when_manual_absent(self):
        svc = _service()
        result = svc._resolve_effective_density_limit(
            override_density=90.0,
            land_density=None,
            manual_density=None,
        )
        assert result == 90.0

    def test_land_wins_when_override_absent(self):
        svc = _service()
        result = svc._resolve_effective_density_limit(
            override_density=None,
            land_density=80.0,
            manual_density=50.0,
        )
        assert result == 80.0

    def test_land_wins_when_override_absent_and_manual_absent(self):
        svc = _service()
        result = svc._resolve_effective_density_limit(
            override_density=None,
            land_density=80.0,
            manual_density=None,
        )
        assert result == 80.0

    def test_manual_wins_when_override_and_land_absent(self):
        svc = _service()
        result = svc._resolve_effective_density_limit(
            override_density=None,
            land_density=None,
            manual_density=50.0,
        )
        assert result == 50.0

    def test_returns_none_when_all_absent(self):
        svc = _service()
        result = svc._resolve_effective_density_limit(
            override_density=None,
            land_density=None,
            manual_density=None,
        )
        assert result is None

    def test_result_preserves_float_precision(self):
        svc = _service()
        result = svc._resolve_effective_density_limit(
            override_density=None,
            land_density=None,
            manual_density=75.5,
        )
        assert result == 75.5


# ===========================================================================
# Priority symmetry — FAR and density use the same resolution logic
# ===========================================================================


class TestPrioritySymmetry:
    """Confirm that FAR and density resolution are governed by the same priority rule."""

    def test_far_and_density_both_prefer_override(self):
        svc = _service()
        far = svc._resolve_effective_far_limit(
            override_far=5.0, land_far=2.0, manual_far=1.0
        )
        density = svc._resolve_effective_density_limit(
            override_density=200.0, land_density=100.0, manual_density=50.0
        )
        assert far == 5.0
        assert density == 200.0

    def test_far_and_density_both_fall_to_land_without_override(self):
        svc = _service()
        far = svc._resolve_effective_far_limit(
            override_far=None, land_far=2.0, manual_far=1.0
        )
        density = svc._resolve_effective_density_limit(
            override_density=None, land_density=100.0, manual_density=50.0
        )
        assert far == 2.0
        assert density == 100.0

    def test_far_and_density_both_fall_to_manual_without_override_or_land(self):
        svc = _service()
        far = svc._resolve_effective_far_limit(
            override_far=None, land_far=None, manual_far=1.0
        )
        density = svc._resolve_effective_density_limit(
            override_density=None, land_density=None, manual_density=50.0
        )
        assert far == 1.0
        assert density == 50.0

    def test_far_and_density_both_return_none_when_nothing_present(self):
        svc = _service()
        far = svc._resolve_effective_far_limit(
            override_far=None, land_far=None, manual_far=None
        )
        density = svc._resolve_effective_density_limit(
            override_density=None, land_density=None, manual_density=None
        )
        assert far is None
        assert density is None
