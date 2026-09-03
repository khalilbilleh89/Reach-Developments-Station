"""Turning construction rows into the module's public responses.

Separate from ``service.py`` because these functions answer a different
question. The service decides what may happen and writes it; this decides what a
caller is shown, and every figure it puts in a response comes from the service
or the calculator rather than being worked out a second time here. Two
implementations of "revised commitment" is one more than the number that can be
right.

Separate from ``api.py`` because a handler that assembled a response would be a
handler containing domain knowledge, and the same assembly is needed by several
routes.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.construction import calculator, schemas, service
from app.modules.construction.calculator import ZERO, money
from app.modules.construction.models import (
    INVOICE_STANDING,
    BudgetVersion,
    Certificate,
    CertificateLine,
    Contract,
    ContractLine,
    CostCode,
    ForecastVersion,
    Invoice,
    Milestone,
    MilestoneDependency,
    Payment,
    Variation,
    VariationLine,
)
from app.modules.inventory.custom_fields import business_today
from app.modules.projects.models import Project
from app.modules.settings.models import Currency


def _currency_code(session: Session, currency_id: uuid.UUID | None) -> str | None:
    """The code a figure is denominated in, or ``None`` where it is unresolved.

    Never guessed from the project: a record says what it is in, and a code
    invented for a row whose currency could not be resolved is a label on a
    number that may not be in that currency at all.
    """
    if currency_id is None:
        return None
    currency = session.get(Currency, currency_id)
    return currency.code if currency is not None else None


def _cost_code_labels(session: Session, *, project_id: uuid.UUID) -> dict[uuid.UUID, CostCode]:
    return {
        code.id: code
        for code in session.scalars(select(CostCode).where(CostCode.project_id == project_id))
    }


def cost_code_out(code: CostCode) -> schemas.CostCodeOut:
    return schemas.CostCodeOut.model_validate(code, from_attributes=True)


# --------------------------------------------------------------------------- #
# Budget
# --------------------------------------------------------------------------- #


def budget_out(session: Session, *, version: BudgetVersion) -> schemas.BudgetOut:
    """A budget version header, with its currency resolved to a code.

    Built field by field rather than validated straight off the ORM row. The
    row stores ``currency_id``; the response states a code, and a schema that
    filled the gap with a default would answer with a null denomination on
    every figure under it.
    """
    return schemas.BudgetOut(
        id=version.id,
        version_number=version.version_number,
        status=version.status,
        effective_date=version.effective_date,
        change_reason=version.change_reason,
        source_version_id=version.source_version_id,
        currency_code=_currency_code(session, version.currency_id),
        created_at=version.created_at,
        submitted_at=version.submitted_at,
        approved_at=version.approved_at,
        rejected_at=version.rejected_at,
        rejection_reason=version.rejection_reason,
        activated_at=version.activated_at,
        superseded_at=version.superseded_at,
    )


def budget_detail(
    session: Session, *, project: Project, version: BudgetVersion
) -> schemas.BudgetDetailOut:
    """One budget version with its lines, each showing what it now carries.

    Commitment and headroom are shown beside the authorisation because the
    question a reader has in front of a budget is never "what did we allow?"
    on its own — it is "what have we allowed, what have we signed, and what is
    left".
    """
    codes = _cost_code_labels(session, project_id=project.id)
    committed = service.committed_by_cost_code(session, project_id=project.id)
    lines = service.budget_lines_by_cost_code(session, budget_version_id=version.id)

    out_lines: list[schemas.BudgetLineOut] = []
    baseline = approved = contingency = control = ZERO
    for cost_code_id, line in sorted(
        lines.items(), key=lambda item: codes[item[0]].code if item[0] in codes else ""
    ):
        code = codes.get(cost_code_id)
        line_control = calculator.control_budget(
            approved_budget=line.approved_budget_amount, contingency=line.contingency_amount
        )
        commitment = committed.get(cost_code_id, ZERO)
        out_lines.append(
            schemas.BudgetLineOut(
                cost_code_id=cost_code_id,
                cost_code=code.code if code else "",
                cost_code_name=code.name if code else "",
                cost_category=code.cost_category if code else "",
                baseline_amount=line.baseline_amount,
                approved_budget_amount=line.approved_budget_amount,
                contingency_amount=line.contingency_amount,
                control_budget=line_control,
                revised_commitment=commitment,
                headroom=calculator.headroom(
                    approved_budget=line.approved_budget_amount,
                    contingency=line.contingency_amount,
                    committed=commitment,
                ),
                funding_source=line.funding_source,
                notes=line.notes,
            )
        )
        baseline = money(baseline + line.baseline_amount)
        approved = money(approved + line.approved_budget_amount)
        contingency = money(contingency + line.contingency_amount)
        control = money(control + line_control)

    return schemas.BudgetDetailOut(
        **budget_out(session, version=version).model_dump(),
        lines=out_lines,
        total_baseline=baseline,
        total_approved_budget=approved,
        total_contingency=contingency,
        total_control_budget=control,
    )


# --------------------------------------------------------------------------- #
# Contracts
# --------------------------------------------------------------------------- #


def _contract_figures(
    session: Session, *, project: Project, contract: Contract
) -> tuple[Decimal, Decimal, Decimal]:
    """A contract's variation delta, revised commitment and certified total."""
    delta = session.scalars(
        select(func.sum(VariationLine.value_delta_ex_tax))
        .join(Variation, Variation.id == VariationLine.variation_id)
        .where(
            Variation.contract_id == contract.id,
            Variation.status == "approved",
        )
    ).first()
    delta = money(delta or ZERO)
    certified = money(
        sum(
            service.certified_by_cost_code(
                session, project_id=project.id, contract_id=contract.id
            ).values(),
            ZERO,
        )
    )
    return (
        delta,
        calculator.revised_commitment(
            original_amount=contract.original_contract_value_ex_tax,
            approved_variation_delta=delta,
        ),
        certified,
    )


