"""
strategy_generator.service

Automated Strategy Generator — Decision Synthesis Layer (PR-V7-05).

Orchestration logic
-------------------
1. Generate candidate strategy scenarios from the cross-product of:
     price_adjustment_pct : [-5, 0, 5, 8]
     phase_delay_months   : [0, 3, 6]
     release_strategy     : ['hold', 'maintain', 'accelerate']
   Up to _MAX_SCENARIOS (20) are passed to the simulation engine.

2. Delegate simulation to the existing ReleaseSimulationService
   (simulate_strategies) — no duplicate IRR / NPV logic.

3. Rank results using a deterministic three-key sort:
     Primary   : irr         — descending (higher = better)
     Secondary : risk_score  — ascending ('low' < 'medium' < 'high')
     Tertiary  : delay       — ascending (less delay = better)

4. Return:
     best_strategy           — top-ranked SimulationResult
     top_strategies          — top 3 SimulationResults
     reason                  — human-readable explanation
     generated_scenario_count — number of scenarios evaluated

Architecture constraints
------------------------
- Pure orchestration — reads from simulation engine only.
- Read-only — no feasibility runs, phases, or pricing records are mutated.
- Deterministic — same inputs always produce the same ranked output.
- No caching — recalculated on every API call.
"""

from __future__ import annotations

import itertools
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError
from app.core.logging import get_logger
from app.modules.release_simulation.schemas import (
    SimulateStrategiesRequest,
    SimulationResult,
    SimulationScenarioInput,
)
from app.modules.release_simulation.service import ReleaseSimulationService
from app.modules.strategy_generator.schemas import (
    PortfolioStrategyInsightsResponse,
    PortfolioStrategyInsightsSummary,
    PortfolioStrategyProjectCard,
    RecommendedStrategyResponse,
)

_logger = get_logger("reach_developments.strategy_generator")

# ---------------------------------------------------------------------------
# Candidate scenario dimensions (per spec)
# ---------------------------------------------------------------------------

_PRICE_ADJUSTMENTS: List[float] = [-5.0, 0.0, 5.0, 8.0]
_PHASE_DELAYS: List[int] = [0, 3, 6]
_RELEASE_STRATEGIES: List[str] = ["hold", "maintain", "accelerate"]

# Maximum scenarios sent to the simulation engine in a single call.
_MAX_SCENARIOS = 20

# Ranking weight for risk_score (lower = better outcome).
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

# Top N strategies included in project-level and portfolio responses.
_TOP_N = 3


def _generate_candidate_scenarios() -> List[SimulationScenarioInput]:
    """Return up to _MAX_SCENARIOS candidate simulation scenarios.

    Iterates the cartesian product of price adjustments × phase delays ×
    release strategies in a deterministic order and stops at _MAX_SCENARIOS.
    """
    scenarios: List[SimulationScenarioInput] = []
    for price_adj, delay, strategy in itertools.product(
        _PRICE_ADJUSTMENTS, _PHASE_DELAYS, _RELEASE_STRATEGIES
    ):
        if len(scenarios) >= _MAX_SCENARIOS:
            break
        scenarios.append(
            SimulationScenarioInput(
                price_adjustment_pct=price_adj,
                phase_delay_months=delay,
                release_strategy=strategy,  # type: ignore[arg-type]
                label=f"{price_adj:+.0f}% / {delay}mo / {strategy}",
            )
        )
    return scenarios


def _rank_results(results: List[SimulationResult]) -> List[SimulationResult]:
    """Sort simulation results by the three-key ranking rule.

    Primary   : IRR descending   (higher IRR = better)
    Secondary : risk_score ascending ('low' < 'medium' < 'high')
    Tertiary  : cashflow_delay_months ascending (less delay = better)
    """
    return sorted(
        results,
        key=lambda r: (
            -r.irr,
            _RISK_ORDER.get(r.risk_score, 1),
            r.cashflow_delay_months,
        ),
    )


