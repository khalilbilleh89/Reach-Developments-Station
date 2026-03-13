"""
Tests for the payment plan service layer.

Validates template management, schedule generation rules, and business constraints.
"""

import pytest
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.payment_plans.schemas import (
    PaymentPlanGenerateRequest,
    PaymentPlanTemplateCreate,
    PaymentPlanTemplateUpdate,
)
from app.modules.payment_plans.service import PaymentPlanService
from app.shared.enums.finance import InstallmentFrequency, PaymentPlanType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_unit(db: Session, project_code: str = "PRJ-PP-SVC") -> str:
    from app.modules.projects.models import Project
    from app.modules.phases.models import Phase
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.units.models import Unit

    project = Project(name="PP Service Project", code=project_code)
    db.add(project)
    db.flush()

    phase = Phase(project_id=project.id, name="Phase 1", sequence=1)
    db.add(phase)
    db.flush()

    building = Building(phase_id=phase.id, name="Block A", code="BLK-A")
    db.add(building)
    db.flush()

    floor = Floor(building_id=building.id, level=1)
    db.add(floor)
    db.flush()

    unit = Unit(floor_id=floor.id, unit_number="101", unit_type="studio", internal_area=100.0)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit.id


def _make_contract(
    db: Session,
    project_code: str = "PRJ-PP-SVC",
    contract_price: float = 500_000.0,
) -> str:
    from app.modules.sales.models import Buyer, SalesContract

    unit_id = _make_unit(db, project_code)

    buyer = Buyer(full_name="PP Buyer", email=f"ppb-{project_code}@test.com", phone="+1")
    db.add(buyer)
    db.flush()

    contract = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer.id,
        contract_number=f"CNT-{project_code}-001",
        contract_date=date(2026, 1, 1),
        contract_price=contract_price,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract.id


_TEMPLATE_CREATE = PaymentPlanTemplateCreate(
    name="Standard 12M",
    plan_type=PaymentPlanType.STANDARD_INSTALLMENTS,
    down_payment_percent=10.0,
    number_of_installments=12,
    installment_frequency=InstallmentFrequency.MONTHLY,
)


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------


def test_create_template(db_session: Session):
    svc = PaymentPlanService(db_session)
    template = svc.create_template(_TEMPLATE_CREATE)
    assert template.name == "Standard 12M"
    assert template.down_payment_percent == pytest.approx(10.0)
    assert template.is_active is True
    assert template.id


def test_get_template(db_session: Session):
    svc = PaymentPlanService(db_session)
    created = svc.create_template(_TEMPLATE_CREATE)
    fetched = svc.get_template(created.id)
    assert fetched.id == created.id
    assert fetched.name == "Standard 12M"


def test_get_template_not_found(db_session: Session):
    svc = PaymentPlanService(db_session)
    with pytest.raises(HTTPException) as exc:
        svc.get_template("no-such-template")
    assert exc.value.status_code == 404


def test_list_templates(db_session: Session):
    svc = PaymentPlanService(db_session)
    svc.create_template(_TEMPLATE_CREATE)
    svc.create_template(
        PaymentPlanTemplateCreate(
            name="Quarterly 4",
            down_payment_percent=20.0,
            number_of_installments=4,
            installment_frequency=InstallmentFrequency.QUARTERLY,
        )
    )
    result = svc.list_templates()
    assert result.total == 2
    assert len(result.items) == 2


def test_update_template(db_session: Session):
    svc = PaymentPlanService(db_session)
    created = svc.create_template(_TEMPLATE_CREATE)
    updated = svc.update_template(created.id, PaymentPlanTemplateUpdate(name="Updated Name"))
    assert updated.name == "Updated Name"
    assert updated.id == created.id


def test_update_template_deactivate(db_session: Session):
    svc = PaymentPlanService(db_session)
    created = svc.create_template(_TEMPLATE_CREATE)
    updated = svc.update_template(created.id, PaymentPlanTemplateUpdate(is_active=False))
    assert updated.is_active is False


def test_update_template_not_found(db_session: Session):
    svc = PaymentPlanService(db_session)
    with pytest.raises(HTTPException) as exc:
        svc.update_template("no-such", PaymentPlanTemplateUpdate(name="X"))
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Schedule generation
# ---------------------------------------------------------------------------


def test_generate_schedule_for_contract(db_session: Session):
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-GEN1", 500_000.0)
    template = svc.create_template(_TEMPLATE_CREATE)

    result = svc.generate_schedule_for_contract(
        PaymentPlanGenerateRequest(
            contract_id=contract_id,
            template_id=template.id,
            start_date=date(2026, 1, 1),
        )
    )

    assert result.contract_id == contract_id
    assert result.total > 0
    assert result.total_due == pytest.approx(500_000.0)