def contract_out(session: Session, *, project: Project, contract: Contract) -> schemas.ContractOut:
    delta, revised, certified = _contract_figures(session, project=project, contract=contract)
    return schemas.ContractOut(
        id=contract.id,
        contract_number=contract.contract_number,
        contract_type=contract.contract_type,
        vendor_name=contract.vendor_name,
        status=contract.status,
        currency_code=_currency_code(session, contract.currency_id),
        original_contract_value_ex_tax=contract.original_contract_value_ex_tax,
        approved_variation_delta=delta,
        revised_commitment=revised,
        certified_to_date=certified,
        advance_entitlement_amount=contract.advance_entitlement_amount,
        retention_rate_fraction=contract.retention_rate_fraction,
        planned_start_date=contract.planned_start_date,
        planned_completion_date=contract.planned_completion_date,
        actual_start_date=contract.actual_start_date,
        actual_completion_date=contract.actual_completion_date,
    )


def contract_detail(
    session: Session, *, project: Project, contract: Contract
) -> schemas.ContractDetailOut:
    """The contract file: what was committed, certified, invoiced and paid.

    The cost figures and the cash figures both appear, in separate groups, and
    the schema names which is which. They are never subtracted from one another:
    certified work ex tax minus cash paid including tax is not a variance, it is
    two different questions answered in one number.
    """
    codes = _cost_code_labels(session, project_id=project.id)
    committed = service.contract_committed_by_cost_code(
        session, project_id=project.id, contract_id=contract.id
    )
    certified_by_code = service.certified_by_cost_code(
        session, project_id=project.id, contract_id=contract.id
    )

    contract_lines = list(
        session.scalars(
            select(ContractLine)
            .where(ContractLine.contract_id == contract.id)
            .order_by(ContractLine.sequence)
        )
    )
    lines = [
        schemas.ContractLineOut(
            id=line.id,
            sequence=line.sequence,
            description=line.description,
            cost_code_id=line.cost_code_id,
            cost_code=codes[line.cost_code_id].code if line.cost_code_id in codes else "",
            original_amount_ex_tax=line.original_amount_ex_tax,
            notes=line.notes,
        )
        for line in contract_lines
    ]

    # The same figures, at the grain that owns them. Two lines naming one cost
    # code contribute one row here, and their originals are added — which is the
    # only operation the model supports on them, since a variation moves the
    # code and not a line.
    original_by_code: dict[uuid.UUID, Decimal] = {}
    for line in contract_lines:
        original_by_code[line.cost_code_id] = money(
            original_by_code.get(line.cost_code_id, ZERO) + line.original_amount_ex_tax
        )
    cost_code_position = [
        schemas.ContractCostCodePosition(
            cost_code_id=cost_code_id,
            cost_code=codes[cost_code_id].code if cost_code_id in codes else "",
            cost_code_name=codes[cost_code_id].name if cost_code_id in codes else "",
            original_amount_ex_tax=original,
            approved_variation_delta=money(committed.get(cost_code_id, ZERO) - original),
            revised_commitment=committed.get(cost_code_id, ZERO),
            certified_to_date=certified_by_code.get(cost_code_id, ZERO),
        )
        for cost_code_id, original in sorted(
            original_by_code.items(),
            key=lambda item: codes[item[0]].code if item[0] in codes else "",
        )
    ]

    approved = session.scalars(
        select(func.sum(Invoice.amount_ex_tax + Invoice.tax_amount)).where(
            Invoice.contract_id == contract.id, Invoice.status == "approved"
        )
    ).first()
    disputed = session.scalars(
        select(func.sum(Invoice.amount_ex_tax + Invoice.tax_amount)).where(
            Invoice.contract_id == contract.id, Invoice.status == "disputed"
        )
    ).first()
    paid = session.scalars(
        select(func.sum(Payment.amount)).where(
            Payment.contract_id == contract.id, Payment.status == "confirmed"
        )
    ).first()
    approved_total = money(approved or ZERO)
    disputed_total = money(disputed or ZERO)
    paid_total = money(paid or ZERO)

    held, released = service.retention_position(
        session, project_id=project.id, contract_id=contract.id
    )
    advance_paid, advance_recovered = service.advance_position(
        session, project_id=project.id, contract_id=contract.id
    )

    return schemas.ContractDetailOut(
        **contract_out(session, project=project, contract=contract).model_dump(),
        vendor_registration_reference=contract.vendor_registration_reference,
        vendor_tax_reference=contract.vendor_tax_reference,
        vendor_contact_reference=contract.vendor_contact_reference,
        payment_terms=contract.payment_terms,
        tax_rate_fraction=contract.tax_rate_fraction,
        notes=contract.notes,
        lines=lines,
        cost_code_position=cost_code_position,
        approved_invoice_payable=approved_total,
        disputed_invoice_payable=disputed_total,
        confirmed_paid=paid_total,
        invoice_outstanding=money(approved_total + disputed_total - paid_total),
        retention_held=held,
        retention_released=released,
        retention_outstanding=calculator.retention_outstanding(held=held, released=released),
        advance_paid=advance_paid,
        advance_recovered=advance_recovered,
        advance_outstanding=calculator.advance_outstanding(
            paid=advance_paid, recovered=advance_recovered
        ),
    )


