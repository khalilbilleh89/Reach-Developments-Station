"""Construction control: the rules that decide what may be committed and paid.

Every guard in this module has the same shape. Read the committed state under a
lock, prove the invariant against what is actually there, then write — never
read, decide, and write while another transaction is deciding the same thing
from the same stale read. The lock order is the project's, taken first and held
through the commit, because that is the order the rest of the platform already
takes and a path that took a child row first would deadlock against one going
the other way.

Five invariants are worth naming, because everything else is bookkeeping.

**A commitment fits inside its authorisation.** Activating a contract or
approving a variation proves, per cost code and under lock, that the revised
standing commitment does not exceed the approved budget plus its contingency.
Two Finance users approving two variations against the same headroom is the
race this exists to lose exactly once.

**Certified work fits inside its commitment.** Certification proves, per cost
code and under lock, that everything certified so far plus this certificate does
not exceed what the contract and its approved variations commit.

**An invoice fits inside what authorised it.** A progress claim may not exceed
the uninvoiced net due of the certificate it names; an advance may not exceed
the contract's entitlement.

**Cash out is exact and dual-controlled.** A payment confirms only when its
allocations equal its amount to the cent, only against invoices that are not
disputed, only up to what each still owes, and only by somebody other than the
person who recorded it.

**Certification of a milestone is atomic with the buyer instalments it triggers.**
Payment plans is called through its own public contract inside the same
transaction, so there is no state in which a milestone is certified and a
schedule still waits for it.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.construction import calculator, permissions
from app.modules.construction.calculator import ZERO, money
from app.modules.construction.models import (
    BUDGET_ACTIVE,
    BUDGET_APPROVED,
    BUDGET_DRAFT,
    BUDGET_FROZEN,
    BUDGET_OPEN,
    BUDGET_REJECTED,
    BUDGET_SUBMITTED,
    BUDGET_SUPERSEDED,
    CERTIFICATE_CERTIFIED,
    CERTIFICATE_DRAFT,
    CERTIFICATE_REJECTED,
    CERTIFICATE_REVERSED,
    CERTIFICATE_SUBMITTED,
    CONTRACT_ACTIVE,
    CONTRACT_CANCELLED,
    CONTRACT_COMMITTING,
    CONTRACT_COMPLETED,
    CONTRACT_DRAFT,
    CONTRACT_EDITABLE,
    CONTRACT_SUBMITTED,
    CONTRACT_TERMINATED,
    ENTITY_BUDGET,
    ENTITY_CERTIFICATE,
    ENTITY_CONTRACT,
    ENTITY_COST_CODE,
    ENTITY_INVOICE,
    ENTITY_PAYMENT,
    ENTITY_VARIATION,
    INVOICE_ADVANCE,
    INVOICE_APPROVED,
    INVOICE_DISPUTED,
    INVOICE_NEEDS_CERTIFICATE,
    INVOICE_RECORDED,
    INVOICE_STANDING,
    INVOICE_VOIDED,
    MILESTONE_CERTIFIED,
    PAYMENT_CONFIRMED,
    PAYMENT_RECORDED,
    PAYMENT_REVERSED,
    VARIATION_APPROVED,
    VARIATION_DRAFT,
    VARIATION_REJECTED,
    VARIATION_SUBMITTED,
    VARIATION_WITHDRAWN,
    BudgetLine,
    BudgetVersion,
    Certificate,
    CertificateLine,
    Contract,
    ContractLine,
    CostCode,
    Invoice,
    Milestone,
    Payment,
    PaymentAllocation,
    Variation,
    VariationLine,
)
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.settings.models import CountryApprovalThreshold

# --------------------------------------------------------------------------- #
# Shared plumbing
# --------------------------------------------------------------------------- #

_COST_CODE_FIELDS = (
    "code",
    "name",
    "cost_category",
    "package",
    "parent_cost_code_id",
    "phase_id",
    "building_id",
    "notes",
    "is_active",
)

_BUDGET_FIELDS = ("status", "effective_date", "change_reason")

_INVOICE_FIELDS = (
    "invoice_number",
    "invoice_type",
    "invoice_date",
    "due_date",
    "amount_ex_tax",
    "tax_amount",
    "status",
)

_PAYMENT_FIELDS = (
    "payment_reference",
    "payment_date",
    "value_date",
    "amount",
    "status",
)

_CERTIFICATE_FIELDS = (
    "certificate_number",
    "period_start",
    "period_end",
    "certificate_date",
    "retention_release_amount",
    "advance_recovery_amount",
    "other_deductions_amount",
    "tax_amount",
    "status",
)

_VARIATION_FIELDS = (
    "variation_number",
    "description",
    "status",
    "time_impact_days",
    "funding_source",
)

_CONTRACT_FIELDS = (
    "contract_number",
    "contract_type",
    "vendor_name",
    "original_contract_value_ex_tax",
    "advance_entitlement_amount",
    "retention_rate_fraction",
    "status",
)


def _flush(session: Session) -> None:
    """Push pending changes so the database's own constraints answer first."""
    session.flush()


def _snapshot(row: object, fields: tuple[str, ...]) -> dict[str, Any]:
    """The audit trail's before/after picture of a row, as plain values."""
    out: dict[str, Any] = {}
    for field in fields:
        value = getattr(row, field, None)
        if isinstance(value, uuid.UUID | Decimal):
            out[field] = str(value)
        elif isinstance(value, date | datetime):
            out[field] = value.isoformat()
        else:
            out[field] = value
    return out


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Cost codes
# --------------------------------------------------------------------------- #


def list_cost_codes(
    session: Session, *, project: Project, include_retired: bool = True
) -> list[CostCode]:
    """The project's construction breakdown, in code order."""
    statement = select(CostCode).where(CostCode.project_id == project.id)
    if not include_retired:
        statement = statement.where(CostCode.is_active.is_(True))
    return list(session.scalars(statement.order_by(CostCode.code)))


def get_cost_code(session: Session, *, project: Project, cost_code_id: uuid.UUID) -> CostCode:
    """Load one cost code of this project, or refuse as if it did not exist.

    Scoped by project in the query rather than fetched by identifier and checked
    afterwards: the second shape is the one that lets another project's
    identifier through a path somebody forgot to guard.
    """
    code = session.scalars(
        select(CostCode).where(CostCode.id == cost_code_id, CostCode.project_id == project.id)
    ).first()
    if code is None:
        raise permissions.cost_code_not_found()
    return code


def _require_no_cycle(
    session: Session, *, project_id: uuid.UUID, code_id: uuid.UUID | None, parent_id: uuid.UUID
) -> None:
    """Refuse a parent that would make the breakdown eat its own tail.

    Ancestry is a property of a chain of rows, so no check constraint can hold
    it — the database can refuse a code that is its own parent and nothing more.
    Walked from the proposed parent upwards; a chain that reaches the code being
    edited is a cycle.
    """
    seen: set[uuid.UUID] = set()
    current: uuid.UUID | None = parent_id
    while current is not None:
        if current == code_id:
            raise ValidationError("A cost code cannot be its own ancestor.")
        if current in seen:
            raise ValidationError("The cost code hierarchy already contains a cycle.")
        seen.add(current)
        current = session.scalars(
            select(CostCode.parent_cost_code_id).where(
                CostCode.id == current, CostCode.project_id == project_id
            )
        ).first()


def create_cost_code(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    code: str,
    name: str,
    cost_category: str,
    package: str | None = None,
    parent_cost_code_id: uuid.UUID | None = None,
    phase_id: uuid.UUID | None = None,
    building_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> CostCode:
    """Add one line to the project's construction breakdown."""
    lock_project(session, project.id)
    if parent_cost_code_id is not None:
        parent = get_cost_code(session, project=project, cost_code_id=parent_cost_code_id)
        _require_no_cycle(session, project_id=project.id, code_id=None, parent_id=parent.id)
    row = CostCode(
        project_id=project.id,
        code=code.strip(),
        name=name.strip(),
        cost_category=cost_category,
        package=(package or "").strip() or None,
        parent_cost_code_id=parent_cost_code_id,
        phase_id=phase_id,
        building_id=building_id,
        notes=(notes or "").strip() or None,
        is_active=True,
        created_by_user_id=actor.user_id,
    )
    session.add(row)
    _flush(session)
    record_event(
        session,
        action="construction.cost_code_created",
        entity_type=ENTITY_COST_CODE,
        entity_id=row.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(row, _COST_CODE_FIELDS),
    )
    return row


def update_cost_code(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    cost_code_id: uuid.UUID,
    changes: dict[str, Any],
) -> CostCode:
    """Amend a cost code's descriptive fields.

    ``code`` and ``cost_category`` are not amendable once anything governed
    references the row: the code is how a budget line, a contract line and a
    forecast line all name the same thing, and the category is what decides
    whether unit economics may read this money as hard cost.
    """
    lock_project(session, project.id)
    row = get_cost_code(session, project=project, cost_code_id=cost_code_id)
    before = _snapshot(row, _COST_CODE_FIELDS)

    if "parent_cost_code_id" in changes and changes["parent_cost_code_id"] is not None:
        parent = get_cost_code(
            session, project=project, cost_code_id=changes["parent_cost_code_id"]
        )
        _require_no_cycle(session, project_id=project.id, code_id=row.id, parent_id=parent.id)

    governed = _cost_code_is_referenced(session, project_id=project.id, cost_code_id=row.id)
    for field in ("code", "cost_category"):
        if field in changes and changes[field] != getattr(row, field) and governed:
            raise ConflictError(
                "This cost code is already used by a budget, contract, certificate or "
                "forecast. Its code and category are how those records name the same "
                "line, so they cannot be changed once they are in use."
            )

    for field, value in changes.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(row, field, value)
    _flush(session)
    record_event(
        session,
        action="construction.cost_code_updated",
        entity_type=ENTITY_COST_CODE,
        entity_id=row.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(row, _COST_CODE_FIELDS),
    )
    return row


def _cost_code_is_referenced(
    session: Session, *, project_id: uuid.UUID, cost_code_id: uuid.UUID
) -> bool:
    """Whether any governed financial row names this cost code."""
    for model in (BudgetLine, ContractLine, VariationLine, CertificateLine):
        found = session.scalars(
            select(model.id)
            .where(model.cost_code_id == cost_code_id, model.project_id == project_id)
            .limit(1)
        ).first()
        if found is not None:
            return True
    return False


def retire_cost_code(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    cost_code_id: uuid.UUID,
    reason: str,
) -> CostCode:
    """Take a cost code out of use without taking it out of history.

    There is no delete. A retired code stops being offered to new budgets and
    contracts and keeps reading everywhere it was already used, because the
    alternative is a certified certificate line pointing at nothing.
    """
    lock_project(session, project.id)
    row = get_cost_code(session, project=project, cost_code_id=cost_code_id)
    if not row.is_active:
        return row
    children = session.scalars(
        select(CostCode.id)
        .where(
            CostCode.parent_cost_code_id == row.id,
            CostCode.project_id == project.id,
            CostCode.is_active.is_(True),
        )
        .limit(1)
    ).first()
    if children is not None:
        raise ConflictError(
            "This cost code still has active children. Retire them first, so the "
            "breakdown never has a live line hanging under a retired one."
        )
    before = _snapshot(row, _COST_CODE_FIELDS)
    row.is_active = False
    _flush(session)
    record_event(
        session,
        action="construction.cost_code_retired",
        entity_type=ENTITY_COST_CODE,
        entity_id=row.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(row, _COST_CODE_FIELDS),
    )
    return row


# --------------------------------------------------------------------------- #
# Standing positions, by cost code
# --------------------------------------------------------------------------- #


def committed_by_cost_code(
    session: Session, *, project_id: uuid.UUID, exclude_contract_id: uuid.UUID | None = None
) -> dict[uuid.UUID, Decimal]:
    """What each cost code currently has committed, from the rows themselves.

    Original contract lines for every contract that is or has been a commitment,
    plus every approved variation line against those contracts. A terminated
    contract is included on purpose: the money was committed, and it leaves
    through a signed negative variation rather than through a status change.

    ``exclude_contract_id`` lets a caller ask "what is committed apart from this
    one", which is what activating a contract needs in order to test its own
    lines against the remaining headroom.
    """
    committed: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)

    line_totals = session.execute(
        select(ContractLine.cost_code_id, func.sum(ContractLine.original_amount_ex_tax))
        .join(Contract, Contract.id == ContractLine.contract_id)
        .where(
            ContractLine.project_id == project_id,
            Contract.status.in_(tuple(CONTRACT_COMMITTING)),
            *((Contract.id != exclude_contract_id,) if exclude_contract_id is not None else ()),
        )
        .group_by(ContractLine.cost_code_id)
    ).all()
    for cost_code_id, amount in line_totals:
        committed[cost_code_id] = money(amount or ZERO)

    variation_totals = session.execute(
        select(VariationLine.cost_code_id, func.sum(VariationLine.value_delta_ex_tax))
        .join(Variation, Variation.id == VariationLine.variation_id)
        .join(Contract, Contract.id == Variation.contract_id)
        .where(
            VariationLine.project_id == project_id,
            Variation.status == VARIATION_APPROVED,
            Contract.status.in_(tuple(CONTRACT_COMMITTING)),
            *((Contract.id != exclude_contract_id,) if exclude_contract_id is not None else ()),
        )
        .group_by(VariationLine.cost_code_id)
    ).all()
    for cost_code_id, amount in variation_totals:
        committed[cost_code_id] = money(committed[cost_code_id] + (amount or ZERO))

    return dict(committed)


