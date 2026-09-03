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
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
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
    CATEGORY_HARD,
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
    ENTITY_FORECAST,
    ENTITY_INVOICE,
    ENTITY_MILESTONE,
    ENTITY_PAYMENT,
    ENTITY_VARIATION,
    FORECAST_ACTIVE,
    FORECAST_APPROVED,
    FORECAST_DRAFT,
    FORECAST_FROZEN,
    FORECAST_OPEN,
    FORECAST_REJECTED,
    FORECAST_SUBMITTED,
    FORECAST_SUPERSEDED,
    INVOICE_ADVANCE,
    INVOICE_APPROVED,
    INVOICE_DISPUTED,
    INVOICE_NEEDS_CERTIFICATE,
    INVOICE_RECORDED,
    INVOICE_STANDING,
    INVOICE_VOIDED,
    MILESTONE_ACHIEVED,
    MILESTONE_CANCELLED,
    MILESTONE_CERTIFIED,
    MILESTONE_PLANNED,
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
    ForecastLine,
    ForecastVersion,
    Invoice,
    Milestone,
    MilestoneDependency,
    Payment,
    PaymentAllocation,
    Variation,
    VariationLine,
)
from app.modules.inventory import service as inventory_service
from app.modules.inventory.custom_fields import business_today
from app.modules.inventory.models import Building, Floor, Phase, Unit
from app.modules.inventory.permissions import visible_phase_ids
from app.modules.payment_plans import service as payment_plans_service
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

_FORECAST_FIELDS = (
    "version_number",
    "status",
    "as_of_date",
    "change_reason",
)

_MILESTONE_FIELDS = (
    "code",
    "name",
    "milestone_type",
    "planned_date",
    "forecast_date",
    "actual_achieved_date",
    "certified_date",
    "progress_fraction",
    "status",
)

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


def require_valid_scope(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    phase_id: uuid.UUID | None,
    building_id: uuid.UUID | None,
) -> None:
    """Prove a phase and building actually go together, and that the caller sees them.

    Proving each half belongs to the project is not the same as proving they
    belong to each other. Phase A paired with a building from Phase B satisfies
    two independent project checks and is still nonsense — the cost code or
    milestone would report against a phase whose buildings do not include it.

    A database check cannot hold this: it spans ``phases`` and ``buildings``,
    which is why the constraint that used to sit on the milestone was written as
    a tautology and protected nothing. It is proved here, against the rows.

    Visibility is proved in the same place, because a phase-scoped engineer
    naming a phase they cannot see is the same mistake wearing a different hat.
    """
    allowed = visible_phase_ids(session, project_id=project.id, actor=actor)

    phase: Phase | None = None
    if phase_id is not None:
        statement = select(Phase).where(Phase.id == phase_id, Phase.project_id == project.id)
        if allowed is not None:
            statement = statement.where(Phase.id.in_(allowed))
        phase = session.scalars(statement).first()
        if phase is None:
            raise NotFoundError("Phase not found.")

    if building_id is not None:
        statement = select(Building).where(
            Building.id == building_id, Building.project_id == project.id
        )
        if allowed is not None:
            statement = statement.where(Building.phase_id.in_(allowed))
        building = session.scalars(statement).first()
        if building is None:
            raise NotFoundError("Building not found.")
        if phase is not None and building.phase_id != phase.id:
            raise ValidationError(
                "That building belongs to a different phase. A record scoped to one "
                "phase and a building in another would report against a phase whose "
                "buildings do not include it."
            )


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
    require_valid_scope(
        session, project=project, actor=actor, phase_id=phase_id, building_id=building_id
    )
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

    if "phase_id" in changes or "building_id" in changes:
        require_valid_scope(
            session,
            project=project,
            actor=actor,
            phase_id=changes.get("phase_id", row.phase_id),
            building_id=changes.get("building_id", row.building_id),
        )

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
    # ForecastLine belongs here as much as the other four. A cost code used
    # only by a forecast still has its meaning fixed by it: changing the code
    # renames what a historical estimate was about, and changing the category
    # can move the money in or out of the hard-cost total unit economics reads.
    for model in (BudgetLine, ContractLine, VariationLine, CertificateLine, ForecastLine):
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

    # An opening version may carry a historical date: the project may have been
    # building for two years before this module existed. A replacement may not,
    # because the period it would claim to govern has already been lived under
    # the budget that actually governed it, and commitments were authorised
    # against that one. Today or later, never yesterday.
    if (
        active_budget(session, project_id=project.id) is not None
        and effective_date < business_today()
    ):
        raise ValidationError(
            f"A replacement budget cannot take effect on {effective_date}, which has "
            "already passed. The budget in force governed that period and commitments "
            "were authorised against it; a replacement takes effect today or later."
        )

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


