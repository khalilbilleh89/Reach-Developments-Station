"""
portfolio_auto_strategy.service

Portfolio Auto-Strategy & Intervention Prioritization Engine (PR-V7-06).

Orchestration logic
-------------------
1. Retrieve all projects via the repository (single bulk query — no N+1).
2. For each project, delegate strategy generation to StrategyGeneratorService
   (PR-V7-05).  Any per-project failure is caught and logged; the project
   receives an `insufficient_data` card rather than failing the whole response.
3. For each strategy result, compute:
     urgency_score         — deterministic 0–100 numeric score
     intervention_priority — five-level urgency classification
     intervention_type     — four-level intervention category
4. Sort all cards by the four-key ranking rule (priority desc, risk desc,
   urgency_score desc, project_name asc).
5. Assemble portfolio summary KPIs and top-N action/risk/upside lists.
6. Return PortfolioAutoStrategyResponse.

Architecture constraints
------------------------
- Pure orchestration — reads from strategy_generator only.
- Read-only — no feasibility runs, phases, pricing, or project records are
  mutated.
- Deterministic — same inputs always produce the same ranked output.
- No caching — recalculated on every API call.
- All projects are evaluated before ranking so that urgency-based ordering
  is never biased by source-list position (e.g., alphabetical order).

Urgency score formula (0–100, capped)
--------------------------------------
  risk component : high=60, medium=30, low=10   (0 if no data / unknown)
  no baseline    : +15  (less visibility → more urgency)
  negative price : +10  (market correction required)
  large delay    : +5   (phase timing issue, delay > 3 months)
  cap at 100.

  Missing risk contributes 0 but does NOT short-circuit the other components.

Intervention priority thresholds
---------------------------------
  insufficient_data      : no best strategy available
  urgent_intervention    : urgency_score >= 70
  recommended_intervention: urgency_score >= 40
  monitor_closely        : urgency_score >= 20
  stable                 : urgency_score < 20

Intervention type classification
---------------------------------
  insufficient_data   : no best_irr
  mixed_intervention  : |price_adj| >= 5% AND delay > 0
  pricing_intervention: |price_adj| >= 5%
  phasing_intervention: delay > 0
  monitor_only        : neither signal present

Top-N list definitions
-----------------------
  top_actions        : highest overall intervention urgency (4-key ranked order)
  top_risk_projects  : highest risk severity (high > medium > low > null),
                       tie-broken by urgency_score desc then project_name asc
  top_upside_projects: highest best_irr desc, tie-broken by project_name asc
"""

from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.portfolio_auto_strategy.repository import PortfolioAutoStrategyRepository
from app.modules.portfolio_auto_strategy.schemas import (
    InterventionPriority,
    InterventionType,
    PortfolioAutoStrategyResponse,
    PortfolioInterventionProjectCard,
    PortfolioInterventionSummary,
    PortfolioTopActionItem,
)
from app.modules.strategy_generator.schemas import PortfolioStrategyProjectCard
from app.modules.strategy_generator.service import StrategyGeneratorService

_logger = get_logger("reach_developments.portfolio_auto_strategy")

# Top-N items included in action/risk/upside lists.
_TOP_N = 5

# Risk score → urgency contribution mapping.
_RISK_URGENCY: Dict[str, int] = {"high": 60, "medium": 30, "low": 10}

# Intervention priority → sort order (lower number = higher urgency).
_PRIORITY_ORDER: Dict[str, int] = {
    "urgent_intervention": 0,
    "recommended_intervention": 1,
    "monitor_closely": 2,
    "stable": 3,
    "insufficient_data": 4,
}

# Risk score → sort order (lower = higher urgency).
_RISK_ORDER: Dict[str, int] = {"high": 0, "medium": 1, "low": 2}

# Risk score → severity weight for top_risk_projects sort (higher = more severe).
_RISK_SEVERITY: Dict[str, int] = {"high": 3, "medium": 2, "low": 1}


# ---------------------------------------------------------------------------
# Pure scoring functions (no I/O dependencies — easy to unit-test)
# ---------------------------------------------------------------------------


def _compute_urgency_score(
    best_risk_score: Optional[str],
    has_feasibility_baseline: bool,
    best_price_adjustment_pct: Optional[float],
    best_phase_delay_months: Optional[int],
) -> int:
    """Return a deterministic urgency score in [0, 100].

    Formula (capped at 100):
      risk component : high=60, medium=30, low=10  (0 if no data / unknown)
      no baseline    : +15
      negative price : +10  (corrective price reduction required)
      large delay    : +5   (delay > 3 months)

    Missing risk (None) contributes 0 to the risk component but does NOT
    prevent the other urgency signals (no baseline, price, delay) from being
    applied.  This avoids under-scoring projects that have clear urgency
    signals but whose risk label is temporarily unavailable.
    """
    score = _RISK_URGENCY.get(best_risk_score or "", 0)

    if not has_feasibility_baseline:
        score += 15

    if best_price_adjustment_pct is not None and best_price_adjustment_pct < 0:
        score += 10

    if best_phase_delay_months is not None and best_phase_delay_months > 3:
        score += 5

    return min(score, 100)