def _build_reason(best: SimulationResult) -> str:
    """Return a human-readable reason string for the best strategy."""
    price_dir = "increase" if best.price_adjustment_pct > 0 else (
        "decrease" if best.price_adjustment_pct < 0 else "no change to"
    )
    irr_pct = round(best.irr * 100, 2)
    return (
        f"Best strategy: {best.release_strategy} release with "
        f"{best.price_adjustment_pct:+.0f}% price adjustment and "
        f"{best.phase_delay_months}mo phase delay. "
        f"Projected IRR: {irr_pct:.2f}% ({best.risk_score} risk). "
        f"Recommendation is to {price_dir} pricing and apply a "
        f"{best.release_strategy} release approach."
    )


class StrategyGeneratorService:
    """Orchestrates candidate strategy generation, simulation, and ranking."""

    def __init__(self, db: Session) -> None:
        self._simulation_service = ReleaseSimulationService(db)
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_recommended_strategy(
        self, project_id: str
    ) -> RecommendedStrategyResponse:
        """Generate and rank candidate strategies for a project.

        Raises ResourceNotFoundError if the project does not exist.
        All source records are read-only — nothing is mutated.
        """
        scenarios = _generate_candidate_scenarios()
        request = SimulateStrategiesRequest(scenarios=scenarios)

        try:
            sim_response = self._simulation_service.simulate_strategies(
                project_id, request
            )
        except ResourceNotFoundError:
            raise

        ranked = _rank_results(sim_response.results)
        best = ranked[0] if ranked else None
        top_strategies = ranked[:_TOP_N]

        reason = _build_reason(best) if best is not None else "No scenarios could be generated."

        _logger.info(
            "strategy_generator: project=%s scenarios=%d best_irr=%s risk=%s",
            project_id,
            len(ranked),
            best.irr if best else None,
            best.risk_score if best else None,
        )

        return RecommendedStrategyResponse(
            project_id=sim_response.project_id,
            project_name=sim_response.project_name,
            has_feasibility_baseline=sim_response.has_feasibility_baseline,
            best_strategy=best,
            top_strategies=top_strategies,
            reason=reason,
            generated_scenario_count=len(ranked),
        )

    def build_portfolio_strategy_insights(
        self,
    ) -> PortfolioStrategyInsightsResponse:
        """Generate strategy recommendations for all projects and aggregate.

        All source records are read-only — nothing is mutated.
        """
        from app.modules.projects.models import Project

        projects = self._db.query(Project).all()

        cards: List[PortfolioStrategyProjectCard] = []
        for project in projects:
            try:
                rec = self.generate_recommended_strategy(project.id)
            except Exception:
                _logger.warning(
                    "strategy_generator: portfolio — failed for project=%s", project.id
                )
                cards.append(
                    PortfolioStrategyProjectCard(
                        project_id=project.id,
                        project_name=project.name,
                        has_feasibility_baseline=False,
                        best_irr=None,
                        best_risk_score=None,
                        best_release_strategy=None,
                        best_price_adjustment_pct=None,
                        best_phase_delay_months=None,
                        reason="Strategy generation failed for this project.",
                    )
                )
                continue

            best = rec.best_strategy
            cards.append(
                PortfolioStrategyProjectCard(
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
            )

        # Sort all cards by best IRR descending (null last).
        cards.sort(key=lambda c: (c.best_irr is None, -(c.best_irr or 0.0)))

        top_strategies = cards[:_TOP_N]
        intervention_required = [c for c in cards if c.best_risk_score == "high"]

        summary = PortfolioStrategyInsightsSummary(
            total_projects=len(cards),
            projects_with_baseline=sum(1 for c in cards if c.has_feasibility_baseline),
            projects_high_risk=len(intervention_required),
            projects_low_risk=sum(1 for c in cards if c.best_risk_score == "low"),
        )

        return PortfolioStrategyInsightsResponse(
            summary=summary,
            projects=cards,
            top_strategies=top_strategies,
            intervention_required=intervention_required,
        )
