"""Sales and legal transactions: reservations, contracts, registry, cancellation.

The rules this file exists to hold, stated once here so no individual function
has to argue for them:

**A commitment is decided under the unit lock.** "Is this unit free?" and "take
it" must be one indivisible step, or two advisors both get told yes. Every
operation that creates or relinquishes a commitment takes ``project`` then
``unit`` for update, re-reads the committed state, and decides against that.
The partial unique indexes are the backstop, not the mechanism.

**A frozen number is never recalculated.** A reservation freezes what pricing
said at the moment terms were agreed, and a contract freezes what the
reservation said. Nothing here re-runs the quote against today's configuration,
because a contract that quietly restates itself is not a contract.

**A gate is an attestation, not a receipt.** ``deposit_confirmed`` and
``first_payment_confirmed`` mean a named person recorded that evidence exists.
They are never counted as money collected: PR-MVP-07 owns receipts, and the
naming here is chosen so the two can never be confused.

**Concession and seller cost are different things.** A discount reduces the
contract price; a furniture package the seller absorbs does not. That
distinction is PR-MVP-04's and it survives into the contract snapshot intact.

**Nothing financial or legal is deleted.** A reservation expires, a contract is
cancelled, a legal event is reversed by another event. The record of the wrong
thing having been believed is itself a fact somebody will need.

**Sales never assigns another module's column.** Unit status moves through
inventory's ``apply_*`` contracts, prices come from pricing's public service,
codes are validated by settings. Nothing here reaches into another domain's
tables and reinterprets its state.

There is no workflow engine, no rules language, no approval framework and no
scheduler. Every transition below is a named function with an explicit
precondition list, which is longer to write and possible to audit.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import User
from app.modules.audit.service import record_event
from app.modules.inventory import custom_fields as inventory_fields
from app.modules.inventory import service as inventory_service
from app.modules.inventory.models import (
    COMMERCIAL_STATUS_AVAILABLE,
    COMMERCIAL_STATUS_CONTRACT_PENDING,
    COMMERCIAL_STATUS_CONTRACTED,
    COMMERCIAL_STATUS_HELD,
    COMMERCIAL_STATUS_RESERVED,
    COMMERCIAL_STATUS_RETURNED,
    LEGAL_STATUS_NO_SPA,
    Building,
    Floor,
    Unit,
)
from app.modules.pricing import service as pricing_service
from app.modules.pricing.calculator import money
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import permissions
from app.modules.sales.models import (
    ADJUSTMENT_RATE_TYPES,
    ADJUSTMENT_TREATMENT_OF,
    ADJUSTMENT_TYPES,
    CANCELLATION_COMPLETED,
    CANCELLATION_CURE,
    CANCELLATION_INITIATORS,
    CANCELLATION_NOTICE,
    CANCELLATION_OPEN,
    CANCELLATION_READY_FOR_RETURN,
    CANCELLATION_STATUSES,
    CANCELLATION_TERMINATION_PENDING,
    CANCELLATION_WITHDRAWAL_PENDING,
    CANCELLATION_WITHDRAWN,
    CATEGORY_CLIENT_LANGUAGE,
    CATEGORY_NATIONALITY,
    CATEGORY_RESIDENCY,
    CATEGORY_SALES_BRANCH,
    CATEGORY_SALES_CHANNEL,
    CLEARANCE_CLEARED,
    CLEARANCE_COLLECTION,
    CLEARANCE_DELIVERY,
    CLEARANCE_LEGAL,
    CLEARANCE_PENDING,
    CLEARANCE_REVOKED,
    CLEARANCE_TYPES,
    ENTITY_ADJUSTMENT,
    ENTITY_CANCELLATION,
    ENTITY_CLEARANCE,
    ENTITY_CLIENT,
    ENTITY_CLIENT_PARTY,
    ENTITY_HANDOVER,
    ENTITY_LEGAL_EVENT,
    ENTITY_RESERVATION,
    ENTITY_SALE,
    ENTITY_SALES_POLICY,
    EVENT_BUYER_SIGNED,
    EVENT_LODGED,
    EVENT_REGISTERED,
    EVENT_SELLER_SIGNED,
    EVENT_TRANSFER_PENDING,
    EVENT_TRANSFERRED,
    EVENT_WITHDRAWAL_STARTED,
    EVENT_WITHDRAWN,
    EXCEPTION_APPROVED,
    EXCEPTION_NOT_REQUIRED,
    EXCEPTION_PENDING,
    EXCEPTION_REJECTED,
    EXCEPTION_SUBMITTED,
    GATE_CONFIRMED,
    GATE_NOT_REQUIRED,
    GATE_PENDING,
    GATE_SATISFIED,
    GATE_WAIVED,
    HANDOVER_CANCELLED,
    HANDOVER_HANDED_OVER,
    HANDOVER_PREPARATION,
    HANDOVER_STATUSES,
    KYC_STATUSES,
    LEGAL_EVENT_TYPES,
    PARTY_ROLES,
    RESERVATION_ACTIVE,
    RESERVATION_CANCELLED,
    RESERVATION_COMMITTED,
    RESERVATION_CONVERTED,
    RESERVATION_DEPOSIT_PENDING,
    RESERVATION_DRAFT,
    RESERVATION_EXPIRED,
    RESERVATION_EXTENDED,
    RESERVATION_PREPARING,
    SALE_ACTIVE,
    SALE_CANCELLED,
    SALE_COMMITTED,
    SALE_DRAFT,
    SALE_SIGNATURE_PENDING,
    SALE_TERMINATION_PENDING,
    WITHDRAWAL_COMPLETED,
    WITHDRAWAL_NOT_REQUIRED,
    WITHDRAWAL_PENDING,
    Client,
    ClientParty,
    HandoverClearance,
    HandoverRecord,
    Reservation,
    ReservationAdjustment,
    ReservationStatusEvent,
    SaleCancellation,
    SaleContract,
    SaleContractParty,
    SaleContractTaxLine,
    SaleLegalEvent,
    SalesProjectPolicy,
)
from app.modules.settings import service as settings_service

ZERO = Decimal("0")
ONE = Decimal("1")
#: The RATE scale buyer shares must reconcile at. Comparing at anything looser
#: would let three buyers at 0.333333 pass as a whole flat.
SHARE_EXPONENT = Decimal("0.000001")

# Field lists for audit snapshots. Personal data is deliberately absent from
# every one of them: an audit trail that copies a passport number has made a
# second, less protected home for it. What changed is recorded; what it changed
# to lives in the business record, where the access rules apply.
_POLICY_FIELDS = (
    "handover_requires_collection_clearance",
    "handover_requires_legal_clearance",
    "handover_requires_delivery_clearance",
    "handover_requires_title_transfer",
    "title_transfer_requires_collection_clearance",
    "reservation_requires_deposit_confirmation",
)
_CLIENT_FIELDS = (
    "client_number",
    "display_name",
    "kyc_status",
    "preferred_language_code",
    "owner_advisor_user_id",
    "is_active",
)
_PARTY_FIELDS = ("party_role", "share_fraction", "is_primary", "is_active")
_RESERVATION_FIELDS = (
    "reservation_number",
    "status",
    "unit_id",
    "client_id",
    "unit_price_version_id",
    "reservation_date",
    "expires_on",
    "price_locked_until",
    "currency_id",
    "reference_price_ex_tax",
    "gross_quoted_price_ex_tax",
    "cash_discount_amount",
    "seller_credit_amount",
    "net_contract_price_ex_tax",
    "seller_cost_total",
    "effective_net_revenue_preview",
    "tax_total",
    "total_buyer_payable",
    "exception_approval_required",
    "exception_approval_status",
    "deposit_gate_status",
)
_ADJUSTMENT_FIELDS = ("adjustment_type", "treatment", "rate_fraction", "amount")
_SALE_FIELDS = (
    "sale_number",
    "spa_number",
    "status",
    "unit_id",
    "client_id",
    "reservation_id",
    "unit_price_version_id",
    "currency_id",
    "contract_date",
    "net_contract_price_ex_tax",
    "seller_cost_total",
    "effective_net_revenue_snapshot",
    "tax_total",
    "total_contract_price",
    "first_payment_gate_status",
)
_LEGAL_EVENT_FIELDS = (
    "event_type",
    "event_date",
    "authority_reference",
    "document_reference",
    "fee_amount",
    "reverses_event_id",
)
_CANCELLATION_FIELDS = (
    "status",
    "initiated_by_party",
    "initiation_date",
    "termination_date",
    "forfeiture_amount",
    "refund_due_amount",
    "financial_approval_required",
    "legal_withdrawal_required",
    "legal_withdrawal_status",
    "unit_return_date",
)
_HANDOVER_FIELDS = (
    "status",
    "readiness_date",
    "inspection_date",
    "snag_status",
    "scheduled_handover_date",
    "handover_date",
    "acceptance_document_reference",
)
_CLEARANCE_FIELDS = ("clearance_type", "status", "evidence_reference")


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _flush(session: Session) -> None:
    """Send pending changes so database constraints answer before we continue.

    Every guard in this module is a service check *and* a database constraint.
    Flushing here is what makes the database's answer arrive inside the
    operation that can still react to it, rather than at an unrelated commit.
    """
    session.flush()


def _snapshot(instance: object, fields: tuple[str, ...]) -> dict[str, Any]:
    return {name: getattr(instance, name) for name in fields}


def _require_reason(reason: str | None, *, detail: str) -> str:
    text = (reason or "").strip()
    if not text:
        raise ValidationError(detail)
    return text


def _now() -> datetime:
    return datetime.now(UTC)


def _effective(effective_date: date | None) -> date:
    """The date a transition takes effect, refusing one that has not happened yet.

    Every operation below changes the record's *current* state the moment it
    runs. A future effective date would produce a unit that is contracted today
    and whose history says the contract begins next week — two statements about
    the same fact that cannot both be true, and the sort of thing nobody notices
    until they are trying to reconstruct a quarter.

    Backdating stays allowed where the chronology rules permit it: recording on
    Thursday something that happened on Tuesday is ordinary business. This
    module runs no scheduler and has no pending states, so a date in the future
    is not a promise it could keep.
    """
    today = inventory_fields.business_today()
    effective = effective_date or today
    if effective > today:
        raise ValidationError(
            f"This takes effect immediately, so it cannot be dated "
            f"{effective.isoformat()}. Use today or a past date."
        )
    return effective


def _amount(value: object) -> Decimal:
    """Coerce an incoming amount to the platform's monetary scale."""
    return money(Decimal(str(value)) if value is not None else ZERO)


def _next_number(
    session: Session,
    *,
    project: Project,
    prefix: str,
    column: InstrumentedAttribute[str],
    project_column: InstrumentedAttribute[uuid.UUID],
) -> str:
    """Assign the next project-scoped human reference under the project lock.

    ``MAX + 1`` is only safe because the caller has already taken the project
    row for update: two requests arriving together are made to take turns, so
    they produce RES-000004 and RES-000005 rather than both claiming the same
    number and one of them losing at the unique index. The index is still there;
    it is the backstop for a caller that forgot the lock, not the mechanism.

    The maximum is taken over the numeric tail rather than the whole string so
    the answer stays right if the prefix ever changes length.
    """
    highest = session.scalar(
        select(func.max(func.substr(column, len(prefix) + 2))).where(
            project_column == project.id, column.like(f"{prefix}-%")
        )
    )
    number = int(highest) + 1 if highest and highest.isdigit() else 1
    return f"{prefix}-{number:06d}"


# --------------------------------------------------------------------------- #
# Project policy
# --------------------------------------------------------------------------- #

#: The defaults a project gets before anyone configures it. They fail closed:
#: a development that hands over before the money is in has to say so, out loud,
#: in configuration somebody signed off.
_POLICY_DEFAULTS: dict[str, bool] = {
    "handover_requires_collection_clearance": True,
    "handover_requires_legal_clearance": True,
    "handover_requires_delivery_clearance": True,
    "handover_requires_title_transfer": False,
    "title_transfer_requires_collection_clearance": True,
    "reservation_requires_deposit_confirmation": True,
}


def policy_for(session: Session, *, project: Project) -> SalesProjectPolicy:
    """This project's sales policy, as an unsaved default row if none exists.

    Reads never write. A GET that created a policy row would make "has this
    project been configured?" unanswerable, and would put an INSERT behind an
    endpoint an auditor is allowed to call.
    """
    policy = session.scalars(
        select(SalesProjectPolicy).where(SalesProjectPolicy.project_id == project.id)
    ).first()
    if policy is not None:
        return policy
    return SalesProjectPolicy(project_id=project.id, **_POLICY_DEFAULTS)


def write_policy(
    session: Session, *, project: Project, actor: ActorContext, **fields: bool
) -> SalesProjectPolicy:
    """Set the project's gates. Creates the row on first write."""
    permissions.require_sales_policy_writer(actor)
    project = lock_project(session, project.id)
    policy = session.scalars(
        select(SalesProjectPolicy).where(SalesProjectPolicy.project_id == project.id)
    ).first()
    before = _snapshot(policy, _POLICY_FIELDS) if policy is not None else None
    if policy is None:
        policy = SalesProjectPolicy(project_id=project.id, **_POLICY_DEFAULTS)
        session.add(policy)
    for name, value in fields.items():
        setattr(policy, name, value)
    policy.updated_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="sales_policy.updated",
        entity_type=ENTITY_SALES_POLICY,
        entity_id=policy.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(policy, _POLICY_FIELDS),
    )
    session.commit()
    session.refresh(policy)
    return policy


# --------------------------------------------------------------------------- #
# Clients and buyer parties
# --------------------------------------------------------------------------- #


def _require_advisor(session: Session, *, advisor_user_id: uuid.UUID | None) -> None:
    """Refuse a salesperson who is not one.

    An arbitrary user identifier in ``advisor_user_id`` would put commission,
    attribution and row-level visibility on a person who never sold anything.
    """
    if advisor_user_id is None:
        return
    user = session.get(User, advisor_user_id)
    if user is None or not user.is_active:
        raise ValidationError("That advisor is not an active user.")
    if not user.role_keys.intersection(permissions.ADVISOR_ROLES):
        raise ValidationError("That user is not a sales advisor.")


def _require_reference(
    session: Session, *, project: Project, category: str, code: str | None
) -> str | None:
    """Validate a newly assigned configuration code, or leave it unset.

    Only new assignments are checked. A record already carrying a since-retired
    channel keeps it: configuration moving on does not rewrite history.
    """
    if code is None:
        return None
    normalized = code.strip()
    if not normalized:
        return None
    settings_service.require_active_reference_value(
        session,
        category=category,
        code=normalized,
        country_pack_id=project.country_pack_id,
    )
    return normalized


def list_clients(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    search: str | None = None,
    is_active: bool | None = None,
) -> list[Client]:
    """The buyers this caller may see, narrowed in SQL.

    An advisor's own book is a ``WHERE`` clause, not a post-filter: loading a
    project's whole client list and dropping other advisors' rows afterwards
    would put them in memory and one refactor from the response.
    """
    permissions.require_sales_reader(actor)
    statement = select(Client).where(Client.project_id == project.id)
    if is_active is not None:
        statement = statement.where(Client.is_active.is_(is_active))
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            Client.display_name.ilike(pattern) | Client.client_number.ilike(pattern)
        )
    statement = permissions.visible_clients(statement, actor=actor).order_by(Client.client_number)
    return list(session.scalars(statement))


def get_client(
    session: Session, *, project: Project, client_id: uuid.UUID, actor: ActorContext
) -> Client:
    """One buyer, or 404 — including when the buyer belongs to another advisor.

    A 403 here would confirm the identifier names a real client of this project,
    which is exactly the fact the scoping exists to withhold.
    """
    permissions.require_sales_reader(actor)
    return permissions.require_visible_client(
        session, project=project, client_id=client_id, actor=actor
    )


def create_client(
    session: Session, *, project: Project, actor: ActorContext, **fields: object
) -> Client:
    """Register a buyer against this project."""
    permissions.require_client_writer(actor)
    permissions.require_operational_project(project)
    project = lock_project(session, project.id)

    advisor_user_id = fields.pop("owner_advisor_user_id", None)
    if advisor_user_id is None and "sales_advisor" in actor.role_keys:
        # An advisor creating a buyer owns it. Leaving it unassigned would make
        # the row invisible to the person who just created it.
        advisor_user_id = actor.user_id
    _require_advisor(session, advisor_user_id=advisor_user_id)
    language = _require_reference(
        session,
        project=project,
        category=CATEGORY_CLIENT_LANGUAGE,
        code=fields.pop("preferred_language_code", None),
    )
    kyc_status = fields.pop("kyc_status", None) or "not_started"
    if kyc_status not in KYC_STATUSES:
        raise ValidationError("That is not a KYC status.")

    client = Client(
        project_id=project.id,
        client_number=_next_number(
            session,
            project=project,
            prefix="CLI",
            column=Client.client_number,
            project_column=Client.project_id,
        ),
        preferred_language_code=language,
        kyc_status=kyc_status,
        owner_advisor_user_id=advisor_user_id,
        created_by_user_id=actor.user_id,
        **fields,
    )
    session.add(client)
    _flush(session)
    record_event(
        session,
        action="client.created",
        entity_type=ENTITY_CLIENT,
        entity_id=client.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(client, _CLIENT_FIELDS),
    )
    session.commit()
    session.refresh(client)
    return client