def _require_cost_code_coverage(
    session: Session, *, project: Project, version: BudgetVersion
) -> None:
    """Refuse a budget that leaves an active cost code unaddressed.

    A missing line and a line of zero are different statements, and only one of
    them is an answer. "Nothing is authorised for this code" is a decision
    somebody made; "nobody wrote a line for this code" is an omission, and a
    register that renders both as an empty cell cannot tell them apart — which
    is exactly the ambiguity the whole versioned-budget design exists to remove.

    Only *active* codes are required. A retired code keeps reading everywhere it
    was used and does not force a line into a version that has no business
    authorising it.
    """
    active = {
        code.id: code.code
        for code in session.scalars(
            select(CostCode).where(CostCode.project_id == project.id, CostCode.is_active.is_(True))
        )
    }
    addressed = set(budget_lines_by_cost_code(session, budget_version_id=version.id))
    missing = sorted(label for code_id, label in active.items() if code_id not in addressed)
    if missing:
        raise ValidationError(
            "Every active cost code needs a line, even if the answer is zero — "
            + ", ".join(missing)
            + ". An omitted line is not the same statement as an authorisation of "
            "nothing, and a budget that cannot tell them apart cannot be read."
        )


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
    _require_cost_code_coverage(session, project=project, version=version)

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
    # Re-proved rather than trusted from submission: a cost code created while
    # the version sat waiting for approval is a code this budget does not
    # authorise, and activating anyway would put a commitment one step away from
    # a line nobody wrote.
    _require_cost_code_coverage(session, project=project, version=version)

    today = business_today()
    if version.effective_date > today:
        raise ConflictError(
            f"This budget takes effect on {version.effective_date}. It stays approved "
            "until then — nothing here schedules an activation, because a budget "
            "coming into force is a decision somebody takes on the day."
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
    # Activating is the act that commits the company. The person who prepared
    # the contract may hold every role in the system and is still one pair of
    # eyes, so the check is on the identifier rather than on what they may do.
    permissions.require_different_approver(
        actor, submitted_by_user_id=contract.submitted_by_user_id
    )
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

    # A signed variation may reduce a commitment, but not into nonsense and not
    # below work that has already been formally certified. Certification is a
    # statement that work was done and authorised; a later omission cannot make
    # that history unauthorised after the fact, and a contract cannot commit a
    # negative amount at all.
    committed = contract_committed_by_cost_code(
        session, project_id=project.id, contract_id=contract.id
    )
    certified = certified_by_cost_code(session, project_id=project.id, contract_id=contract.id)
    below: list[str] = []
    for cost_code_id, delta in deltas.items():
        if delta >= ZERO:
            continue
        code = session.get(CostCode, cost_code_id)
        label = code.code if code is not None else str(cost_code_id)
        after = money(committed.get(cost_code_id, ZERO) + delta)
        if after < ZERO:
            below.append(f"{label}: would commit {after}")
            continue
        standing = certified.get(cost_code_id, ZERO)
        if after < standing:
            below.append(f"{label}: would leave {after} committed against {standing} certified")
    if below:
        raise ConflictError(
            "This variation would reduce the commitment below what has already been "
            "certified, or below zero — "
            + "; ".join(sorted(below))
            + ". Work that has been certified was authorised when it was certified, "
            "and an omission cannot take that authorisation away afterwards."
        )

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
            "Every invoice except an advance must name the certified certificate "
            "that authorises it. An invoice with no ceiling is a liability made "
            "out of nothing."
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
    # Approving turns a document into a liability the company owes. Same
    # discipline as confirming the payment that later settles it.
    permissions.require_different_invoice_approver(
        actor, recorded_by_user_id=invoice.recorded_by_user_id
    )
    contract = _lock_contract(session, project_id=project.id, contract_id=invoice.contract_id)
    payable = calculator.invoice_payable(
        amount_ex_tax=invoice.amount_ex_tax, tax=invoice.tax_amount
    )

    if invoice.certificate_id is not None:
        certificate = get_certificate(
            session, project=project, certificate_id=invoice.certificate_id
        )
        # Re-read rather than trusted from when the invoice was entered. A
        # recorded invoice is only a document, so it does not block a reversal
        # of the certificate it names — which leaves exactly this window:
        # reverse the certification, then approve the claim, and the liability
        # rests on an authorisation that has been withdrawn.
        if certificate.status != CERTIFICATE_CERTIFIED:
            raise ConflictError(
                f"Certificate {certificate.certificate_number} is no longer certified, "
                "so it authorises nothing. Record the claim against the certificate "
                "that does."
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


# --------------------------------------------------------------------------- #
# Milestones
# --------------------------------------------------------------------------- #


def list_milestones(session: Session, *, project: Project) -> list[Milestone]:
    """The project's milestones, in planned order."""
    return list(
        session.scalars(
            select(Milestone)
            .where(Milestone.project_id == project.id)
            .order_by(Milestone.planned_date.nulls_last(), Milestone.code)
        )
    )


def get_milestone(session: Session, *, project: Project, milestone_id: uuid.UUID) -> Milestone:
    """Load one milestone of this project, or refuse as if it did not exist."""
    milestone = session.scalars(
        select(Milestone).where(Milestone.id == milestone_id, Milestone.project_id == project.id)
    ).first()
    if milestone is None:
        raise permissions.milestone_not_found()
    return milestone


def milestone_delay_days(milestone: Milestone, *, today: date) -> int | None:
    """How late a milestone is against its plan, in days. Derived, never stored.

    One precedence, stated once and used everywhere: the date it was actually
    certified or achieved if it has one, else its forecast, else today where the
    planned date has already passed. A milestone with no plan has no delay —
    there is nothing to be late against, and returning zero would say it was on
    time.
    """
    if milestone.planned_date is None:
        return None
    against = milestone.certified_date or milestone.actual_achieved_date or milestone.forecast_date
    if against is None:
        against = today if today > milestone.planned_date else milestone.planned_date
    return (against - milestone.planned_date).days


def create_milestone(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    code: str,
    name: str,
    milestone_type: str,
    phase_id: uuid.UUID | None = None,
    building_id: uuid.UUID | None = None,
    planned_date: date | None = None,
    forecast_date: date | None = None,
    notes: str | None = None,
) -> Milestone:
    """Add a milestone. Its code is its handle for ever after."""
    lock_project(session, project.id)
    require_valid_scope(
        session, project=project, actor=actor, phase_id=phase_id, building_id=building_id
    )
    milestone = Milestone(
        project_id=project.id,
        code=code.strip(),
        name=name.strip(),
        milestone_type=milestone_type,
        phase_id=phase_id,
        building_id=building_id,
        planned_date=planned_date,
        forecast_date=forecast_date,
        notes=(notes or "").strip() or None,
        status=MILESTONE_PLANNED,
        created_by_user_id=actor.user_id,
    )
    session.add(milestone)
    _flush(session)
    record_event(
        session,
        action="construction.milestone_created",
        entity_type=ENTITY_MILESTONE,
        entity_id=milestone.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(milestone, _MILESTONE_FIELDS),
    )
    return milestone


def update_milestone(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    milestone_id: uuid.UUID,
    changes: dict[str, object],
) -> Milestone:
    """Amend a milestone's planning fields.

    ``code`` is refused outright. A payment plan written years ago may point at
    it through ``trigger_reference``, and renaming it would silently detach a
    live contractual schedule from the event that triggers it — a failure that
    surfaces as an instalment that never falls due, which is exactly the kind of
    thing nobody notices until a buyer stops paying.
    """
    lock_project(session, project.id)
    milestone = get_milestone(session, project=project, milestone_id=milestone_id)
    if "code" in changes and changes["code"] != milestone.code:
        raise ConflictError(
            "A milestone's code is the handle payment plans use to point at it and "
            "cannot be changed. Create a new milestone if the breakdown has changed."
        )
    if milestone.status == MILESTONE_CERTIFIED:
        raise ConflictError("A certified milestone is a record of what happened.")
    if "phase_id" in changes or "building_id" in changes:
        require_valid_scope(
            session,
            project=project,
            actor=actor,
            phase_id=changes.get("phase_id", milestone.phase_id),
            building_id=changes.get("building_id", milestone.building_id),
        )
    before = _snapshot(milestone, _MILESTONE_FIELDS)
    for field, value in changes.items():
        if field == "code":
            continue
        setattr(milestone, field, value)
    _flush(session)
    record_event(
        session,
        action="construction.milestone_updated",
        entity_type=ENTITY_MILESTONE,
        entity_id=milestone.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(milestone, _MILESTONE_FIELDS),
    )
    return milestone


def achieve_milestone(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    milestone_id: uuid.UUID,
    achieved_date: date,
    evidence_reference: str | None = None,
) -> Milestone:
    """Record that site says the work is done. This triggers nothing.

    The gap between this and certification is the control the module exists to
    keep. Somebody on site reporting that a floor is complete is information;
    it is not the formal certification a buyer's contract makes their money
    depend on, and nothing here touches a payment plan.
    """
    lock_project(session, project.id)
    milestone = get_milestone(session, project=project, milestone_id=milestone_id)
    if milestone.status in (MILESTONE_CERTIFIED, MILESTONE_CANCELLED):
        raise ConflictError("This milestone is already closed.")
    before = _snapshot(milestone, _MILESTONE_FIELDS)
    milestone.status = MILESTONE_ACHIEVED
    milestone.actual_achieved_date = achieved_date
    milestone.achieved_at = _now()
    milestone.achieved_by_user_id = actor.user_id
    if evidence_reference is not None:
        milestone.evidence_reference = evidence_reference.strip() or None
    _flush(session)
    record_event(
        session,
        action="construction.milestone_achieved",
        entity_type=ENTITY_MILESTONE,
        entity_id=milestone.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(milestone, _MILESTONE_FIELDS),
    )
    return milestone


def certify_milestone(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    milestone_id: uuid.UUID,
    certified_date: date,
    evidence_reference: str | None = None,
    linked_certificate_id: uuid.UUID | None = None,
) -> tuple[Milestone, payment_plans_service.MilestoneCertificationResult]:
    """Formally certify a milestone, and make the buyer instalments waiting on it due.

    The two halves are one transaction, deliberately. There is no state in which
    a milestone is certified and a schedule still waits for it, and none in which
    an instalment is due for a milestone that was not certified: if either half
    fails, the caller's rollback discards both.

    Payment plans is reached through its own public contract, so construction
    never writes an instalment column and payment plans never imports
    construction. The dependency runs one way and the buyer's due date is set by
    the module that owns buyers' due dates.

    Re-certifying a milestone that is already certified on the same date is a
    no-op rather than an error, because a retried request should not be a
    failure. Re-certifying on a *different* date is refused: moving a date a
    buyer's receivable, ageing and collection actions already stand on is not
    something to do by accident.
    """
    lock_project(session, project.id)
    milestone = get_milestone(session, project=project, milestone_id=milestone_id)
    if milestone.status == MILESTONE_CANCELLED:
        raise ConflictError("A cancelled milestone cannot be certified.")
    if milestone.status == MILESTONE_CERTIFIED:
        if milestone.certified_date == certified_date:
            return milestone, payment_plans_service.MilestoneCertificationResult(
                triggered_installment_ids=(), plan_ids=()
            )
        raise ConflictError(
            f"This milestone was already certified on {milestone.certified_date}. "
            "A buyer's instalment may already be due on that date, so it cannot be "
            "moved by re-certifying."
        )

    certificate: Certificate | None = None
    if linked_certificate_id is not None:
        certificate = get_certificate(
            session, project=project, certificate_id=linked_certificate_id
        )
        if certificate.status != CERTIFICATE_CERTIFIED:
            raise ConflictError(
                "A milestone can only be evidenced by a certificate that has been certified."
            )

    before = _snapshot(milestone, _MILESTONE_FIELDS)
    milestone.status = MILESTONE_CERTIFIED
    milestone.certified_date = certified_date
    milestone.certified_at = _now()
    milestone.certified_by_user_id = actor.user_id
    if certificate is not None:
        milestone.linked_certificate_id = certificate.id
    if evidence_reference is not None:
        milestone.evidence_reference = evidence_reference.strip() or None
    if milestone.actual_achieved_date is None:
        milestone.actual_achieved_date = certified_date
    _flush(session)

    result = payment_plans_service.apply_construction_milestone_certification(
        session,
        project=project,
        milestone_code=milestone.code,
        certified_date=certified_date,
        evidence_reference=milestone.evidence_reference,
        actor=actor,
        correlation_id=actor.correlation_id,
    )

    record_event(
        session,
        action="construction.milestone_certified",
        entity_type=ENTITY_MILESTONE,
        entity_id=milestone.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=(
            f"{len(result.triggered_installment_ids)} instalment(s) became due on {certified_date}"
        ),
        before=before,
        after=_snapshot(milestone, _MILESTONE_FIELDS),
    )
    return milestone, result


def cancel_milestone(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    milestone_id: uuid.UUID,
    reason: str,
) -> Milestone:
    """Retire a milestone, unless a live payment plan is waiting on it.

    Asked of payment plans through its own read contract rather than guessed
    from a join here. A milestone removed while a contractual schedule still
    points at its code would leave that instalment waiting for an event that can
    never happen — money the buyer owes that the system will never ask for.
    """
    lock_project(session, project.id)
    milestone = get_milestone(session, project=project, milestone_id=milestone_id)
    if milestone.status == MILESTONE_CERTIFIED:
        raise ConflictError("A certified milestone is a record of what happened.")
    waiting = payment_plans_service.plans_awaiting_milestone(
        session, project_id=project.id, milestone_code=milestone.code
    )
    if waiting:
        raise ConflictError(
            f"{len(waiting)} active payment plan(s) are waiting on milestone "
            f"{milestone.code}. Revise those schedules before retiring it, or the "
            "instalments will wait for an event that can no longer happen."
        )
    before = _snapshot(milestone, _MILESTONE_FIELDS)
    milestone.status = MILESTONE_CANCELLED
    milestone.cancelled_at = _now()
    milestone.cancellation_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action="construction.milestone_cancelled",
        entity_type=ENTITY_MILESTONE,
        entity_id=milestone.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(milestone, _MILESTONE_FIELDS),
    )
    return milestone


def add_milestone_dependency(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    milestone_id: uuid.UUID,
    depends_on_milestone_id: uuid.UUID,
) -> MilestoneDependency:
    """Record that one milestone waits on another. Refuses a cycle."""
    lock_project(session, project.id)
    milestone = get_milestone(session, project=project, milestone_id=milestone_id)
    upstream = get_milestone(session, project=project, milestone_id=depends_on_milestone_id)
    if milestone.id == upstream.id:
        raise ValidationError("A milestone cannot depend on itself.")
    _require_no_dependency_cycle(
        session, project_id=project.id, milestone_id=milestone.id, upstream_id=upstream.id
    )
    dependency = MilestoneDependency(
        project_id=project.id,
        milestone_id=milestone.id,
        depends_on_milestone_id=upstream.id,
        created_by_user_id=actor.user_id,
    )
    session.add(dependency)
    _flush(session)
    return dependency


def _require_no_dependency_cycle(
    session: Session, *, project_id: uuid.UUID, milestone_id: uuid.UUID, upstream_id: uuid.UUID
) -> None:
    """Refuse a dependency that would make the programme wait on itself.

    Breadth-first from the proposed upstream milestone: if the milestone being
    edited is reachable from it, adding this edge closes a loop. Not a scheduler
    and not a critical path — one traversal, so a register can be read without a
    dependency chain that never terminates.
    """
    seen: set[uuid.UUID] = set()
    queue: deque[uuid.UUID] = deque([upstream_id])
    while queue:
        current = queue.popleft()
        if current == milestone_id:
            raise ValidationError("That dependency would make the programme wait on itself.")
        if current in seen:
            continue
        seen.add(current)
        for (next_id,) in session.execute(
            select(MilestoneDependency.depends_on_milestone_id).where(
                MilestoneDependency.milestone_id == current,
                MilestoneDependency.project_id == project_id,
            )
        ).all():
            queue.append(next_id)


def remove_milestone_dependency(
    session: Session,
    *,
    project: Project,
    milestone_id: uuid.UUID,
    depends_on_milestone_id: uuid.UUID,
) -> None:
    """Drop a dependency from a milestone that is not yet certified."""
    lock_project(session, project.id)
    milestone = get_milestone(session, project=project, milestone_id=milestone_id)
    if milestone.status == MILESTONE_CERTIFIED:
        raise ConflictError("A certified milestone's programme is history.")
    dependency = session.scalars(
        select(MilestoneDependency).where(
            MilestoneDependency.milestone_id == milestone.id,
            MilestoneDependency.depends_on_milestone_id == depends_on_milestone_id,
        )
    ).first()
    if dependency is None:
        raise permissions.milestone_not_found()
    session.delete(dependency)
    _flush(session)


def milestone_trigger_options(session: Session, *, project: Project) -> list[Milestone]:
    """The milestones a payment plan may point at, and nothing else.

    Deliberately the whole milestone rows for the caller to narrow: the schema
    that serialises them returns only code, name, scope, dates and certification
    state. A plan builder is used by Sales Operations, who may not read this
    module at all — so the endpoint that exposes this must never hand back a
    budget, a contract value, an estimate at completion or any other cost.
    """
    return list(
        session.scalars(
            select(Milestone)
            .where(
                Milestone.project_id == project.id,
                Milestone.status != MILESTONE_CANCELLED,
            )
            .order_by(Milestone.planned_date.nulls_last(), Milestone.code)
        )
    )


# --------------------------------------------------------------------------- #
# Forecast
# --------------------------------------------------------------------------- #


def list_forecasts(session: Session, *, project: Project) -> list[ForecastVersion]:
    """Every forecast this project has had, newest first."""
    return list(
        session.scalars(
            select(ForecastVersion)
            .where(ForecastVersion.project_id == project.id)
            .order_by(ForecastVersion.version_number.desc())
        )
    )


def get_forecast(session: Session, *, project: Project, version_id: uuid.UUID) -> ForecastVersion:
    """Load one forecast version of this project, or refuse as if it were absent."""
    version = session.scalars(
        select(ForecastVersion).where(
            ForecastVersion.id == version_id, ForecastVersion.project_id == project.id
        )
    ).first()
    if version is None:
        raise permissions.forecast_not_found()
    return version


def active_forecast(session: Session, *, project_id: uuid.UUID) -> ForecastVersion | None:
    """The forecast currently in force, or ``None`` where none has been activated."""
    return session.scalars(
        select(ForecastVersion).where(
            ForecastVersion.project_id == project_id, ForecastVersion.status == FORECAST_ACTIVE
        )
    ).first()


def _lock_forecast(
    session: Session, *, project_id: uuid.UUID, version_id: uuid.UUID
) -> ForecastVersion:
    """Take a forecast version for update, after the project lock above it."""
    version = session.scalars(
        select(ForecastVersion)
        .where(ForecastVersion.id == version_id, ForecastVersion.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if version is None:
        raise permissions.forecast_not_found()
    return version


def forecast_lines_by_cost_code(
    session: Session, *, forecast_version_id: uuid.UUID
) -> dict[uuid.UUID, ForecastLine]:
    """One forecast version's lines, keyed by cost code."""
    return {
        line.cost_code_id: line
        for line in session.scalars(
            select(ForecastLine).where(ForecastLine.forecast_version_id == forecast_version_id)
        )
    }


def create_forecast(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    as_of_date: date,
    change_reason: str,
    budget_version_id: uuid.UUID | None = None,
    source_version_id: uuid.UUID | None = None,
) -> ForecastVersion:
    """Open a forecast, measured against a stated budget as at a stated date.

    Two dates decide everything about a forecast's meaning. ``as_of_date`` fixes
    which certified work is inside its estimate, which is what lets a superseded
    forecast still be reproduced a year later instead of quietly re-deriving
    itself from today's certificates. And the budget version it names fixes what
    its variance is measured against, so "over budget" refers to an
    authorisation somebody can point at rather than whatever happens to be
    current when the screen is opened.

    A future cutoff is refused: a forecast cannot include work that has not been
    certified yet, and a date in the future would silently mean "today" until
    the day arrived and then mean something else.
    """
    lock_project(session, project.id)
    if as_of_date > business_today():
        raise ValidationError(
            "A forecast cannot be taken as at a future date. Its certified basis is "
            "the work certified by its cutoff, and there is none after today."
        )
    if _open_forecast(session, project_id=project.id) is not None:
        raise ConflictError(
            "This project already has a forecast being prepared. Finish or reject it "
            "before opening another."
        )

    budget: BudgetVersion | None
    if budget_version_id is not None:
        budget = get_budget(session, project=project, version_id=budget_version_id)
    else:
        budget = active_budget(session, project_id=project.id)
    if budget is None:
        raise ConflictError(
            "A forecast is measured against an approved budget, and this project has none in force."
        )

    source: ForecastVersion | None = None
    if source_version_id is not None:
        source = get_forecast(session, project=project, version_id=source_version_id)
    elif (current := active_forecast(session, project_id=project.id)) is not None:
        source = current
    if source is not None and as_of_date < source.as_of_date:
        raise ValidationError(
            f"This forecast is taken as at {as_of_date}, before the standing "
            f"forecast's own cutoff of {source.as_of_date}. A replacement looks "
            "forward from where the last one stopped."
        )

    highest = session.scalars(
        select(func.max(ForecastVersion.version_number)).where(
            ForecastVersion.project_id == project.id
        )
    ).first()
    version = ForecastVersion(
        project_id=project.id,
        version_number=(highest or 0) + 1,
        currency_id=project.base_currency_id,
        budget_version_id=budget.id,
        as_of_date=as_of_date,
        status=FORECAST_DRAFT,
        source_version_id=source.id if source is not None else None,
        change_reason=change_reason.strip(),
        created_by_user_id=actor.user_id,
    )
    session.add(version)
    _flush(session)

    if source is not None:
        for line in session.scalars(
            select(ForecastLine).where(ForecastLine.forecast_version_id == source.id)
        ):
            session.add(
                ForecastLine(
                    project_id=project.id,
                    forecast_version_id=version.id,
                    cost_code_id=line.cost_code_id,
                    forecast_remaining_amount_ex_tax=line.forecast_remaining_amount_ex_tax,
                    note=line.note,
                )
            )
        _flush(session)

    record_event(
        session,
        action="construction.forecast_created",
        entity_type=ENTITY_FORECAST,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=change_reason,
        after=_snapshot(version, _FORECAST_FIELDS),
    )
    return version


def _open_forecast(session: Session, *, project_id: uuid.UUID) -> ForecastVersion | None:
    """The forecast being drafted, checked or waiting to be activated."""
    return session.scalars(
        select(ForecastVersion).where(
            ForecastVersion.project_id == project_id,
            ForecastVersion.status.in_(tuple(FORECAST_OPEN)),
        )
    ).first()


def set_forecast_line(
    session: Session,
    *,
    project: Project,
    version_id: uuid.UUID,
    cost_code_id: uuid.UUID,
    forecast_remaining_amount_ex_tax: Decimal,
    note: str | None = None,
) -> ForecastLine:
    """Write what one cost code has left to spend, in Finance's judgement.

    An explicit zero is a statement — nothing further expected here. It is not
    the same as no line, which is why submission refuses until every governed
    code has one.
    """
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    if version.status in FORECAST_FROZEN:
        raise ConflictError(
            "This forecast is no longer a draft. Open a revision to change what the "
            "project expects to spend."
        )
    code = get_cost_code(session, project=project, cost_code_id=cost_code_id)

    line = session.scalars(
        select(ForecastLine).where(
            ForecastLine.forecast_version_id == version.id,
            ForecastLine.cost_code_id == code.id,
        )
    ).first()
    if line is None:
        line = ForecastLine(
            project_id=project.id,
            forecast_version_id=version.id,
            cost_code_id=code.id,
            forecast_remaining_amount_ex_tax=money(forecast_remaining_amount_ex_tax),
            note=(note or "").strip() or None,
        )
        session.add(line)
    else:
        line.forecast_remaining_amount_ex_tax = money(forecast_remaining_amount_ex_tax)
        line.note = (note or "").strip() or None
    _flush(session)
    return line


def _require_forecast_coverage(
    session: Session, *, project: Project, version: ForecastVersion
) -> None:
    """Refuse a forecast that leaves an active cost code unaddressed.

    Same rule as the budget's, for the same reason: "we expect no further cost
    here" and "nobody looked at this code" are different statements, and a
    forecast that cannot tell them apart is a guess wearing a governed
    version number.
    """
    active = {
        code.id: code.code
        for code in session.scalars(
            select(CostCode).where(CostCode.project_id == project.id, CostCode.is_active.is_(True))
        )
    }
    addressed = set(forecast_lines_by_cost_code(session, forecast_version_id=version.id))
    missing = sorted(label for code_id, label in active.items() if code_id not in addressed)
    if missing:
        raise ValidationError(
            "Every active cost code needs a forecast line, even if the answer is "
            "zero — " + ", ".join(missing) + "."
        )


def forecast_position(
    session: Session, *, project: Project, version: ForecastVersion
) -> dict[uuid.UUID, calculator.CostCodePosition]:
    """Each cost code's whole control position on this forecast's own basis.

    Certified work is read as at the version's cutoff rather than as at today,
    which is the property that makes a superseded forecast reproducible: asking
    a year-old forecast what it thought is answered with what it actually
    thought, not with today's certificates run through yesterday's judgement.
    """
    budget = session.get(BudgetVersion, version.budget_version_id)
    budget_lines = (
        budget_lines_by_cost_code(session, budget_version_id=budget.id)
        if budget is not None
        else {}
    )
    committed = committed_by_cost_code(session, project_id=project.id)
    certified = certified_by_cost_code(session, project_id=project.id, as_of=version.as_of_date)
    lines = forecast_lines_by_cost_code(session, forecast_version_id=version.id)

    positions: dict[uuid.UUID, calculator.CostCodePosition] = {}
    for cost_code_id in set(budget_lines) | set(lines) | set(committed) | set(certified):
        budget_line = budget_lines.get(cost_code_id)
        line = lines.get(cost_code_id)
        positions[cost_code_id] = calculator.cost_code_position(
            approved_budget=budget_line.approved_budget_amount if budget_line else ZERO,
            contingency=budget_line.contingency_amount if budget_line else ZERO,
            revised_commitment_amount=committed.get(cost_code_id, ZERO),
            certified_to_date=certified.get(cost_code_id, ZERO),
            forecast_remaining=(
                line.forecast_remaining_amount_ex_tax if line is not None else ZERO
            ),
        )
    return positions


def submit_forecast(
    session: Session, *, project: Project, actor: ActorContext, version_id: uuid.UUID
) -> ForecastVersion:
    """Hand a draft forecast to a checker."""
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    if version.status != FORECAST_DRAFT:
        raise ConflictError("Only a draft forecast can be submitted.")
    _require_forecast_coverage(session, project=project, version=version)

    before = _snapshot(version, _FORECAST_FIELDS)
    version.status = FORECAST_SUBMITTED
    version.submitted_at = _now()
    version.submitted_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.forecast_submitted",
        entity_type=ENTITY_FORECAST,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(version, _FORECAST_FIELDS),
    )
    return version


def approve_forecast(
    session: Session, *, project: Project, actor: ActorContext, version_id: uuid.UUID
) -> ForecastVersion:
    """Sign off a submitted forecast. Not the same act as putting it in force."""
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    if version.status != FORECAST_SUBMITTED:
        raise ConflictError("Only a submitted forecast can be approved.")
    permissions.require_different_approver(actor, submitted_by_user_id=version.submitted_by_user_id)
    before = _snapshot(version, _FORECAST_FIELDS)
    version.status = FORECAST_APPROVED
    version.approved_at = _now()
    version.approved_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.forecast_approved",
        entity_type=ENTITY_FORECAST,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(version, _FORECAST_FIELDS),
    )
    return version


def reject_forecast(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    reason: str,
) -> ForecastVersion:
    """Refuse a submitted forecast, with the reason on the record."""
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    if version.status != FORECAST_SUBMITTED:
        raise ConflictError("Only a submitted forecast can be rejected.")
    permissions.require_different_approver(actor, submitted_by_user_id=version.submitted_by_user_id)
    before = _snapshot(version, _FORECAST_FIELDS)
    version.status = FORECAST_REJECTED
    version.rejected_at = _now()
    version.rejected_by_user_id = actor.user_id
    version.rejection_reason = reason.strip()
    _flush(session)
    record_event(
        session,
        action="construction.forecast_rejected",
        entity_type=ENTITY_FORECAST,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(version, _FORECAST_FIELDS),
    )
    return version


def activate_forecast(
    session: Session, *, project: Project, actor: ActorContext, version_id: uuid.UUID
) -> ForecastVersion:
    """Put an approved forecast into force, superseding the one it replaces.

    Coverage is re-proved here rather than trusted from submission: a cost code
    created while the version waited for approval is a code this forecast does
    not address, and activating anyway would put a project estimate one line
    short without saying so.
    """
    lock_project(session, project.id)
    version = _lock_forecast(session, project_id=project.id, version_id=version_id)
    if version.status != FORECAST_APPROVED:
        raise ConflictError("Only an approved forecast can be activated.")
    if version.currency_id != project.base_currency_id:
        raise ConflictError(
            "This forecast was prepared in a currency the project no longer accounts "
            "in. Prepare a revision in the project's base currency."
        )
    _require_forecast_coverage(session, project=project, version=version)

    current = active_forecast(session, project_id=project.id)
    if current is not None:
        current.status = FORECAST_SUPERSEDED
        current.superseded_at = _now()
        _flush(session)
        record_event(
            session,
            action="construction.forecast_superseded",
            entity_type=ENTITY_FORECAST,
            entity_id=current.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            after=_snapshot(current, _FORECAST_FIELDS),
        )

    before = _snapshot(version, _FORECAST_FIELDS)
    version.status = FORECAST_ACTIVE
    version.activated_at = _now()
    version.activated_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="construction.forecast_activated",
        entity_type=ENTITY_FORECAST,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(version, _FORECAST_FIELDS),
    )
    return version


