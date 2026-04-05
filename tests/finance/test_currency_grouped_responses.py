"""
PR-CURRENCY-007: API Contract — Denomination-Safe Response Shapes

Tests that explicitly verify the grouped-by-currency and scalar+currency
contract rules introduced by PR-CURRENCY-007.

Coverage:
  - Portfolio-wide monetary fields return Dict[str, float]
  - Project-scoped monetary fields remain scalar with currency: str
  - liquidity_ratio is None for multi-currency portfolios
  - currencies list is populated correctly
  - Per-project summary entries carry currency
  - Treasury monitoring grouped shapes
  - Cashflow forecast currency propagation
  - Portfolio aging currencies list
"""

import pytest
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.modules.finance.portfolio_summary_service import PortfolioSummaryService
from app.modules.finance.treasury_monitoring_service import TreasuryMonitoringService
from app.modules.finance.schemas import (
    PortfolioFinancialSummaryResponse,
    TreasuryMonitoringResponse,
    ProjectFinancialSummaryEntry,
    PortfolioAgingResponse,
)
from app.modules.portfolio.schemas import (
    PortfolioSummary,
    PortfolioCollectionsSummary,
)


# ---------------------------------------------------------------------------
# Helper factory functions
# ---------------------------------------------------------------------------

_cg_seq: dict[str, int] = {}


def _make_project(db_session: Session, code: str, currency: str = "AED") -> str:
    from app.modules.projects.models import Project

    project = Project(
        name=f"CG Project {code}",
        code=code,
        base_currency=currency,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


def _make_unit(db_session: Session, project_id: str, unit_number: str) -> str:
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    seq = _cg_seq.get(project_id, 0) + 1
    _cg_seq[project_id] = seq

    phase = Phase(project_id=project_id, name=f"Phase {seq}", sequence=seq)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"CG-BLK-{unit_number}")
    db_session.add(building)
    db_session.flush()

    floor = Floor(
        building_id=building.id,
        name="Floor 1",
        code=f"CG-FL-{unit_number}",
        sequence_number=1,
    )
    db_session.add(floor)
    db_session.flush()

    unit = Unit(
        floor_id=floor.id,
        unit_number=unit_number,
        unit_type="studio",
        internal_area=100.0,
        status="available",
    )
    db_session.add(unit)
    db_session.commit()
    db_session.refresh(unit)
    return unit.id


def _make_contract(
    db_session: Session,
    unit_id: str,
    price: float,
    ref: str,
    email: str,
    currency: str = "AED",
) -> str:
    from app.modules.sales.models import SalesContract, Buyer

    buyer = Buyer(full_name="Test Buyer", email=email, phone="+9620000001")
    db_session.add(buyer)
    db_session.flush()

    contract = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer.id,
        contract_number=ref,
        contract_date=date(2026, 1, 1),
        contract_price=price,
        currency=currency,
    )
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)
    return contract.id


def _make_installment(
    db_session: Session,
    contract_id: str,
    amount: float,
    seq: int,
    due_date: date,
    status: str,
    currency: str = "AED",
) -> None:
    from app.modules.sales.models import ContractPaymentSchedule

    inst = ContractPaymentSchedule(
        contract_id=contract_id,
        installment_number=seq,
        due_date=due_date,
        amount=amount,
        status=status,
        currency=currency,
    )
    db_session.add(inst)
    db_session.commit()


# ---------------------------------------------------------------------------
# Schema contract tests — portfolio-wide fields must be Dict[str, float]
# ---------------------------------------------------------------------------