def update_client(
    session: Session,
    *,
    project: Project,
    client_id: uuid.UUID,
    actor: ActorContext,
    **fields: object,
) -> Client:
    """Correct a buyer's record.

    The audit entry names the fields that changed and not their values: an
    address history in the audit table is a second, less protected copy of
    somebody's personal data.
    """
    permissions.require_client_writer(actor)
    client = permissions.require_visible_client(
        session, project=project, client_id=client_id, actor=actor
    )
    if "owner_advisor_user_id" in fields:
        _require_advisor(
            session,
            advisor_user_id=fields["owner_advisor_user_id"],  # type: ignore[arg-type]
        )
    if "preferred_language_code" in fields:
        fields["preferred_language_code"] = _require_reference(
            session,
            project=project,
            category=CATEGORY_CLIENT_LANGUAGE,
            code=fields["preferred_language_code"],  # type: ignore[arg-type]
        )
    if fields.get("kyc_status") is not None and fields["kyc_status"] not in KYC_STATUSES:
        raise ValidationError("That is not a KYC status.")

    before = _snapshot(client, _CLIENT_FIELDS)
    changed = [name for name, value in fields.items() if getattr(client, name) != value]
    for name, value in fields.items():
        setattr(client, name, value)
    client.updated_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="client.deactivated" if fields.get("is_active") is False else "client.updated",
        entity_type=ENTITY_CLIENT,
        entity_id=client.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after={**_snapshot(client, _CLIENT_FIELDS), "changed_fields": sorted(changed)},
    )
    session.commit()
    session.refresh(client)
    return client


def list_parties(
    session: Session, *, client: Client, include_inactive: bool = True
) -> list[ClientParty]:
    """The named buyers on one client record."""
    statement = select(ClientParty).where(ClientParty.client_id == client.id)
    if not include_inactive:
        statement = statement.where(ClientParty.is_active.is_(True))
    return list(session.scalars(statement.order_by(ClientParty.created_at)))


def active_share_total(session: Session, *, client: Client) -> Decimal:
    """What this client's active buyers currently add up to.

    Public because the workspace shows it before anyone tries to commit a unit:
    finding out that two buyers hold eighty per cent between them at the moment
    of activation is finding out too late.
    """
    total = session.scalar(
        select(func.coalesce(func.sum(ClientParty.share_fraction), 0)).where(
            ClientParty.client_id == client.id, ClientParty.is_active.is_(True)
        )
    )
    return Decimal(str(total or 0)).quantize(SHARE_EXPONENT)


def _require_reconciled_shares(session: Session, *, client: Client) -> None:
    """Refuse a commitment whose buyers do not add up to the whole flat.

    Two buyers at forty per cent each is a contract that sells eighty per cent
    of a unit and leaves the rest with nobody. Checked at the RATE scale the
    column stores, so the arithmetic here and the arithmetic in the database
    agree about what "one" means.
    """
    total = active_share_total(session, client=client)
    if total != ONE:
        raise ConflictError(
            f"The buyer shares on this client total {total}, not 1.000000. "
            "Correct them before committing the unit."
        )


def create_party(
    session: Session,
    *,
    project: Project,
    client: Client,
    actor: ActorContext,
    **fields: object,
) -> ClientParty:
    """Add a named buyer to a client record.

    The client row is locked first: shares are read, judged and written as one
    decision, and two people adding a joint purchaser at the same moment must
    not both see a total of 0.5 and both decide there is room.
    """
    permissions.require_client_writer(actor)
    permissions.require_operational_project(project)
    locked = _lock_client(session, project_id=project.id, client_id=client.id)

    role = fields.pop("party_role", None) or "purchaser"
    if role not in PARTY_ROLES:
        raise ValidationError("That is not a buyer role.")
    for category, name in (
        (CATEGORY_NATIONALITY, "nationality_code"),
        (CATEGORY_RESIDENCY, "residency_code"),
    ):
        if name in fields:
            fields[name] = _require_reference(
                session,
                project=project,
                category=category,
                code=fields[name],  # type: ignore[arg-type]
            )

    party = ClientParty(
        project_id=project.id,
        client_id=locked.id,
        party_role=role,
        created_by_user_id=actor.user_id,
        **fields,
    )
    session.add(party)
    _flush(session)
    record_event(
        session,
        action="client_party.created",
        entity_type=ENTITY_CLIENT_PARTY,
        entity_id=party.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(party, _PARTY_FIELDS),
    )
    session.commit()
    session.refresh(party)
    return party


def update_party(
    session: Session,
    *,
    project: Project,
    party_id: uuid.UUID,
    actor: ActorContext,
    **fields: object,
) -> ClientParty:
    """Correct a named buyer, or stand them down.

    Corrects the *client master*, never a contract: a party frozen onto a
    submitted sale is a different row, and stays exactly as it was signed.
    """
    permissions.require_client_writer(actor)
    party = session.scalars(
        select(ClientParty).where(ClientParty.id == party_id, ClientParty.project_id == project.id)
    ).first()
    if party is None:
        raise NotFoundError("Buyer party not found.")
    client = permissions.require_visible_client(
        session, project=project, client_id=party.client_id, actor=actor
    )
    _lock_client(session, project_id=project.id, client_id=client.id)

    if fields.get("party_role") is not None and fields["party_role"] not in PARTY_ROLES:
        raise ValidationError("That is not a buyer role.")
    for category, name in (
        (CATEGORY_NATIONALITY, "nationality_code"),
        (CATEGORY_RESIDENCY, "residency_code"),
    ):
        if name in fields:
            fields[name] = _require_reference(
                session,
                project=project,
                category=category,
                code=fields[name],  # type: ignore[arg-type]
            )

    before = _snapshot(party, _PARTY_FIELDS)
    changed = [name for name, value in fields.items() if getattr(party, name) != value]
    for name, value in fields.items():
        setattr(party, name, value)
    _flush(session)
    record_event(
        session,
        action="client_party.updated",
        entity_type=ENTITY_CLIENT_PARTY,
        entity_id=party.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after={**_snapshot(party, _PARTY_FIELDS), "changed_fields": sorted(changed)},
    )
    session.commit()
    session.refresh(party)
    return party