def _classify_intervention_priority(
    urgency_score: int,
    has_best_strategy: bool,
) -> InterventionPriority:
    """Classify intervention urgency from urgency_score.

    Returns:
      insufficient_data       — no strategy data available
      urgent_intervention     — urgency_score >= 70
      recommended_intervention— urgency_score >= 40
      monitor_closely         — urgency_score >= 20
      stable                  — urgency_score < 20
    """
    if not has_best_strategy:
        return "insufficient_data"
    if urgency_score >= 70:
        return "urgent_intervention"
    if urgency_score >= 40:
        return "recommended_intervention"
    if urgency_score >= 20:
        return "monitor_closely"
    return "stable"


def _classify_intervention_type(
    best_irr: Optional[float],
    best_price_adjustment_pct: Optional[float],
    best_phase_delay_months: Optional[int],
) -> InterventionType:
    """Classify the type of intervention indicated by the best strategy.

    Returns:
      insufficient_data   — no best_irr available
      mixed_intervention  — significant price adjustment AND phase delay
      pricing_intervention— significant price adjustment only (|adj| >= 5%)
      phasing_intervention— phase delay only (delay > 0)
      monitor_only        — neither signal significant
    """
    if best_irr is None:
        return "insufficient_data"

    has_price_signal = (
        best_price_adjustment_pct is not None
        and abs(best_price_adjustment_pct) >= 5.0
    )
    has_delay_signal = (
        best_phase_delay_months is not None and best_phase_delay_months > 0
    )

    if has_price_signal and has_delay_signal:
        return "mixed_intervention"
    if has_price_signal:
        return "pricing_intervention"
    if has_delay_signal:
        return "phasing_intervention"
    return "monitor_only"


def _build_intervention_reason(
    project_name: str,
    intervention_priority: InterventionPriority,
    intervention_type: InterventionType,
    risk_score: Optional[str],
    urgency_score: int,
    strategy_reason: str,
) -> str:
    """Return a human-readable intervention recommendation reason."""
    priority_label = intervention_priority.replace("_", " ").capitalize()
    type_label = intervention_type.replace("_", " ").capitalize()
    risk_label = (risk_score or "unknown").capitalize()
    return (
        f"{priority_label} for {project_name}. "
        f"Intervention type: {type_label}. "
        f"Risk: {risk_label}. Urgency score: {urgency_score}. "
        f"Strategy detail: {strategy_reason}"
    )


def _build_intervention_card(
    strategy_card: PortfolioStrategyProjectCard,
) -> PortfolioInterventionProjectCard:
    """Convert a strategy project card into an intervention priority card."""
    urgency_score = _compute_urgency_score(
        best_risk_score=strategy_card.best_risk_score,
        has_feasibility_baseline=strategy_card.has_feasibility_baseline,
        best_price_adjustment_pct=strategy_card.best_price_adjustment_pct,
        best_phase_delay_months=strategy_card.best_phase_delay_months,
    )
    has_best_strategy = strategy_card.best_irr is not None
    intervention_priority = _classify_intervention_priority(urgency_score, has_best_strategy)
    intervention_type = _classify_intervention_type(
        best_irr=strategy_card.best_irr,
        best_price_adjustment_pct=strategy_card.best_price_adjustment_pct,
        best_phase_delay_months=strategy_card.best_phase_delay_months,
    )
    reason = _build_intervention_reason(
        project_name=strategy_card.project_name,
        intervention_priority=intervention_priority,
        intervention_type=intervention_type,
        risk_score=strategy_card.best_risk_score,
        urgency_score=urgency_score,
        strategy_reason=strategy_card.reason,
    )

    return PortfolioInterventionProjectCard(
        project_id=strategy_card.project_id,
        project_name=strategy_card.project_name,
        has_feasibility_baseline=strategy_card.has_feasibility_baseline,
        recommended_strategy=strategy_card.best_release_strategy,
        best_irr=strategy_card.best_irr,
        irr_delta=None,  # Requires baseline reference IRR; deferred to PR-V7-07
        risk_score=strategy_card.best_risk_score,
        intervention_priority=intervention_priority,
        intervention_type=intervention_type,
        urgency_score=urgency_score,
        reason=reason,
    )