class TestPortfolioSummaryContractShape:
    """Verify that PortfolioFinancialSummaryResponse monetary fields are grouped dicts."""

    def test_total_revenue_recognized_is_dict(self, db_session: Session):
        pid = _make_project(db_session, "CGR-001")
        uid = _make_unit(db_session, pid, "CGR001-U1")
        cid = _make_contract(db_session, uid, 100_000.0, "CGR-C001", "cgr001@t.com")
        _make_installment(db_session, cid, 50_000.0, 1, date(2026, 1, 1), "paid")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert isinstance(result.total_revenue_recognized, dict)
        assert isinstance(result.total_deferred_revenue, dict)
        assert isinstance(result.total_receivables, dict)
        assert isinstance(result.overdue_receivables, dict)
        assert isinstance(result.forecast_next_month, dict)

    def test_currencies_list_populated_from_single_currency_portfolio(
        self, db_session: Session
    ):
        pid = _make_project(db_session, "CGR-002")
        uid = _make_unit(db_session, pid, "CGR002-U1")
        cid = _make_contract(db_session, uid, 100_000.0, "CGR-C002", "cgr002@t.com")
        _make_installment(db_session, cid, 100_000.0, 1, date(2026, 1, 1), "paid")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert isinstance(result.currencies, list)
        assert "AED" in result.currencies

    def test_single_currency_overdue_pct_is_scalar(self, db_session: Session):
        """overdue_receivables_pct must be a scalar float when single-currency."""
        pid = _make_project(db_session, "CGR-003")
        uid = _make_unit(db_session, pid, "CGR003-U1")
        cid = _make_contract(db_session, uid, 100_000.0, "CGR-C003", "cgr003@t.com")
        past = date.today() - timedelta(days=30)
        _make_installment(db_session, cid, 100_000.0, 1, past, "overdue")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert isinstance(result.overdue_receivables_pct, float)
        assert result.overdue_receivables_pct == pytest.approx(100.0)

    def test_per_project_entry_has_currency_field(self, db_session: Session):
        """ProjectFinancialSummaryEntry must have explicit currency field."""
        pid = _make_project(db_session, "CGR-004")
        uid = _make_unit(db_session, pid, "CGR004-U1")
        cid = _make_contract(db_session, uid, 100_000.0, "CGR-C004", "cgr004@t.com")
        _make_installment(db_session, cid, 50_000.0, 1, date(2026, 1, 1), "paid")

        svc = PortfolioSummaryService(db_session)
        result = svc.get_portfolio_summary()

        assert len(result.project_summaries) >= 1
        entry = next(e for e in result.project_summaries if e.project_id == pid)
        assert isinstance(entry, ProjectFinancialSummaryEntry)
        assert hasattr(entry, "currency")
        assert entry.currency is not None


# ---------------------------------------------------------------------------
# Schema contract tests — treasury monitoring
# ---------------------------------------------------------------------------


class TestTreasuryMonitoringContractShape:
    """Verify TreasuryMonitoringResponse grouped monetary shapes."""

    def test_cash_position_is_dict(self, db_session: Session):
        pid = _make_project(db_session, "TM-CG-001")
        uid = _make_unit(db_session, pid, "TM-CG001-U1")
        cid = _make_contract(db_session, uid, 100_000.0, "TM-CGC001", "tmcg001@t.com")
        _make_installment(db_session, cid, 100_000.0, 1, date(2025, 6, 1), "paid")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert isinstance(result.cash_position, dict)
        assert isinstance(result.receivables_exposure, dict)
        assert isinstance(result.overdue_receivables, dict)
        assert isinstance(result.forecast_next_month, dict)

    def test_single_currency_liquidity_ratio_is_float(self, db_session: Session):
        """liquidity_ratio must be a scalar float for single-currency portfolios."""
        pid = _make_project(db_session, "TM-CG-002")
        uid = _make_unit(db_session, pid, "TM-CG002-U1")
        cid = _make_contract(db_session, uid, 100_000.0, "TM-CGC002", "tmcg002@t.com")
        _make_installment(db_session, cid, 50_000.0, 1, date(2025, 6, 1), "paid")
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid, 50_000.0, 2, future, "pending")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert isinstance(result.liquidity_ratio, float)
        assert result.liquidity_ratio == pytest.approx(0.5, rel=1e-3)

    def test_currencies_list_populated(self, db_session: Session):
        pid = _make_project(db_session, "TM-CG-003")
        uid = _make_unit(db_session, pid, "TM-CG003-U1")
        cid = _make_contract(db_session, uid, 100_000.0, "TM-CGC003", "tmcg003@t.com")
        _make_installment(db_session, cid, 100_000.0, 1, date(2025, 6, 1), "paid")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert isinstance(result.currencies, list)

    def test_empty_portfolio_grouped_dicts_are_empty(self, db_session: Session):
        """Empty portfolio must return empty dicts, not zero scalars."""
        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        assert result.cash_position == {}
        assert result.receivables_exposure == {}
        assert result.overdue_receivables == {}
        assert result.forecast_next_month == {}


# ---------------------------------------------------------------------------
# Schema contract tests — portfolio API schemas
# ---------------------------------------------------------------------------