def test_generate_schedule_total_equals_contract_price(db_session: Session):
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-SUM1", 333_333.33)
    template = svc.create_template(
        PaymentPlanTemplateCreate(
            name="Awkward Price Plan",
            down_payment_percent=10.0,
            number_of_installments=7,
            installment_frequency=InstallmentFrequency.MONTHLY,
        )
    )

    result = svc.generate_schedule_for_contract(
        PaymentPlanGenerateRequest(
            contract_id=contract_id,
            template_id=template.id,
            start_date=date(2026, 1, 1),
        )
    )

    assert abs(result.total_due - 333_333.33) < 0.02


def test_generate_schedule_contract_not_found(db_session: Session):
    svc = PaymentPlanService(db_session)
    template = svc.create_template(_TEMPLATE_CREATE)

    with pytest.raises(HTTPException) as exc:
        svc.generate_schedule_for_contract(
            PaymentPlanGenerateRequest(
                contract_id="no-such-contract",
                template_id=template.id,
            )
        )
    assert exc.value.status_code == 404


def test_generate_schedule_template_not_found(db_session: Session):
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-TNFND")

    with pytest.raises(HTTPException) as exc:
        svc.generate_schedule_for_contract(
            PaymentPlanGenerateRequest(
                contract_id=contract_id,
                template_id="no-such-template",
            )
        )
    assert exc.value.status_code == 404


def test_generate_schedule_inactive_template_rejected(db_session: Session):
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-INACT")
    template = svc.create_template(_TEMPLATE_CREATE)
    svc.update_template(template.id, PaymentPlanTemplateUpdate(is_active=False))

    with pytest.raises(HTTPException) as exc:
        svc.generate_schedule_for_contract(
            PaymentPlanGenerateRequest(
                contract_id=contract_id,
                template_id=template.id,
            )
        )
    assert exc.value.status_code == 422


def test_generate_schedule_default_start_date_is_today(db_session: Session):
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-TODAY")
    template = svc.create_template(_TEMPLATE_CREATE)

    result = svc.generate_schedule_for_contract(
        PaymentPlanGenerateRequest(contract_id=contract_id, template_id=template.id)
    )
    assert result.items[0].due_date == date.today()


# ---------------------------------------------------------------------------
# Schedule retrieval
# ---------------------------------------------------------------------------


def test_get_schedule_for_contract(db_session: Session):
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-GETSCHED")
    template = svc.create_template(_TEMPLATE_CREATE)

    svc.generate_schedule_for_contract(
        PaymentPlanGenerateRequest(
            contract_id=contract_id,
            template_id=template.id,
            start_date=date(2026, 1, 1),
        )
    )

    result = svc.get_schedule_for_contract(contract_id)
    assert result.contract_id == contract_id
    assert result.total > 0
    assert result.total_due == pytest.approx(500_000.0)


def test_get_schedule_contract_not_found(db_session: Session):
    svc = PaymentPlanService(db_session)
    with pytest.raises(HTTPException) as exc:
        svc.get_schedule_for_contract("no-such-contract")
    assert exc.value.status_code == 404


def test_get_schedule_returns_empty_before_generation(db_session: Session):
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-NOSCHED")

    result = svc.get_schedule_for_contract(contract_id)
    assert result.total == 0
    assert result.items == []


# ---------------------------------------------------------------------------
# Schedule regeneration
# ---------------------------------------------------------------------------


def test_regenerate_schedule_replaces_existing(db_session: Session):
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-REGEN")
    template = svc.create_template(_TEMPLATE_CREATE)

    req = PaymentPlanGenerateRequest(
        contract_id=contract_id,
        template_id=template.id,
        start_date=date(2026, 1, 1),
    )
    first = svc.generate_schedule_for_contract(req)

    new_req = PaymentPlanGenerateRequest(
        contract_id=contract_id,
        template_id=template.id,
        start_date=date(2026, 6, 1),
    )
    second = svc.regenerate_schedule_for_contract(contract_id, new_req)

    # Totals must both reconcile to contract price
    assert first.total_due == pytest.approx(500_000.0)
    assert second.total_due == pytest.approx(500_000.0)
    # Start dates differ
    assert second.items[0].due_date == date(2026, 6, 1)


def test_regenerate_schedule_mismatched_contract_id_rejected(db_session: Session):
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-REGMIS")
    template = svc.create_template(_TEMPLATE_CREATE)

    req = PaymentPlanGenerateRequest(
        contract_id="different-contract-id",
        template_id=template.id,
    )
    with pytest.raises(HTTPException) as exc:
        svc.regenerate_schedule_for_contract(contract_id, req)
    assert exc.value.status_code == 400