def certified_by_cost_code(
    session: Session,
    *,
    project_id: uuid.UUID,
    contract_id: uuid.UUID | None = None,
    as_of: date | None = None,
    exclude_certificate_id: uuid.UUID | None = None,
) -> dict[uuid.UUID, Decimal]:
    """What each cost code has certified, optionally as at a historical cutoff.

    ``as_of`` is what makes a superseded forecast reproducible: its estimate was
    built on the work certified by its own cutoff, and re-deriving it from
    today's certificates a year later would answer a different question from the
    one Finance approved.
    """
    conditions = [
        CertificateLine.project_id == project_id,
        Certificate.status == CERTIFICATE_CERTIFIED,
    ]
    if contract_id is not None:
        conditions.append(Certificate.contract_id == contract_id)
    if as_of is not None:
        conditions.append(Certificate.certificate_date <= as_of)
    if exclude_certificate_id is not None:
        conditions.append(Certificate.id != exclude_certificate_id)

    rows = session.execute(
        select(CertificateLine.cost_code_id, func.sum(CertificateLine.current_work_value_ex_tax))
        .join(Certificate, Certificate.id == CertificateLine.certificate_id)
        .where(*conditions)
        .group_by(CertificateLine.cost_code_id)
    ).all()
    return {cost_code_id: money(amount or ZERO) for cost_code_id, amount in rows}


def contract_committed_by_cost_code(
    session: Session, *, project_id: uuid.UUID, contract_id: uuid.UUID
) -> dict[uuid.UUID, Decimal]:
    """One contract's revised commitment, split by cost code.

    The ceiling certification is proven against: work may be certified against
    what this contract and its approved variations commit, never against another
    contract's headroom on the same code.
    """
    committed: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for cost_code_id, amount in session.execute(
        select(ContractLine.cost_code_id, func.sum(ContractLine.original_amount_ex_tax))
        .where(ContractLine.project_id == project_id, ContractLine.contract_id == contract_id)
        .group_by(ContractLine.cost_code_id)
    ).all():
        committed[cost_code_id] = money(amount or ZERO)
    for cost_code_id, amount in session.execute(
        select(VariationLine.cost_code_id, func.sum(VariationLine.value_delta_ex_tax))
        .join(Variation, Variation.id == VariationLine.variation_id)
        .where(
            VariationLine.project_id == project_id,
            Variation.contract_id == contract_id,
            Variation.status == VARIATION_APPROVED,
        )
        .group_by(VariationLine.cost_code_id)
    ).all():
        committed[cost_code_id] = money(committed[cost_code_id] + (amount or ZERO))
    return dict(committed)


def active_budget(session: Session, *, project_id: uuid.UUID) -> BudgetVersion | None:
    """The budget currently in force, or ``None`` where none has been activated."""
    return session.scalars(
        select(BudgetVersion).where(
            BudgetVersion.project_id == project_id, BudgetVersion.status == BUDGET_ACTIVE
        )
    ).first()


def budget_lines_by_cost_code(
    session: Session, *, budget_version_id: uuid.UUID
) -> dict[uuid.UUID, BudgetLine]:
    """One budget version's lines, keyed by the cost code each authorises."""
    return {
        line.cost_code_id: line
        for line in session.scalars(
            select(BudgetLine).where(BudgetLine.budget_version_id == budget_version_id)
        )
    }


# --------------------------------------------------------------------------- #
# Budget
# --------------------------------------------------------------------------- #


def list_budgets(session: Session, *, project: Project) -> list[BudgetVersion]:
    """Every budget version this project has had, newest first."""
    return list(
        session.scalars(
            select(BudgetVersion)
            .where(BudgetVersion.project_id == project.id)
            .order_by(BudgetVersion.version_number.desc())
        )
    )


def get_budget(session: Session, *, project: Project, version_id: uuid.UUID) -> BudgetVersion:
    """Load one budget version of this project, or refuse as if it did not exist."""
    version = session.scalars(
        select(BudgetVersion).where(
            BudgetVersion.id == version_id, BudgetVersion.project_id == project.id
        )
    ).first()
    if version is None:
        raise permissions.budget_not_found()
    return version


def _lock_budget(
    session: Session, *, project_id: uuid.UUID, version_id: uuid.UUID
) -> BudgetVersion:
    """Take a budget version for update, after the project lock above it."""
    version = session.scalars(
        select(BudgetVersion)
        .where(BudgetVersion.id == version_id, BudgetVersion.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if version is None:
        raise permissions.budget_not_found()
    return version


def _open_budget(session: Session, *, project_id: uuid.UUID) -> BudgetVersion | None:
    """The version currently being drafted, checked or waiting to be activated."""
    return session.scalars(
        select(BudgetVersion).where(
            BudgetVersion.project_id == project_id,
            BudgetVersion.status.in_(tuple(BUDGET_OPEN)),
        )
    ).first()


def create_budget(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    effective_date: date,
    change_reason: str,
    source_version_id: uuid.UUID | None = None,
) -> BudgetVersion:
    """Open a new budget version, cloning the lines of the one it replaces.

    A revision never rewrites the version it came from, and it carries every
    baseline forward untouched: a baseline that moved with each revision would
    stop being the original authorisation and start being a second copy of the
    current one, at which point nobody could say what the project was first
    approved to cost.

    A cost code that did not exist at the opening baseline starts at zero rather
    than at its first approved amount. Zero is the honest answer — there was no
    original authorisation for it — and manufacturing one would put a baseline
    in the record that nobody ever approved.
    """
    lock_project(session, project.id)
    if _open_budget(session, project_id=project.id) is not None:
        raise ConflictError(
            "This project already has a budget version being prepared. Finish or "
            "reject it before opening another, so there is never a question about "
            "which revision is the one under discussion."
        )

    source: BudgetVersion | None = None
    if source_version_id is not None:
        source = get_budget(session, project=project, version_id=source_version_id)
    elif (current := active_budget(session, project_id=project.id)) is not None:
        source = current

    highest = session.scalars(
        select(func.max(BudgetVersion.version_number)).where(BudgetVersion.project_id == project.id)
    ).first()
    version = BudgetVersion(
        project_id=project.id,
        version_number=(highest or 0) + 1,
        currency_id=project.base_currency_id,
        status=BUDGET_DRAFT,
        effective_date=effective_date,
        source_version_id=source.id if source is not None else None,
        change_reason=change_reason.strip(),
        created_by_user_id=actor.user_id,
    )
    session.add(version)
    _flush(session)

    if source is not None:
        for line in session.scalars(
            select(BudgetLine)
            .where(BudgetLine.budget_version_id == source.id)
            .order_by(BudgetLine.cost_code_id)
        ):
            session.add(
                BudgetLine(
                    project_id=project.id,
                    budget_version_id=version.id,
                    cost_code_id=line.cost_code_id,
                    baseline_amount=line.baseline_amount,
                    approved_budget_amount=line.approved_budget_amount,
                    contingency_amount=line.contingency_amount,
                    funding_source=line.funding_source,
                    notes=line.notes,
                )
            )
        _flush(session)

    record_event(
        session,
        action="construction.budget_created",
        entity_type=ENTITY_BUDGET,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=change_reason,
        after=_snapshot(version, _BUDGET_FIELDS),
    )
    return version


def _require_budget_editable(version: BudgetVersion) -> None:
    if version.status in BUDGET_FROZEN:
        raise ConflictError(
            "This budget version is no longer a draft. Open a revision to change "
            "what the project is authorised to spend."
        )
    if version.status == BUDGET_REJECTED:
        raise ConflictError("A rejected budget version is history and cannot be edited.")


def set_budget_line(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    cost_code_id: uuid.UUID,
    approved_budget_amount: Decimal,
    contingency_amount: Decimal,
    baseline_amount: Decimal | None = None,
    funding_source: str | None = None,
    notes: str | None = None,
) -> BudgetLine:
    """Write one cost code's authorisation into a draft budget version.

    ``baseline_amount`` may be supplied only where the line does not yet exist —
    an opening baseline for a project whose construction started before this
    system did. On an existing line it is carried, never overwritten: a
    revision that could restate the original authorisation would let somebody
    make an overrun disappear by moving the line it was measured from.
    """
    lock_project(session, project.id)
    version = _lock_budget(session, project_id=project.id, version_id=version_id)
    _require_budget_editable(version)
    code = get_cost_code(session, project=project, cost_code_id=cost_code_id)
    if not code.is_active:
        raise ValidationError(
            "That cost code has been retired and cannot be given a new authorisation."
        )

    line = session.scalars(
        select(BudgetLine).where(
            BudgetLine.budget_version_id == version.id, BudgetLine.cost_code_id == code.id
        )
    ).first()
    if line is None:
        line = BudgetLine(
            project_id=project.id,
            budget_version_id=version.id,
            cost_code_id=code.id,
            baseline_amount=money(baseline_amount if baseline_amount is not None else ZERO),
            approved_budget_amount=money(approved_budget_amount),
            contingency_amount=money(contingency_amount),
            funding_source=(funding_source or "").strip() or None,
            notes=(notes or "").strip() or None,
        )
        session.add(line)
    else:
        if baseline_amount is not None and money(baseline_amount) != line.baseline_amount:
            raise ConflictError(
                "The original baseline for this cost code is history and cannot be "
                "restated. Change the approved budget instead."
            )
        line.approved_budget_amount = money(approved_budget_amount)
        line.contingency_amount = money(contingency_amount)
        if funding_source is not None:
            line.funding_source = funding_source.strip() or None
        if notes is not None:
            line.notes = notes.strip() or None
    _flush(session)
    return line


def remove_budget_line(
    session: Session,
    *,
    project: Project,
    version_id: uuid.UUID,
    cost_code_id: uuid.UUID,
) -> None:
    """Drop a line from a draft version. Refused once anything is committed to it."""
    lock_project(session, project.id)
    version = _lock_budget(session, project_id=project.id, version_id=version_id)
    _require_budget_editable(version)
    line = session.scalars(
        select(BudgetLine).where(
            BudgetLine.budget_version_id == version.id, BudgetLine.cost_code_id == cost_code_id
        )
    ).first()
    if line is None:
        raise permissions.budget_not_found()
    committed = committed_by_cost_code(session, project_id=project.id).get(cost_code_id, ZERO)
    if committed != ZERO:
        raise ConflictError(
            "This cost code already carries a commitment. Removing its authorisation "
            "would leave money committed against nothing."
        )
    session.delete(line)
    _flush(session)


def submit_budget(
    session: Session, *, project: Project, actor: ActorContext, version_id: uuid.UUID
) -> BudgetVersion:
    """Hand a draft budget to a checker."""
    lock_project(session, project.id)
    version = _lock_budget(session, project_id=project.id, version_id=version_id)
    if version.status != BUDGET_DRAFT:
        raise ConflictError("Only a draft budget version can be submitted.")
    lines = session.scalars(
        select(BudgetLine).where(BudgetLine.budget_version_id == version.id)
    ).all()
    if not lines:
        raise ValidationError("A budget with no lines authorises nothing.")

    before = _snapshot(version, _BUDGET_FIELDS)
    version.status = BUDGET_SUBMITTED
    version.submitted_at = _now()
    version.submitted_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.budget_submitted",
        entity_type=ENTITY_BUDGET,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(version, _BUDGET_FIELDS),
    )
    return version


def approve_budget(
    session: Session, *, project: Project, actor: ActorContext, version_id: uuid.UUID
) -> BudgetVersion:
    """Sign off a submitted budget. Not the same act as putting it into force."""
    lock_project(session, project.id)
    version = _lock_budget(session, project_id=project.id, version_id=version_id)
    if version.status != BUDGET_SUBMITTED:
        raise ConflictError("Only a submitted budget version can be approved.")
    permissions.require_different_approver(actor, submitted_by_user_id=version.submitted_by_user_id)

    before = _snapshot(version, _BUDGET_FIELDS)
    version.status = BUDGET_APPROVED
    version.approved_at = _now()
    version.approved_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.budget_approved",
        entity_type=ENTITY_BUDGET,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(version, _BUDGET_FIELDS),
    )
    return version