# --------------------------------------------------------------------------- #
# Variations
# --------------------------------------------------------------------------- #


def variation_out(
    session: Session, *, project: Project, variation: Variation
) -> schemas.VariationOut:
    """A variation, with the escalation rule already applied on the server."""
    escalated, threshold, total = service.variation_requires_escalation(
        session, project=project, variation_id=variation.id
    )
    contract = session.get(Contract, variation.contract_id)
    return schemas.VariationOut(
        id=variation.id,
        contract_id=variation.contract_id,
        contract_number=contract.contract_number if contract else "",
        variation_number=variation.variation_number,
        description=variation.description,
        cause=variation.cause,
        instruction_reference=variation.instruction_reference,
        requested_date=variation.requested_date,
        time_impact_days=variation.time_impact_days,
        funding_source=variation.funding_source,
        status=variation.status,
        total_value_ex_tax=total,
        requires_escalation=escalated,
        review_amount=threshold,
        approved_at=variation.approved_at,
        rejected_at=variation.rejected_at,
        rejection_reason=variation.rejection_reason,
        withdrawn_at=variation.withdrawn_at,
        withdrawal_reason=variation.withdrawal_reason,
    )


def variation_detail(
    session: Session, *, project: Project, variation: Variation
) -> schemas.VariationDetailOut:
    codes = _cost_code_labels(session, project_id=project.id)
    lines = [
        schemas.VariationLineOut(
            id=line.id,
            sequence=line.sequence,
            cost_code_id=line.cost_code_id,
            cost_code=codes[line.cost_code_id].code if line.cost_code_id in codes else "",
            description=line.description,
            value_delta_ex_tax=line.value_delta_ex_tax,
        )
        for line in session.scalars(
            select(VariationLine)
            .where(VariationLine.variation_id == variation.id)
            .order_by(VariationLine.sequence)
        )
    ]
    return schemas.VariationDetailOut(
        **variation_out(session, project=project, variation=variation).model_dump(),
        lines=lines,
    )


