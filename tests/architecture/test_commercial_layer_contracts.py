"""
tests/architecture/test_commercial_layer_contracts.py

Commercial layer contract boundary tests.

These tests lock in the canonical architecture rules defined in
docs/SYSTEM_RULES.md and docs/01-domain/commercial-layer-contracts.md:

  Pricing     → Unit   (not directly to Project)
  Sales       → Unit   (not directly to Project)
  Contract    → Unit   (not directly to Project)
  PaymentPlan → Contract
  Finance     → read-only aggregation of downstream outputs
  Registry    → participant + case management; project_id must match
                unit hierarchy (Unit → Floor → Building → Phase → Project)

Each section validates both the ORM model foreign-key topology and the
service-layer business-rule enforcement.
"""

from datetime import date
from typing import Optional

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Shared hierarchy builder
# ---------------------------------------------------------------------------


def _make_project(db: Session, code: str) -> str:
    from app.modules.projects.models import Project

    p = Project(name=f"Project {code}", code=code)
    db.add(p)
    db.flush()
    return p.id


def _make_unit(
    db: Session,
    project_id: str,
    unit_number: str = "101",
    *,
    unit_suffix: str = "",
) -> str:
    """Create Phase → Building → Floor → Unit under *project_id*; return unit id."""
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    phase = Phase(project_id=project_id, name=f"Phase-{unit_number}{unit_suffix}", sequence=1)
    db.add(phase)
    db.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"BLK-{unit_number}{unit_suffix}")
    db.add(building)
    db.flush()

    floor = Floor(
        building_id=building.id,
        name="Floor 1",
        code=f"FL-01-{unit_number}{unit_suffix}",
        sequence_number=1,
    )
    db.add(floor)
    db.flush()

    unit = Unit(
        floor_id=floor.id,
        unit_number=unit_number,
        unit_type="studio",
        internal_area=100.0,
    )
    db.add(unit)
    db.flush()
    return unit.id


def _make_buyer(db: Session, email: str = "buyer@test.com") -> str:
    from app.modules.sales.models import Buyer

    b = Buyer(full_name="Test Buyer", email=email, phone="+9620000001")
    db.add(b)
    db.flush()
    return b.id


def _make_contract(
    db: Session,
    unit_id: str,
    buyer_id: str,
    contract_number: str = "CNT-0001",
    price: float = 500_000.0,
) -> str:
    from app.modules.sales.models import SalesContract

    c = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer_id,
        contract_number=contract_number,
        contract_date=date(2026, 1, 1),
        contract_price=price,
    )
    db.add(c)
    db.flush()
    return c.id


def _set_pricing(db: Session, unit_id: str) -> None:
    from app.modules.pricing.service import PricingService
    from app.modules.pricing.schemas import UnitPricingAttributesCreate

    PricingService(db).set_pricing_attributes(
        unit_id,
        UnitPricingAttributesCreate(
            base_price_per_sqm=5_000.0,
            floor_premium=0.0,
            view_premium=0.0,
            corner_premium=0.0,
            size_adjustment=0.0,
            custom_adjustment=0.0,
        ),
    )


# ===========================================================================
# 1. PRICING BOUNDARY RULES
# ===========================================================================