def reject_budget(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    reason: str,
) -> BudgetVersion:
    """Refuse a submitted budget, with the reason on the record."""
    lock_project(session, project.id)
    version = _lock_budget(session, project_id=project.id, version_id=version_id)
    if version.status != BUDGET_SUBMITTED:
        raise ConflictError("Only a submitted budget version can be rejected.")
    permissions.require_different_approver(actor, submitted_by_user_id=version.submitted_by_user_id)

    before = _snapshot(version, _BUDGET_FIELDS)
    version.status = BUDGET_REJECTED
    version.rejected_at = _now()
    version.rejected_by_user_id = actor.user_id
    version.rejection_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action="construction.budget_rejected",
        entity_type=ENTITY_BUDGET,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(version, _BUDGET_FIELDS),
    )
    return version


def activate_budget(
    session: Session, *, project: Project, actor: ActorContext, version_id: uuid.UUID
) -> BudgetVersion:
    """Put an approved budget into force, having proved it covers what is committed.

    The check that matters is the last one. Every commitment already signed is
    re-read under lock and tested against the authorisation this version would
    give its cost code, and a version that would leave a standing contract
    outside its own budget is refused. The right order is to revise the budget
    and then commit; activating a budget that retrospectively puts an existing
    contract over its limit gets that order backwards and hides the overrun in
    the same move.
    """
    lock_project(session, project.id)
    version = _lock_budget(session, project_id=project.id, version_id=version_id)
    if version.status != BUDGET_APPROVED:
        raise ConflictError("Only an approved budget version can be activated.")
    if version.currency_id != project.base_currency_id:
        raise ConflictError(
            "This budget was prepared in a currency the project no longer accounts "
            "in. Prepare a revision in the project's base currency."
        )

    lines = budget_lines_by_cost_code(session, budget_version_id=version.id)
    committed = committed_by_cost_code(session, project_id=project.id)
    shortfalls: list[str] = []
    for cost_code_id, amount in committed.items():
        if amount == ZERO:
            continue
        line = lines.get(cost_code_id)
        code = session.get(CostCode, cost_code_id)
        label = code.code if code is not None else str(cost_code_id)
        if line is None:
            shortfalls.append(f"{label}: {amount} committed, no line in this version")
            continue
        available = calculator.control_budget(
            approved_budget=line.approved_budget_amount, contingency=line.contingency_amount
        )
        if amount > available:
            shortfalls.append(f"{label}: {amount} committed against {available} authorised")
    if shortfalls:
        raise ConflictError(
            "This budget does not cover commitments the project has already made — "
            + "; ".join(sorted(shortfalls))
            + ". Revise the budget upward, or reduce the commitment with an approved "
            "variation, before activating."
        )

    current = active_budget(session, project_id=project.id)
    if current is not None:
        current.status = BUDGET_SUPERSEDED
        current.superseded_at = _now()
        _flush(session)
        record_event(
            session,
            action="construction.budget_superseded",
            entity_type=ENTITY_BUDGET,
            entity_id=current.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            after=_snapshot(current, _BUDGET_FIELDS),
        )

    before = _snapshot(version, _BUDGET_FIELDS)
    version.status = BUDGET_ACTIVE
    version.activated_at = _now()
    version.activated_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.budget_activated",
        entity_type=ENTITY_BUDGET,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(version, _BUDGET_FIELDS),
    )
    return version


# --------------------------------------------------------------------------- #
# Contracts
# --------------------------------------------------------------------------- #


def list_contracts(session: Session, *, project: Project) -> list[Contract]:
    """The project's commitments, newest first."""
    return list(
        session.scalars(
            select(Contract)
            .where(Contract.project_id == project.id)
            .order_by(Contract.created_at.desc())
        )
    )


def get_contract(session: Session, *, project: Project, contract_id: uuid.UUID) -> Contract:
    """Load one contract of this project, or refuse as if it did not exist."""
    contract = session.scalars(
        select(Contract).where(Contract.id == contract_id, Contract.project_id == project.id)
    ).first()
    if contract is None:
        raise permissions.contract_not_found()
    return contract