def hard_cost_estimate_at_completion(
    session: Session, *, project_id: uuid.UUID
) -> tuple[ForecastVersion, Decimal] | None:
    """The project's governed hard-cost estimate at completion, for unit economics.

    The public read contract in the other direction: unit economics may consume
    this, and construction never writes a cost pool. Returns the version as well
    as the amount, because a pool that cannot say which forecast it came from is
    an amount with no provenance — and provenance is what stops a later forecast
    appearing to rewrite a basis units were already sold against.

    ``None`` where no forecast is in force. A missing estimate is a missing
    estimate; answering zero would let a version be built on a hard cost of
    nothing without anybody noticing.
    """
    version = active_forecast(session, project_id=project_id)
    if version is None:
        return None
    return version, hard_cost_estimate_of(session, project_id=project_id, version=version)


def hard_cost_estimate_of(
    session: Session, *, project_id: uuid.UUID, version: ForecastVersion
) -> Decimal:
    """The hard-cost estimate at completion of one named forecast version.

    The second half of the same contract, and the half staleness detection
    needs. A consumer that pinned a forecast has to be able to ask what *that*
    forecast says today, not only what the current one says — otherwise the two
    ways a pinned amount can go wrong are indistinguishable. A newer forecast
    having been activated is a decision somebody made and a basis somebody
    should rebuild on purpose; the pinned forecast's own estimate having moved
    underneath it, because a certificate dated on or before its as-of date was
    reversed or added since, is a figure that was never re-approved. Both are
    stale, and a caller that can only see the first would activate the second.
    """
    total = session.scalars(
        select(func.sum(ForecastLine.forecast_remaining_amount_ex_tax))
        .join(CostCode, CostCode.id == ForecastLine.cost_code_id)
        .where(
            ForecastLine.forecast_version_id == version.id,
            CostCode.cost_category == CATEGORY_HARD,
        )
    ).first()
    remaining = money(total or ZERO)
    certified = session.scalars(
        select(func.sum(CertificateLine.current_work_value_ex_tax))
        .join(Certificate, Certificate.id == CertificateLine.certificate_id)
        .join(CostCode, CostCode.id == CertificateLine.cost_code_id)
        .where(
            CertificateLine.project_id == project_id,
            Certificate.status == CERTIFICATE_CERTIFIED,
            Certificate.certificate_date <= version.as_of_date,
            CostCode.cost_category == CATEGORY_HARD,
        )
    ).first()
    return calculator.estimate_at_completion(
        certified_to_date=money(certified or ZERO), forecast_remaining=remaining
    )


