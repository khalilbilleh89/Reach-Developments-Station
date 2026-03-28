"""
pricing_optimization.service

Demand-Responsive Pricing Optimization Engine (PR-V7-02).

Generates deterministic, explainable pricing recommendations from:
  - absorption metrics (actual vs planned sales velocity)
  - unit inventory (availability per unit type)
  - formal pricing records (current avg price per unit type)

Rules are intentionally transparent and documented inline.

Demand classification thresholds:
  high_demand  : absorption_vs_plan_pct >= 100 (selling faster than plan)
                 OR sell_through_pct > 60 when no feasibility plan exists
  balanced     : absorption_vs_plan_pct in [80, 100)
                 OR sell_through_pct in [40, 60] when no plan
  low_demand   : absorption_vs_plan_pct < 80
                 OR sell_through_pct < 40 when no plan
  no_data      : unit_type_sold_units == 0 (no usable sales signal for demand classification)

Recommendation thresholds (change_pct applied to current_avg_price):
  high_demand + availability_pct ≤ 20 %  → +8 %  (confidence: high)
  high_demand + availability_pct ≤ 40 %  → +5 %  (confidence: high)
  high_demand + availability_pct > 40 %  → +2 %  (confidence: medium)
  balanced                               → 0 %   (confidence: high)
  low_demand + availability_pct ≥ 70 %   → −8 %  (confidence: high)
  low_demand + availability_pct ≥ 50 %   → −5 %  (confidence: medium)
  low_demand + availability_pct < 50 %   → −3 %  (confidence: low)
  no_data                                → None  (confidence: insufficient_data)

No pricing records are mutated.  All outputs are recommendations only.
"""

from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError
from app.core.logging import get_logger
from app.modules.pricing_optimization.repository import PricingOptimizationRepository
from app.modules.pricing_optimization.schemas import (
    PortfolioPricingInsightsResponse,
    PortfolioPricingInsightsSummary,
    PortfolioPricingProjectCard,
    ProjectPricingRecommendationsResponse,
    UnitTypePricingRecommendation,
)

_logger = get_logger("reach_developments.pricing_optimization")

# ---------------------------------------------------------------------------
# Demand classification thresholds
# ---------------------------------------------------------------------------
_HIGH_DEMAND_PLAN_THRESHOLD = 100.0   # absorption_vs_plan_pct ≥ 100 → high
_BALANCED_PLAN_THRESHOLD = 80.0       # absorption_vs_plan_pct ≥ 80 → balanced

_HIGH_DEMAND_SELLTHROUGH_THRESHOLD = 60.0  # sell_through_pct > 60 → high (no plan)
_BALANCED_SELLTHROUGH_THRESHOLD = 40.0    # sell_through_pct >= 40 → balanced (no plan)

# ---------------------------------------------------------------------------
# Recommendation thresholds
# ---------------------------------------------------------------------------
_HIGH_DEMAND_CRITICAL_AVAIL = 20.0   # availability_pct ≤ this → +8 %
_HIGH_DEMAND_LOW_AVAIL = 40.0        # availability_pct ≤ this → +5 %
_HIGH_CHANGE_PCT = 8.0
_MED_HIGH_CHANGE_PCT = 5.0
_LOW_CHANGE_PCT = 2.0

_LOW_DEMAND_HIGH_AVAIL = 70.0        # availability_pct ≥ this → −8 %
_LOW_DEMAND_MED_AVAIL = 50.0         # availability_pct ≥ this → −5 %
_NEG_HIGH_CHANGE_PCT = -8.0
_NEG_MED_CHANGE_PCT = -5.0
_NEG_LOW_CHANGE_PCT = -3.0

# Months per day constant (average Gregorian year / 12)
_AVG_DAYS_PER_MONTH = 30.4375


def _safe_pct(numerator: float, denominator: float) -> Optional[float]:
    """Return numerator / denominator * 100, or None when denominator is zero."""
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 2)


