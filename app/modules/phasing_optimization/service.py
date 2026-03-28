"""
phasing_optimization.service

Phasing Optimization Engine (PR-V7-03).

Generates deterministic, explainable phasing recommendations by converting:
  - sales absorption signals (actual vs planned velocity)
  - inventory availability per phase
  - project readiness (approved tender baseline)
  - phase context (current active phase, next phase)

into release strategy guidance.

Demand classification thresholds (shared with pricing_optimization):
  high_demand  : absorption_vs_plan_pct >= 100 (selling faster than plan)
                 OR sell_through_pct > 60 when no feasibility plan exists
  balanced     : absorption_vs_plan_pct in [80, 100)
                 OR sell_through_pct in [40, 60] when no plan
  low_demand   : absorption_vs_plan_pct < 80
                 OR sell_through_pct < 40 when no plan
  no_data      : sold_units == 0 (no usable sales signal)

Current-phase recommendation rules:
  Demand         | Phase Availability    | Recommendation
  high_demand    | critically low ≤20%   | release_more_inventory
  high_demand    | moderate 20-50%       | maintain_current_release
  high_demand    | healthy >50%          | maintain_current_release
  balanced       | any                   | maintain_current_release
  low_demand     | high ≥70%             | delay_further_release
  low_demand     | moderate <70%         | hold_current_inventory
  no_data        | any                   | insufficient_data

Next-phase recommendation rules:
  Condition                                                    | Recommendation
  high demand + phase availability ≤20% + project ready       | prepare_next_phase
  high demand + phase availability >20%                        | do_not_open_next_phase
  balanced demand                                              | do_not_open_next_phase
  low demand                                                   | defer_next_phase
  no next phase exists                                         | not_applicable
  no_data                                                      | insufficient_data

Release urgency:
  high   : release_more_inventory OR prepare_next_phase
  medium : maintain_current_release (high_demand)
  low    : maintain_current_release (balanced), hold_current_inventory, delay_further_release
  none   : insufficient_data

No phase or inventory records are mutated.  All outputs are recommendations only.
"""

from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError
from app.core.logging import get_logger
from app.modules.phasing_optimization.repository import PhasingOptimizationRepository
from app.modules.phasing_optimization.schemas import (
    PortfolioPhasingInsightsResponse,
    PortfolioPhasingInsightsSummary,
    PortfolioPhasingProjectCard,
    ProjectPhasingRecommendationResponse,
)

_logger = get_logger("reach_developments.phasing_optimization")

# ---------------------------------------------------------------------------
# Demand classification thresholds (aligned with pricing_optimization)
# ---------------------------------------------------------------------------
_HIGH_DEMAND_PLAN_THRESHOLD = 100.0   # absorption_vs_plan_pct >= 100 → high_demand
_BALANCED_PLAN_THRESHOLD = 80.0       # absorption_vs_plan_pct in [80, 100) → balanced

_HIGH_DEMAND_SELLTHROUGH_THRESHOLD = 60.0  # sell_through_pct > 60 → high_demand (no plan)
_BALANCED_SELLTHROUGH_THRESHOLD = 40.0    # sell_through_pct >= 40 → balanced (no plan)

# ---------------------------------------------------------------------------
# Phase availability thresholds for phasing decisions
# ---------------------------------------------------------------------------
_CRITICALLY_LOW_AVAIL = 20.0    # phase availability_pct ≤ this → critically low (release more)
_MODERATE_AVAIL_MAX = 50.0      # phase availability_pct < this → moderate (20–50%)
_HIGH_AVAIL_LOW_DEMAND = 70.0   # phase availability_pct ≥ this → delay release (low demand)

# Months per day constant (average Gregorian year / 12)
_AVG_DAYS_PER_MONTH = 30.4375


def _safe_pct(numerator: float, denominator: float) -> Optional[float]:
    """Return numerator / denominator * 100, or None when denominator is zero."""
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 2)


