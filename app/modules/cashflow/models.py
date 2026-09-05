"""Cashflow: when money arrives, when it leaves, and how much of it is usable.

Cashflow **consolidates**; it does not restate. Payment plans own what a buyer is
scheduled to pay, collections owns what actually arrived, construction owns what
was paid to contractors, sales owns the contract. None of those rows is copied
here. What lives in this module is the cash the rest of the platform has no
record of — a consultant's fee, an equity drawdown, the escrow that makes
received cash unusable — plus the governed statement of *when* Finance expects
the rest of it to move.

Seven tables, and the division between them is the point.

**The forecast version** is a governed historical statement, on the same ladder
as a construction forecast: prepared, submitted, approved, activated, superseded.
It pins the construction forecast it was measured against and freezes the buyer
schedule it was built on, because a forecast that silently re-reads its sources
is not reproducible and cannot be the thing anybody approved.

**Forecast lines** carry only the future judgements no transaction module
generates: what Finance expects to spend and when, and what it expects to collect
from inventory nobody has contracted yet. Contracted customer cash comes from the
snapshot; actual cash comes from the transaction modules. Neither is retyped
here.

**The customer schedule snapshot** is provenance, not a second payment plan. It
records which installments of which plan version the forecast used and which date
it chose for each, so the version can be re-derived in a year without asking what
the schedule looks like now.

**Development and financing movements** are the cash this module owns outright,
because nothing else in the platform records it. Both follow the discipline
collections and construction already use for money: recording is not paying, a
second person confirms, and a correction is a reversal rather than an edit.

**Restrictions and releases** answer the question a total cash balance cannot:
how much of this money may we actually spend? A restriction attaches to a
confirmed buyer receipt and takes cash out of the usable pool without taking it
out of the bank. A release moves it back. Neither creates or destroys project
cash — they move availability, and the reporting keeps the two balances apart
because a developer who pays a contractor out of escrowed buyer money has a
problem no total will show.
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

#: The governed ladder, identical to the construction forecast's. One vocabulary
#: for "a financial statement somebody approved" across the platform: a reader
#: who has learned what *superseded* means on a budget should not have to learn
#: it again here.
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

#: Being prepared, checked, or waiting to be put in force. One per project.
FORECAST_OPEN = frozenset({FORECAST_DRAFT, FORECAST_SUBMITTED, FORECAST_APPROVED})
#: Whose sources may still be re-pinned underneath it.
#:
#: Deliberately not ``FORECAST_OPEN``. "Occupies the project's one open slot" and
#: "may still be changed" are different questions, and an approved version
#: answers them differently: it is open, because a second forecast alongside it
#: would be a second answer to one question — and it is not changeable, because
#: the CFO approved the months a particular buyer schedule produced. Refreshing
#: that schedule under a recorded approval changes what was approved without
#: anybody approving it again.
FORECAST_REFRESHABLE = frozenset({FORECAST_DRAFT, FORECAST_SUBMITTED})
#: Governed and no longer editable — what a historical read may draw on.
FORECAST_GOVERNED = frozenset({FORECAST_ACTIVE, FORECAST_SUPERSEDED})

#: The lifecycle every cash movement in this module follows, matching collections
#: receipts and construction payments exactly. Recording is a claim; confirming
#: is cash; reversing withdraws it from the current position without erasing that
#: it was once standing.
MOVEMENT_STATUSES = ("recorded", "confirmed", "reversed")
MOVEMENT_RECORDED = "recorded"
MOVEMENT_CONFIRMED = "confirmed"
MOVEMENT_REVERSED = "reversed"

#: Project cash the platform has no other record of. Deliberately without a
#: construction entry: construction payments are PR-MVP-09's, and a category
#: here that could hold one would let the same disbursement be counted twice —
#: once by the module that governs it and once by somebody retyping it.
DEVELOPMENT_CATEGORIES = (
    "land_acquisition",
    "land_fees",
    "design",
    "consultants",
    "permits",
    "insurance",
    "developer_overhead",
    "marketing",
    "commissions",
    "tax",
    "handover",
    "other",
)

#: Financing cash, in. ``guarantee_cash_release`` is cash collateral coming back
#: and never a guarantee being cancelled: a non-cash instrument has no place in a
#: cash ledger.
FINANCING_INFLOW_TYPES = (
    "equity_contribution",
    "debt_drawdown",
    "guarantee_cash_release",
)
#: Financing cash, out.
FINANCING_OUTFLOW_TYPES = (
    "equity_distribution",
    "debt_fee",
    "interest_payment",
    "principal_repayment",
    "guarantee_cash_posting",
)
FINANCING_TYPES = FINANCING_INFLOW_TYPES + FINANCING_OUTFLOW_TYPES

#: The two equity movements the investor IRR is built from. Named here so the
#: sign transformation in the calculator has one place to read them from.
EQUITY_CONTRIBUTION = "equity_contribution"
EQUITY_DISTRIBUTION = "equity_distribution"

FLOW_DIRECTIONS = ("inflow", "outflow")
FLOW_INFLOW = "inflow"
FLOW_OUTFLOW = "outflow"

#: Where a forecast line's amount came from. A small closed set: contracted
#: customer cash is generated from the frozen snapshot and actual cash comes from
#: the transaction modules, so neither has a source kind here.
FORECAST_SOURCE_KINDS = (
    "unsold_customer",
    "development",
    "construction",
    "financing",
)
SOURCE_UNSOLD_CUSTOMER = "unsold_customer"
SOURCE_DEVELOPMENT = "development"
SOURCE_CONSTRUCTION = "construction"
SOURCE_FINANCING = "financing"

#: The category axis every monthly figure is reported on. One vocabulary across
#: forecast lines, actual movements and the monthly report, so a forecast row and
#: the actual that lands against it can be compared without translation.
CATEGORY_CUSTOMER_COLLECTION = "customer_collection"
CATEGORY_CONSTRUCTION = "construction"
FORECAST_LINE_CATEGORIES = (
    CATEGORY_CUSTOMER_COLLECTION,
    CATEGORY_CONSTRUCTION,
    *DEVELOPMENT_CATEGORIES,
    *FINANCING_TYPES,
)


def _financing_direction_rule() -> str:
    """The SQL that keeps a financing movement's direction honest.

    An equity contribution is cash in and a distribution is cash out; those are
    facts about the transaction, not choices an operator makes on a form, so the
    database holds them rather than trusting six call sites to agree.
    """
    inflows = ", ".join(f"'{value}'" for value in FINANCING_INFLOW_TYPES)
    outflows = ", ".join(f"'{value}'" for value in FINANCING_OUTFLOW_TYPES)
    return (
        f"(movement_type IN ({inflows}) AND flow_direction = 'inflow')"
        f" OR (movement_type IN ({outflows}) AND flow_direction = 'outflow')"
    )


def _forecast_line_shape_rule() -> str:
    """Which category and scope each forecast source kind may carry.

    A construction line without a cost code cannot be reconciled against the
    construction forecast it is supposed to schedule, and a development line
    carrying one claims a precision the category set does not have. Both are
    refused here rather than in a validator somebody can forget to call.
    """
    development = ", ".join(f"'{value}'" for value in DEVELOPMENT_CATEGORIES)
    financing = ", ".join(f"'{value}'" for value in FINANCING_TYPES)
    return (
        "(source_kind = 'construction' AND category = 'construction'"
        " AND construction_cost_code_id IS NOT NULL AND flow_direction = 'outflow')"
        f" OR (source_kind = 'development' AND category IN ({development})"
        " AND construction_cost_code_id IS NULL AND flow_direction = 'outflow')"
        " OR (source_kind = 'unsold_customer' AND category = 'customer_collection'"
        " AND construction_cost_code_id IS NULL AND flow_direction = 'inflow')"
        f" OR (source_kind = 'financing' AND category IN ({financing})"
        " AND construction_cost_code_id IS NULL)"
    )


#: A month column holds the first day of the month it names. Storing 15 March and
#: 1 March in the same column means two rows for one period that no GROUP BY will
#: ever put together.
_FIRST_OF_MONTH = "EXTRACT(DAY FROM {column}) = 1"


# --------------------------------------------------------------------------- #
# Forecast version
# --------------------------------------------------------------------------- #


class CashflowForecastVersion(Base):
    """A governed statement of expected cash, as at a stated date.

    ``as_of_date`` is the cutoff the version was built at, and it is what makes
    the version reproducible: an actual transaction confirmed after it is not
    part of what Finance knew, however early its business date. The horizon
    (``forecast_start_month`` to ``forecast_end_month``) is separate and is about
    which months the statement covers.

    Two pins, both deliberate. ``construction_forecast_version_id`` names the
    construction forecast whose remaining cost this version schedules, so a later
    construction forecast makes a draft stale rather than silently rewriting it.
    ``source_version_id`` names the cashflow forecast this one was prepared from,
    which is provenance rather than inheritance — nothing is copied through it.

    ``opening_unrestricted_cash`` and ``opening_restricted_cash`` are stated, not
    derived. The platform's cash history begins where somebody says it begins,
    and inferring an opening balance from transactions that predate the system
    would be inventing one.
    """

    __tablename__ = "cashflow_forecast_versions"

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

    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_start_month: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_end_month: Mapped[date] = mapped_column(Date, nullable=False)

    opening_unrestricted_cash: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    opening_restricted_cash: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    #: Per period, never per annum. Converting an annual rate to a monthly one
    #: is a compounding assumption, and a service that made it silently would be
    #: choosing the project's discount rate on Finance's behalf.
    discount_rate_per_period: Mapped[Decimal] = mapped_column(RATE, nullable=False)

    source_version_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    construction_forecast_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )

    change_reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=FORECAST_DRAFT)

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
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Provenance stays inside the project. A bare UUID would let a version
        # cite one project's forecast from another's and nothing would object.
        ForeignKeyConstraint(
            ["source_version_id", "project_id"],
            ["cashflow_forecast_versions.id", "cashflow_forecast_versions.project_id"],
            name="source_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["construction_forecast_version_id", "project_id"],
            ["construction_forecast_versions.id", "construction_forecast_versions.project_id"],
            name="construction_forecast",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="cf_forecast_project"),
        UniqueConstraint("project_id", "version_number", name="uq_cf_forecast_number"),
        CheckConstraint(in_list("status", FORECAST_STATUSES), name="status_ok"),
        CheckConstraint("version_number >= 1", name="number_positive"),
        CheckConstraint("length(change_reason) > 0", name="reason_present"),
        CheckConstraint("opening_unrestricted_cash >= 0", name="opening_unrestricted_nonneg"),
        CheckConstraint("opening_restricted_cash >= 0", name="opening_restricted_nonneg"),
        CheckConstraint("discount_rate_per_period >= 0", name="discount_rate_nonneg"),
        CheckConstraint("forecast_end_month >= forecast_start_month", name="horizon_ordered"),
        CheckConstraint(
            _FIRST_OF_MONTH.format(column="forecast_start_month"), name="start_canonical"
        ),
        CheckConstraint(_FIRST_OF_MONTH.format(column="forecast_end_month"), name="end_canonical"),
        CheckConstraint(
            "source_version_id IS NULL OR source_version_id <> id", name="source_not_self"
        ),
        CheckConstraint(
            "status <> 'rejected'"
            " OR (rejected_at IS NOT NULL AND rejected_by_user_id IS NOT NULL"
            " AND rejection_reason IS NOT NULL)",
            name="rejected_shape",
        ),
        CheckConstraint(
            "status NOT IN ('approved', 'active', 'superseded')"
            " OR (approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)",
            name="approved_shape",
        ),
        CheckConstraint(
            "status NOT IN ('active', 'superseded')"
            " OR (activated_at IS NOT NULL AND activated_by_user_id IS NOT NULL)",
            name="activated_shape",
        ),
        Index(
            "uq_cf_forecasts_one_active",
            "project_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_cf_forecasts_one_open",
            "project_id",
            unique=True,
            postgresql_where=text("status IN ('draft', 'submitted', 'approved')"),
        ),
        Index("ix_cf_forecasts_project_status", "project_id", "status"),
    )


class CashflowForecastLine(Base):
    """One month's expected movement, for a judgement nothing else generates.

    Deliberately narrow. Contracted customer cash comes from the frozen schedule
    snapshot, and every actual belongs to the module that recorded it — so what
    is left for a human to type is future spend, future financing, and expected
    sales of inventory nobody has contracted yet. A forecast line for a contract
    that already exists would be a second opinion about a governed fact.

    ``amount`` is unsigned and ``flow_direction`` carries the sense, so a sum
    over the column is never quietly cancelled by a negative row somebody entered
    to represent a correction.
    """

    __tablename__ = "cashflow_forecast_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    forecast_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    flow_direction: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    phase_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    construction_cost_code_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )

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
            ["cashflow_forecast_versions.id", "cashflow_forecast_versions.project_id"],
            name="version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["construction_cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="cf_forecast_line_project"),
        CheckConstraint(in_list("flow_direction", FLOW_DIRECTIONS), name="direction_ok"),
        CheckConstraint(in_list("category", FORECAST_LINE_CATEGORIES), name="category_ok"),
        CheckConstraint(in_list("source_kind", FORECAST_SOURCE_KINDS), name="source_kind_ok"),
        # An explicit zero is a statement: nothing expected this month. A
        # negative is a direction wearing the wrong column's clothes.
        CheckConstraint("amount >= 0", name="amount_nonneg"),
        CheckConstraint(_FIRST_OF_MONTH.format(column="period_month"), name="month_canonical"),
        CheckConstraint(_forecast_line_shape_rule(), name="source_shape_ok"),
        Index("ix_cf_forecast_lines_version_month", "forecast_version_id", "period_month"),
        Index("ix_cf_forecast_lines_version_source", "forecast_version_id", "source_kind"),
        Index("ix_cf_forecast_lines_cost_code", "forecast_version_id", "construction_cost_code_id"),
    )


class CashflowCustomerScheduleSnapshot(Base):
    """Which buyer instalments a forecast was built on, and the date it chose.

    Provenance, not a second payment plan. The amounts and dates are copied so
    the version can be re-derived in a year, and nothing else is: no buyer name,
    no contact detail, no term. A snapshot that grew into a mirror of the payment
    plan would become a second source of truth about what a buyer owes, and the
    two would eventually disagree.

    ``chosen_forecast_date`` records which of the three dates this forecast used
    and is the answer to "why is this instalment in April?" — a question the raw
    dates alone cannot settle, because the rule for choosing between them is a
    judgement the version made at preparation time.
    """

    __tablename__ = "cashflow_customer_schedule_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    forecast_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    payment_plan_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    installment_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sale_contract_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    contractual_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    forecast_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    chosen_forecast_date: Mapped[date] = mapped_column(Date, nullable=False)

    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_status: Mapped[str] = mapped_column(String(24), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["forecast_version_id", "project_id"],
            ["cashflow_forecast_versions.id", "cashflow_forecast_versions.project_id"],
            name="version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["payment_plan_version_id", "project_id"],
            ["payment_plan_versions.id", "payment_plan_versions.project_id"],
            name="plan_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["installment_id", "project_id"],
            ["payment_plan_installments.id", "payment_plan_installments.project_id"],
            name="installment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "forecast_version_id", "installment_id", name="uq_cf_snapshot_installment"
        ),
        CheckConstraint("amount >= 0", name="amount_nonneg"),
        Index("ix_cf_snapshots_version_date", "forecast_version_id", "chosen_forecast_date"),
        Index("ix_cf_snapshots_sale", "forecast_version_id", "sale_contract_id"),
    )


# --------------------------------------------------------------------------- #
# Cash this module owns
# --------------------------------------------------------------------------- #


class CashflowDevelopmentMovement(Base):
    """Project cash leaving for something no other module records.

    Consultants, permits, insurance, marketing, overhead — real disbursements
    with no contract, certificate or buyer behind them in this platform. The
    category set has no construction entry on purpose: construction cash belongs
    to PR-MVP-09, and an escape hatch here would let one payment be counted by
    both modules with nothing to detect it.

    Recorded is not paid. A recorded movement is Finance preparing a payment; a
    confirmed one is cash that has left, and the person who confirms it is never
    the person who recorded it.
    """

    __tablename__ = "cashflow_development_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    #: The project-scoped human reference, ``DEV-000001``.
    movement_reference: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: When the bank actually moved it, where that differs from the instruction.
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: A phase where the spend genuinely belongs to one. Optional, because most
    #: development cash is the project's and inventing an allocation to make a
    #: phase filter tidy would be inventing a number.
    phase_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    counterparty_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoice_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=MOVEMENT_RECORDED)

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
    reversal_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "movement_reference", name="uq_cf_dev_reference"),
        UniqueConstraint("id", "project_id", name="cf_dev_movement_project"),
        CheckConstraint(in_list("category", DEVELOPMENT_CATEGORIES), name="category_ok"),
        CheckConstraint(in_list("status", MOVEMENT_STATUSES), name="status_ok"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "status <> 'confirmed'"
            " OR (confirmed_at IS NOT NULL AND confirmed_by_user_id IS NOT NULL)",
            name="confirmed_has_actor",
        ),
        CheckConstraint(
            "status <> 'reversed'"
            " OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL"
            " AND reversal_reason IS NOT NULL)",
            name="reversed_has_reason",
        ),
        # A second person, by identifier. One user holding two roles is still one
        # pair of eyes, which a role comparison would not notice.
        CheckConstraint(
            "confirmed_by_user_id IS NULL OR confirmed_by_user_id <> recorded_by_user_id",
            name="confirmer_is_not_recorder",
        ),
        Index("ix_cf_dev_movements_project_status", "project_id", "status"),
        Index("ix_cf_dev_movements_date", "project_id", "movement_date"),
    )


class CashflowFinancingMovement(Base):
    """Equity and debt cash, and only where cash actually moves.

    A facility signed is not a drawdown; a guarantee issued is not cash posted.
    This table holds transactions, so an instrument that never moved money has no
    row here and appears in no cash position. That boundary is what keeps this a
    cash ledger rather than the beginning of a treasury system.
    """

    __tablename__ = "cashflow_financing_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    #: The project-scoped human reference, ``FIN-000001``.
    movement_reference: Mapped[str] = mapped_column(String(32), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Derived from the type at write time and stored, so a direction can never
    #: be read one way by a report and another by a control.
    flow_direction: Mapped[str] = mapped_column(String(16), nullable=False)

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    counterparty_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    facility_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=MOVEMENT_RECORDED)

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
    reversal_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "movement_reference", name="uq_cf_fin_reference"),
        UniqueConstraint("id", "project_id", name="cf_fin_movement_project"),
        CheckConstraint(in_list("movement_type", FINANCING_TYPES), name="movement_type_ok"),
        CheckConstraint(in_list("flow_direction", FLOW_DIRECTIONS), name="direction_ok"),
        CheckConstraint(_financing_direction_rule(), name="direction_matches_type"),
        CheckConstraint(in_list("status", MOVEMENT_STATUSES), name="status_ok"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "status <> 'confirmed'"
            " OR (confirmed_at IS NOT NULL AND confirmed_by_user_id IS NOT NULL)",
            name="confirmed_has_actor",
        ),
        CheckConstraint(
            "status <> 'reversed'"
            " OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL"
            " AND reversal_reason IS NOT NULL)",
            name="reversed_has_reason",
        ),
        CheckConstraint(
            "confirmed_by_user_id IS NULL OR confirmed_by_user_id <> recorded_by_user_id",
            name="confirmer_is_not_recorder",
        ),
        Index("ix_cf_fin_movements_project_status", "project_id", "status"),
        Index("ix_cf_fin_movements_date", "project_id", "movement_date"),
        Index("ix_cf_fin_movements_type", "project_id", "movement_type"),
    )


# --------------------------------------------------------------------------- #
# Restricted cash
# --------------------------------------------------------------------------- #


class CashflowReceiptRestriction(Base):
    """How much of one confirmed buyer receipt the developer may not yet spend.

    Attached to the receipt rather than held as a project-level balance, because
    "40% of buyer cash is escrowed" is a rule and this is the record of it being
    applied to a specific transfer — which is what an auditor asks for and what
    lets the release name what it is releasing.

    The restriction never moves cash. Total project cash is unchanged by it; what
    changes is how much of that total is available, and the reporting keeps the
    two apart because a developer paying a contractor out of escrowed buyer money
    has a problem no total will show.
    """

    __tablename__ = "cashflow_receipt_restrictions"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    receipt_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    restricted_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=MOVEMENT_RECORDED)

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
    reversal_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["receipt_id", "project_id"],
            ["collection_receipts.id", "collection_receipts.project_id"],
            name="receipt",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="cf_restriction_project"),
        CheckConstraint(in_list("status", MOVEMENT_STATUSES), name="status_ok"),
        # Zero is allowed and means "reviewed, nothing restricted" — a different
        # statement from no record at all. Negative is not a statement.
        CheckConstraint("restricted_amount >= 0", name="amount_nonneg"),
        CheckConstraint("length(reason) > 0", name="reason_present"),
        CheckConstraint(
            "status <> 'confirmed'"
            " OR (confirmed_at IS NOT NULL AND confirmed_by_user_id IS NOT NULL)",
            name="confirmed_has_actor",
        ),
        CheckConstraint(
            "status <> 'reversed'"
            " OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL"
            " AND reversal_reason IS NOT NULL)",
            name="reversed_has_reason",
        ),
        # One standing restriction per receipt. Two would each be checked against
        # the receipt on its own and together exceed it.
        Index(
            "uq_cf_restriction_one_standing",
            "receipt_id",
            unique=True,
            postgresql_where=text("status IN ('recorded', 'confirmed')"),
        ),
        Index("ix_cf_restrictions_project_status", "project_id", "status"),
    )


class CashflowRestrictionRelease(Base):
    """Cash moving from restricted to usable. Never new cash.

    A release increases what the developer may spend and leaves the bank balance
    exactly where it was. Reporting it as an inflow — which is the obvious
    mistake, since it makes usable cash go up — would show the project collecting
    money twice: once when the buyer paid and again when the bank let go of it.
    """

    __tablename__ = "cashflow_restriction_releases"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    restriction_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    release_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    certification_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=MOVEMENT_RECORDED)

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
    reversal_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["restriction_id", "project_id"],
            [
                "cashflow_receipt_restrictions.id",
                "cashflow_receipt_restrictions.project_id",
            ],
            name="restriction",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="cf_release_project"),
        CheckConstraint(in_list("status", MOVEMENT_STATUSES), name="status_ok"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "status <> 'confirmed'"
            " OR (confirmed_at IS NOT NULL AND confirmed_by_user_id IS NOT NULL)",
            name="confirmed_has_actor",
        ),
        CheckConstraint(
            "status <> 'reversed'"
            " OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL"
            " AND reversal_reason IS NOT NULL)",
            name="reversed_has_reason",
        ),
        CheckConstraint(
            "confirmed_by_user_id IS NULL OR confirmed_by_user_id <> recorded_by_user_id",
            name="confirmer_is_not_recorder",
        ),
        Index("ix_cf_releases_restriction_status", "restriction_id", "status"),
        Index("ix_cf_releases_project_date", "project_id", "release_date"),
    )
