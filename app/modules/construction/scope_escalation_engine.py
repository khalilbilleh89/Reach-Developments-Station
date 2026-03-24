"""
construction.scope_escalation_engine

Pure Scope Escalation & Contractor Watchlist Engine.

Converts already-computed contractor analytics into actionable breach
classifications.  No database access, no HTTP concerns.

This engine answers: "who must be escalated right now?"

Watchlist Status Priority (highest to lowest)
----------------------------------------------
    Critical  — severe signals requiring immediate intervention
    Escalate  — significant signals requiring management attention
    Watch     — early warning signals requiring monitoring
    Normal    — no breach triggers detected

The status is assigned by evaluating rules in priority order (Critical
first).  The first matching tier wins.  Breach reasons are collected
only for the winning tier so that callers receive the evidence
supporting the assigned status.

Critical triggers (any of)
~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - reliability_band == "Critical"
    - delay_rate >= 0.50
    - cost_overrun_rate >= 0.50
    - risk_signal_count >= 5

Escalate triggers (any of)
~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - reliability_band in {"Watch", "Critical"}
    - average_delay_days >= 14
    - average_cost_variance_pct >= 0.15
    - risk_signal_count >= 3

Watch triggers (any of)
~~~~~~~~~~~~~~~~~~~~~~~~
    - average_delay_days >= 7
    - average_cost_variance_pct >= 0.08
    - risk_signal_count >= 1

Normal
~~~~~~
    No triggers from any tier.

Escalation Score
----------------
An internal numeric severity indicator for downstream sorting:

    Critical  → 3
    Escalate  → 2
    Watch     → 1
    Normal    → 0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("construction_scope_escalation_engine")

# ---------------------------------------------------------------------------
# Watchlist status constants
# ---------------------------------------------------------------------------

STATUS_CRITICAL = "Critical"
STATUS_ESCALATE = "Escalate"
STATUS_WATCH = "Watch"
STATUS_NORMAL = "Normal"

# Numeric severity scores (higher = more severe)
_SCORE_CRITICAL: int = 3
_SCORE_ESCALATE: int = 2
_SCORE_WATCH: int = 1
_SCORE_NORMAL: int = 0

# ---------------------------------------------------------------------------
# Critical thresholds
# ---------------------------------------------------------------------------

CRITICAL_DELAY_RATE: float = 0.50
CRITICAL_COST_OVERRUN_RATE: float = 0.50
CRITICAL_RISK_SIGNAL_COUNT: int = 5

# ---------------------------------------------------------------------------
# Escalate thresholds
# ---------------------------------------------------------------------------

ESCALATE_AVERAGE_DELAY_DAYS: float = 14.0
ESCALATE_AVERAGE_COST_VARIANCE_PCT: float = 0.15
ESCALATE_RISK_SIGNAL_COUNT: int = 3

# ---------------------------------------------------------------------------
# Watch thresholds
# ---------------------------------------------------------------------------

WATCH_AVERAGE_DELAY_DAYS: float = 7.0
WATCH_AVERAGE_COST_VARIANCE_PCT: float = 0.08
WATCH_RISK_SIGNAL_COUNT: int = 1


# ---------------------------------------------------------------------------
# Input dataclass
# ---------------------------------------------------------------------------


@dataclass
class ContractorEscalationInput:
    """Analytics inputs required to compute the contractor watchlist status.

    All fields are sourced from already-computed contractor scorecard and
    reliability engine outputs.

    Parameters
    ----------
    contractor_id:
        Matches ConstructionContractor.id.
    reliability_index:
        Composite reliability score 0–100.  None if not yet computed.
    reliability_band:
        Human-readable reliability band: ``Elite`` / ``Strong`` / ``Watch``
        / ``Critical``.  None if not yet computed.
    delay_rate:
        Fraction of assessed milestones that are delayed.
        None if no assessed milestones.
    average_delay_days:
        Mean delay in days across delayed milestones.
        None if no delayed milestones.
    cost_overrun_rate:
        Fraction of assessed packages exceeding planned cost.
        None if no assessed packages.
    average_cost_variance_pct:
        Mean percentage cost variance across assessed packages.
        Positive = overrun.  None if no assessed packages.
    risk_signal_count:
        Count of HIGH-severity contractor ratio alerts from the risk alert
        engine.
    """

    contractor_id: str
    reliability_index: Optional[float] = None
    reliability_band: Optional[str] = None
    delay_rate: Optional[float] = None
    average_delay_days: Optional[float] = None
    cost_overrun_rate: Optional[float] = None
    average_cost_variance_pct: Optional[float] = None
    risk_signal_count: int = 0


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class ContractorEscalationResult:
    """Escalation classification for a single contractor.

    Parameters
    ----------
    watchlist_status:
        Highest-severity tier triggered: ``Critical`` / ``Escalate`` /
        ``Watch`` / ``Normal``.
    breach_reasons:
        Human-readable list of all triggered breach conditions, collected
        across all tiers regardless of which status tier won.
    escalation_score:
        Internal numeric severity indicator: Critical=3, Escalate=2,
        Watch=1, Normal=0.  Used for downstream sorting.
    """

    watchlist_status: str
    breach_reasons: List[str] = field(default_factory=list)
    escalation_score: int = 0


# ---------------------------------------------------------------------------
# Private rule helpers
# ---------------------------------------------------------------------------


def _collect_critical_breaches(inp: ContractorEscalationInput) -> List[str]:
    """Return breach reason strings for all triggered Critical rules."""
    reasons: List[str] = []
    if inp.reliability_band == "Critical":
        reasons.append("reliability band is Critical")
    if inp.delay_rate is not None and inp.delay_rate >= CRITICAL_DELAY_RATE:
        reasons.append(
            f"delay rate {inp.delay_rate:.0%} >= {CRITICAL_DELAY_RATE:.0%} threshold"
        )
    if inp.cost_overrun_rate is not None and inp.cost_overrun_rate >= CRITICAL_COST_OVERRUN_RATE:
        reasons.append(
            f"cost overrun rate {inp.cost_overrun_rate:.0%}"
            f" >= {CRITICAL_COST_OVERRUN_RATE:.0%} threshold"
        )
    if inp.risk_signal_count >= CRITICAL_RISK_SIGNAL_COUNT:
        reasons.append(
            f"risk signal count {inp.risk_signal_count}"
            f" >= {CRITICAL_RISK_SIGNAL_COUNT} threshold"
        )
    return reasons


def _collect_escalate_breaches(inp: ContractorEscalationInput) -> List[str]:
    """Return breach reason strings for all triggered Escalate rules."""
    reasons: List[str] = []
    if inp.reliability_band in {"Watch", "Critical"}:
        reasons.append(f"reliability band is {inp.reliability_band}")
    if inp.average_delay_days is not None and inp.average_delay_days >= ESCALATE_AVERAGE_DELAY_DAYS:
        reasons.append(
            f"average delay {inp.average_delay_days:.1f} days"
            f" >= {ESCALATE_AVERAGE_DELAY_DAYS:.0f} day threshold"
        )
    if (
        inp.average_cost_variance_pct is not None
        and inp.average_cost_variance_pct >= ESCALATE_AVERAGE_COST_VARIANCE_PCT
    ):
        reasons.append(
            f"average cost variance {inp.average_cost_variance_pct:.0%}"
            f" >= {ESCALATE_AVERAGE_COST_VARIANCE_PCT:.0%} threshold"
        )
    if inp.risk_signal_count >= ESCALATE_RISK_SIGNAL_COUNT:
        reasons.append(
            f"risk signal count {inp.risk_signal_count}"
            f" >= {ESCALATE_RISK_SIGNAL_COUNT} threshold"
        )
    return reasons


def _collect_watch_breaches(inp: ContractorEscalationInput) -> List[str]:
    """Return breach reason strings for all triggered Watch rules."""
    reasons: List[str] = []
    if inp.average_delay_days is not None and inp.average_delay_days >= WATCH_AVERAGE_DELAY_DAYS:
        reasons.append(
            f"average delay {inp.average_delay_days:.1f} days"
            f" >= {WATCH_AVERAGE_DELAY_DAYS:.0f} day threshold"
        )
    if (
        inp.average_cost_variance_pct is not None
        and inp.average_cost_variance_pct >= WATCH_AVERAGE_COST_VARIANCE_PCT
    ):
        reasons.append(
            f"average cost variance {inp.average_cost_variance_pct:.0%}"
            f" >= {WATCH_AVERAGE_COST_VARIANCE_PCT:.0%} threshold"
        )
    if inp.risk_signal_count >= WATCH_RISK_SIGNAL_COUNT:
        reasons.append(
            f"risk signal count {inp.risk_signal_count}"
            f" >= {WATCH_RISK_SIGNAL_COUNT} threshold"
        )
    return reasons


# ---------------------------------------------------------------------------
# Public engine function
# ---------------------------------------------------------------------------


def compute_contractor_escalation(
    inp: ContractorEscalationInput,
) -> ContractorEscalationResult:
    """Classify a contractor into a watchlist tier based on breach rules.

    Parameters
    ----------
    inp:
        Pre-computed analytics fields sourced from the scorecard and
        reliability engines.

    Returns
    -------
    ContractorEscalationResult
        Watchlist status, breach reasons for the winning tier, and
        escalation score.

        Rules are evaluated in priority order (Critical → Escalate →
        Watch → Normal).  The first tier with at least one triggered
        rule determines ``watchlist_status``.  ``breach_reasons``
        contains only the reasons associated with that winning tier.
    """
    critical_reasons = _collect_critical_breaches(inp)
    escalate_reasons = _collect_escalate_breaches(inp)
    watch_reasons = _collect_watch_breaches(inp)

    if critical_reasons:
        logger.debug(
            "contractor=%s watchlist=Critical reasons=%s",
            inp.contractor_id,
            critical_reasons,
        )
        return ContractorEscalationResult(
            watchlist_status=STATUS_CRITICAL,
            breach_reasons=critical_reasons,
            escalation_score=_SCORE_CRITICAL,
        )

    if escalate_reasons:
        logger.debug(
            "contractor=%s watchlist=Escalate reasons=%s",
            inp.contractor_id,
            escalate_reasons,
        )
        return ContractorEscalationResult(
            watchlist_status=STATUS_ESCALATE,
            breach_reasons=escalate_reasons,
            escalation_score=_SCORE_ESCALATE,
        )

    if watch_reasons:
        logger.debug(
            "contractor=%s watchlist=Watch reasons=%s",
            inp.contractor_id,
            watch_reasons,
        )
        return ContractorEscalationResult(
            watchlist_status=STATUS_WATCH,
            breach_reasons=watch_reasons,
            escalation_score=_SCORE_WATCH,
        )

    logger.debug("contractor=%s watchlist=Normal", inp.contractor_id)
    return ContractorEscalationResult(
        watchlist_status=STATUS_NORMAL,
        breach_reasons=[],
        escalation_score=_SCORE_NORMAL,
    )
