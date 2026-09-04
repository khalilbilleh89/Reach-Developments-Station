"""The construction API.

Handlers validate, authorise and orchestrate. Nothing here computes a figure:
every commitment, certified total, net due, outstanding balance, estimate and
variance arrives from the service already decided, so the API and the rows agree
by construction rather than by two implementations happening to match.

No status is writable. Submitting, approving, rejecting, activating, certifying,
confirming and reversing are separate acts with separate rights and separate
preconditions, so each has its own route — a ``PATCH {"status": "certified"}``
would be somebody's signature available to whoever could reach the endpoint.

There is no DELETE anywhere in this module. A financial record leaves through a
controlled reversal, void, cancellation or supersession, each with an actor, a
timestamp and a reason, because the question a year later is not whether a row
exists but who removed it and why.

Two dependencies decide what a caller may reach. ``ConstructionProject`` gates
every route on being able to read the module at all. ``GovernedConstructionProject``
additionally requires whole-project access, and is used on every route that
returns a project-wide total — a phase-scoped reader given "the project's control
budget" with the hidden phases quietly removed would be handed a number that is
neither the project's nor their own, with nothing on screen to say so.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.errors import ValidationError
from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.construction import permissions, schemas, service
from app.modules.construction.models import BudgetVersion
from app.modules.construction.permissions import (
    ConstructionProject,
    GovernedConstructionProject,
)
from app.modules.construction.read import (
    budget_detail,
    budget_out,
    certificate_detail,
    contract_detail,
    contract_out,
    cost_code_out,
    forecast_detail,
    forecast_out,
    invoice_out,
    milestone_out,
    payment_out,
    summary_out,
    variation_detail,
    variation_out,
)

router = APIRouter(prefix="/projects/{project_id}/construction", tags=["construction"])


# --------------------------------------------------------------------------- #
# Summary and reconciliation
# --------------------------------------------------------------------------- #


@router.get("/summary", response_model=schemas.ConstructionSummaryOut)
def read_summary(
    project: GovernedConstructionProject, session: DbSession, actor: ActiveActor
) -> schemas.ConstructionSummaryOut:
    """The project's whole construction position, on both bases, each labelled."""
    del actor
    return summary_out(session, project=project)


@router.get("/reconciliation", response_model=schemas.ReconciliationOut)
def read_reconciliation(
    project: GovernedConstructionProject, session: DbSession, actor: ActiveActor
) -> schemas.ReconciliationOut:
    """Every check the rows must answer, and whether they do."""
    del actor
    checks = service.reconciliation(session, project=project)
    return schemas.ReconciliationOut(
        ok=all(check.ok for check in checks),
        checks=[
            schemas.ReconciliationCheckOut(
                key=check.key,
                label=check.label,
                ok=check.ok,
                amount=check.amount,
                expected=check.expected,
                variance=check.variance,
                detail=check.detail,
            )
            for check in checks
        ],
    )


# --------------------------------------------------------------------------- #
# Cost codes
# --------------------------------------------------------------------------- #


@router.get("/cost-codes", response_model=list[schemas.CostCodeOut])
def list_cost_codes(
    project: ConstructionProject, session: DbSession, actor: ActiveActor
) -> list[schemas.CostCodeOut]:
    del actor
    return [cost_code_out(code) for code in service.list_cost_codes(session, project=project)]