def _lock_contract(session: Session, *, project_id: uuid.UUID, contract_id: uuid.UUID) -> Contract:
    """Take a contract for update, after the project lock above it."""
    contract = session.scalars(
        select(Contract)
        .where(Contract.id == contract_id, Contract.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if contract is None:
        raise permissions.contract_not_found()
    return contract


def create_contract(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    contract_number: str,
    contract_type: str,
    vendor_name: str,
    original_contract_value_ex_tax: Decimal,
    currency_id: uuid.UUID,
    advance_entitlement_amount: Decimal = ZERO,
    retention_rate_fraction: Decimal = Decimal("0.000000"),
    tax_rate_fraction: Decimal | None = None,
    vendor_registration_reference: str | None = None,
    vendor_tax_reference: str | None = None,
    vendor_contact_reference: str | None = None,
    payment_terms: str | None = None,
    planned_start_date: date | None = None,
    planned_completion_date: date | None = None,
    notes: str | None = None,
) -> Contract:
    """Draft a commitment. Nothing is committed until it is activated."""
    lock_project(session, project.id)
    if currency_id != project.base_currency_id:
        raise ValidationError(
            "A contract must be denominated in the project's base currency. This "
            "platform holds no exchange rates, so a second denomination would be a "
            "number nothing could add to the project's position."
        )
    contract = Contract(
        project_id=project.id,
        contract_number=contract_number.strip(),
        contract_type=contract_type,
        vendor_name=vendor_name.strip(),
        currency_id=currency_id,
        original_contract_value_ex_tax=money(original_contract_value_ex_tax),
        advance_entitlement_amount=money(advance_entitlement_amount),
        retention_rate_fraction=retention_rate_fraction,
        tax_rate_fraction=tax_rate_fraction,
        status=CONTRACT_DRAFT,
        created_by_user_id=actor.user_id,
        vendor_registration_reference=(vendor_registration_reference or "").strip() or None,
        vendor_tax_reference=(vendor_tax_reference or "").strip() or None,
        vendor_contact_reference=(vendor_contact_reference or "").strip() or None,
        payment_terms=(payment_terms or "").strip() or None,
        planned_start_date=planned_start_date,
        planned_completion_date=planned_completion_date,
        notes=(notes or "").strip() or None,
    )
    session.add(contract)
    _flush(session)
    record_event(
        session,
        action="construction.contract_created",
        entity_type=ENTITY_CONTRACT,
        entity_id=contract.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(contract, _CONTRACT_FIELDS),
    )
    return contract


def _require_contract_editable(contract: Contract) -> None:
    if contract.status not in CONTRACT_EDITABLE:
        raise ConflictError(
            "This contract has left draft. Its original value and lines are what "
            "was signed, and a change to what is owed is a variation."
        )


def set_contract_line(
    session: Session,
    *,
    project: Project,
    contract_id: uuid.UUID,
    sequence: int,
    description: str,
    cost_code_id: uuid.UUID,
    original_amount_ex_tax: Decimal,
    notes: str | None = None,
) -> ContractLine:
    """Write one cost code's share of a draft contract's value."""
    lock_project(session, project.id)
    contract = _lock_contract(session, project_id=project.id, contract_id=contract_id)
    _require_contract_editable(contract)
    code = get_cost_code(session, project=project, cost_code_id=cost_code_id)
    if not code.is_active:
        raise ValidationError("That cost code has been retired and cannot take new commitment.")

    line = session.scalars(
        select(ContractLine).where(
            ContractLine.contract_id == contract.id, ContractLine.sequence == sequence
        )
    ).first()
    if line is None:
        line = ContractLine(
            project_id=project.id,
            contract_id=contract.id,
            sequence=sequence,
            description=description.strip(),
            cost_code_id=code.id,
            original_amount_ex_tax=money(original_amount_ex_tax),
            notes=(notes or "").strip() or None,
        )
        session.add(line)
    else:
        line.description = description.strip()
        line.cost_code_id = code.id
        line.original_amount_ex_tax = money(original_amount_ex_tax)
        line.notes = (notes or "").strip() or None
    _flush(session)
    return line


def remove_contract_line(
    session: Session, *, project: Project, contract_id: uuid.UUID, sequence: int
) -> None:
    """Drop a line from a draft contract."""
    lock_project(session, project.id)
    contract = _lock_contract(session, project_id=project.id, contract_id=contract_id)
    _require_contract_editable(contract)
    line = session.scalars(
        select(ContractLine).where(
            ContractLine.contract_id == contract.id, ContractLine.sequence == sequence
        )
    ).first()
    if line is None:
        raise permissions.contract_not_found()
    session.delete(line)
    _flush(session)


def contract_line_total(session: Session, *, contract_id: uuid.UUID) -> Decimal:
    """What a contract's lines add up to, at the stored scale."""
    total = session.scalars(
        select(func.sum(ContractLine.original_amount_ex_tax)).where(
            ContractLine.contract_id == contract_id
        )
    ).first()
    return money(total or ZERO)


def submit_contract(
    session: Session, *, project: Project, actor: ActorContext, contract_id: uuid.UUID
) -> Contract:
    """Freeze a draft contract for financial authorisation."""
    lock_project(session, project.id)
    contract = _lock_contract(session, project_id=project.id, contract_id=contract_id)
    if contract.status != CONTRACT_DRAFT:
        raise ConflictError("Only a draft contract can be submitted.")
    _require_lines_reconcile(session, contract=contract)

    before = _snapshot(contract, _CONTRACT_FIELDS)
    contract.status = CONTRACT_SUBMITTED
    contract.submitted_at = _now()
    contract.submitted_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.contract_submitted",
        entity_type=ENTITY_CONTRACT,
        entity_id=contract.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(contract, _CONTRACT_FIELDS),
    )
    return contract


def _require_lines_reconcile(session: Session, *, contract: Contract) -> None:
    """Refuse a contract whose lines do not add up to its header, to the cent.

    No tolerance. A contract that is out by a cent is a contract whose cost-code
    split is wrong by a cent, and every budget comparison built on it inherits
    the error — silently, because a tolerance is exactly the mechanism that
    stops anybody noticing.
    """
    lines = contract_line_total(session, contract_id=contract.id)
    if lines != contract.original_contract_value_ex_tax:
        raise ValidationError(
            f"The contract's lines total {lines}, but its value is "
            f"{contract.original_contract_value_ex_tax}. They must agree exactly "
            "before it can be authorised."
        )


def activate_contract(
    session: Session, *, project: Project, actor: ActorContext, contract_id: uuid.UUID
) -> Contract:
    """Make a submitted contract a commitment, having proved the budget covers it.

    Everything is re-proved here under lock rather than trusted from submission:
    the lines still reconcile, the currency is still the project's, a budget is
    still in force, and every cost code this contract touches still has room for
    it beside whatever else has been committed since. The last of those is the
    race — two contracts submitted against the same headroom, both activated,
    neither aware of the other.
    """
    lock_project(session, project.id)
    contract = _lock_contract(session, project_id=project.id, contract_id=contract_id)
    if contract.status != CONTRACT_SUBMITTED:
        raise ConflictError("Only a submitted contract can be activated.")
    if contract.currency_id != project.base_currency_id:
        raise ConflictError(
            "This contract is not denominated in the project's base currency and "
            "cannot be activated."
        )
    _require_lines_reconcile(session, contract=contract)

    budget = active_budget(session, project_id=project.id)
    if budget is None:
        raise ConflictError(
            "This project has no active construction budget. A commitment needs an "
            "authorisation to sit inside."
        )
    lines = budget_lines_by_cost_code(session, budget_version_id=budget.id)
    others = committed_by_cost_code(session, project_id=project.id, exclude_contract_id=contract.id)
    mine = contract_committed_by_cost_code(session, project_id=project.id, contract_id=contract.id)
    _require_headroom(session, budget_lines=lines, standing=others, additional=mine)

    before = _snapshot(contract, _CONTRACT_FIELDS)
    contract.status = CONTRACT_ACTIVE
    contract.activated_at = _now()
    contract.activated_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.contract_activated",
        entity_type=ENTITY_CONTRACT,
        entity_id=contract.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(contract, _CONTRACT_FIELDS),
    )
    return contract


def _require_headroom(
    session: Session,
    *,
    budget_lines: dict[uuid.UUID, BudgetLine],
    standing: dict[uuid.UUID, Decimal],
    additional: dict[uuid.UUID, Decimal],
) -> None:
    """Prove every affected cost code can carry what is about to be committed.

    Reports every cost code that fails rather than the first, because a
    contractor waiting on an authorisation should be told the whole shortfall
    once instead of discovering it one code at a time.
    """
    shortfalls: list[str] = []
    for cost_code_id, delta in additional.items():
        if delta <= ZERO:
            continue
        line = budget_lines.get(cost_code_id)
        code = session.get(CostCode, cost_code_id)
        label = code.code if code is not None else str(cost_code_id)
        if line is None:
            shortfalls.append(f"{label}: no authorisation in the active budget")
            continue
        room = calculator.headroom(
            approved_budget=line.approved_budget_amount,
            contingency=line.contingency_amount,
            committed=standing.get(cost_code_id, ZERO),
        )
        if delta > room:
            shortfalls.append(f"{label}: needs {delta}, {room} remains")
    if shortfalls:
        raise ConflictError(
            "The active budget does not have room for this — "
            + "; ".join(sorted(shortfalls))
            + ". Revise and approve the budget first; authorising the commitment and "
            "finding the money afterwards is the wrong way round."
        )


def _close_contract(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    contract_id: uuid.UUID,
    to_status: str,
    action: str,
    reason: str | None,
) -> Contract:
    """Move a contract to a terminal state without touching what it committed.

    This is the function the module's second invariant lives in. Completing,
    terminating or cancelling a contract changes what may happen next; it does
    not change what has been committed, and there is deliberately no line here
    that reduces a value. A commitment that should no longer stand leaves
    through an approved negative variation, which has an approver, a reason and
    a date — none of which a status change has.
    """
    lock_project(session, project.id)
    contract = _lock_contract(session, project_id=project.id, contract_id=contract_id)
    if to_status == CONTRACT_CANCELLED and contract.status not in (
        CONTRACT_DRAFT,
        CONTRACT_SUBMITTED,
    ):
        raise ConflictError(
            "Only a contract that never became a commitment can be cancelled. One "
            "that did is terminated, and its money leaves through a variation."
        )
    if (
        to_status in (CONTRACT_COMPLETED, CONTRACT_TERMINATED)
        and contract.status != CONTRACT_ACTIVE
    ):
        raise ConflictError("Only an active contract can be completed or terminated.")

    before = _snapshot(contract, _CONTRACT_FIELDS)
    contract.status = to_status
    stamp = _now()
    if to_status == CONTRACT_COMPLETED:
        contract.completed_at = stamp
    elif to_status == CONTRACT_TERMINATED:
        contract.terminated_at = stamp
        contract.termination_reason = (reason or "").strip() or None
    else:
        contract.cancelled_at = stamp
        contract.cancellation_reason = (reason or "").strip() or None
    _flush(session)
    record_event(
        session,
        action=action,
        entity_type=ENTITY_CONTRACT,
        entity_id=contract.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(contract, _CONTRACT_FIELDS),
    )
    return contract


def complete_contract(
    session: Session, *, project: Project, actor: ActorContext, contract_id: uuid.UUID
) -> Contract:
    """Record that a contract's work is finished. Its commitment stands."""
    return _close_contract(
        session,
        project=project,
        actor=actor,
        contract_id=contract_id,
        to_status=CONTRACT_COMPLETED,
        action="construction.contract_completed",
        reason=None,
    )


def terminate_contract(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    contract_id: uuid.UUID,
    reason: str,
) -> Contract:
    """End a live contract early. Its commitment stands until a variation removes it."""
    return _close_contract(
        session,
        project=project,
        actor=actor,
        contract_id=contract_id,
        to_status=CONTRACT_TERMINATED,
        action="construction.contract_terminated",
        reason=reason,
    )


def cancel_contract(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    contract_id: uuid.UUID,
    reason: str,
) -> Contract:
    """Abandon a contract that never became a commitment."""
    return _close_contract(
        session,
        project=project,
        actor=actor,
        contract_id=contract_id,
        to_status=CONTRACT_CANCELLED,
        action="construction.contract_cancelled",
        reason=reason,
    )


# --------------------------------------------------------------------------- #
# Variations
# --------------------------------------------------------------------------- #


def list_variations(
    session: Session, *, project: Project, contract_id: uuid.UUID | None = None
) -> list[Variation]:
    """The project's change orders, newest first."""
    statement = select(Variation).where(Variation.project_id == project.id)
    if contract_id is not None:
        statement = statement.where(Variation.contract_id == contract_id)
    return list(session.scalars(statement.order_by(Variation.created_at.desc())))


def get_variation(session: Session, *, project: Project, variation_id: uuid.UUID) -> Variation:
    """Load one variation of this project, or refuse as if it did not exist."""
    variation = session.scalars(
        select(Variation).where(Variation.id == variation_id, Variation.project_id == project.id)
    ).first()
    if variation is None:
        raise permissions.variation_not_found()
    return variation


def variation_total(session: Session, *, variation_id: uuid.UUID) -> Decimal:
    """What a variation is worth: the signed sum of its lines, never a column."""
    total = session.scalars(
        select(func.sum(VariationLine.value_delta_ex_tax)).where(
            VariationLine.variation_id == variation_id
        )
    ).first()
    return money(total or ZERO)


def variation_delta_by_cost_code(
    session: Session, *, variation_id: uuid.UUID
) -> dict[uuid.UUID, Decimal]:
    """One variation's signed effect, split by the cost codes it touches."""
    rows = session.execute(
        select(VariationLine.cost_code_id, func.sum(VariationLine.value_delta_ex_tax))
        .where(VariationLine.variation_id == variation_id)
        .group_by(VariationLine.cost_code_id)
    ).all()
    return {cost_code_id: money(amount or ZERO) for cost_code_id, amount in rows}