def _rank_cards(
    cards: List[PortfolioInterventionProjectCard],
) -> List[PortfolioInterventionProjectCard]:
    """Sort cards by the four-key deterministic ranking rule.

    Primary   : intervention_priority severity (urgent=0 … insufficient=4)
    Secondary : risk_score severity (high=0 … null=3)
    Tertiary  : urgency_score descending
    Quaternary: project_name ascending (deterministic tie-break)
    """
    return sorted(
        cards,
        key=lambda c: (
            _PRIORITY_ORDER.get(c.intervention_priority, 4),
            _RISK_ORDER.get(c.risk_score or "", 3),
            -c.urgency_score,
            c.project_name,
        ),
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PortfolioAutoStrategyService:
    """Orchestrates portfolio-level intervention prioritization.

    Reads project strategy outputs from StrategyGeneratorService and converts
    them into a ranked portfolio intervention view.

    All source records are read-only — nothing is mutated.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = PortfolioAutoStrategyRepository(db)
        self._strategy_service = StrategyGeneratorService(db)

    def build_portfolio_auto_strategy(self) -> PortfolioAutoStrategyResponse:
        """Generate portfolio-level intervention priorities.

        Steps:
          1. Load all projects (single bulk query).
          2. Generate strategy for each project via StrategyGeneratorService.
          3. Convert each strategy card into an intervention card.
          4. Rank cards by four-key rule.
          5. Assemble summary KPIs and top-N lists.
          6. Return PortfolioAutoStrategyResponse.

        Per-project failures are caught and logged; those projects receive an
        insufficient_data card rather than failing the whole response.

        All available projects are evaluated before ranking so intervention
        priority is based on scored urgency rather than source-list ordering.
        """
        projects = self._repo.list_projects()

        intervention_cards: List[PortfolioInterventionProjectCard] = []

        for project in projects:
            try:
                rec = self._strategy_service.generate_recommended_strategy(project.id)
            except Exception:
                _logger.exception(
                    "portfolio_auto_strategy: strategy generation failed for project=%s",
                    project.id,
                )
                # Build an insufficient_data card so the project still appears.
                intervention_cards.append(
                    PortfolioInterventionProjectCard(
                        project_id=project.id,
                        project_name=project.name,
                        has_feasibility_baseline=False,
                        recommended_strategy=None,
                        best_irr=None,
                        irr_delta=None,
                        risk_score=None,
                        intervention_priority="insufficient_data",
                        intervention_type="insufficient_data",
                        urgency_score=0,
                        reason=(
                            f"Insufficient data for {project.name}. "
                            "Strategy generation failed — check project configuration."
                        ),
                    )
                )
                continue

            # Build a PortfolioStrategyProjectCard proxy from the recommendation.
            best = rec.best_strategy
            strategy_card = PortfolioStrategyProjectCard(
                project_id=project.id,
                project_name=project.name,
                has_feasibility_baseline=rec.has_feasibility_baseline,
                best_irr=best.irr if best else None,
                best_risk_score=best.risk_score if best else None,
                best_release_strategy=best.release_strategy if best else None,
                best_price_adjustment_pct=best.price_adjustment_pct if best else None,
                best_phase_delay_months=best.phase_delay_months if best else None,
                reason=rec.reason,
            )
            intervention_cards.append(_build_intervention_card(strategy_card))

        ranked_cards = _rank_cards(intervention_cards)

        # --- Summary KPIs -------------------------------------------------
        urgent_count = sum(
            1 for c in ranked_cards if c.intervention_priority == "urgent_intervention"
        )
        no_data_count = sum(
            1 for c in ranked_cards if c.intervention_priority == "insufficient_data"
        )
        monitor_only_count = sum(
            1
            for c in ranked_cards
            if c.intervention_priority in ("stable", "monitor_closely")
        )
        with_baseline_count = sum(1 for c in ranked_cards if c.has_feasibility_baseline)
        analyzed_count = sum(
            1 for c in ranked_cards if c.intervention_priority != "insufficient_data"
        )

        summary = PortfolioInterventionSummary(
            total_projects=len(ranked_cards),
            analyzed_projects=analyzed_count,
            projects_with_baseline=with_baseline_count,
            urgent_intervention_count=urgent_count,
            monitor_only_count=monitor_only_count,
            no_data_count=no_data_count,
        )

        # --- Top-N lists --------------------------------------------------
        # top_actions: best intervention ordering (primary ranked list)
        top_actions = [
            PortfolioTopActionItem(
                project_id=c.project_id,
                project_name=c.project_name,
                intervention_priority=c.intervention_priority,
                intervention_type=c.intervention_type,
                urgency_score=c.urgency_score,
                reason=c.reason,
            )
            for c in ranked_cards[:_TOP_N]
        ]

        # top_risk_projects: genuinely risk-focused — sorted by risk severity
        # desc (high=3 > medium=2 > low=1 > null=0), then urgency_score desc,
        # then project_name asc.  This produces a distinct view from top_actions.
        top_risk_projects = sorted(
            ranked_cards,
            key=lambda c: (
                -_RISK_SEVERITY.get((c.risk_score or "").lower(), 0),
                -c.urgency_score,
                c.project_name,
            ),
        )[:_TOP_N]

        # top_upside_projects: highest best_irr (excluding null-IRR cards)
        cards_with_irr = [c for c in ranked_cards if c.best_irr is not None]
        top_upside_projects = sorted(
            cards_with_irr,
            key=lambda c: (-(c.best_irr or 0.0), c.project_name),
        )[:_TOP_N]

        _logger.info(
            "portfolio_auto_strategy: total=%d analyzed=%d urgent=%d no_data=%d",
            len(ranked_cards),
            analyzed_count,
            urgent_count,
            no_data_count,
        )

        return PortfolioAutoStrategyResponse(
            summary=summary,
            top_actions=top_actions,
            top_risk_projects=top_risk_projects,
            top_upside_projects=top_upside_projects,
            project_cards=ranked_cards,
        )