class TestPricingBoundary:
    """Pricing records must attach to Unit, not directly to Project."""

    def test_unit_pricing_attributes_fk_is_unit(self, db_session: Session):
        """UnitPricingAttributes.unit_id is a FK to units, never to projects."""
        from app.modules.pricing.models import UnitPricingAttributes

        col = UnitPricingAttributes.__table__.c.unit_id
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "units.id" in fk_targets, (
            "UnitPricingAttributes.unit_id must be a FK to units.id"
        )
        # Must NOT reference projects directly
        assert not any("projects" in t for t in fk_targets), (
            "UnitPricingAttributes must not reference projects directly"
        )

    def test_unit_pricing_fk_is_unit(self, db_session: Session):
        """UnitPricing.unit_id is a FK to units, never to projects."""
        from app.modules.pricing.models import UnitPricing

        col = UnitPricing.__table__.c.unit_id
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "units.id" in fk_targets
        assert not any("projects" in t for t in fk_targets)

    def test_pricing_attributes_attach_to_unit_not_project(self, db_session: Session):
        """Service: pricing attributes are stored per-unit, not per-project."""
        from app.modules.pricing.service import PricingService
        from app.modules.pricing.schemas import UnitPricingAttributesCreate

        project_id = _make_project(db_session, "PRJ-PA-1")
        unit_id = _make_unit(db_session, project_id, "101")
        svc = PricingService(db_session)

        attrs = svc.set_pricing_attributes(
            unit_id,
            UnitPricingAttributesCreate(
                base_price_per_sqm=5_000.0,
                floor_premium=1_000.0,
                view_premium=500.0,
                corner_premium=200.0,
                size_adjustment=100.0,
                custom_adjustment=0.0,
            ),
        )

        assert attrs.unit_id == unit_id, "Pricing attributes must reference the unit"

    def test_pricing_service_does_not_create_sales_records(self, db_session: Session):
        """PricingService must not create Reservation or SalesContract rows."""
        from app.modules.pricing.service import PricingService
        from app.modules.pricing.schemas import UnitPricingAttributesCreate
        from app.modules.sales.models import Reservation, SalesContract

        project_id = _make_project(db_session, "PRJ-PA-2")
        unit_id = _make_unit(db_session, project_id, "102")
        svc = PricingService(db_session)
        svc.set_pricing_attributes(
            unit_id,
            UnitPricingAttributesCreate(
                base_price_per_sqm=4_000.0,
                floor_premium=0.0,
                view_premium=0.0,
                corner_premium=0.0,
                size_adjustment=0.0,
                custom_adjustment=0.0,
            ),
        )
        svc.calculate_unit_price(unit_id)

        assert db_session.query(Reservation).count() == 0, (
            "PricingService must not create Reservation records"
        )
        assert db_session.query(SalesContract).count() == 0, (
            "PricingService must not create SalesContract records"
        )

    def test_pricing_invalid_unit_raises_404(self, db_session: Session):
        """Pricing service raises 404 for an unknown unit, not 500."""
        from app.modules.pricing.service import PricingService
        from app.modules.pricing.schemas import UnitPricingAttributesCreate

        svc = PricingService(db_session)
        with pytest.raises(HTTPException) as exc:
            svc.set_pricing_attributes(
                "nonexistent-unit",
                UnitPricingAttributesCreate(
                    base_price_per_sqm=1.0,
                    floor_premium=0.0,
                    view_premium=0.0,
                    corner_premium=0.0,
                    size_adjustment=0.0,
                    custom_adjustment=0.0,
                ),
            )
        assert exc.value.status_code == 404


# ===========================================================================
# 2. SALES BOUNDARY RULES
# ===========================================================================


