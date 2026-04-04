"""
strategy_execution_package.service

Strategy Execution Package Generator — Action Packaging Layer (PR-V7-07).

Orchestration logic
-------------------
1. Accept a project_id (or iterate all projects for the portfolio endpoint).
2. Delegate strategy generation to StrategyGeneratorService (PR-V7-05).
3. Translate the recommended strategy output into a structured execution
   package containing:
     - execution readiness classification
     - ordered action steps (with urgency, dependency, and review flags)
     - dependency checks (feasibility baseline, strategy data)
     - caution notes (risk, missing baseline, delay signals)
     - supporting metrics
     - expected impact summary
4. For the portfolio endpoint, convert each project package into a compact
   PortfolioPackagedInterventionCard and assemble a portfolio summary.

Architecture constraints
------------------------
- Pure orchestration — reads from strategy_generator and portfolio_auto_strategy.
- Read-only — no feasibility runs, phases, pricing, or project records are mutated.
- Deterministic — same inputs always produce the same output.
- No caching — recalculated on every API call.

Execution readiness classification
------------------------------------
  insufficient_data     : no best strategy available
  blocked_by_dependency : no feasibility baseline (simulation is indicative only)
  caution_required      : best strategy carries high risk classification
  ready_for_review      : baseline present, strategy available, risk is low/medium

Action sequence rules
---------------------
  1. Baseline dependency review (if no baseline, blocked step first)
  2. Simulation evidence review (always present when strategy exists)
  3. Pricing preparation (if |price_adj| >= 5%)
  4. Phasing preparation (if phase_delay > 0)
  5. Holdback or release readiness validation (if hold / accelerate strategy)
  6. Executive review routing (if high risk)

Portfolio packaging ranking
-----------------------------
  Primary   : execution_readiness (ready_for_review first … insufficient_data last)
  Secondary : urgency_score descending
  Tertiary  : project_name ascending
"""

from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError
from app.core.logging import get_logger
from app.modules.portfolio_auto_strategy.service import (
    _classify_intervention_priority,
    _classify_intervention_type,
    _compute_urgency_score,
)
from app.modules.release_simulation.schemas import SimulationResult
from app.modules.strategy_execution_package.repository import StrategyExecutionPackageRepository
from app.modules.strategy_execution_package.schemas import (
    ExecutionReadiness,
    PortfolioExecutionPackageResponse,
    PortfolioExecutionPackageSummary,
    PortfolioPackagedInterventionCard,
    ProjectStrategyExecutionPackageResponse,
    StrategyExecutionActionItem,
    StrategyExecutionCautionItem,
    StrategyExecutionDependencyItem,
    StrategyExecutionSupportingMetrics,
)
from app.modules.strategy_generator.schemas import RecommendedStrategyResponse
from app.modules.strategy_generator.service import StrategyGeneratorService

_logger = get_logger("reach_developments.strategy_execution_package")

# Top-N items for portfolio sub-lists.
_TOP_N = 5

# Execution readiness → sort order (lower = higher priority in portfolio view).
_READINESS_ORDER: Dict[str, int] = {
    "ready_for_review": 0,
    "caution_required": 1,
    "blocked_by_dependency": 2,
    "insufficient_data": 3,
}


# ---------------------------------------------------------------------------
# Pure helper functions (no I/O — easy to unit-test)
# ---------------------------------------------------------------------------


def _determine_execution_readiness(
    best: Optional[SimulationResult],
    has_feasibility_baseline: bool,
) -> ExecutionReadiness:
    """Classify execution readiness from strategy output.

    Returns:
      insufficient_data     — no best strategy available
      blocked_by_dependency — no feasibility baseline
      caution_required      — strategy carries high risk
      ready_for_review      — baseline present, strategy available, risk low/medium
    """
    if best is None:
        return "insufficient_data"
    if not has_feasibility_baseline:
        return "blocked_by_dependency"
    if best.risk_score == "high":
        return "caution_required"
    return "ready_for_review"