# --------------------------------------------------------------------------- #
# Certificates
# --------------------------------------------------------------------------- #


def certificate_detail(
    session: Session, *, project: Project, certificate: Certificate, with_lines: bool = True
) -> schemas.CertificateDetailOut:
    """One certificate, with the waterfall in the one order a valuation has.

    Every component is returned separately — work, tax, release, held, recovery,
    deductions and the net — so the browser renders the arithmetic rather than
    performing it. A screen that subtracted its own retention would be a second
    implementation of the rule the certificate was signed under.
    """
    contract = session.get(Contract, certificate.contract_id)
    amounts = service.certificate_amounts(session, contract=contract, certificate=certificate)
    claimed = session.scalars(
        select(func.sum(Invoice.amount_ex_tax + Invoice.tax_amount)).where(
            Invoice.certificate_id == certificate.id,
            Invoice.status.in_(tuple(INVOICE_STANDING)),
        )
    ).first()

    lines: list[schemas.CertificateLineOut] = []
    if with_lines:
        codes = _cost_code_labels(session, project_id=project.id)
        committed = service.contract_committed_by_cost_code(
            session, project_id=project.id, contract_id=certificate.contract_id
        )
        previous = service.certified_by_cost_code(
            session,
            project_id=project.id,
            contract_id=certificate.contract_id,
            exclude_certificate_id=certificate.id,
        )
        for line in session.scalars(
            select(CertificateLine).where(CertificateLine.certificate_id == certificate.id)
        ):
            before = previous.get(line.cost_code_id, ZERO)
            lines.append(
                schemas.CertificateLineOut(
                    cost_code_id=line.cost_code_id,
                    cost_code=(codes[line.cost_code_id].code if line.cost_code_id in codes else ""),
                    current_work_value_ex_tax=line.current_work_value_ex_tax,
                    previously_certified=before,
                    cumulative_certified=money(before + line.current_work_value_ex_tax),
                    revised_commitment=committed.get(line.cost_code_id, ZERO),
                    notes=line.notes,
                )
            )

    return schemas.CertificateDetailOut(
        id=certificate.id,
        contract_id=certificate.contract_id,
        contract_number=contract.contract_number if contract else "",
        certificate_number=certificate.certificate_number,
        period_start=certificate.period_start,
        period_end=certificate.period_end,
        certificate_date=certificate.certificate_date,
        status=certificate.status,
        certifier_name=certificate.certifier_name,
        evidence_reference=certificate.evidence_reference,
        current_work_value_ex_tax=amounts.current_work_ex_tax,
        tax_amount=amounts.tax,
        retention_release_amount=amounts.retention_release,
        retention_held_amount=amounts.retention_held,
        advance_recovery_amount=amounts.advance_recovery,
        other_deductions_amount=amounts.other_deductions,
        net_due=amounts.net_due,
        uninvoiced_net_due=money(amounts.net_due - money(claimed or ZERO)),
        certified_at=certificate.certified_at,
        rejection_reason=certificate.rejection_reason,
        reversal_reason=certificate.reversal_reason,
        lines=lines,
    )


# --------------------------------------------------------------------------- #
# Invoices and payments
# --------------------------------------------------------------------------- #