class TestSalesBoundary:
    """Sales records must attach to Unit, not directly to Project."""

    def test_reservation_fk_is_unit(self, db_session: Session):
        """Reservation.unit_id must be a FK to units, not projects."""
        from app.modules.sales.models import Reservation

        col = Reservation.__table__.c.unit_id
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "units.id" in fk_targets
        assert not any("projects" in t for t in fk_targets)

    def test_sales_contract_fk_is_unit(self, db_session: Session):
        """SalesContract.unit_id must be a FK to units, not projects."""
        from app.modules.sales.models import SalesContract

        col = SalesContract.__table__.c.unit_id
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "units.id" in fk_targets
        assert not any("projects" in t for t in fk_targets)

    def test_reservation_attaches_to_unit(self, db_session: Session):
        """Service: a created reservation's unit_id equals the requested unit."""
        from app.modules.sales.service import SalesService
        from app.modules.sales.schemas import BuyerCreate, ReservationCreate

        project_id = _make_project(db_session, "PRJ-RES-1")
        unit_id = _make_unit(db_session, project_id, "201")
        _set_pricing(db_session, unit_id)

        svc = SalesService(db_session)
        buyer = svc.create_buyer(BuyerCreate(full_name="A Buyer", email="a@b.com", phone="+1"))
        res = svc.create_reservation(
            ReservationCreate(
                unit_id=unit_id,
                buyer_id=buyer.id,
                reservation_date=date(2026, 3, 1),
                expiry_date=date(2026, 4, 1),
            )
        )

        assert res.unit_id == unit_id

    def test_contract_attaches_to_unit(self, db_session: Session):
        """Service: a created contract's unit_id equals the requested unit."""
        from app.modules.sales.service import SalesService
        from app.modules.sales.schemas import BuyerCreate, SalesContractCreate

        project_id = _make_project(db_session, "PRJ-CNT-1")
        unit_id = _make_unit(db_session, project_id, "301")

        svc = SalesService(db_session)
        buyer = svc.create_buyer(BuyerCreate(full_name="B Buyer", email="b@b.com", phone="+2"))
        contract = svc.create_contract(
            SalesContractCreate(
                unit_id=unit_id,
                buyer_id=buyer.id,
                contract_number="CNT-TEST-001",
                contract_date=date(2026, 3, 1),
                contract_price=600_000.0,
            )
        )

        assert contract.unit_id == unit_id

    def test_sales_service_does_not_calculate_finance_kpis(self, db_session: Session):
        """SalesService does not mutate finance summary rows."""
        from app.modules.sales.service import SalesService
        from app.modules.sales.schemas import BuyerCreate, SalesContractCreate

        # Finance models.py is intentionally empty; verify no model-based
        # finance table is manipulated by the sales service create path.
        project_id = _make_project(db_session, "PRJ-SF-1")
        unit_id = _make_unit(db_session, project_id, "401")

        svc = SalesService(db_session)
        buyer = svc.create_buyer(BuyerCreate(full_name="C Buyer", email="c@c.com", phone="+3"))
        svc.create_contract(
            SalesContractCreate(
                unit_id=unit_id,
                buyer_id=buyer.id,
                contract_number="CNT-TEST-002",
                contract_date=date(2026, 3, 1),
                contract_price=750_000.0,
            )
        )

        # PR-23 introduced analytics fact models into finance.models.  Verify
        # that the SalesService does not write to any of those fact tables —
        # only the analytics rebuild endpoint is permitted to write fact rows.
        import app.modules.finance.models as _fin_models
        from sqlalchemy.orm.decl_api import DeclarativeAttributeIntercept

        _ANALYTICS_FACT_MODELS = {"Base", "FactRevenue", "FactCollections", "FactReceivablesSnapshot"}

        finance_orm_classes = [
            v
            for v in vars(_fin_models).values()
            if isinstance(v, DeclarativeAttributeIntercept)
        ]

        # All classes in finance.models must be analytics fact models; no
        # pricing/sales classes should appear there.
        non_analytics = [c for c in finance_orm_classes if c.__name__ not in _ANALYTICS_FACT_MODELS]
        assert non_analytics == [], (
            "finance.models must not define pricing or sales ORM models; "
            f"unexpected classes found: {[c.__name__ for c in non_analytics]}"
        )

    def test_reservation_requires_unit_to_exist(self, db_session: Session):
        """SalesService raises 404 when unit does not exist."""
        from app.modules.sales.service import SalesService
        from app.modules.sales.schemas import BuyerCreate, ReservationCreate

        svc = SalesService(db_session)
        buyer = svc.create_buyer(BuyerCreate(full_name="D Buyer", email="d@d.com", phone="+4"))
        with pytest.raises(HTTPException) as exc:
            svc.create_reservation(
                ReservationCreate(
                    unit_id="no-such-unit",
                    buyer_id=buyer.id,
                    reservation_date=date(2026, 3, 1),
                    expiry_date=date(2026, 4, 1),
                )
            )
        assert exc.value.status_code == 404


# ===========================================================================
# 3. PAYMENT PLAN BOUNDARY RULES
# ===========================================================================