def _lock_client(session: Session, *, project_id: uuid.UUID, client_id: uuid.UUID) -> Client:
    """Take the client row for update and return its committed state."""
    client = session.scalars(
        select(Client)
        .where(Client.id == client_id, Client.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if client is None:
        raise NotFoundError("Client not found.")
    return client


# --------------------------------------------------------------------------- #
# Quotes: turning commercial inputs into a frozen offer
# --------------------------------------------------------------------------- #

#: How each adjustment type is presented to the pricing calculator. The mapping
#: is here, once, so the sales vocabulary and pricing's input contract can be
#: read side by side — and so an adjustment type nobody wired up fails loudly
#: rather than being silently dropped from the quote.
_QUOTE_INPUT_OF: dict[str, str] = {
    "percentage_discount": "discount_fraction",
    "fixed_discount": "discount_amount",
    "seller_credit": "seller_credit",
    "package_cost": "package_cost",
    "upgrade_allowance": "upgrade_allowance_cost",
    "commission_support": "commission_support",
    "financing_subsidy": "financing_subsidy",
    "extended_terms_npv_cost": "extended_terms_npv_cost",
    "paid_upgrade": "paid_upgrade_amount",
    "payment_plan_adjustment": "payment_plan_adjustment_fraction",
}


def _jsonable(value: object) -> object:
    """Render a quote result as JSON that still says what the numbers were.

    Decimals become strings, never floats: ``185000.00`` is a different fact
    from ``185000.00000000001``, and the snapshot exists precisely so the
    figures can be read back exactly as they were agreed.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _quote_inputs(
    session: Session, *, reservation_id: uuid.UUID, buyer_fee_total: Decimal
) -> dict[str, Any]:
    """The pricing inputs this reservation's recorded adjustments amount to."""
    inputs: dict[str, Any] = {"buyer_paid_fees": buyer_fee_total}
    for adjustment in session.scalars(
        select(ReservationAdjustment).where(ReservationAdjustment.reservation_id == reservation_id)
    ):
        key = _QUOTE_INPUT_OF[adjustment.adjustment_type]
        inputs[key] = (
            adjustment.rate_fraction
            if adjustment.adjustment_type in ADJUSTMENT_RATE_TYPES
            else adjustment.amount
        )
    return inputs


def _require_reconciled_quote(quote: dict[str, Any]) -> None:
    """Refuse a quote whose waterfall does not add up.

    Reference plus what the buyer additionally contracts for, less what the
    contract price concedes, must equal the net contract price. Seller costs are
    not in that sum and never will be — that is the distinction PR-MVP-04 exists
    to hold, and this is where sales proves it survived the crossing.
    """
    gross = (
        quote["approved_reference_price_ex_tax"]
        + quote["paid_upgrade_price"]
        + quote["payment_plan_price_adjustment"]
    )
    net = gross - quote["cash_discount"] - quote["seller_credit"]
    if (
        money(gross) != quote["gross_quoted_price_ex_tax"]
        or money(net) != (quote["net_contract_price_ex_tax"])
    ):  # pragma: no cover - a pricing regression, not a reachable input
        raise ConflictError("The quote does not reconcile. It has not been stored.")


def _freeze_quote(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    reservation: Reservation,
    buyer_fee_total: Decimal,
) -> dict[str, Any]:
    """Run the quote and copy its result onto the reservation.

    Everything financial about a reservation comes through here. The typed
    columns are the figures somebody will be asked about; ``quote_snapshot_json``
    keeps the whole calculation beside them so the waterfall is still
    explainable line by line in two years, when the configuration that produced
    it has been superseded three times.

    A recalculation always clears any approval that was standing: an exception
    approved against a 12% discount must never remain approved beside a 20% one.
    """
    inputs = _quote_inputs(session, reservation_id=reservation.id, buyer_fee_total=buyer_fee_total)
    quote = pricing_service.quote_preview(session, project=project, unit=unit, inputs=inputs)
    _require_reconciled_quote(quote)

    version = pricing_service.get_price_version(
        session, project_id=project.id, version_id=quote["unit_price_version_id"]
    )

    reservation.unit_price_version_id = quote["unit_price_version_id"]
    reservation.currency_id = quote["currency_id"]
    reservation.reference_price_ex_tax = quote["approved_reference_price_ex_tax"]
    reservation.paid_upgrade_amount = quote["paid_upgrade_price"]
    reservation.payment_plan_adjustment_amount = quote["payment_plan_price_adjustment"]
    reservation.gross_quoted_price_ex_tax = quote["gross_quoted_price_ex_tax"]
    reservation.cash_discount_amount = quote["cash_discount"]
    reservation.seller_credit_amount = quote["seller_credit"]
    reservation.net_contract_price_ex_tax = quote["net_contract_price_ex_tax"]
    reservation.seller_cost_total = quote["seller_cost_total"]
    reservation.effective_net_revenue_preview = quote["effective_net_revenue_preview"]
    reservation.tax_total = quote["tax_total"]
    reservation.buyer_fee_total = quote["buyer_paid_fees"]
    reservation.total_buyer_payable = quote["total_buyer_payable_preview"]

    reservation.exception_approval_required = bool(quote["approval_required"])
    reservation.exception_reason = quote["approval_reason"]
    reservation.exception_required_role = quote["required_role"]
    reservation.exception_approval_status = (
        EXCEPTION_PENDING if quote["approval_required"] else EXCEPTION_NOT_REQUIRED
    )
    reservation.exception_submitted_by_user_id = None
    reservation.exception_submitted_at = None
    reservation.exception_approved_by_user_id = None
    reservation.exception_approved_at = None
    reservation.exception_decision_reason = None

    reservation.quote_snapshot_json = _jsonable(
        {
            **quote,
            "pricing_configuration_id": version.pricing_configuration_id,
            "project_id": project.id,
            "unit_id": unit.id,
            "inputs": inputs,
            # The date the tax observation was taken on. Recorded because the
            # contract freezes these lines and has to be able to say which
            # day's configuration produced them.
            "tax_valid_on": inventory_fields.business_today(),
            "calculated_at": _now(),
        }
    )
    return quote


# --------------------------------------------------------------------------- #
# Reservations
# --------------------------------------------------------------------------- #


def _lock_reservation(
    session: Session, *, project_id: uuid.UUID, reservation_id: uuid.UUID
) -> Reservation:
    """Take the reservation row for update and return its committed state."""
    reservation = session.scalars(
        select(Reservation)
        .where(Reservation.id == reservation_id, Reservation.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if reservation is None:
        raise NotFoundError("Reservation not found.")
    return reservation


def _record_reservation_event(
    session: Session,
    *,
    reservation: Reservation,
    from_status: str,
    to_status: str,
    effective_date: date,
    actor: ActorContext,
    reason: str | None = None,
) -> None:
    """Append one movement to a reservation's history, dates running forwards.

    A chain that carries dates running backwards — active on the 10th, cancelled
    on the 1st — is consistent in its statuses and a fiction in its history, and
    every later question asked of it has two answers. Same-day is allowed: a
    correction recorded the same day is ordinary business.
    """
    latest = session.scalar(
        select(func.max(ReservationStatusEvent.effective_date)).where(
            ReservationStatusEvent.reservation_id == reservation.id
        )
    )
    if latest is not None and effective_date < latest:
        raise ValidationError(
            f"This reservation's last change was effective {latest.isoformat()}. "
            "A later change cannot be dated before it."
        )
    session.add(
        ReservationStatusEvent(
            project_id=reservation.project_id,
            reservation_id=reservation.id,
            from_status=from_status,
            to_status=to_status,
            effective_date=effective_date,
            reason=reason,
            actor_user_id=actor.user_id,
        )
    )


def requires_closure(reservation: Reservation, *, today: date) -> bool:
    """Whether this reservation is past its expiry but still holding the unit.

    Displayed as "Expired — closure required". Nothing here writes: a GET that
    quietly expired a reservation would be a hidden mutation with no actor, no
    reason and no audit entry behind it, and PR-MVP-05 runs no scheduler that
    could do it honestly either.
    """
    return reservation.status in RESERVATION_COMMITTED and reservation.expires_on < today


def _committed_reservation(session: Session, *, unit_id: uuid.UUID) -> Reservation | None:
    """The reservation currently holding this unit, if any."""
    return session.scalars(
        select(Reservation).where(
            Reservation.unit_id == unit_id, Reservation.status.in_(RESERVATION_COMMITTED)
        )
    ).first()


def _committed_sale(session: Session, *, unit_id: uuid.UUID) -> SaleContract | None:
    """The contract currently holding this unit, if any."""
    return session.scalars(
        select(SaleContract).where(
            SaleContract.unit_id == unit_id, SaleContract.status.in_(SALE_COMMITTED)
        )
    ).first()


def _require_no_commitment(session: Session, *, unit: Unit, today: date) -> None:
    """Refuse a second commitment on a unit that already carries one.

    Both tables are consulted through the one locked unit row, because the
    invariant spans them: an active reservation and an unrelated signature-
    pending contract on the same unit is exactly as wrong as two reservations.
    A cross-table trigger or a generic commitment abstraction would say the same
    thing less legibly, so the unit lock says it.
    """
    reservation = _committed_reservation(session, unit_id=unit.id)
    if reservation is not None:
        if reservation.expires_on < today:
            raise ConflictError(
                "The current reservation has expired but must be formally closed "
                "before the unit can be reserved again."
            )
        raise ConflictError(
            f"Reservation {reservation.reservation_number} already holds this unit."
        )
    sale = _committed_sale(session, unit_id=unit.id)
    if sale is not None:
        raise ConflictError(f"Sale contract {sale.sale_number} already holds this unit.")


def list_reservations(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    status: str | None = None,
    unit_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
) -> list[Reservation]:
    """The reservations this caller may see, narrowed in SQL on both axes.

    Phase scoping first — a reservation of a unit in a phase the caller was not
    granted must not appear, and must not have been loaded — then the advisor's
    own book where that applies.
    """
    permissions.require_sales_reader(actor)
    statement = select(Reservation).where(Reservation.project_id == project.id)
    allowed_units = permissions.visible_unit_ids(session, project_id=project.id, actor=actor)
    if allowed_units is not None:
        statement = statement.where(Reservation.unit_id.in_(allowed_units))
    if permissions.restricts_clients_to_own(actor):
        statement = statement.where(
            Reservation.client_id.in_(
                select(Client.id).where(
                    Client.project_id == project.id,
                    Client.owner_advisor_user_id == actor.user_id,
                )
            )
        )
    if status is not None:
        statement = statement.where(Reservation.status == status)
    if unit_id is not None:
        statement = statement.where(Reservation.unit_id == unit_id)
    if client_id is not None:
        statement = statement.where(Reservation.client_id == client_id)
    return list(session.scalars(statement.order_by(Reservation.reservation_number.desc())))


def get_reservation(
    session: Session, *, project: Project, reservation_id: uuid.UUID, actor: ActorContext
) -> Reservation:
    """One reservation the caller may see, or 404."""
    permissions.require_sales_reader(actor)
    reservation = session.scalars(
        select(Reservation).where(
            Reservation.id == reservation_id, Reservation.project_id == project.id
        )
    ).first()
    if reservation is None:
        raise NotFoundError("Reservation not found.")
    # Re-asked through the phase and advisor scopes rather than trusted: the row
    # is only this caller's to see if the unit and the client are.
    permissions.require_sellable_unit(
        session, project=project, unit_id=reservation.unit_id, actor=actor
    )
    permissions.require_visible_client(
        session, project=project, client_id=reservation.client_id, actor=actor
    )
    return reservation


def _require_preparing(reservation: Reservation) -> None:
    if reservation.status not in RESERVATION_PREPARING:
        raise ConflictError(
            "This reservation is no longer in preparation. Its commercial terms are frozen."
        )


def _require_open_exception(reservation: Reservation) -> None:
    """Allow an exception to be worked while it is genuinely outstanding.

    Ordinarily that means the reservation is still in preparation. The one other
    case is a live reservation that has been re-quoted: activation refuses an
    unsettled exception, so a committed reservation can only be carrying one
    because ``requote_reservation`` produced it. That exception has to be
    approvable, or a re-quote would leave the deal stuck behind a decision
    nobody could take.

    This widens nothing else. A committed reservation's adjustments, dates and
    money stay frozen; the explicit re-quote remains the only route to them.
    """
    if reservation.status in RESERVATION_PREPARING:
        return
    outstanding = reservation.exception_approval_status in {
        EXCEPTION_PENDING,
        EXCEPTION_SUBMITTED,
        EXCEPTION_REJECTED,
    }
    if reservation.status in RESERVATION_COMMITTED and outstanding:
        return
    raise ConflictError(
        "This reservation is no longer in preparation. Its commercial terms are frozen."
    )


def create_reservation(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    unit_id: uuid.UUID,
    client_id: uuid.UUID,
    reservation_date: date | None = None,
    expires_on: date | None = None,
    price_locked_until: date | None = None,
    sales_channel_code: str | None = None,
    sales_branch_code: str | None = None,
    advisor_user_id: uuid.UUID | None = None,
    deposit_required_amount: Decimal | None = None,
    buyer_fee_total: Decimal | None = None,
) -> Reservation:
    """Open a reservation against a unit's live price, and freeze that quote.

    Creating one holds nothing: the unit stays on the market until somebody
    activates it. What creation does establish is *which* price the deal is
    being talked about at, and it must be the live, approved one — a draft, a
    submitted, an approved-but-not-live or a superseded price is not something
    the company has agreed to sell at. Pricing decides that, through its own
    quote contract, rather than sales reading its tables and forming a second
    opinion.

    The status a reservation starts in is a project policy, not a user choice:
    where a deposit stands between preparation and commitment the reservation
    starts in ``deposit_pending``, and where none does it starts in ``draft``.
    """
    permissions.require_reservation_writer(actor)
    permissions.require_operational_project(project)
    project = lock_project(session, project.id)
    unit = permissions.require_sellable_unit(session, project=project, unit_id=unit_id, actor=actor)
    client = permissions.require_visible_client(
        session, project=project, client_id=client_id, actor=actor
    )
    if not client.is_active:
        raise ConflictError("This client is not active.")

    today = inventory_fields.business_today()
    # Asked here as well as at activation. Two people may both prepare terms on
    # a unit nobody has committed to; neither may start preparing terms on one
    # somebody already holds, because the answer to "can I sell this?" is
    # already no and finding that out at activation is finding out late.
    unit = inventory_service.lock_unit(session, project_id=project.id, unit_id=unit.id)
    _require_no_commitment(session, unit=unit, today=today)
    reservation_date = reservation_date or today
    if reservation_date > today:
        raise ValidationError("A reservation cannot be dated in the future.")

    advisor_user_id = advisor_user_id or client.owner_advisor_user_id
    _require_advisor(session, advisor_user_id=advisor_user_id)
    channel = _require_reference(
        session, project=project, category=CATEGORY_SALES_CHANNEL, code=sales_channel_code
    )
    branch = _require_reference(
        session, project=project, category=CATEGORY_SALES_BRANCH, code=sales_branch_code
    )

    active = pricing_service.active_price(session, unit_id=unit.id)
    if active is None:
        raise ConflictError("This unit has no active price to reserve against.")
    configuration = pricing_service.get_configuration(
        session, project_id=project.id, configuration_id=active.pricing_configuration_id
    )
    expiry_days = configuration.reservation_expiry_days
    lock_days = configuration.price_lock_days
    if expires_on is None:
        if expiry_days is None:
            raise ValidationError(
                "This project's pricing configuration sets no reservation expiry. "
                "Give the reservation an explicit expiry date."
            )
        expires_on = reservation_date + timedelta(days=expiry_days)
    if price_locked_until is None:
        if lock_days is None:
            raise ValidationError(
                "This project's pricing configuration sets no price-lock period. "
                "Give the reservation an explicit price-lock date."
            )
        price_locked_until = reservation_date + timedelta(days=lock_days)
    if expires_on < reservation_date or price_locked_until < reservation_date:
        raise ValidationError("Expiry and price lock cannot fall before the reservation date.")

    policy = policy_for(session, project=project)
    gate_required = policy.reservation_requires_deposit_confirmation

    reservation = Reservation(
        project_id=project.id,
        reservation_number=_next_number(
            session,
            project=project,
            prefix="RES",
            column=Reservation.reservation_number,
            project_column=Reservation.project_id,
        ),
        unit_id=unit.id,
        client_id=client.id,
        unit_price_version_id=active.id,
        status=RESERVATION_DEPOSIT_PENDING if gate_required else RESERVATION_DRAFT,
        reservation_date=reservation_date,
        expires_on=expires_on,
        price_locked_until=price_locked_until,
        sales_channel_code=channel,
        sales_branch_code=branch,
        advisor_user_id=advisor_user_id,
        deposit_required_amount=(
            _amount(deposit_required_amount) if deposit_required_amount is not None else None
        ),
        deposit_currency_id=active.currency_id if deposit_required_amount is not None else None,
        deposit_gate_status=GATE_PENDING if gate_required else GATE_NOT_REQUIRED,
        currency_id=active.currency_id,
        quote_snapshot_json={},
        created_by_user_id=actor.user_id,
        # Written by _freeze_quote below, which is the only thing that ever sets
        # them. Zeroes here would be numbers nobody quoted.
        reference_price_ex_tax=ZERO,
        paid_upgrade_amount=ZERO,
        payment_plan_adjustment_amount=ZERO,
        gross_quoted_price_ex_tax=ZERO,
        cash_discount_amount=ZERO,
        seller_credit_amount=ZERO,
        net_contract_price_ex_tax=ZERO,
        seller_cost_total=ZERO,
        effective_net_revenue_preview=ZERO,
        tax_total=ZERO,
        buyer_fee_total=_amount(buyer_fee_total),
        total_buyer_payable=ZERO,
        exception_approval_status=EXCEPTION_NOT_REQUIRED,
        exception_approval_required=False,
    )
    session.add(reservation)
    _flush(session)
    _freeze_quote(
        session,
        project=project,
        unit=unit,
        reservation=reservation,
        buyer_fee_total=reservation.buyer_fee_total,
    )
    _flush(session)
    record_event(
        session,
        action="reservation.created",
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


def update_reservation(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    **fields: object,
) -> Reservation:
    """Correct a reservation's non-financial terms while it is still in preparation.

    Deliberately cannot reach a price column. Money on a reservation is produced
    by ``_freeze_quote`` from recorded adjustments and nowhere else, so there is
    no route by which a net contract price can be typed in.
    """
    permissions.require_reservation_writer(actor)
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)
    _require_preparing(reservation)

    if "advisor_user_id" in fields:
        _require_advisor(
            session,
            advisor_user_id=fields["advisor_user_id"],  # type: ignore[arg-type]
        )
    for category, name in (
        (CATEGORY_SALES_CHANNEL, "sales_channel_code"),
        (CATEGORY_SALES_BRANCH, "sales_branch_code"),
    ):
        if name in fields:
            fields[name] = _require_reference(
                session,
                project=project,
                category=category,
                code=fields[name],  # type: ignore[arg-type]
            )
    if "deposit_required_amount" in fields and fields["deposit_required_amount"] is not None:
        fields["deposit_required_amount"] = _amount(fields["deposit_required_amount"])
        reservation.deposit_currency_id = reservation.currency_id

    before = _snapshot(reservation, _RESERVATION_FIELDS)
    for name, value in fields.items():
        setattr(reservation, name, value)
    if reservation.expires_on < reservation.reservation_date:
        raise ValidationError("Expiry cannot fall before the reservation date.")
    if reservation.expires_on > reservation.price_locked_until:
        raise ConflictError(
            "Re-quote the reservation before extending it beyond the approved price lock."
        )
    _flush(session)
    record_event(
        session,
        action="reservation.updated",
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


def recalculate_reservation(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    buyer_fee_total: Decimal | None = None,
) -> Reservation:
    """Re-run the quote from the recorded adjustments and freeze the new result.

    Any approval that was standing is withdrawn by ``_freeze_quote``, because an
    exception sanctioned against one discount says nothing about another. That
    is the whole reason recalculation is an explicit, audited operation rather
    than something that happens on read.
    """
    permissions.require_reservation_writer(actor)
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    unit = permissions.require_sellable_unit(
        session, project=project, unit_id=reservation.unit_id, actor=actor
    )
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)
    _require_preparing(reservation)

    before = _snapshot(reservation, _RESERVATION_FIELDS)
    if buyer_fee_total is not None:
        reservation.buyer_fee_total = _amount(buyer_fee_total)
    _freeze_quote(
        session,
        project=project,
        unit=unit,
        reservation=reservation,
        buyer_fee_total=reservation.buyer_fee_total,
    )
    _flush(session)
    record_event(
        session,
        action="reservation.recalculated",
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


# --------------------------------------------------------------------------- #
# Reservation adjustments
# --------------------------------------------------------------------------- #


def list_adjustments(session: Session, *, reservation: Reservation) -> list[ReservationAdjustment]:
    """The commercial inputs behind a reservation's quote."""
    return list(
        session.scalars(
            select(ReservationAdjustment)
            .where(ReservationAdjustment.reservation_id == reservation.id)
            .order_by(ReservationAdjustment.adjustment_type)
        )
    )


def _validate_adjustment(
    *, adjustment_type: str, rate_fraction: Decimal | None, amount: Decimal | None
) -> tuple[str, Decimal | None, Decimal | None]:
    """Check the shape of one commercial input and derive what it does.

    Treatment is derived, never accepted. The difference between a concession
    and a seller cost is the single distinction this module exists to keep, and
    letting a user choose it would be letting them decide whether the contract
    price falls.
    """
    if adjustment_type not in ADJUSTMENT_TYPES:
        raise ValidationError("That is not an adjustment type.")
    if adjustment_type in ADJUSTMENT_RATE_TYPES:
        if rate_fraction is None or amount is not None:
            raise ValidationError(
                f"A {adjustment_type.replace('_', ' ')} is stated as a rate, not an amount."
            )
        if rate_fraction < ZERO or rate_fraction > ONE:
            raise ValidationError("A rate must be a fraction between 0 and 1.")
        return ADJUSTMENT_TREATMENT_OF[adjustment_type], rate_fraction, None
    if amount is None or rate_fraction is not None:
        raise ValidationError(
            f"A {adjustment_type.replace('_', ' ')} is stated as an amount, not a rate."
        )
    if amount < ZERO:
        raise ValidationError("An amount cannot be negative.")
    return ADJUSTMENT_TREATMENT_OF[adjustment_type], None, money(amount)


def create_adjustment(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    adjustment_type: str,
    rate_fraction: Decimal | None = None,
    amount: Decimal | None = None,
    reason: str | None = None,
) -> ReservationAdjustment:
    """Record one commercial input and re-freeze the quote around it."""
    permissions.require_reservation_writer(actor)
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    unit = permissions.require_sellable_unit(
        session, project=project, unit_id=reservation.unit_id, actor=actor
    )
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)
    _require_preparing(reservation)

    treatment, rate, value = _validate_adjustment(
        adjustment_type=adjustment_type, rate_fraction=rate_fraction, amount=amount
    )
    adjustment = ReservationAdjustment(
        project_id=project.id,
        reservation_id=reservation.id,
        adjustment_type=adjustment_type,
        treatment=treatment,
        rate_fraction=rate,
        amount=value,
        reason=(reason or "").strip() or None,
        requested_by_user_id=actor.user_id,
    )
    session.add(adjustment)
    _flush(session)
    _freeze_quote(
        session,
        project=project,
        unit=unit,
        reservation=reservation,
        buyer_fee_total=reservation.buyer_fee_total,
    )
    _flush(session)
    record_event(
        session,
        action="reservation_adjustment.created",
        entity_type=ENTITY_ADJUSTMENT,
        entity_id=adjustment.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=adjustment.reason,
        after=_snapshot(adjustment, _ADJUSTMENT_FIELDS),
    )
    session.commit()
    session.refresh(adjustment)
    return adjustment


def update_adjustment(
    session: Session,
    *,
    project: Project,
    adjustment_id: uuid.UUID,
    actor: ActorContext,
    rate_fraction: Decimal | None = None,
    amount: Decimal | None = None,
    reason: str | None = None,
) -> ReservationAdjustment:
    """Revise one commercial input while the reservation is still in preparation.

    The type cannot change: an input that turns from a seller cost into a
    discount is a different commercial decision, and it is recorded as one.
    """
    permissions.require_reservation_writer(actor)
    adjustment = session.scalars(
        select(ReservationAdjustment).where(
            ReservationAdjustment.id == adjustment_id,
            ReservationAdjustment.project_id == project.id,
        )
    ).first()
    if adjustment is None:
        raise NotFoundError("Adjustment not found.")
    reservation = get_reservation(
        session, project=project, reservation_id=adjustment.reservation_id, actor=actor
    )
    unit = permissions.require_sellable_unit(
        session, project=project, unit_id=reservation.unit_id, actor=actor
    )
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)
    _require_preparing(reservation)

    _, rate, value = _validate_adjustment(
        adjustment_type=adjustment.adjustment_type,
        rate_fraction=rate_fraction,
        amount=amount,
    )
    before = _snapshot(adjustment, _ADJUSTMENT_FIELDS)
    adjustment.rate_fraction = rate
    adjustment.amount = value
    if reason is not None:
        adjustment.reason = reason.strip() or None
    _flush(session)
    _freeze_quote(
        session,
        project=project,
        unit=unit,
        reservation=reservation,
        buyer_fee_total=reservation.buyer_fee_total,
    )
    _flush(session)
    record_event(
        session,
        action="reservation_adjustment.updated",
        entity_type=ENTITY_ADJUSTMENT,
        entity_id=adjustment.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=adjustment.reason,
        before=before,
        after=_snapshot(adjustment, _ADJUSTMENT_FIELDS),
    )
    session.commit()
    session.refresh(adjustment)
    return adjustment


# --------------------------------------------------------------------------- #
# Exception approval and the deposit gate
# --------------------------------------------------------------------------- #


def submit_exception(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    reason: str,
) -> Reservation:
    """Put a quote that breaches the country's thresholds forward for sanction."""
    permissions.require_reservation_writer(actor)
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)
    _require_open_exception(reservation)
    if not reservation.exception_approval_required:
        raise ConflictError("This quote is within the approval thresholds.")
    if reservation.exception_approval_status not in {EXCEPTION_PENDING, EXCEPTION_REJECTED}:
        raise ConflictError("This exception has already been put forward.")

    before = _snapshot(reservation, _RESERVATION_FIELDS)
    reservation.exception_approval_status = EXCEPTION_SUBMITTED
    reservation.exception_submitted_by_user_id = actor.user_id
    reservation.exception_submitted_at = _now()
    reservation.exception_decision_reason = None
    _flush(session)
    record_event(
        session,
        action="reservation.exception_submitted",
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=_require_reason(reason, detail="Say why this exception is justified."),
        before=before,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


def decide_exception(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    approved: bool,
    reason: str,
) -> Reservation:
    """Sanction or refuse a submitted exception.

    Only the office the threshold names may do it, the administrator cannot
    stand in for them, and the person who submitted it cannot be the person who
    approves it. Those three sentences are the entire approval mechanism — there
    is no engine, no rule table and nothing configurable about who signs.
    """
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    required_role = reservation.exception_required_role or "approver_cfo"
    if required_role == "approver_cfo":
        permissions.require_financial_approver(actor)
    elif required_role not in actor.role_keys:
        raise PermissionDeniedError(
            f"Only {required_role.replace('_', ' ')} may decide this exception."
        )
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)
    _require_open_exception(reservation)
    if reservation.exception_approval_status != EXCEPTION_SUBMITTED:
        raise ConflictError("There is no submitted exception on this reservation.")
    permissions.require_different_checker(
        actor, maker_user_id=reservation.exception_submitted_by_user_id
    )

    before = _snapshot(reservation, _RESERVATION_FIELDS)
    reservation.exception_approval_status = EXCEPTION_APPROVED if approved else EXCEPTION_REJECTED
    reservation.exception_approved_by_user_id = actor.user_id
    reservation.exception_approved_at = _now()
    reservation.exception_decision_reason = _require_reason(
        reason, detail="Say why this exception was decided as it was."
    )
    _flush(session)
    record_event(
        session,
        action="reservation.exception_approved" if approved else "reservation.exception_rejected",
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reservation.exception_decision_reason,
        before=before,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


def confirm_deposit(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    evidence_reference: str,
) -> Reservation:
    """Record that deposit evidence exists. Never that money arrived.

    This is an attestation by a named person with a reference to the evidence
    they saw, and it is a gate in front of the commitment — nothing more. It is
    not a receipt, it is not collected cash, and ``deposit_required_amount``
    must never be summed into a collections or cashflow figure. PR-MVP-07
    introduces the record that can say money arrived.
    """
    permissions.require_gate_evidence_recorder(actor)
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)
    _require_preparing(reservation)
    if reservation.deposit_gate_status != GATE_PENDING:
        raise ConflictError("This reservation has no deposit gate awaiting evidence.")

    before = _snapshot(reservation, _RESERVATION_FIELDS)
    reservation.deposit_gate_status = GATE_CONFIRMED
    reservation.deposit_confirmation_reference = _require_reason(
        evidence_reference, detail="Record the reference of the deposit evidence."
    )
    reservation.deposit_confirmed_by_user_id = actor.user_id
    reservation.deposit_confirmed_at = _now()
    _flush(session)
    record_event(
        session,
        action="reservation.deposit_confirmed",
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


def waive_deposit(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    reason: str,
) -> Reservation:
    """Let a reservation proceed without its deposit, on a named signature."""
    permissions.require_financial_approver(actor)
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)
    _require_preparing(reservation)
    if reservation.deposit_gate_status != GATE_PENDING:
        raise ConflictError("This reservation has no deposit gate to waive.")

    before = _snapshot(reservation, _RESERVATION_FIELDS)
    reservation.deposit_gate_status = GATE_WAIVED
    reservation.deposit_waiver_reason = _require_reason(
        reason, detail="Say why the deposit is being waived."
    )
    reservation.deposit_confirmed_by_user_id = actor.user_id
    reservation.deposit_confirmed_at = _now()
    _flush(session)
    record_event(
        session,
        action="reservation.deposit_waived",
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reservation.deposit_waiver_reason,
        before=before,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


def _require_live_quote(
    session: Session, *, reservation: Reservation, unit: Unit, today: date
) -> None:
    """Refuse to *take* a unit on a quote that is not the price it is offered at.

    The rule before a reservation commits anything. Until that moment the buyer
    has been shown a number and nobody has agreed to it, so the number had
    better still be the one on the list: a draft prepared last month against a
    superseded price is not something to hold a unit with.

    Five separate refusals, each with its own message, because "invalid" tells
    an operator nothing: the reservation has run out, the lock has run out, the
    unit's pricing was withdrawn, the price it was cut from is no longer live, or
    there is no frozen quote at all.
    """
    _require_lock_intact(reservation=reservation, today=today)
    if not unit.pricing_approved:
        raise ConflictError("This unit requires repricing before it can be committed.")
    active = pricing_service.active_price(session, unit_id=unit.id)
    if active is None or active.id != reservation.unit_price_version_id:
        raise ConflictError(
            "The unit's price has changed since this reservation was quoted. "
            "Re-quote it before activating."
        )


def _require_lock_intact(*, reservation: Reservation, today: date) -> None:
    """Refuse to proceed on a reservation that has run out of time."""
    if reservation.expires_on < today:
        raise ConflictError("This reservation has expired. Close it and prepare a new one.")
    if reservation.price_locked_until < today:
        raise ConflictError(
            "The price lock on this reservation has expired. Re-quote it before proceeding."
        )
    if not reservation.quote_snapshot_json:  # pragma: no cover - creation always freezes one
        raise ConflictError("This reservation has no frozen quote.")


def _require_locked_quote_still_sellable(
    session: Session, *, reservation: Reservation, today: date
) -> None:
    """Refuse to contract on a locked quote that has stopped describing the unit.

    The rule *after* a reservation has committed, and deliberately a different
    one. A price lock is a promise: for these thirty days this buyer pays this
    number. Finance putting a new list price live the following Wednesday is
    commercial repricing — it changes what the unit is offered at tomorrow and
    says nothing about what this buyer already agreed. Refusing the sale because
    the frozen version is no longer today's active price would make the lock
    mean nothing, which is why this does not ask that question.

    What it does ask is whether the unit is still the unit. Pricing owns the
    comparison of a version's frozen basis against current inventory, and
    answers it through one public contract; a locked price is not permission to
    sell a materially different flat under last month's geometry.
    """
    _require_lock_intact(reservation=reservation, today=today)
    version = pricing_service.get_price_version(
        session,
        project_id=reservation.project_id,
        version_id=reservation.unit_price_version_id,
    )
    try:
        pricing_service.require_price_basis_current(session, version=version)
    except ConflictError as exc:
        raise ConflictError(
            "This unit has changed since the reservation was quoted. Re-quote it "
            "before drawing up a contract."
        ) from exc


def _require_exception_settled(reservation: Reservation) -> None:
    if reservation.exception_approval_status in {EXCEPTION_PENDING, EXCEPTION_SUBMITTED}:
        raise ConflictError("This reservation's commercial exception has not been approved.")
    if reservation.exception_approval_status == EXCEPTION_REJECTED:
        raise ConflictError("This reservation's commercial exception was refused.")


def activate_reservation(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    effective_date: date | None = None,
) -> Reservation:
    """Commit the unit to this buyer. One transaction, one commit.

    Everything below is a precondition rather than a step: the unit must be
    available, released, priced and unencumbered; the quote must still describe
    it; the buyers must add up to a whole flat; every exception must be settled
    and the deposit gate satisfied. Only then does the unit move, and it moves
    through inventory's own contract, which writes the status event and the
    audit entry that make the change explainable afterwards.

    The order of locks is fixed project → unit → reservation, the same order
    every other operation in this module takes them, because two operations
    taking two locks in two orders is a deadlock waiting for load.
    """
    permissions.require_reservation_writer(actor)
    permissions.require_operational_project(project)
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    client = permissions.require_visible_client(
        session, project=project, client_id=reservation.client_id, actor=actor
    )

    project = lock_project(session, project.id)
    unit = inventory_service.lock_unit(session, project_id=project.id, unit_id=reservation.unit_id)
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)

    today = inventory_fields.business_today()
    effective_date = _effective(effective_date)
    if reservation.status not in RESERVATION_PREPARING:
        raise ConflictError("Only a reservation in preparation can be activated.")
    if not unit.is_active:
        raise ConflictError("This unit is not active.")
    if unit.commercial_status != COMMERCIAL_STATUS_AVAILABLE:
        raise ConflictError(
            f"This unit is {unit.commercial_status.replace('_', ' ')}, not available."
        )
    blockers = inventory_service.release_blockers(session, unit=unit, today=today)
    if blockers:
        raise ConflictError("This unit is not released for sale: " + "; ".join(blockers) + ".")
    _require_no_commitment(session, unit=unit, today=today)
    if not client.is_active:
        raise ConflictError("This client is not active.")
    _require_reconciled_shares(session, client=client)
    _require_live_quote(session, reservation=reservation, unit=unit, today=today)
    _require_exception_settled(reservation)
    if reservation.deposit_gate_status not in GATE_SATISFIED:
        raise ConflictError("The deposit on this reservation has not been confirmed or waived.")

    before = _snapshot(reservation, _RESERVATION_FIELDS)
    from_status = reservation.status
    reservation.status = RESERVATION_ACTIVE
    reservation.activated_at = _now()
    _record_reservation_event(
        session,
        reservation=reservation,
        from_status=from_status,
        to_status=RESERVATION_ACTIVE,
        effective_date=effective_date,
        actor=actor,
    )
    inventory_service.apply_sales_commercial_status(
        session,
        project=project,
        unit=unit,
        to_status=COMMERCIAL_STATUS_RESERVED,
        effective_date=effective_date,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=f"Reservation {reservation.reservation_number} activated.",
    )
    _flush(session)
    record_event(
        session,
        action="reservation.activated",
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


def extend_reservation(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    expires_on: date,
    reason: str,
    effective_date: date | None = None,
) -> Reservation:
    """Push a live reservation's expiry out. The quote does not move with it.

    An extension past the price lock is refused rather than repriced. Silently
    re-quoting would change what the buyer was told while they were still
    deciding, which is the one thing a price lock exists to prevent.
    """
    permissions.require_reservation_writer(actor)
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)
    if reservation.status not in RESERVATION_COMMITTED:
        raise ConflictError("Only a live reservation can be extended.")
    if expires_on <= reservation.expires_on:
        raise ValidationError("The new expiry must be later than the current one.")
    if expires_on > reservation.price_locked_until:
        raise ConflictError(
            "Re-quote the reservation before extending it beyond the approved price lock."
        )

    before = _snapshot(reservation, _RESERVATION_FIELDS)
    from_status = reservation.status
    reservation.expires_on = expires_on
    reservation.status = RESERVATION_EXTENDED
    _record_reservation_event(
        session,
        reservation=reservation,
        from_status=from_status,
        to_status=RESERVATION_EXTENDED,
        effective_date=_effective(effective_date),
        actor=actor,
        reason=_require_reason(reason, detail="Say why the reservation is being extended."),
    )
    _flush(session)
    record_event(
        session,
        action="reservation.extended",
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


def _close_reservation(
    session: Session,
    *,
    project: Project,
    reservation: Reservation,
    actor: ActorContext,
    to_status: str,
    effective_date: date,
    reason: str,
    action: str,
) -> Reservation:
    """End a reservation and put the unit back where the release rules allow.

    Shared by expiry and cancellation because the unit side is identical: a
    reservation letting go of a unit does not decide the unit is sellable again.
    Release is inventory's gate and it is asked, not assumed — a unit whose
    pricing has since been withdrawn comes back to ``held``, not to the market.
    """
    project = lock_project(session, project.id)
    unit = inventory_service.lock_unit(session, project_id=project.id, unit_id=reservation.unit_id)
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)
    if reservation.status not in RESERVATION_COMMITTED:
        raise ConflictError("Only a live reservation can be closed this way.")
    sale = session.scalars(
        select(SaleContract).where(
            SaleContract.reservation_id == reservation.id,
            SaleContract.status != SALE_CANCELLED,
        )
    ).first()
    if sale is not None and sale.status != SALE_DRAFT:
        raise ConflictError(f"Sale contract {sale.sale_number} has taken this reservation over.")

    before = _snapshot(reservation, _RESERVATION_FIELDS)
    from_status = reservation.status
    reservation.status = to_status
    reservation.closed_at = _now()
    reservation.closure_reason = reason
    _record_reservation_event(
        session,
        reservation=reservation,
        from_status=from_status,
        to_status=to_status,
        effective_date=effective_date,
        actor=actor,
        reason=reason,
    )
    if unit.commercial_status == COMMERCIAL_STATUS_RESERVED:
        _release_or_hold(
            session,
            project=project,
            unit=unit,
            actor=actor,
            effective_date=effective_date,
            reason=reason,
        )
    _flush(session)
    record_event(
        session,
        action=action,
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


def _release_or_hold(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    actor: ActorContext,
    effective_date: date,
    reason: str,
) -> None:
    """Put a unit a commitment has let go of back where the release gates allow.

    A reservation ending is not a decision that the unit is sellable again. If
    every release gate still passes it goes back on the market; if one does not
    — most often because the price was withdrawn while the unit was reserved —
    it goes to ``held``, with the blockers recorded as the reason. Held is an
    inventory state with an inventory route back to available, so the next
    person to offer this unit has to go through the gate rather than around it.
    """
    blockers = inventory_service.release_blockers(
        session, unit=unit, today=effective_date, actor=actor
    )
    if blockers:
        inventory_service.apply_sales_commercial_status(
            session,
            project=project,
            unit=unit,
            to_status=COMMERCIAL_STATUS_HELD,
            effective_date=effective_date,
            actor_user_id=actor.user_id,
            correlation_id=actor.correlation_id,
            reason=f"{reason} Not releasable: {'; '.join(blockers)}.",
        )
        return
    inventory_service.apply_sales_commercial_status(
        session,
        project=project,
        unit=unit,
        to_status=COMMERCIAL_STATUS_AVAILABLE,
        effective_date=effective_date,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason,
    )


def expire_reservation(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    effective_date: date | None = None,
) -> Reservation:
    """Close a reservation that has run past its expiry date.

    Explicit, because nothing in this system expires a reservation on its own.
    A reservation past its date keeps holding the unit and is displayed as
    "Expired — closure required" until an authorised person closes it: a
    scheduler doing it silently would move commercial commitments with no actor
    and no reason behind them, and a GET doing it would be a hidden write.
    """
    permissions.require_reservation_writer(actor)
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    today = inventory_fields.business_today()
    if reservation.expires_on >= today:
        raise ConflictError("This reservation has not expired yet.")
    return _close_reservation(
        session,
        project=project,
        reservation=reservation,
        actor=actor,
        to_status=RESERVATION_EXPIRED,
        effective_date=_effective(effective_date),
        reason=f"Reservation expired on {reservation.expires_on.isoformat()}.",
        action="reservation.expired",
    )


def cancel_reservation(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    reason: str,
    effective_date: date | None = None,
) -> Reservation:
    """End a live reservation before its time, on a recorded reason.

    Nothing is deleted. The reservation, its quote, its adjustments and its
    status history all remain: what the company once agreed to is a fact even
    when it did not happen.
    """
    permissions.require_reservation_writer(actor)
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    return _close_reservation(
        session,
        project=project,
        reservation=reservation,
        actor=actor,
        to_status=RESERVATION_CANCELLED,
        effective_date=_effective(effective_date),
        reason=_require_reason(reason, detail="Say why the reservation is being cancelled."),
        action="reservation.cancelled",
    )


def list_reservation_events(
    session: Session, *, reservation: Reservation
) -> list[ReservationStatusEvent]:
    """A reservation's movement history, oldest first. Append-only."""
    return list(
        session.scalars(
            select(ReservationStatusEvent)
            .where(ReservationStatusEvent.reservation_id == reservation.id)
            .order_by(ReservationStatusEvent.effective_date, ReservationStatusEvent.created_at)
        )
    )


def _draft_contract_on(session: Session, *, reservation: Reservation) -> SaleContract | None:
    """The contract drawn up from this reservation and not yet cancelled."""
    return session.scalars(
        select(SaleContract).where(
            SaleContract.reservation_id == reservation.id,
            SaleContract.status != SALE_CANCELLED,
        )
    ).first()


def _refresh_draft_terms(session: Session, *, reservation: Reservation, sale: SaleContract) -> None:
    """Bring a draft contract back into step with the reservation it came from.

    A draft holds nothing and nobody has signed it, so this rewrites no
    agreement — it copies the reservation's terms across again, exactly as
    creating the draft did. Without it a re-quote would leave the draft
    describing a price the reservation no longer says, and the mismatch would
    surface as a refusal at submission with nothing the operator could do about
    it.
    """
    sale.unit_price_version_id = reservation.unit_price_version_id
    sale.currency_id = reservation.currency_id
    sale.reference_price_ex_tax = reservation.reference_price_ex_tax
    sale.gross_quoted_price_ex_tax = reservation.gross_quoted_price_ex_tax
    sale.cash_discount_amount = reservation.cash_discount_amount
    sale.seller_credit_amount = reservation.seller_credit_amount
    sale.net_contract_price_ex_tax = reservation.net_contract_price_ex_tax
    sale.seller_cost_total = reservation.seller_cost_total
    sale.effective_net_revenue_snapshot = reservation.effective_net_revenue_preview
    sale.tax_total = reservation.tax_total
    sale.buyer_fee_total = reservation.buyer_fee_total
    sale.total_contract_price = reservation.total_buyer_payable
    sale.reservation_quote_snapshot_json = reservation.quote_snapshot_json


def requote_reservation(
    session: Session,
    *,
    project: Project,
    reservation_id: uuid.UUID,
    actor: ActorContext,
    reason: str,
) -> Reservation:
    """Re-price a live reservation against the unit's current list price.

    The one way a committed reservation's commercial terms may move, and it is
    deliberately explicit. A price lock that has run out leaves a real and
    otherwise unresolvable position: the reservation still holds the unit, the
    buyer has not gone away, and no contract can be drawn up because the price
    they were promised has expired. Without this the only exits are cancelling a
    live commitment or silently repricing the buyer at submission, and the second
    is exactly what the lock exists to prevent.

    So the operator asks for a new quote, on the record, with a reason. The unit
    stays reserved for the same buyer, the same recorded adjustments are re-run
    against today's approved price, and the standing approval is withdrawn —
    because an exception sanctioned against last month's number says nothing
    about this month's. Where the new quote breaches the country's thresholds,
    it needs approving again before the sale can proceed.

    Nothing about pricing moves. The public list price is whatever pricing says
    it is; this reads it, and writes only to sales' own rows.
    """
    permissions.require_reservation_writer(actor)
    permissions.require_operational_project(project)
    reason = _require_reason(reason, detail="Say why this reservation is being re-quoted.")
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    client = permissions.require_visible_client(
        session, project=project, client_id=reservation.client_id, actor=actor
    )

    project = lock_project(session, project.id)
    unit = inventory_service.lock_unit(session, project_id=project.id, unit_id=reservation.unit_id)
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)

    today = inventory_fields.business_today()
    if reservation.status not in RESERVATION_COMMITTED:
        raise ConflictError("Only a live reservation can be re-quoted.")
    if reservation.expires_on < today:
        raise ConflictError("This reservation has expired. Close it and prepare a new one.")
    if unit.commercial_status != COMMERCIAL_STATUS_RESERVED:
        raise ConflictError(
            f"This unit is {unit.commercial_status.replace('_', ' ')}, not reserved."
        )
    committed = _committed_sale(session, unit_id=unit.id)
    if committed is not None:
        raise ConflictError(
            f"Sale contract {committed.sale_number} has taken this reservation over."
        )
    if not unit.pricing_approved:
        raise ConflictError("This unit requires repricing before it can be re-quoted.")
    active = pricing_service.active_price(session, unit_id=unit.id)
    if active is None:  # pragma: no cover - quote_preview refuses this first
        raise ConflictError("This unit has no active price to re-quote against.")
    _require_reconciled_shares(session, client=client)

    configuration = pricing_service.get_configuration(
        session, project_id=project.id, configuration_id=active.pricing_configuration_id
    )
    if configuration.price_lock_days is None:
        raise ValidationError(
            "This project's pricing configuration sets no price-lock period, so a "
            "re-quote has no term to run for."
        )

    before = _snapshot(reservation, _RESERVATION_FIELDS)
    _freeze_quote(
        session,
        project=project,
        unit=unit,
        reservation=reservation,
        buyer_fee_total=reservation.buyer_fee_total,
    )
    # The lock runs from today, not from the original reservation date: what the
    # buyer is being promised is this price, from now.
    reservation.price_locked_until = today + timedelta(days=configuration.price_lock_days)
    draft = _draft_contract_on(session, reservation=reservation)
    if draft is not None:
        _refresh_draft_terms(session, reservation=reservation, sale=draft)
    _flush(session)
    record_event(
        session,
        action="reservation.requoted",
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    session.commit()
    session.refresh(reservation)
    return reservation


# --------------------------------------------------------------------------- #
# Sale contracts
# --------------------------------------------------------------------------- #


def _lock_sale(session: Session, *, project_id: uuid.UUID, sale_id: uuid.UUID) -> SaleContract:
    """Take the contract row for update and return its committed state."""
    sale = session.scalars(
        select(SaleContract)
        .where(SaleContract.id == sale_id, SaleContract.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if sale is None:
        raise NotFoundError("Sale contract not found.")
    return sale


def list_sales(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    status: str | None = None,
    unit_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
) -> list[SaleContract]:
    """The contracts this caller may see, narrowed in SQL."""
    permissions.require_sales_reader(actor)
    statement = select(SaleContract).where(SaleContract.project_id == project.id)
    allowed_units = permissions.visible_unit_ids(session, project_id=project.id, actor=actor)
    if allowed_units is not None:
        statement = statement.where(SaleContract.unit_id.in_(allowed_units))
    if permissions.restricts_clients_to_own(actor):
        statement = statement.where(
            SaleContract.client_id.in_(
                select(Client.id).where(
                    Client.project_id == project.id,
                    Client.owner_advisor_user_id == actor.user_id,
                )
            )
        )
    if status is not None:
        statement = statement.where(SaleContract.status == status)
    if unit_id is not None:
        statement = statement.where(SaleContract.unit_id == unit_id)
    if client_id is not None:
        statement = statement.where(SaleContract.client_id == client_id)
    return list(session.scalars(statement.order_by(SaleContract.sale_number.desc())))


def get_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> SaleContract:
    """One contract the caller may see, or 404."""
    permissions.require_sales_reader(actor)
    sale = session.scalars(
        select(SaleContract).where(
            SaleContract.id == sale_id, SaleContract.project_id == project.id
        )
    ).first()
    if sale is None:
        raise NotFoundError("Sale contract not found.")
    permissions.require_sellable_unit(session, project=project, unit_id=sale.unit_id, actor=actor)
    permissions.require_visible_client(
        session, project=project, client_id=sale.client_id, actor=actor
    )
    return sale


def create_sale(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    reservation_id: uuid.UUID,
    contract_date: date | None = None,
    spa_number: str | None = None,
    first_payment_required_amount: Decimal | None = None,
) -> SaleContract:
    """Open a contract draft on an active reservation, copying its frozen quote.

    A draft holds nothing: the reservation still owns the unit, and it keeps
    owning it until the contract is submitted. There is deliberately no route
    from a bare unit to a contract — one canonical flow, reservation first, is
    what makes "who agreed to this price, and when" answerable for every sale in
    the register.
    """
    permissions.require_sale_writer(actor)
    permissions.require_operational_project(project)
    reservation = get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    client = permissions.require_visible_client(
        session, project=project, client_id=reservation.client_id, actor=actor
    )

    project = lock_project(session, project.id)
    unit = inventory_service.lock_unit(session, project_id=project.id, unit_id=reservation.unit_id)
    reservation = _lock_reservation(session, project_id=project.id, reservation_id=reservation.id)

    today = inventory_fields.business_today()
    contract_date = contract_date or today
    if contract_date > today:
        raise ValidationError("A contract cannot be dated in the future.")
    if reservation.status not in RESERVATION_COMMITTED:
        raise ConflictError("A contract can only be drawn up on a live reservation.")
    if reservation.expires_on < today:
        raise ConflictError(
            "The current reservation has expired but must be formally closed "
            "before a contract can be drawn up."
        )
    if unit.commercial_status != COMMERCIAL_STATUS_RESERVED:
        raise ConflictError(
            f"This unit is {unit.commercial_status.replace('_', ' ')}, not reserved."
        )
    existing = session.scalars(
        select(SaleContract).where(
            SaleContract.reservation_id == reservation.id,
            SaleContract.status != SALE_CANCELLED,
        )
    ).first()
    if existing is not None:
        raise ConflictError(f"Contract {existing.sale_number} already exists on this reservation.")
    if _committed_sale(session, unit_id=unit.id) is not None:
        raise ConflictError("Another contract already holds this unit.")
    _require_reconciled_shares(session, client=client)
    _require_locked_quote_still_sellable(session, reservation=reservation, today=today)
    _require_exception_settled(reservation)

    policy = policy_for(session, project=project)
    gate_required = first_payment_required_amount is not None
    sale = SaleContract(
        project_id=project.id,
        sale_number=_next_number(
            session,
            project=project,
            prefix="SALE",
            column=SaleContract.sale_number,
            project_column=SaleContract.project_id,
        ),
        spa_number=(spa_number or "").strip() or None,
        reservation_id=reservation.id,
        unit_id=unit.id,
        client_id=client.id,
        unit_price_version_id=reservation.unit_price_version_id,
        currency_id=reservation.currency_id,
        contract_date=contract_date,
        status=SALE_DRAFT,
        # The quote crosses over exactly as the reservation froze it. Nothing is
        # recalculated here: a contract that restated its own price would be a
        # different agreement from the one the buyer accepted.
        reference_price_ex_tax=reservation.reference_price_ex_tax,
        gross_quoted_price_ex_tax=reservation.gross_quoted_price_ex_tax,
        cash_discount_amount=reservation.cash_discount_amount,
        seller_credit_amount=reservation.seller_credit_amount,
        net_contract_price_ex_tax=reservation.net_contract_price_ex_tax,
        seller_cost_total=reservation.seller_cost_total,
        effective_net_revenue_snapshot=reservation.effective_net_revenue_preview,
        tax_total=reservation.tax_total,
        buyer_fee_total=reservation.buyer_fee_total,
        total_contract_price=reservation.total_buyer_payable,
        reservation_quote_snapshot_json=reservation.quote_snapshot_json,
        sales_channel_code=reservation.sales_channel_code,
        sales_branch_code=reservation.sales_branch_code,
        advisor_user_id=reservation.advisor_user_id,
        first_payment_required_amount=(
            _amount(first_payment_required_amount) if gate_required else None
        ),
        first_payment_gate_status=GATE_PENDING if gate_required else GATE_NOT_REQUIRED,
        created_by_user_id=actor.user_id,
    )
    session.add(sale)
    _flush(session)
    record_event(
        session,
        action="sale_contract.created",
        entity_type=ENTITY_SALE,
        entity_id=sale.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after={**_snapshot(sale, _SALE_FIELDS), "policy_id": policy.id},
    )
    session.commit()
    session.refresh(sale)
    return sale


def update_sale(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor: ActorContext,
    **fields: object,
) -> SaleContract:
    """Correct a draft contract's references and attribution.

    Draft only, and never a money column. After submission the commercial terms
    are what was signed: changing them means cancelling the pending contract,
    re-quoting the reservation, obtaining the approvals again and producing a
    new snapshot — which is four recorded decisions instead of one silent edit.
    """
    permissions.require_sale_writer(actor)
    sale = get_sale(session, project=project, sale_id=sale_id, actor=actor)
    sale = _lock_sale(session, project_id=project.id, sale_id=sale.id)
    if sale.status != SALE_DRAFT:
        raise ConflictError("This contract's terms are frozen. It is no longer a draft.")
    if "advisor_user_id" in fields:
        _require_advisor(
            session,
            advisor_user_id=fields["advisor_user_id"],  # type: ignore[arg-type]
        )
    for category, name in (
        (CATEGORY_SALES_CHANNEL, "sales_channel_code"),
        (CATEGORY_SALES_BRANCH, "sales_branch_code"),
    ):
        if name in fields:
            fields[name] = _require_reference(
                session,
                project=project,
                category=category,
                code=fields[name],  # type: ignore[arg-type]
            )
    if "first_payment_required_amount" in fields:
        amount = fields["first_payment_required_amount"]
        fields["first_payment_required_amount"] = _amount(amount) if amount is not None else None
        sale.first_payment_gate_status = GATE_PENDING if amount is not None else GATE_NOT_REQUIRED

    before = _snapshot(sale, _SALE_FIELDS)
    for name, value in fields.items():
        setattr(sale, name, value)
    _flush(session)
    record_event(
        session,
        action="sale_contract.updated",
        entity_type=ENTITY_SALE,
        entity_id=sale.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(sale, _SALE_FIELDS),
    )
    session.commit()
    session.refresh(sale)
    return sale


def _freeze_parties(session: Session, *, sale: SaleContract) -> None:
    """Copy the buyers onto the contract as they stand at signature.

    The client master will be corrected later — an address changes, a passport
    is renewed, a name is spelled properly at last. None of that may reach back
    into a signed contract, so the names and shares that were agreed are copied
    here and never updated again.
    """
    for party in session.scalars(
        select(ClientParty).where(
            ClientParty.client_id == sale.client_id, ClientParty.is_active.is_(True)
        )
    ):
        session.add(
            SaleContractParty(
                project_id=sale.project_id,
                sale_contract_id=sale.id,
                client_party_id=party.id,
                party_role=party.party_role,
                name_as_identification=party.name_as_identification,
                nationality_code=party.nationality_code,
                residency_code=party.residency_code,
                tax_id=party.tax_id,
                identity_document_type=party.identity_document_type,
                identity_document_number=party.identity_document_number,
                share_fraction=party.share_fraction,
                representative_name=party.representative_name,
                poa_reference=party.poa_reference,
            )
        )


def _freeze_tax_lines(session: Session, *, project: Project, sale: SaleContract) -> None:
    """Copy the tax observation the contract was priced under.

    Taken from the reservation's frozen quote rather than recomputed, so a rate
    change next quarter cannot restate an SPA signed this one. ``tax_rule_id``
    is resolved where the rule still exists and left null where it does not: a
    missing pointer is honest, a wrong one is not.
    """
    snapshot = sale.reservation_quote_snapshot_json or {}
    lines = snapshot.get("taxes") or []
    valid_on = snapshot.get("tax_valid_on")
    as_of = date.fromisoformat(valid_on) if isinstance(valid_on, str) else sale.contract_date
    rules = {
        rule.tax_code: rule
        for rule in settings_service.list_tax_rules(
            session, country_pack_id=project.country_pack_id
        )
    }
    for line in lines:
        rule = rules.get(line["tax_code"])
        session.add(
            SaleContractTaxLine(
                project_id=sale.project_id,
                sale_contract_id=sale.id,
                tax_rule_id=rule.id if rule is not None else None,
                tax_code=line["tax_code"],
                label=line["label"],
                rate_fraction=Decimal(str(line["rate_fraction"])),
                calculation_basis=line["calculation_basis"],
                taxable_amount=sale.net_contract_price_ex_tax,
                tax_amount=Decimal(str(line["amount"])),
                currency_id=sale.currency_id,
                valid_on=as_of,
            )
        )


def submit_sale(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor: ActorContext,
    spa_number: str | None = None,
    effective_date: date | None = None,
) -> SaleContract:
    """Hand the unit's commitment from the reservation to the contract.

    The only moment in this module where a commitment moves between two records,
    and therefore the one that must be indivisible: the reservation becomes
    converted, the contract becomes signature-pending and the unit becomes
    contract-pending in a single transaction. There is no instant in between at
    which the unit looks available, because there is no commit in between.

    Everything that made the reservation valid is re-checked against the locked
    rows first. A contract drafted last week on a price that has since been
    superseded does not quietly become the contract.
    """
    permissions.require_sale_writer(actor)
    sale = get_sale(session, project=project, sale_id=sale_id, actor=actor)
    client = permissions.require_visible_client(
        session, project=project, client_id=sale.client_id, actor=actor
    )

    project = lock_project(session, project.id)
    unit = inventory_service.lock_unit(session, project_id=project.id, unit_id=sale.unit_id)
    reservation = _lock_reservation(
        session, project_id=project.id, reservation_id=sale.reservation_id
    )
    sale = _lock_sale(session, project_id=project.id, sale_id=sale.id)

    today = inventory_fields.business_today()
    effective_date = _effective(effective_date)
    if sale.status != SALE_DRAFT:
        raise ConflictError("Only a draft contract can be submitted.")
    if reservation.status not in RESERVATION_COMMITTED:
        raise ConflictError("The reservation behind this contract is no longer live.")
    if unit.commercial_status != COMMERCIAL_STATUS_RESERVED:
        raise ConflictError(
            f"This unit is {unit.commercial_status.replace('_', ' ')}, not reserved."
        )
    if _committed_sale(session, unit_id=unit.id) is not None:
        raise ConflictError("Another contract already holds this unit.")
    _require_reconciled_shares(session, client=client)
    _require_locked_quote_still_sellable(session, reservation=reservation, today=today)
    _require_exception_settled(reservation)
    if (
        sale.net_contract_price_ex_tax != reservation.net_contract_price_ex_tax
        or sale.total_contract_price != reservation.total_buyer_payable
        or sale.seller_cost_total != reservation.seller_cost_total
    ):  # pragma: no cover - only reachable if a price column were writable
        raise ConflictError(
            "This contract's terms no longer match the reservation it was drawn from."
        )

    before = _snapshot(sale, _SALE_FIELDS)
    if spa_number is not None:
        sale.spa_number = spa_number.strip() or None
    sale.status = SALE_SIGNATURE_PENDING
    sale.submitted_at = _now()
    sale.submitted_by_user_id = actor.user_id
    _freeze_parties(session, sale=sale)
    _freeze_tax_lines(session, project=project, sale=sale)

    reservation_before = _snapshot(reservation, _RESERVATION_FIELDS)
    reservation_from = reservation.status
    reservation.status = RESERVATION_CONVERTED
    reservation.converted_at = _now()
    _record_reservation_event(
        session,
        reservation=reservation,
        from_status=reservation_from,
        to_status=RESERVATION_CONVERTED,
        effective_date=effective_date,
        actor=actor,
        reason=f"Converted to sale contract {sale.sale_number}.",
    )
    inventory_service.apply_sales_commercial_status(
        session,
        project=project,
        unit=unit,
        to_status=COMMERCIAL_STATUS_CONTRACT_PENDING,
        effective_date=effective_date,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=f"Sale contract {sale.sale_number} submitted for signature.",
    )
    _flush(session)
    record_event(
        session,
        action="reservation.converted",
        entity_type=ENTITY_RESERVATION,
        entity_id=reservation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=reservation_before,
        after=_snapshot(reservation, _RESERVATION_FIELDS),
    )
    record_event(
        session,
        action="sale_contract.submitted",
        entity_type=ENTITY_SALE,
        entity_id=sale.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(sale, _SALE_FIELDS),
    )
    session.commit()
    session.refresh(sale)
    return sale


def confirm_first_payment(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor: ActorContext,
    evidence_reference: str,
) -> SaleContract:
    """Record that first-payment evidence exists. Never that money arrived.

    The same attestation the deposit gate is, at the same distance from cash.
    ``first_payment_required_amount`` is what the contract says is due before
    activation; it is not a receipt, not collected, and must never appear in a
    cash or collections figure. PR-MVP-07 owns the record that can say a payment
    was received, and this one is deliberately named so the two cannot be
    mistaken for each other.
    """
    permissions.require_gate_evidence_recorder(actor)
    sale = get_sale(session, project=project, sale_id=sale_id, actor=actor)
    sale = _lock_sale(session, project_id=project.id, sale_id=sale.id)
    if sale.status not in {SALE_DRAFT, SALE_SIGNATURE_PENDING}:
        raise ConflictError("This contract is past the first-payment gate.")
    if sale.first_payment_gate_status != GATE_PENDING:
        raise ConflictError("This contract has no first-payment gate awaiting evidence.")

    before = _snapshot(sale, _SALE_FIELDS)
    sale.first_payment_gate_status = GATE_CONFIRMED
    sale.first_payment_evidence_reference = _require_reason(
        evidence_reference, detail="Record the reference of the payment evidence."
    )
    sale.first_payment_confirmed_by_user_id = actor.user_id
    sale.first_payment_confirmed_at = _now()
    _flush(session)
    record_event(
        session,
        action="sale_contract.first_payment_confirmed",
        entity_type=ENTITY_SALE,
        entity_id=sale.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(sale, _SALE_FIELDS),
    )
    session.commit()
    session.refresh(sale)
    return sale


def waive_first_payment(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor: ActorContext,
    reason: str,
) -> SaleContract:
    """Let a contract activate without its first payment, on a named signature."""
    permissions.require_financial_approver(actor)
    sale = get_sale(session, project=project, sale_id=sale_id, actor=actor)
    sale = _lock_sale(session, project_id=project.id, sale_id=sale.id)
    if sale.status not in {SALE_DRAFT, SALE_SIGNATURE_PENDING}:
        raise ConflictError("This contract is past the first-payment gate.")
    if sale.first_payment_gate_status != GATE_PENDING:
        raise ConflictError("This contract has no first-payment gate to waive.")

    before = _snapshot(sale, _SALE_FIELDS)
    sale.first_payment_gate_status = GATE_WAIVED
    sale.first_payment_waiver_reason = _require_reason(
        reason, detail="Say why the first payment is being waived."
    )
    sale.first_payment_confirmed_by_user_id = actor.user_id
    sale.first_payment_confirmed_at = _now()
    _flush(session)
    record_event(
        session,
        action="sale_contract.first_payment_waived",
        entity_type=ENTITY_SALE,
        entity_id=sale.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=sale.first_payment_waiver_reason,
        before=before,
        after=_snapshot(sale, _SALE_FIELDS),
    )
    session.commit()
    session.refresh(sale)
    return sale


def activate_sale(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor: ActorContext,
    effective_date: date | None = None,
) -> SaleContract:
    """Make the contract commercially live and the unit contracted.

    Both signatures must already be recorded as legal events. That is the point
    of insisting the legal timeline exists: "the contract is signed" should be a
    dated, attributed record somebody entered, not a checkbox on the contract
    that anybody could tick.
    """
    permissions.require_sale_writer(actor)
    sale = get_sale(session, project=project, sale_id=sale_id, actor=actor)

    project = lock_project(session, project.id)
    unit = inventory_service.lock_unit(session, project_id=project.id, unit_id=sale.unit_id)
    sale = _lock_sale(session, project_id=project.id, sale_id=sale.id)

    effective_date = _effective(effective_date)
    if sale.status != SALE_SIGNATURE_PENDING:
        raise ConflictError("Only a contract awaiting signature can be activated.")
    if unit.commercial_status != COMMERCIAL_STATUS_CONTRACT_PENDING:
        raise ConflictError(
            f"This unit is {unit.commercial_status.replace('_', ' ')}, not contract pending."
        )
    recorded = _recorded_event_types(session, sale_id=sale.id)
    missing = {EVENT_BUYER_SIGNED, EVENT_SELLER_SIGNED} - recorded
    if missing:
        raise ConflictError(
            "Record the signature events before activating: "
            + ", ".join(sorted(name.replace("_", " ") for name in missing))
            + "."
        )
    if sale.first_payment_gate_status not in GATE_SATISFIED:
        raise ConflictError("The first payment on this contract has not been confirmed or waived.")
    reservation = session.get(Reservation, sale.reservation_id)
    if reservation is None or reservation.status != RESERVATION_CONVERTED:
        raise ConflictError("The reservation behind this contract was not converted.")

    before = _snapshot(sale, _SALE_FIELDS)
    sale.status = SALE_ACTIVE
    sale.activated_at = _now()
    sale.activated_by_user_id = actor.user_id
    inventory_service.apply_sales_commercial_status(
        session,
        project=project,
        unit=unit,
        to_status=COMMERCIAL_STATUS_CONTRACTED,
        effective_date=effective_date,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=f"Sale contract {sale.sale_number} activated.",
    )
    _flush(session)
    record_event(
        session,
        action="sale_contract.activated",
        entity_type=ENTITY_SALE,
        entity_id=sale.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(sale, _SALE_FIELDS),
    )
    session.commit()
    session.refresh(sale)
    return sale


def list_sale_parties(session: Session, *, sale: SaleContract) -> list[SaleContractParty]:
    """The buyers as the contract froze them. Immutable after submission."""
    return list(
        session.scalars(
            select(SaleContractParty)
            .where(SaleContractParty.sale_contract_id == sale.id)
            .order_by(SaleContractParty.created_at)
        )
    )


def list_sale_tax_lines(session: Session, *, sale: SaleContract) -> list[SaleContractTaxLine]:
    """The tax observation the contract was priced under. Immutable."""
    return list(
        session.scalars(
            select(SaleContractTaxLine)
            .where(SaleContractTaxLine.sale_contract_id == sale.id)
            .order_by(SaleContractTaxLine.tax_code)
        )
    )


# --------------------------------------------------------------------------- #
# Legal events
# --------------------------------------------------------------------------- #

#: The order the legal milestones actually happen in. Used for chronology, not
#: as a workflow: nothing here executes a step, and an event can be entered long
#: after the fact — it just cannot be entered as having happened before
#: something that necessarily preceded it.
_LEGAL_ORDER: tuple[str, ...] = LEGAL_EVENT_TYPES

#: What must already be on the record before each event can be. Small, explicit
#: and jurisdiction-neutral: a seller cannot sign an SPA that was never issued,
#: and a title cannot transfer before the registration that establishes it.
#: Anything finer than this is a country's own procedure, and hard-coding one
#: country's procedure would make the second country a rewrite.
_LEGAL_PREREQUISITES: dict[str, frozenset[str]] = {
    "spa_approved": frozenset({"spa_drafted"}),
    "spa_issued": frozenset({"spa_drafted"}),
    "buyer_signed": frozenset({"spa_issued"}),
    "seller_signed": frozenset({"spa_issued"}),
    "stamped": frozenset({"buyer_signed", "seller_signed"}),
    "stamp_duty_recorded": frozenset({"stamped"}),
    "land_registry_lodged": frozenset({"buyer_signed", "seller_signed"}),
    "land_registry_accepted": frozenset({"land_registry_lodged"}),
    "registered": frozenset({"land_registry_lodged"}),
    "title_transfer_pending": frozenset({"registered"}),
    "title_transferred": frozenset({"registered"}),
    "withdrawn": frozenset({"withdrawal_started"}),
}

#: The unit legal status each recorded event establishes. The status is never
#: set directly anywhere: it is what the most recent effective legal event says
#: it is, so a unit displaying "registered" always has a dated, attributed,
#: evidenced record behind it.
_LEGAL_STATUS_OF: dict[str, str] = {
    "spa_drafted": "drafting",
    "spa_approved": "drafting",
    "spa_issued": "issued",
    "buyer_signed": "buyer_signed",
    "seller_signed": "fully_signed",
    "stamped": "stamped",
    "stamp_duty_recorded": "stamped",
    "land_registry_lodged": "lodged_submitted",
    "land_registry_accepted": "lodged_submitted",
    "registered": "registered",
    "title_transfer_pending": "transfer_pending",
    "title_transferred": "transferred",
    "withdrawal_started": "withdrawal_pending",
    "withdrawn": "withdrawn",
}

#: The events that mean the registry is involved and cannot simply be forgotten.
#: A contract that reached any of them needs a recorded withdrawal before its
#: unit goes back on the market: the register still says somebody else's name.
REGISTRY_ENGAGED_EVENTS = frozenset(
    {EVENT_LODGED, EVENT_REGISTERED, EVENT_TRANSFER_PENDING, EVENT_TRANSFERRED}
)


def list_legal_events(session: Session, *, sale: SaleContract) -> list[SaleLegalEvent]:
    """A contract's legal timeline, oldest first. Append-only, reversals and all."""
    return list(
        session.scalars(
            select(SaleLegalEvent)
            .where(SaleLegalEvent.sale_contract_id == sale.id)
            .order_by(SaleLegalEvent.event_date, SaleLegalEvent.created_at)
        )
    )


def effective_legal_events(session: Session, *, sale_id: uuid.UUID) -> list[SaleLegalEvent]:
    """The events that still stand: neither reversals nor reversed.

    A reversal does not delete anything. Both rows remain on the timeline, and
    both are shown; this is the reading of that timeline that the unit's legal
    status is derived from.
    """
    events = list(
        session.scalars(select(SaleLegalEvent).where(SaleLegalEvent.sale_contract_id == sale_id))
    )
    reversed_ids = {event.reverses_event_id for event in events if event.reverses_event_id}
    return [
        event
        for event in events
        if event.reverses_event_id is None and event.id not in reversed_ids
    ]


def _recorded_event_types(session: Session, *, sale_id: uuid.UUID) -> set[str]:
    return {event.event_type for event in effective_legal_events(session, sale_id=sale_id)}


def derived_legal_status(events: list[SaleLegalEvent]) -> str:
    """The legal status the timeline as a whole establishes.

    The furthest milestone reached, by the canonical order — not the most
    recently entered row, because an event entered late about something that
    happened early must not drag the status backwards.
    """
    if not events:
        return LEGAL_STATUS_NO_SPA
    furthest = max(events, key=lambda event: _LEGAL_ORDER.index(event.event_type))
    return _LEGAL_STATUS_OF[furthest.event_type]


def _require_legal_chronology(
    session: Session, *, sale: SaleContract, event_type: str, event_date: date
) -> None:
    """Refuse an event the recorded timeline says could not have happened.

    Three separate refusals, each with its own message, because "invalid" tells
    an operator nothing: the milestone is already recorded, something it depends
    on is not, or the date puts it on the wrong side of an event it must follow
    or precede.
    """
    recorded = {
        event.event_type: event for event in effective_legal_events(session, sale_id=sale.id)
    }
    if event_type in recorded:
        raise ConflictError(
            f"This contract already has a {event_type.replace('_', ' ')} event. "
            "Reverse the existing one if it was wrong."
        )
    missing = _LEGAL_PREREQUISITES.get(event_type, frozenset()) - set(recorded)
    if missing:
        raise ConflictError(
            "Record these first: "
            + ", ".join(sorted(name.replace("_", " ") for name in missing))
            + "."
        )
    position = _LEGAL_ORDER.index(event_type)
    for name, event in recorded.items():
        other = _LEGAL_ORDER.index(name)
        if other < position and event.event_date > event_date:
            raise ValidationError(
                f"{event_type.replace('_', ' ').capitalize()} cannot be dated before "
                f"{name.replace('_', ' ')} on {event.event_date.isoformat()}."
            )
        if other > position and event.event_date < event_date:
            raise ValidationError(
                f"{event_type.replace('_', ' ').capitalize()} cannot be dated after "
                f"{name.replace('_', ' ')} on {event.event_date.isoformat()}."
            )


def _require_title_transfer_gate(session: Session, *, project: Project, sale: SaleContract) -> None:
    """Refuse a title transfer the project's own policy says is premature.

    Where a development requires collections to be clear before title moves, the
    clearance has to be on the record — attested by Collections, not by the
    person recording the transfer. PR-MVP-07 will make that clearance an
    assertion about real money; until then it is an attestation, and it is still
    a different person's signature.
    """
    policy = policy_for(session, project=project)
    if not policy.title_transfer_requires_collection_clearance:
        return
    handover = session.scalars(
        select(HandoverRecord).where(HandoverRecord.sale_contract_id == sale.id)
    ).first()
    cleared = (
        handover is not None
        and session.scalars(
            select(HandoverClearance).where(
                HandoverClearance.handover_id == handover.id,
                HandoverClearance.clearance_type == CLEARANCE_COLLECTION,
                HandoverClearance.status == CLEARANCE_CLEARED,
            )
        ).first()
        is not None
    )
    if not cleared:
        raise ConflictError("This project requires a collection clearance before title transfers.")


def _apply_derived_legal_status(
    session: Session,
    *,
    project: Project,
    sale: SaleContract,
    actor: ActorContext,
    effective_date: date,
    reason: str,
) -> None:
    """Push the timeline's conclusion onto the unit, through inventory."""
    status = derived_legal_status(effective_legal_events(session, sale_id=sale.id))
    unit = inventory_service.lock_unit(session, project_id=project.id, unit_id=sale.unit_id)
    inventory_service.apply_legal_status(
        session,
        project=project,
        unit=unit,
        to_status=status,
        effective_date=effective_date,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason,
    )


def _record_withdrawal_progress(session: Session, *, sale: SaleContract, event_type: str) -> None:
    """Let an open cancellation know the registry unwind has been recorded.

    Both tables belong to this module, so this is not one domain reaching into
    another's state — it is the one place where "Legal recorded the withdrawal"
    and "the cancellation may now release the unit" are the same fact. Written
    here rather than read on demand so the cancellation carries its own answer
    and does not have to re-derive it from a timeline every time it is asked.
    """
    if event_type not in {EVENT_WITHDRAWAL_STARTED, EVENT_WITHDRAWN}:
        return
    cancellation = _open_cancellation(session, sale_id=sale.id)
    if cancellation is None or not cancellation.legal_withdrawal_required:
        return
    cancellation.legal_withdrawal_status = (
        WITHDRAWAL_COMPLETED if event_type == EVENT_WITHDRAWN else WITHDRAWAL_PENDING
    )


def record_legal_event(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor: ActorContext,
    event_type: str,
    event_date: date,
    authority_reference: str | None = None,
    document_reference: str | None = None,
    fee_amount: Decimal | None = None,
    currency_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> SaleLegalEvent:
    """Record what the registry, the notary or the parties actually did.

    Legal only. A sales desk that could record a registration would be a sales
    desk that could assert the buyer owns the flat, and the whole point of a
    separate legal timeline is that somebody else has to say so.

    A fee recorded here is a legal fact — what the authority charged — and not a
    cash movement. PR-MVP-10 owns money leaving the company.
    """
    permissions.require_legal_writer(actor)
    sale = get_sale(session, project=project, sale_id=sale_id, actor=actor)
    if event_type not in LEGAL_EVENT_TYPES:
        raise ValidationError("That is not a legal event type.")
    if sale.status == SALE_DRAFT:
        raise ConflictError("This contract has not been submitted for signature yet.")
    if event_date > inventory_fields.business_today():
        raise ValidationError("A legal event cannot be dated in the future.")
    if fee_amount is not None and currency_id is None:
        raise ValidationError("A recorded fee needs a currency.")

    project = lock_project(session, project.id)
    sale = _lock_sale(session, project_id=project.id, sale_id=sale.id)
    _require_legal_chronology(session, sale=sale, event_type=event_type, event_date=event_date)
    if event_type == EVENT_TRANSFERRED:
        _require_title_transfer_gate(session, project=project, sale=sale)

    event = SaleLegalEvent(
        project_id=project.id,
        sale_contract_id=sale.id,
        event_type=event_type,
        event_date=event_date,
        authority_reference=authority_reference,
        document_reference=document_reference,
        fee_amount=_amount(fee_amount) if fee_amount is not None else None,
        currency_id=currency_id,
        notes=notes,
        entered_by_user_id=actor.user_id,
    )
    session.add(event)
    _flush(session)
    _record_withdrawal_progress(session, sale=sale, event_type=event_type)
    _apply_derived_legal_status(
        session,
        project=project,
        sale=sale,
        actor=actor,
        effective_date=event_date,
        reason=f"{event_type.replace('_', ' ').capitalize()} recorded on contract "
        f"{sale.sale_number}.",
    )
    _flush(session)
    record_event(
        session,
        action="sale_legal_event.recorded",
        entity_type=ENTITY_LEGAL_EVENT,
        entity_id=event.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(event, _LEGAL_EVENT_FIELDS),
    )
    session.commit()
    session.refresh(event)
    return event


def reverse_legal_event(
    session: Session,
    *,
    project: Project,
    event_id: uuid.UUID,
    actor: ActorContext,
    reason: str,
    event_date: date | None = None,
) -> SaleLegalEvent:
    """Withdraw a legal event by recording another one that says so.

    There is no PATCH and no DELETE on this timeline. An event entered in error
    stays on the record with a correction beside it, because "we believed the
    title had transferred until the 14th" is itself a fact somebody will need —
    and because a legal record that can be quietly overwritten is not a legal
    record.
    """
    permissions.require_legal_writer(actor)
    original = session.scalars(
        select(SaleLegalEvent).where(
            SaleLegalEvent.id == event_id, SaleLegalEvent.project_id == project.id
        )
    ).first()
    if original is None:
        raise NotFoundError("Legal event not found.")
    sale = get_sale(session, project=project, sale_id=original.sale_contract_id, actor=actor)
    if original.reverses_event_id is not None:
        raise ConflictError("A correction cannot itself be reversed.")

    project = lock_project(session, project.id)
    sale = _lock_sale(session, project_id=project.id, sale_id=sale.id)
    if original.id not in {event.id for event in effective_legal_events(session, sale_id=sale.id)}:
        raise ConflictError("This event has already been reversed.")
    later = [
        event
        for event in effective_legal_events(session, sale_id=sale.id)
        if _LEGAL_ORDER.index(event.event_type) > _LEGAL_ORDER.index(original.event_type)
    ]
    if later:
        raise ConflictError(
            "Reverse the later events first: "
            + ", ".join(sorted(event.event_type.replace("_", " ") for event in later))
            + "."
        )

    correction = SaleLegalEvent(
        project_id=project.id,
        sale_contract_id=sale.id,
        event_type=original.event_type,
        event_date=event_date or inventory_fields.business_today(),
        reverses_event_id=original.id,
        reversal_reason=_require_reason(reason, detail="Say why this event is being withdrawn."),
        entered_by_user_id=actor.user_id,
    )
    session.add(correction)
    _flush(session)
    _apply_derived_legal_status(
        session,
        project=project,
        sale=sale,
        actor=actor,
        effective_date=correction.event_date,
        reason=correction.reversal_reason or "",
    )
    _flush(session)
    record_event(
        session,
        action="sale_legal_event.reversed",
        entity_type=ENTITY_LEGAL_EVENT,
        entity_id=correction.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=correction.reversal_reason,
        before=_snapshot(original, _LEGAL_EVENT_FIELDS),
        after=_snapshot(correction, _LEGAL_EVENT_FIELDS),
    )
    session.commit()
    session.refresh(correction)
    return correction


# --------------------------------------------------------------------------- #
# Cancellation
# --------------------------------------------------------------------------- #

#: How a cancellation case may move. Operational rather than jurisprudential:
#: notice, the cure period, the money decision, the registry unwind, the unit
#: coming back. ``withdrawn`` is the case itself being dropped — the parties
#: settled — and puts the contract back where it was.
_CANCELLATION_TRANSITIONS: dict[str, frozenset[str]] = {
    CANCELLATION_NOTICE: frozenset(
        {CANCELLATION_CURE, CANCELLATION_TERMINATION_PENDING, CANCELLATION_WITHDRAWN}
    ),
    CANCELLATION_CURE: frozenset({CANCELLATION_TERMINATION_PENDING, CANCELLATION_WITHDRAWN}),
    CANCELLATION_TERMINATION_PENDING: frozenset(
        {
            CANCELLATION_WITHDRAWAL_PENDING,
            CANCELLATION_READY_FOR_RETURN,
            CANCELLATION_WITHDRAWN,
        }
    ),
    CANCELLATION_WITHDRAWAL_PENDING: frozenset({CANCELLATION_READY_FOR_RETURN}),
    CANCELLATION_READY_FOR_RETURN: frozenset({CANCELLATION_WITHDRAWN}),
}


def _lock_cancellation(
    session: Session, *, project_id: uuid.UUID, cancellation_id: uuid.UUID
) -> SaleCancellation:
    cancellation = session.scalars(
        select(SaleCancellation)
        .where(
            SaleCancellation.id == cancellation_id,
            SaleCancellation.project_id == project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if cancellation is None:
        raise NotFoundError("Cancellation not found.")
    return cancellation


def get_cancellation(
    session: Session, *, project: Project, sale: SaleContract
) -> SaleCancellation | None:
    """The open cancellation case on a contract, if there is one."""
    return session.scalars(
        select(SaleCancellation)
        .where(SaleCancellation.sale_contract_id == sale.id)
        .order_by(SaleCancellation.created_at.desc())
    ).first()


def _open_cancellation(session: Session, *, sale_id: uuid.UUID) -> SaleCancellation | None:
    return session.scalars(
        select(SaleCancellation).where(
            SaleCancellation.sale_contract_id == sale_id,
            SaleCancellation.status.in_(CANCELLATION_OPEN),
        )
    ).first()


def start_cancellation(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor: ActorContext,
    initiated_by_party: str,
    reason: str,
    initiation_date: date | None = None,
    notice_date: date | None = None,
    cure_deadline: date | None = None,
    reason_code: str | None = None,
    forfeiture_amount: Decimal | None = None,
    refund_due_amount: Decimal | None = None,
) -> SaleCancellation:
    """Open the controlled process that ends a contract.

    Opening a case does not free the unit. It moves the contract to
    ``termination_pending``, which is deliberately not a state in which the unit
    looks sellable: between "we are cancelling" and "the unit is back" there is
    a money decision and, where the registry is involved, a withdrawal — and the
    unit stays committed until both are done.

    ``refund_due_amount`` is what the contract says is owed. There is no
    ``refund_paid``: a refund that was actually paid is a payment transaction,
    and PR-MVP-07 owns those.
    """
    permissions.require_cancellation_writer(actor)
    sale = get_sale(session, project=project, sale_id=sale_id, actor=actor)
    if initiated_by_party not in CANCELLATION_INITIATORS:
        raise ValidationError("That is not a cancellation initiator.")

    project = lock_project(session, project.id)
    sale = _lock_sale(session, project_id=project.id, sale_id=sale.id)
    # The open-case check comes first deliberately: a contract already in
    # termination is not "live", and telling the operator that would answer a
    # question they did not ask instead of the one they did.
    if _open_cancellation(session, sale_id=sale.id) is not None:
        raise ConflictError("This contract already has an open cancellation case.")
    if sale.status not in {SALE_SIGNATURE_PENDING, SALE_ACTIVE}:
        raise ConflictError("Only a live contract can be cancelled.")

    today = inventory_fields.business_today()
    initiation_date = initiation_date or today
    forfeiture = _amount(forfeiture_amount) if forfeiture_amount is not None else None
    refund = _amount(refund_due_amount) if refund_due_amount is not None else None
    registry = _recorded_event_types(session, sale_id=sale.id) & REGISTRY_ENGAGED_EVENTS

    cancellation = SaleCancellation(
        project_id=project.id,
        sale_contract_id=sale.id,
        initiated_by_party=initiated_by_party,
        initiation_date=initiation_date,
        notice_date=notice_date,
        cure_deadline=cure_deadline,
        reason_code=reason_code,
        reason=_require_reason(reason, detail="Say why the contract is being cancelled."),
        status=CANCELLATION_NOTICE,
        forfeiture_amount=forfeiture,
        refund_due_amount=refund,
        # Money changing hands on the way out is a decision somebody has to
        # sign. Where nothing is forfeited and nothing is owed, there is
        # nothing to approve and no signature is invented.
        financial_approval_required=bool(
            (forfeiture and forfeiture > ZERO) or (refund and refund > ZERO)
        ),
        legal_withdrawal_required=bool(registry),
        legal_withdrawal_status=WITHDRAWAL_PENDING if registry else WITHDRAWAL_NOT_REQUIRED,
        remarketing_required=True,
        created_by_user_id=actor.user_id,
    )
    session.add(cancellation)

    sale_before = _snapshot(sale, _SALE_FIELDS)
    sale.status = SALE_TERMINATION_PENDING
    _flush(session)
    record_event(
        session,
        action="sale_cancellation.started",
        entity_type=ENTITY_CANCELLATION,
        entity_id=cancellation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=cancellation.reason,
        after=_snapshot(cancellation, _CANCELLATION_FIELDS),
    )
    record_event(
        session,
        action="sale_contract.termination_started",
        entity_type=ENTITY_SALE,
        entity_id=sale.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=sale_before,
        after=_snapshot(sale, _SALE_FIELDS),
    )
    session.commit()
    session.refresh(cancellation)
    return cancellation


def approve_cancellation_terms(
    session: Session,
    *,
    project: Project,
    cancellation_id: uuid.UUID,
    actor: ActorContext,
    reason: str,
) -> SaleCancellation:
    """Sanction the forfeiture and refund the cancellation proposes.

    The office that approves a discount approves this too, and the person who
    opened the case cannot be the person who signs off the money coming out of
    it.
    """
    permissions.require_financial_approver(actor)
    cancellation = _lock_cancellation(
        session, project_id=project.id, cancellation_id=cancellation_id
    )
    get_sale(session, project=project, sale_id=cancellation.sale_contract_id, actor=actor)
    if not cancellation.financial_approval_required:
        raise ConflictError("This cancellation has no financial terms to approve.")
    if cancellation.financial_approved_at is not None:
        raise ConflictError("These financial terms have already been approved.")
    permissions.require_different_checker(actor, maker_user_id=cancellation.created_by_user_id)

    before = _snapshot(cancellation, _CANCELLATION_FIELDS)
    cancellation.financial_approved_by_user_id = actor.user_id
    cancellation.financial_approved_at = _now()
    _flush(session)
    record_event(
        session,
        action="sale_cancellation.financial_terms_approved",
        entity_type=ENTITY_CANCELLATION,
        entity_id=cancellation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=_require_reason(reason, detail="Say why these terms were approved."),
        before=before,
        after=_snapshot(cancellation, _CANCELLATION_FIELDS),
    )
    session.commit()
    session.refresh(cancellation)
    return cancellation


def advance_cancellation(
    session: Session,
    *,
    project: Project,
    cancellation_id: uuid.UUID,
    actor: ActorContext,
    to_status: str,
    reason: str | None = None,
    notice_date: date | None = None,
    cure_deadline: date | None = None,
) -> SaleCancellation:
    """Move a cancellation case one named step along.

    Withdrawing the case — the parties settled — puts the contract back to
    active and leaves the case on the record saying what nearly happened.
    """
    permissions.require_cancellation_writer(actor)
    if to_status not in CANCELLATION_STATUSES:
        raise ValidationError("That is not a cancellation status.")

    project = lock_project(session, project.id)
    cancellation = _lock_cancellation(
        session, project_id=project.id, cancellation_id=cancellation_id
    )
    sale = get_sale(session, project=project, sale_id=cancellation.sale_contract_id, actor=actor)
    sale = _lock_sale(session, project_id=project.id, sale_id=sale.id)

    allowed = _CANCELLATION_TRANSITIONS.get(cancellation.status, frozenset())
    if to_status not in allowed:
        raise ConflictError(
            f"A cancellation cannot move from {cancellation.status.replace('_', ' ')} "
            f"to {to_status.replace('_', ' ')}."
        )
    if to_status == CANCELLATION_READY_FOR_RETURN:
        if (
            cancellation.legal_withdrawal_required
            and cancellation.legal_withdrawal_status != WITHDRAWAL_COMPLETED
        ):
            raise ConflictError(
                "The registry withdrawal has not been recorded. The unit cannot be "
                "returned while the register still says otherwise."
            )
        if cancellation.financial_approval_required and cancellation.financial_approved_at is None:
            raise ConflictError("The cancellation's financial terms have not been approved.")

    before = _snapshot(cancellation, _CANCELLATION_FIELDS)
    sale_before = _snapshot(sale, _SALE_FIELDS)
    cancellation.status = to_status
    if notice_date is not None:
        cancellation.notice_date = notice_date
    if cure_deadline is not None:
        cancellation.cure_deadline = cure_deadline
    if to_status == CANCELLATION_WITHDRAWN:
        sale.status = SALE_ACTIVE if sale.activated_at else SALE_SIGNATURE_PENDING
    _flush(session)
    record_event(
        session,
        action="sale_cancellation.advanced",
        entity_type=ENTITY_CANCELLATION,
        entity_id=cancellation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=reason,
        before=before,
        after=_snapshot(cancellation, _CANCELLATION_FIELDS),
    )
    if to_status == CANCELLATION_WITHDRAWN:
        record_event(
            session,
            action="sale_contract.termination_withdrawn",
            entity_type=ENTITY_SALE,
            entity_id=sale.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            reason=reason,
            before=sale_before,
            after=_snapshot(sale, _SALE_FIELDS),
        )
    session.commit()
    session.refresh(cancellation)
    return cancellation


def complete_cancellation(
    session: Session,
    *,
    project: Project,
    cancellation_id: uuid.UUID,
    actor: ActorContext,
    unit_return_date: date | None = None,
) -> SaleCancellation:
    """End the contract and take the unit back. One transaction.

    The unit comes back as ``returned``, not ``available``, and its pricing
    approval is withdrawn. Those two facts are the same decision: the price this
    unit carried was the price of a deal that fell through, and putting it
    straight back on the list at that price would offer the next buyer a number
    nobody has re-agreed. Somebody prices it again, and inventory's release gate
    is what lets it back onto the market.
    """
    permissions.require_cancellation_writer(actor)
    project = lock_project(session, project.id)
    cancellation = _lock_cancellation(
        session, project_id=project.id, cancellation_id=cancellation_id
    )
    sale = get_sale(session, project=project, sale_id=cancellation.sale_contract_id, actor=actor)
    unit = inventory_service.lock_unit(session, project_id=project.id, unit_id=sale.unit_id)
    sale = _lock_sale(session, project_id=project.id, sale_id=sale.id)

    if cancellation.status != CANCELLATION_READY_FOR_RETURN:
        raise ConflictError("This cancellation is not ready for the unit to be returned.")
    if cancellation.financial_approval_required and cancellation.financial_approved_at is None:
        raise ConflictError("The cancellation's financial terms have not been approved.")
    if (
        cancellation.legal_withdrawal_required
        and cancellation.legal_withdrawal_status != WITHDRAWAL_COMPLETED
    ):
        raise ConflictError("The registry withdrawal has not been recorded.")
    handover = session.scalars(
        select(HandoverRecord).where(HandoverRecord.sale_contract_id == sale.id)
    ).first()
    if handover is not None and handover.status == HANDOVER_HANDED_OVER:
        raise ConflictError("This unit has already been handed over to the buyer.")

    effective_date = _effective(unit_return_date)
    before = _snapshot(cancellation, _CANCELLATION_FIELDS)
    sale_before = _snapshot(sale, _SALE_FIELDS)
    cancellation.status = CANCELLATION_COMPLETED
    cancellation.termination_date = effective_date
    cancellation.unit_return_date = effective_date
    sale.status = SALE_CANCELLED
    sale.cancelled_at = _now()
    inventory_service.apply_sales_commercial_status(
        session,
        project=project,
        unit=unit,
        to_status=COMMERCIAL_STATUS_RETURNED,
        effective_date=effective_date,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=f"Sale contract {sale.sale_number} cancelled: {cancellation.reason}",
    )
    inventory_service.invalidate_pricing(session, unit=unit)
    if handover is not None and handover.status != HANDOVER_CANCELLED:
        handover.status = HANDOVER_CANCELLED
    _flush(session)
    record_event(
        session,
        action="sale_cancellation.completed",
        entity_type=ENTITY_CANCELLATION,
        entity_id=cancellation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=cancellation.reason,
        before=before,
        after=_snapshot(cancellation, _CANCELLATION_FIELDS),
    )
    record_event(
        session,
        action="sale_contract.cancelled",
        entity_type=ENTITY_SALE,
        entity_id=sale.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=cancellation.reason,
        before=sale_before,
        after=_snapshot(sale, _SALE_FIELDS),
    )
    session.commit()
    session.refresh(cancellation)
    return cancellation


# --------------------------------------------------------------------------- #
# Handover
# --------------------------------------------------------------------------- #


def _lock_handover(
    session: Session, *, project_id: uuid.UUID, handover_id: uuid.UUID
) -> HandoverRecord:
    handover = session.scalars(
        select(HandoverRecord)
        .where(HandoverRecord.id == handover_id, HandoverRecord.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if handover is None:
        raise NotFoundError("Handover not found.")
    return handover


def get_handover(
    session: Session, *, project: Project, sale: SaleContract
) -> HandoverRecord | None:
    """The handover record on a contract, if one has been opened."""
    return session.scalars(
        select(HandoverRecord).where(
            HandoverRecord.sale_contract_id == sale.id,
            HandoverRecord.project_id == project.id,
        )
    ).first()


def create_handover(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor: ActorContext,
    readiness_date: date | None = None,
    scheduled_handover_date: date | None = None,
    notes: str | None = None,
) -> HandoverRecord:
    """Open the operational record for giving the buyer their keys.

    Three clearances are created pending at the same moment, one per department.
    Creating them up front rather than on demand is deliberate: the handover
    screen should say "three sign-offs, none of them given" from the first day,
    not grow gates as people happen to think of them.
    """
    permissions.require_handover_writer(actor)
    sale = get_sale(session, project=project, sale_id=sale_id, actor=actor)
    if sale.status != SALE_ACTIVE:
        raise ConflictError("Only an active contract can be prepared for handover.")

    project = lock_project(session, project.id)
    sale = _lock_sale(session, project_id=project.id, sale_id=sale.id)
    if get_handover(session, project=project, sale=sale) is not None:
        raise ConflictError("This contract already has a handover record.")

    handover = HandoverRecord(
        project_id=project.id,
        sale_contract_id=sale.id,
        readiness_date=readiness_date,
        scheduled_handover_date=scheduled_handover_date,
        notes=notes,
        status=HANDOVER_PREPARATION,
        created_by_user_id=actor.user_id,
    )
    session.add(handover)
    _flush(session)
    for clearance_type in CLEARANCE_TYPES:
        session.add(
            HandoverClearance(
                project_id=project.id,
                handover_id=handover.id,
                clearance_type=clearance_type,
                status=CLEARANCE_PENDING,
            )
        )
    _flush(session)
    record_event(
        session,
        action="handover.created",
        entity_type=ENTITY_HANDOVER,
        entity_id=handover.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(handover, _HANDOVER_FIELDS),
    )
    session.commit()
    session.refresh(handover)
    return handover


def update_handover(
    session: Session,
    *,
    project: Project,
    handover_id: uuid.UUID,
    actor: ActorContext,
    **fields: object,
) -> HandoverRecord:
    """Record inspection dates, snagging and scheduling.

    Cannot complete a handover: ``handed_over`` is the one status this route
    refuses, because that transition has gates in front of it and a PATCH that
    could set it would be a way around them.
    """
    permissions.require_handover_writer(actor)
    project_locked = lock_project(session, project.id)
    handover = _lock_handover(session, project_id=project_locked.id, handover_id=handover_id)
    get_sale(session, project=project, sale_id=handover.sale_contract_id, actor=actor)
    if handover.status == HANDOVER_HANDED_OVER:
        raise ConflictError("This unit has already been handed over.")

    status = fields.get("status")
    if status is not None:
        if status not in HANDOVER_STATUSES:
            raise ValidationError("That is not a handover status.")
        if status == HANDOVER_HANDED_OVER:
            raise ConflictError(
                "Complete the handover through its own action so the clearances are checked."
            )

    before = _snapshot(handover, _HANDOVER_FIELDS)
    for name, value in fields.items():
        setattr(handover, name, value)
    _flush(session)
    record_event(
        session,
        action="handover.updated",
        entity_type=ENTITY_HANDOVER,
        entity_id=handover.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(handover, _HANDOVER_FIELDS),
    )
    session.commit()
    session.refresh(handover)
    return handover


def list_clearances(session: Session, *, handover: HandoverRecord) -> list[HandoverClearance]:
    """Every clearance ever recorded on this handover, revoked ones included.

    History is the point: "this was cleared, then revoked on the 3rd, then
    cleared again" is exactly what somebody will need to see.
    """
    return list(
        session.scalars(
            select(HandoverClearance)
            .where(HandoverClearance.handover_id == handover.id)
            .order_by(HandoverClearance.clearance_type, HandoverClearance.created_at)
        )
    )


def _current_clearance(
    session: Session, *, handover_id: uuid.UUID, clearance_type: str
) -> HandoverClearance | None:
    """The live clearance of one type — the one the partial index permits."""
    return session.scalars(
        select(HandoverClearance).where(
            HandoverClearance.handover_id == handover_id,
            HandoverClearance.clearance_type == clearance_type,
            HandoverClearance.status != CLEARANCE_REVOKED,
        )
    ).first()


def _refuse_manual_collection_clearance(clearance_type: str) -> None:
    """Close the generic route for the one clearance that now has a ledger.

    Until PR-MVP-07 there was nothing to check a collection clearance against,
    so it was an attestation like the other two: somebody in Collections said
    the account was clear and the system took their word for it. There is a
    ledger now, and a signature that can contradict it is not a gate.

    Legal and delivery are untouched. Their concerns are judgements this system
    holds no arithmetic for, and an attestation remains the honest shape.
    """
    if clearance_type == CLEARANCE_COLLECTION:
        raise ConflictError(
            "The collection clearance is granted from the Collections account, where it "
            "is checked against the receivable. Clear the ledger and sign it off there."
        )


def _clearance_for_sale(
    session: Session, *, sale_id: uuid.UUID
) -> tuple[HandoverRecord, HandoverClearance | None] | None:
    """This sale's handover and its live collection clearance, if there is one."""
    handover = session.scalars(
        select(HandoverRecord).where(HandoverRecord.sale_contract_id == sale_id)
    ).first()
    if handover is None:
        return None
    return handover, _current_clearance(
        session, handover_id=handover.id, clearance_type=CLEARANCE_COLLECTION
    )


def apply_collection_clearance(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    evidence_reference: str,
) -> HandoverClearance:
    """Record Collections' sign-off, on Collections' say-so. Does not commit.

    Sales keeps owning :class:`HandoverClearance` — the rows, the partial index
    that permits one live clearance per type, and the handover gate that reads
    them. What it no longer owns is the decision, because the facts the decision
    rests on live in a ledger this module cannot see and should not learn to.

    The caller has already proved the account is clear. This writes the row.
    """
    found = _clearance_for_sale(session, sale_id=sale_id)
    if found is None:
        raise ConflictError(
            "This sale has no handover record yet, so there is no collection clearance "
            "to give. Start the handover first."
        )
    handover, clearance = found
    if handover.status == HANDOVER_HANDED_OVER:
        raise ConflictError("This unit has already been handed over.")
    if clearance is None:
        clearance = HandoverClearance(
            project_id=project.id,
            handover_id=handover.id,
            clearance_type=CLEARANCE_COLLECTION,
            status=CLEARANCE_PENDING,
        )
        session.add(clearance)
    if clearance.status == CLEARANCE_CLEARED:
        raise ConflictError("This clearance has already been given.")

    before = _snapshot(clearance, _CLEARANCE_FIELDS)
    clearance.status = CLEARANCE_CLEARED
    clearance.evidence_reference = evidence_reference
    clearance.cleared_by_user_id = actor_user_id
    clearance.cleared_at = _now()
    _flush(session)
    record_event(
        session,
        action="handover.clearance_granted",
        entity_type=ENTITY_CLEARANCE,
        entity_id=clearance.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(clearance, _CLEARANCE_FIELDS),
    )
    return clearance


def revoke_collection_clearance(
    session: Session,
    *,
    project: Project,
    sale_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason: str,
) -> HandoverClearance | None:
    """Withdraw the collection clearance when the ledger reopens. Does not commit.

    Returns ``None`` when there was nothing to withdraw, because the common case
    is exactly that: most receipt reversals happen on accounts nobody ever
    cleared, and a caller that had to distinguish "no handover yet" from "no
    clearance yet" from "already revoked" before every reversal would grow three
    branches for one outcome.

    A revoked row stays and, before handover, a fresh pending one replaces it,
    so the gate is closed again and the record still shows that somebody cleared
    it and the ledger later disagreed.

    **After handover the clearance is still revoked.** The physical handover is
    untouched — the keys are with the buyer and no part of this system claims
    otherwise — but the financial sign-off is a statement about the ledger, and
    the ledger has reopened. Leaving it reading ``cleared`` beside an account
    that is owed money again is the one outcome that would let a reversed
    receipt disappear from every screen that matters. What is *not* done is
    queue a new pending clearance: a pending gate on a completed handover would
    be a gate on nothing, and would read as though the unit were waiting to be
    handed over a second time.
    """
    found = _clearance_for_sale(session, sale_id=sale_id)
    if found is None:
        return None
    handover, clearance = found
    if clearance is None or clearance.status != CLEARANCE_CLEARED:
        return None
    handed_over = handover.status == HANDOVER_HANDED_OVER

    before = _snapshot(clearance, _CLEARANCE_FIELDS)
    clearance.status = CLEARANCE_REVOKED
    clearance.revoked_by_user_id = actor_user_id
    clearance.revoked_at = _now()
    clearance.revocation_reason = reason
    if not handed_over:
        session.add(
            HandoverClearance(
                project_id=project.id,
                handover_id=handover.id,
                clearance_type=CLEARANCE_COLLECTION,
                status=CLEARANCE_PENDING,
            )
        )
    _flush(session)
    record_event(
        session,
        action="handover.clearance_revoked",
        entity_type=ENTITY_CLEARANCE,
        entity_id=clearance.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        reason=reason,
        before=before,
        after=_snapshot(clearance, _CLEARANCE_FIELDS),
    )
    return clearance


def collection_clearance_status(session: Session, *, sale_id: uuid.UUID) -> str | None:
    """The live collection clearance's status, for the collections account view."""
    found = _clearance_for_sale(session, sale_id=sale_id)
    if found is None:
        return None
    _, clearance = found
    return clearance.status if clearance is not None else None


def grant_clearance(
    session: Session,
    *,
    project: Project,
    handover_id: uuid.UUID,
    clearance_type: str,
    actor: ActorContext,
    evidence_reference: str,
) -> HandoverClearance:
    """Sign off one department's concern about handing over this unit.

    Legal clears legal, Collections clears collections, and delivery belongs to
    the people who built the thing. Sales Operations completes the handover and
    signs none of the three: a gate one office can open on everyone's behalf is
    not a gate.
    """
    if clearance_type not in CLEARANCE_TYPES:
        raise ValidationError("That is not a clearance type.")
    permissions.require_clearance_owner(actor, clearance_type=clearance_type)
    _refuse_manual_collection_clearance(clearance_type)

    project_locked = lock_project(session, project.id)
    handover = _lock_handover(session, project_id=project_locked.id, handover_id=handover_id)
    get_sale(session, project=project, sale_id=handover.sale_contract_id, actor=actor)
    if handover.status == HANDOVER_HANDED_OVER:
        raise ConflictError("This unit has already been handed over.")

    clearance = _current_clearance(session, handover_id=handover.id, clearance_type=clearance_type)
    if clearance is None:
        clearance = HandoverClearance(
            project_id=project_locked.id,
            handover_id=handover.id,
            clearance_type=clearance_type,
            status=CLEARANCE_PENDING,
        )
        session.add(clearance)
    if clearance.status == CLEARANCE_CLEARED:
        raise ConflictError("This clearance has already been given.")

    before = _snapshot(clearance, _CLEARANCE_FIELDS)
    clearance.status = CLEARANCE_CLEARED
    clearance.evidence_reference = _require_reason(
        evidence_reference, detail="Record the reference of the evidence for this clearance."
    )
    clearance.cleared_by_user_id = actor.user_id
    clearance.cleared_at = _now()
    _flush(session)
    record_event(
        session,
        action="handover.clearance_granted",
        entity_type=ENTITY_CLEARANCE,
        entity_id=clearance.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(clearance, _CLEARANCE_FIELDS),
    )
    session.commit()
    session.refresh(clearance)
    return clearance


def revoke_clearance(
    session: Session,
    *,
    project: Project,
    handover_id: uuid.UUID,
    clearance_type: str,
    actor: ActorContext,
    reason: str,
) -> HandoverClearance:
    """Withdraw a clearance, and leave the record of it having been given.

    The revoked row stays and a fresh pending one takes its place, so the
    handover is blocked again and the history still shows that somebody cleared
    it and somebody else changed their mind.
    """
    if clearance_type not in CLEARANCE_TYPES:
        raise ValidationError("That is not a clearance type.")
    permissions.require_clearance_owner(actor, clearance_type=clearance_type)
    _refuse_manual_collection_clearance(clearance_type)

    project_locked = lock_project(session, project.id)
    handover = _lock_handover(session, project_id=project_locked.id, handover_id=handover_id)
    get_sale(session, project=project, sale_id=handover.sale_contract_id, actor=actor)
    if handover.status == HANDOVER_HANDED_OVER:
        raise ConflictError("This unit has already been handed over.")

    clearance = _current_clearance(session, handover_id=handover.id, clearance_type=clearance_type)
    if clearance is None or clearance.status != CLEARANCE_CLEARED:
        raise ConflictError("There is no given clearance of this type to revoke.")

    before = _snapshot(clearance, _CLEARANCE_FIELDS)
    clearance.status = CLEARANCE_REVOKED
    clearance.revoked_by_user_id = actor.user_id
    clearance.revoked_at = _now()
    clearance.revocation_reason = _require_reason(
        reason, detail="Say why this clearance is being withdrawn."
    )
    replacement = HandoverClearance(
        project_id=project_locked.id,
        handover_id=handover.id,
        clearance_type=clearance_type,
        status=CLEARANCE_PENDING,
    )
    session.add(replacement)
    _flush(session)
    record_event(
        session,
        action="handover.clearance_revoked",
        entity_type=ENTITY_CLEARANCE,
        entity_id=clearance.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=clearance.revocation_reason,
        before=before,
        after=_snapshot(clearance, _CLEARANCE_FIELDS),
    )
    session.commit()
    session.refresh(clearance)
    return clearance


def handover_blockers(
    session: Session, *, project: Project, sale: SaleContract, handover: HandoverRecord
) -> list[str]:
    """Everything standing between this handover and the buyer's keys.

    Returned as a list rather than raised one at a time so the screen can show
    the whole gate at once. Which of the clearances apply is the project's own
    configuration — five booleans, named, in ``sales_project_policies`` — and
    not a condition language that could express anything and be audited for
    nothing.
    """
    policy = policy_for(session, project=project)
    blockers: list[str] = []
    if sale.status != SALE_ACTIVE:
        blockers.append("The sale contract is not active")
    unit = session.get(Unit, sale.unit_id)
    if unit is None or unit.commercial_status != COMMERCIAL_STATUS_CONTRACTED:
        blockers.append("The unit is not contracted")
    required = {
        CLEARANCE_LEGAL: policy.handover_requires_legal_clearance,
        CLEARANCE_COLLECTION: policy.handover_requires_collection_clearance,
        CLEARANCE_DELIVERY: policy.handover_requires_delivery_clearance,
    }
    for clearance_type, needed in required.items():
        if not needed:
            continue
        current = _current_clearance(
            session, handover_id=handover.id, clearance_type=clearance_type
        )
        if current is None or current.status != CLEARANCE_CLEARED:
            blockers.append(f"{clearance_type.capitalize()} clearance not given")
    if policy.handover_requires_title_transfer and (
        EVENT_TRANSFERRED not in _recorded_event_types(session, sale_id=sale.id)
    ):
        blockers.append("Title has not transferred")
    if _open_cancellation(session, sale_id=sale.id) is not None:
        blockers.append("A cancellation case is open on this contract")
    if handover.handover_date is None:
        blockers.append("Handover date not recorded")
    if not handover.acceptance_document_reference:
        blockers.append("Acceptance document reference not recorded")
    return blockers


def complete_handover(
    session: Session,
    *,
    project: Project,
    handover_id: uuid.UUID,
    actor: ActorContext,
    handover_date: date | None = None,
    acceptance_document_reference: str | None = None,
    keys_reference: str | None = None,
) -> HandoverRecord:
    """Hand the unit over, once every configured gate has been passed.

    The unit's delivery status follows, through inventory's contract. There is
    no route that sets ``delivery_status`` directly: a unit that says it was
    handed over always has a handover record, three departments' answers and a
    dated acceptance behind it.
    """
    permissions.require_handover_writer(actor)
    project_locked = lock_project(session, project.id)
    handover = _lock_handover(session, project_id=project_locked.id, handover_id=handover_id)
    sale = get_sale(session, project=project, sale_id=handover.sale_contract_id, actor=actor)
    unit = inventory_service.lock_unit(session, project_id=project_locked.id, unit_id=sale.unit_id)
    sale = _lock_sale(session, project_id=project_locked.id, sale_id=sale.id)

    if handover.status == HANDOVER_HANDED_OVER:
        raise ConflictError("This unit has already been handed over.")
    before = _snapshot(handover, _HANDOVER_FIELDS)
    if handover_date is not None:
        handover.handover_date = handover_date
    if acceptance_document_reference is not None:
        handover.acceptance_document_reference = acceptance_document_reference.strip() or None
    if keys_reference is not None:
        handover.keys_reference = keys_reference.strip() or None

    blockers = handover_blockers(session, project=project_locked, sale=sale, handover=handover)
    if blockers:
        raise ConflictError("This handover cannot be completed: " + "; ".join(blockers) + ".")

    handover.status = HANDOVER_HANDED_OVER
    handover.completed_by_user_id = actor.user_id
    inventory_service.apply_delivery_status(
        session,
        project=project_locked,
        unit=unit,
        to_status="handed_over",
        effective_date=_effective(handover.handover_date),
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=f"Handover completed on contract {sale.sale_number}.",
    )
    _flush(session)
    record_event(
        session,
        action="handover.completed",
        entity_type=ENTITY_HANDOVER,
        entity_id=handover.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(handover, _HANDOVER_FIELDS),
    )
    session.commit()
    session.refresh(handover)
    return handover


# --------------------------------------------------------------------------- #
# The sales register
# --------------------------------------------------------------------------- #

#: What the legal timeline is waiting for next, given what it has already got.
#: Read off the same prerequisite map the recording route enforces, so the
#: screen and the rule cannot drift apart.
_NEXT_LEGAL_STEP: tuple[str, ...] = (
    "spa_drafted",
    "spa_issued",
    "buyer_signed",
    "seller_signed",
    "land_registry_lodged",
    "registered",
    "title_transferred",
)


def next_legal_step(recorded: set[str]) -> str | None:
    """The next milestone this contract's timeline is waiting for."""
    if EVENT_WITHDRAWN in recorded:
        return None
    for step in _NEXT_LEGAL_STEP:
        if step not in recorded:
            return step
    return None


def sales_register(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    phase_id: uuid.UUID | None = None,
    building_id: uuid.UUID | None = None,
    commercial_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    """One line per unit: where it stands commercially, legally and on delivery.

    The four status dimensions are reported side by side and never collapsed
    into "sold". A unit can be contracted, lodged with the registry, overdue on
    collections and still under construction; those are four teams' answers, and
    a register that merged them would be wrong for at least three of them.

    Aggregates are computed over the whole authorised, filtered set rather than
    the page being displayed. A total that changes when you turn the page is not
    a total.
    """
    permissions.require_sales_reader(actor)
    units = select(Unit).where(Unit.project_id == project.id, Unit.is_active.is_(True))
    allowed = permissions.visible_unit_ids(session, project_id=project.id, actor=actor)
    if allowed is not None:
        units = units.where(Unit.id.in_(allowed))
    if commercial_status is not None:
        units = units.where(Unit.commercial_status == commercial_status)
    if building_id is not None or phase_id is not None:
        units = units.where(Unit.floor_id.in_(_floor_ids(phase_id, building_id)))

    every = list(session.scalars(units.order_by(Unit.unit_reference)))
    total = len(every)
    page = every[offset : offset + limit]
    unit_ids = [unit.id for unit in every]

    # The reservation a unit's line should show: the one holding it if there is
    # one, and otherwise the newest still being prepared. A reservation awaiting
    # a deposit or an approval holds nothing, but somebody has to be able to
    # find it — and the register is where they are looking.
    reservations: dict[uuid.UUID, Reservation] = {}
    for reservation in session.scalars(
        select(Reservation)
        .where(
            Reservation.unit_id.in_(unit_ids),
            Reservation.status.in_(RESERVATION_COMMITTED | RESERVATION_PREPARING),
        )
        .order_by(Reservation.created_at)
    ):
        held = reservations.get(reservation.unit_id)
        if held is None or reservation.status in RESERVATION_COMMITTED:
            reservations[reservation.unit_id] = reservation
    committed_units = {
        unit_id
        for unit_id, reservation in reservations.items()
        if reservation.status in RESERVATION_COMMITTED
    }
    sales = {
        sale.unit_id: sale
        for sale in session.scalars(
            select(SaleContract).where(
                SaleContract.unit_id.in_(unit_ids), SaleContract.status.in_(SALE_COMMITTED)
            )
        )
    }
    clients = {
        client.id: client
        for client in session.scalars(select(Client).where(Client.project_id == project.id))
    }
    handovers = {
        handover.sale_contract_id: handover
        for handover in session.scalars(
            select(HandoverRecord).where(HandoverRecord.project_id == project.id)
        )
    }
    today = inventory_fields.business_today()

    rows: list[dict[str, Any]] = []
    for unit in page:
        reservation = reservations.get(unit.id)
        sale = sales.get(unit.id)
        client_id = sale.client_id if sale else (reservation.client_id if reservation else None)
        client = clients.get(client_id) if client_id else None
        handover = handovers.get(sale.id) if sale else None
        recorded = _recorded_event_types(session, sale_id=sale.id) if sale else set()
        rows.append(
            {
                "unit_id": unit.id,
                "unit_reference": unit.unit_reference,
                "unit_number": unit.unit_number,
                "commercial_status": unit.commercial_status,
                "legal_status": unit.legal_status,
                "delivery_status": unit.delivery_status,
                "client_id": client.id if client else None,
                "client_display_name": client.display_name if client else None,
                "reservation_id": reservation.id if reservation else None,
                "reservation_number": reservation.reservation_number if reservation else None,
                "reservation_status": reservation.status if reservation else None,
                "reservation_expires_on": reservation.expires_on if reservation else None,
                "closure_required": (
                    requires_closure(reservation, today=today) if reservation else False
                ),
                "sale_id": sale.id if sale else None,
                "sale_number": sale.sale_number if sale else None,
                "spa_number": sale.spa_number if sale else None,
                "sale_status": sale.status if sale else None,
                "contract_date": sale.contract_date if sale else None,
                "currency_id": sale.currency_id if sale else None,
                "net_contract_price_ex_tax": (sale.net_contract_price_ex_tax if sale else None),
                "cash_discount_amount": sale.cash_discount_amount if sale else None,
                "total_contract_price": sale.total_contract_price if sale else None,
                "sales_branch_code": sale.sales_branch_code if sale else None,
                "advisor_user_id": (
                    sale.advisor_user_id
                    if sale
                    else (reservation.advisor_user_id if reservation else None)
                ),
                "next_legal_step": next_legal_step(recorded) if sale else None,
                "handover_status": handover.status if handover else None,
            }
        )

    contracted = [sales[unit.id] for unit in every if unit.id in sales]
    currencies = {sale.currency_id for sale in contracted}
    mixed = len(currencies) > 1
    totals = {
        "units": total,
        "available": sum(1 for unit in every if unit.commercial_status == "available"),
        "reserved": sum(1 for unit in every if unit.commercial_status == "reserved"),
        "contract_pending": sum(
            1 for unit in every if unit.commercial_status == "contract_pending"
        ),
        "contracted": sum(1 for unit in every if unit.commercial_status == "contracted"),
        "returned": sum(1 for unit in every if unit.commercial_status == "returned"),
        "active_reservations": sum(1 for unit in every if unit.id in committed_units),
        "active_contracts": sum(1 for sale in contracted if sale.status == SALE_ACTIVE),
        "open_cancellations": session.scalar(
            select(func.count())
            .select_from(SaleCancellation)
            .where(
                SaleCancellation.project_id == project.id,
                SaleCancellation.status.in_(CANCELLATION_OPEN),
                SaleCancellation.sale_contract_id.in_([sale.id for sale in contracted] or [None]),
            )
        )
        or 0,
        # A sum of two currencies is not a number. Where a project's contracts
        # are denominated in more than one, the value is withheld rather than
        # added up: PR-MVP-05 has no governed FX model and will not invent one.
        "contracted_value": (
            None if mixed else money(sum((sale.total_contract_price for sale in contracted), ZERO))
        ),
        "currency_id": next(iter(currencies)) if len(currencies) == 1 else None,
        "mixed_currency": mixed,
    }
    return rows, totals, total


def _floor_ids(
    phase_id: uuid.UUID | None, building_id: uuid.UUID | None
) -> Select[tuple[uuid.UUID]]:
    """Floors under one phase or building, as a subquery for the unit filter."""
    statement = select(Floor.id).join(Building, Building.id == Floor.building_id)
    if building_id is not None:
        statement = statement.where(Building.id == building_id)
    if phase_id is not None:
        statement = statement.where(Building.phase_id == phase_id)
    return statement