def _build_dependencies(
    best: Optional[SimulationResult],
    has_feasibility_baseline: bool,
) -> List[StrategyExecutionDependencyItem]:
    """Build the dependency check list for an execution package."""
    deps: List[StrategyExecutionDependencyItem] = []

    deps.append(
        StrategyExecutionDependencyItem(
            dependency_type="feasibility_baseline",
            dependency_label="Feasibility Baseline",
            dependency_status="cleared" if has_feasibility_baseline else "blocked",
            blocking_reason=(
                None
                if has_feasibility_baseline
                else (
                    "No approved feasibility baseline exists for this project. "
                    "Simulation outputs are based on default assumptions and are indicative only."
                )
            ),
        )
    )

    deps.append(
        StrategyExecutionDependencyItem(
            dependency_type="strategy_data",
            dependency_label="Strategy Data",
            dependency_status="cleared" if best is not None else "blocked",
            blocking_reason=(
                None
                if best is not None
                else (
                    "No strategy could be generated for this project. "
                    "Ensure a feasibility run has been calculated."
                )
            ),
        )
    )

    return deps


def _build_cautions(
    best: Optional[SimulationResult],
    has_feasibility_baseline: bool,
) -> List[StrategyExecutionCautionItem]:
    """Build the caution list for an execution package."""
    cautions: List[StrategyExecutionCautionItem] = []

    if not has_feasibility_baseline:
        cautions.append(
            StrategyExecutionCautionItem(
                severity="high",
                caution_title="Missing Feasibility Baseline",
                caution_description=(
                    "This project does not have an approved feasibility baseline. "
                    "All simulation outputs are based on default assumptions and are indicative only. "
                    "Establish a baseline before executing any strategy change."
                ),
            )
        )

    if best is not None:
        if best.risk_score == "high":
            cautions.append(
                StrategyExecutionCautionItem(
                    severity="high",
                    caution_title="High-Risk Strategy",
                    caution_description=(
                        "The recommended strategy carries a high risk classification. "
                        "Executive review and sign-off is required before proceeding."
                    ),
                )
            )
        elif best.risk_score == "medium":
            cautions.append(
                StrategyExecutionCautionItem(
                    severity="medium",
                    caution_title="Medium-Risk Strategy",
                    caution_description=(
                        "The recommended strategy carries a medium risk classification. "
                        "Review supporting simulation evidence carefully before proceeding."
                    ),
                )
            )

        if best.phase_delay_months > 3:
            cautions.append(
                StrategyExecutionCautionItem(
                    severity="medium",
                    caution_title="Extended Phase Delay",
                    caution_description=(
                        f"A phase delay of {best.phase_delay_months} months is recommended. "
                        "Validate cash flow impact and sales trajectory before approving the delay."
                    ),
                )
            )

    return cautions