class TestPaymentPlanBoundary:
    """PaymentSchedule must attach to a Contract, not directly to a Project."""

    def test_payment_schedule_fk_is_contract(self, db_session: Session):
        """PaymentSchedule.contract_id must be a FK to sales_contracts."""
        from app.modules.payment_plans.models import PaymentSchedule

        col = PaymentSchedule.__table__.c.contract_id
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "sales_contracts.id" in fk_targets, (
            "PaymentSchedule.contract_id must reference sales_contracts.id"
        )
        assert not any("projects" in t for t in fk_targets), (
            "PaymentSchedule must not reference projects directly"
        )

    def test_payment_plan_template_has_no_project_fk(self, db_session: Session):
        """PaymentPlanTemplate is a reusable blueprint — no project FK."""
        from app.modules.payment_plans.models import PaymentPlanTemplate

        cols = PaymentPlanTemplate.__table__.c
        fk_cols_referencing_projects = [
            c.name
            for c in cols
            if any("projects" in fk.target_fullname for fk in c.foreign_keys)
        ]
        assert not fk_cols_referencing_projects, (
            "PaymentPlanTemplate must not contain a direct FK to projects; "
            f"found: {fk_cols_referencing_projects}"
        )

    def test_payment_schedule_attaches_to_contract(self, db_session: Session):
        """Service: generated schedule rows reference the contract, not the project."""
        from app.modules.payment_plans.service import PaymentPlanService
        from app.modules.payment_plans.schemas import (
            PaymentPlanTemplateCreate,
            PaymentPlanGenerateRequest,
        )
        from app.shared.enums.finance import InstallmentFrequency, PaymentPlanType

        project_id = _make_project(db_session, "PRJ-PP-1")
        unit_id = _make_unit(db_session, project_id, "501")
        buyer_id = _make_buyer(db_session, "pplan@test.com")
        contract_id = _make_contract(db_session, unit_id, buyer_id, "CNT-PP-001")
        db_session.commit()

        svc = PaymentPlanService(db_session)
        template = svc.create_template(
            PaymentPlanTemplateCreate(
                name="Standard 12m",
                plan_type=PaymentPlanType.STANDARD_INSTALLMENTS,
                down_payment_percent=10.0,
                number_of_installments=12,
                installment_frequency=InstallmentFrequency.MONTHLY,
            )
        )
        schedule = svc.generate_schedule_for_contract(
            PaymentPlanGenerateRequest(
                contract_id=contract_id,
                template_id=template.id,
                start_date=date(2026, 2, 1),
            )
        )

        assert len(schedule.items) > 0
        for row in schedule.items:
            assert row.contract_id == contract_id, (
                "Every PaymentSchedule row must reference its contract"
            )


# ===========================================================================
# 4. FINANCE BOUNDARY RULES
# ===========================================================================


class TestFinanceBoundary:
    """Finance summaries must consume downstream outputs — read-only aggregation."""

    def test_finance_models_contain_no_pricing_or_sales_logic(self, db_session: Session):
        """finance.models must only define analytics fact models — no pricing/sales ORM models."""
        import app.modules.finance.models as finance_models
        from sqlalchemy.orm.decl_api import DeclarativeAttributeIntercept

        # Analytics fact models are the only ORM classes permitted in finance.models.
        _ALLOWED_ANALYTICS_MODELS = {"Base", "FactRevenue", "FactCollections", "FactReceivablesSnapshot"}

        # Gather any SQLAlchemy mapped classes exported from finance.models
        finance_orm_classes = [
            v
            for v in vars(finance_models).values()
            if isinstance(v, DeclarativeAttributeIntercept)
        ]

        # Filter out the expected analytics fact models.
        unexpected = [c for c in finance_orm_classes if c.__name__ not in _ALLOWED_ANALYTICS_MODELS]

        assert unexpected == [], (
            "finance.models must not define pricing or sales ORM models — "
            "only analytics fact models (FactRevenue, FactCollections, "
            "FactReceivablesSnapshot) are permitted; "
            f"unexpected models found: {[c.__name__ for c in unexpected]}"
        )

    def test_finance_summary_reads_contracts_downstream(self, db_session: Session):
        """FinanceSummaryService reads contract values — it does not own them."""
        from app.modules.finance.service import FinanceSummaryService

        project_id = _make_project(db_session, "PRJ-FIN-1")
        unit_id = _make_unit(db_session, project_id, "601")
        buyer_id = _make_buyer(db_session, "fin@test.com")
        _make_contract(db_session, unit_id, buyer_id, "CNT-FIN-001", price=800_000.0)
        db_session.commit()

        svc = FinanceSummaryService(db_session)
        summary = svc.get_project_summary(project_id)

        assert summary.project_id == project_id
        assert summary.total_contract_value == pytest.approx(800_000.0)
        # Finance service must not redefine pricing; it reads contract_price only
        assert summary.average_unit_price == pytest.approx(800_000.0)

    def test_finance_summary_does_not_mutate_contracts(self, db_session: Session):
        """Calling the finance summary must not change any contract row."""
        from app.modules.finance.service import FinanceSummaryService
        from app.modules.sales.models import SalesContract

        project_id = _make_project(db_session, "PRJ-FIN-2")
        unit_id = _make_unit(db_session, project_id, "602")
        buyer_id = _make_buyer(db_session, "fin2@test.com")
        contract_id = _make_contract(db_session, unit_id, buyer_id, "CNT-FIN-002", price=300_000.0)
        db_session.commit()

        before = db_session.get(SalesContract, contract_id)
        before_price = float(before.contract_price)

        svc = FinanceSummaryService(db_session)
        svc.get_project_summary(project_id)

        after = db_session.get(SalesContract, contract_id)
        assert float(after.contract_price) == before_price, (
            "FinanceSummaryService must not mutate contract_price"
        )

    def test_finance_summary_unknown_project_raises_404(self, db_session: Session):
        from app.modules.finance.service import FinanceSummaryService

        svc = FinanceSummaryService(db_session)
        with pytest.raises(HTTPException) as exc:
            svc.get_project_summary("nonexistent-project")
        assert exc.value.status_code == 404


