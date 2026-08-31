"""The first cash ledger in the system: what arrived, and where it was applied.

Seven tables, and one chain running through them::

    Sale Contract
        ↓
    Active Payment Plan Version          PR-MVP-06 — what is owed
        ↓
    Instalment
        ↓
    Receipt Allocation  ←──────────  Confirmed Receipt   — what arrived
        ↓
    derived outstanding / aging

and, when a contract is unwound::

    SaleCancellation.refund_due_amount
        ↓
    Confirmed Refund                                     — what left

Four distinctions are load-bearing, and every table below exists to keep one of
them.

**Scheduled is not collected.** PR-MVP-06 deliberately has no ``paid_amount``.
This module supplies the missing half, and does it with rows rather than a
balance column, so the answer to "how much has this buyer paid?" is always a
list of receipts somebody can point at.

**A receipt is not an allocation.** Ten thousand arriving is a fact about the
company's bank account. Which instalment it settles is a separate decision,
made by a person, recorded separately, and reversible without pretending the
money never came. Cash that has arrived and not yet been applied is *unapplied*,
and it is visible rather than quietly absorbed.

**A refund is not a negative receipt.** Money leaving gets its own table. A
signed amount in :class:`CollectionReceipt` would make every ``SUM`` in this
file ambiguous and would misstate PR-MVP-10's cashflow the day it is written.

**Nothing here is a balance column.** There is no ``outstanding_amount``, no
``unapplied_amount``, no ``project_total_overdue``. Every figure the API
reports is computed from these rows at read time. A stored total is a second
source of truth, and it becomes the wrong one the first time a write path
forgets it.

Deletion does not appear in this file either. A receipt is reversed, an
allocation is reversed or superseded, a dispute is resolved or withdrawn, a
waiver is revoked. Each keeps its actor, its timestamp and — where it undoes
something — its reason.
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
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MONEY, Base, in_list

# --------------------------------------------------------------------------- #
# Closed sets
# --------------------------------------------------------------------------- #

#: A receipt's life. ``recorded`` is a claim that money arrived; ``confirmed``
#: is Finance accepting it. Only the second is cash truth, and the gap between
#: them is the whole point of having two values.
RECEIPT_STATUSES = ("recorded", "confirmed", "reversed")
RECEIPT_RECORDED = "recorded"
RECEIPT_CONFIRMED = "confirmed"
RECEIPT_REVERSED = "reversed"

#: An allocation's life. ``superseded`` is not a reversal: the cash stayed
#: applied, it simply moved onto the instalment that replaced the original when
#: the schedule was restructured.
ALLOCATION_STATUSES = ("active", "superseded", "reversed")
ALLOCATION_ACTIVE = "active"
ALLOCATION_SUPERSEDED = "superseded"
ALLOCATION_REVERSED = "reversed"

#: What Collections did about an overdue amount. A closed list, because an
#: operator typing a free-form activity type is a register nobody can filter.
ACTION_TYPES = (
    "call",
    "email",
    "meeting",
    "reminder",
    "formal_notice",
    "promise_to_pay",
    "legal_referral",
    "follow_up",
    "other",
)
ACTION_PROMISE = "promise_to_pay"

#: A dispute's life. Resolved means somebody decided it; withdrawn means the
#: buyer or Collections dropped it. Neither has ever changed what is owed.
DISPUTE_STATUSES = ("open", "resolved", "withdrawn")
DISPUTE_OPEN = "open"
DISPUTE_RESOLVED = "resolved"
DISPUTE_WITHDRAWN = "withdrawn"

#: What an approved waiver actually suspends. Both are operational: they pause
#: *collection action*, never the obligation. There is deliberately no
#: ``principal_forgiveness`` here — forgiving money is a contractual amendment
#: and belongs to Sales/Legal with a payment-plan restructure behind it.
WAIVER_TYPES = ("collection_hold", "grace_extension")
WAIVER_HOLD = "collection_hold"
WAIVER_GRACE = "grace_extension"

#: A waiver's life. Maker submits, CFO decides, and an approved one can later
#: be withdrawn when circumstances change.
WAIVER_STATUSES = ("submitted", "approved", "rejected", "revoked")
WAIVER_SUBMITTED = "submitted"
WAIVER_APPROVED = "approved"
WAIVER_REJECTED = "rejected"
WAIVER_REVOKED = "revoked"

#: The waivers that are still standing in one form or another. At most one per
#: instalment, so nobody has to decide which of two holds applies.
WAIVER_LIVE = frozenset({WAIVER_SUBMITTED, WAIVER_APPROVED})

#: A restructure's life. ``abandoned`` exists because the CFO can refuse the
#: replacement schedule: PR-MVP-06 makes a rejected version terminal, so
#: without a way to close the restructure that asked for it, one refusal would
#: block the plan from ever being restructured again.
RESTRUCTURE_STATUSES = ("open", "applied", "abandoned")
RESTRUCTURE_OPEN = "open"
RESTRUCTURE_APPLIED = "applied"
RESTRUCTURE_ABANDONED = "abandoned"

#: A refund's life, mirroring a receipt's for the same reason: Collections
#: records that a repayment is being made, Finance confirms the money left.
REFUND_STATUSES = ("recorded", "confirmed", "reversed")
REFUND_RECORDED = "recorded"
REFUND_CONFIRMED = "confirmed"
REFUND_REVERSED = "reversed"


class CollectionReceipt(Base):
    """One claimed incoming cash transaction against one contract.

    ``amount`` is always positive. Money leaving is :class:`CollectionRefund`,
    not a negative row here, so every ``SUM(amount)`` over this table means
    exactly one thing.

    A confirmed receipt is never edited and never deleted. A correction is a
    reversal plus a fresh receipt, which leaves both the mistake and the fix on
    the record — the sequence an auditor asking "why does this account show two
    receipts for the same transfer?" needs to be able to read.
    """

    __tablename__ = "collection_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    #: The project-scoped human reference, ``RCT-000001``. A label, not identity.
    receipt_number: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Copied from the contract, never chosen by the operator. A JOD contract
    #: cannot receive a USD receipt: this MVP settles in the contract's frozen
    #: currency and has no FX model to convert one into the other.
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    #: The business date the money arrived. Never in the future: a receipt is a
    #: record of something that happened, not a plan.
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)

    bank_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=RECEIPT_RECORDED)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reversal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "receipt_number", name="uq_collection_receipts_number"),
        UniqueConstraint("id", "project_id", name="collection_receipt_project"),
        CheckConstraint(in_list("status", RECEIPT_STATUSES), name="status_ok"),
        # Cash in is positive. A "negative receipt" would be a refund wearing
        # the wrong table's name.
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "status <> 'confirmed' OR (confirmed_at IS NOT NULL"
            " AND confirmed_by_user_id IS NOT NULL)",
            name="confirmed_has_actor",
        ),
        CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL"
            " AND reversed_by_user_id IS NOT NULL AND reversal_reason IS NOT NULL)",
            name="reversed_has_reason",
        ),
        Index("ix_collection_receipts_sale_status", "sale_contract_id", "status"),
        Index("ix_collection_receipts_project_id", "project_id"),
        Index("ix_collection_receipts_receipt_date", "receipt_date"),
    )


class CollectionReceiptAllocation(Base):
    """This much of this receipt was applied to this instalment.

    Every identifier in the chain is stored — sale, plan, version, instalment,
    receipt — and each is bound to ``project_id`` by a composite foreign key, so
    a row pairing project A's receipt with project B's instalment cannot be
    written even through direct SQL.

    Storing the version alongside the instalment is not redundancy for its own
    sake. When a schedule is restructured the instalment identifiers change, and
    reconstructing *which schedule this cash was believed to settle at the time*
    is exactly the question an auditor asks about a restructured plan.

    ``superseded`` rows are the other half of that answer. A restructure never
    edits an allocation; it closes the old row, links it to the restructure that
    closed it, and opens a new one against the replacement instalment.
    """

    __tablename__ = "collection_receipt_allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    payment_plan_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    payment_plan_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    installment_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    receipt_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ALLOCATION_ACTIVE)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reversal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_restructure_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["payment_plan_id", "project_id"],
            ["payment_plans.id", "payment_plans.project_id"],
            name="plan",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["payment_plan_version_id", "project_id"],
            ["payment_plan_versions.id", "payment_plan_versions.project_id"],
            name="version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["installment_id", "project_id"],
            ["payment_plan_installments.id", "payment_plan_installments.project_id"],
            name="installment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["receipt_id", "project_id"],
            ["collection_receipts.id", "collection_receipts.project_id"],
            name="receipt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["superseded_by_restructure_id", "project_id"],
            ["collection_restructures.id", "collection_restructures.project_id"],
            name="restructure",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="collection_allocation_project"),
        CheckConstraint(in_list("status", ALLOCATION_STATUSES), name="status_ok"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL"
            " AND reversed_by_user_id IS NOT NULL AND reversal_reason IS NOT NULL)",
            name="reversed_has_reason",
        ),
        CheckConstraint(
            "status <> 'superseded' OR (superseded_at IS NOT NULL"
            " AND superseded_by_restructure_id IS NOT NULL)",
            name="superseded_has_cause",
        ),
        Index("ix_collection_allocations_receipt", "receipt_id", "status"),
        Index("ix_collection_allocations_installment", "installment_id", "status"),
        Index("ix_collection_allocations_version", "payment_plan_version_id", "status"),
        Index("ix_collection_allocations_sale", "sale_contract_id", "status"),
        Index("ix_collection_allocations_project_id", "project_id"),
    )


class CollectionAction(Base):
    """One thing Collections did about an amount, appended and never edited.

    There is no update route and no delete route. A note recorded in error is
    followed by another note, because the register's value is that it shows what
    was actually done and when, not a tidied summary of it.

    ``promised_amount`` is deliberately not cash. A buyer promising ten thousand
    tomorrow moves no figure in this ledger; only a confirmed receipt does. The
    promise is kept beside the money so a collections officer can see the gap
    between the two, which is the whole reason for recording it.
    """

    __tablename__ = "collection_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: The instalment this was about, when it was about one. A general chase of
    #: an account is not attached to a row.
    installment_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    #: When the action happened. Not in the future — this records something
    #: done, and ``next_action_date`` is where an intention goes.
    action_at: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(String(2000), nullable=False)

    promised_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    promised_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
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
        ForeignKeyConstraint(
            ["installment_id", "project_id"],
            ["payment_plan_installments.id", "payment_plan_installments.project_id"],
            name="installment",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="collection_action_project"),
        CheckConstraint(in_list("action_type", ACTION_TYPES), name="type_ok"),
        CheckConstraint("promised_amount IS NULL OR promised_amount > 0", name="promise_positive"),
        CheckConstraint("length(notes) > 0", name="notes_not_blank"),
        Index("ix_collection_actions_sale_action_at", "sale_contract_id", "action_at"),
        Index("ix_collection_actions_next_action_date", "next_action_date"),
        Index("ix_collection_actions_project_id", "project_id"),
    )


class CollectionDispute(Base):
    """The buyer contests an instalment. The instalment stays due.

    A dispute changes no amount and no date. An instalment can be disputed,
    forty-seven days overdue and eight thousand outstanding at the same time,
    and all three facts stay readable — collapsing them into one badge is how a
    receivables report quietly stops adding up.
    """

    __tablename__ = "collection_disputes"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    installment_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=DISPUTE_OPEN)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    resolution: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["installment_id", "project_id"],
            ["payment_plan_installments.id", "payment_plan_installments.project_id"],
            name="installment",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="collection_dispute_project"),
        CheckConstraint(in_list("status", DISPUTE_STATUSES), name="status_ok"),
        CheckConstraint("length(reason) > 0", name="reason_not_blank"),
        CheckConstraint(
            "status = 'open' OR (resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)",
            name="closed_has_actor",
        ),
        # One open dispute per instalment. Two simultaneous disputes over the
        # same money is two answers to "is this contested?".
        Index(
            "uq_collection_disputes_open",
            "installment_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("ix_collection_disputes_sale_status", "sale_contract_id", "status"),
        Index("ix_collection_disputes_project_id", "project_id"),
    )


class CollectionWaiver(Base):
    """An approved pause on chasing an instalment. Never on owing it.

    ``waiver_type`` names an operational concession — hold the chase, extend the
    enforcement grace — and the money stays scheduled, stays outstanding and
    stays counted. There is no waiver here that reduces principal, tax or buyer
    fees, because forgiving money is a contractual act: it goes through a
    Sales/Legal amendment and a payment-plan restructure, where the CFO is
    approving a changed schedule rather than a collections note.
    """

    __tablename__ = "collection_waivers"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    installment_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    waiver_type: Mapped[str] = mapped_column(String(24), nullable=False)
    #: The date the concession runs to. In the future when submitted: a hold
    #: that expired before it was asked for concedes nothing.
    waived_until: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=WAIVER_SUBMITTED)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    submitted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
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
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    revocation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["installment_id", "project_id"],
            ["payment_plan_installments.id", "payment_plan_installments.project_id"],
            name="installment",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="collection_waiver_project"),
        CheckConstraint(in_list("waiver_type", WAIVER_TYPES), name="type_ok"),
        CheckConstraint(in_list("status", WAIVER_STATUSES), name="status_ok"),
        CheckConstraint("length(reason) > 0", name="reason_not_blank"),
        CheckConstraint(
            "status <> 'approved' OR (approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)",
            name="approved_has_actor",
        ),
        CheckConstraint(
            "status <> 'rejected' OR (rejected_at IS NOT NULL"
            " AND rejected_by_user_id IS NOT NULL AND rejection_reason IS NOT NULL)",
            name="rejected_has_reason",
        ),
        CheckConstraint(
            "status <> 'revoked' OR (revoked_at IS NOT NULL"
            " AND revoked_by_user_id IS NOT NULL AND revocation_reason IS NOT NULL)",
            name="revoked_has_reason",
        ),
        # One live waiver per instalment, submitted or approved. Rejected and
        # revoked rows fall out of the index and stay in the table.
        Index(
            "uq_collection_waivers_live",
            "installment_id",
            unique=True,
            postgresql_where=text("status IN ('submitted', 'approved')"),
        ),
        Index("ix_collection_waivers_sale_status", "sale_contract_id", "status"),
        Index("ix_collection_waivers_project_id", "project_id"),
    )


class CollectionRestructure(Base):
    """Why a plan with cash against it is being rescheduled, and what replaced it.

    This table holds no instalments. The revised schedule is an ordinary
    :class:`~app.modules.payment_plans.models.PaymentPlanVersion`, edited in the
    Payment Plan Builder and sanctioned by the CFO through PR-MVP-06's existing
    lifecycle — one financial decision, one approval, one editor.

    What Collections owns is the part PR-MVP-06 cannot know about: that money
    has already been received against the schedule being replaced, and that
    every unit of it has to survive the change. ``applied_at`` is the moment
    that carry-forward happened, and the superseded allocations point back here.
    """

    __tablename__ = "collection_restructures"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    payment_plan_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    #: The project-scoped human reference, ``RST-000001``.
    restructure_number: Mapped[str] = mapped_column(String(32), nullable=False)
    #: The version that was governing when this was raised.
    source_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: The revision opened to replace it.
    replacement_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=RESTRUCTURE_OPEN)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    abandoned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    abandonment_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
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
        ForeignKeyConstraint(
            ["replacement_version_id", "project_id"],
            ["payment_plan_versions.id", "payment_plan_versions.project_id"],
            name="replacement",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id", "restructure_number", name="uq_collection_restructures_number"
        ),
        UniqueConstraint("id", "project_id", name="collection_restructure_project"),
        CheckConstraint(in_list("status", RESTRUCTURE_STATUSES), name="status_ok"),
        CheckConstraint("length(reason) > 0", name="reason_not_blank"),
        CheckConstraint("source_version_id <> replacement_version_id", name="versions_differ"),
        CheckConstraint(
            "status <> 'applied' OR (applied_at IS NOT NULL AND applied_by_user_id IS NOT NULL)",
            name="applied_has_actor",
        ),
        CheckConstraint(
            "status <> 'abandoned' OR (abandoned_at IS NOT NULL"
            " AND abandoned_by_user_id IS NOT NULL AND abandonment_reason IS NOT NULL)",
            name="abandoned_has_reason",
        ),
        # One restructure in flight per plan. A second would leave two answers
        # to "which revision is the one carrying the cash forward?".
        Index(
            "uq_collection_restructures_open",
            "payment_plan_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("ix_collection_restructures_plan_status", "payment_plan_id", "status"),
        Index("ix_collection_restructures_project_id", "project_id"),
    )


class CollectionRefund(Base):
    """Money going back to a buyer whose contract was unwound.

    PR-MVP-05 records what is *due* on a cancellation and is careful never to
    call it paid. This is the other half: a dated, referenced, Finance-confirmed
    record that the money actually left. The two are reported side by side and
    never merged, because "we owe them twelve thousand" and "we have paid them
    five" are different sentences and a buyer will ask about both.

    Cumulative confirmed refunds may not exceed the approved amount due. Partial
    refunds are ordinary — several transfers against one cancellation is how
    this is usually settled.
    """

    __tablename__ = "collection_refunds"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    cancellation_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    #: The project-scoped human reference, ``RFD-000001``.
    refund_number: Mapped[str] = mapped_column(String(32), nullable=False)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    refund_date: Mapped[date] = mapped_column(Date, nullable=False)

    bank_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=REFUND_RECORDED)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reversal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["cancellation_id", "project_id"],
            ["sale_cancellations.id", "sale_cancellations.project_id"],
            name="cancellation",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "refund_number", name="uq_collection_refunds_number"),
        UniqueConstraint("id", "project_id", name="collection_refund_project"),
        CheckConstraint(in_list("status", REFUND_STATUSES), name="status_ok"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "status <> 'confirmed' OR (confirmed_at IS NOT NULL"
            " AND confirmed_by_user_id IS NOT NULL)",
            name="confirmed_has_actor",
        ),
        CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL"
            " AND reversed_by_user_id IS NOT NULL AND reversal_reason IS NOT NULL)",
            name="reversed_has_reason",
        ),
        Index("ix_collection_refunds_cancellation", "cancellation_id", "status"),
        Index("ix_collection_refunds_sale_status", "sale_contract_id", "status"),
        Index("ix_collection_refunds_project_id", "project_id"),
    )