# --------------------------------------------------------------------------- #
# Project position
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CostControl:
    """The project's cost side. Every figure ex tax, without exception."""

    original_baseline: Decimal
    current_approved_budget: Decimal
    approved_contingency: Decimal
    control_budget: Decimal
    original_commitment: Decimal
    approved_variation_delta: Decimal
    revised_commitment: Decimal
    certified_to_date: Decimal
    forecast_remaining: Decimal | None
    estimate_at_completion: Decimal | None
    variance_at_completion: Decimal | None


@dataclass(frozen=True)
class Payable:
    """The project's cash side. These carry tax, retention and deductions."""

    approved_invoice_payable: Decimal
    disputed_invoice_payable: Decimal
    confirmed_paid: Decimal
    invoice_outstanding: Decimal
    retention_outstanding: Decimal
    advance_paid: Decimal
    advance_recovered: Decimal
    advance_outstanding: Decimal


def cost_control_position(session: Session, *, project: Project) -> CostControl:
    """Assemble the project's cost position from the rows, on one basis: ex tax.

    Nothing here is stored and nothing is a running total kept up to date by the
    writes. Each figure is a sum over immutable rows taken at read time, which
    is why a reversal is simply a row that stops counting rather than a
    correction that has to find every place the number was cached.
    """
    budget = active_budget(session, project_id=project.id)
    baseline = approved = contingency = ZERO
    if budget is not None:
        totals = session.execute(
            select(
                func.coalesce(func.sum(BudgetLine.baseline_amount), 0),
                func.coalesce(func.sum(BudgetLine.approved_budget_amount), 0),
                func.coalesce(func.sum(BudgetLine.contingency_amount), 0),
            ).where(BudgetLine.budget_version_id == budget.id)
        ).one()
        baseline, approved, contingency = (money(value) for value in totals)

    original = session.scalars(
        select(func.sum(ContractLine.original_amount_ex_tax))
        .join(Contract, Contract.id == ContractLine.contract_id)
        .where(
            ContractLine.project_id == project.id,
            Contract.status.in_(tuple(CONTRACT_COMMITTING)),
        )
    ).first()
    variations = session.scalars(
        select(func.sum(VariationLine.value_delta_ex_tax))
        .join(Variation, Variation.id == VariationLine.variation_id)
        .join(Contract, Contract.id == Variation.contract_id)
        .where(
            VariationLine.project_id == project.id,
            Variation.status == VARIATION_APPROVED,
            Contract.status.in_(tuple(CONTRACT_COMMITTING)),
        )
    ).first()
    original_commitment = money(original or ZERO)
    variation_delta = money(variations or ZERO)

    forecast = active_forecast(session, project_id=project.id)
    certified_as_of = forecast.as_of_date if forecast is not None else None
    certified = money(
        sum(
            certified_by_cost_code(session, project_id=project.id, as_of=certified_as_of).values(),
            ZERO,
        )
    )

    remaining: Decimal | None = None
    eac: Decimal | None = None
    vac: Decimal | None = None
    if forecast is not None:
        total = session.scalars(
            select(func.sum(ForecastLine.forecast_remaining_amount_ex_tax)).where(
                ForecastLine.forecast_version_id == forecast.id
            )
        ).first()
        remaining = money(total or ZERO)
        eac = calculator.estimate_at_completion(
            certified_to_date=certified, forecast_remaining=remaining
        )
        vac = calculator.variance_at_completion(
            estimate_at_completion=eac,
            control_budget=calculator.control_budget(
                approved_budget=approved, contingency=contingency
            ),
        )

    return CostControl(
        original_baseline=baseline,
        current_approved_budget=approved,
        approved_contingency=contingency,
        control_budget=calculator.control_budget(approved_budget=approved, contingency=contingency),
        original_commitment=original_commitment,
        approved_variation_delta=variation_delta,
        revised_commitment=calculator.revised_commitment(
            original_amount=original_commitment, approved_variation_delta=variation_delta
        ),
        certified_to_date=certified,
        forecast_remaining=remaining,
        estimate_at_completion=eac,
        variance_at_completion=vac,
    )