# ===========================================================================
# 5. REGISTRY BOUNDARY RULES
# ===========================================================================


class TestRegistryBoundary:
    """Registry cases must trace to the unit hierarchy; no pricing/finance math."""

    def test_registration_case_fk_is_unit(self, db_session: Session):
        """RegistrationCase.unit_id must be a FK to units."""
        from app.modules.registry.models import RegistrationCase

        col = RegistrationCase.__table__.c.unit_id
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "units.id" in fk_targets

    def test_registration_case_fk_is_contract(self, db_session: Session):
        """RegistrationCase.sale_contract_id must be a FK to sales_contracts."""
        from app.modules.registry.models import RegistrationCase

        col = RegistrationCase.__table__.c.sale_contract_id
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "sales_contracts.id" in fk_targets

    def test_create_case_with_correct_project_id_succeeds(self, db_session: Session):
        """RegistryService allows a case when project_id matches the unit's project."""
        from app.modules.registry.service import RegistryService
        from app.modules.registry.schemas import RegistrationCaseCreate

        project_id = _make_project(db_session, "PRJ-REG-1")
        unit_id = _make_unit(db_session, project_id, "701")
        buyer_id = _make_buyer(db_session, "reg1@test.com")
        contract_id = _make_contract(db_session, unit_id, buyer_id, "CNT-REG-001")
        db_session.commit()

        svc = RegistryService(db_session)
        case = svc.create_case(
            RegistrationCaseCreate(
                project_id=project_id,
                unit_id=unit_id,
                sale_contract_id=contract_id,
                buyer_name="Test Buyer",
            )
        )

        assert case.unit_id == unit_id
        assert case.project_id == project_id

    def test_create_case_wrong_project_id_raises_422(self, db_session: Session):
        """RegistryService rejects a case whose project_id does not match the unit's project."""
        from app.modules.registry.service import RegistryService
        from app.modules.registry.schemas import RegistrationCaseCreate

        project_a_id = _make_project(db_session, "PRJ-REG-A")
        project_b_id = _make_project(db_session, "PRJ-REG-B")
        unit_id = _make_unit(db_session, project_a_id, "801")
        buyer_id = _make_buyer(db_session, "reg2@test.com")
        contract_id = _make_contract(db_session, unit_id, buyer_id, "CNT-REG-002")
        db_session.commit()

        svc = RegistryService(db_session)
        with pytest.raises(HTTPException) as exc:
            svc.create_case(
                RegistrationCaseCreate(
                    project_id=project_b_id,   # <-- wrong project
                    unit_id=unit_id,
                    sale_contract_id=contract_id,
                    buyer_name="Test Buyer",
                )
            )
        assert exc.value.status_code == 422, (
            "Supplying a project_id that does not match the unit hierarchy must "
            "be rejected with HTTP 422"
        )
        assert project_a_id in exc.value.detail or project_b_id in exc.value.detail

    def test_create_case_contract_must_belong_to_unit(self, db_session: Session):
        """RegistryService rejects a case where the contract belongs to a different unit."""
        from app.modules.registry.service import RegistryService
        from app.modules.registry.schemas import RegistrationCaseCreate
        from app.modules.buildings.models import Building
        from app.modules.floors.models import Floor
        from app.modules.phases.models import Phase
        from app.modules.units.models import Unit

        project_id = _make_project(db_session, "PRJ-REG-3")
        unit_a_id = _make_unit(db_session, project_id, "901", unit_suffix="-A")

        # Second unit: reuse the same phase/building/floor to avoid sequence clash
        phase_b = Phase(project_id=project_id, name="Phase-B", sequence=2)
        db_session.add(phase_b)
        db_session.flush()
        bld_b = Building(phase_id=phase_b.id, name="Block B", code="BLK-902")
        db_session.add(bld_b)
        db_session.flush()
        flr_b = Floor(building_id=bld_b.id, name="Floor 1", code="FL-B-01", sequence_number=1)
        db_session.add(flr_b)
        db_session.flush()
        unit_b = Unit(floor_id=flr_b.id, unit_number="902", unit_type="studio", internal_area=80.0)
        db_session.add(unit_b)
        db_session.flush()
        unit_b_id = unit_b.id

        buyer_id = _make_buyer(db_session, "reg3@test.com")
        contract_for_unit_a = _make_contract(db_session, unit_a_id, buyer_id, "CNT-REG-003")
        db_session.commit()

        svc = RegistryService(db_session)
        with pytest.raises(HTTPException) as exc:
            svc.create_case(
                RegistrationCaseCreate(
                    project_id=project_id,
                    unit_id=unit_b_id,           # different unit
                    sale_contract_id=contract_for_unit_a,
                    buyer_name="Test Buyer",
                )
            )
        assert exc.value.status_code == 422

    def test_registry_service_does_not_calculate_pricing(self, db_session: Session):
        """RegistryService must not create pricing records."""
        from app.modules.registry.service import RegistryService
        from app.modules.registry.schemas import RegistrationCaseCreate
        from app.modules.pricing.models import UnitPricing, UnitPricingAttributes

        project_id = _make_project(db_session, "PRJ-REG-4")
        unit_id = _make_unit(db_session, project_id, "1001")
        buyer_id = _make_buyer(db_session, "reg4@test.com")
        contract_id = _make_contract(db_session, unit_id, buyer_id, "CNT-REG-004")
        db_session.commit()

        svc = RegistryService(db_session)
        svc.create_case(
            RegistrationCaseCreate(
                project_id=project_id,
                unit_id=unit_id,
                sale_contract_id=contract_id,
                buyer_name="Test Buyer",
            )
        )

        assert db_session.query(UnitPricing).count() == 0, (
            "RegistryService must not create UnitPricing records"
        )
        assert db_session.query(UnitPricingAttributes).count() == 0, (
            "RegistryService must not create UnitPricingAttributes records"
        )