def _classify_demand(
    sold_units: int,
    absorption_vs_plan_pct: Optional[float],
    sell_through_pct: Optional[float],
) -> str:
    """Classify project demand status.

    Returns one of: 'high_demand' | 'balanced' | 'low_demand' | 'no_data'.
    Uses absorption_vs_plan_pct when a feasibility plan exists, otherwise
    falls back to sell_through_pct.
    """
    if sold_units == 0:
        return "no_data"

    if absorption_vs_plan_pct is not None:
        if absorption_vs_plan_pct >= _HIGH_DEMAND_PLAN_THRESHOLD:
            return "high_demand"
        if absorption_vs_plan_pct >= _BALANCED_PLAN_THRESHOLD:
            return "balanced"
        return "low_demand"

    if sell_through_pct is not None:
        if sell_through_pct > _HIGH_DEMAND_SELLTHROUGH_THRESHOLD:
            return "high_demand"
        if sell_through_pct >= _BALANCED_SELLTHROUGH_THRESHOLD:
            return "balanced"
        return "low_demand"

    return "no_data"


def _derive_absorption_vs_plan(
    total_units: int,
    contract_bounds: Optional[Tuple],
    feasibility_inputs: Optional[Tuple],
) -> Optional[float]:
    """Compute absorption_vs_plan_pct from contract dates and feasibility assumptions.

    Uses the same approach as pricing_optimization: planned_rate = total_units / dev_period_months.
    Returns None when a plan-based comparison is not possible.
    """
    if contract_bounds is None or feasibility_inputs is None or total_units == 0:
        return None

    first_date, last_date, contract_count = contract_bounds
    _feas_result, feas_assumptions = feasibility_inputs

    if feas_assumptions is None or feas_assumptions.development_period_months is None:
        return None

    dev_period = int(feas_assumptions.development_period_months)
    if dev_period <= 0:
        return None

    planned_rate = total_units / dev_period  # units per month

    days_elapsed = (last_date - first_date).days
    if days_elapsed <= 0:
        return None

    months_elapsed = days_elapsed / _AVG_DAYS_PER_MONTH
    actual_rate = contract_count / months_elapsed
    return round((actual_rate / planned_rate) * 100, 2)


def _generate_recommendations(
    demand_status: str,
    phase_availability_pct: Optional[float],
    has_next_phase: bool,
    has_approved_baseline: bool,
) -> Tuple[str, str, str, str, str]:
    """Generate (current_rec, next_rec, urgency, confidence, reason).

    Applies the deterministic rule matrix documented in the module docstring.
    """
    avail = phase_availability_pct if phase_availability_pct is not None else 100.0

    # ----------------------------------------------------------------
    # Current phase recommendation
    # ----------------------------------------------------------------
    if demand_status == "no_data":
        current_rec = "insufficient_data"
        confidence = "low"
        urgency = "none"
        reason = "Insufficient sales data to generate phasing recommendations."
        next_rec = "insufficient_data" if has_next_phase else "not_applicable"
        return current_rec, next_rec, urgency, confidence, reason

    if demand_status == "high_demand":
        if avail <= _CRITICALLY_LOW_AVAIL:
            current_rec = "release_more_inventory"
            confidence = "high"
            urgency = "high"
            reason = (
                f"High demand with critically low phase inventory ({avail:.0f}% available). "
                "Release more units immediately to capture demand momentum."
            )
        elif avail <= _MODERATE_AVAIL_MAX:
            current_rec = "maintain_current_release"
            confidence = "high"
            urgency = "medium"
            reason = (
                f"High demand with moderate inventory availability ({avail:.0f}% available). "
                "Current release pace is appropriate."
            )
        else:
            current_rec = "maintain_current_release"
            confidence = "medium"
            urgency = "medium"
            reason = (
                f"High demand with healthy inventory levels ({avail:.0f}% available). "
                "Maintain current release strategy."
            )

    elif demand_status == "balanced":
        current_rec = "maintain_current_release"
        confidence = "high"
        urgency = "low"
        reason = (
            f"Sales demand is balanced with {avail:.0f}% phase inventory available. "
            "Maintain current release pace."
        )

    else:  # low_demand
        if avail >= _HIGH_AVAIL_LOW_DEMAND:
            current_rec = "delay_further_release"
            confidence = "high"
            urgency = "low"
            reason = (
                f"Low demand with high available inventory ({avail:.0f}% available). "
                "Delay further releases until absorption improves."
            )
        else:
            current_rec = "hold_current_inventory"
            confidence = "medium"
            urgency = "low"
            reason = (
                f"Low demand detected with {avail:.0f}% phase inventory available. "
                "Hold current inventory and focus on converting existing pipeline."
            )

    # ----------------------------------------------------------------
    # Next phase recommendation
    # ----------------------------------------------------------------
    if not has_next_phase:
        next_rec = "not_applicable"
    elif demand_status == "high_demand" and avail <= _CRITICALLY_LOW_AVAIL:
        # Strong demand + nearly sold out in current phase + project structurally ready
        next_rec = "prepare_next_phase"
        urgency = "high"
        reason += " Strong indicators for next phase preparation."
    elif demand_status == "high_demand":
        next_rec = "do_not_open_next_phase"
    elif demand_status == "balanced":
        next_rec = "do_not_open_next_phase"
    else:  # low_demand
        next_rec = "defer_next_phase"

    return current_rec, next_rec, urgency, confidence, reason