def create_variation(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    contract_id: uuid.UUID,
    variation_number: str,
    description: str,
    requested_date: date,
    instruction_reference: str | None = None,
    cause: str | None = None,
    time_impact_days: int = 0,
    funding_source: str | None = None,
) -> Variation:
    """Draft a change to what a contract commits."""
    lock_project(session, project.id)
    contract = get_contract(session, project=project, contract_id=contract_id)
    if contract.status not in CONTRACT_COMMITTING:
        raise ConflictError(
            "Only a contract that stands as a commitment can be varied. A draft "
            "contract is changed by editing it."
        )
    variation = Variation(
        project_id=project.id,
        contract_id=contract.id,
        variation_number=variation_number.strip(),
        description=description.strip(),
        requested_date=requested_date,
        instruction_reference=(instruction_reference or "").strip() or None,
        cause=(cause or "").strip() or None,
        time_impact_days=time_impact_days,
        funding_source=(funding_source or "").strip() or None,
        status=VARIATION_DRAFT,
        created_by_user_id=actor.user_id,
    )
    session.add(variation)
    _flush(session)
    record_event(
        session,
        action="construction.variation_created",
        entity_type=ENTITY_VARIATION,
        entity_id=variation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(variation, _VARIATION_FIELDS),
    )
    return variation


def set_variation_line(
    session: Session,
    *,
    project: Project,
    variation_id: uuid.UUID,
    sequence: int,
    cost_code_id: uuid.UUID,
    description: str,
    value_delta_ex_tax: Decimal,
) -> VariationLine:
    """Write one signed change against one cost code.

    Zero is refused by the column, and deliberately: a change worth nothing is
    not a change, and a line carrying it would appear on a register as a
    variation that did something.
    """
    lock_project(session, project.id)
    variation = get_variation(session, project=project, variation_id=variation_id)
    if variation.status != VARIATION_DRAFT:
        raise ConflictError("Only a draft variation can be edited.")
    code = get_cost_code(session, project=project, cost_code_id=cost_code_id)
    delta = money(value_delta_ex_tax)
    if delta == ZERO:
        raise ValidationError("A variation line must change the value by something.")

    line = session.scalars(
        select(VariationLine).where(
            VariationLine.variation_id == variation.id, VariationLine.sequence == sequence
        )
    ).first()
    if line is None:
        line = VariationLine(
            project_id=project.id,
            variation_id=variation.id,
            sequence=sequence,
            cost_code_id=code.id,
            description=description.strip(),
            value_delta_ex_tax=delta,
        )
        session.add(line)
    else:
        line.cost_code_id = code.id
        line.description = description.strip()
        line.value_delta_ex_tax = delta
    _flush(session)
    return line


def remove_variation_line(
    session: Session, *, project: Project, variation_id: uuid.UUID, sequence: int
) -> None:
    """Drop a line from a draft variation."""
    lock_project(session, project.id)
    variation = get_variation(session, project=project, variation_id=variation_id)
    if variation.status != VARIATION_DRAFT:
        raise ConflictError("Only a draft variation can be edited.")
    line = session.scalars(
        select(VariationLine).where(
            VariationLine.variation_id == variation.id, VariationLine.sequence == sequence
        )
    ).first()
    if line is None:
        raise permissions.variation_not_found()
    session.delete(line)
    _flush(session)


def submit_variation(
    session: Session, *, project: Project, actor: ActorContext, variation_id: uuid.UUID
) -> Variation:
    """Freeze a draft variation for a decision."""
    lock_project(session, project.id)
    variation = get_variation(session, project=project, variation_id=variation_id)
    if variation.status != VARIATION_DRAFT:
        raise ConflictError("Only a draft variation can be submitted.")
    if (
        variation_total(session, variation_id=variation.id) == ZERO
        and not session.scalars(
            select(VariationLine.id).where(VariationLine.variation_id == variation.id).limit(1)
        ).first()
    ):
        raise ValidationError("A variation with no lines changes nothing.")

    before = _snapshot(variation, _VARIATION_FIELDS)
    variation.status = VARIATION_SUBMITTED
    variation.submitted_at = _now()
    variation.submitted_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.variation_submitted",
        entity_type=ENTITY_VARIATION,
        entity_id=variation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(variation, _VARIATION_FIELDS),
    )
    return variation


def variation_review_amount(session: Session, *, project: Project) -> Decimal | None:
    """The country pack's escalation threshold, or ``None`` where none is set.

    Read from the pack the project is configured against rather than from a
    construction-specific setting, because the platform already has one place
    where a country's approval authorities are stated and a second would be a
    second answer to the same question.
    """
    thresholds = session.scalars(
        select(CountryApprovalThreshold).where(
            CountryApprovalThreshold.country_pack_id == project.country_pack_id
        )
    ).first()
    if thresholds is None:
        return None
    return thresholds.construction_variation_review_amount


def variation_requires_escalation(
    session: Session, *, project: Project, variation_id: uuid.UUID
) -> tuple[bool, Decimal | None, Decimal]:
    """Whether this variation needs an Approver / CFO, and the figures behind it.

    Escalation is decided on the **absolute** value of the change. A million
    removed from a contract is as much a scope decision as a million added, and
    a threshold that only looked at increases would let the larger of the two
    through on a single signature.

    Returned as a triple so the API can state the rule rather than the browser
    re-deriving it: a threshold recomputed on the client is a threshold that can
    disagree with the one the server will actually enforce.
    """
    total = variation_total(session, variation_id=variation_id)
    threshold = variation_review_amount(session, project=project)
    if threshold is None:
        return False, None, total
    return abs(total) >= threshold, threshold, total


def approve_variation(
    session: Session, *, project: Project, actor: ActorContext, variation_id: uuid.UUID
) -> Variation:
    """Approve a change, having proved the budget can carry it.

    Two guards, in this order. The threshold decides who may sign — and it is
    evaluated here, on the server, against the pack's configured amount rather
    than trusted from whatever the client believed when it drew the button. Then
    the headroom is re-read under lock: a variation that would push a cost code
    past its authorisation is refused with the code and the shortfall named, so
    the next step is obvious rather than a mystery.

    Contingency is not moved into the approved budget by any of this. The two
    stay separately visible and only their total constrains the commitment; a
    reserve that silently became budget the first time it was used would stop
    being a reserve anybody could report on.
    """
    lock_project(session, project.id)
    variation = get_variation(session, project=project, variation_id=variation_id)
    if variation.status != VARIATION_SUBMITTED:
        raise ConflictError("Only a submitted variation can be approved.")
    permissions.require_different_approver(
        actor, submitted_by_user_id=variation.submitted_by_user_id
    )
    escalated, threshold, total = variation_requires_escalation(
        session, project=project, variation_id=variation.id
    )
    if escalated:
        permissions.require_construction_approver(actor)
    else:
        permissions.require_construction_checker(actor)

    contract = _lock_contract(session, project_id=project.id, contract_id=variation.contract_id)
    deltas = variation_delta_by_cost_code(session, variation_id=variation.id)
    if any(delta > ZERO for delta in deltas.values()):
        budget = active_budget(session, project_id=project.id)
        if budget is None:
            raise ConflictError(
                "This project has no active construction budget, so there is no "
                "authorisation for this variation to sit inside."
            )
        _require_headroom(
            session,
            budget_lines=budget_lines_by_cost_code(session, budget_version_id=budget.id),
            standing=committed_by_cost_code(session, project_id=project.id),
            additional={code: delta for code, delta in deltas.items() if delta > ZERO},
        )

    before = _snapshot(variation, _VARIATION_FIELDS)
    variation.status = VARIATION_APPROVED
    variation.approved_at = _now()
    variation.approved_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.variation_approved",
        entity_type=ENTITY_VARIATION,
        entity_id=variation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=(
            f"{total} against a review amount of {threshold}"
            if threshold is not None
            else f"{total}, no review amount configured"
        ),
        before=before,
        after=_snapshot(variation, _VARIATION_FIELDS),
    )
    # Touched so the contract's updated_at moves with what it now commits.
    contract.updated_at = _now()
    return variation


def reject_variation(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    variation_id: uuid.UUID,
    reason: str,
) -> Variation:
    """Refuse a submitted variation, with the reason on the record."""
    lock_project(session, project.id)
    variation = get_variation(session, project=project, variation_id=variation_id)
    if variation.status != VARIATION_SUBMITTED:
        raise ConflictError("Only a submitted variation can be rejected.")
    permissions.require_different_approver(
        actor, submitted_by_user_id=variation.submitted_by_user_id
    )
    before = _snapshot(variation, _VARIATION_FIELDS)
    variation.status = VARIATION_REJECTED
    variation.rejected_at = _now()
    variation.rejected_by_user_id = actor.user_id
    variation.rejection_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action="construction.variation_rejected",
        entity_type=ENTITY_VARIATION,
        entity_id=variation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(variation, _VARIATION_FIELDS),
    )
    return variation


def withdraw_variation(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    variation_id: uuid.UUID,
    reason: str,
) -> Variation:
    """Take back a submitted variation before anybody decides on it."""
    lock_project(session, project.id)
    variation = get_variation(session, project=project, variation_id=variation_id)
    if variation.status != VARIATION_SUBMITTED:
        raise ConflictError("Only a submitted variation can be withdrawn.")
    before = _snapshot(variation, _VARIATION_FIELDS)
    variation.status = VARIATION_WITHDRAWN
    variation.withdrawn_at = _now()
    variation.withdrawal_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action="construction.variation_withdrawn",
        entity_type=ENTITY_VARIATION,
        entity_id=variation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(variation, _VARIATION_FIELDS),
    )
    return variation


# --------------------------------------------------------------------------- #
# Certificates
# --------------------------------------------------------------------------- #


def list_certificates(
    session: Session, *, project: Project, contract_id: uuid.UUID | None = None
) -> list[Certificate]:
    """The project's valuations, newest period first."""
    statement = select(Certificate).where(Certificate.project_id == project.id)
    if contract_id is not None:
        statement = statement.where(Certificate.contract_id == contract_id)
    return list(session.scalars(statement.order_by(Certificate.period_end.desc())))


def get_certificate(
    session: Session, *, project: Project, certificate_id: uuid.UUID
) -> Certificate:
    """Load one certificate of this project, or refuse as if it did not exist."""
    certificate = session.scalars(
        select(Certificate).where(
            Certificate.id == certificate_id, Certificate.project_id == project.id
        )
    ).first()
    if certificate is None:
        raise permissions.certificate_not_found()
    return certificate