def _build_actions(
    best: Optional[SimulationResult],
    has_feasibility_baseline: bool,
) -> List[StrategyExecutionActionItem]:
    """Build the ordered action step list for an execution package.

    Action sequence:
      1. Baseline dependency review (if no baseline)
      2. Simulation evidence review (when strategy exists)
      3. Pricing preparation (if |price_adj| >= 5%)
      4. Phasing preparation (if phase_delay > 0)
      5. Holdback or release readiness validation (if hold / accelerate)
      6. Executive review routing (if high risk)

    If no strategy data exists, a single resolution step is returned.
    """
    actions: List[StrategyExecutionActionItem] = []
    step = 1

    if best is None:
        # Only one action possible when there is no strategy data.
        actions.append(
            StrategyExecutionActionItem(
                step_number=step,
                action_type="baseline_dependency_review",
                action_title="Resolve Insufficient Strategy Data",
                action_description=(
                    "No strategy could be generated for this project. "
                    "Ensure a feasibility run exists and has been calculated, "
                    "then re-generate the strategy recommendation."
                ),
                target_area="feasibility",
                urgency="high",
                depends_on=None,
                review_required=True,
            )
        )
        return actions

    # Step: Baseline dependency review (if missing baseline — comes first).
    if not has_feasibility_baseline:
        actions.append(
            StrategyExecutionActionItem(
                step_number=step,
                action_type="baseline_dependency_review",
                action_title="Establish Feasibility Baseline",
                action_description=(
                    "Create and approve a feasibility run for this project before executing "
                    "the recommended strategy. Current simulation uses default assumptions."
                ),
                target_area="feasibility",
                urgency="high",
                depends_on=None,
                review_required=True,
            )
        )
        step += 1

    # Step: Simulation evidence review (always present when strategy data exists).
    irr_pct = round(best.irr * 100, 2)
    actions.append(
        StrategyExecutionActionItem(
            step_number=step,
            action_type="simulation_review",
            action_title="Review Simulation Evidence",
            action_description=(
                f"Review the simulation output supporting the recommended strategy. "
                f"Best scenario: {best.release_strategy} release at {best.price_adjustment_pct:+.0f}% "
                f"price adjustment with {best.phase_delay_months}mo phase delay. "
                f"Projected IRR: {irr_pct:.2f}% ({best.risk_score} risk)."
            ),
            target_area="review",
            urgency="high" if best.risk_score == "high" else "medium",
            depends_on=None,
            review_required=False,
        )
    )
    step += 1

    # Step: Pricing preparation (if significant price adjustment).
    if abs(best.price_adjustment_pct) >= 5.0:
        direction = "increase" if best.price_adjustment_pct > 0 else "reduction"
        actions.append(
            StrategyExecutionActionItem(
                step_number=step,
                action_type="pricing_update_preparation",
                action_title=f"Prepare Pricing {direction.capitalize()} Package",
                action_description=(
                    f"Prepare a pricing {direction} package of {best.price_adjustment_pct:+.0f}% "
                    "aligned with the recommended strategy. "
                    "Review unit pricing tiers and market comparables before submission."
                ),
                target_area="pricing",
                urgency="high" if best.price_adjustment_pct < 0 else "medium",
                depends_on=None,
                review_required=True,
            )
        )
        step += 1

    # Step: Phasing preparation (if phase delay recommended).
    if best.phase_delay_months > 0:
        actions.append(
            StrategyExecutionActionItem(
                step_number=step,
                action_type="phase_release_preparation",
                action_title="Prepare Phase Release Plan",
                action_description=(
                    f"Prepare a phase release plan incorporating a {best.phase_delay_months}-month delay. "
                    "Validate sales absorption rates and construction schedule alignment."
                ),
                target_area="phasing",
                urgency="high" if best.phase_delay_months > 3 else "medium",
                depends_on=None,
                review_required=True,
            )
        )
        step += 1

    # Step: Holdback validation (if hold release strategy).
    if best.release_strategy == "hold":
        actions.append(
            StrategyExecutionActionItem(
                step_number=step,
                action_type="holdback_validation",
                action_title="Validate Inventory Holdback",
                action_description=(
                    "The recommended strategy is to hold inventory. "
                    "Validate that current cash flow supports a holdback period "
                    "without compromising project funding covenants."
                ),
                target_area="release",
                urgency="medium",
                depends_on=None,
                review_required=True,
            )
        )
        step += 1

    # Step: Release readiness validation (if accelerate release strategy).
    elif best.release_strategy == "accelerate":
        actions.append(
            StrategyExecutionActionItem(
                step_number=step,
                action_type="phase_release_preparation",
                action_title="Validate Release Readiness",
                action_description=(
                    "The recommended strategy is to accelerate release. "
                    "Confirm sales team readiness, marketing materials, and legal documents "
                    "are in place before accelerating unit release."
                ),
                target_area="release",
                urgency="medium",
                depends_on=None,
                review_required=True,
            )
        )
        step += 1

    # Step: Executive review routing (if high risk — always last).
    if best.risk_score == "high":
        actions.append(
            StrategyExecutionActionItem(
                step_number=step,
                action_type="executive_review",
                action_title="Route for Executive Sign-Off",
                action_description=(
                    "This strategy carries a high risk classification. "
                    "Route the complete execution package to senior leadership for review "
                    "and approval before implementing any changes."
                ),
                target_area="review",
                urgency="high",
                depends_on=None,
                review_required=True,
            )
        )

    return actions