class PricingOptimizationService:
    """Service that generates demand-responsive pricing recommendations."""

    def __init__(self, db: Session) -> None:
        self.repo = PricingOptimizationRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_pricing_recommendations(
        self, project_id: str
    ) -> ProjectPricingRecommendationsResponse:
        """Return per-unit-type pricing recommendations for a project.

        Derives demand status from absorption velocity vs feasibility plan,
        then applies deterministic recommendation rules per unit type.

        Raises ResourceNotFoundError if the project does not exist.
        All source records are read-only — no pricing data is mutated.
        """
        project = self.repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        # Batch all data for this project
        unit_type_status_counts = self.repo.get_unit_type_status_counts_for_project(project_id)
        avg_prices = self.repo.get_avg_price_by_unit_type_for_project(project_id)
        contract_bounds = self.repo.get_contract_date_bounds_for_project(project_id)
        feasibility_inputs = self.repo.get_feasibility_inputs_for_project(project_id)

        # Compute project-level demand context
        absorption_vs_plan_pct, sell_through_pct, demand_context = (
            self._derive_project_demand_context(
                unit_type_status_counts=unit_type_status_counts,
                contract_bounds=contract_bounds,
                feasibility_inputs=feasibility_inputs,
            )
        )

        # Build per-unit-type recommendations
        has_pricing_data = bool(avg_prices)
        recommendations: List[UnitTypePricingRecommendation] = []

        for unit_type in sorted(unit_type_status_counts.keys()):
            status_counts = unit_type_status_counts[unit_type]
            rec = self._build_unit_type_recommendation(
                unit_type=unit_type,
                status_counts=status_counts,
                avg_price=avg_prices.get(unit_type),
                absorption_vs_plan_pct=absorption_vs_plan_pct,
                project_sell_through_pct=sell_through_pct,
            )
            recommendations.append(rec)

        return ProjectPricingRecommendationsResponse(
            project_id=project_id,
            project_name=project.name,
            recommendations=recommendations,
            has_pricing_data=has_pricing_data,
            demand_context=demand_context,
        )

    def build_portfolio_pricing_insights(self) -> PortfolioPricingInsightsResponse:
        """Return portfolio-wide pricing intelligence.

        Uses batched repository queries to avoid N+1 patterns.
        All projects are always represented in the response.

        All source records are read-only — no pricing data is mutated.
        """
        projects = self.repo.list_projects()

        # Batch all data dimensions
        unit_type_counts_map = self.repo.get_unit_type_status_counts_by_project()
        avg_prices_map = self.repo.get_avg_price_by_unit_type_by_project()
        contract_bounds_map = self.repo.get_contract_date_bounds_by_project()
        feasibility_map = self.repo.get_feasibility_inputs_by_project()

        project_cards: List[PortfolioPricingProjectCard] = []

        for project in projects:
            try:
                card = self._build_portfolio_project_card(
                    project=project,
                    unit_type_status_counts=unit_type_counts_map.get(project.id, {}),
                    avg_prices=avg_prices_map.get(project.id, {}),
                    contract_bounds=contract_bounds_map.get(project.id),
                    feasibility_inputs=feasibility_map.get(project.id),
                )
            except Exception as exc:  # pragma: no cover — unexpected path
                _logger.warning(
                    "Portfolio pricing card failed for project %s (%s): %s",
                    project.id,
                    project.name,
                    exc,
                    exc_info=True,
                )
                card = PortfolioPricingProjectCard(
                    project_id=project.id,
                    project_name=project.name,
                    pricing_status="no_data",
                    avg_recommended_adjustment_pct=None,
                    recommendation_count=0,
                    high_demand_unit_types=[],
                    low_demand_unit_types=[],
                )
            project_cards.append(card)

        # Sort by avg_recommended_adjustment_pct descending (highest opportunity first)
        project_cards.sort(
            key=lambda c: (
                c.avg_recommended_adjustment_pct is None,
                -(c.avg_recommended_adjustment_pct or 0.0),
            )
        )

        # Portfolio summary
        total_projects = len(project_cards)
        projects_with_pricing_data = sum(
            1
            for project in projects
            if project.id in avg_prices_map and avg_prices_map[project.id]
        )
        underpriced = sum(1 for c in project_cards if c.pricing_status == "underpriced")
        overpriced = sum(1 for c in project_cards if c.pricing_status == "overpriced")
        balanced = sum(1 for c in project_cards if c.pricing_status == "balanced")

        adj_cards = [
            c for c in project_cards if c.avg_recommended_adjustment_pct is not None
        ]
        avg_adjustment = (
            round(
                sum(c.avg_recommended_adjustment_pct for c in adj_cards)  # type: ignore[arg-type]
                / len(adj_cards),
                2,
            )
            if adj_cards
            else None
        )

        summary = PortfolioPricingInsightsSummary(
            total_projects=total_projects,
            projects_with_pricing_data=projects_with_pricing_data,
            avg_recommended_adjustment_pct=avg_adjustment,
            projects_underpriced=underpriced,
            projects_overpriced=overpriced,
            projects_balanced=balanced,
        )

        # Top opportunities (underpriced, highest upward adjustment first)
        top_opportunities = [c for c in project_cards if c.pricing_status == "underpriced"][:5]

        # Pricing risk zones (overpriced)
        pricing_risk_zones = [c for c in project_cards if c.pricing_status == "overpriced"]

        return PortfolioPricingInsightsResponse(
            summary=summary,
            projects=project_cards,
            top_opportunities=top_opportunities,
            pricing_risk_zones=pricing_risk_zones,
        )

    # ------------------------------------------------------------------
    # Demand derivation
    # ------------------------------------------------------------------

    def _derive_project_demand_context(
        self,
        unit_type_status_counts: Dict[str, Dict[str, int]],
        contract_bounds: Optional[Tuple],
        feasibility_inputs: Optional[Tuple],
    ) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """Derive (absorption_vs_plan_pct, sell_through_pct, demand_context_note).

        Returns three values:
          absorption_vs_plan_pct — actual / planned * 100; None when unavailable
          sell_through_pct       — sold / total * 100; None when no units
          demand_context         — human-readable demand context note
        """
        # Aggregate unit counts across all types
        total_units = 0
        sold_units = 0
        for status_counts in unit_type_status_counts.values():
            for status, count in status_counts.items():
                total_units += count
                if status in ("under_contract", "registered"):
                    sold_units += count

        sell_through_pct = _safe_pct(sold_units, total_units)

        # Absorption rate from contract dates
        absorption_rate_per_month: Optional[float] = None
        if contract_bounds is not None:
            first_date, last_date, contract_count = contract_bounds
            days_elapsed = (last_date - first_date).days
            if days_elapsed > 0:
                months_elapsed = days_elapsed / _AVG_DAYS_PER_MONTH
                absorption_rate_per_month = round(contract_count / months_elapsed, 4)

        # Planned rate from feasibility
        planned_absorption_rate_per_month: Optional[float] = None
        if feasibility_inputs is not None:
            _feas_result, feas_assumptions = feasibility_inputs
            if (
                feas_assumptions is not None
                and feas_assumptions.development_period_months is not None
                and total_units > 0
            ):
                dev_period = int(feas_assumptions.development_period_months)
                if dev_period > 0:
                    planned_absorption_rate_per_month = total_units / dev_period

        # Absorption vs plan
        absorption_vs_plan_pct: Optional[float] = None
        if (
            absorption_rate_per_month is not None
            and planned_absorption_rate_per_month is not None
            and planned_absorption_rate_per_month > 0
        ):
            absorption_vs_plan_pct = round(
                (absorption_rate_per_month / planned_absorption_rate_per_month) * 100, 2
            )

        # Demand context note
        demand_context: Optional[str]
        if absorption_vs_plan_pct is not None:
            if absorption_vs_plan_pct >= _HIGH_DEMAND_PLAN_THRESHOLD:
                demand_context = (
                    f"Sales velocity is {absorption_vs_plan_pct:.1f}% of plan — "
                    "project is selling faster than planned."
                )
            elif absorption_vs_plan_pct >= _BALANCED_PLAN_THRESHOLD:
                demand_context = (
                    f"Sales velocity is {absorption_vs_plan_pct:.1f}% of plan — "
                    "project is on plan."
                )
            else:
                demand_context = (
                    f"Sales velocity is {absorption_vs_plan_pct:.1f}% of plan — "
                    "project is behind absorption plan."
                )
        elif sell_through_pct is not None:
            demand_context = (
                f"No feasibility plan available. "
                f"Sell-through is {sell_through_pct:.1f}%."
            )
        else:
            demand_context = None

        return absorption_vs_plan_pct, sell_through_pct, demand_context

    # ------------------------------------------------------------------
    # Unit-type recommendation builder
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_demand(
        absorption_vs_plan_pct: Optional[float],
        sell_through_pct: Optional[float],
        unit_type_sell_through_pct: Optional[float],
        unit_type_sold_units: int,
    ) -> str:
        """Classify demand for a unit type.

        Returns 'no_data' immediately when the unit type has no recorded sales
        (sold_units == 0) — insufficient signal to classify demand.

        Uses absorption_vs_plan_pct (project-level) as primary signal when
        available.  Falls back to sell_through_pct comparisons when no
        feasibility plan exists.

        Returns 'high_demand' | 'balanced' | 'low_demand' | 'no_data'.
        """
        # No sales activity at all → insufficient signal
        if unit_type_sold_units == 0:
            return "no_data"

        if absorption_vs_plan_pct is not None:
            if absorption_vs_plan_pct >= _HIGH_DEMAND_PLAN_THRESHOLD:
                return "high_demand"
            if absorption_vs_plan_pct >= _BALANCED_PLAN_THRESHOLD:
                return "balanced"
            return "low_demand"

        # No plan: use unit-type sell-through as proxy
        st = unit_type_sell_through_pct if unit_type_sell_through_pct is not None else sell_through_pct
        if st is None:
            return "no_data"
        if st > _HIGH_DEMAND_SELLTHROUGH_THRESHOLD:
            return "high_demand"
        if st >= _BALANCED_SELLTHROUGH_THRESHOLD:
            return "balanced"
        return "low_demand"

    @staticmethod
    def _recommend(
        demand_status: str,
        availability_pct: Optional[float],
    ) -> Tuple[Optional[float], str, str]:
        """Return (change_pct, confidence, reason) for a demand/availability combination.

        All thresholds are documented at the top of this module.
        """
        if demand_status == "no_data":
            return (
                None,
                "insufficient_data",
                "Insufficient sales data for pricing recommendation.",
            )

        if demand_status == "high_demand":
            if availability_pct is not None and availability_pct <= _HIGH_DEMAND_CRITICAL_AVAIL:
                return (
                    _HIGH_CHANGE_PCT,
                    "high",
                    "High demand with critically low inventory. "
                    "Recommend price increase of ~8%.",
                )
            if availability_pct is not None and availability_pct <= _HIGH_DEMAND_LOW_AVAIL:
                return (
                    _MED_HIGH_CHANGE_PCT,
                    "high",
                    "High demand with low inventory. "
                    "Recommend price increase of ~5%.",
                )
            return (
                _LOW_CHANGE_PCT,
                "medium",
                "High demand with moderate inventory. "
                "Recommend mild price increase of ~2%.",
            )

        if demand_status == "balanced":
            return (
                0.0,
                "high",
                "Demand is on plan. No price change recommended.",
            )

        # low_demand
        if availability_pct is not None and availability_pct >= _LOW_DEMAND_HIGH_AVAIL:
            return (
                _NEG_HIGH_CHANGE_PCT,
                "high",
                "Low demand with high inventory. "
                "Recommend price reduction of ~8% or incentive program.",
            )
        if availability_pct is not None and availability_pct >= _LOW_DEMAND_MED_AVAIL:
            return (
                _NEG_MED_CHANGE_PCT,
                "medium",
                "Low demand with elevated inventory. "
                "Recommend price reduction of ~5%.",
            )
        return (
            _NEG_LOW_CHANGE_PCT,
            "low",
            "Low demand. Consider a minor price reduction of ~3% or incentive.",
        )

    def _build_unit_type_recommendation(
        self,
        unit_type: str,
        status_counts: Dict[str, int],
        avg_price: Optional[float],
        absorption_vs_plan_pct: Optional[float],
        project_sell_through_pct: Optional[float],
    ) -> UnitTypePricingRecommendation:
        """Build a UnitTypePricingRecommendation from pre-fetched data."""
        total_units = sum(status_counts.values())
        available_units = status_counts.get("available", 0)
        sold_units = (
            status_counts.get("under_contract", 0) + status_counts.get("registered", 0)
        )

        availability_pct = _safe_pct(available_units, total_units)
        unit_type_sell_through_pct = _safe_pct(sold_units, total_units)

        demand_status = self._classify_demand(
            absorption_vs_plan_pct=absorption_vs_plan_pct,
            sell_through_pct=project_sell_through_pct,
            unit_type_sell_through_pct=unit_type_sell_through_pct,
            unit_type_sold_units=sold_units,
        )

        change_pct, confidence, reason = self._recommend(demand_status, availability_pct)

        recommended_price: Optional[float] = None
        if avg_price is not None and change_pct is not None:
            recommended_price = round(avg_price * (1 + change_pct / 100), 2)

        return UnitTypePricingRecommendation(
            unit_type=unit_type,
            current_avg_price=round(avg_price, 2) if avg_price is not None else None,
            recommended_price=recommended_price,
            change_pct=change_pct,
            confidence=confidence,
            reason=reason,
            demand_status=demand_status,
            total_units=total_units,
            available_units=available_units,
            sold_units=sold_units,
            availability_pct=availability_pct,
        )

    # ------------------------------------------------------------------
    # Portfolio project card builder
    # ------------------------------------------------------------------

    def _build_portfolio_project_card(
        self,
        project,
        unit_type_status_counts: Dict[str, Dict[str, int]],
        avg_prices: Dict[str, float],
        contract_bounds: Optional[Tuple],
        feasibility_inputs: Optional[Tuple],
    ) -> PortfolioPricingProjectCard:
        """Build a PortfolioPricingProjectCard from pre-fetched data."""
        absorption_vs_plan_pct, sell_through_pct, _demand_context = (
            self._derive_project_demand_context(
                unit_type_status_counts=unit_type_status_counts,
                contract_bounds=contract_bounds,
                feasibility_inputs=feasibility_inputs,
            )
        )

        recommendations = []
        for unit_type, status_counts in unit_type_status_counts.items():
            rec = self._build_unit_type_recommendation(
                unit_type=unit_type,
                status_counts=status_counts,
                avg_price=avg_prices.get(unit_type),
                absorption_vs_plan_pct=absorption_vs_plan_pct,
                project_sell_through_pct=sell_through_pct,
            )
            recommendations.append(rec)

        if not recommendations:
            return PortfolioPricingProjectCard(
                project_id=project.id,
                project_name=project.name,
                pricing_status="no_data",
                avg_recommended_adjustment_pct=None,
                recommendation_count=0,
                high_demand_unit_types=[],
                low_demand_unit_types=[],
            )

        # Derive project pricing status from recommendations
        change_pcts = [r.change_pct for r in recommendations if r.change_pct is not None]
        avg_change_pct: Optional[float] = None
        if change_pcts:
            avg_change_pct = round(sum(change_pcts) / len(change_pcts), 2)

        if not avg_prices:
            pricing_status = "no_data"
        elif avg_change_pct is None:
            pricing_status = "no_data"
        elif avg_change_pct > 0:
            pricing_status = "underpriced"
        elif avg_change_pct < 0:
            pricing_status = "overpriced"
        else:
            pricing_status = "balanced"

        actionable_count = sum(
            1 for r in recommendations if r.change_pct is not None and r.change_pct != 0
        )

        high_demand_types = sorted(
            r.unit_type for r in recommendations if r.demand_status == "high_demand"
        )
        low_demand_types = sorted(
            r.unit_type for r in recommendations if r.demand_status == "low_demand"
        )

        return PortfolioPricingProjectCard(
            project_id=project.id,
            project_name=project.name,
            pricing_status=pricing_status,
            avg_recommended_adjustment_pct=avg_change_pct,
            recommendation_count=actionable_count,
            high_demand_unit_types=high_demand_types,
            low_demand_unit_types=low_demand_types,
        )
