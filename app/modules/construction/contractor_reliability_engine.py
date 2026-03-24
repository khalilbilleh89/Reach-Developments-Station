"""
construction.contractor_reliability_engine

Pure Contractor Reliability Index Engine.

Derives a unified reliability signal from already-computed contractor
scorecard analytics.  No database access, no HTTP concerns.

This engine answers: "how dependable is this contractor, combining schedule
discipline, cost discipline, and risk load into a single decision-grade
metric?"

Reliability Index (0–100, higher is better)
--------------------------------------------
Computed as a weighted combination of three discipline components:

    Schedule Discipline  40 %
    Cost Discipline      35 %
    Risk Load            25 %

Schedule Discipline component
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Built from ``on_time_rate`` and ``delay_rate`` (sourced from schedule
variance engine outputs).

    - on_time_rate contribution (primary):
        score = on_time_rate * 100
    - delay_rate penalty (secondary, max 20-point deduction):
        penalty = min(20, delay_rate * 100)

    When both are None (no assessed milestones), schedule_discipline = 100.

Cost Discipline component
~~~~~~~~~~~~~~~~~~~~~~~~~~
Built from ``average_cost_variance_pct`` and ``cost_overrun_rate`` (sourced
from cost variance engine outputs).

    - cost_overrun_rate contribution (primary):
        base = (1 - cost_overrun_rate) * 100
    - average_cost_variance_pct penalty (secondary, max 20-point deduction):
        penalty = min(20, max(0, average_cost_variance_pct) / 5.0)

    When both are None (no assessed packages), cost_discipline = 100.

Risk Load component
~~~~~~~~~~~~~~~~~~~~
Built from ``risk_signal_count``.  Each HIGH-severity signal deducts 15
points (floor: 0).

    risk_load_score = max(0, 100 - risk_signal_count * 15)

Reliability Banding
--------------------
Score range → Band:

    85–100   →  Elite
    70–84.99 →  Strong
    50–69.99 →  Watch
    <50      →  Critical

Confidence Layer
-----------------
Thin evidence (few milestones, few packages) reduces statistical confidence.

    Evidence thresholds:
        Low    — assessed_milestones < 3  AND assessed_packages < 2
        Medium — assessed_milestones < 10 AND assessed_packages < 5
        High   — assessed_milestones >= 10 OR  assessed_packages >= 5

    (``assessed_milestones`` = milestones contributing to delay_rate;
     ``assessed_packages``  = packages contributing to cost_overrun_rate.)

Ranking Sort Score
------------------
An internal-use float for deterministic ranking.  It equals
``reliability_index`` when both are present.  None when reliability_index
is not computable.

ranking_sort_score is intentionally not exposed in the public API response
to keep the contract clean; the caller may use it internally for ordering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("construction_contractor_reliability_engine")

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

SCHEDULE_DISCIPLINE_WEIGHT: float = 0.40
COST_DISCIPLINE_WEIGHT: float = 0.35
RISK_LOAD_WEIGHT: float = 0.25

# Points deducted per HIGH-severity risk signal (floor: 0)
RISK_SIGNAL_PENALTY: float = 15.0

# Maximum secondary penalty points for delay rate / cost variance
MAX_DELAY_RATE_PENALTY: float = 20.0
MAX_COST_VARIANCE_PENALTY: float = 20.0

# Reliability band thresholds
BAND_ELITE_MIN: float = 85.0
BAND_STRONG_MIN: float = 70.0
BAND_WATCH_MIN: float = 50.0

# Confidence thresholds
CONFIDENCE_HIGH_MILESTONES: int = 10
CONFIDENCE_HIGH_PACKAGES: int = 5
CONFIDENCE_MEDIUM_MILESTONES: int = 3
CONFIDENCE_MEDIUM_PACKAGES: int = 2

BAND_ELITE = "Elite"
BAND_STRONG = "Strong"
BAND_WATCH = "Watch"
BAND_CRITICAL = "Critical"

CONFIDENCE_HIGH = "High"
CONFIDENCE_MEDIUM = "Medium"
CONFIDENCE_LOW = "Low"


# ---------------------------------------------------------------------------
# Input dataclass
# ---------------------------------------------------------------------------


@dataclass
class ContractorReliabilityInput:
    """Analytics inputs required to compute the contractor reliability index.

    All fields are sourced from the contractor scorecard / variance engine
    outputs and should already be computed before calling this engine.

    Parameters
    ----------
    on_time_rate:
        Fraction of completed milestones delivered on or before target_date.
        None if no completed milestones with both dates set.
    delay_rate:
        Fraction of assessed milestones (both dates set) that are delayed.
        None if no assessed milestones.
    average_delay_days:
        Mean delay in days across delayed milestones.  Used for
        informational context; not directly used in the index formula.
    average_cost_variance_pct:
        Mean percentage cost variance across assessed packages.
        Positive = overrun, negative = under budget.
        None if no assessed packages with non-zero planned value.
    cost_overrun_rate:
        Fraction of assessed packages that exceed planned cost.
        None if no assessed packages.
    risk_signal_count:
        Count of HIGH-severity contractor ratio alerts from the risk alert
        engine.
    assessed_milestones:
        Number of milestones that contributed to schedule variance metrics
        (i.e. had both completion_date and target_date set).  Used for
        confidence banding.
    assessed_packages:
        Number of packages that contributed to cost variance metrics
        (i.e. had both planned_cost and actual_cost set).  Used for
        confidence banding.
    """

    on_time_rate: Optional[float] = None
    delay_rate: Optional[float] = None
    average_delay_days: Optional[float] = None
    average_cost_variance_pct: Optional[float] = None
    cost_overrun_rate: Optional[float] = None
    risk_signal_count: int = 0
    assessed_milestones: int = 0
    assessed_packages: int = 0


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class ContractorReliabilityResult:
    """Computed reliability outputs for a single contractor.

    Parameters
    ----------
    reliability_index:
        Composite reliability score 0–100.  Higher is better.
        None when insufficient evidence is available to compute a score.
    reliability_band:
        Human-readable band: ``Elite`` / ``Strong`` / ``Watch`` / ``Critical``.
        None when ``reliability_index`` is None.
    reliability_confidence:
        Statistical confidence in the score based on evidence volume:
        ``Low`` / ``Medium`` / ``High``.
        None when ``reliability_index`` is None.
    ranking_sort_score:
        Internal-use float for deterministic ranking.  Equals
        ``reliability_index`` when computable, otherwise None.
        Not intended for public API exposure.
    """

    reliability_index: Optional[float] = None
    reliability_band: Optional[str] = None
    reliability_confidence: Optional[str] = None
    ranking_sort_score: Optional[float] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_schedule_discipline(
    on_time_rate: Optional[float],
    delay_rate: Optional[float],
    assessed_milestones: int,
) -> float:
    """Compute the schedule discipline component (0–100).

    Uses on_time_rate as the primary driver, then applies a secondary penalty
    from delay_rate.  Returns 100.0 when no assessed milestones exist (i.e.
    no milestones have both completion_date and target_date set — no temporal
    evidence is available).
    """
    if assessed_milestones == 0:
        # No date evidence — neutral baseline, not a negative signal
        return 100.0

    # Primary: on_time_rate drives the base score
    if on_time_rate is not None:
        base = on_time_rate * 100.0
    else:
        # on_time_rate is None but delay_rate is available — infer from it
        base = max(0.0, 100.0 - (delay_rate or 0.0) * 100.0)

    # Secondary: delay_rate adds a small additional penalty (max 20 pts)
    if delay_rate is not None and delay_rate > 0.0:
        penalty = min(MAX_DELAY_RATE_PENALTY, delay_rate * 100.0)
        base = max(0.0, base - penalty)

    return round(base, 4)


def _compute_cost_discipline(
    cost_overrun_rate: Optional[float],
    average_cost_variance_pct: Optional[float],
) -> float:
    """Compute the cost discipline component (0–100).

    Uses cost_overrun_rate as the primary driver, then applies a secondary
    penalty from average_cost_variance_pct.  Returns 100.0 when no assessed
    packages exist.
    """
    if cost_overrun_rate is None:
        return 100.0

    base = max(0.0, (1.0 - cost_overrun_rate) * 100.0)

    if average_cost_variance_pct is not None and average_cost_variance_pct > 0.0:
        penalty = min(MAX_COST_VARIANCE_PENALTY, average_cost_variance_pct / 5.0)
        base = max(0.0, base - penalty)

    return round(base, 4)


def _compute_risk_load_score(risk_signal_count: int) -> float:
    """Compute the risk load component (0–100).

    Each HIGH-severity alert deducts RISK_SIGNAL_PENALTY points (floor 0).
    """
    return max(0.0, 100.0 - risk_signal_count * RISK_SIGNAL_PENALTY)


def _assign_band(index: float) -> str:
    """Map a reliability index value to the corresponding band string."""
    if index >= BAND_ELITE_MIN:
        return BAND_ELITE
    if index >= BAND_STRONG_MIN:
        return BAND_STRONG
    if index >= BAND_WATCH_MIN:
        return BAND_WATCH
    return BAND_CRITICAL


def _assign_confidence(assessed_milestones: int, assessed_packages: int) -> str:
    """Assign evidence confidence based on assessed evidence volume.

    High   — assessed_milestones >= 10 OR  assessed_packages >= 5
    Medium — assessed_milestones >= 3  OR  assessed_packages >= 2
    Low    — everything else
    """
    if assessed_milestones >= CONFIDENCE_HIGH_MILESTONES or (
        assessed_packages >= CONFIDENCE_HIGH_PACKAGES
    ):
        return CONFIDENCE_HIGH
    if assessed_milestones >= CONFIDENCE_MEDIUM_MILESTONES or (
        assessed_packages >= CONFIDENCE_MEDIUM_PACKAGES
    ):
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


# ---------------------------------------------------------------------------
# Engine entry point
# ---------------------------------------------------------------------------


def compute_contractor_reliability(
    inp: ContractorReliabilityInput,
) -> ContractorReliabilityResult:
    """Compute the contractor reliability index from scorecard analytics.

    Parameters
    ----------
    inp:
        Pre-computed analytics fields sourced from the scorecard and
        variance engines.

    Returns
    -------
    ContractorReliabilityResult
        Reliability index, band, confidence, and ranking sort score.

        When the contractor has no assessed milestones and no assessed
        packages and no risk signals, the index is still computed (defaults
        to 100.0 indicating no negative evidence), but with ``Low``
        confidence.

        All output fields are bounded:
            - ``reliability_index`` ∈ [0, 100]
            - ``reliability_band`` ∈ {Elite, Strong, Watch, Critical}
            - ``reliability_confidence`` ∈ {Low, Medium, High}
    """
    schedule_discipline = _compute_schedule_discipline(
        inp.on_time_rate, inp.delay_rate, inp.assessed_milestones
    )
    cost_discipline = _compute_cost_discipline(
        inp.cost_overrun_rate, inp.average_cost_variance_pct
    )
    risk_load = _compute_risk_load_score(inp.risk_signal_count)

    raw_index = (
        schedule_discipline * SCHEDULE_DISCIPLINE_WEIGHT
        + cost_discipline * COST_DISCIPLINE_WEIGHT
        + risk_load * RISK_LOAD_WEIGHT
    )
    # Clamp to [0, 100] and round to 2 decimal places
    reliability_index = round(max(0.0, min(100.0, raw_index)), 2)

    band = _assign_band(reliability_index)
    confidence = _assign_confidence(inp.assessed_milestones, inp.assessed_packages)

    logger.debug(
        "reliability_index=%.2f band=%s confidence=%s "
        "schedule_discipline=%.2f cost_discipline=%.2f risk_load=%.2f",
        reliability_index,
        band,
        confidence,
        schedule_discipline,
        cost_discipline,
        risk_load,
    )

    return ContractorReliabilityResult(
        reliability_index=reliability_index,
        reliability_band=band,
        reliability_confidence=confidence,
        ranking_sort_score=reliability_index,
    )