def certificate_work_total(session: Session, *, certificate_id: uuid.UUID) -> Decimal:
    """The gross work certified on one certificate, from its lines."""
    total = session.scalars(
        select(func.sum(CertificateLine.current_work_value_ex_tax)).where(
            CertificateLine.certificate_id == certificate_id
        )
    ).first()
    return money(total or ZERO)


def certificate_amounts(
    session: Session, *, contract: Contract, certificate: Certificate
) -> calculator.CertificateAmounts:
    """Lay out one certificate's payable figures from its own stored inputs."""
    return calculator.certificate_amounts(
        current_work_ex_tax=certificate_work_total(session, certificate_id=certificate.id),
        retention_rate_fraction=contract.retention_rate_fraction,
        retention_release=certificate.retention_release_amount,
        advance_recovery=certificate.advance_recovery_amount,
        other_deductions=certificate.other_deductions_amount,
        tax=certificate.tax_amount,
    )


def retention_position(
    session: Session, *, project_id: uuid.UUID, contract_id: uuid.UUID
) -> tuple[Decimal, Decimal]:
    """Retention held and released to date on one contract, from certified rows.

    Held is recomputed from each certificate's own work and the contract's rate
    rather than read from a column, so a reversal simply stops contributing.
    A stored balance would need every reversal to remember to decrement it.
    """
    contract = session.get(Contract, contract_id)
    rate = contract.retention_rate_fraction if contract is not None else ZERO
    rows = session.execute(
        select(
            Certificate.id,
            Certificate.retention_release_amount,
            func.coalesce(func.sum(CertificateLine.current_work_value_ex_tax), 0),
        )
        .join(CertificateLine, CertificateLine.certificate_id == Certificate.id, isouter=True)
        .where(
            Certificate.project_id == project_id,
            Certificate.contract_id == contract_id,
            Certificate.status == CERTIFICATE_CERTIFIED,
        )
        .group_by(Certificate.id, Certificate.retention_release_amount)
    ).all()
    held = ZERO
    released = ZERO
    for _certificate_id, release, work in rows:
        held = money(
            held
            + calculator.retention_held(
                current_work_ex_tax=money(work or ZERO), retention_rate_fraction=rate
            )
        )
        released = money(released + (release or ZERO))
    return held, released


def advance_position(
    session: Session, *, project_id: uuid.UUID, contract_id: uuid.UUID
) -> tuple[Decimal, Decimal]:
    """Advance cash actually paid, and advance recovered through certificates.

    Paid is confirmed, unreversed payment allocated to approved or disputed
    advance invoices — not the contract's entitlement, and not a recorded
    payment. An entitlement nobody drew down is not money anybody has to
    recover, and a payment nobody confirmed has not left the bank.
    """
    paid = session.scalars(
        select(func.sum(PaymentAllocation.amount))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .join(Invoice, Invoice.id == PaymentAllocation.invoice_id)
        .where(
            PaymentAllocation.project_id == project_id,
            PaymentAllocation.contract_id == contract_id,
            Payment.status == PAYMENT_CONFIRMED,
            Invoice.invoice_type == INVOICE_ADVANCE,
            Invoice.status.in_(tuple(INVOICE_STANDING)),
        )
    ).first()
    recovered = session.scalars(
        select(func.sum(Certificate.advance_recovery_amount)).where(
            Certificate.project_id == project_id,
            Certificate.contract_id == contract_id,
            Certificate.status == CERTIFICATE_CERTIFIED,
        )
    ).first()
    return money(paid or ZERO), money(recovered or ZERO)


def create_certificate(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    contract_id: uuid.UUID,
    certificate_number: str,
    period_start: date,
    period_end: date,
    certificate_date: date,
    retention_release_amount: Decimal = ZERO,
    advance_recovery_amount: Decimal = ZERO,
    other_deductions_amount: Decimal = ZERO,
    tax_amount: Decimal = ZERO,
    certifier_name: str | None = None,
    evidence_reference: str | None = None,
    notes: str | None = None,
) -> Certificate:
    """Draft a valuation. Nothing is certified until somebody certifies it."""
    lock_project(session, project.id)
    contract = get_contract(session, project=project, contract_id=contract_id)
    if contract.status not in CONTRACT_COMMITTING:
        raise ConflictError(
            "Work can only be certified against a contract that stands as a commitment."
        )
    certificate = Certificate(
        project_id=project.id,
        contract_id=contract.id,
        certificate_number=certificate_number.strip(),
        period_start=period_start,
        period_end=period_end,
        certificate_date=certificate_date,
        retention_release_amount=money(retention_release_amount),
        advance_recovery_amount=money(advance_recovery_amount),
        other_deductions_amount=money(other_deductions_amount),
        tax_amount=money(tax_amount),
        certifier_name=(certifier_name or "").strip() or None,
        evidence_reference=(evidence_reference or "").strip() or None,
        notes=(notes or "").strip() or None,
        status=CERTIFICATE_DRAFT,
        created_by_user_id=actor.user_id,
    )
    session.add(certificate)
    _flush(session)
    record_event(
        session,
        action="construction.certificate_created",
        entity_type=ENTITY_CERTIFICATE,
        entity_id=certificate.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(certificate, _CERTIFICATE_FIELDS),
    )
    return certificate


def set_certificate_line(
    session: Session,
    *,
    project: Project,
    certificate_id: uuid.UUID,
    cost_code_id: uuid.UUID,
    current_work_value_ex_tax: Decimal,
    notes: str | None = None,
) -> CertificateLine:
    """Write the value of work done against one cost code in this period."""
    lock_project(session, project.id)
    certificate = get_certificate(session, project=project, certificate_id=certificate_id)
    if certificate.status != CERTIFICATE_DRAFT:
        raise ConflictError("Only a draft certificate can be edited.")
    code = get_cost_code(session, project=project, cost_code_id=cost_code_id)

    line = session.scalars(
        select(CertificateLine).where(
            CertificateLine.certificate_id == certificate.id,
            CertificateLine.cost_code_id == code.id,
        )
    ).first()
    if line is None:
        line = CertificateLine(
            project_id=project.id,
            certificate_id=certificate.id,
            cost_code_id=code.id,
            current_work_value_ex_tax=money(current_work_value_ex_tax),
            notes=(notes or "").strip() or None,
        )
        session.add(line)
    else:
        line.current_work_value_ex_tax = money(current_work_value_ex_tax)
        line.notes = (notes or "").strip() or None
    _flush(session)
    return line


def submit_certificate(
    session: Session, *, project: Project, actor: ActorContext, certificate_id: uuid.UUID
) -> Certificate:
    """Freeze a draft valuation for certification."""
    lock_project(session, project.id)
    certificate = get_certificate(session, project=project, certificate_id=certificate_id)
    if certificate.status != CERTIFICATE_DRAFT:
        raise ConflictError("Only a draft certificate can be submitted.")
    if not session.scalars(
        select(CertificateLine.id).where(CertificateLine.certificate_id == certificate.id).limit(1)
    ).first():
        raise ValidationError("A certificate with no lines certifies nothing.")

    before = _snapshot(certificate, _CERTIFICATE_FIELDS)
    certificate.status = CERTIFICATE_SUBMITTED
    certificate.submitted_at = _now()
    certificate.submitted_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.certificate_submitted",
        entity_type=ENTITY_CERTIFICATE,
        entity_id=certificate.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(certificate, _CERTIFICATE_FIELDS),
    )
    return certificate


def certify_certificate(
    session: Session, *, project: Project, actor: ActorContext, certificate_id: uuid.UUID
) -> Certificate:
    """Certify work as done — the one act in this module that becomes cost.

    Four proofs, all under the contract's lock so two certifiers cannot each see
    the same remaining commitment and both use it:

    * **Commitment.** Everything already certified on this contract, plus this
      certificate, must fit inside what the contract and its approved variations
      commit — per cost code, not merely in total, because a total that fits
      while one code is 400% over is a total that hides the overrun.
    * **Retention.** A release cannot exceed retention actually held and not yet
      given back. Money that was never withheld cannot be returned.
    * **Advance.** A recovery cannot exceed advance cash actually paid and not
      yet recovered. An advance that never left the bank cannot be taken back
      out of a valuation.
    * **Net due.** The certificate must not come out negative. A valuation whose
      deductions exceed its work is not a payment certificate; it is a credit
      note, and this module does not pretend one is the other.
    """
    lock_project(session, project.id)
    certificate = get_certificate(session, project=project, certificate_id=certificate_id)
    if certificate.status != CERTIFICATE_SUBMITTED:
        raise ConflictError("Only a submitted certificate can be certified.")
    permissions.require_different_approver(
        actor, submitted_by_user_id=certificate.submitted_by_user_id
    )
    contract = _lock_contract(session, project_id=project.id, contract_id=certificate.contract_id)

    committed = contract_committed_by_cost_code(
        session, project_id=project.id, contract_id=contract.id
    )
    already = certified_by_cost_code(
        session,
        project_id=project.id,
        contract_id=contract.id,
        exclude_certificate_id=certificate.id,
    )
    this_certificate = {
        line.cost_code_id: line.current_work_value_ex_tax
        for line in session.scalars(
            select(CertificateLine).where(CertificateLine.certificate_id == certificate.id)
        )
    }
    over: list[str] = []
    for cost_code_id, work in this_certificate.items():
        ceiling = committed.get(cost_code_id, ZERO)
        cumulative = money(already.get(cost_code_id, ZERO) + work)
        if cumulative > ceiling:
            code = session.get(CostCode, cost_code_id)
            label = code.code if code is not None else str(cost_code_id)
            over.append(f"{label}: {cumulative} certified against {ceiling} committed")
    if over:
        raise ConflictError(
            "This certificate would certify more than the contract commits — "
            + "; ".join(sorted(over))
            + ". Approve a variation for the extra scope before certifying it."
        )

    held, released = retention_position(session, project_id=project.id, contract_id=contract.id)
    if certificate.retention_release_amount > money(held - released):
        raise ConflictError(
            f"This certificate releases {certificate.retention_release_amount} of "
            f"retention, but only {money(held - released)} is being held."
        )
    paid, recovered = advance_position(session, project_id=project.id, contract_id=contract.id)
    if certificate.advance_recovery_amount > money(paid - recovered):
        raise ConflictError(
            f"This certificate recovers {certificate.advance_recovery_amount} of "
            f"advance, but only {money(paid - recovered)} of advance cash has been "
            "paid and not yet recovered."
        )

    amounts = certificate_amounts(session, contract=contract, certificate=certificate)
    if amounts.net_due < ZERO:
        raise ValidationError(
            f"This certificate's deductions exceed its work: net due would be "
            f"{amounts.net_due}. A negative valuation is a credit note, not a "
            "payment certificate."
        )

    before = _snapshot(certificate, _CERTIFICATE_FIELDS)
    certificate.status = CERTIFICATE_CERTIFIED
    certificate.certified_at = _now()
    certificate.certified_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.certificate_certified",
        entity_type=ENTITY_CERTIFICATE,
        entity_id=certificate.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=f"net due {amounts.net_due}, retention held {amounts.retention_held}",
        before=before,
        after=_snapshot(certificate, _CERTIFICATE_FIELDS),
    )
    return certificate


