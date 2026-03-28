"""
portfolio.service

Portfolio Intelligence aggregation service.

Composes repository query results into dashboard-ready response structures.
All methods are read-only — no source records are mutated.

Health badge rules are intentionally simple and transparent:
  - 'at_risk'         : sell-through < 20 % OR overdue receivables > 0
  - 'needs_attention' : sell-through < 50 %
  - 'on_track'        : sell-through >= 50 % and no overdue receivables

Risk flag thresholds are documented inline.

Cost variance status rules (PR-V6-12):
  - 'overrun'  : variance_amount > 0
  - 'saving'   : variance_amount < 0
  - 'neutral'  : variance_amount == 0
"""

from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.portfolio.repository import PortfolioRepository
from app.modules.portfolio.schemas import (
    PortfolioCollectionsSummary,
    PortfolioCostVarianceFlag,
    PortfolioCostVarianceProjectCard,
    PortfolioCostVarianceResponse,
    PortfolioCostVarianceSummary,
    PortfolioDashboardResponse,
    PortfolioPipelineSummary,
    PortfolioProjectCard,
    PortfolioRiskFlag,
    PortfolioSummary,
)

_logger = get_logger("reach_developments.portfolio")


# ---------------------------------------------------------------------------
# Health badge thresholds (transparent, documented)
# ---------------------------------------------------------------------------
_AT_RISK_SELL_THROUGH_THRESHOLD = 0.20   # below 20 % → at_risk
_NEEDS_ATTENTION_SELL_THROUGH_THRESHOLD = 0.50  # below 50 % → needs_attention

# Risk flag thresholds
_LOW_SELL_THROUGH_FLAG_THRESHOLD = 0.30   # portfolio-project sell-through below 30 %
_LOW_COLLECTIONS_RATE_THRESHOLD = 0.30    # collection rate below 30 %

# Cost variance flag thresholds (PR-V6-12)
# major overrun: variance_pct > 10 % of baseline
_MAJOR_OVERRUN_PCT_THRESHOLD = Decimal("10.00")
# major saving: variance_pct < -10 % of baseline
_MAJOR_SAVING_PCT_THRESHOLD = Decimal("-10.00")
# Top-N list size for overruns/savings
_TOP_N_VARIANCE = 5
# Decimal places for variance percentage rounding
_VARIANCE_PCT_PRECISION = 4


def _safe_pct(numerator: float, denominator: float) -> Optional[float]:
    """Return numerator / denominator * 100, or None when denominator is zero."""
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 2)


