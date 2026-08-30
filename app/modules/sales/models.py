"""Sales and legal: contract truth.

PR-MVP-04 established what a unit is *offered* at. This module establishes what
was actually agreed, with whom, and how far the paperwork has got. It is the
first place in the system where a real, persistent commercial commitment exists.

Five rules shape every table here.

**A commitment is exclusive.** One unit cannot carry two live reservations, and
cannot carry two live sale contracts. Partial unique indexes say so in the
database; the unit row lock is how two concurrent writers are made to take turns
in front of them.

**A contract freezes what it was signed on.** A sale copies the price version,
the quote, the buyer parties and the tax observation it was agreed under. The
client's address may be corrected next year and a tax rate may change next
quarter; a signed contract must keep saying what it said.

**Money and law are separate timelines.** A unit can be contracted, lodged with
the registry, overdue on collections and still under construction — four facts
owned by four teams. They are four columns and they are never collapsed into
"sold".

**Nothing financial or legal is deleted.** A reservation expires, a contract is
cancelled, a legal event is reversed by another event. The record of the wrong
thing having been believed is itself a fact somebody will need.

**A gate is an attestation until its domain exists.** A confirmed deposit and a
confirmed first payment are recorded commercial evidence, named so they cannot
be mistaken for cash: PR-MVP-07 owns receipts, and this module must never let a
gate be counted as collected money.

Constraint names are kept short deliberately: PostgreSQL truncates identifiers
at 63 characters, and a truncated name stops matching the metadata, which makes
``alembic check`` report drift for ever afterwards.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MONEY, RATE, Base, in_list

# --------------------------------------------------------------------------- #
# Closed sets
# --------------------------------------------------------------------------- #

#: Where a client stands on identity checks. A code, not a workflow: the
#: evidence itself lives with the parties.
KYC_STATUSES = ("not_started", "in_progress", "cleared", "rejected")
KYC_NOT_STARTED = "not_started"

#: What a person is to a purchase. Two roles, because a purchase has buyers and
#: nothing else; a representative is an attribute of a buyer, not a third kind
#: of party, and modelling them as one produces a relationship graph nobody
#: asked for.
PARTY_ROLES = ("purchaser", "joint_purchaser")
PARTY_PURCHASER = "purchaser"

#: The commercial life of a reservation.
#:
#: ``draft`` and ``deposit_pending`` prepare terms and hold nothing — the unit is
#: still on the market. ``active`` and ``extended`` are the commitment, and are
#: the two states the unit lock and the partial unique index care about.
#: ``converted`` means a sale took the commitment over. The other two are the
#: ways a reservation ends without one.
RESERVATION_STATUSES = (
    "draft",
    "deposit_pending",
    "active",
    "extended",
    "converted",
    "expired",
    "cancelled",
)
RESERVATION_DRAFT = "draft"
RESERVATION_DEPOSIT_PENDING = "deposit_pending"
RESERVATION_ACTIVE = "active"
RESERVATION_EXTENDED = "extended"
RESERVATION_CONVERTED = "converted"
RESERVATION_EXPIRED = "expired"
RESERVATION_CANCELLED = "cancelled"

#: The two reservation states that hold a unit off the market. The partial
#: unique index below is built on exactly this set.
RESERVATION_COMMITTED = frozenset({RESERVATION_ACTIVE, RESERVATION_EXTENDED})

#: States a reservation may still be edited in.
RESERVATION_PREPARING = frozenset({RESERVATION_DRAFT, RESERVATION_DEPOSIT_PENDING})

#: A gate is satisfied, waived by an authorised approver, or not applicable.
#: ``pending`` is the only state that blocks.
#:
#: Deliberately *not* called a payment. A confirmed deposit is a named person
#: attesting that evidence exists; PR-MVP-07 introduces the receipt that says
#: money arrived. Naming these the same thing is how a gate ends up in a
#: cash-collected report.
GATE_STATUSES = ("not_required", "pending", "confirmed", "waived")
GATE_NOT_REQUIRED = "not_required"
GATE_PENDING = "pending"
GATE_CONFIRMED = "confirmed"
GATE_WAIVED = "waived"

#: A gate that lets a commitment proceed.
GATE_SATISFIED = frozenset({GATE_NOT_REQUIRED, GATE_CONFIRMED, GATE_WAIVED})

#: Whether a quote exception needed sanctioning, and what happened.
EXCEPTION_STATUSES = ("not_required", "pending", "submitted", "approved", "rejected")
EXCEPTION_NOT_REQUIRED = "not_required"
EXCEPTION_PENDING = "pending"
EXCEPTION_SUBMITTED = "submitted"
EXCEPTION_APPROVED = "approved"
EXCEPTION_REJECTED = "rejected"

#: The commercial inputs a person may put into a quote. A closed list of real
#: business levers — there is no formula column and no expression column, and
#: adding a lever means a migration and a reviewed decision.
ADJUSTMENT_TYPES = (
    "percentage_discount",
    "fixed_discount",
    "seller_credit",
    "package_cost",
    "upgrade_allowance",
    "commission_support",
    "financing_subsidy",
    "extended_terms_npv_cost",
    "paid_upgrade",
    "payment_plan_adjustment",
)

#: What an adjustment *does* to the deal. This is derived from the type, never
#: chosen: the difference between a concession and a seller cost is the single
#: distinction this module exists to keep, and letting a user pick it would be
#: letting them decide whether the contract price falls.
ADJUSTMENT_TREATMENTS = ("price_concession", "seller_cost", "price_addition")
TREATMENT_CONCESSION = "price_concession"
TREATMENT_SELLER_COST = "seller_cost"
TREATMENT_ADDITION = "price_addition"

#: The one true mapping. Everything else about an adjustment is input; this is
#: policy, and it is stated once.
ADJUSTMENT_TREATMENT_OF: dict[str, str] = {
    "percentage_discount": TREATMENT_CONCESSION,
    "fixed_discount": TREATMENT_CONCESSION,
    "seller_credit": TREATMENT_CONCESSION,
    "package_cost": TREATMENT_SELLER_COST,
    "upgrade_allowance": TREATMENT_SELLER_COST,
    "commission_support": TREATMENT_SELLER_COST,
    "financing_subsidy": TREATMENT_SELLER_COST,
    "extended_terms_npv_cost": TREATMENT_SELLER_COST,
    "paid_upgrade": TREATMENT_ADDITION,
    "payment_plan_adjustment": TREATMENT_ADDITION,
}

#: The two adjustment types stated as a rate rather than an amount.
ADJUSTMENT_RATE_TYPES = frozenset({"percentage_discount", "payment_plan_adjustment"})

#: The life of a sale contract.
#:
#: ``draft`` is preparation and holds nothing — the reservation still owns the
#: commitment. From ``signature_pending`` onward the contract owns it, which is
#: why those three states are the ones the partial unique index counts.
SALE_STATUSES = ("draft", "signature_pending", "active", "termination_pending", "cancelled")
SALE_DRAFT = "draft"
SALE_SIGNATURE_PENDING = "signature_pending"
SALE_ACTIVE = "active"
SALE_TERMINATION_PENDING = "termination_pending"
SALE_CANCELLED = "cancelled"

#: The sale states that hold a unit. One per unit, enforced by partial index.
SALE_COMMITTED = frozenset({SALE_SIGNATURE_PENDING, SALE_ACTIVE, SALE_TERMINATION_PENDING})

#: The legal milestones this system records. Canonical codes: a jurisdiction's
#: own wording for "lodged with the registry" is display configuration, and
#: hard-coding one country's procedure into the vocabulary would make the second
#: country a rewrite.
LEGAL_EVENT_TYPES = (
    "spa_drafted",
    "spa_approved",
    "spa_issued",
    "buyer_signed",
    "seller_signed",
    "stamped",
    "stamp_duty_recorded",
    "land_registry_lodged",
    "land_registry_accepted",
    "registered",
    "title_transfer_pending",
    "title_transferred",
    "withdrawal_started",
    "withdrawn",
)
EVENT_SPA_DRAFTED = "spa_drafted"
EVENT_SPA_APPROVED = "spa_approved"
EVENT_SPA_ISSUED = "spa_issued"
EVENT_BUYER_SIGNED = "buyer_signed"
EVENT_SELLER_SIGNED = "seller_signed"
EVENT_STAMPED = "stamped"
EVENT_STAMP_DUTY = "stamp_duty_recorded"
EVENT_LODGED = "land_registry_lodged"
EVENT_ACCEPTED = "land_registry_accepted"
EVENT_REGISTERED = "registered"
EVENT_TRANSFER_PENDING = "title_transfer_pending"
EVENT_TRANSFERRED = "title_transferred"
EVENT_WITHDRAWAL_STARTED = "withdrawal_started"
EVENT_WITHDRAWN = "withdrawn"

#: Who ended the contract. A closed list, because "why" is free text but "who"
#: decides which side's remedies apply.
CANCELLATION_INITIATORS = ("buyer", "seller", "mutual", "developer_default_process")

#: How far a cancellation has got. Operational, not a legal treatise: notice,
#: the cure period, the money decision, the registry unwind, the unit coming
#: back, and done.
CANCELLATION_STATUSES = (
    "notice",
    "cure",
    "termination_pending_approval",
    "withdrawal_pending",
    "ready_for_unit_return",
    "completed",
    "withdrawn",
)
CANCELLATION_NOTICE = "notice"
CANCELLATION_CURE = "cure"
CANCELLATION_TERMINATION_PENDING = "termination_pending_approval"
CANCELLATION_WITHDRAWAL_PENDING = "withdrawal_pending"
CANCELLATION_READY_FOR_RETURN = "ready_for_unit_return"
CANCELLATION_COMPLETED = "completed"
CANCELLATION_WITHDRAWN = "withdrawn"

#: Cancellation states that still hold the unit. A cancellation in progress is
#: not a unit back on the market.
CANCELLATION_OPEN = frozenset(
    {
        CANCELLATION_NOTICE,
        CANCELLATION_CURE,
        CANCELLATION_TERMINATION_PENDING,
        CANCELLATION_WITHDRAWAL_PENDING,
        CANCELLATION_READY_FOR_RETURN,
    }
)

#: Whether the registry has to be unwound before the unit can come back.
WITHDRAWAL_STATUSES = ("not_required", "pending", "completed")
WITHDRAWAL_NOT_REQUIRED = "not_required"
WITHDRAWAL_PENDING = "pending"
WITHDRAWAL_COMPLETED = "completed"

#: The operational life of a handover.
HANDOVER_STATUSES = (
    "preparation",
    "inspection_pending",
    "snagging",
    "ready",
    "handed_over",
    "cancelled",
)
HANDOVER_PREPARATION = "preparation"
HANDOVER_READY = "ready"
HANDOVER_HANDED_OVER = "handed_over"
HANDOVER_CANCELLED = "cancelled"

#: The three independent sign-offs a handover needs, each owned by a different
#: team. Three fixed types, not a configurable checklist: the point of the gate
#: is that one department cannot clear another's concern.
CLEARANCE_TYPES = ("legal", "collection", "delivery")
CLEARANCE_LEGAL = "legal"
CLEARANCE_COLLECTION = "collection"
CLEARANCE_DELIVERY = "delivery"

CLEARANCE_STATUSES = ("pending", "cleared", "revoked")
CLEARANCE_PENDING = "pending"
CLEARANCE_CLEARED = "cleared"
CLEARANCE_REVOKED = "revoked"

#: Reference-value categories this module validates newly assigned codes against.
CATEGORY_SALES_CHANNEL = "sales_channel"
CATEGORY_SALES_BRANCH = "sales_branch"
CATEGORY_CLIENT_LANGUAGE = "client_language"
CATEGORY_NATIONALITY = "nationality"
CATEGORY_RESIDENCY = "residency"

#: Audit entity labels.
ENTITY_SALES_POLICY = "sales_project_policy"
ENTITY_CLIENT = "client"
ENTITY_CLIENT_PARTY = "client_party"
ENTITY_RESERVATION = "reservation"
ENTITY_ADJUSTMENT = "reservation_adjustment"
ENTITY_SALE = "sale_contract"
ENTITY_LEGAL_EVENT = "sale_legal_event"
ENTITY_CANCELLATION = "sale_cancellation"
ENTITY_HANDOVER = "handover_record"
ENTITY_CLEARANCE = "handover_clearance"


# --------------------------------------------------------------------------- #
# Project policy
# --------------------------------------------------------------------------- #


class SalesProjectPolicy(Base):
    """The gates one project puts in front of title transfer and handover.

    Five booleans and nothing else. A development that hands over before the
    money is in and one that does not are both real, so the choice is
    configuration — but it is *this* choice, named, with a default that fails
    closed, not a condition language that can express anything and be audited
    for nothing.
    """

    __tablename__ = "sales_project_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )

    handover_requires_collection_clearance: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    handover_requires_legal_clearance: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    handover_requires_delivery_clearance: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    handover_requires_title_transfer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    title_transfer_requires_collection_clearance: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    reservation_requires_deposit_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (UniqueConstraint("project_id", name="uq_sales_policy_project"),)


# --------------------------------------------------------------------------- #
# Client and buyer parties
# --------------------------------------------------------------------------- #


class Client(Base):
    """A buyer, scoped to the project they are buying in.

    Project-scoped on purpose. A portfolio-wide customer master is a real thing
    a real company eventually wants, and it brings deduplication, merge, consent
    scope and cross-project visibility with it — none of which this MVP has
    decided. Scoping to the project keeps the security answer simple ("can you
    see this project?") and leaves the harder question to a PR that is actually
    about it.

    This is the first substantial personal data in the system. The sensitive
    fields live on the parties below rather than here, so that the commercial
    summary a project manager legitimately needs can be served without the
    identity documents they do not.
    """

    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    #: Human-readable reference. Never identity: see ENGINEERING_RULES §6.
    client_number: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)

    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preferred_language_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    kyc_status: Mapped[str] = mapped_column(String(16), nullable=False, default=KYC_NOT_STARTED)
    #: When the buyer agreed to their data being held, and the reference to the
    #: record of it. Consent is a fact with a date, not a checkbox.
    privacy_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    privacy_consent_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)

    #: The advisor this client belongs to. Drives row-level visibility: an
    #: advisor sees their own clients, not the desk's.
    owner_advisor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("project_id", "client_number", name="uq_clients_number"),
        # Every child carries project_id and points at this pair, so a client of
        # one project can never end up on another project's reservation however
        # the identifiers are shuffled.
        UniqueConstraint("id", "project_id", name="client_project"),
        CheckConstraint("length(client_number) > 0", name="number_not_blank"),
        CheckConstraint("length(display_name) > 0", name="name_not_blank"),
        CheckConstraint(in_list("kyc_status", KYC_STATUSES), name="kyc_ok"),
        Index("ix_clients_project_id_is_active", "project_id", "is_active"),
        Index("ix_clients_owner_advisor_user_id", "owner_advisor_user_id"),
    )


class ClientParty(Base):
    """One named buyer on a purchase, with the share they take.

    Joint purchase is the ordinary case, not an edge case, so shares are a
    column rather than an assumption. They must total exactly one before a
    reservation can be activated — see the service — because two buyers at forty
    per cent each is a contract that sells sixty per cent of a flat to nobody.

    This row holds the identity documents. Access is decided per role before
    serialisation, never in the browser.
    """

    __tablename__ = "client_parties"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    party_role: Mapped[str] = mapped_column(String(16), nullable=False, default=PARTY_PURCHASER)
    #: The name exactly as it appears on the identity document, which is the
    #: name that has to appear on the contract.
    name_as_identification: Mapped[str] = mapped_column(String(200), nullable=False)
    nationality_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    residency_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_document_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    share_fraction: Mapped[Decimal] = mapped_column(RATE, nullable=False)

    #: A representative acts for this buyer under a power of attorney. An
    #: attribute of the buyer, not a party of its own.
    representative_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    poa_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)

    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["client_id", "project_id"],
            ["clients.id", "clients.project_id"],
            name="client",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="party_project"),
        CheckConstraint(in_list("party_role", PARTY_ROLES), name="role_ok"),
        CheckConstraint("length(name_as_identification) > 0", name="name_not_blank"),
        CheckConstraint("share_fraction > 0 AND share_fraction <= 1", name="share_range"),
        Index("ix_client_parties_client_id", "client_id"),
    )


# --------------------------------------------------------------------------- #
# Reservation
# --------------------------------------------------------------------------- #


class Reservation(Base):
    """The first persistent commercial commitment: this buyer, this unit, this price.

    A reservation freezes a quote. The typed columns below are the figures a
    person will be asked about — what the buyer was quoted, what they were given,
    what the seller absorbed — and ``quote_snapshot_json`` keeps the complete
    calculation beside them so the waterfall can still be reproduced line by
    line in two years.

    The snapshot is a record, not master data. Nothing recalculates it after
    activation: that is the whole point of freezing it.
    """

    __tablename__ = "reservations"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    reservation_number: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: The exact price version this deal was quoted from. Immutable in pricing,
    #: so the reference alone is enough to reproduce the list price.
    unit_price_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=RESERVATION_DRAFT)
    reservation_date: Mapped[date] = mapped_column(Date, nullable=False)
    expires_on: Mapped[date] = mapped_column(Date, nullable=False)
    #: How long the quoted price itself is guaranteed. Distinct from expiry: a
    #: reservation may be extended, but not past the price it was sold on.
    price_locked_until: Mapped[date] = mapped_column(Date, nullable=False)

    sales_channel_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sales_branch_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    advisor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    # The deposit gate. Evidence that a deposit exists, recorded by a named
    # person — never a receipt, never collected cash, never revenue.
    deposit_required_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    deposit_currency_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=True
    )
    deposit_gate_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=GATE_NOT_REQUIRED
    )
    deposit_confirmation_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    deposit_confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    deposit_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deposit_waiver_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # The frozen quote. Typed columns for the figures that get asked about;
    # the JSON below keeps everything else.
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    reference_price_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    paid_upgrade_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    payment_plan_adjustment_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    gross_quoted_price_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    cash_discount_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    seller_credit_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    net_contract_price_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    #: What the seller absorbed. Never subtracted from the contract price.
    seller_cost_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    effective_net_revenue_preview: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    buyer_fee_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_buyer_payable: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    # The exception. Explicit state on the row rather than a generic approval
    # engine: one thing needs sanctioning here, and it needs it in one shape.
    exception_approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    exception_approval_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EXCEPTION_NOT_REQUIRED
    )
    exception_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    exception_required_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exception_submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    exception_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exception_approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    exception_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exception_decision_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    #: The complete quote calculation, exactly as pricing returned it.
    quote_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["client_id", "project_id"],
            ["clients.id", "clients.project_id"],
            name="client",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["unit_price_version_id", "project_id"],
            ["unit_price_versions.id", "unit_price_versions.project_id"],
            name="price_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "reservation_number", name="uq_reservations_number"),
        UniqueConstraint("id", "project_id", name="reservation_project"),
        CheckConstraint(in_list("status", RESERVATION_STATUSES), name="status_ok"),
        CheckConstraint(in_list("deposit_gate_status", GATE_STATUSES), name="deposit_gate_ok"),
        CheckConstraint(
            in_list("exception_approval_status", EXCEPTION_STATUSES), name="exception_ok"
        ),
        CheckConstraint("expires_on >= reservation_date", name="expiry_after_start"),
        CheckConstraint("price_locked_until >= reservation_date", name="lock_after_start"),
        CheckConstraint("reference_price_ex_tax >= 0", name="reference_nonneg"),
        CheckConstraint("gross_quoted_price_ex_tax >= 0", name="gross_nonneg"),
        CheckConstraint("net_contract_price_ex_tax >= 0", name="net_nonneg"),
        CheckConstraint("seller_cost_total >= 0", name="seller_cost_nonneg"),
        CheckConstraint("tax_total >= 0", name="tax_nonneg"),
        CheckConstraint("total_buyer_payable >= 0", name="payable_nonneg"),
        CheckConstraint(
            "deposit_required_amount IS NULL OR deposit_required_amount >= 0",
            name="deposit_nonneg",
        ),
        # A waiver has to say why. A gate somebody skipped without a reason is
        # a gate that was not there.
        CheckConstraint(
            "deposit_gate_status <> 'waived' OR deposit_waiver_reason IS NOT NULL",
            name="waiver_has_reason",
        ),
        # One live reservation per unit. The unit row lock is the mechanism;
        # this is the backstop that holds when something writes around it.
        Index(
            "uq_reservations_committed_unit",
            "unit_id",
            unique=True,
            postgresql_where=text("status IN ('active', 'extended')"),
        ),
        Index("ix_reservations_project_id_status", "project_id", "status"),
        Index("ix_reservations_unit_id", "unit_id"),
        Index("ix_reservations_client_id", "client_id"),
    )


class ReservationAdjustment(Base):
    """One commercial input that shaped the quote.

    Rows rather than columns, because "the discount" is not one number: a deal
    can carry a percentage off, a fixed sum off, a furniture package the seller
    absorbs and a paid upgrade the buyer adds, and each has a different effect
    on a different total. Flattening them loses which lever was pulled.

    ``treatment`` is derived from ``adjustment_type`` and stored beside it so the
    row can be read on its own. A CHECK ties the pair together, so the two can
    never disagree.
    """

    __tablename__ = "reservation_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    adjustment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    treatment: Mapped[str] = mapped_column(String(16), nullable=False)
    #: A rate for the two types stated as one; an amount for the rest. Never
    #: both, never neither — see the CHECK below.
    rate_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["reservation_id", "project_id"],
            ["reservations.id", "reservations.project_id"],
            name="reservation",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "reservation_id", "adjustment_type", name="uq_reservation_adjustments_type"
        ),
        CheckConstraint(in_list("adjustment_type", ADJUSTMENT_TYPES), name="type_ok"),
        CheckConstraint(in_list("treatment", ADJUSTMENT_TREATMENTS), name="treatment_ok"),
        # The type decides the treatment. Stated here so a direct write cannot
        # turn a furniture package into a discount by editing one column.
        CheckConstraint(
            "(adjustment_type IN ('percentage_discount', 'fixed_discount', 'seller_credit') "
            "  AND treatment = 'price_concession') "
            "OR (adjustment_type IN ('package_cost', 'upgrade_allowance', 'commission_support', "
            "  'financing_subsidy', 'extended_terms_npv_cost') AND treatment = 'seller_cost') "
            "OR (adjustment_type IN ('paid_upgrade', 'payment_plan_adjustment') "
            "  AND treatment = 'price_addition')",
            name="treatment_matches_type",
        ),
        # A rate type carries a rate; everything else carries an amount.
        CheckConstraint(
            "(adjustment_type IN ('percentage_discount', 'payment_plan_adjustment') "
            "  AND rate_fraction IS NOT NULL AND amount IS NULL) "
            "OR (adjustment_type NOT IN ('percentage_discount', 'payment_plan_adjustment') "
            "  AND amount IS NOT NULL AND rate_fraction IS NULL)",
            name="shape_ok",
        ),
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_nonneg"),
        Index("ix_reservation_adjustments_reservation_id", "reservation_id"),
    )


class ReservationStatusEvent(Base):
    """Append-only history of one reservation's commercial life.

    Never edited, never deleted. A reservation that was active for a fortnight
    and then expired is two facts, and the second does not erase the first.
    """

    __tablename__ = "reservation_status_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    from_status: Mapped[str] = mapped_column(String(16), nullable=False)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["reservation_id", "project_id"],
            ["reservations.id", "reservations.project_id"],
            name="reservation",
            ondelete="RESTRICT",
        ),
        CheckConstraint(in_list("from_status", RESERVATION_STATUSES), name="from_ok"),
        CheckConstraint(in_list("to_status", RESERVATION_STATUSES), name="to_ok"),
        Index(
            "ix_reservation_status_events_reservation_id_effective_date",
            "reservation_id",
            "effective_date",
        ),
    )


# --------------------------------------------------------------------------- #
# Sale contract
# --------------------------------------------------------------------------- #


class SaleContract(Base):
    """The signed agreement: this buyer, this unit, this price, these terms.

    Everything commercial on this row is a copy taken at submission, not a
    pointer to something that keeps moving. The client's name may be corrected,
    the tax rule may be amended, a new price version may be activated on the
    unit next quarter — and the contract still says what the parties signed.

    ``sale_number`` is this system's reference; ``spa_number`` is the legal
    document's. Neither is identity.
    """

    __tablename__ = "sale_contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    sale_number: Mapped[str] = mapped_column(String(32), nullable=False)
    spa_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reservation_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    unit_price_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    contract_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=SALE_DRAFT)

    # Frozen commercial terms.
    reference_price_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    gross_quoted_price_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    cash_discount_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    seller_credit_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    net_contract_price_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    seller_cost_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    effective_net_revenue_snapshot: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    buyer_fee_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    #: What the buyer contracts to pay in total. Never reduced by a seller cost.
    total_contract_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    reservation_quote_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    sales_channel_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sales_branch_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    advisor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    # The first-payment gate. Recorded evidence that a payment exists, not the
    # payment. PR-MVP-07 owns receipts; this must never reach a cash report.
    first_payment_required_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    first_payment_gate_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=GATE_NOT_REQUIRED
    )
    first_payment_evidence_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    first_payment_confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    first_payment_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_payment_waiver_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["client_id", "project_id"],
            ["clients.id", "clients.project_id"],
            name="client",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reservation_id", "project_id"],
            ["reservations.id", "reservations.project_id"],
            name="reservation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["unit_price_version_id", "project_id"],
            ["unit_price_versions.id", "unit_price_versions.project_id"],
            name="price_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "sale_number", name="uq_sale_contracts_number"),
        UniqueConstraint("id", "project_id", name="sale_project"),
        CheckConstraint(in_list("status", SALE_STATUSES), name="status_ok"),
        CheckConstraint(
            in_list("first_payment_gate_status", GATE_STATUSES), name="first_payment_gate_ok"
        ),
        CheckConstraint("net_contract_price_ex_tax >= 0", name="net_nonneg"),
        CheckConstraint("total_contract_price >= 0", name="total_nonneg"),
        CheckConstraint("seller_cost_total >= 0", name="seller_cost_nonneg"),
        CheckConstraint("tax_total >= 0", name="tax_nonneg"),
        CheckConstraint(
            "first_payment_required_amount IS NULL OR first_payment_required_amount >= 0",
            name="first_payment_nonneg",
        ),
        CheckConstraint(
            "first_payment_gate_status <> 'waived' OR first_payment_waiver_reason IS NOT NULL",
            name="waiver_has_reason",
        ),
        # One SPA number per project, where one has been issued. Partial,
        # because a draft has not got one yet and NULLs are not duplicates.
        Index(
            "uq_sale_contracts_spa_number",
            "project_id",
            "spa_number",
            unique=True,
            postgresql_where=text("spa_number IS NOT NULL"),
        ),
        # One live contract per unit. Draft is excluded on purpose: the
        # reservation still owns the commitment until the contract is submitted.
        Index(
            "uq_sale_contracts_committed_unit",
            "unit_id",
            unique=True,
            postgresql_where=text(
                "status IN ('signature_pending', 'active', 'termination_pending')"
            ),
        ),
        Index("ix_sale_contracts_project_id_status", "project_id", "status"),
        Index("ix_sale_contracts_unit_id", "unit_id"),
        Index("ix_sale_contracts_client_id", "client_id"),
    )


class SaleContractParty(Base):
    """A buyer's details as they stood when the contract was submitted.

    A copy, not a reference. Client master data is corrected all the time — a
    misspelled name, a renewed passport, a new address — and none of that may
    reach back and change who a signed contract says bought the flat, or in what
    shares.
    """

    __tablename__ = "sale_contract_parties"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: Where this snapshot came from. Kept for lineage; never followed for truth.
    client_party_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    party_role: Mapped[str] = mapped_column(String(16), nullable=False)
    name_as_identification: Mapped[str] = mapped_column(String(200), nullable=False)
    nationality_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    residency_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_document_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    share_fraction: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    representative_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    poa_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        CheckConstraint(in_list("party_role", PARTY_ROLES), name="role_ok"),
        CheckConstraint("share_fraction > 0 AND share_fraction <= 1", name="share_range"),
        Index("ix_sale_contract_parties_sale_contract_id", "sale_contract_id"),
    )


class SaleContractTaxLine(Base):
    """The tax observation the contract was priced under, frozen.

    A tax rule is governed configuration that changes. A contract signed at 16%
    keeps saying 16% when the rate moves to 18% next year, so the calculation is
    copied here rather than re-derived from a rule that has moved on.
    """

    __tablename__ = "sale_contract_tax_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: Lineage to the rule, where it still exists. Nullable because a historical
    #: contract must survive its rule being retired.
    tax_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tax_rules.id", ondelete="RESTRICT"), nullable=True
    )
    tax_code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    rate_fraction: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    calculation_basis: Mapped[str] = mapped_column(String(64), nullable=False)
    taxable_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    valid_on: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        CheckConstraint("taxable_amount >= 0", name="taxable_nonneg"),
        CheckConstraint("tax_amount >= 0", name="tax_nonneg"),
        Index("ix_sale_contract_tax_lines_sale_contract_id", "sale_contract_id"),
    )


# --------------------------------------------------------------------------- #
# Legal timeline
# --------------------------------------------------------------------------- #


class SaleLegalEvent(Base):
    """One dated, attributed, evidenced step in a contract's legal life.

    Append-only. There is no PATCH and no DELETE: a mis-entered registration is
    corrected by recording a reversal that points at it, because the fact that
    the wrong thing was believed between Tuesday and Friday is itself something
    somebody may have to account for.
    """

    __tablename__ = "sale_legal_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    authority_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    document_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: A legal fee recorded as a fact of the transaction. Not a cash payment:
    #: no ledger, no allocation, no bank. PR-MVP-10 sources actual movements.
    fee_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    currency_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    #: Set on a correcting event, pointing at the one it withdraws.
    reverses_event_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    entered_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reverses_event_id"],
            ["sale_legal_events.id"],
            name="reverses",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="legal_event_project"),
        CheckConstraint(in_list("event_type", LEGAL_EVENT_TYPES), name="type_ok"),
        CheckConstraint("fee_amount IS NULL OR fee_amount >= 0", name="fee_nonneg"),
        CheckConstraint("fee_amount IS NULL OR currency_id IS NOT NULL", name="fee_has_currency"),
        # A reversal says what it withdraws and why. One without a reason is an
        # edit wearing a different hat.
        CheckConstraint(
            "reverses_event_id IS NULL OR reversal_reason IS NOT NULL",
            name="reversal_has_reason",
        ),
        # One reversal per event: an event already withdrawn cannot be
        # withdrawn again, and two reversals would leave its state ambiguous.
        Index(
            "uq_sale_legal_events_reverses",
            "reverses_event_id",
            unique=True,
            postgresql_where=text("reverses_event_id IS NOT NULL"),
        ),
        Index(
            "ix_sale_legal_events_sale_contract_id_event_date",
            "sale_contract_id",
            "event_date",
        ),
    )


# --------------------------------------------------------------------------- #
# Cancellation
# --------------------------------------------------------------------------- #


class SaleCancellation(Base):
    """A controlled unwinding of a contract.

    One open case per contract. It records who ended it, on what grounds, what
    money is forfeited and what is *due* back — never what was paid back, which
    is a transaction PR-MVP-07 owns.

    A cancellation does not put the unit back on the market. It brings it back
    to ``returned``, with its pricing approval withdrawn, and somebody has to
    price it again before it can be sold to anyone else.
    """

    __tablename__ = "sale_cancellations"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    initiated_by_party: Mapped[str] = mapped_column(String(32), nullable=False)
    initiation_date: Mapped[date] = mapped_column(Date, nullable=False)
    notice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cure_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=CANCELLATION_NOTICE)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    forfeiture_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    #: What the buyer is owed. Due, not paid: this system has no record of money
    #: leaving, and calling it "refunded" would be inventing one.
    refund_due_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    financial_approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    financial_approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    financial_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    legal_withdrawal_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    legal_withdrawal_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WITHDRAWAL_NOT_REQUIRED
    )
    unit_return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remarketing_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="cancellation_project"),
        CheckConstraint(
            in_list("initiated_by_party", CANCELLATION_INITIATORS), name="initiator_ok"
        ),
        CheckConstraint(in_list("status", CANCELLATION_STATUSES), name="status_ok"),
        CheckConstraint(
            in_list("legal_withdrawal_status", WITHDRAWAL_STATUSES), name="withdrawal_ok"
        ),
        CheckConstraint(
            "forfeiture_amount IS NULL OR forfeiture_amount >= 0", name="forfeiture_nonneg"
        ),
        CheckConstraint(
            "refund_due_amount IS NULL OR refund_due_amount >= 0", name="refund_nonneg"
        ),
        CheckConstraint("length(reason) > 0", name="reason_not_blank"),
        CheckConstraint(
            "cure_deadline IS NULL OR notice_date IS NULL OR cure_deadline >= notice_date",
            name="cure_after_notice",
        ),
        # One open case per contract. A second unwinding of the same contract
        # while the first is running is two answers to "is this cancelled?".
        Index(
            "uq_sale_cancellations_open",
            "sale_contract_id",
            unique=True,
            postgresql_where=text(
                "status IN ('notice', 'cure', 'termination_pending_approval', "
                "'withdrawal_pending', 'ready_for_unit_return')"
            ),
        ),
        Index("ix_sale_cancellations_sale_contract_id_status", "sale_contract_id", "status"),
    )


# --------------------------------------------------------------------------- #
# Handover
# --------------------------------------------------------------------------- #


class HandoverRecord(Base):
    """Getting the keys to the buyer, and the sign-offs that must come first.

    One record per contract. The gates are the three clearances below, each
    granted by a different team; this row holds the operational detail around
    them — inspection, snagging, notice, keys, meters, acceptance.
    """

    __tablename__ = "handover_records"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    readiness_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    inspection_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    snag_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snag_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    client_notice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    scheduled_handover_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    handover_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    keys_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meter_readings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    acceptance_document_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=HANDOVER_PREPARATION)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("sale_contract_id", name="uq_handover_records_sale"),
        UniqueConstraint("id", "project_id", name="handover_project"),
        CheckConstraint(in_list("status", HANDOVER_STATUSES), name="status_ok"),
        CheckConstraint(
            "status <> 'handed_over' OR handover_date IS NOT NULL", name="handover_has_date"
        ),
    )


class HandoverClearance(Base):
    """One team's sign-off that handover may proceed, or its withdrawal.

    Three fixed types, each with a different owner: legal, collections and
    delivery. History is kept — a clearance that was granted and then revoked is
    two rows, and the partial index below allows exactly one current row of each
    type while leaving the withdrawn ones in place.
    """

    __tablename__ = "handover_clearances"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    handover_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    clearance_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CLEARANCE_PENDING)
    evidence_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cleared_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["handover_id", "project_id"],
            ["handover_records.id", "handover_records.project_id"],
            name="handover",
            ondelete="RESTRICT",
        ),
        CheckConstraint(in_list("clearance_type", CLEARANCE_TYPES), name="type_ok"),
        CheckConstraint(in_list("status", CLEARANCE_STATUSES), name="status_ok"),
        CheckConstraint(
            "status <> 'revoked' OR revocation_reason IS NOT NULL", name="revocation_has_reason"
        ),
        # One current clearance per type. Revoked rows fall out of the index and
        # stay in the table, which is what keeps the history readable.
        Index(
            "uq_handover_clearances_current",
            "handover_id",
            "clearance_type",
            unique=True,
            postgresql_where=text("status <> 'revoked'"),
        ),
        Index("ix_handover_clearances_handover_id", "handover_id"),
    )