def payable_position(session: Session, *, project: Project) -> Payable:
    """Assemble the project's cash position. Never added to the cost position."""
    approved = session.scalars(
        select(func.sum(Invoice.amount_ex_tax + Invoice.tax_amount)).where(
            Invoice.project_id == project.id, Invoice.status == INVOICE_APPROVED
        )
    ).first()
    disputed = session.scalars(
        select(func.sum(Invoice.amount_ex_tax + Invoice.tax_amount)).where(
            Invoice.project_id == project.id, Invoice.status == INVOICE_DISPUTED
        )
    ).first()
    paid = session.scalars(
        select(func.sum(PaymentAllocation.amount))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(PaymentAllocation.project_id == project.id, Payment.status == PAYMENT_CONFIRMED)
    ).first()
    approved_total = money(approved or ZERO)
    disputed_total = money(disputed or ZERO)
    paid_total = money(paid or ZERO)

    held = released = advance_paid = advance_recovered = ZERO
    for contract in session.scalars(
        select(Contract).where(
            Contract.project_id == project.id,
            Contract.status.in_(tuple(CONTRACT_COMMITTING)),
        )
    ):
        contract_held, contract_released = retention_position(
            session, project_id=project.id, contract_id=contract.id
        )
        held = money(held + contract_held)
        released = money(released + contract_released)
        contract_advance, contract_recovered = advance_position(
            session, project_id=project.id, contract_id=contract.id
        )
        advance_paid = money(advance_paid + contract_advance)
        advance_recovered = money(advance_recovered + contract_recovered)

    return Payable(
        approved_invoice_payable=approved_total,
        disputed_invoice_payable=disputed_total,
        confirmed_paid=paid_total,
        # A disputed invoice is still owed. Subtracting it would make the
        # obligation fall the moment somebody objected to it.
        invoice_outstanding=money(approved_total + disputed_total - paid_total),
        retention_outstanding=calculator.retention_outstanding(held=held, released=released),
        advance_paid=advance_paid,
        advance_recovered=advance_recovered,
        advance_outstanding=calculator.advance_outstanding(
            paid=advance_paid, recovered=advance_recovered
        ),
    )