class PortfolioService:
    """Service that assembles portfolio dashboard data from source domain records."""

    def __init__(self, db: Session) -> None:
        self.repo = PortfolioRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_dashboard(self) -> PortfolioDashboardResponse:
        """Assemble and return the full portfolio dashboard response.

        Portfolio-wide aggregates that feed multiple sections are computed once
        and passed into the section builders to avoid redundant DB round-trips.
        """
        # Pre-compute shared portfolio-wide aggregates used by multiple sections
        total_projects = self.repo.count_projects()
        collected_cash = self.repo.sum_collected_cash()
        outstanding_balance = self.repo.sum_outstanding_balance()

        summary = self._build_summary(total_projects, collected_cash, outstanding_balance)
        projects = self._build_project_cards()
        pipeline = self._build_pipeline_summary(total_projects)
        collections = self._build_collections_summary(collected_cash, outstanding_balance)
        risk_flags = self._derive_risk_flags(projects, collections)

        return PortfolioDashboardResponse(
            summary=summary,
            projects=projects,
            pipeline=pipeline,
            collections=collections,
            risk_flags=risk_flags,
        )

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        total_projects: int,
        collected_cash: float,
        outstanding_balance: float,
    ) -> PortfolioSummary:
        unit_counts = self.repo.count_units_by_status()
        return PortfolioSummary(
            total_projects=total_projects,
            active_projects=self.repo.count_active_projects(),
            total_units=sum(unit_counts.values()),
            available_units=unit_counts.get("available", 0),
            reserved_units=unit_counts.get("reserved", 0),
            under_contract_units=unit_counts.get("under_contract", 0),
            registered_units=unit_counts.get("registered", 0),
            contracted_revenue=self.repo.sum_contracted_revenue(),
            collected_cash=collected_cash,
            outstanding_balance=outstanding_balance,
        )

    def _build_project_cards(self) -> List[PortfolioProjectCard]:
        """Build per-project cards using bulk grouped queries to avoid N+1 queries."""
        projects = self.repo.list_projects()
        if not projects:
            return []

        # Fetch all per-project aggregates in bulk (one query each, grouped by project)
        unit_counts_map = self.repo.get_unit_status_counts_by_project()
        revenue_map = self.repo.get_contracted_revenue_by_project()
        collected_map = self.repo.get_collected_cash_by_project()
        balance_map = self.repo.get_outstanding_balance_by_project()
        overdue_map = self.repo.get_overdue_receivable_counts_by_project()

        cards: List[PortfolioProjectCard] = []
        for project in projects:
            unit_counts = unit_counts_map.get(project.id, {})
            total_units = sum(unit_counts.values())
            available = unit_counts.get("available", 0)
            reserved = unit_counts.get("reserved", 0)
            under_contract = unit_counts.get("under_contract", 0)
            registered = unit_counts.get("registered", 0)
            contracted_revenue = revenue_map.get(project.id, 0.0)
            collected_cash = collected_map.get(project.id, 0.0)
            outstanding_balance = balance_map.get(project.id, 0.0)

            sold_units = under_contract + registered
            sell_through_pct = _safe_pct(sold_units, total_units)
            sell_through_ratio = sold_units / total_units if total_units > 0 else None

            overdue_count = overdue_map.get(project.id, 0)
            health_badge = self._derive_health_badge(sell_through_ratio, overdue_count)

            cards.append(
                PortfolioProjectCard(
                    project_id=project.id,
                    project_name=project.name,
                    project_code=project.code,
                    status=project.status,
                    total_units=total_units,
                    available_units=available,
                    reserved_units=reserved,
                    under_contract_units=under_contract,
                    registered_units=registered,
                    contracted_revenue=contracted_revenue,
                    collected_cash=collected_cash,
                    outstanding_balance=outstanding_balance,
                    sell_through_pct=sell_through_pct,
                    health_badge=health_badge,
                )
            )

        return cards

    def _build_pipeline_summary(self, total_projects: int) -> PortfolioPipelineSummary:
        run_counts_by_project = self.repo.get_all_project_feasibility_run_counts()
        # Count projects that have zero feasibility runs
        projects_with_runs = len(run_counts_by_project)
        projects_with_no_feasibility = max(0, total_projects - projects_with_runs)

        return PortfolioPipelineSummary(
            total_scenarios=self.repo.count_scenarios(),
            approved_scenarios=self.repo.count_active_scenarios(),
            total_feasibility_runs=self.repo.count_feasibility_runs(),
            calculated_feasibility_runs=self.repo.count_calculated_feasibility_runs(),
            projects_with_no_feasibility=projects_with_no_feasibility,
        )

    def _build_collections_summary(
        self,
        collected_cash: float,
        outstanding_balance: float,
    ) -> PortfolioCollectionsSummary:
        total_receivables = self.repo.count_receivables()
        overdue_receivables = self.repo.count_overdue_receivables()
        overdue_balance = self.repo.sum_overdue_balance()
        collection_rate_pct = _safe_pct(collected_cash, collected_cash + outstanding_balance)

        return PortfolioCollectionsSummary(
            total_receivables=total_receivables,
            overdue_receivables=overdue_receivables,
            overdue_balance=overdue_balance,
            collection_rate_pct=collection_rate_pct,
        )

    # ------------------------------------------------------------------
    # Health badge derivation
    # ------------------------------------------------------------------

    def _derive_health_badge(
        self,
        sell_through_ratio: Optional[float],
        overdue_count: int,
    ) -> Optional[str]:
        """Return a health badge string or None when no units exist."""
        if sell_through_ratio is None:
            return None
        if sell_through_ratio < _AT_RISK_SELL_THROUGH_THRESHOLD or overdue_count > 0:
            return "at_risk"
        if sell_through_ratio < _NEEDS_ATTENTION_SELL_THROUGH_THRESHOLD:
            return "needs_attention"
        return "on_track"

    # ------------------------------------------------------------------
    # Risk flag derivation
    # ------------------------------------------------------------------

    def _derive_risk_flags(
        self,
        project_cards: List[PortfolioProjectCard],
        collections: PortfolioCollectionsSummary,
    ) -> List[PortfolioRiskFlag]:
        """Derive portfolio-level risk flags from assembled data.

        Rules are intentionally simple and transparent for this first slice:
          1. Portfolio has overdue receivables → 'overdue_receivables' warning/critical
          2. Project sell-through < 30 % → 'low_sell_through' warning per project
          3. Portfolio collection rate < 30 % → 'low_collections' warning
        """
        flags: List[PortfolioRiskFlag] = []

        # Rule 1 — portfolio-wide overdue receivables
        if collections.overdue_receivables > 0:
            severity = (
                "critical" if collections.overdue_receivables >= 10 else "warning"
            )
            flags.append(
                PortfolioRiskFlag(
                    flag_type="overdue_receivables",
                    severity=severity,
                    description=(
                        f"{collections.overdue_receivables} overdue receivable(s) with "
                        f"total outstanding balance of AED {collections.overdue_balance:,.2f}."
                    ),
                    affected_project_id=None,
                    affected_project_name=None,
                )
            )

        # Rule 2 — low sell-through per project
        for card in project_cards:
            if card.sell_through_pct is not None:
                sell_through_ratio = card.sell_through_pct / 100.0
                if sell_through_ratio < _LOW_SELL_THROUGH_FLAG_THRESHOLD:
                    flags.append(
                        PortfolioRiskFlag(
                            flag_type="low_sell_through",
                            severity="warning",
                            description=(
                                f"Project '{card.project_name}' has a sell-through rate of "
                                f"{card.sell_through_pct:.1f}% (below {_LOW_SELL_THROUGH_FLAG_THRESHOLD * 100:.0f}% threshold)."
                            ),
                            affected_project_id=card.project_id,
                            affected_project_name=card.project_name,
                        )
                    )

        # Rule 3 — low collection rate at portfolio level
        if (
            collections.collection_rate_pct is not None
            and collections.collection_rate_pct / 100.0 < _LOW_COLLECTIONS_RATE_THRESHOLD
        ):
            flags.append(
                PortfolioRiskFlag(
                    flag_type="low_collections",
                    severity="warning",
                    description=(
                        f"Portfolio collection rate is {collections.collection_rate_pct:.1f}% "
                        f"(below {_LOW_COLLECTIONS_RATE_THRESHOLD * 100:.0f}% threshold)."
                    ),
                    affected_project_id=None,
                    affected_project_name=None,
                )
            )

        return flags

    # ------------------------------------------------------------------
    # Portfolio cost variance roll-up (PR-V6-12)
    # ------------------------------------------------------------------

    def get_cost_variance(self) -> PortfolioCostVarianceResponse:
        """Assemble and return the portfolio cost variance roll-up response.

        Aggregates tender comparison data from all active comparison sets
        across projects.  All values are live-read — no source records are
        mutated.
        """
        # Bulk-load per-project aggregates in as few queries as possible
        all_projects = self.repo.list_projects()
        projects_with_sets = self.repo.list_projects_with_active_comparison_sets()
        variance_by_project = self.repo.get_variance_totals_by_project()
        set_count_by_project = self.repo.get_active_set_count_by_project()
        stage_by_project = self.repo.get_latest_comparison_stage_by_project()

        # Build per-project variance cards — keep variance_pct as Decimal for
        # threshold comparisons; convert to float only at response boundary.
        project_cards: List[PortfolioCostVarianceProjectCard] = []
        project_variance_pcts: Dict[str, Optional[Decimal]] = {}
        for project in projects_with_sets:
            pid = project.id
            baseline, comparison, variance = variance_by_project.get(
                pid, (Decimal("0"), Decimal("0"), Decimal("0"))
            )
            variance_pct_decimal: Optional[Decimal] = None
            if baseline != Decimal("0"):
                variance_pct_decimal = round(
                    (variance / baseline) * Decimal("100"), _VARIANCE_PCT_PRECISION
                )
            project_variance_pcts[pid] = variance_pct_decimal

            variance_status = self._derive_variance_status(variance)

            project_cards.append(
                PortfolioCostVarianceProjectCard(
                    project_id=pid,
                    project_name=project.name,
                    comparison_set_count=set_count_by_project.get(pid, 0),
                    latest_comparison_stage=stage_by_project.get(pid),
                    baseline_total=float(baseline),
                    comparison_total=float(comparison),
                    variance_amount=float(variance),
                    # float conversion only at response boundary
                    variance_pct=(
                        float(variance_pct_decimal)
                        if variance_pct_decimal is not None
                        else None
                    ),
                    variance_status=variance_status,
                )
            )

        # Sort all cards by variance_amount descending (largest overrun first)
        project_cards.sort(key=lambda c: c.variance_amount, reverse=True)

        # Build portfolio-wide summary
        total_baseline, total_comparison, total_variance = (
            self.repo.get_portfolio_variance_totals()
        )
        total_variance_pct: Optional[float] = None
        if total_baseline != Decimal("0"):
            total_variance_pct = float(
                round(
                    (total_variance / total_baseline) * Decimal("100"),
                    _VARIANCE_PCT_PRECISION,
                )
            )

        summary = PortfolioCostVarianceSummary(
            projects_with_comparison_sets=len(projects_with_sets),
            total_baseline_amount=float(total_baseline),
            total_comparison_amount=float(total_comparison),
            total_variance_amount=float(total_variance),
            total_variance_pct=total_variance_pct,
        )

        # Top-N overruns: positive variance, largest first (already sorted desc)
        top_overruns = [c for c in project_cards if c.variance_amount > 0][
            :_TOP_N_VARIANCE
        ]
        # Top-N savings: negative variance, largest saving first (most negative)
        top_savings = sorted(
            [c for c in project_cards if c.variance_amount < 0],
            key=lambda c: c.variance_amount,
        )[:_TOP_N_VARIANCE]

        # Derive portfolio-level cost variance flags — pass pre-fetched project
        # list and Decimal pcts to avoid extra DB round-trip and float round-trip.
        flags = self._derive_cost_variance_flags(
            project_cards, all_projects, project_variance_pcts
        )

        return PortfolioCostVarianceResponse(
            summary=summary,
            projects=project_cards,
            top_overruns=top_overruns,
            top_savings=top_savings,
            flags=flags,
        )

    @staticmethod
    def _derive_variance_status(variance_amount: Decimal) -> str:
        """Return transparent status label based on variance sign.

        Rules:
          positive → 'overrun'
          negative → 'saving'
          zero     → 'neutral'
        """
        if variance_amount > Decimal("0"):
            return "overrun"
        if variance_amount < Decimal("0"):
            return "saving"
        return "neutral"

    def _derive_cost_variance_flags(
        self,
        project_cards: List[PortfolioCostVarianceProjectCard],
        all_projects: list,
        project_variance_pcts: "Dict[str, Optional[Decimal]]",
    ) -> List[PortfolioCostVarianceFlag]:
        """Derive cost variance flags for the portfolio.

        Rules:
          1. Projects with no active comparison sets → 'missing_comparison_data'
          2. Per-project variance_pct (Decimal) > threshold → 'major_overrun'
          3. Per-project variance_pct (Decimal) < negative threshold → 'major_saving'

        Threshold comparisons use Decimal arithmetic throughout; the
        float-formatted description uses the card's pre-rounded float value
        (already at the response boundary).
        """
        flags: List[PortfolioCostVarianceFlag] = []

        # Rule 1 — missing comparison data (projects with no active sets)
        projects_with_data_ids = {c.project_id for c in project_cards}
        for project in all_projects:
            if project.id not in projects_with_data_ids:
                flags.append(
                    PortfolioCostVarianceFlag(
                        flag_type="missing_comparison_data",
                        description=(
                            f"Project '{project.name}' has no active tender comparison sets."
                        ),
                        affected_project_id=project.id,
                        affected_project_name=project.name,
                    )
                )

        # Rule 2 & 3 — major overrun / major saving per project
        for card in project_cards:
            variance_pct_decimal = project_variance_pcts.get(card.project_id)
            if variance_pct_decimal is None:
                continue
            if variance_pct_decimal > _MAJOR_OVERRUN_PCT_THRESHOLD:
                flags.append(
                    PortfolioCostVarianceFlag(
                        flag_type="major_overrun",
                        description=(
                            f"Project '{card.project_name}' has a cost overrun of "
                            f"{card.variance_pct:.2f}% above baseline "
                            f"(threshold: {_MAJOR_OVERRUN_PCT_THRESHOLD}%)."
                        ),
                        affected_project_id=card.project_id,
                        affected_project_name=card.project_name,
                    )
                )
            elif variance_pct_decimal < _MAJOR_SAVING_PCT_THRESHOLD:
                flags.append(
                    PortfolioCostVarianceFlag(
                        flag_type="major_saving",
                        description=(
                            f"Project '{card.project_name}' has a cost saving of "
                            f"{abs(card.variance_pct):.2f}% below baseline "
                            f"(threshold: {abs(_MAJOR_SAVING_PCT_THRESHOLD)}%)."
                        ),
                        affected_project_id=card.project_id,
                        affected_project_name=card.project_name,
                    )
                )

        return flags

    # ------------------------------------------------------------------
    # Portfolio Absorption (PR-V7-01)
    # ------------------------------------------------------------------

    def get_portfolio_absorption(self) -> "PortfolioAbsorptionResponse":
        """Assemble and return the portfolio absorption aggregation.

        Uses batched repository queries (one query per data dimension) to avoid
        the N+1 pattern of calling get_absorption_metrics() per project.  Cards
        are built in memory from the batched results.

        Projects that are in the portfolio are always represented — if any
        unexpected data issue prevents card computation the project is logged
        and included as a ``no_data`` placeholder card.

        All values are read-only and non-destructive.
        """
        from app.modules.portfolio.schemas import (
            PortfolioAbsorptionProjectCard,
            PortfolioAbsorptionResponse,
            PortfolioAbsorptionSummary,
        )

        projects = self.repo.list_projects()

        # --- Batch all data dimensions in a fixed number of queries ---
        unit_counts_map = self.repo.get_unit_status_counts_by_project()
        revenue_map = self.repo.get_contracted_revenue_by_project()
        contract_counts_map = self.repo.get_contract_counts_by_project()
        date_bounds_map = self.repo.get_contract_date_bounds_by_project()
        feasibility_map = self.repo.get_latest_feasibility_inputs_by_project()

        cards: list[PortfolioAbsorptionProjectCard] = []
        for project in projects:
            try:
                card = self._build_absorption_card(
                    project=project,
                    unit_counts=unit_counts_map.get(project.id, {}),
                    contracted_revenue=revenue_map.get(project.id, 0.0),
                    contract_count=contract_counts_map.get(project.id, 0),
                    date_bounds=date_bounds_map.get(project.id),
                    feasibility_inputs=feasibility_map.get(project.id),
                )
            except Exception as exc:  # pragma: no cover — unexpected path
                _logger.warning(
                    "Absorption card computation failed for project %s (%s): %s",
                    project.id,
                    project.name,
                    exc,
                    exc_info=True,
                )
                card = PortfolioAbsorptionProjectCard(
                    project_id=project.id,
                    project_name=project.name,
                    project_code=project.code,
                    total_units=0,
                    sold_units=0,
                    sell_through_pct=None,
                    absorption_rate_per_month=None,
                    planned_absorption_rate_per_month=None,
                    absorption_vs_plan_pct=None,
                    contracted_revenue=0.0,
                    absorption_status="no_data",
                )
            cards.append(card)

        # Sort by sell-through descending (None last)
        cards.sort(
            key=lambda c: (c.sell_through_pct is None, -(c.sell_through_pct or 0.0))
        )

        # Build summary
        total_projects = len(cards)
        projects_with_data = sum(
            1 for c in cards if c.absorption_rate_per_month is not None
        )
        projects_with_units = [c for c in cards if c.total_units > 0]
        avg_sell_through = (
            round(
                sum(c.sell_through_pct for c in projects_with_units if c.sell_through_pct is not None)
                / max(len(projects_with_units), 1),
                2,
            )
            if projects_with_units
            else None
        )
        rate_cards = [c for c in cards if c.absorption_rate_per_month is not None]
        avg_absorption_rate = (
            round(
                sum(c.absorption_rate_per_month for c in rate_cards)  # type: ignore[arg-type]
                / len(rate_cards),
                4,
            )
            if rate_cards
            else None
        )
        ahead_count = sum(1 for c in cards if c.absorption_status == "ahead_of_plan")
        on_count = sum(1 for c in cards if c.absorption_status == "on_plan")
        behind_count = sum(1 for c in cards if c.absorption_status == "behind_plan")
        no_data_count = sum(
            1 for c in cards if c.absorption_status == "no_data" or c.absorption_status is None
        )

        summary = PortfolioAbsorptionSummary(
            total_projects=total_projects,
            projects_with_absorption_data=projects_with_data,
            portfolio_avg_sell_through_pct=avg_sell_through,
            portfolio_avg_absorption_rate=avg_absorption_rate,
            projects_ahead_of_plan=ahead_count,
            projects_on_plan=on_count,
            projects_behind_plan=behind_count,
            projects_no_absorption_data=no_data_count,
        )

        # Top/bottom 5 by absorption rate
        sorted_by_rate = sorted(
            [c for c in cards if c.absorption_rate_per_month is not None],
            key=lambda c: c.absorption_rate_per_month or 0.0,
            reverse=True,
        )
        fastest = sorted_by_rate[:5]
        if len(sorted_by_rate) > 5:
            slowest = sorted_by_rate[-5:][::-1]
        else:
            slowest = sorted_by_rate[::-1]

        below_plan = [c for c in cards if c.absorption_status == "behind_plan"]

        return PortfolioAbsorptionResponse(
            summary=summary,
            projects=cards,
            fastest_projects=fastest,
            slowest_projects=slowest,
            below_plan_projects=below_plan,
        )

    @staticmethod
    def _build_absorption_card(
        project: "Project",
        unit_counts: dict,
        contracted_revenue: float,
        contract_count: int,
        date_bounds: "Optional[tuple]",
        feasibility_inputs: "Optional[tuple]",
    ) -> "PortfolioAbsorptionProjectCard":
        """Assemble a single PortfolioAbsorptionProjectCard from pre-fetched data.

        All arguments are pre-fetched by bulk repository queries so this method
        performs no DB access.
        """
        from app.modules.portfolio.schemas import PortfolioAbsorptionProjectCard

        # Unit inventory
        total_units = sum(unit_counts.values())
        sold_units = unit_counts.get("under_contract", 0) + unit_counts.get("registered", 0)

        # Absorption velocity
        absorption_rate_per_month: Optional[float] = None
        if date_bounds is not None and contract_count >= 2:
            first_date, last_date = date_bounds
            days_elapsed = (last_date - first_date).days
            if days_elapsed > 0:
                months_elapsed = days_elapsed / 30.4375
                absorption_rate_per_month = round(contract_count / months_elapsed, 4)

        # Planned absorption from feasibility
        planned_absorption_rate_per_month: Optional[float] = None
        if feasibility_inputs is not None:
            feas_result, feas_assumptions = feasibility_inputs
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

        # Absorption status badge
        absorption_status: Optional[str]
        if total_units == 0:
            absorption_status = None
        elif absorption_vs_plan_pct is None:
            absorption_status = "no_data"
        elif absorption_vs_plan_pct >= 100.0:
            absorption_status = "ahead_of_plan"
        elif absorption_vs_plan_pct >= 80.0:
            absorption_status = "on_plan"
        else:
            absorption_status = "behind_plan"

        return PortfolioAbsorptionProjectCard(
            project_id=project.id,
            project_name=project.name,
            project_code=project.code,
            total_units=total_units,
            sold_units=sold_units,
            sell_through_pct=_safe_pct(sold_units, total_units),
            absorption_rate_per_month=absorption_rate_per_month,
            planned_absorption_rate_per_month=planned_absorption_rate_per_month,
            absorption_vs_plan_pct=absorption_vs_plan_pct,
            contracted_revenue=contracted_revenue,
            absorption_status=absorption_status,
        )