def invoice_out(session: Session, *, project: Project, invoice: Invoice) -> schemas.InvoiceOut:
    del project
    contract = session.get(Contract, invoice.contract_id)
    payable = calculator.invoice_payable(
        amount_ex_tax=invoice.amount_ex_tax, tax=invoice.tax_amount
    )
    allocated = service.invoice_allocated(session, invoice_id=invoice.id)
    return schemas.InvoiceOut(
        id=invoice.id,
        contract_id=invoice.contract_id,
        contract_number=contract.contract_number if contract else "",
        certificate_id=invoice.certificate_id,
        invoice_number=invoice.invoice_number,
        invoice_type=invoice.invoice_type,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        status=invoice.status,
        amount_ex_tax=invoice.amount_ex_tax,
        tax_amount=invoice.tax_amount,
        net_payable=payable,
        allocated=allocated,
        outstanding=calculator.outstanding(payable=payable, allocated=allocated),
        dispute_reason=invoice.dispute_reason,
        void_reason=invoice.void_reason,
        approved_at=invoice.approved_at,
    )


def payment_out(session: Session, *, project: Project, payment: Payment) -> schemas.PaymentOut:
    del project
    contract = session.get(Contract, payment.contract_id)
    allocations = []
    total = ZERO
    for allocation in session.scalars(
        select(service.PaymentAllocation).where(service.PaymentAllocation.payment_id == payment.id)
    ):
        invoice = session.get(Invoice, allocation.invoice_id)
        allocations.append(
            schemas.AllocationOut(
                invoice_id=allocation.invoice_id,
                invoice_number=invoice.invoice_number if invoice else "",
                amount=allocation.amount,
            )
        )
        total = money(total + allocation.amount)
    return schemas.PaymentOut(
        id=payment.id,
        contract_id=payment.contract_id,
        contract_number=contract.contract_number if contract else "",
        payment_reference=payment.payment_reference,
        payment_date=payment.payment_date,
        value_date=payment.value_date,
        amount=payment.amount,
        status=payment.status,
        currency_code=_currency_code(session, payment.currency_id),
        bank_reference=payment.bank_reference,
        proof_reference=payment.proof_reference,
        allocated=total,
        unallocated=money(payment.amount - total),
        confirmed_at=payment.confirmed_at,
        reversed_at=payment.reversed_at,
        reversal_reason=payment.reversal_reason,
        allocations=allocations,
    )


# --------------------------------------------------------------------------- #
# Milestones
# --------------------------------------------------------------------------- #


def milestone_out(session: Session, *, milestone: Milestone) -> schemas.MilestoneOut:
    depends = [
        row[0]
        for row in session.execute(
            select(MilestoneDependency.depends_on_milestone_id).where(
                MilestoneDependency.milestone_id == milestone.id
            )
        ).all()
    ]
    return schemas.MilestoneOut(
        id=milestone.id,
        code=milestone.code,
        name=milestone.name,
        milestone_type=milestone.milestone_type,
        phase_id=milestone.phase_id,
        building_id=milestone.building_id,
        scope_label=service.milestone_scope_label(session, milestone=milestone),
        planned_date=milestone.planned_date,
        forecast_date=milestone.forecast_date,
        actual_achieved_date=milestone.actual_achieved_date,
        certified_date=milestone.certified_date,
        progress_fraction=milestone.progress_fraction,
        status=milestone.status,
        delay_days=service.milestone_delay_days(milestone, today=business_today()),
        evidence_reference=milestone.evidence_reference,
        linked_certificate_id=milestone.linked_certificate_id,
        depends_on=depends,
    )


# --------------------------------------------------------------------------- #
# Forecast
# --------------------------------------------------------------------------- #


def forecast_out(
    session: Session, *, version: ForecastVersion, budget: BudgetVersion | None
) -> schemas.ForecastOut:
    """A forecast version header, with its currency and its budget resolved.

    Two fields the row does not carry: the currency's code, and the number of
    the budget the variance is measured against. A forecast presented without
    that number is a variance against an unnamed baseline.
    """
    return schemas.ForecastOut(
        id=version.id,
        version_number=version.version_number,
        status=version.status,
        as_of_date=version.as_of_date,
        budget_version_id=version.budget_version_id,
        budget_version_number=budget.version_number if budget is not None else None,
        change_reason=version.change_reason,
        source_version_id=version.source_version_id,
        currency_code=_currency_code(session, version.currency_id),
        created_at=version.created_at,
        submitted_at=version.submitted_at,
        approved_at=version.approved_at,
        rejected_at=version.rejected_at,
        rejection_reason=version.rejection_reason,
        activated_at=version.activated_at,
        superseded_at=version.superseded_at,
    )


