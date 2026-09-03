"""What was approved to be spent, committed, certified, invoiced and paid.

Six questions that a single "construction cost" column cannot answer, and the
reason this module has sixteen tables rather than one:

```text
budget          what the business authorised
commitment      what it contractually owes, once signed
certification   what work has been formally certified as done
invoice         what has become an approved liability
payment         what cash has actually left the account
forecast        what Finance now expects the whole thing to cost
```

Each is a different fact with a different owner, a different approver and a
different moment. Collapsing any two of them loses somebody's accountability: a
contractor's claim is not certified work, a certificate is not an invoice, an
approved invoice is not cash, and none of them is the budget.

Three properties are worth stating because everything below follows from them.

**Nothing that can be derived is stored.** There is no ``revised_contract_value``
column, no ``retention_balance``, no ``cumulative_certified``, no
``advance_outstanding``. Each is a sum over immutable rows, and a stored copy is
a number that will one day disagree with the rows it claims to summarise. The
one deliberate exception is the certificate's own deduction inputs, which are
what somebody signed rather than a summary of anything.

**Status is not money.** A contract that terminates does not stop being a
million dirhams of commitment; it stops being a contract anybody will certify
more work under. Removing the money takes a signed negative variation, which is
a financial transaction with an approver and a reason. So no lifecycle
transition anywhere in this module subtracts an amount as a side effect.

**Cost basis and cash basis never share a total.** Budget, commitment,
certified work, EAC and VAC are ex tax. Invoices, payments, retention and
advance carry tax and deductions, because that is what actually moves through a
bank. The two are reported beside each other and never added, and every schema
that returns them says which basis it is on.
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
# Cost codes
# --------------------------------------------------------------------------- #

#: The economic groups a cost code can belong to. Four, closed, and not a chart
#: of accounts: a configurable ledger here would be an accounting system, and
#: the platform already refuses to become one. Only ``hard`` carries downstream
#: meaning — it is what unit economics may source as a project's hard cost.
COST_CATEGORIES = ("hard", "soft", "contingency", "other")
CATEGORY_HARD = "hard"
CATEGORY_SOFT = "soft"
CATEGORY_CONTINGENCY = "contingency"
CATEGORY_OTHER = "other"

# --------------------------------------------------------------------------- #
# Budget
# --------------------------------------------------------------------------- #

#: How an approved budget moves. The same six states pricing and unit economics
#: use, for the same reason: a financial basis is drafted, checked, approved,
#: made current, and then kept because money was committed against it.
BUDGET_STATUSES = (
    "draft",
    "submitted",
    "approved",
    "active",
    "superseded",
    "rejected",
)
BUDGET_DRAFT = "draft"
BUDGET_SUBMITTED = "submitted"
BUDGET_APPROVED = "approved"
BUDGET_ACTIVE = "active"
BUDGET_SUPERSEDED = "superseded"
BUDGET_REJECTED = "rejected"

#: States in which a version's lines are frozen. Editing a line here would move
#: the authorisation a standing contract was activated against.
BUDGET_FROZEN = frozenset({BUDGET_SUBMITTED, BUDGET_APPROVED, BUDGET_ACTIVE, BUDGET_SUPERSEDED})

#: States that occupy the single revision slot. One project may hold one budget
#: being worked on and one budget in force, never two of either.
BUDGET_OPEN = frozenset({BUDGET_DRAFT, BUDGET_SUBMITTED, BUDGET_APPROVED})

# --------------------------------------------------------------------------- #
# Contracts
# --------------------------------------------------------------------------- #

#: What kind of commitment this is. A short closed list so a register can be
#: read at a glance, not a contract-type rules engine: nothing in this module
#: branches on the value.
CONTRACT_TYPES = ("works", "consultancy", "supply", "purchase_order", "other")

#: A commitment's life. ``cancelled`` is for one that never became a commitment
#: at all; ``terminated`` is for one that did and stopped early, which is why
#: the two are not the same word.
CONTRACT_STATUSES = ("draft", "submitted", "active", "completed", "terminated", "cancelled")
CONTRACT_DRAFT = "draft"
CONTRACT_SUBMITTED = "submitted"
CONTRACT_ACTIVE = "active"
CONTRACT_COMPLETED = "completed"
CONTRACT_TERMINATED = "terminated"
CONTRACT_CANCELLED = "cancelled"

#: Contracts whose value stands as commitment. A terminated contract is here on
#: purpose: work was committed and, in most cases, certified. Its money leaves
#: through a signed negative variation, never through a status change.
CONTRACT_COMMITTING = frozenset({CONTRACT_ACTIVE, CONTRACT_COMPLETED, CONTRACT_TERMINATED})

#: Contracts whose header and lines may still be edited.
CONTRACT_EDITABLE = frozenset({CONTRACT_DRAFT})

# --------------------------------------------------------------------------- #
# Variations
# --------------------------------------------------------------------------- #

#: A change's life. Approved is terminal: a mistake is corrected by a counter
#: variation, which leaves an auditable bridge, rather than by editing the row
#: somebody signed.
VARIATION_STATUSES = ("draft", "submitted", "approved", "rejected", "withdrawn")
VARIATION_DRAFT = "draft"
VARIATION_SUBMITTED = "submitted"
VARIATION_APPROVED = "approved"
VARIATION_REJECTED = "rejected"
VARIATION_WITHDRAWN = "withdrawn"

# --------------------------------------------------------------------------- #
# Certificates
# --------------------------------------------------------------------------- #

#: A certificate's life. ``certified`` is the only state that is work done; the
#: rest are a document in progress, a refusal, or a signed certificate that was
#: formally undone with a reason.
CERTIFICATE_STATUSES = ("draft", "submitted", "certified", "rejected", "reversed")
CERTIFICATE_DRAFT = "draft"
CERTIFICATE_SUBMITTED = "submitted"
CERTIFICATE_CERTIFIED = "certified"
CERTIFICATE_REJECTED = "rejected"
CERTIFICATE_REVERSED = "reversed"

# --------------------------------------------------------------------------- #
# Invoices
# --------------------------------------------------------------------------- #

#: What an invoice is claiming against. ``advance`` is the only kind that may
#: exist without a certificate, because an advance is paid before any work.
INVOICE_TYPES = ("advance", "progress", "retention_release", "final", "other")
INVOICE_ADVANCE = "advance"
INVOICE_PROGRESS = "progress"
INVOICE_RETENTION_RELEASE = "retention_release"
INVOICE_FINAL = "final"
INVOICE_OTHER = "other"

#: Invoice kinds that must name the certificate that authorises them, which is
#: every kind but the advance. ``other`` is in here deliberately: an invoice type
#: with no ceiling is a way to approve a liability that no certified work and no
#: contractual entitlement supports, and that is the one thing this module is
#: built to prevent.
INVOICE_NEEDS_CERTIFICATE = frozenset(
    {INVOICE_PROGRESS, INVOICE_RETENTION_RELEASE, INVOICE_FINAL, INVOICE_OTHER}
)

#: An invoice's life. ``recorded`` is a document somebody entered; it is not yet
#: a liability. ``disputed`` is a liability under argument — still owed, still
#: reported, and not payable until the argument ends.
INVOICE_STATUSES = ("recorded", "approved", "disputed", "voided")
INVOICE_RECORDED = "recorded"
INVOICE_APPROVED = "approved"
INVOICE_DISPUTED = "disputed"
INVOICE_VOIDED = "voided"

#: Invoices that stand as an obligation. A dispute is an argument about an
#: amount, not a reduction of it: subtracting a disputed invoice from what the
#: developer owes would make the obligation disappear the moment somebody
#: objected to it.
INVOICE_STANDING = frozenset({INVOICE_APPROVED, INVOICE_DISPUTED})

# --------------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------------- #

#: Cash out, with the same discipline collections applies to cash in: a person
#: records it, a different person confirms it, and a mistake is reversed with a
#: reason rather than deleted.
PAYMENT_STATUSES = ("recorded", "confirmed", "reversed")
PAYMENT_RECORDED = "recorded"
PAYMENT_CONFIRMED = "confirmed"
PAYMENT_REVERSED = "reversed"

# --------------------------------------------------------------------------- #
# Milestones
# --------------------------------------------------------------------------- #

#: What a milestone marks. Four, closed, and nothing branches on the value.
MILESTONE_TYPES = ("start", "progress", "completion", "other")

#: A milestone's life. The distance between ``achieved`` and ``certified`` is
#: the whole point of the table: somebody on site saying the work is done is not
#: the formal certification that makes a buyer's instalment fall due.
MILESTONE_STATUSES = ("planned", "in_progress", "achieved", "certified", "cancelled")
MILESTONE_PLANNED = "planned"
MILESTONE_IN_PROGRESS = "in_progress"
MILESTONE_ACHIEVED = "achieved"
MILESTONE_CERTIFIED = "certified"
MILESTONE_CANCELLED = "cancelled"

# --------------------------------------------------------------------------- #
# Forecast
# --------------------------------------------------------------------------- #

#: A forecast's life, matching the budget's. One active per project, because
#: "what we now expect this to cost" has exactly one current answer.
FORECAST_STATUSES = (
    "draft",
    "submitted",
    "approved",
    "active",
    "superseded",
    "rejected",
)
FORECAST_DRAFT = "draft"
FORECAST_SUBMITTED = "submitted"
FORECAST_APPROVED = "approved"
FORECAST_ACTIVE = "active"
FORECAST_SUPERSEDED = "superseded"
FORECAST_REJECTED = "rejected"

FORECAST_FROZEN = frozenset(
    {FORECAST_SUBMITTED, FORECAST_APPROVED, FORECAST_ACTIVE, FORECAST_SUPERSEDED}
)
FORECAST_OPEN = frozenset({FORECAST_DRAFT, FORECAST_SUBMITTED, FORECAST_APPROVED})

#: Audit entity names.
ENTITY_COST_CODE = "construction_cost_code"
ENTITY_BUDGET = "construction_budget_version"
ENTITY_CONTRACT = "construction_contract"
ENTITY_VARIATION = "construction_variation"
ENTITY_CERTIFICATE = "construction_certificate"
ENTITY_INVOICE = "construction_invoice"
ENTITY_PAYMENT = "construction_payment"
ENTITY_MILESTONE = "construction_milestone"
ENTITY_FORECAST = "construction_forecast_version"


# --------------------------------------------------------------------------- #
# Cost codes
# --------------------------------------------------------------------------- #


class CostCode(Base):
    """One line of the project's construction breakdown, stable for its life.

    Every financial row in this module points at a cost code, which is what
    makes budget, commitment, certification and forecast comparable at all: they
    are four numbers about the same thing. A code is therefore never deleted
    once anything governed has referenced it — it is retired, and the history
    that names it keeps reading.
    """

    __tablename__ = "construction_cost_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: The code this one rolls up into. Same project, never itself, and the
    #: service refuses a cycle — an invariant that spans rows and therefore
    #: cannot be a check constraint.
    parent_cost_code_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )

    cost_category: Mapped[str] = mapped_column(String(16), nullable=False)
    #: A practical grouping for people — "Main Works", "MEP", "Landscape". It
    #: is a label on a register and nothing in this module branches on it.
    package: Mapped[str | None] = mapped_column(String(120), nullable=True)

    phase_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    building_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

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

    __table_args__ = (
        ForeignKeyConstraint(
            ["parent_cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="parent_code",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["building_id", "project_id"],
            ["buildings.id", "buildings.project_id"],
            name="building",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "code", name="uq_cx_cost_code"),
        UniqueConstraint("id", "project_id", name="cx_cost_code_project"),
        CheckConstraint(in_list("cost_category", COST_CATEGORIES), name="category_ok"),
        CheckConstraint("length(code) > 0", name="code_present"),
        CheckConstraint("length(name) > 0", name="name_present"),
        CheckConstraint("parent_cost_code_id <> id", name="parent_not_self"),
        Index("ix_cx_cost_codes_project_active", "project_id", "is_active"),
    )


# --------------------------------------------------------------------------- #
# Budget
# --------------------------------------------------------------------------- #


class BudgetVersion(Base):
    """One governed authorisation to spend, and the reason it replaced the last.

    A budget is never overwritten. Revising one clones its lines into a new
    draft, and the original keeps saying what it said, because a commitment was
    authorised against it and "what were we allowed to spend when we signed
    that?" has to stay answerable.
    """

    __tablename__ = "construction_budget_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    #: The project's base currency, captured here rather than read through at
    #: display time. A budget approved in dirhams stays a budget in dirhams even
    #: if the project's configuration is ever re-based.
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=BUDGET_DRAFT)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    #: The version this one was cloned from, where it was. A composite key
    #: rather than a bare identifier: lineage that cannot prove the parent
    #: exists and belongs to the same project is a note, not provenance, and the
    #: first thing anybody asks of a budget is what it replaced.
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    change_reason: Mapped[str] = mapped_column(String(1000), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
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
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["source_version_id", "project_id"],
            [
                "construction_budget_versions.id",
                "construction_budget_versions.project_id",
            ],
            name="source_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="cx_budget_project"),
        UniqueConstraint("project_id", "version_number", name="uq_cx_budget_number"),
        CheckConstraint(in_list("status", BUDGET_STATUSES), name="status_ok"),
        CheckConstraint("version_number >= 1", name="number_positive"),
        CheckConstraint("length(change_reason) > 0", name="reason_present"),
        # A status is a claim; these are the fields that make it evidence. A row
        # saying "approved" with nobody's name on it is exactly what an audit
        # asks about and exactly what the service must never be the only thing
        # preventing.
        CheckConstraint(
            "status <> 'rejected'"
            " OR (rejected_at IS NOT NULL AND rejected_by_user_id IS NOT NULL"
            " AND rejection_reason IS NOT NULL)",
            name="rejected_shape",
        ),
        CheckConstraint(
            "status NOT IN ('active', 'superseded')"
            " OR (activated_at IS NOT NULL AND activated_by_user_id IS NOT NULL)",
            name="activated_shape",
        ),
        CheckConstraint(
            "status NOT IN ('approved', 'active', 'superseded')"
            " OR (approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)",
            name="approved_shape",
        ),
        # One budget in force, and one being worked on. Both are partial unique
        # indexes rather than service checks because two concurrent activations
        # would each read "no active version" and both write one.
        Index(
            "uq_cx_budgets_one_active",
            "project_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_cx_budgets_one_open",
            "project_id",
            unique=True,
            postgresql_where=text("status IN ('draft', 'submitted', 'approved')"),
        ),
        Index("ix_cx_budgets_project_status", "project_id", "status"),
    )


class BudgetLine(Base):
    """One cost code's authorisation inside one budget version.

    Three amounts, deliberately not four. ``baseline_amount`` is history and a
    revision must carry it forward unchanged; ``approved_budget_amount`` is the
    current authorisation; ``contingency_amount`` is the separately approved
    reserve. The control budget is their sum and is derived, because a stored
    total is a number that can disagree with the two figures printed beside it.
    """

    __tablename__ = "construction_budget_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    budget_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    cost_code_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    #: The original approved baseline for this cost code. A later revision
    #: carries it forward untouched: the point of a baseline is that it says
    #: what was first authorised, not what is authorised now.
    baseline_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    approved_budget_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    contingency_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.00")
    )

    funding_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["budget_version_id", "project_id"],
            ["construction_budget_versions.id", "construction_budget_versions.project_id"],
            name="budget",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("budget_version_id", "cost_code_id", name="uq_cx_budget_line"),
        CheckConstraint("baseline_amount >= 0", name="baseline_nonneg"),
        CheckConstraint("approved_budget_amount >= 0", name="approved_nonneg"),
        CheckConstraint("contingency_amount >= 0", name="contingency_nonneg"),
        Index("ix_cx_budget_lines_version", "budget_version_id"),
    )


# --------------------------------------------------------------------------- #
# Contracts
# --------------------------------------------------------------------------- #


class Contract(Base):
    """One commitment to a vendor, frozen at the value it was authorised for.

    The vendor is a snapshot of name and references rather than a row in a
    supplier register, because this module is not a vendor CRM and the thing
    that matters financially is what the contract said about who it was with
    when somebody signed it.

    ``original_contract_value_ex_tax`` never changes after activation. What the
    developer now owes is that value plus every approved variation, derived on
    read — so a terminated contract still carries its commitment, and removing
    that money takes a signed negative variation rather than a status change.
    """

    __tablename__ = "construction_contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contract_number: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(24), nullable=False)

    vendor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    vendor_registration_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vendor_tax_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vendor_contact_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)

    #: A contractual fact, recorded because it is one. In this release the
    #: service refuses any value but the project's base currency: there is no
    #: FX anywhere in the platform, and a column that could hold a second
    #: denomination without a rate to convert it is a column that will one day
    #: be summed with the first.
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    original_contract_value_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    #: What the contract entitles the vendor to claim in advance. An
    #: entitlement, not cash: advance money exists only once an advance invoice
    #: is approved and a payment against it is confirmed.
    advance_entitlement_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.00")
    )
    retention_rate_fraction: Mapped[Decimal] = mapped_column(
        RATE, nullable=False, default=Decimal("0.000000")
    )
    #: Stated on the contract where one applies. Nothing derives tax from a
    #: country pack here: the sales tax rules govern what a buyer pays, and
    #: guessing a vendor's tax from them would be inventing a liability.
    tax_rate_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)

    payment_terms: Mapped[str | None] = mapped_column(String(500), nullable=True)

    planned_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CONTRACT_DRAFT)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "contract_number", name="uq_cx_contract_number"),
        UniqueConstraint("id", "project_id", name="cx_contract_project"),
        CheckConstraint(in_list("contract_type", CONTRACT_TYPES), name="type_ok"),
        CheckConstraint(in_list("status", CONTRACT_STATUSES), name="status_ok"),
        CheckConstraint("original_contract_value_ex_tax >= 0", name="value_nonneg"),
        CheckConstraint("advance_entitlement_amount >= 0", name="advance_nonneg"),
        CheckConstraint(
            "retention_rate_fraction >= 0 AND retention_rate_fraction <= 1",
            name="retention_range",
        ),
        CheckConstraint(
            "tax_rate_fraction IS NULL OR (tax_rate_fraction >= 0 AND tax_rate_fraction <= 1)",
            name="tax_range",
        ),
        CheckConstraint("length(vendor_name) > 0", name="vendor_present"),
        CheckConstraint("length(contract_number) > 0", name="number_present"),
        CheckConstraint(
            "planned_completion_date IS NULL OR planned_start_date IS NULL"
            " OR planned_completion_date >= planned_start_date",
            name="planned_order",
        ),
        CheckConstraint(
            "actual_completion_date IS NULL OR actual_start_date IS NULL"
            " OR actual_completion_date >= actual_start_date",
            name="actual_order",
        ),
        # Ending a contract early is a decision somebody has to explain.
        CheckConstraint(
            "status <> 'terminated' OR termination_reason IS NOT NULL",
            name="terminated_has_reason",
        ),
        CheckConstraint(
            "status <> 'cancelled' OR cancellation_reason IS NOT NULL",
            name="cancelled_has_reason",
        ),
        Index("ix_cx_contracts_project_status", "project_id", "status"),
    )


class ContractLine(Base):
    """One cost code's share of one contract's original value.

    The lines are the reason a contract can be compared with a budget at all: a
    single contract value tells you what was committed, but not against which
    authorisation. Their sum must equal the header exactly before activation —
    exactly, with no tolerance, because a tolerance is a rounding error somebody
    decided to stop noticing.
    """

    __tablename__ = "construction_contract_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    cost_code_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    original_amount_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["contract_id", "project_id"],
            ["construction_contracts.id", "construction_contracts.project_id"],
            name="contract",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("contract_id", "sequence", name="uq_cx_contract_line_seq"),
        CheckConstraint("original_amount_ex_tax >= 0", name="amount_nonneg"),
        CheckConstraint("sequence >= 1", name="sequence_positive"),
        CheckConstraint("length(description) > 0", name="description_present"),
        Index("ix_cx_contract_lines_contract", "contract_id"),
        Index("ix_cx_contract_lines_cost_code", "cost_code_id"),
    )


# --------------------------------------------------------------------------- #
# Variations
# --------------------------------------------------------------------------- #


class Variation(Base):
    """An approved change to what a contract commits the developer to.

    The header carries no total. A variation is worth the sum of its lines, and
    storing that sum beside them creates two answers to one question — which is
    how a change order comes to be worth one amount on the register and another
    in the contract it changed.
    """

    __tablename__ = "construction_variations"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    variation_number: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The site instruction, letter or change order this records. A reference,
    #: not a document store.
    instruction_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)

    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    cause: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    requested_date: Mapped[date] = mapped_column(Date, nullable=False)

    #: Signed. ``+14`` extends the contract's duration, ``-7`` accelerates it.
    #: Recorded because it is part of what was agreed; it does not move a
    #: completion date, a milestone or a forecast on its own — those are
    #: governed separately and a change order is not a scheduler.
    time_impact_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    funding_source: Mapped[str | None] = mapped_column(String(120), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=VARIATION_DRAFT)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
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
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawal_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["contract_id", "project_id"],
            ["construction_contracts.id", "construction_contracts.project_id"],
            name="contract",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("contract_id", "variation_number", name="uq_cx_variation_number"),
        UniqueConstraint("id", "project_id", name="cx_variation_project"),
        CheckConstraint(in_list("status", VARIATION_STATUSES), name="status_ok"),
        CheckConstraint("length(description) > 0", name="description_present"),
        CheckConstraint("length(variation_number) > 0", name="number_present"),
        CheckConstraint(
            "status <> 'rejected' OR rejection_reason IS NOT NULL", name="rejected_has_reason"
        ),
        CheckConstraint(
            "status <> 'withdrawn' OR withdrawal_reason IS NOT NULL", name="withdrawn_has_reason"
        ),
        Index("ix_cx_variations_contract_status", "contract_id", "status"),
        Index("ix_cx_variations_project_status", "project_id", "status"),
    )


class VariationLine(Base):
    """One cost code's signed change in value.

    The sign carries the meaning. ``+100,000`` is extra work and ``-40,000`` is
    omitted scope, and modelling a saving as its own record type would mean
    every total over this table had to know which type meant which direction.
    Zero is refused: a change worth nothing is not a change.
    """

    __tablename__ = "construction_variation_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    variation_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_code_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    value_delta_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["variation_id", "project_id"],
            ["construction_variations.id", "construction_variations.project_id"],
            name="variation",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("variation_id", "sequence", name="uq_cx_variation_line_seq"),
        CheckConstraint("value_delta_ex_tax <> 0", name="delta_nonzero"),
        CheckConstraint("sequence >= 1", name="sequence_positive"),
        CheckConstraint("length(description) > 0", name="description_present"),
        Index("ix_cx_variation_lines_variation", "variation_id"),
        Index("ix_cx_variation_lines_cost_code", "cost_code_id"),
    )


# --------------------------------------------------------------------------- #
# Certificates
# --------------------------------------------------------------------------- #


class Certificate(Base):
    """Work formally certified as done, and what that makes payable.

    This is the table the module exists to protect. Certified work is not a
    contractor's claim, not elapsed time, not a forecast, not an invoice and not
    a payment — it is somebody with authority stating that work to a value has
    been carried out, and it is the only thing in this module that becomes cost.

    The deduction columns are inputs somebody signed, not summaries: retention
    released, advance recovered and other deductions are decisions taken on this
    certificate. What they add up to — net due — is derived, as is retention
    held, as is everything cumulative. A ``previous_certified`` column would be a
    cache of a sum over immutable rows, and the first reversal would make it
    wrong.
    """

    __tablename__ = "construction_certificates"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    certificate_number: Mapped[str] = mapped_column(String(64), nullable=False)

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    certificate_date: Mapped[date] = mapped_column(Date, nullable=False)

    #: Retention previously held that this certificate gives back. Capped by
    #: the service at what has actually been retained and not yet released:
    #: money that was never held cannot be returned.
    retention_release_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.00")
    )
    #: Advance being recovered on this certificate. Capped at advance cash that
    #: has actually been paid and not yet recovered — an advance that never left
    #: the developer's bank cannot be taken back out of a valuation.
    advance_recovery_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.00")
    )
    other_deductions_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.00")
    )
    #: Stated on the certificate. Not derived from a country pack: the sales tax
    #: rules answer what a buyer pays, and applying them to a vendor valuation
    #: would be inventing a liability nobody agreed to.
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.00"))

    certifier_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CERTIFICATE_DRAFT)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reversal_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["contract_id", "project_id"],
            ["construction_contracts.id", "construction_contracts.project_id"],
            name="contract",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("contract_id", "certificate_number", name="uq_cx_cert_number"),
        UniqueConstraint("id", "project_id", name="cx_cert_project"),
        UniqueConstraint("id", "contract_id", "project_id", name="cx_cert_contract_project"),
        CheckConstraint(in_list("status", CERTIFICATE_STATUSES), name="status_ok"),
        CheckConstraint("period_end >= period_start", name="period_order"),
        CheckConstraint("retention_release_amount >= 0", name="release_nonneg"),
        CheckConstraint("advance_recovery_amount >= 0", name="recovery_nonneg"),
        # A negative deduction is an addition wearing a disguise, and it would
        # make every total over this column ambiguous. An extra sum owed is a
        # contractual transaction with its own record.
        CheckConstraint("other_deductions_amount >= 0", name="deduction_nonneg"),
        CheckConstraint("tax_amount >= 0", name="tax_nonneg"),
        CheckConstraint("length(certificate_number) > 0", name="number_present"),
        CheckConstraint(
            "status <> 'rejected' OR rejection_reason IS NOT NULL", name="rejected_has_reason"
        ),
        CheckConstraint(
            "status <> 'reversed'"
            " OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL"
            " AND reversal_reason IS NOT NULL)",
            name="reversed_shape",
        ),
        CheckConstraint(
            "status <> 'certified'"
            " OR (certified_at IS NOT NULL AND certified_by_user_id IS NOT NULL)",
            name="certified_shape",
        ),
        Index("ix_cx_certs_contract_status", "contract_id", "status"),
        Index("ix_cx_certs_project_status", "project_id", "status"),
        Index("ix_cx_certs_certified_at", "certified_at"),
    )


class CertificateLine(Base):
    """The value of work certified against one cost code on one certificate.

    Gross for the period and never cumulative, so a certificate reads as what
    was done in its own window. What has been certified to date is the sum of
    the standing lines, which means a reversal simply stops contributing rather
    than requiring every later certificate to be restated.
    """

    __tablename__ = "construction_certificate_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    certificate_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    cost_code_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    current_work_value_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["certificate_id", "project_id"],
            ["construction_certificates.id", "construction_certificates.project_id"],
            name="certificate",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("certificate_id", "cost_code_id", name="uq_cx_cert_line"),
        CheckConstraint("current_work_value_ex_tax >= 0", name="work_nonneg"),
        Index("ix_cx_cert_lines_certificate", "certificate_id"),
        Index("ix_cx_cert_lines_cost_code", "cost_code_id"),
    )


# --------------------------------------------------------------------------- #
# Invoices
# --------------------------------------------------------------------------- #


class Invoice(Base):
    """A claim that has become an approved liability — or is still arguing.

    An invoice is not a certificate and not a payment. A progress invoice may
    only claim what a certificate authorised, an advance invoice may only claim
    what the contract entitled, and neither is cash until a payment against it
    is confirmed by somebody other than the person who recorded it.

    ``disputed`` deliberately keeps standing as an obligation. A dispute is an
    argument about an amount, not a reduction of it; subtracting it would make
    what the developer owes fall the moment somebody objected.
    """

    __tablename__ = "construction_invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: The certificate this invoice claims against. Null only for an advance,
    #: which is claimed before any work exists to certify.
    certificate_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    invoice_type: Mapped[str] = mapped_column(String(24), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    amount_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.00"))

    accounting_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=INVOICE_RECORDED)
    dispute_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    disputed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disputed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    dispute_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispute_resolution_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    void_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["contract_id", "project_id"],
            ["construction_contracts.id", "construction_contracts.project_id"],
            name="contract",
            ondelete="RESTRICT",
        ),
        # Three columns, so an invoice cannot name a certificate from one
        # contract while claiming to belong to another.
        ForeignKeyConstraint(
            ["certificate_id", "contract_id", "project_id"],
            [
                "construction_certificates.id",
                "construction_certificates.contract_id",
                "construction_certificates.project_id",
            ],
            name="certificate",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("contract_id", "invoice_number", name="uq_cx_invoice_number"),
        UniqueConstraint("id", "project_id", name="cx_invoice_project"),
        UniqueConstraint("id", "contract_id", "project_id", name="cx_invoice_contract_project"),
        CheckConstraint(in_list("invoice_type", INVOICE_TYPES), name="type_ok"),
        CheckConstraint(in_list("status", INVOICE_STATUSES), name="status_ok"),
        CheckConstraint("amount_ex_tax >= 0", name="amount_nonneg"),
        CheckConstraint("tax_amount >= 0", name="tax_nonneg"),
        CheckConstraint("length(invoice_number) > 0", name="number_present"),
        CheckConstraint("due_date IS NULL OR due_date >= invoice_date", name="due_order"),
        # Everything but an advance claims against certified work — "other"
        # included. An invoice type with no authorisation ceiling is a way to
        # make an approved liability out of nothing, and the module rests on an
        # invoice fitting inside what authorised it. A liability that genuinely
        # sits outside certified work needs its own authorisation model, not an
        # unrestricted escape hatch.
        CheckConstraint(
            "invoice_type = 'advance' OR certificate_id IS NOT NULL",
            name="claim_has_certificate",
        ),
        CheckConstraint(
            "invoice_type <> 'advance' OR certificate_id IS NULL",
            name="advance_has_no_certificate",
        ),
        CheckConstraint(
            "status <> 'disputed' OR dispute_reason IS NOT NULL", name="disputed_has_reason"
        ),
        CheckConstraint(
            "status <> 'voided'"
            " OR (voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL"
            " AND void_reason IS NOT NULL)",
            name="voided_shape",
        ),
        CheckConstraint(
            "status <> 'approved' OR (approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)",
            name="approved_shape",
        ),
        Index("ix_cx_invoices_contract_status", "contract_id", "status"),
        Index("ix_cx_invoices_project_status", "project_id", "status"),
        Index("ix_cx_invoices_due_date", "due_date"),
        Index("ix_cx_invoices_certificate", "certificate_id"),
    )


# --------------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------------- #


class Payment(Base):
    """Money leaving the project, and the two people who agreed it should.

    The same discipline collections applies to money arriving, in the other
    direction: recording a payment is not paying it. A recorded payment is
    Finance preparing a disbursement; only a confirmed, unreversed payment is
    cash that has left, and the person who confirms it is never the person who
    recorded it.

    Unlike a buyer receipt, a construction payment may not carry an unapplied
    balance. Cash arriving with no obligation named is a real operational state
    somebody must report; cash leaving with no obligation named is a payment
    nobody can explain, so confirmation refuses until the allocations are exact.
    """

    __tablename__ = "construction_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    payment_reference: Mapped[str] = mapped_column(String(64), nullable=False)

    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: When the bank actually moved it, where that differs from the instruction
    #: date. Recorded, never derived.
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )

    bank_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    proof_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=PAYMENT_RECORDED)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
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
    reversal_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["contract_id", "project_id"],
            ["construction_contracts.id", "construction_contracts.project_id"],
            name="contract",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "payment_reference", name="uq_cx_payment_reference"),
        UniqueConstraint("id", "project_id", name="cx_payment_project"),
        UniqueConstraint("id", "contract_id", "project_id", name="cx_payment_contract_project"),
        CheckConstraint(in_list("status", PAYMENT_STATUSES), name="status_ok"),
        # Money leaving is its own record and never a negative row in another
        # one. A signed amount would make every total over this table ambiguous.
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("length(payment_reference) > 0", name="reference_present"),
        CheckConstraint("value_date IS NULL OR value_date >= payment_date", name="value_order"),
        CheckConstraint(
            "status <> 'reversed'"
            " OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL"
            " AND reversal_reason IS NOT NULL)",
            name="reversed_shape",
        ),
        # Cash leaving needs the second person's name on the row, not only in
        # the service that wrote it.
        CheckConstraint(
            "status <> 'confirmed'"
            " OR (confirmed_at IS NOT NULL AND confirmed_by_user_id IS NOT NULL)",
            name="confirmed_shape",
        ),
        Index("ix_cx_payments_contract_status", "contract_id", "status"),
        Index("ix_cx_payments_project_status", "project_id", "status"),
        Index("ix_cx_payments_payment_date", "payment_date"),
    )


class PaymentAllocation(Base):
    """Which invoice one payment settled, and by how much.

    Applying cash is a separate decision from moving it, so it is a separate
    row. The rows survive a reversal untouched: they are the evidence of what
    the reversed payment had been applied against, and deleting them would erase
    the reason the reversal mattered.
    """

    __tablename__ = "construction_payment_allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: Carried so the composite keys below can prove both sides belong to one
    #: contract, rather than trusting two independent lookups to agree.
    contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    payment_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

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
            ["payment_id", "contract_id", "project_id"],
            [
                "construction_payments.id",
                "construction_payments.contract_id",
                "construction_payments.project_id",
            ],
            name="payment",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["invoice_id", "contract_id", "project_id"],
            [
                "construction_invoices.id",
                "construction_invoices.contract_id",
                "construction_invoices.project_id",
            ],
            name="invoice",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("payment_id", "invoice_id", name="uq_cx_alloc_pair"),
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_cx_allocs_payment", "payment_id"),
        Index("ix_cx_allocs_invoice", "invoice_id"),
    )


# --------------------------------------------------------------------------- #
# Milestones
# --------------------------------------------------------------------------- #


class Milestone(Base):
    """A point in the build that somebody has to certify has been reached.

    Four dates, and the distance between them is the control this table exists
    to keep. ``planned_date`` is what was agreed, ``forecast_date`` is what the
    team now expects, ``actual_achieved_date`` is what site says happened, and
    ``certified_date`` is what somebody with authority formally certified. Only
    the last of those makes a buyer's instalment fall due.

    ``code`` is immutable once created. Payment plans already reference a
    milestone by its code in ``trigger_reference`` — a stable handle rather than
    a foreign key, so that a contractual schedule written before this module
    existed keeps working — and renaming a code would silently detach a live
    plan from the event that triggers it.
    """

    __tablename__ = "construction_milestones"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    milestone_type: Mapped[str] = mapped_column(String(16), nullable=False)

    phase_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    building_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    forecast_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_achieved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    certified_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: An exact fraction of one, like every other rate in the platform. The
    #: browser prints 65%; the payload never carries 65.
    progress_fraction: Mapped[Decimal] = mapped_column(
        RATE, nullable=False, default=Decimal("0.000000")
    )
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: The progress certificate that evidences this milestone, where one does.
    #: Its presence is why a certificate cannot be reversed out from under a
    #: certified milestone that a buyer's schedule already depends on.
    linked_certificate_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=MILESTONE_PLANNED)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    achieved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["building_id", "project_id"],
            ["buildings.id", "buildings.project_id"],
            name="building",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["linked_certificate_id", "project_id"],
            ["construction_certificates.id", "construction_certificates.project_id"],
            name="certificate",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "code", name="uq_cx_milestone_code"),
        UniqueConstraint("id", "project_id", name="cx_milestone_project"),
        CheckConstraint(in_list("milestone_type", MILESTONE_TYPES), name="type_ok"),
        CheckConstraint(in_list("status", MILESTONE_STATUSES), name="status_ok"),
        CheckConstraint("length(code) > 0", name="code_present"),
        CheckConstraint("length(name) > 0", name="name_present"),
        CheckConstraint("progress_fraction >= 0 AND progress_fraction <= 1", name="progress_range"),
        # Certification is a state, a date and an actor together. A certified
        # date on a milestone nobody certified is exactly the shape of the
        # mistake this module exists to prevent.
        # Certification is a state, a date, a time and a person together. The
        # earlier version checked only the date, which let a raw insert claim a
        # certification nobody signed — and a certified milestone is what makes
        # a buyer's instalment fall due.
        #
        # The scope check that used to sit here was a tautology: "building IS
        # NULL OR phase IS NULL OR building IS NOT NULL" is true for every row.
        # Whether a building belongs to the named phase spans two other tables
        # and is proved in the service, so a constraint that looked like it
        # covered it was worse than no constraint at all.
        CheckConstraint(
            "(status = 'certified')"
            " = (certified_date IS NOT NULL AND certified_at IS NOT NULL"
            " AND certified_by_user_id IS NOT NULL)",
            name="certified_shape",
        ),
        CheckConstraint(
            "status <> 'cancelled'"
            " OR (cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL)",
            name="cancelled_shape",
        ),
        CheckConstraint(
            "status <> 'achieved'"
            " OR (actual_achieved_date IS NOT NULL AND achieved_by_user_id IS NOT NULL)",
            name="achieved_shape",
        ),
        Index("ix_cx_milestones_project_status", "project_id", "status"),
        Index("ix_cx_milestones_planned_date", "planned_date"),
        Index("ix_cx_milestones_phase", "phase_id"),
        Index("ix_cx_milestones_building", "building_id"),
    )


class MilestoneDependency(Base):
    """One milestone waits on another. Visibility, not a scheduler.

    Nothing in this module computes a critical path, moves a date because a
    predecessor slipped, or refuses certification because a dependency is
    outstanding. It records what the programme says depends on what, so a late
    milestone can be read with its consequences beside it.
    """

    __tablename__ = "construction_milestone_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    milestone_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    depends_on_milestone_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["milestone_id", "project_id"],
            ["construction_milestones.id", "construction_milestones.project_id"],
            name="milestone",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["depends_on_milestone_id", "project_id"],
            ["construction_milestones.id", "construction_milestones.project_id"],
            name="depends_on",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("milestone_id", "depends_on_milestone_id", name="uq_cx_dep_pair"),
        CheckConstraint("milestone_id <> depends_on_milestone_id", name="not_self"),
        Index("ix_cx_deps_milestone", "milestone_id"),
        Index("ix_cx_deps_depends_on", "depends_on_milestone_id"),
    )


# --------------------------------------------------------------------------- #
# Forecast
# --------------------------------------------------------------------------- #


class ForecastVersion(Base):
    """What Finance now expects the construction to cost, as of a stated date.

    Two things make this a governed snapshot rather than a number in a
    spreadsheet. It names the budget version it is measured against, so its
    variance is against a stated authorisation rather than whatever is current
    when somebody opens the screen. And it carries an ``as_of_date``, so the
    certified work inside its estimate is the work certified by that cutoff —
    which is what makes a superseded forecast still reproducible a year later,
    instead of quietly re-deriving itself from today's certificates.
    """

    __tablename__ = "construction_forecast_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    #: The authorisation this forecast is measured against. Variance at
    #: completion is meaningless without it.
    budget_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=FORECAST_DRAFT)
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    change_reason: Mapped[str] = mapped_column(String(1000), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
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
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["budget_version_id", "project_id"],
            ["construction_budget_versions.id", "construction_budget_versions.project_id"],
            name="budget",
            ondelete="RESTRICT",
        ),
        # Same proof as the budget's lineage, for the same reason.
        ForeignKeyConstraint(
            ["source_version_id", "project_id"],
            [
                "construction_forecast_versions.id",
                "construction_forecast_versions.project_id",
            ],
            name="source_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="cx_forecast_project"),
        UniqueConstraint("project_id", "version_number", name="uq_cx_forecast_number"),
        CheckConstraint(in_list("status", FORECAST_STATUSES), name="status_ok"),
        CheckConstraint("version_number >= 1", name="number_positive"),
        CheckConstraint("length(change_reason) > 0", name="reason_present"),
        CheckConstraint(
            "status <> 'rejected'"
            " OR (rejected_at IS NOT NULL AND rejected_by_user_id IS NOT NULL"
            " AND rejection_reason IS NOT NULL)",
            name="rejected_shape",
        ),
        CheckConstraint(
            "status NOT IN ('active', 'superseded')"
            " OR (activated_at IS NOT NULL AND activated_by_user_id IS NOT NULL)",
            name="activated_shape",
        ),
        CheckConstraint(
            "status NOT IN ('approved', 'active', 'superseded')"
            " OR (approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)",
            name="approved_shape",
        ),
        Index(
            "uq_cx_forecasts_one_active",
            "project_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_cx_forecasts_one_open",
            "project_id",
            unique=True,
            postgresql_where=text("status IN ('draft', 'submitted', 'approved')"),
        ),
        Index("ix_cx_forecasts_project_status", "project_id", "status"),
    )


class ForecastLine(Base):
    """What one cost code still has left to spend, in Finance's judgement.

    ``forecast_remaining_amount_ex_tax`` is an explicit input and never a
    subtraction of certified work from budget. Deriving it that way would make
    the forecast a restatement of the budget, and a forecast that cannot
    disagree with the budget cannot warn anybody about it.

    An explicit zero is a statement — nothing left to spend here. A missing line
    is not zero, and submission refuses until every governed cost code has one:
    the difference between "we expect no further cost" and "nobody looked" is
    the difference between a forecast and a guess.
    """

    __tablename__ = "construction_forecast_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    forecast_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    cost_code_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    forecast_remaining_amount_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["forecast_version_id", "project_id"],
            ["construction_forecast_versions.id", "construction_forecast_versions.project_id"],
            name="forecast",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("forecast_version_id", "cost_code_id", name="uq_cx_forecast_line"),
        CheckConstraint("forecast_remaining_amount_ex_tax >= 0", name="remaining_nonneg"),
        Index("ix_cx_forecast_lines_version", "forecast_version_id"),
    )