def _build_package_from_recommendation(
    rec: RecommendedStrategyResponse,
) -> ProjectStrategyExecutionPackageResponse:
    """Translate a RecommendedStrategyResponse into a full execution package.

    All source records are read-only — nothing is mutated.
    """
    best = rec.best_strategy
    project_id = rec.project_id
    project_name = rec.project_name
    has_baseline = rec.has_feasibility_baseline

    readiness = _determine_execution_readiness(best, has_baseline)
    dependencies = _build_dependencies(best, has_baseline)
    cautions = _build_cautions(best, has_baseline)
    actions = _build_actions(best, has_baseline)

    if best is None:
        summary = (
            f"Insufficient data to generate an execution package for {project_name}. "
            "No strategy could be generated — check project configuration."
        )
        expected_impact = "Unable to estimate impact — no strategy data available."
    else:
        irr_pct = round(best.irr * 100, 2)
        summary = (
            f"Execution package for {project_name}. "
            f"Recommended: {best.release_strategy} release with "
            f"{best.price_adjustment_pct:+.0f}% price adjustment and "
            f"{best.phase_delay_months}mo phase delay. "
            f"Execution readiness: {readiness.replace('_', ' ')}."
        )
        baseline_note = (
            "Baseline available — simulation is calibrated."
            if has_baseline
            else "No baseline — impact estimate is indicative only."
        )
        expected_impact = (
            f"Projected IRR: {irr_pct:.2f}% ({best.risk_score} risk). {baseline_note}"
        )

    supporting_metrics = StrategyExecutionSupportingMetrics(
        best_irr=best.irr if best else None,
        risk_score=best.risk_score if best else None,
        price_adjustment_pct=best.price_adjustment_pct if best else None,
        phase_delay_months=best.phase_delay_months if best else None,
        release_strategy=best.release_strategy if best else None,
    )

    requires_manual_review = readiness in (
        "blocked_by_dependency",
        "caution_required",
        "insufficient_data",
    ) or any(a.review_required for a in actions)

    return ProjectStrategyExecutionPackageResponse(
        project_id=project_id,
        project_name=project_name,
        has_feasibility_baseline=has_baseline,
        recommended_strategy=best.release_strategy if best else None,
        execution_readiness=readiness,
        summary=summary,
        actions=actions,
        dependencies=dependencies,
        cautions=cautions,
        supporting_metrics=supporting_metrics,
        expected_impact=expected_impact,
        requires_manual_review=requires_manual_review,
    )


def _build_portfolio_card(
    rec: RecommendedStrategyResponse,
    pkg: ProjectStrategyExecutionPackageResponse,
) -> PortfolioPackagedInterventionCard:
    """Convert a project package into a compact portfolio intervention card."""
    best = rec.best_strategy

    urgency_score = _compute_urgency_score(
        best_risk_score=best.risk_score if best else None,
        has_feasibility_baseline=rec.has_feasibility_baseline,
        best_price_adjustment_pct=best.price_adjustment_pct if best else None,
        best_phase_delay_months=best.phase_delay_months if best else None,
    )
    has_best_strategy = best is not None
    intervention_priority = _classify_intervention_priority(urgency_score, has_best_strategy)
    intervention_type = _classify_intervention_type(
        best_irr=best.irr if best else None,
        best_price_adjustment_pct=best.price_adjustment_pct if best else None,
        best_phase_delay_months=best.phase_delay_months if best else None,
    )

    blockers = [
        d.dependency_label for d in pkg.dependencies if d.dependency_status == "blocked"
    ]
    next_best_action = pkg.actions[0].action_title if pkg.actions else None

    return PortfolioPackagedInterventionCard(
        project_id=rec.project_id,
        project_name=rec.project_name,
        recommended_strategy=best.release_strategy if best else None,
        intervention_priority=intervention_priority,
        intervention_type=intervention_type,
        execution_readiness=pkg.execution_readiness,
        has_feasibility_baseline=rec.has_feasibility_baseline,
        requires_manual_review=pkg.requires_manual_review,
        next_best_action=next_best_action,
        blockers=blockers,
        urgency_score=urgency_score,
        expected_impact=pkg.expected_impact,
    )