def construction_controls(session: Session, *, project: Project) -> dict[str, int | bool]:
    """The counts a screen may act on, each from a stored fact.

    No severity, no score, no weighting. A health percentage over a set of
    pass/fail questions tells a reader something is wrong without saying what,
    and goes green while one of them is still failing.
    """
    today = business_today()
    budget = active_budget(session, project_id=project.id)
    forecast = active_forecast(session, project_id=project.id)

    over_budget = 0
    below_commitment = 0
    if budget is not None:
        lines = budget_lines_by_cost_code(session, budget_version_id=budget.id)
        committed = committed_by_cost_code(session, project_id=project.id)
        positions = (
            forecast_position(session, project=project, version=forecast)
            if forecast is not None
            else {}
        )
        for cost_code_id, line in lines.items():
            if committed.get(cost_code_id, ZERO) > calculator.control_budget(
                approved_budget=line.approved_budget_amount,
                contingency=line.contingency_amount,
            ):
                over_budget += 1
        below_commitment = sum(
            1 for position in positions.values() if position.forecast_below_commitment
        )

    open_variations = session.scalar(
        select(func.count())
        .select_from(Variation)
        .where(Variation.project_id == project.id, Variation.status == VARIATION_SUBMITTED)
    )
    late = session.scalar(
        select(func.count())
        .select_from(Milestone)
        .where(
            Milestone.project_id == project.id,
            Milestone.status.notin_((MILESTONE_CERTIFIED, MILESTONE_CANCELLED)),
            Milestone.planned_date.is_not(None),
            Milestone.planned_date < today,
        )
    )
    uncertified = session.scalar(
        select(func.count())
        .select_from(Milestone)
        .where(Milestone.project_id == project.id, Milestone.status == MILESTONE_ACHIEVED)
    )
    overdue_invoices = session.scalar(
        select(func.count())
        .select_from(Invoice)
        .where(
            Invoice.project_id == project.id,
            Invoice.status == INVOICE_APPROVED,
            Invoice.due_date.is_not(None),
            Invoice.due_date < today,
        )
    )
    escalated = 0
    for variation in session.scalars(
        select(Variation).where(
            Variation.project_id == project.id, Variation.status == VARIATION_SUBMITTED
        )
    ):
        needs, _threshold, _total = variation_requires_escalation(
            session, project=project, variation_id=variation.id
        )
        if needs:
            escalated += 1

    return {
        "open_variations": int(open_variations or 0),
        "escalated_variations": escalated,
        "over_budget_cost_codes": over_budget,
        "forecast_below_commitment_cost_codes": below_commitment,
        "late_milestones": int(late or 0),
        "achieved_uncertified_milestones": int(uncertified or 0),
        "overdue_approved_invoices": int(overdue_invoices or 0),
        "has_active_budget": budget is not None,
        "has_active_forecast": forecast is not None,
    }


