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


# ---------------------------------------------------------------------------
# Hardening tests: duplicate generation, safe regeneration, plan type, allocation
# ---------------------------------------------------------------------------


def test_generate_returns_409_if_schedule_already_exists(db_session: Session):
    """Second call to generate for the same contract must return 409."""
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-DUP409")
    template = svc.create_template(_TEMPLATE_CREATE)

    req = PaymentPlanGenerateRequest(
        contract_id=contract_id,
        template_id=template.id,
        start_date=date(2026, 1, 1),
    )
    svc.generate_schedule_for_contract(req)

    with pytest.raises(HTTPException) as exc:
        svc.generate_schedule_for_contract(req)
    assert exc.value.status_code == 409
    detail = exc.value.detail.lower()
    assert "already" in detail or "regenerate" in detail


def test_generate_409_message_mentions_regenerate(db_session: Session):
    """The 409 detail must guide the user to the regenerate endpoint."""
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-409MSG")
    template = svc.create_template(_TEMPLATE_CREATE)

    req = PaymentPlanGenerateRequest(contract_id=contract_id, template_id=template.id)
    svc.generate_schedule_for_contract(req)

    with pytest.raises(HTTPException) as exc:
        svc.generate_schedule_for_contract(req)
    assert "regenerate" in exc.value.detail.lower()


def test_regenerate_preserves_schedule_on_invalid_template(db_session: Session):
    """If regeneration fails (invalid template), the original schedule must still exist."""
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-SAFE-REGEN")
    template = svc.create_template(_TEMPLATE_CREATE)

    svc.generate_schedule_for_contract(
        PaymentPlanGenerateRequest(
            contract_id=contract_id,
            template_id=template.id,
            start_date=date(2026, 1, 1),
        )
    )
    original_count = svc.get_schedule_for_contract(contract_id).total

    # Attempt regeneration with a non-existent template → 404 before any deletion
    with pytest.raises(HTTPException) as exc:
        svc.regenerate_schedule_for_contract(
            contract_id,
            PaymentPlanGenerateRequest(
                contract_id=contract_id,
                template_id="no-such-template",
            ),
        )
    assert exc.value.status_code == 404

    # Original schedule must still be intact
    after = svc.get_schedule_for_contract(contract_id)
    assert after.total == original_count
    assert after.total_due == pytest.approx(500_000.0)


def test_regenerate_preserves_schedule_on_inactive_template(db_session: Session):
    """Regeneration with an inactive template leaves the original schedule intact."""
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-SAFE-INACT")
    template = svc.create_template(_TEMPLATE_CREATE)

    svc.generate_schedule_for_contract(
        PaymentPlanGenerateRequest(
            contract_id=contract_id,
            template_id=template.id,
            start_date=date(2026, 1, 1),
        )
    )
    original_total = svc.get_schedule_for_contract(contract_id).total_due

    svc.update_template(template.id, PaymentPlanTemplateUpdate(is_active=False))

    with pytest.raises(HTTPException) as exc:
        svc.regenerate_schedule_for_contract(
            contract_id,
            PaymentPlanGenerateRequest(
                contract_id=contract_id,
                template_id=template.id,
            ),
        )
    assert exc.value.status_code == 422

    # Original schedule must still be intact
    after = svc.get_schedule_for_contract(contract_id)
    assert after.total_due == pytest.approx(original_total)


def test_create_template_unsupported_plan_type_rejected(db_session: Session):
    """Creating a template with an unsupported plan type must return 422."""
    svc = PaymentPlanService(db_session)
    with pytest.raises(HTTPException) as exc:
        svc.create_template(
            PaymentPlanTemplateCreate(
                name="Milestone Plan",
                plan_type=PaymentPlanType.MILESTONE,
                down_payment_percent=10.0,
                number_of_installments=5,
                installment_frequency=InstallmentFrequency.MONTHLY,
            )
        )
    assert exc.value.status_code == 422
    assert "not yet implemented" in exc.value.detail.lower() or "supported" in exc.value.detail.lower()


def test_update_template_unsupported_plan_type_rejected(db_session: Session):
    """Updating a template's plan_type to an unsupported value must return 422."""
    svc = PaymentPlanService(db_session)
    created = svc.create_template(_TEMPLATE_CREATE)
    with pytest.raises(HTTPException) as exc:
        svc.update_template(
            created.id,
            PaymentPlanTemplateUpdate(plan_type=PaymentPlanType.POST_HANDOVER),
        )
    assert exc.value.status_code == 422


def test_update_template_invalid_merged_allocation_rejected(db_session: Session):
    """Updating only handover_percent when down_payment pushes total > 100 must fail."""
    svc = PaymentPlanService(db_session)
    # Create template with 60% down payment
    created = svc.create_template(
        PaymentPlanTemplateCreate(
            name="High Down Plan",
            down_payment_percent=60.0,
            number_of_installments=6,
            installment_frequency=InstallmentFrequency.MONTHLY,
        )
    )
    # Update sets handover to 50%; merged total = 60 + 50 = 110 → invalid
    with pytest.raises(HTTPException) as exc:
        svc.update_template(
            created.id,
            PaymentPlanTemplateUpdate(handover_percent=50.0),
        )
    assert exc.value.status_code == 422


def test_update_template_invalid_allocation_both_in_payload(db_session: Session):
    """Schema-level: both percent fields in update payload exceeding 100 returns 422."""
    with pytest.raises(ValueError):
        PaymentPlanTemplateUpdate(
            down_payment_percent=60.0,
            handover_percent=50.0,
        )


def test_generate_unsupported_plan_type_rejected(db_session: Session):
    """Generation must fail if the template has an unsupported plan type stored in DB."""
    svc = PaymentPlanService(db_session)
    contract_id = _make_contract(db_session, "PRJ-UNSUP-GEN")
    # Create a valid template, then directly mutate plan_type in DB to bypass service guard
    from app.modules.payment_plans.models import PaymentPlanTemplate
    template_obj = PaymentPlanTemplate(
        name="Bad Type",
        plan_type="milestone",  # unsupported, injected directly
        down_payment_percent=10.0,
        number_of_installments=6,
        installment_frequency="monthly",
        is_active=True,
    )
    db_session.add(template_obj)
    db_session.commit()
    db_session.refresh(template_obj)

    with pytest.raises(HTTPException) as exc:
        svc.generate_schedule_for_contract(
            PaymentPlanGenerateRequest(
                contract_id=contract_id,
                template_id=template_obj.id,
            )
        )
    assert exc.value.status_code == 422


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
