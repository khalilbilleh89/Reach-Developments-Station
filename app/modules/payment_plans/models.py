"""The contractual receivable schedule behind a sale.

Four tables, one shape::

    Sale Contract
        1 ─→ 1   Payment Plan            stable identity, one per sale
             1 ─→ n   Plan Version       one governing schedule at a time
                  1 ─→ n   Installment   one row per receivable, never a column
                           1 ─→ n   Trigger Event   manual maker/checker events

Three rules run through every table below.

**An installment is a row.** There is no ``payment_1`` … ``payment_6``. A plan
with one instalment and a plan with a hundred are the same schema, because the
number of instalments is a commercial negotiation and not a database decision.

**The schedule is versioned, not edited.** A contractual term changes by
creating a new version; the standing one keeps governing the sale until its
replacement is approved and activated. Nothing that has left draft is mutable,
so the schedule the parties agreed can always be read back exactly.

**Scheduled is not collected.** There is deliberately no ``paid_amount``, no
``balance_due``, no ``receipt_id`` and no ``days_overdue`` anywhere in this
file. An instalment of 25,000 due in September is a contractual expectation;
whether money arrived is a fact this system cannot yet state, and inventing a
column for it here would make the first collections report a lie.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MONEY, RATE, Base, in_list

# --------------------------------------------------------------------------- #
# Closed sets
# --------------------------------------------------------------------------- #

#: A version's life. ``rejected`` is a terminal side path, not a way back to
#: draft: a schedule that was refused stays refused and readable, and the
#: revision is a new version.
VERSION_STATUSES = ("draft", "submitted", "approved", "active", "superseded", "rejected")
VERSION_DRAFT = "draft"
VERSION_SUBMITTED = "submitted"
VERSION_APPROVED = "approved"
VERSION_ACTIVE = "active"
VERSION_SUPERSEDED = "superseded"
VERSION_REJECTED = "rejected"

#: The versions that are on their way somewhere. At most one per plan, so a
#: sale never has three competing draft schedules and no way to say which one
#: is being negotiated.
VERSION_OPEN = frozenset({VERSION_DRAFT, VERSION_SUBMITTED, VERSION_APPROVED})

#: The versions whose figures are settled enough to copy from.
VERSION_COPYABLE = frozenset({VERSION_APPROVED, VERSION_ACTIVE, VERSION_SUPERSEDED})

#: Which figure the preparer types. The other is derived, so a schedule can
#: never hold an amount and a percentage that disagree.
ALLOCATION_MODES = ("percentage", "amount")
ALLOCATION_PERCENTAGE = "percentage"
ALLOCATION_AMOUNT = "amount"

#: How the sale's frozen tax and buyer fees are spread across the instalments.
CHARGE_ALLOCATION_MODES = ("pro_rata", "manual")
CHARGE_PRO_RATA = "pro_rata"
CHARGE_MANUAL = "manual"

#: How the pre-contract reservation appears in the schedule.
#:
#: Neither value treats PR-MVP-05's deposit attestation as collected cash, and
#: both reconcile the full contract principal. The choice is presentational: it
#: says whether the schedule opens with an instalment representing the amount
#: agreed at reservation, or leaves that attestation to be read on the deal.
RESERVATION_TREATMENTS = ("included_in_schedule", "reference_only")
RESERVATION_INCLUDED = "included_in_schedule"
RESERVATION_REFERENCE_ONLY = "reference_only"

#: Where a version's shape came from. Two values, because a template subsystem
#: is not needed to answer "did somebody start this from an existing plan?".
ORIGIN_TYPES = ("custom", "copied_plan")
ORIGIN_CUSTOM = "custom"
ORIGIN_COPIED = "copied_plan"

#: What makes an instalment due. A closed set, deliberately: an expression
#: language here would be a rules engine, and a rules engine is a thing nobody
#: can audit.
TRIGGER_TYPES = (
    "fixed_date",
    "days_after_spa",
    "recurring_monthly",
    "recurring_quarterly",
    "construction_milestone",
    "handover",
    "title_transfer",
    "manual_approved_event",
)
TRIGGER_FIXED_DATE = "fixed_date"
TRIGGER_DAYS_AFTER_SPA = "days_after_spa"
TRIGGER_RECURRING_MONTHLY = "recurring_monthly"
TRIGGER_RECURRING_QUARTERLY = "recurring_quarterly"
TRIGGER_CONSTRUCTION_MILESTONE = "construction_milestone"
TRIGGER_HANDOVER = "handover"
TRIGGER_TITLE_TRANSFER = "title_transfer"
TRIGGER_MANUAL_EVENT = "manual_approved_event"

#: Triggers whose date the calendar already settles. Their contractual due date
#: is known when the plan is written, so activation materialises it directly.
TRIGGER_DATE_BASED = frozenset(
    {
        TRIGGER_FIXED_DATE,
        TRIGGER_DAYS_AFTER_SPA,
        TRIGGER_RECURRING_MONTHLY,
        TRIGGER_RECURRING_QUARTERLY,
    }
)

#: Triggers waiting on something to happen. A forecast date may exist for
#: planning; it never makes the money due.
TRIGGER_EVENT_BASED = frozenset(
    {
        TRIGGER_CONSTRUCTION_MILESTONE,
        TRIGGER_HANDOVER,
        TRIGGER_TITLE_TRANSFER,
        TRIGGER_MANUAL_EVENT,
    }
)

#: Where an instalment stands against its own trigger — NOT against payment.
#:
#: There is no ``paid``, ``partial``, ``overdue`` or ``defaulted`` here, and
#: adding one would be inventing cash truth this system does not have.
TRIGGER_STATUSES = ("scheduled", "awaiting_trigger", "triggered")
TRIGGER_SCHEDULED = "scheduled"
TRIGGER_AWAITING = "awaiting_trigger"
TRIGGER_TRIGGERED = "triggered"

#: A manually approved trigger event's life. Maker submits, checker approves,
#: and a mistake is reversed rather than deleted.
TRIGGER_EVENT_STATUSES = ("submitted", "approved", "reversed")
TRIGGER_EVENT_SUBMITTED = "submitted"
TRIGGER_EVENT_APPROVED = "approved"
TRIGGER_EVENT_REVERSED = "reversed"

#: How often a recurring series falls due, and the month step each implies.
RECURRENCE_MONTHS = {TRIGGER_RECURRING_MONTHLY: 1, TRIGGER_RECURRING_QUARTERLY: 3}


class PaymentPlan(Base):
    """The stable identity of a sale's payment schedule.

    One per sale contract, enforced by a unique index rather than by hoping the
    service layer always checks. It holds no money: every figure belongs to a
    version, because every figure can be revised and the revision must not
    silently rewrite what came before.
    """

    __tablename__ = "payment_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: The project-scoped human reference, ``PLN-000001``. Not identity.
    plan_number: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    #: When the first receipt against this plan was confirmed. Set once, by
    #: PR-MVP-07 through :func:`~app.modules.payment_plans.service.
    #: mark_collections_started`, and never cleared.
    #:
    #: It lives here rather than in collections because it guards a rule this
    #: module enforces: once cash has been received against a schedule, the
    #: ordinary activation path must refuse to swap the instalments underneath
    #: it, because the replacement rows have new identifiers and the money
    #: already allocated would drop out of the current view. The dependency
    #: points one way — collections calls payment plans, never the reverse — so
    #: the column that carries the fact belongs to the module that reads it.
    collections_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

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
        # Project-safe: a plan in project A cannot reference a sale in project B
        # even through direct SQL.
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("sale_contract_id", name="uq_payment_plans_sale"),
        UniqueConstraint("project_id", "plan_number", name="uq_payment_plans_number"),
        UniqueConstraint("id", "project_id", name="payment_plan_project"),
        Index("ix_payment_plans_project_id", "project_id"),
    )


class PaymentPlanVersion(Base):
    """One governing schedule, and the sale basis it was written against.

    The frozen basis is copied from the sale contract when the version is
    created and never recomputed. Pricing is not consulted and tax is not
    recalculated: the contract is already the truth about what the buyer owes,
    and a schedule that re-derived it would eventually disagree with the
    document the parties signed.
    """

    __tablename__ = "payment_plan_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    payment_plan_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=VERSION_DRAFT)
    #: The business date from which this schedule governs. A future date keeps
    #: the version approved and unactivatable; there is no scheduler.
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    # The sale's frozen basis. Copied once, at version creation.
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    contract_value_covered: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    tax_total_snapshot: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    buyer_fee_total_snapshot: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_buyer_payable_snapshot: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    allocation_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ALLOCATION_PERCENTAGE
    )
    charge_allocation_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CHARGE_PRO_RATA
    )
    reservation_treatment: Mapped[str] = mapped_column(
        String(24), nullable=False, default=RESERVATION_REFERENCE_ONLY
    )
    origin_type: Mapped[str] = mapped_column(String(16), nullable=False, default=ORIGIN_CUSTOM)
    #: The version this one was copied from, where it was.
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["payment_plan_id", "project_id"],
            ["payment_plans.id", "payment_plans.project_id"],
            name="plan",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_version_id", "project_id"],
            ["payment_plan_versions.id", "payment_plan_versions.project_id"],
            name="source",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("payment_plan_id", "version_number", name="uq_plan_versions_number"),
        UniqueConstraint("id", "project_id", name="plan_version_project"),
        CheckConstraint(in_list("status", VERSION_STATUSES), name="status_ok"),
        CheckConstraint(in_list("allocation_mode", ALLOCATION_MODES), name="allocation_ok"),
        CheckConstraint(
            in_list("charge_allocation_mode", CHARGE_ALLOCATION_MODES), name="charge_ok"
        ),
        CheckConstraint(
            in_list("reservation_treatment", RESERVATION_TREATMENTS), name="reservation_ok"
        ),
        CheckConstraint(in_list("origin_type", ORIGIN_TYPES), name="origin_ok"),
        CheckConstraint("version_number >= 1", name="version_positive"),
        CheckConstraint("contract_value_covered >= 0", name="covered_nonneg"),
        CheckConstraint("tax_total_snapshot >= 0", name="tax_nonneg"),
        CheckConstraint("buyer_fee_total_snapshot >= 0", name="fee_nonneg"),
        CheckConstraint("total_buyer_payable_snapshot >= 0", name="payable_nonneg"),
        CheckConstraint(
            "origin_type <> 'copied_plan' OR source_version_id IS NOT NULL",
            name="copied_has_source",
        ),
        CheckConstraint(
            "status <> 'rejected' OR rejection_reason IS NOT NULL", name="rejected_has_reason"
        ),
        # One standing schedule per plan. The sale cannot be governed by two
        # contradictory sets of instalments at once.
        Index(
            "uq_plan_versions_active",
            "payment_plan_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        # One version in preparation per plan. Three simultaneous drafts would
        # leave nobody able to say which schedule is being negotiated.
        Index(
            "uq_plan_versions_open",
            "payment_plan_id",
            unique=True,
            postgresql_where=text("status IN ('draft', 'submitted', 'approved')"),
        ),
        Index("ix_plan_versions_plan_status", "payment_plan_id", "status"),
        Index("ix_plan_versions_project_id", "project_id"),
    )


class PaymentPlanInstallment(Base):
    """One contractual receivable: an amount, and what makes it due.

    Both ``principal_amount`` and ``principal_fraction`` are stored so an active
    schedule reads as the contract states it — 20% and 44,000 are the same term
    said two ways, and a reader should not have to divide. Only one of them is
    typed: the version's allocation mode decides which, and the service derives
    the other, so the pair can never disagree.

    Three dates, and they are not interchangeable. ``contractual_due_date`` is
    what the contract says. ``forecast_due_date`` is somebody's expectation of
    when a contingent event will happen. ``actual_due_date`` is set only when
    the trigger has genuinely occurred — a forecast passing does not fill it in,
    which is the whole reason there are three columns and not one.
    """

    __tablename__ = "payment_plan_installments"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    payment_plan_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)

    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    #: The milestone code, event description or other human handle for the
    #: trigger. A stable reference, not a foreign key: PR-MVP-09 owns
    #: construction certification and this must not pretend to.
    trigger_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: Days after the SPA's contract date, for ``days_after_spa``.
    offset_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Position within a generated recurring series, from 1.
    recurrence_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    contractual_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    forecast_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    grace_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    principal_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    principal_fraction: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.00"))
    fee_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.00"))

    trigger_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=TRIGGER_SCHEDULED
    )
    #: Who chases this instalment. A real user in a role that does the chasing,
    #: not an arbitrary identifier.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["payment_plan_version_id", "project_id"],
            ["payment_plan_versions.id", "payment_plan_versions.project_id"],
            name="version",
            ondelete="CASCADE",
        ),
        UniqueConstraint("payment_plan_version_id", "sequence", name="uq_installments_sequence"),
        UniqueConstraint("id", "project_id", name="plan_installment_project"),
        CheckConstraint(in_list("trigger_type", TRIGGER_TYPES), name="trigger_type_ok"),
        CheckConstraint(in_list("trigger_status", TRIGGER_STATUSES), name="trigger_status_ok"),
        CheckConstraint("sequence >= 1", name="sequence_positive"),
        CheckConstraint("principal_amount >= 0", name="principal_nonneg"),
        CheckConstraint("tax_amount >= 0", name="tax_nonneg"),
        CheckConstraint("fee_amount >= 0", name="fee_nonneg"),
        CheckConstraint("grace_days >= 0", name="grace_nonneg"),
        CheckConstraint(
            "principal_fraction >= 0 AND principal_fraction <= 1", name="fraction_range"
        ),
        CheckConstraint(
            "offset_days IS NULL OR offset_days >= 0",
            name="offset_nonneg",
        ),
        # A relative trigger without its offset is not a schedule.
        CheckConstraint(
            "trigger_type <> 'days_after_spa' OR offset_days IS NOT NULL",
            name="relative_has_offset",
        ),
        # A date-based trigger must say which date.
        CheckConstraint(
            "trigger_type NOT IN ('fixed_date', 'recurring_monthly', 'recurring_quarterly')"
            " OR contractual_due_date IS NOT NULL",
            name="dated_has_date",
        ),
        # The control this whole module exists to keep: money becomes due on a
        # contingent trigger only when that trigger actually fired. A forecast
        # date can never fill in an actual due date.
        CheckConstraint(
            "trigger_type IN ('fixed_date', 'days_after_spa', 'recurring_monthly',"
            " 'recurring_quarterly')"
            " OR actual_due_date IS NULL OR trigger_status = 'triggered'",
            name="contingent_needs_trigger",
        ),
        Index("ix_installments_version_sequence", "payment_plan_version_id", "sequence"),
        Index("ix_installments_project_id", "project_id"),
        Index("ix_installments_actual_due_date", "actual_due_date"),
        Index("ix_installments_forecast_due_date", "forecast_due_date"),
        Index("ix_installments_trigger_status", "trigger_status"),
        Index("ix_installments_owner_user_id", "owner_user_id"),
    )


class InstallmentTriggerEvent(Base):
    """A manually attested event that makes one instalment due.

    Only for ``manual_approved_event``. A construction milestone cannot be
    triggered this way — PR-MVP-09 certifies those, and letting somebody type
    one in here would manufacture the certification this system is not yet
    entitled to make.

    Maker and checker are different people, and a mistake is reversed rather
    than deleted: the original attestation stays on the record because somebody
    made it.
    """

    __tablename__ = "installment_trigger_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    installment_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=TRIGGER_EVENT_SUBMITTED)

    submitted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["installment_id", "project_id"],
            ["payment_plan_installments.id", "payment_plan_installments.project_id"],
            name="installment",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="plan_trigger_event_project"),
        CheckConstraint(in_list("status", TRIGGER_EVENT_STATUSES), name="status_ok"),
        CheckConstraint(
            "status <> 'reversed' OR reversal_reason IS NOT NULL", name="reversed_has_reason"
        ),
        CheckConstraint(
            "status <> 'approved' OR approved_by_user_id IS NOT NULL", name="approved_has_approver"
        ),
        # One event at a time per instalment: a second attestation cannot be
        # opened while one is standing or awaiting a decision.
        Index(
            "uq_trigger_events_standing",
            "installment_id",
            unique=True,
            postgresql_where=text("status IN ('submitted', 'approved')"),
        ),
        Index("ix_trigger_events_installment_id", "installment_id"),
        Index("ix_trigger_events_project_id", "project_id"),
    )