def forecast_detail(
    session: Session, *, project: Project, version: ForecastVersion
) -> schemas.ForecastDetailOut:
    """One forecast on its own basis, cost code by cost code."""
    codes = _cost_code_labels(session, project_id=project.id)
    positions = service.forecast_position(session, project=project, version=version)
    lines = service.forecast_lines_by_cost_code(session, forecast_version_id=version.id)
    budget = session.get(BudgetVersion, version.budget_version_id)

    out_lines: list[schemas.ForecastLineOut] = []
    control = certified = remaining = eac = ZERO
    vac = ZERO
    for cost_code_id, position in sorted(
        positions.items(), key=lambda item: codes[item[0]].code if item[0] in codes else ""
    ):
        code = codes.get(cost_code_id)
        line = lines.get(cost_code_id)
        out_lines.append(
            schemas.ForecastLineOut(
                cost_code_id=cost_code_id,
                cost_code=code.code if code else "",
                cost_code_name=code.name if code else "",
                control_budget=position.control_budget,
                revised_commitment=position.revised_commitment,
                certified_to_date=position.certified_to_date,
                forecast_remaining_amount_ex_tax=position.forecast_remaining,
                estimate_at_completion=position.estimate_at_completion,
                variance_at_completion=position.variance_at_completion,
                forecast_below_commitment=position.forecast_below_commitment,
                uncovered_commitment=position.uncovered_commitment,
                note=line.note if line is not None else None,
            )
        )
        control = money(control + position.control_budget)
        certified = money(certified + position.certified_to_date)
        remaining = money(remaining + position.forecast_remaining)
        eac = money(eac + position.estimate_at_completion)
    vac = calculator.variance_at_completion(estimate_at_completion=eac, control_budget=control)

    return schemas.ForecastDetailOut(
        **forecast_out(session, version=version, budget=budget).model_dump(),
        lines=out_lines,
        total_control_budget=control,
        total_certified=certified,
        total_forecast_remaining=remaining,
        total_estimate_at_completion=eac,
        total_variance_at_completion=vac,
    )


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #


def summary_out(session: Session, *, project: Project) -> schemas.ConstructionSummaryOut:
    """The project's whole position, with the two bases in separate models."""
    cost = service.cost_control_position(session, project=project)
    payable = service.payable_position(session, project=project)
    controls = service.construction_controls(session, project=project)
    budget = service.active_budget(session, project_id=project.id)
    forecast = service.active_forecast(session, project_id=project.id)

    return schemas.ConstructionSummaryOut(
        currency_code=_currency_code(session, project.base_currency_id),
        budget_version_number=budget.version_number if budget else None,
        forecast_version_number=forecast.version_number if forecast else None,
        forecast_as_of=forecast.as_of_date if forecast else None,
        cost_control=schemas.CostControlPosition(
            original_baseline=cost.original_baseline,
            current_approved_budget=cost.current_approved_budget,
            approved_contingency=cost.approved_contingency,
            control_budget=cost.control_budget,
            original_commitment=cost.original_commitment,
            approved_variation_delta=cost.approved_variation_delta,
            revised_commitment=cost.revised_commitment,
            certified_to_date=cost.certified_to_date,
            forecast_certified_as_of=cost.forecast_certified_as_of,
            forecast_remaining=cost.forecast_remaining,
            estimate_at_completion=cost.estimate_at_completion,
            variance_at_completion=cost.variance_at_completion,
        ),
        payable=schemas.PayablePosition(
            approved_invoice_payable=payable.approved_invoice_payable,
            disputed_invoice_payable=payable.disputed_invoice_payable,
            confirmed_paid=payable.confirmed_paid,
            invoice_outstanding=payable.invoice_outstanding,
            retention_outstanding=payable.retention_outstanding,
            advance_paid=payable.advance_paid,
            advance_recovered=payable.advance_recovered,
            advance_outstanding=payable.advance_outstanding,
        ),
        controls=schemas.ConstructionControls(**controls),
    )