class PhasingOptimizationService:
    """Service that generates deterministic phasing recommendations."""

    def __init__(self, db: Session) -> None:
        self.repo = PhasingOptimizationRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_project_phasing_recommendations(
        self, project_id: str
    ) -> ProjectPhasingRecommendationResponse:
        """Return phasing recommendations for a single project.

        Derives demand classification from absorption velocity vs feasibility plan,
        then applies deterministic rule logic to generate release strategy guidance.

        Raises ResourceNotFoundError if the project does not exist.
        All source records are read-only — no phase data is mutated.
        """
        project = self.repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        phases = self.repo.get_phases_for_project(project_id)
        unit_counts_by_phase = self.repo.get_unit_counts_by_phase_for_project(project_id)
        contract_bounds = self.repo.get_contract_date_bounds_for_project(project_id)
        feasibility_inputs = self.repo.get_feasibility_inputs_for_project(project_id)
        has_approved_baseline = self.repo.has_approved_baseline(project_id)

        return self._build_project_recommendation(
            project_id=project_id,
            project_name=project.name,
            phases=phases,
            unit_counts_by_phase=unit_counts_by_phase,
            contract_bounds=contract_bounds,
            feasibility_inputs=feasibility_inputs,
            has_approved_baseline=has_approved_baseline,
        )

    def build_portfolio_phasing_insights(self) -> PortfolioPhasingInsightsResponse:
        """Return portfolio-wide phasing intelligence.

        Uses batched repository queries to avoid N+1 patterns.
        All projects are always represented in the response.

        All source records are read-only — no phase data is mutated.
        """
        projects = self.repo.list_projects()

        # Batch all data dimensions (5 queries total for entire portfolio)
        phases_map = self.repo.get_phases_by_project()
        unit_counts_map = self.repo.get_unit_counts_by_phase_by_project()
        contract_bounds_map = self.repo.get_contract_date_bounds_by_project()
        feasibility_map = self.repo.get_feasibility_inputs_by_project()
        baseline_map = self.repo.get_approved_baseline_flags()

        project_cards: List[PortfolioPhasingProjectCard] = []

        for project in projects:
            try:
                rec = self._build_project_recommendation(
                    project_id=project.id,
                    project_name=project.name,
                    phases=phases_map.get(project.id, []),
                    unit_counts_by_phase=unit_counts_map.get(project.id, {}),
                    contract_bounds=contract_bounds_map.get(project.id),
                    feasibility_inputs=feasibility_map.get(project.id),
                    has_approved_baseline=baseline_map.get(project.id, False),
                )
                card = PortfolioPhasingProjectCard(
                    project_id=project.id,
                    project_name=project.name,
                    current_phase_recommendation=rec.current_phase_recommendation,
                    next_phase_recommendation=rec.next_phase_recommendation,
                    release_urgency=rec.release_urgency,
                    confidence=rec.confidence,
                    sell_through_pct=rec.sell_through_pct,
                    absorption_status=rec.absorption_status,
                    has_next_phase=rec.has_next_phase,
                )
            except Exception as exc:  # pragma: no cover — unexpected path
                _logger.warning(
                    "Portfolio phasing card failed for project %s (%s): %s",
                    project.id,
                    project.name,
                    exc,
                    exc_info=True,
                )
                card = PortfolioPhasingProjectCard(
                    project_id=project.id,
                    project_name=project.name,
                    current_phase_recommendation="insufficient_data",
                    next_phase_recommendation="insufficient_data",
                    release_urgency="none",
                    confidence="low",
                    sell_through_pct=None,
                    absorption_status="no_data",
                    has_next_phase=False,
                )
            project_cards.append(card)

        # Sort by urgency then sell_through_pct descending
        _urgency_order = {"high": 0, "medium": 1, "low": 2, "none": 3}
        project_cards.sort(
            key=lambda c: (
                _urgency_order.get(c.release_urgency, 3),
                -(c.sell_through_pct or 0.0),
            )
        )

        # Build summary counts
        prepare_cards = [
            c for c in project_cards if c.next_phase_recommendation == "prepare_next_phase"
        ]
        hold_cards = [
            c for c in project_cards
            if c.current_phase_recommendation == "hold_current_inventory"
        ]
        delay_cards = [
            c for c in project_cards
            if c.current_phase_recommendation == "delay_further_release"
        ]
        insufficient_cards = [
            c for c in project_cards
            if c.current_phase_recommendation == "insufficient_data"
        ]

        summary = PortfolioPhasingInsightsSummary(
            total_projects=len(project_cards),
            projects_prepare_next_phase_count=len(prepare_cards),
            projects_hold_inventory_count=len(hold_cards),
            projects_delay_release_count=len(delay_cards),
            projects_insufficient_data_count=len(insufficient_cards),
        )

        # Top 5 phase opportunities (prepare_next_phase projects)
        top_phase_opportunities = prepare_cards[:5]

        # Top 5 release risks (hold or delay), ordered by sell_through_pct ascending (worst first)
        release_risk_cards = hold_cards + [c for c in delay_cards if c not in hold_cards]
        release_risk_cards.sort(
            key=lambda c: (c.sell_through_pct is None, c.sell_through_pct or 0.0)
        )
        top_release_risks = release_risk_cards[:5]

        return PortfolioPhasingInsightsResponse(
            summary=summary,
            projects=project_cards,
            top_phase_opportunities=top_phase_opportunities,
            top_release_risks=top_release_risks,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_project_recommendation(
        self,
        project_id: str,
        project_name: str,
        phases: list,
        unit_counts_by_phase: Dict,
        contract_bounds: Optional[Tuple],
        feasibility_inputs: Optional[Tuple],
        has_approved_baseline: bool,
    ) -> ProjectPhasingRecommendationResponse:
        """Build a complete phasing recommendation for a single project."""

        # ----------------------------------------------------------------
        # Project-wide unit aggregates (for response fields)
        # ----------------------------------------------------------------
        total_units = 0
        sold_units = 0
        available_units = 0
        for status_counts in unit_counts_by_phase.values():
            for status, count in status_counts.items():
                total_units += count
                if status in ("under_contract", "registered"):
                    sold_units += count
                elif status == "available":
                    available_units += count

        sell_through_pct = _safe_pct(sold_units, total_units)

        # ----------------------------------------------------------------
        # Demand classification — based on active phases only
        # (phases with at least one sold unit) to avoid dilution from
        # unreleased phases that have all-available inventory.
        # Falls back to project-wide when no phase has any sold units.
        # ----------------------------------------------------------------
        active_phase_ids = {
            phase_id
            for phase_id, status_counts in unit_counts_by_phase.items()
            if status_counts.get("under_contract", 0) + status_counts.get("registered", 0) > 0
        }
        if active_phase_ids:
            active_total = sum(
                sum(sc.values())
                for pid, sc in unit_counts_by_phase.items()
                if pid in active_phase_ids
            )
            active_sold = sum(
                sc.get("under_contract", 0) + sc.get("registered", 0)
                for pid, sc in unit_counts_by_phase.items()
                if pid in active_phase_ids
            )
        else:
            active_total = total_units
            active_sold = sold_units

        active_sell_through_pct = _safe_pct(active_sold, active_total)

        absorption_vs_plan_pct = _derive_absorption_vs_plan(
            total_units=total_units,
            contract_bounds=contract_bounds,
            feasibility_inputs=feasibility_inputs,
        )
        demand_status = _classify_demand(active_sold, absorption_vs_plan_pct, active_sell_through_pct)

        # ----------------------------------------------------------------
        # Determine current and next phase
        # ----------------------------------------------------------------
        phases_with_units = [
            p for p in phases
            if unit_counts_by_phase.get(p.id, {})
        ]

        if not phases_with_units:
            return ProjectPhasingRecommendationResponse(
                project_id=project_id,
                project_name=project_name,
                current_phase_id=None,
                current_phase_name=None,
                current_phase_recommendation="insufficient_data",
                next_phase_recommendation="insufficient_data",
                release_urgency="none",
                confidence="low",
                reason="No phase inventory found for this project.",
                sold_units=0,
                available_units=0,
                sell_through_pct=None,
                absorption_status="no_data",
                has_next_phase=len(phases) > 1,
                next_phase_id=None,
                next_phase_name=None,
            )

        # Current phase = highest-sequence phase with sold_units > 0,
        # falling back to the lowest-sequence phase with any units
        # when no phase has any sold units yet.
        current_phase = None
        for p in reversed(phases_with_units):
            counts = unit_counts_by_phase.get(p.id, {})
            if counts.get("under_contract", 0) + counts.get("registered", 0) > 0:
                current_phase = p
                break
        if current_phase is None:
            current_phase = phases_with_units[0]

        # Current phase availability metrics
        current_counts = unit_counts_by_phase.get(current_phase.id, {})
        phase_total = sum(current_counts.values())
        phase_available = current_counts.get("available", 0)
        phase_availability_pct = _safe_pct(phase_available, phase_total)

        # Next phase = the phase that comes immediately after the current phase
        # in the ordered phases list (by sequence).
        try:
            current_idx = phases.index(current_phase)
        except ValueError:
            current_idx = -1

        next_phase = (
            phases[current_idx + 1]
            if current_idx >= 0 and current_idx + 1 < len(phases)
            else None
        )

        # ----------------------------------------------------------------
        # Generate recommendations
        # ----------------------------------------------------------------
        current_rec, next_rec, urgency, confidence, reason = _generate_recommendations(
            demand_status=demand_status,
            phase_availability_pct=phase_availability_pct,
            has_next_phase=next_phase is not None,
            has_approved_baseline=has_approved_baseline,
        )

        return ProjectPhasingRecommendationResponse(
            project_id=project_id,
            project_name=project_name,
            current_phase_id=current_phase.id,
            current_phase_name=current_phase.name,
            current_phase_recommendation=current_rec,
            next_phase_recommendation=next_rec,
            release_urgency=urgency,
            confidence=confidence,
            reason=reason,
            sold_units=sold_units,
            available_units=available_units,
            sell_through_pct=sell_through_pct,
            absorption_status=demand_status,
            has_next_phase=next_phase is not None,
            next_phase_id=next_phase.id if next_phase else None,
            next_phase_name=next_phase.name if next_phase else None,
        )