def reconciliation(session: Session, *, project: Project) -> list[calculator.Check]:
    """Explicit questions the rows must answer, with no tolerance anywhere.

    Each check is a sentence somebody can act on rather than a contribution to a
    score. A reconciliation that reported "94% healthy" would be green while a
    contract's lines disagreed with its own header by a cent, which is exactly
    the case this exists to surface.
    """
    checks: list[calculator.Check] = []

    for contract in session.scalars(select(Contract).where(Contract.project_id == project.id)):
        checks.append(
            calculator.equality_check(
                key=f"contract_lines:{contract.contract_number}",
                label=f"Contract {contract.contract_number}: lines against header",
                amount=contract_line_total(session, contract_id=contract.id),
                expected=contract.original_contract_value_ex_tax,
            )
        )
        committed = contract_committed_by_cost_code(
            session, project_id=project.id, contract_id=contract.id
        )
        certified = certified_by_cost_code(session, project_id=project.id, contract_id=contract.id)
        checks.append(
            calculator.limit_check(
                key=f"certified:{contract.contract_number}",
                label=f"Contract {contract.contract_number}: certified against commitment",
                amount=money(sum(certified.values(), ZERO)),
                limit=money(sum(committed.values(), ZERO)),
            )
        )
        held, released = retention_position(session, project_id=project.id, contract_id=contract.id)
        checks.append(
            calculator.limit_check(
                key=f"retention:{contract.contract_number}",
                label=f"Contract {contract.contract_number}: retention released against held",
                amount=released,
                limit=held,
            )
        )
        advance_paid, recovered = advance_position(
            session, project_id=project.id, contract_id=contract.id
        )
        checks.append(
            calculator.limit_check(
                key=f"advance:{contract.contract_number}",
                label=f"Contract {contract.contract_number}: advance recovered against paid",
                amount=recovered,
                limit=advance_paid,
            )
        )

    for payment in session.scalars(
        select(Payment).where(Payment.project_id == project.id, Payment.status == PAYMENT_CONFIRMED)
    ):
        checks.append(
            calculator.equality_check(
                key=f"payment_allocated:{payment.payment_reference}",
                label=f"Payment {payment.payment_reference}: allocations against amount",
                amount=payment_allocated(session, payment_id=payment.id),
                expected=payment.amount,
                detail="A confirmed disbursement must say in full what it settled.",
            )
        )

    for invoice in session.scalars(
        select(Invoice).where(
            Invoice.project_id == project.id, Invoice.status.in_(tuple(INVOICE_STANDING))
        )
    ):
        checks.append(
            calculator.limit_check(
                key=f"invoice_paid:{invoice.invoice_number}",
                label=f"Invoice {invoice.invoice_number}: cash applied against payable",
                amount=invoice_allocated(session, invoice_id=invoice.id),
                limit=calculator.invoice_payable(
                    amount_ex_tax=invoice.amount_ex_tax, tax=invoice.tax_amount
                ),
            )
        )

    forecast = active_forecast(session, project_id=project.id)
    active_codes = session.scalar(
        select(func.count())
        .select_from(CostCode)
        .where(CostCode.project_id == project.id, CostCode.is_active.is_(True))
    )
    if forecast is not None:
        covered = len(forecast_lines_by_cost_code(session, forecast_version_id=forecast.id))
        checks.append(
            calculator.equality_check(
                key="forecast_coverage",
                label="Forecast addresses every active cost code",
                amount=Decimal(covered),
                expected=Decimal(int(active_codes or 0)),
                detail="A missing line is not a forecast of zero.",
            )
        )

    # No exchange rates exist anywhere in this platform, so a second
    # denomination is a figure nothing could add to the project's position.
    unlike = session.scalar(
        select(func.count())
        .select_from(Contract)
        .where(
            Contract.project_id == project.id,
            Contract.currency_id != project.base_currency_id,
        )
    )
    checks.append(
        calculator.equality_check(
            key="currency",
            label="Every contract is in the project's base currency",
            amount=Decimal(int(unlike or 0)),
            expected=ZERO,
            detail="There is no FX in this platform; unlike currencies are never added.",
        )
    )
    return checks