def reject_certificate(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    certificate_id: uuid.UUID,
    reason: str,
) -> Certificate:
    """Refuse a submitted valuation, with the reason on the record."""
    lock_project(session, project.id)
    certificate = get_certificate(session, project=project, certificate_id=certificate_id)
    if certificate.status != CERTIFICATE_SUBMITTED:
        raise ConflictError("Only a submitted certificate can be rejected.")
    before = _snapshot(certificate, _CERTIFICATE_FIELDS)
    certificate.status = CERTIFICATE_REJECTED
    certificate.rejected_at = _now()
    certificate.rejected_by_user_id = actor.user_id
    certificate.rejection_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action="construction.certificate_rejected",
        entity_type=ENTITY_CERTIFICATE,
        entity_id=certificate.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(certificate, _CERTIFICATE_FIELDS),
    )
    return certificate


def reverse_certificate(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    certificate_id: uuid.UUID,
    reason: str,
) -> Certificate:
    """Undo a certification, if nothing downstream is standing on it.

    Refused while an invoice claims against it or a certified milestone
    evidences it. Both are cases where the certificate has already become
    somebody else's fact — a liability on the ledger, or a due date on a buyer's
    schedule — and removing it underneath them would leave an invoice claiming
    against nothing or an instalment due for a milestone that is no longer
    certified. The downstream record is corrected first, deliberately, because a
    partial unwind is worse than a refusal.
    """
    lock_project(session, project.id)
    certificate = get_certificate(session, project=project, certificate_id=certificate_id)
    if certificate.status != CERTIFICATE_CERTIFIED:
        raise ConflictError("Only a certified certificate can be reversed.")

    claiming = session.scalars(
        select(Invoice.invoice_number)
        .where(
            Invoice.certificate_id == certificate.id,
            Invoice.status.in_(tuple(INVOICE_STANDING)),
        )
        .limit(1)
    ).first()
    if claiming is not None:
        raise ConflictError(
            f"Invoice {claiming} claims against this certificate. Void or resolve the "
            "invoice first — a claim against a certificate that no longer exists is "
            "a liability nobody can trace."
        )
    evidencing = session.scalars(
        select(Milestone.code)
        .where(
            Milestone.linked_certificate_id == certificate.id,
            Milestone.status == MILESTONE_CERTIFIED,
        )
        .limit(1)
    ).first()
    if evidencing is not None:
        raise ConflictError(
            f"Milestone {evidencing} is certified against this certificate, and a "
            "buyer's schedule may already be due because of it. That has to be "
            "corrected through the contractual records before this certificate can "
            "be reversed."
        )

    before = _snapshot(certificate, _CERTIFICATE_FIELDS)
    certificate.status = CERTIFICATE_REVERSED
    certificate.reversed_at = _now()
    certificate.reversed_by_user_id = actor.user_id
    certificate.reversal_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action="construction.certificate_reversed",
        entity_type=ENTITY_CERTIFICATE,
        entity_id=certificate.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(certificate, _CERTIFICATE_FIELDS),
    )
    return certificate


# --------------------------------------------------------------------------- #
# Invoices
# --------------------------------------------------------------------------- #


def list_invoices(
    session: Session, *, project: Project, contract_id: uuid.UUID | None = None
) -> list[Invoice]:
    """The project's payables, newest first."""
    statement = select(Invoice).where(Invoice.project_id == project.id)
    if contract_id is not None:
        statement = statement.where(Invoice.contract_id == contract_id)
    return list(session.scalars(statement.order_by(Invoice.invoice_date.desc())))


def get_invoice(session: Session, *, project: Project, invoice_id: uuid.UUID) -> Invoice:
    """Load one invoice of this project, or refuse as if it did not exist."""
    invoice = session.scalars(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.project_id == project.id)
    ).first()
    if invoice is None:
        raise permissions.invoice_not_found()
    return invoice


def _lock_invoice(session: Session, *, project_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    """Take an invoice for update, after the project and contract locks above it."""
    invoice = session.scalars(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if invoice is None:
        raise permissions.invoice_not_found()
    return invoice


def invoice_allocated(session: Session, *, invoice_id: uuid.UUID) -> Decimal:
    """Confirmed, unreversed cash applied to one invoice."""
    total = session.scalars(
        select(func.sum(PaymentAllocation.amount))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(
            PaymentAllocation.invoice_id == invoice_id,
            Payment.status == PAYMENT_CONFIRMED,
        )
    ).first()
    return money(total or ZERO)


def invoice_outstanding(session: Session, *, invoice: Invoice) -> Decimal:
    """What an invoice still owes after confirmed cash."""
    return calculator.outstanding(
        payable=calculator.invoice_payable(
            amount_ex_tax=invoice.amount_ex_tax, tax=invoice.tax_amount
        ),
        allocated=invoice_allocated(session, invoice_id=invoice.id),
    )


def record_invoice(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    contract_id: uuid.UUID,
    invoice_number: str,
    invoice_type: str,
    invoice_date: date,
    amount_ex_tax: Decimal,
    tax_amount: Decimal = ZERO,
    certificate_id: uuid.UUID | None = None,
    due_date: date | None = None,
    accounting_reference: str | None = None,
    notes: str | None = None,
) -> Invoice:
    """Enter a claim. Recorded is a document, not yet a liability."""
    lock_project(session, project.id)
    contract = get_contract(session, project=project, contract_id=contract_id)
    certificate: Certificate | None = None
    if certificate_id is not None:
        certificate = get_certificate(session, project=project, certificate_id=certificate_id)
        if certificate.contract_id != contract.id:
            raise permissions.certificate_not_found()
        if certificate.status != CERTIFICATE_CERTIFIED:
            raise ConflictError(
                "An invoice can only claim against a certificate that has actually been certified."
            )
    elif invoice_type in INVOICE_NEEDS_CERTIFICATE:
        raise ValidationError(
            "A progress, retention release or final invoice must name the "
            "certificate that authorises it."
        )

    invoice = Invoice(
        project_id=project.id,
        contract_id=contract.id,
        certificate_id=certificate.id if certificate is not None else None,
        invoice_number=invoice_number.strip(),
        invoice_type=invoice_type,
        invoice_date=invoice_date,
        due_date=due_date,
        amount_ex_tax=money(amount_ex_tax),
        tax_amount=money(tax_amount),
        accounting_reference=(accounting_reference or "").strip() or None,
        notes=(notes or "").strip() or None,
        status=INVOICE_RECORDED,
        recorded_by_user_id=actor.user_id,
    )
    session.add(invoice)
    _flush(session)
    record_event(
        session,
        action="construction.invoice_recorded",
        entity_type=ENTITY_INVOICE,
        entity_id=invoice.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(invoice, _INVOICE_FIELDS),
    )
    return invoice


def approve_invoice(
    session: Session, *, project: Project, actor: ActorContext, invoice_id: uuid.UUID
) -> Invoice:
    """Turn a recorded claim into a liability, within what authorised it.

    A progress claim is capped by the certificate it names: the standing
    invoices against that certificate, plus this one, may not exceed its net
    due. An advance is capped by the contract's entitlement. Both are read under
    lock, because two claims approved against the same certificate is the same
    race as two variations against the same headroom.
    """
    lock_project(session, project.id)
    invoice = _lock_invoice(session, project_id=project.id, invoice_id=invoice_id)
    if invoice.status != INVOICE_RECORDED:
        raise ConflictError("Only a recorded invoice can be approved.")
    contract = _lock_contract(session, project_id=project.id, contract_id=invoice.contract_id)
    payable = calculator.invoice_payable(
        amount_ex_tax=invoice.amount_ex_tax, tax=invoice.tax_amount
    )

    if invoice.certificate_id is not None:
        certificate = get_certificate(
            session, project=project, certificate_id=invoice.certificate_id
        )
        amounts = certificate_amounts(session, contract=contract, certificate=certificate)
        claimed = session.scalars(
            select(func.sum(Invoice.amount_ex_tax + Invoice.tax_amount)).where(
                Invoice.certificate_id == certificate.id,
                Invoice.id != invoice.id,
                Invoice.status.in_(tuple(INVOICE_STANDING)),
            )
        ).first()
        already = money(claimed or ZERO)
        if money(already + payable) > amounts.net_due:
            raise ConflictError(
                f"Certificate {certificate.certificate_number} authorises "
                f"{amounts.net_due}; {already} is already claimed against it, so this "
                f"invoice of {payable} would exceed it."
            )
    elif invoice.invoice_type == INVOICE_ADVANCE:
        claimed = session.scalars(
            select(func.sum(Invoice.amount_ex_tax)).where(
                Invoice.contract_id == contract.id,
                Invoice.invoice_type == INVOICE_ADVANCE,
                Invoice.id != invoice.id,
                Invoice.status.in_(tuple(INVOICE_STANDING)),
            )
        ).first()
        already = money(claimed or ZERO)
        if money(already + invoice.amount_ex_tax) > contract.advance_entitlement_amount:
            raise ConflictError(
                f"This contract entitles the vendor to "
                f"{contract.advance_entitlement_amount} in advance; {already} is "
                "already claimed."
            )

    before = _snapshot(invoice, _INVOICE_FIELDS)
    invoice.status = INVOICE_APPROVED
    invoice.approved_at = _now()
    invoice.approved_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.invoice_approved",
        entity_type=ENTITY_INVOICE,
        entity_id=invoice.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(invoice, _INVOICE_FIELDS),
    )
    return invoice


def dispute_invoice(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    invoice_id: uuid.UUID,
    reason: str,
) -> Invoice:
    """Mark an approved liability as under argument. It still stands.

    Disputing does not reduce what the developer owes and does not remove the
    invoice from the payable position. It blocks payment while the argument
    runs, and nothing else — an obligation that vanished the moment somebody
    objected to it would make the ledger a record of opinions.
    """
    lock_project(session, project.id)
    invoice = _lock_invoice(session, project_id=project.id, invoice_id=invoice_id)
    if invoice.status != INVOICE_APPROVED:
        raise ConflictError("Only an approved invoice can be disputed.")
    before = _snapshot(invoice, _INVOICE_FIELDS)
    invoice.status = INVOICE_DISPUTED
    invoice.disputed_at = _now()
    invoice.disputed_by_user_id = actor.user_id
    invoice.dispute_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action="construction.invoice_disputed",
        entity_type=ENTITY_INVOICE,
        entity_id=invoice.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(invoice, _INVOICE_FIELDS),
    )
    return invoice