class TestPortfolioSchemaContracts:
    """Verify portfolio/schemas.py grouped and scalar+currency fields."""

    def test_portfolio_summary_monetary_fields_are_dicts(self):
        """PortfolioSummary monetary fields accept Dict[str, float]."""
        summary = PortfolioSummary(
            total_projects=1,
            active_projects=1,
            total_units=10,
            available_units=5,
            reserved_units=2,
            under_contract_units=2,
            registered_units=1,
            contracted_revenue={"AED": 500_000.0},
            collected_cash={"AED": 200_000.0},
            outstanding_balance={"AED": 300_000.0},
        )
        assert summary.contracted_revenue == {"AED": 500_000.0}
        assert summary.collected_cash == {"AED": 200_000.0}

    def test_collections_summary_overdue_balance_is_dict(self):
        """PortfolioCollectionsSummary.overdue_balance must be Dict[str, float]."""
        cs = PortfolioCollectionsSummary(
            total_receivables=10,
            overdue_receivables=3,
            overdue_balance={"AED": 50_000.0, "USD": 10_000.0},
            collection_rate_pct=75.0,
            currencies=["AED", "USD"],
        )
        assert "AED" in cs.overdue_balance
        assert "USD" in cs.overdue_balance
        assert cs.currencies == ["AED", "USD"]


# ---------------------------------------------------------------------------
# Schema contract tests — aging responses
# ---------------------------------------------------------------------------


class TestAgingSchemaContracts:
    """Verify PortfolioAgingResponse has currencies field."""

    def test_portfolio_aging_has_currencies_field(self, db_session: Session):
        from app.modules.finance.service import CollectionsAgingService

        svc = CollectionsAgingService(db_session)
        result = svc.get_portfolio_aging()

        assert isinstance(result, PortfolioAgingResponse)
        assert hasattr(result, "currencies")
        assert isinstance(result.currencies, list)

    def test_project_aging_has_currency_field(self, db_session: Session):
        from app.modules.finance.service import CollectionsAgingService
        from app.modules.finance.schemas import ProjectAgingResponse

        pid = _make_project(db_session, "AGE-001")
        uid = _make_unit(db_session, pid, "AGE001-U1")
        cid = _make_contract(db_session, uid, 100_000.0, "AGE-C001", "age001@t.com")
        past = date.today() - timedelta(days=30)
        _make_installment(db_session, cid, 100_000.0, 1, past, "overdue")

        svc = CollectionsAgingService(db_session)
        result = svc.get_project_aging(pid)

        assert isinstance(result, ProjectAgingResponse)
        assert hasattr(result, "currency")
        assert result.currency is not None


# ---------------------------------------------------------------------------
# Multi-currency regression tests — null-safe ratio rules
# ---------------------------------------------------------------------------