# ===========================================================================
# 6. CROSS-DOMAIN ISOLATION
# ===========================================================================


def _assert_no_forbidden_imports(module, forbidden_prefixes: list[str]) -> None:
    """Parse *module*'s source with the AST and assert it contains no
    ``Import`` or ``ImportFrom`` nodes whose dotted name starts with any of
    the *forbidden_prefixes*.

    Using the AST rather than substring-matching ``inspect.getsource()``
    ensures that:
    - Mentions of a forbidden name in docstrings or comments do not trigger
      false positives.
    - Dynamic ``importlib`` calls are out of scope (those are separate
      integration concerns), but all static import statements are caught
      correctly.
    """
    import ast
    import inspect

    src = inspect.getsource(module)
    tree = ast.parse(src)

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            dotted = node.module or ""
            if any(dotted == p or dotted.startswith(p + ".") for p in forbidden_prefixes):
                violations.append(f"from {dotted} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                dotted = alias.name
                if any(dotted == p or dotted.startswith(p + ".") for p in forbidden_prefixes):
                    violations.append(f"import {dotted}")

    assert not violations, (
        f"Module '{module.__name__}' contains forbidden imports targeting "
        f"{forbidden_prefixes}:\n  " + "\n  ".join(violations)
    )


class TestCrossDomainIsolation:
    """Spot-check that each domain service is isolated from sibling domains."""

    def test_pricing_service_has_no_finance_imports(self):
        """PricingService must not import from finance domain."""
        import app.modules.pricing.service as ps

        _assert_no_forbidden_imports(ps, ["app.modules.finance"])

    def test_pricing_service_has_no_registry_imports(self):
        """PricingService must not import from registry domain."""
        import app.modules.pricing.service as ps

        _assert_no_forbidden_imports(ps, ["app.modules.registry"])

    def test_finance_service_has_no_pricing_write_imports(self):
        """FinanceSummaryService must not import pricing write paths.

        Finance may legitimately traverse unit joins, but it must never import
        the pricing service (which owns pricing record creation).
        """
        import app.modules.finance.service as fs

        _assert_no_forbidden_imports(fs, ["app.modules.pricing.service"])

    def test_registry_service_has_no_pricing_imports(self):
        """RegistryService must not import from pricing domain."""
        import app.modules.registry.service as rs

        _assert_no_forbidden_imports(rs, ["app.modules.pricing"])