def resolve_invoice_dispute(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    invoice_id: uuid.UUID,
    reason: str,
) -> Invoice:
    """End an argument and return the invoice to the payment queue."""
    lock_project(session, project.id)
    invoice = _lock_invoice(session, project_id=project.id, invoice_id=invoice_id)
    if invoice.status != INVOICE_DISPUTED:
        raise ConflictError("Only a disputed invoice can be resolved.")
    before = _snapshot(invoice, _INVOICE_FIELDS)
    invoice.status = INVOICE_APPROVED
    invoice.dispute_resolved_at = _now()
    invoice.dispute_resolution_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action="construction.invoice_dispute_resolved",
        entity_type=ENTITY_INVOICE,
        entity_id=invoice.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(invoice, _INVOICE_FIELDS),
    )
    return invoice


def void_invoice(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    invoice_id: uuid.UUID,
    reason: str,
) -> Invoice:
    """Withdraw an invoice that should never have stood. Never a delete."""
    lock_project(session, project.id)
    invoice = _lock_invoice(session, project_id=project.id, invoice_id=invoice_id)
    if invoice.status == INVOICE_VOIDED:
        raise ConflictError("This invoice is already void.")
    allocated = invoice_allocated(session, invoice_id=invoice.id)
    if allocated != ZERO:
        raise ConflictError(
            f"{allocated} of confirmed cash is applied to this invoice. Reverse the "
            "payment first — voiding it here would leave cash allocated to an "
            "invoice that no longer stands."
        )
    before = _snapshot(invoice, _INVOICE_FIELDS)
    invoice.status = INVOICE_VOIDED
    invoice.voided_at = _now()
    invoice.voided_by_user_id = actor.user_id
    invoice.void_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action="construction.invoice_voided",
        entity_type=ENTITY_INVOICE,
        entity_id=invoice.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(invoice, _INVOICE_FIELDS),
    )
    return invoice


# --------------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------------- #


def list_payments(
    session: Session, *, project: Project, contract_id: uuid.UUID | None = None
) -> list[Payment]:
    """The project's disbursements, newest first."""
    statement = select(Payment).where(Payment.project_id == project.id)
    if contract_id is not None:
        statement = statement.where(Payment.contract_id == contract_id)
    return list(session.scalars(statement.order_by(Payment.payment_date.desc())))


def get_payment(session: Session, *, project: Project, payment_id: uuid.UUID) -> Payment:
    """Load one payment of this project, or refuse as if it did not exist."""
    payment = session.scalars(
        select(Payment).where(Payment.id == payment_id, Payment.project_id == project.id)
    ).first()
    if payment is None:
        raise permissions.payment_not_found()
    return payment


def _lock_payment(session: Session, *, project_id: uuid.UUID, payment_id: uuid.UUID) -> Payment:
    """Take a payment for update, after the project and contract locks above it."""
    payment = session.scalars(
        select(Payment)
        .where(Payment.id == payment_id, Payment.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if payment is None:
        raise permissions.payment_not_found()
    return payment


def payment_allocated(session: Session, *, payment_id: uuid.UUID) -> Decimal:
    """What one payment has been applied to, whatever its status."""
    total = session.scalars(
        select(func.sum(PaymentAllocation.amount)).where(PaymentAllocation.payment_id == payment_id)
    ).first()
    return money(total or ZERO)


def record_payment(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    contract_id: uuid.UUID,
    payment_reference: str,
    payment_date: date,
    amount: Decimal,
    currency_id: uuid.UUID,
    value_date: date | None = None,
    bank_reference: str | None = None,
    proof_reference: str | None = None,
    notes: str | None = None,
) -> Payment:
    """Prepare a disbursement. Recorded is not paid."""
    lock_project(session, project.id)
    contract = get_contract(session, project=project, contract_id=contract_id)
    if currency_id != contract.currency_id:
        raise ValidationError(
            "A payment must be denominated in the contract's currency. There are no "
            "exchange rates in this platform, so a second denomination could not be "
            "applied to the invoice it is meant to settle."
        )
    payment = Payment(
        project_id=project.id,
        contract_id=contract.id,
        payment_reference=payment_reference.strip(),
        payment_date=payment_date,
        value_date=value_date,
        amount=money(amount),
        currency_id=currency_id,
        bank_reference=(bank_reference or "").strip() or None,
        proof_reference=(proof_reference or "").strip() or None,
        notes=(notes or "").strip() or None,
        status=PAYMENT_RECORDED,
        recorded_by_user_id=actor.user_id,
    )
    session.add(payment)
    _flush(session)
    record_event(
        session,
        action="construction.payment_recorded",
        entity_type=ENTITY_PAYMENT,
        entity_id=payment.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(payment, _PAYMENT_FIELDS),
    )
    return payment


def allocate_payment(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    payment_id: uuid.UUID,
    invoice_id: uuid.UUID,
    amount: Decimal,
) -> PaymentAllocation:
    """Say which invoice part of a recorded payment is settling."""
    lock_project(session, project.id)
    payment = _lock_payment(session, project_id=project.id, payment_id=payment_id)
    if payment.status != PAYMENT_RECORDED:
        raise ConflictError(
            "Only a recorded payment can be allocated. A confirmed payment's "
            "allocations are what it settled and stay as they are."
        )
    invoice = _lock_invoice(session, project_id=project.id, invoice_id=invoice_id)
    if invoice.contract_id != payment.contract_id:
        raise permissions.invoice_not_found()

    allocation = session.scalars(
        select(PaymentAllocation).where(
            PaymentAllocation.payment_id == payment.id,
            PaymentAllocation.invoice_id == invoice.id,
        )
    ).first()
    if allocation is None:
        allocation = PaymentAllocation(
            project_id=project.id,
            contract_id=payment.contract_id,
            payment_id=payment.id,
            invoice_id=invoice.id,
            amount=money(amount),
            created_by_user_id=actor.user_id,
        )
        session.add(allocation)
    else:
        allocation.amount = money(amount)
    _flush(session)
    return allocation


def remove_allocation(
    session: Session, *, project: Project, payment_id: uuid.UUID, invoice_id: uuid.UUID
) -> None:
    """Take an invoice off a payment that has not been confirmed."""
    lock_project(session, project.id)
    payment = _lock_payment(session, project_id=project.id, payment_id=payment_id)
    if payment.status != PAYMENT_RECORDED:
        raise ConflictError("Only a recorded payment's allocations can be changed.")
    allocation = session.scalars(
        select(PaymentAllocation).where(
            PaymentAllocation.payment_id == payment.id,
            PaymentAllocation.invoice_id == invoice_id,
        )
    ).first()
    if allocation is None:
        raise permissions.invoice_not_found()
    session.delete(allocation)
    _flush(session)


def confirm_payment(
    session: Session, *, project: Project, actor: ActorContext, payment_id: uuid.UUID
) -> Payment:
    """Confirm that cash has left. Four proofs, all under lock.

    * **A different person.** The recorder may not confirm. This is money
      leaving the company and one person who can both prepare and release a
      disbursement is the control failure every construction fraud case has in
      common.
    * **Exactly allocated.** The allocations must equal the payment to the cent.
      Unapplied cash arriving is a real state somebody must report; unapplied
      cash *leaving* is a payment nobody can explain.
    * **Nothing disputed.** An invoice under argument is not paid while the
      argument runs.
    * **No overpayment.** Each invoice's confirmed allocations, including this
      payment's, may not exceed what it owes — read under the invoice's lock, so
      two payments cannot each see the same outstanding balance.
    """
    lock_project(session, project.id)
    payment = _lock_payment(session, project_id=project.id, payment_id=payment_id)
    if payment.status != PAYMENT_RECORDED:
        raise ConflictError("Only a recorded payment can be confirmed.")
    permissions.require_different_confirmer(actor, recorded_by_user_id=payment.recorded_by_user_id)

    allocations = list(
        session.scalars(select(PaymentAllocation).where(PaymentAllocation.payment_id == payment.id))
    )
    allocated = money(sum((row.amount for row in allocations), ZERO))
    if allocated != payment.amount:
        raise ValidationError(
            f"This payment is {payment.amount} and {allocated} of it is allocated. "
            "A construction disbursement must say in full which obligations it "
            "settles before it is released."
        )

    for allocation in allocations:
        invoice = _lock_invoice(session, project_id=project.id, invoice_id=allocation.invoice_id)
        if invoice.status == INVOICE_DISPUTED:
            raise ConflictError(
                f"Invoice {invoice.invoice_number} is under dispute and cannot be "
                "paid until the dispute is resolved."
            )
        if invoice.status != INVOICE_APPROVED:
            raise ConflictError(f"Invoice {invoice.invoice_number} is not an approved liability.")
        owing = invoice_outstanding(session, invoice=invoice)
        if allocation.amount > owing:
            raise ConflictError(
                f"Invoice {invoice.invoice_number} owes {owing}; this payment would "
                f"apply {allocation.amount} to it."
            )

    before = _snapshot(payment, _PAYMENT_FIELDS)
    payment.status = PAYMENT_CONFIRMED
    payment.confirmed_at = _now()
    payment.confirmed_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.payment_confirmed",
        entity_type=ENTITY_PAYMENT,
        entity_id=payment.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(payment, _PAYMENT_FIELDS),
    )
    return payment


def reverse_payment(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    payment_id: uuid.UUID,
    reason: str,
) -> Payment:
    """Undo a confirmed payment, reopening what it had settled.

    The allocations stay. They are the evidence of what this payment had been
    applied against, and deleting them would erase the reason the reversal
    mattered — the invoice simply stops counting them as settled.

    Refused where an advance payment's reversal would leave more advance
    recovered on certified valuations than advance cash paid. That would put the
    contract's advance position below zero, which is not a state anybody can
    explain: the valuation that recovered it must be corrected first.
    """
    lock_project(session, project.id)
    payment = _lock_payment(session, project_id=project.id, payment_id=payment_id)
    if payment.status != PAYMENT_CONFIRMED:
        raise ConflictError("Only a confirmed payment can be reversed.")

    advance_here = session.scalars(
        select(func.sum(PaymentAllocation.amount))
        .join(Invoice, Invoice.id == PaymentAllocation.invoice_id)
        .where(
            PaymentAllocation.payment_id == payment.id,
            Invoice.invoice_type == INVOICE_ADVANCE,
        )
    ).first()
    advance_here = money(advance_here or ZERO)
    if advance_here > ZERO:
        paid, recovered = advance_position(
            session, project_id=project.id, contract_id=payment.contract_id
        )
        if money(paid - advance_here) < recovered:
            raise ConflictError(
                f"Reversing this payment would leave {recovered} of advance recovered "
                f"against {money(paid - advance_here)} of advance cash paid. Correct "
                "the certificate that recovered it first."
            )

    before = _snapshot(payment, _PAYMENT_FIELDS)
    payment.status = PAYMENT_REVERSED
    payment.reversed_at = _now()
    payment.reversed_by_user_id = actor.user_id
    payment.reversal_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action="construction.payment_reversed",
        entity_type=ENTITY_PAYMENT,
        entity_id=payment.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(payment, _PAYMENT_FIELDS),
    )
    return payment