# --------------------------------------------------------------------------- #
# Delivery
# --------------------------------------------------------------------------- #

#: The build states construction answers for. Handover — blocked, ready, handed
#: over — belongs to sales, and nothing here can reach it: a module that could
#: mark a unit handed over would be a second writer for a status somebody else
#: is accountable for.
CONSTRUCTION_DELIVERY_STATES = ("not_started", "under_construction", "ready")


def milestone_scope_label(session: Session, *, milestone: Milestone) -> str | None:
    """What a milestone is about, in words: a phase, a building, or the project."""
    if milestone.building_id is not None:
        building = session.get(Building, milestone.building_id)
        if building is not None:
            return building.code
    if milestone.phase_id is not None:
        phase = session.get(Phase, milestone.phase_id)
        if phase is not None:
            return phase.code
    return None


def apply_delivery(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    to_status: str,
    unit_id: uuid.UUID | None,
    building_id: uuid.UUID | None,
    phase_id: uuid.UUID | None,
    effective_date: date,
    reason: str | None = None,
    revoking: bool = False,
) -> dict[str, object]:
    """Move a unit, a building's units or a phase's units through the build.

    Everything is validated before anything is applied. A bulk action that
    updated eighty-seven units and failed on the eighty-eighth would leave a
    building in two states with no record of which half moved, so the whole set
    is proved first and then written — all of it or none.

    Every write goes through inventory's public contract. Construction decides
    which value follows from the build; inventory owns the column, the closed
    set and the append-only event behind it, and there is no line here that
    assigns ``unit.delivery_status``.
    """
    lock_project(session, project.id)
    if to_status not in CONSTRUCTION_DELIVERY_STATES:
        raise ValidationError(
            "Construction moves units between not started, under construction and "
            "ready. Handover states belong to sales."
        )
    named = [value for value in (unit_id, building_id, phase_id) if value is not None]
    if len(named) != 1:
        raise ValidationError("Name exactly one of a unit, a building or a phase.")

    require_valid_scope(
        session,
        project=project,
        actor=actor,
        phase_id=phase_id,
        building_id=building_id,
    )

    # A unit hangs off a floor, a floor off a building, a building off a phase.
    # Every scope below reaches the unit through that chain rather than through
    # a denormalised column, because there is no such column and inventing one
    # here would be a second answer to where a unit sits.
    in_building = select(Unit.id).join(Floor, Floor.id == Unit.floor_id)
    statement = select(Unit).where(Unit.project_id == project.id)
    if unit_id is not None:
        statement = statement.where(Unit.id == unit_id)
    elif building_id is not None:
        statement = statement.where(
            Unit.id.in_(in_building.where(Floor.building_id == building_id))
        )
    else:
        statement = statement.where(
            Unit.id.in_(
                in_building.join(Building, Building.id == Floor.building_id).where(
                    Building.phase_id == phase_id, Building.project_id == project.id
                )
            )
        )
    allowed = visible_phase_ids(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(
            Unit.id.in_(
                select(Unit.id)
                .join(Floor, Floor.id == Unit.floor_id)
                .join(Building, Building.id == Floor.building_id)
                .where(Building.phase_id.in_(allowed), Building.project_id == project.id)
            )
        )
    # Deterministic order, so two concurrent bulk actions take the same unit
    # locks in the same sequence rather than deadlocking against each other.
    units = list(session.scalars(statement.order_by(Unit.id)))
    if not units:
        raise NotFoundError("No units found in that scope.")

    blocked: list[str] = []
    for unit in units:
        current = unit.delivery_status
        if current not in CONSTRUCTION_DELIVERY_STATES:
            blocked.append(
                f"{unit.unit_number}: {current} is a handover state and belongs to sales"
            )
            continue
        if revoking and current != "ready":
            blocked.append(f"{unit.unit_number}: is {current}, not ready")
    if blocked:
        raise ConflictError(
            "This would not apply to every unit in the scope, so none of it was "
            "applied — " + "; ".join(sorted(blocked)) + "."
        )

    moved: list[uuid.UUID] = []
    for unit in units:
        if unit.delivery_status == to_status:
            continue
        inventory_service.apply_delivery_status(
            session,
            project=project,
            unit=unit,
            to_status=to_status,
            effective_date=effective_date,
            actor_user_id=actor.user_id,
            correlation_id=actor.correlation_id,
            reason=reason,
        )
        moved.append(unit.id)
    _flush(session)
    return {"to_status": to_status, "unit_count": len(moved), "unit_ids": moved}