def _rank_portfolio_cards(
    cards: List[PortfolioPackagedInterventionCard],
) -> List[PortfolioPackagedInterventionCard]:
    """Sort portfolio cards by the three-key deterministic ranking rule.

    Primary   : execution_readiness (ready_for_review=0 … insufficient_data=3)
    Secondary : urgency_score descending
    Tertiary  : project_name ascending (deterministic tie-break)
    """
    return sorted(
        cards,
        key=lambda c: (
            _READINESS_ORDER.get(c.execution_readiness, 3),
            -c.urgency_score,
            c.project_name,
        ),
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class StrategyExecutionPackageService:
    """Orchestrates strategy execution package generation.

    Reads project strategy outputs from StrategyGeneratorService and converts
    them into execution-ready action packages.

    All source records are read-only — nothing is mutated.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = StrategyExecutionPackageRepository(db)
        self._strategy_service = StrategyGeneratorService(db)

    def get_project_execution_package(
        self, project_id: str
    ) -> ProjectStrategyExecutionPackageResponse:
        """Generate an execution package for a single project.

        Raises ResourceNotFoundError if the project does not exist.
        All source records are read-only — nothing is mutated.
        """
        project = self._repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        try:
            rec = self._strategy_service.generate_recommended_strategy(project_id)
        except ResourceNotFoundError:
            raise
        except Exception:
            _logger.exception(
                "strategy_execution_package: strategy generation failed for project=%s",
                project_id,
            )
            # Return an insufficient_data package so the caller always gets a valid response.
            rec = RecommendedStrategyResponse(
                project_id=project_id,
                project_name=project.name,
                has_feasibility_baseline=False,
                best_strategy=None,
                top_strategies=[],
                reason="Strategy generation failed — check project configuration.",
                generated_scenario_count=0,
            )

        pkg = _build_package_from_recommendation(rec)

        _logger.info(
            "strategy_execution_package: project=%s readiness=%s actions=%d",
            project_id,
            pkg.execution_readiness,
            len(pkg.actions),
        )

        return pkg

    def build_portfolio_execution_packages(self) -> PortfolioExecutionPackageResponse:
        """Generate portfolio-level execution packages for all projects.

        Steps:
          1. Load all projects (single bulk query).
          2. Generate strategy + execution package for each project.
          3. Convert each project package into a compact portfolio card.
          4. Rank cards by three-key rule.
          5. Assemble summary KPIs and top-N sub-lists.
          6. Return PortfolioExecutionPackageResponse.

        Per-project failures are caught and logged; those projects receive an
        insufficient_data card rather than failing the whole response.

        All source records are read-only — nothing is mutated.
        """
        projects = self._repo.list_projects()

        cards: List[PortfolioPackagedInterventionCard] = []

        for project in projects:
            try:
                rec = self._strategy_service.generate_recommended_strategy(project.id)
                pkg = _build_package_from_recommendation(rec)
                card = _build_portfolio_card(rec, pkg)
            except Exception:
                _logger.exception(
                    "strategy_execution_package: portfolio — failed for project=%s",
                    project.id,
                )
                # Build an insufficient_data card so the project still appears.
                cards.append(
                    PortfolioPackagedInterventionCard(
                        project_id=project.id,
                        project_name=project.name,
                        recommended_strategy=None,
                        intervention_priority="insufficient_data",
                        intervention_type="insufficient_data",
                        execution_readiness="insufficient_data",
                        has_feasibility_baseline=False,
                        requires_manual_review=True,
                        next_best_action="Resolve Insufficient Strategy Data",
                        blockers=["Strategy Data", "Feasibility Baseline"],
                        urgency_score=0,
                        expected_impact="Unable to estimate impact — strategy generation failed.",
                    )
                )
                continue

            cards.append(card)

        ranked_cards = _rank_portfolio_cards(cards)

        # --- Summary KPIs -------------------------------------------------
        ready_count = sum(
            1 for c in ranked_cards if c.execution_readiness == "ready_for_review"
        )
        blocked_count = sum(
            1 for c in ranked_cards if c.execution_readiness == "blocked_by_dependency"
        )
        caution_count = sum(
            1 for c in ranked_cards if c.execution_readiness == "caution_required"
        )
        no_data_count = sum(
            1 for c in ranked_cards if c.execution_readiness == "insufficient_data"
        )

        summary = PortfolioExecutionPackageSummary(
            total_projects=len(ranked_cards),
            ready_for_review_count=ready_count,
            blocked_count=blocked_count,
            caution_required_count=caution_count,
            insufficient_data_count=no_data_count,
        )

        # --- Top-N sub-lists ----------------------------------------------
        top_ready = [
            c for c in ranked_cards if c.execution_readiness == "ready_for_review"
        ][:_TOP_N]

        top_blocked = sorted(
            [c for c in ranked_cards if c.execution_readiness == "blocked_by_dependency"],
            key=lambda c: (-c.urgency_score, c.project_name),
        )[:_TOP_N]

        top_high_risk = sorted(
            [c for c in ranked_cards if c.execution_readiness == "caution_required"],
            key=lambda c: (-c.urgency_score, c.project_name),
        )[:_TOP_N]

        _logger.info(
            "strategy_execution_package: portfolio total=%d ready=%d blocked=%d caution=%d no_data=%d",
            len(ranked_cards),
            ready_count,
            blocked_count,
            caution_count,
            no_data_count,
        )

        return PortfolioExecutionPackageResponse(
            summary=summary,
            top_ready_actions=top_ready,
            top_blocked_actions=top_blocked,
            top_high_risk_packages=top_high_risk,
            packages=ranked_cards,
        )