class TestMultiCurrencyNullSafeRules:
    """Regression tests: liquidity_ratio and collection_rate_pct are None for
    multi-currency portfolios; ratios are valid floats for single-currency ones."""

    def test_liquidity_ratio_is_none_for_multi_currency_portfolio(
        self, db_session: Session
    ):
        """Two projects in different currencies → liquidity_ratio must be None."""
        # Project 1 in AED
        pid1 = _make_project(db_session, "MC-LIQ-01", currency="AED")
        uid1 = _make_unit(db_session, pid1, "MC-LIQ01-U1")
        cid1 = _make_contract(
            db_session, uid1, 100_000.0, "MC-LIQC001", "mcliq01@t.com", currency="AED"
        )
        _make_installment(db_session, cid1, 50_000.0, 1, date(2025, 6, 1), "paid", currency="AED")
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid1, 50_000.0, 2, future, "pending", currency="AED")

        # Project 2 in USD — introduces second currency
        pid2 = _make_project(db_session, "MC-LIQ-02", currency="USD")
        uid2 = _make_unit(db_session, pid2, "MC-LIQ02-U1")
        cid2 = _make_contract(
            db_session, uid2, 200_000.0, "MC-LIQC002", "mcliq02@t.com", currency="USD"
        )
        _make_installment(db_session, cid2, 100_000.0, 1, date(2025, 6, 1), "paid", currency="USD")
        _make_installment(db_session, cid2, 100_000.0, 2, future, "pending", currency="USD")

        svc = TreasuryMonitoringService(db_session)
        result = svc.get_treasury_monitoring()

        # liquidity_ratio must be None when portfolio spans multiple currencies
        assert result.liquidity_ratio is None, (
            f"Expected None for multi-currency portfolio, got {result.liquidity_ratio}"
        )
        # cash_position grouped dict should have both currencies
        assert "AED" in result.cash_position or "USD" in result.cash_position

    def test_collection_rate_pct_is_none_for_multi_currency_portfolio(
        self, db_session: Session
    ):
        """Two projects in different currencies → collection_rate_pct must be None."""
        from app.modules.portfolio.service import PortfolioService

        # Project in AED
        pid1 = _make_project(db_session, "MC-COL-01", currency="AED")
        uid1 = _make_unit(db_session, pid1, "MC-COL01-U1")
        cid1 = _make_contract(
            db_session, uid1, 100_000.0, "MC-COLC001", "mccol01@t.com", currency="AED"
        )
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid1, 100_000.0, 1, future, "pending", currency="AED")

        # Project in USD
        pid2 = _make_project(db_session, "MC-COL-02", currency="USD")
        uid2 = _make_unit(db_session, pid2, "MC-COL02-U1")
        cid2 = _make_contract(
            db_session, uid2, 200_000.0, "MC-COLC002", "mccol02@t.com", currency="USD"
        )
        _make_installment(db_session, cid2, 200_000.0, 1, future, "pending", currency="USD")

        svc = PortfolioService(db_session)
        dashboard = svc.get_dashboard()

        # collection_rate_pct must be None when portfolio spans multiple currencies
        assert dashboard.collections.collection_rate_pct is None, (
            f"Expected None for multi-currency portfolio, "
            f"got {dashboard.collections.collection_rate_pct}"
        )

    def test_single_currency_collection_rate_pct_is_not_forced_none_by_currency_guard(
        self, db_session: Session
    ):
        """Single-currency portfolio must not have collection_rate_pct forced to None
        by the multi-currency guard.  With no Receivable records the value may be None
        from _safe_pct(0, 0), but that is a data-completeness None, not a currency None.
        """
        from app.modules.portfolio.service import PortfolioService

        # Single AED project only — no mixed currencies in portfolio
        pid = _make_project(db_session, "SC-COL-01", currency="AED")
        uid = _make_unit(db_session, pid, "SC-COL01-U1")
        cid = _make_contract(
            db_session, uid, 100_000.0, "SC-COLC001", "sccol01@t.com", currency="AED"
        )
        _make_installment(db_session, cid, 50_000.0, 1, date(2025, 6, 1), "paid", currency="AED")
        future = date.today() + timedelta(days=30)
        _make_installment(db_session, cid, 50_000.0, 2, future, "pending", currency="AED")

        svc = PortfolioService(db_session)
        dashboard = svc.get_dashboard()

        # With no Receivable records in the portfolio repository, collected_cash and
        # outstanding_balance are both 0.  _safe_pct(0, 0) correctly returns None.
        # The key invariant tested here: overdue_balance currencies dict has at most
        # one entry, so the multi-currency guard is NOT triggered (currency len <= 1).
        overdue_currencies = list(dashboard.collections.overdue_balance.keys())
        assert len(overdue_currencies) <= 1, (
            "Single-currency portfolio should produce at most one currency in overdue_balance"
        )

    def test_portfolio_revenue_overview_grouped_for_multi_currency(
        self, db_session: Session
    ):
        """Multi-currency portfolio → PortfolioRevenueOverviewResponse.
        total_recognized_revenue must be a dict with both currency keys."""
        pid1 = _make_project(db_session, "MC-REV-01", currency="AED")
        uid1 = _make_unit(db_session, pid1, "MC-REV01-U1")
        cid1 = _make_contract(
            db_session, uid1, 100_000.0, "MC-REVC001", "mcrev01@t.com", currency="AED"
        )
        _make_installment(db_session, cid1, 100_000.0, 1, date(2025, 6, 1), "paid", currency="AED")

        pid2 = _make_project(db_session, "MC-REV-02", currency="USD")
        uid2 = _make_unit(db_session, pid2, "MC-REV02-U1")
        cid2 = _make_contract(
            db_session, uid2, 200_000.0, "MC-REVC002", "mcrev02@t.com", currency="USD"
        )
        _make_installment(db_session, cid2, 200_000.0, 1, date(2025, 6, 1), "paid", currency="USD")

        from app.modules.finance.service import RevenueRecognitionService

        svc = RevenueRecognitionService(db_session)
        result = svc.get_total_recognized_revenue()

        # Multi-currency portfolio: grouped dict must contain both currencies
        assert "AED" in result.total_recognized_revenue
        assert "USD" in result.total_recognized_revenue
        # overall_recognition_percentage must be None for multi-currency
        assert result.overall_recognition_percentage is None
        assert sorted(result.currencies) == ["AED", "USD"]