@router.post("/cost-codes", response_model=schemas.CostCodeOut, status_code=status.HTTP_201_CREATED)
def create_cost_code(
    project: ConstructionProject,
    payload: schemas.CostCodeCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.CostCodeOut:
    permissions.require_construction_preparer(actor)
    code = service.create_cost_code(
        session,
        project=project,
        actor=actor,
        code=payload.code,
        name=payload.name,
        cost_category=payload.cost_category,
        package=payload.package,
        parent_cost_code_id=payload.parent_cost_code_id,
        phase_id=payload.phase_id,
        building_id=payload.building_id,
        notes=payload.notes,
    )
    session.commit()
    return cost_code_out(code)


@router.patch("/cost-codes/{cost_code_id}", response_model=schemas.CostCodeOut)
def update_cost_code(
    project: ConstructionProject,
    cost_code_id: uuid.UUID,
    payload: schemas.CostCodeUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.CostCodeOut:
    permissions.require_construction_preparer(actor)
    code = service.update_cost_code(
        session,
        project=project,
        actor=actor,
        cost_code_id=cost_code_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    session.commit()
    return cost_code_out(code)


@router.post("/cost-codes/{cost_code_id}/retire", response_model=schemas.CostCodeOut)
def retire_cost_code(
    project: ConstructionProject,
    cost_code_id: uuid.UUID,
    payload: schemas.CostCodeRetire,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.CostCodeOut:
    """Take a code out of use. There is no delete: history keeps reading it."""
    permissions.require_construction_preparer(actor)
    code = service.retire_cost_code(
        session,
        project=project,
        actor=actor,
        cost_code_id=cost_code_id,
        reason=payload.reason,
    )
    session.commit()
    return cost_code_out(code)


# --------------------------------------------------------------------------- #
# Budget
# --------------------------------------------------------------------------- #


@router.get("/budgets", response_model=list[schemas.BudgetOut])
def list_budgets(
    project: GovernedConstructionProject, session: DbSession, actor: ActiveActor
) -> list[schemas.BudgetOut]:
    del actor
    return [
        budget_out(session, version=version)
        for version in service.list_budgets(session, project=project)
    ]


@router.post(
    "/budgets", response_model=schemas.BudgetDetailOut, status_code=status.HTTP_201_CREATED
)
def create_budget(
    project: GovernedConstructionProject,
    payload: schemas.BudgetCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.BudgetDetailOut:
    permissions.require_construction_preparer(actor)
    version = service.create_budget(
        session,
        project=project,
        actor=actor,
        effective_date=payload.effective_date,
        change_reason=payload.change_reason,
        source_version_id=payload.source_version_id,
    )
    session.commit()
    return budget_detail(session, project=project, version=version)


@router.get("/budgets/{version_id}", response_model=schemas.BudgetDetailOut)
def read_budget(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.BudgetDetailOut:
    del actor
    version = service.get_budget(session, project=project, version_id=version_id)
    return budget_detail(session, project=project, version=version)


@router.put("/budgets/{version_id}/lines", response_model=schemas.BudgetDetailOut)
def write_budget_line(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    payload: schemas.BudgetLineWrite,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.BudgetDetailOut:
    """Write one cost code's authorisation. An explicit zero is an answer."""
    permissions.require_construction_preparer(actor)
    service.set_budget_line(
        session,
        project=project,
        actor=actor,
        version_id=version_id,
        cost_code_id=payload.cost_code_id,
        approved_budget_amount=payload.approved_budget_amount,
        contingency_amount=payload.contingency_amount,
        baseline_amount=payload.baseline_amount,
        funding_source=payload.funding_source,
        notes=payload.notes,
    )
    session.commit()
    version = service.get_budget(session, project=project, version_id=version_id)
    return budget_detail(session, project=project, version=version)


@router.post("/budgets/{version_id}/submit", response_model=schemas.BudgetDetailOut)
def submit_budget(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.BudgetDetailOut:
    permissions.require_construction_preparer(actor)
    version = service.submit_budget(session, project=project, actor=actor, version_id=version_id)
    session.commit()
    return budget_detail(session, project=project, version=version)


@router.post("/budgets/{version_id}/approve", response_model=schemas.BudgetDetailOut)
def approve_budget(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.BudgetDetailOut:
    permissions.require_construction_approver(actor)
    version = service.approve_budget(session, project=project, actor=actor, version_id=version_id)
    session.commit()
    return budget_detail(session, project=project, version=version)


@router.post("/budgets/{version_id}/reject", response_model=schemas.BudgetDetailOut)
def reject_budget(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.BudgetDetailOut:
    permissions.require_construction_approver(actor)
    version = service.reject_budget(
        session, project=project, actor=actor, version_id=version_id, reason=payload.reason
    )
    session.commit()
    return budget_detail(session, project=project, version=version)


@router.post("/budgets/{version_id}/activate", response_model=schemas.BudgetDetailOut)
def activate_budget(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.BudgetDetailOut:
    """Put an approved budget in force, having re-proved it covers what is committed."""
    permissions.require_construction_activator(actor)
    version = service.activate_budget(session, project=project, actor=actor, version_id=version_id)
    session.commit()
    return budget_detail(session, project=project, version=version)


# --------------------------------------------------------------------------- #
# Contracts
# --------------------------------------------------------------------------- #


@router.get("/contracts", response_model=list[schemas.ContractOut])
def list_contracts(
    project: GovernedConstructionProject, session: DbSession, actor: ActiveActor
) -> list[schemas.ContractOut]:
    del actor
    return [
        contract_out(session, project=project, contract=contract)
        for contract in service.list_contracts(session, project=project)
    ]


@router.post(
    "/contracts", response_model=schemas.ContractDetailOut, status_code=status.HTTP_201_CREATED
)
def create_contract(
    project: GovernedConstructionProject,
    payload: schemas.ContractCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ContractDetailOut:
    permissions.require_construction_preparer(actor)
    contract = service.create_contract(
        session,
        project=project,
        actor=actor,
        contract_number=payload.contract_number,
        contract_type=payload.contract_type,
        vendor_name=payload.vendor_name,
        original_contract_value_ex_tax=payload.original_contract_value_ex_tax,
        currency_id=payload.currency_id,
        advance_entitlement_amount=payload.advance_entitlement_amount,
        retention_rate_fraction=payload.retention_rate_fraction,
        tax_rate_fraction=payload.tax_rate_fraction,
        vendor_registration_reference=payload.vendor_registration_reference,
        vendor_tax_reference=payload.vendor_tax_reference,
        vendor_contact_reference=payload.vendor_contact_reference,
        payment_terms=payload.payment_terms,
        planned_start_date=payload.planned_start_date,
        planned_completion_date=payload.planned_completion_date,
        notes=payload.notes,
    )
    session.commit()
    return contract_detail(session, project=project, contract=contract)


@router.get("/contracts/{contract_id}", response_model=schemas.ContractDetailOut)
def read_contract(
    project: GovernedConstructionProject,
    contract_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ContractDetailOut:
    """The contract file: commitment, certification and cash, each on its own basis."""
    del actor
    contract = service.get_contract(session, project=project, contract_id=contract_id)
    return contract_detail(session, project=project, contract=contract)


@router.put("/contracts/{contract_id}/lines", response_model=schemas.ContractDetailOut)
def write_contract_line(
    project: GovernedConstructionProject,
    contract_id: uuid.UUID,
    payload: schemas.ContractLineWrite,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ContractDetailOut:
    permissions.require_construction_preparer(actor)
    service.set_contract_line(
        session,
        project=project,
        contract_id=contract_id,
        sequence=payload.sequence,
        description=payload.description,
        cost_code_id=payload.cost_code_id,
        original_amount_ex_tax=payload.original_amount_ex_tax,
        notes=payload.notes,
    )
    session.commit()
    contract = service.get_contract(session, project=project, contract_id=contract_id)
    return contract_detail(session, project=project, contract=contract)


@router.post("/contracts/{contract_id}/submit", response_model=schemas.ContractDetailOut)
def submit_contract(
    project: GovernedConstructionProject,
    contract_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ContractDetailOut:
    permissions.require_construction_preparer(actor)
    contract = service.submit_contract(
        session, project=project, actor=actor, contract_id=contract_id
    )
    session.commit()
    return contract_detail(session, project=project, contract=contract)


@router.post("/contracts/{contract_id}/activate", response_model=schemas.ContractDetailOut)
def activate_contract(
    project: GovernedConstructionProject,
    contract_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ContractDetailOut:
    """Commit the company, by somebody other than whoever prepared it."""
    permissions.require_construction_activator(actor)
    contract = service.activate_contract(
        session, project=project, actor=actor, contract_id=contract_id
    )
    session.commit()
    return contract_detail(session, project=project, contract=contract)


@router.post("/contracts/{contract_id}/complete", response_model=schemas.ContractDetailOut)
def complete_contract(
    project: GovernedConstructionProject,
    contract_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ContractDetailOut:
    permissions.require_construction_activator(actor)
    contract = service.complete_contract(
        session, project=project, actor=actor, contract_id=contract_id
    )
    session.commit()
    return contract_detail(session, project=project, contract=contract)


@router.post("/contracts/{contract_id}/terminate", response_model=schemas.ContractDetailOut)
def terminate_contract(
    project: GovernedConstructionProject,
    contract_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ContractDetailOut:
    """End a contract early. Its commitment stands until a variation removes it."""
    permissions.require_construction_activator(actor)
    contract = service.terminate_contract(
        session,
        project=project,
        actor=actor,
        contract_id=contract_id,
        reason=payload.reason,
    )
    session.commit()
    return contract_detail(session, project=project, contract=contract)


@router.post("/contracts/{contract_id}/cancel", response_model=schemas.ContractDetailOut)
def cancel_contract(
    project: GovernedConstructionProject,
    contract_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ContractDetailOut:
    permissions.require_construction_preparer(actor)
    contract = service.cancel_contract(
        session,
        project=project,
        actor=actor,
        contract_id=contract_id,
        reason=payload.reason,
    )
    session.commit()
    return contract_detail(session, project=project, contract=contract)


# --------------------------------------------------------------------------- #
# Variations
# --------------------------------------------------------------------------- #


@router.get("/variations", response_model=list[schemas.VariationOut])
def list_variations(
    project: GovernedConstructionProject,
    session: DbSession,
    actor: ActiveActor,
    contract_id: uuid.UUID | None = None,
) -> list[schemas.VariationOut]:
    del actor
    return [
        variation_out(session, project=project, variation=variation)
        for variation in service.list_variations(session, project=project, contract_id=contract_id)
    ]


@router.post(
    "/contracts/{contract_id}/variations",
    response_model=schemas.VariationDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def create_variation(
    project: GovernedConstructionProject,
    contract_id: uuid.UUID,
    payload: schemas.VariationCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.VariationDetailOut:
    permissions.require_construction_preparer(actor)
    variation = service.create_variation(
        session,
        project=project,
        actor=actor,
        contract_id=contract_id,
        variation_number=payload.variation_number,
        description=payload.description,
        requested_date=payload.requested_date,
        instruction_reference=payload.instruction_reference,
        cause=payload.cause,
        time_impact_days=payload.time_impact_days,
        funding_source=payload.funding_source,
    )
    session.commit()
    return variation_detail(session, project=project, variation=variation)


@router.get("/variations/{variation_id}", response_model=schemas.VariationDetailOut)
def read_variation(
    project: GovernedConstructionProject,
    variation_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.VariationDetailOut:
    del actor
    variation = service.get_variation(session, project=project, variation_id=variation_id)
    return variation_detail(session, project=project, variation=variation)


@router.put("/variations/{variation_id}/lines", response_model=schemas.VariationDetailOut)
def write_variation_line(
    project: GovernedConstructionProject,
    variation_id: uuid.UUID,
    payload: schemas.VariationLineWrite,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.VariationDetailOut:
    """A signed line. An omission is negative, not a different record type."""
    permissions.require_construction_preparer(actor)
    service.set_variation_line(
        session,
        project=project,
        variation_id=variation_id,
        sequence=payload.sequence,
        cost_code_id=payload.cost_code_id,
        description=payload.description,
        value_delta_ex_tax=payload.value_delta_ex_tax,
    )
    session.commit()
    variation = service.get_variation(session, project=project, variation_id=variation_id)
    return variation_detail(session, project=project, variation=variation)


@router.post("/variations/{variation_id}/submit", response_model=schemas.VariationDetailOut)
def submit_variation(
    project: GovernedConstructionProject,
    variation_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.VariationDetailOut:
    permissions.require_construction_preparer(actor)
    variation = service.submit_variation(
        session, project=project, actor=actor, variation_id=variation_id
    )
    session.commit()
    return variation_detail(session, project=project, variation=variation)


@router.post("/variations/{variation_id}/approve", response_model=schemas.VariationDetailOut)
def approve_variation(
    project: GovernedConstructionProject,
    variation_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.VariationDetailOut:
    """Approve a change. Who may sign is decided on the server from the country
    pack's review amount, against the absolute value of the change."""
    variation = service.approve_variation(
        session, project=project, actor=actor, variation_id=variation_id
    )
    session.commit()
    return variation_detail(session, project=project, variation=variation)


@router.post("/variations/{variation_id}/reject", response_model=schemas.VariationDetailOut)
def reject_variation(
    project: GovernedConstructionProject,
    variation_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.VariationDetailOut:
    permissions.require_construction_checker(actor)
    variation = service.reject_variation(
        session,
        project=project,
        actor=actor,
        variation_id=variation_id,
        reason=payload.reason,
    )
    session.commit()
    return variation_detail(session, project=project, variation=variation)


@router.post("/variations/{variation_id}/withdraw", response_model=schemas.VariationDetailOut)
def withdraw_variation(
    project: GovernedConstructionProject,
    variation_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.VariationDetailOut:
    permissions.require_construction_preparer(actor)
    variation = service.withdraw_variation(
        session,
        project=project,
        actor=actor,
        variation_id=variation_id,
        reason=payload.reason,
    )
    session.commit()
    return variation_detail(session, project=project, variation=variation)


# --------------------------------------------------------------------------- #
# Certificates
# --------------------------------------------------------------------------- #


@router.get("/certificates", response_model=list[schemas.CertificateOut])
def list_certificates(
    project: GovernedConstructionProject,
    session: DbSession,
    actor: ActiveActor,
    contract_id: uuid.UUID | None = None,
) -> list[schemas.CertificateOut]:
    del actor
    return [
        certificate_detail(session, project=project, certificate=certificate, with_lines=False)
        for certificate in service.list_certificates(
            session, project=project, contract_id=contract_id
        )
    ]


@router.post(
    "/contracts/{contract_id}/certificates",
    response_model=schemas.CertificateDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def create_certificate(
    project: GovernedConstructionProject,
    contract_id: uuid.UUID,
    payload: schemas.CertificateCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.CertificateDetailOut:
    permissions.require_construction_technical(actor)
    certificate = service.create_certificate(
        session,
        project=project,
        actor=actor,
        contract_id=contract_id,
        certificate_number=payload.certificate_number,
        period_start=payload.period_start,
        period_end=payload.period_end,
        certificate_date=payload.certificate_date,
        retention_release_amount=payload.retention_release_amount,
        advance_recovery_amount=payload.advance_recovery_amount,
        other_deductions_amount=payload.other_deductions_amount,
        tax_amount=payload.tax_amount,
        certifier_name=payload.certifier_name,
        evidence_reference=payload.evidence_reference,
        notes=payload.notes,
    )
    session.commit()
    return certificate_detail(session, project=project, certificate=certificate)


@router.get("/certificates/{certificate_id}", response_model=schemas.CertificateDetailOut)
def read_certificate(
    project: GovernedConstructionProject,
    certificate_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.CertificateDetailOut:
    """The certificate file, including the waterfall in the one order it has."""
    del actor
    certificate = service.get_certificate(session, project=project, certificate_id=certificate_id)
    return certificate_detail(session, project=project, certificate=certificate)


@router.put("/certificates/{certificate_id}/lines", response_model=schemas.CertificateDetailOut)
def write_certificate_line(
    project: GovernedConstructionProject,
    certificate_id: uuid.UUID,
    payload: schemas.CertificateLineWrite,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.CertificateDetailOut:
    permissions.require_construction_technical(actor)
    service.set_certificate_line(
        session,
        project=project,
        certificate_id=certificate_id,
        cost_code_id=payload.cost_code_id,
        current_work_value_ex_tax=payload.current_work_value_ex_tax,
        notes=payload.notes,
    )
    session.commit()
    certificate = service.get_certificate(session, project=project, certificate_id=certificate_id)
    return certificate_detail(session, project=project, certificate=certificate)


@router.post("/certificates/{certificate_id}/submit", response_model=schemas.CertificateDetailOut)
def submit_certificate(
    project: GovernedConstructionProject,
    certificate_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.CertificateDetailOut:
    permissions.require_construction_technical(actor)
    certificate = service.submit_certificate(
        session, project=project, actor=actor, certificate_id=certificate_id
    )
    session.commit()
    return certificate_detail(session, project=project, certificate=certificate)


@router.post("/certificates/{certificate_id}/certify", response_model=schemas.CertificateDetailOut)
def certify_certificate(
    project: GovernedConstructionProject,
    certificate_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.CertificateDetailOut:
    """The one act in this module that becomes cost."""
    permissions.require_construction_certifier(actor)
    certificate = service.certify_certificate(
        session, project=project, actor=actor, certificate_id=certificate_id
    )
    session.commit()
    return certificate_detail(session, project=project, certificate=certificate)


@router.post("/certificates/{certificate_id}/reject", response_model=schemas.CertificateDetailOut)
def reject_certificate(
    project: GovernedConstructionProject,
    certificate_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.CertificateDetailOut:
    permissions.require_construction_certifier(actor)
    certificate = service.reject_certificate(
        session,
        project=project,
        actor=actor,
        certificate_id=certificate_id,
        reason=payload.reason,
    )
    session.commit()
    return certificate_detail(session, project=project, certificate=certificate)


@router.post("/certificates/{certificate_id}/reverse", response_model=schemas.CertificateDetailOut)
def reverse_certificate(
    project: GovernedConstructionProject,
    certificate_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.CertificateDetailOut:
    """Refused while an invoice claims against it or a certified milestone
    evidences it: a partial unwind is worse than a refusal."""
    permissions.require_construction_certifier(actor)
    certificate = service.reverse_certificate(
        session,
        project=project,
        actor=actor,
        certificate_id=certificate_id,
        reason=payload.reason,
    )
    session.commit()
    return certificate_detail(session, project=project, certificate=certificate)


# --------------------------------------------------------------------------- #
# Invoices
# --------------------------------------------------------------------------- #


@router.get("/invoices", response_model=list[schemas.InvoiceOut])
def list_invoices(
    project: GovernedConstructionProject,
    session: DbSession,
    actor: ActiveActor,
    contract_id: uuid.UUID | None = None,
) -> list[schemas.InvoiceOut]:
    del actor
    return [
        invoice_out(session, project=project, invoice=invoice)
        for invoice in service.list_invoices(session, project=project, contract_id=contract_id)
    ]


@router.post(
    "/contracts/{contract_id}/invoices",
    response_model=schemas.InvoiceOut,
    status_code=status.HTTP_201_CREATED,
)
def record_invoice(
    project: GovernedConstructionProject,
    contract_id: uuid.UUID,
    payload: schemas.InvoiceRecord,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.InvoiceOut:
    """Recorded is a document. It is not yet a liability."""
    permissions.require_construction_finance(actor)
    invoice = service.record_invoice(
        session,
        project=project,
        actor=actor,
        contract_id=contract_id,
        invoice_number=payload.invoice_number,
        invoice_type=payload.invoice_type,
        invoice_date=payload.invoice_date,
        amount_ex_tax=payload.amount_ex_tax,
        tax_amount=payload.tax_amount,
        certificate_id=payload.certificate_id,
        due_date=payload.due_date,
        accounting_reference=payload.accounting_reference,
        notes=payload.notes,
    )
    session.commit()
    return invoice_out(session, project=project, invoice=invoice)


@router.get("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def read_invoice(
    project: GovernedConstructionProject,
    invoice_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.InvoiceOut:
    del actor
    invoice = service.get_invoice(session, project=project, invoice_id=invoice_id)
    return invoice_out(session, project=project, invoice=invoice)


@router.post("/invoices/{invoice_id}/approve", response_model=schemas.InvoiceOut)
def approve_invoice(
    project: GovernedConstructionProject,
    invoice_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.InvoiceOut:
    """Approving makes it a liability, so a second person does it."""
    permissions.require_construction_checker(actor)
    invoice = service.approve_invoice(session, project=project, actor=actor, invoice_id=invoice_id)
    session.commit()
    return invoice_out(session, project=project, invoice=invoice)


@router.post("/invoices/{invoice_id}/dispute", response_model=schemas.InvoiceOut)
def dispute_invoice(
    project: GovernedConstructionProject,
    invoice_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.InvoiceOut:
    """A dispute blocks payment. It does not reduce what is owed."""
    permissions.require_construction_finance(actor)
    invoice = service.dispute_invoice(
        session, project=project, actor=actor, invoice_id=invoice_id, reason=payload.reason
    )
    session.commit()
    return invoice_out(session, project=project, invoice=invoice)


@router.post("/invoices/{invoice_id}/resolve", response_model=schemas.InvoiceOut)
def resolve_invoice_dispute(
    project: GovernedConstructionProject,
    invoice_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.InvoiceOut:
    permissions.require_construction_finance(actor)
    invoice = service.resolve_invoice_dispute(
        session, project=project, actor=actor, invoice_id=invoice_id, reason=payload.reason
    )
    session.commit()
    return invoice_out(session, project=project, invoice=invoice)


@router.post("/invoices/{invoice_id}/void", response_model=schemas.InvoiceOut)
def void_invoice(
    project: GovernedConstructionProject,
    invoice_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.InvoiceOut:
    permissions.require_construction_finance(actor)
    invoice = service.void_invoice(
        session, project=project, actor=actor, invoice_id=invoice_id, reason=payload.reason
    )
    session.commit()
    return invoice_out(session, project=project, invoice=invoice)


# --------------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------------- #


@router.get("/payments", response_model=list[schemas.PaymentOut])
def list_payments(
    project: GovernedConstructionProject,
    session: DbSession,
    actor: ActiveActor,
    contract_id: uuid.UUID | None = None,
) -> list[schemas.PaymentOut]:
    del actor
    return [
        payment_out(session, project=project, payment=payment)
        for payment in service.list_payments(session, project=project, contract_id=contract_id)
    ]


@router.post(
    "/contracts/{contract_id}/payments",
    response_model=schemas.PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
def record_payment(
    project: GovernedConstructionProject,
    contract_id: uuid.UUID,
    payload: schemas.PaymentRecord,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.PaymentOut:
    """Recorded is Finance preparing a disbursement. It is not cash."""
    permissions.require_construction_finance(actor)
    payment = service.record_payment(
        session,
        project=project,
        actor=actor,
        contract_id=contract_id,
        payment_reference=payload.payment_reference,
        payment_date=payload.payment_date,
        amount=payload.amount,
        currency_id=payload.currency_id,
        value_date=payload.value_date,
        bank_reference=payload.bank_reference,
        proof_reference=payload.proof_reference,
        notes=payload.notes,
    )
    session.commit()
    return payment_out(session, project=project, payment=payment)


@router.get("/payments/{payment_id}", response_model=schemas.PaymentOut)
def read_payment(
    project: GovernedConstructionProject,
    payment_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.PaymentOut:
    del actor
    payment = service.get_payment(session, project=project, payment_id=payment_id)
    return payment_out(session, project=project, payment=payment)


@router.put("/payments/{payment_id}/allocations", response_model=schemas.PaymentOut)
def allocate_payment(
    project: GovernedConstructionProject,
    payment_id: uuid.UUID,
    payload: schemas.AllocationWrite,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.PaymentOut:
    permissions.require_construction_finance(actor)
    service.allocate_payment(
        session,
        project=project,
        actor=actor,
        payment_id=payment_id,
        invoice_id=payload.invoice_id,
        amount=payload.amount,
    )
    session.commit()
    payment = service.get_payment(session, project=project, payment_id=payment_id)
    return payment_out(session, project=project, payment=payment)


@router.post("/payments/{payment_id}/confirm", response_model=schemas.PaymentOut)
def confirm_payment(
    project: GovernedConstructionProject,
    payment_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.PaymentOut:
    """Cash leaves here, by somebody other than whoever prepared it, and only
    when the allocations equal the payment exactly."""
    permissions.require_construction_checker(actor)
    payment = service.confirm_payment(session, project=project, actor=actor, payment_id=payment_id)
    session.commit()
    return payment_out(session, project=project, payment=payment)


@router.post("/payments/{payment_id}/reverse", response_model=schemas.PaymentOut)
def reverse_payment(
    project: GovernedConstructionProject,
    payment_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.PaymentOut:
    permissions.require_construction_checker(actor)
    payment = service.reverse_payment(
        session, project=project, actor=actor, payment_id=payment_id, reason=payload.reason
    )
    session.commit()
    return payment_out(session, project=project, payment=payment)


# --------------------------------------------------------------------------- #
# Milestones
# --------------------------------------------------------------------------- #


@router.get("/milestones", response_model=list[schemas.MilestoneOut])
def list_milestones(
    project: ConstructionProject, session: DbSession, actor: ActiveActor
) -> list[schemas.MilestoneOut]:
    """The register, narrowed in SQL to what this caller may see.

    A phase-scoped engineer is given the milestones of the phases they hold, not
    the project's list with the rest hidden by the browser.
    """
    return [
        milestone_out(session, project_id=project.id, milestone=milestone, actor=actor)
        for milestone in service.list_milestones(session, project=project, actor=actor)
    ]


@router.post(
    "/milestones", response_model=schemas.MilestoneOut, status_code=status.HTTP_201_CREATED
)
def create_milestone(
    project: ConstructionProject,
    payload: schemas.MilestoneCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.MilestoneOut:
    permissions.require_construction_technical(actor)
    milestone = service.create_milestone(
        session,
        project=project,
        actor=actor,
        code=payload.code,
        name=payload.name,
        milestone_type=payload.milestone_type,
        phase_id=payload.phase_id,
        building_id=payload.building_id,
        planned_date=payload.planned_date,
        forecast_date=payload.forecast_date,
        notes=payload.notes,
    )
    session.commit()
    return milestone_out(session, project_id=project.id, milestone=milestone, actor=actor)


@router.get("/milestones/{milestone_id}", response_model=schemas.MilestoneOut)
def read_milestone(
    project: ConstructionProject,
    milestone_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.MilestoneOut:
    milestone = service.get_milestone(
        session, project=project, milestone_id=milestone_id, actor=actor
    )
    return milestone_out(session, project_id=project.id, milestone=milestone, actor=actor)


@router.patch("/milestones/{milestone_id}", response_model=schemas.MilestoneOut)
def update_milestone(
    project: ConstructionProject,
    milestone_id: uuid.UUID,
    payload: schemas.MilestoneUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.MilestoneOut:
    """The code is not in the request model: a payment plan points at it."""
    permissions.require_construction_technical(actor)
    milestone = service.update_milestone(
        session,
        project=project,
        actor=actor,
        milestone_id=milestone_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    session.commit()
    return milestone_out(session, project_id=project.id, milestone=milestone, actor=actor)


@router.post("/milestones/{milestone_id}/achieve", response_model=schemas.MilestoneOut)
def achieve_milestone(
    project: ConstructionProject,
    milestone_id: uuid.UUID,
    payload: schemas.MilestoneAchieve,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.MilestoneOut:
    """Site says the work is done. No buyer's money moves because of this."""
    permissions.require_construction_technical(actor)
    milestone = service.achieve_milestone(
        session,
        project=project,
        actor=actor,
        milestone_id=milestone_id,
        achieved_date=payload.achieved_date,
        evidence_reference=payload.evidence_reference,
    )
    session.commit()
    return milestone_out(session, project_id=project.id, milestone=milestone, actor=actor)


@router.post("/milestones/{milestone_id}/certify", response_model=schemas.MilestoneCertifiedOut)
def certify_milestone(
    project: ConstructionProject,
    milestone_id: uuid.UUID,
    payload: schemas.MilestoneCertify,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.MilestoneCertifiedOut:
    """Formal certification, and the buyer instalments it makes due.

    One transaction covers both. There is no state in which the milestone is
    certified and a schedule still waits for it, and none in which an instalment
    is due for a milestone that was not certified.
    """
    permissions.require_construction_certifier(actor)
    milestone, result = service.certify_milestone(
        session,
        project=project,
        actor=actor,
        milestone_id=milestone_id,
        certified_date=payload.certified_date,
        evidence_reference=payload.evidence_reference,
        linked_certificate_id=payload.linked_certificate_id,
    )
    session.commit()
    return schemas.MilestoneCertifiedOut(
        milestone=milestone_out(session, project_id=project.id, milestone=milestone, actor=actor),
        triggered_installment_count=len(result.triggered_installment_ids),
        triggered_plan_count=len(result.plan_ids),
    )


@router.post("/milestones/{milestone_id}/cancel", response_model=schemas.MilestoneOut)
def cancel_milestone(
    project: ConstructionProject,
    milestone_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.MilestoneOut:
    """Refused while an active payment plan still waits on this code."""
    permissions.require_construction_technical(actor)
    milestone = service.cancel_milestone(
        session,
        project=project,
        actor=actor,
        milestone_id=milestone_id,
        reason=payload.reason,
    )
    session.commit()
    return milestone_out(session, project_id=project.id, milestone=milestone, actor=actor)


@router.put("/milestones/{milestone_id}/dependencies", response_model=schemas.MilestoneOut)
def add_dependency(
    project: ConstructionProject,
    milestone_id: uuid.UUID,
    payload: schemas.DependencyWrite,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.MilestoneOut:
    permissions.require_construction_technical(actor)
    service.add_milestone_dependency(
        session,
        project=project,
        actor=actor,
        milestone_id=milestone_id,
        depends_on_milestone_id=payload.depends_on_milestone_id,
    )
    session.commit()
    milestone = service.get_milestone(
        session, project=project, milestone_id=milestone_id, actor=actor
    )
    return milestone_out(session, project_id=project.id, milestone=milestone, actor=actor)


@router.get("/milestone-trigger-options", response_model=list[schemas.MilestoneTriggerOption])
def read_milestone_trigger_options(
    project_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> list[schemas.MilestoneTriggerOption]:
    """The narrow endpoint a payment plan builder may call.

    Deliberately **not** gated on reading construction. Sales Operations writes
    payment plans and cannot read this module, so this route is gated on payment
    plan authorship instead and returns a code, a name, a scope and dates —
    never a budget, a contract value, an estimate or any cost.
    """
    from app.modules.payment_plans import permissions as plan_permissions
    from app.modules.projects.permissions import require_project_access

    project = require_project_access(session, project_id=project_id, actor=actor)
    plan_permissions.require_plan_reader(actor)
    return [
        schemas.MilestoneTriggerOption(
            code=milestone.code,
            name=milestone.name,
            scope_label=service.milestone_scope_label(session, milestone=milestone),
            planned_date=milestone.planned_date,
            forecast_date=milestone.forecast_date,
            is_certified=milestone.certified_date is not None,
            certified_date=milestone.certified_date,
        )
        for milestone in service.milestone_trigger_options(session, project=project, actor=actor)
    ]


# --------------------------------------------------------------------------- #
# Forecast
# --------------------------------------------------------------------------- #


@router.get("/forecasts", response_model=list[schemas.ForecastOut])
def list_forecasts(
    project: GovernedConstructionProject, session: DbSession, actor: ActiveActor
) -> list[schemas.ForecastOut]:
    del actor
    return [
        forecast_out(
            session,
            version=version,
            budget=session.get(BudgetVersion, version.budget_version_id),
        )
        for version in service.list_forecasts(session, project=project)
    ]


@router.post(
    "/forecasts", response_model=schemas.ForecastDetailOut, status_code=status.HTTP_201_CREATED
)
def create_forecast(
    project: GovernedConstructionProject,
    payload: schemas.ForecastCreate,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastDetailOut:
    permissions.require_construction_finance(actor)
    version = service.create_forecast(
        session,
        project=project,
        actor=actor,
        as_of_date=payload.as_of_date,
        change_reason=payload.change_reason,
        budget_version_id=payload.budget_version_id,
        source_version_id=payload.source_version_id,
    )
    session.commit()
    return forecast_detail(session, project=project, version=version)


@router.get("/forecasts/{version_id}", response_model=schemas.ForecastDetailOut)
def read_forecast(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastDetailOut:
    """A superseded forecast reads as what it said, on its own cutoff."""
    del actor
    version = service.get_forecast(session, project=project, version_id=version_id)
    return forecast_detail(session, project=project, version=version)


@router.put("/forecasts/{version_id}/lines", response_model=schemas.ForecastDetailOut)
def write_forecast_line(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    payload: schemas.ForecastLineWrite,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastDetailOut:
    """Finance's explicit judgement. Never budget minus certified."""
    permissions.require_construction_finance(actor)
    service.set_forecast_line(
        session,
        project=project,
        version_id=version_id,
        cost_code_id=payload.cost_code_id,
        forecast_remaining_amount_ex_tax=payload.forecast_remaining_amount_ex_tax,
        note=payload.note,
    )
    session.commit()
    version = service.get_forecast(session, project=project, version_id=version_id)
    return forecast_detail(session, project=project, version=version)


@router.post("/forecasts/{version_id}/submit", response_model=schemas.ForecastDetailOut)
def submit_forecast(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastDetailOut:
    permissions.require_construction_finance(actor)
    version = service.submit_forecast(session, project=project, actor=actor, version_id=version_id)
    session.commit()
    return forecast_detail(session, project=project, version=version)


@router.post("/forecasts/{version_id}/approve", response_model=schemas.ForecastDetailOut)
def approve_forecast(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastDetailOut:
    permissions.require_construction_approver(actor)
    version = service.approve_forecast(session, project=project, actor=actor, version_id=version_id)
    session.commit()
    return forecast_detail(session, project=project, version=version)


@router.post("/forecasts/{version_id}/reject", response_model=schemas.ForecastDetailOut)
def reject_forecast(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastDetailOut:
    permissions.require_construction_approver(actor)
    version = service.reject_forecast(
        session, project=project, actor=actor, version_id=version_id, reason=payload.reason
    )
    session.commit()
    return forecast_detail(session, project=project, version=version)


@router.post("/forecasts/{version_id}/activate", response_model=schemas.ForecastDetailOut)
def activate_forecast(
    project: GovernedConstructionProject,
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.ForecastDetailOut:
    permissions.require_construction_activator(actor)
    version = service.activate_forecast(
        session, project=project, actor=actor, version_id=version_id
    )
    session.commit()
    return forecast_detail(session, project=project, version=version)


# --------------------------------------------------------------------------- #
# Delivery
# --------------------------------------------------------------------------- #


@router.post("/delivery/start", response_model=schemas.DeliveryResultOut)
def mark_construction_started(
    project: ConstructionProject,
    payload: schemas.DeliveryAction,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.DeliveryResultOut:
    """Move units into construction, all of them or none.

    Written through inventory's public contract. Construction decides which
    value follows from the build; inventory owns the column and the event.
    """
    permissions.require_construction_technical(actor)
    result = service.apply_delivery(
        session,
        project=project,
        actor=actor,
        to_status="under_construction",
        unit_id=payload.unit_id,
        building_id=payload.building_id,
        phase_id=payload.phase_id,
        effective_date=payload.effective_date,
        reason=payload.reason,
    )
    session.commit()
    return result


@router.post("/delivery/ready", response_model=schemas.DeliveryResultOut)
def mark_construction_ready(
    project: ConstructionProject,
    payload: schemas.DeliveryAction,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.DeliveryResultOut:
    permissions.require_construction_technical(actor)
    result = service.apply_delivery(
        session,
        project=project,
        actor=actor,
        to_status="ready",
        unit_id=payload.unit_id,
        building_id=payload.building_id,
        phase_id=payload.phase_id,
        effective_date=payload.effective_date,
        reason=payload.reason,
    )
    session.commit()
    return result


@router.post("/delivery/revoke-ready", response_model=schemas.DeliveryResultOut)
def revoke_construction_readiness(
    project: ConstructionProject,
    payload: schemas.DeliveryAction,
    session: DbSession,
    actor: ActiveActor,
) -> schemas.DeliveryResultOut:
    """Pull a unit back from ready, with a reason, before handover has moved on.

    Refused once sales owns the unit's delivery state: handover is not
    construction's to undo.
    """
    permissions.require_construction_technical(actor)
    if not (payload.reason or "").strip():
        raise ValidationError("Revoking readiness needs a reason on the record.")
    result = service.apply_delivery(
        session,
        project=project,
        actor=actor,
        to_status="under_construction",
        unit_id=payload.unit_id,
        building_id=payload.building_id,
        phase_id=payload.phase_id,
        effective_date=payload.effective_date,
        reason=payload.reason,
        revoking=True,
    )
    session.commit()
    return result
