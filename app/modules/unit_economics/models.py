"""What a unit costs, and the governed basis that decided it.

Four tables and one idea: a shared project cost becomes a unit cost only
through a **version** somebody approved, and that version keeps saying what it
said. Everything else in this module follows from that.

```text
allocation version      one governed basis, effective from a date
    cost pool           one shared amount, one category, one method
        allocation      one unit's share of one pool, with its driver
unit cost               one cost attributable to one unit directly
```

Three properties are worth stating because the rest of the design is downstream
of them.

**Allocations are stored, not cached.** Every other total in the platform is
derived — an outstanding balance, a weighted area, a project margin — and this
module keeps that rule for profit. Allocations are the exception, and the reason
is that recalculating one from today's areas and today's prices would not
reproduce it. The version has to preserve which units were eligible, what driver
each carried, which approved area schedule and which price version supplied it,
and where the rounding residual went. That is transaction detail, not a cache of
something still derivable.

**A sold unit keeps the basis that governed when it was sold.** Not by a foreign
key from the sale — sales does not know this module exists and must not learn —
but by effective dating: the version whose window contains the contract date is
the sale's basis, permanently. Activating a new version tomorrow moves unsold
economics and leaves sold ones exactly where they were. It is the same
mechanism as an effective-dated price, for the same reason.

**Money leaves through reversal, never deletion.** A unit cost that was wrong is
reversed with a reason and replaced. There is no update path on a recorded
amount and no delete path at all.
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

from app.db.base import MEASURE, MONEY, RATE, Base, in_list

# --------------------------------------------------------------------------- #
# Allocation version lifecycle
# --------------------------------------------------------------------------- #

#: How a cost allocation basis moves. The same five states pricing uses, for the
#: same reason: a financial basis is drafted, checked, approved, made current,
#: and then kept because something was sold against it.
VERSION_STATUSES = (
    "draft",
    "submitted",
    "approved",
    "active",
    "superseded",
    "rejected",
)
VERSION_DRAFT = "draft"
VERSION_SUBMITTED = "submitted"
VERSION_APPROVED = "approved"
VERSION_ACTIVE = "active"
VERSION_SUPERSEDED = "superseded"
VERSION_REJECTED = "rejected"

#: States in which the version's inputs are frozen. Editing a pool here would
#: change an allocation somebody has already approved, or worse, sold against.
VERSION_FROZEN = frozenset(
    {VERSION_SUBMITTED, VERSION_APPROVED, VERSION_ACTIVE, VERSION_SUPERSEDED}
)

#: States that have governed, or still govern, real economics. A rejected draft
#: never did and is excluded; it stays readable and decides nothing.
VERSION_GOVERNING = frozenset({VERSION_ACTIVE, VERSION_SUPERSEDED})

#: Whether this version allocates a share of project financing to units, or
#: deliberately leaves finance cost out. Explicit because the alternative is a
#: reader assuming zero finance cost when the truth is "not analysed here".
FINANCE_TREATMENTS = ("allocated", "excluded")
FINANCE_ALLOCATED = "allocated"
FINANCE_EXCLUDED = "excluded"

# --------------------------------------------------------------------------- #
# Cost pools
# --------------------------------------------------------------------------- #

#: The four economic cost groups a shared pool can belong to. A closed list, not
#: a chart of accounts: PR-MVP-09 owns cost codes and this is not it.
POOL_CATEGORIES = ("land", "hard", "soft", "finance")
CATEGORY_LAND = "land"
CATEGORY_HARD = "hard"
CATEGORY_SOFT = "soft"
CATEGORY_FINANCE = "finance"

#: The three categories a version must address explicitly before it may be
#: submitted. Finance is separate: it is addressed by ``finance_treatment``,
#: because "no finance pools" and "finance deliberately excluded" are different
#: statements and only one of them is an omission.
REQUIRED_CATEGORIES = (CATEGORY_LAND, CATEGORY_HARD, CATEGORY_SOFT)

#: Where a pool's amount comes from. ``project_land`` is derived from the land
#: register and re-derived at activation; ``manual`` is governed Finance input.
#: There is no third kind until PR-MVP-09 exists to supply one.
POOL_SOURCE_KINDS = ("project_land", "manual")
SOURCE_PROJECT_LAND = "project_land"
SOURCE_MANUAL = "manual"

#: Which units a pool reaches. Three explicit shapes, never an expression.
POOL_SCOPES = ("project", "phase", "building")
SCOPE_PROJECT = "project"
SCOPE_PHASE = "phase"
SCOPE_BUILDING = "building"

#: How a pool is divided. A closed list of five, each with its own arithmetic in
#: ``calculator.py``. Not a formula language, and deliberately not extensible by
#: configuration: a new method is code, a migration and a test.
ALLOCATION_METHODS = (
    "weighted_area",
    "raw_area",
    "unit_count",
    "revenue_value",
    "custom_driver",
)
METHOD_WEIGHTED_AREA = "weighted_area"
METHOD_RAW_AREA = "raw_area"
METHOD_UNIT_COUNT = "unit_count"
METHOD_REVENUE_VALUE = "revenue_value"
METHOD_CUSTOM_DRIVER = "custom_driver"

#: Methods that read an approved area schedule, and therefore go stale when one
#: is superseded between calculation and activation.
AREA_METHODS = frozenset({METHOD_WEIGHTED_AREA, METHOD_RAW_AREA})

# --------------------------------------------------------------------------- #
# Direct unit costs
# --------------------------------------------------------------------------- #

#: What a directly attributable cost is for. Closed, because the economic class
#: below is derived from it rather than chosen.
UNIT_COST_TYPES = (
    "unit_upgrade",
    "finishes",
    "furniture_appliance",
    "legal_registry_support",
    "rectification",
    "other_direct",
    "marketing",
    "sales_commission",
    "branch_commission",
    "payment_fee",
    "seller_paid_legal",
    "other_selling",
)

#: The two economic classes a unit cost can carry. Development cost sits above
#: gross profit; selling cost sits below it, in contribution.
COST_CLASSES = ("direct", "variable_selling")
CLASS_DIRECT = "direct"
CLASS_VARIABLE_SELLING = "variable_selling"

#: The one true mapping, stated once. Sales makes the same choice for adjustment
#: treatment and for the same reason: letting a user pick both the type and what
#: it does to profit is letting them pick which side of gross profit a cost
#: lands on, which is not an operational decision.
UNIT_COST_CLASS_OF: dict[str, str] = {
    "unit_upgrade": CLASS_DIRECT,
    "finishes": CLASS_DIRECT,
    "furniture_appliance": CLASS_DIRECT,
    "legal_registry_support": CLASS_DIRECT,
    "rectification": CLASS_DIRECT,
    "other_direct": CLASS_DIRECT,
    "marketing": CLASS_VARIABLE_SELLING,
    "sales_commission": CLASS_VARIABLE_SELLING,
    "branch_commission": CLASS_VARIABLE_SELLING,
    "payment_fee": CLASS_VARIABLE_SELLING,
    "seller_paid_legal": CLASS_VARIABLE_SELLING,
    "other_selling": CLASS_VARIABLE_SELLING,
}

#: Whether a recorded cost is what Finance expects or what actually happened.
#: An unsold unit is analysed on forecast; a sold one on actual.
COST_BASES = ("forecast", "actual")
BASIS_FORECAST = "forecast"
BASIS_ACTUAL = "actual"

#: A recorded cost stands until somebody reverses it. There is no third state
#: and no delete.
UNIT_COST_STATUSES = ("active", "reversed")
COST_ACTIVE = "active"
COST_REVERSED = "reversed"

# --------------------------------------------------------------------------- #
# Profitability
# --------------------------------------------------------------------------- #

#: Whether a unit's profit could be calculated, and if not, exactly why. A
#: status is returned instead of a number because a fabricated margin is worse
#: than a missing one: nobody checks a number that looks finished.
PROFITABILITY_STATUSES = (
    "ready",
    "missing_revenue",
    "missing_cost_basis",
    "unreconciled_cost_basis",
    "currency_mismatch",
)
PROFIT_READY = "ready"
PROFIT_MISSING_REVENUE = "missing_revenue"
PROFIT_MISSING_COST_BASIS = "missing_cost_basis"
PROFIT_UNRECONCILED = "unreconciled_cost_basis"
PROFIT_CURRENCY_MISMATCH = "currency_mismatch"

#: Where a unit's revenue figure came from.
REVENUE_SOURCES = ("approved_price", "sale_contract")
REVENUE_FROM_PRICE = "approved_price"
REVENUE_FROM_SALE = "sale_contract"

#: Which side of the sold line a unit is analysed on.
ECONOMIC_BASES = ("forecast", "sold")
BASIS_SOLD = "sold"

#: Audit entity names.
ENTITY_VERSION = "unit_economics_allocation_version"
ENTITY_POOL = "unit_economics_cost_pool"
ENTITY_UNIT_COST = "unit_economics_unit_cost"


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #


class AllocationVersion(Base):
    """One governed project-wide basis for turning shared cost into unit cost.

    ``effective_from`` is the load-bearing column. It is what a sold unit is
    matched against, so the window a version governs is the window whose
    economics it decides — for ever, not until the next version is approved.
    """

    __tablename__ = "unit_economics_allocation_versions"

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
    #: Always the project's base currency. Recorded rather than assumed so the
    #: version stays readable if the project is ever re-based, and checked on
    #: creation so Finance cannot allocate a project's cost in a currency the
    #: project does not account in.
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=VERSION_DRAFT)
    finance_treatment: Mapped[str] = mapped_column(
        String(16), nullable=False, default=FINANCE_EXCLUDED
    )

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    #: Closed when the next version takes over. Open on the current one.
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    change_reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    #: The version this one was cloned from, where it was.
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    #: When the allocation rows below were last generated. Null on a version
    #: nobody has calculated yet, which is a version that cannot be submitted.
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
        # A clone says which version it was taken from, and the database proves
        # that version exists and belongs to the same project. Without this the
        # column is a note: a lineage pointing at a deleted version, or at
        # another developer's project, reads back as provenance and is not.
        ForeignKeyConstraint(
            ["source_version_id", "project_id"],
            [
                "unit_economics_allocation_versions.id",
                "unit_economics_allocation_versions.project_id",
            ],
            name="source_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "version_number", name="uq_ue_version_number"),
        UniqueConstraint("id", "project_id", name="ue_version_project"),
        CheckConstraint(in_list("status", VERSION_STATUSES), name="status_ok"),
        CheckConstraint(in_list("finance_treatment", FINANCE_TREATMENTS), name="treatment_ok"),
        CheckConstraint("version_number >= 1", name="number_positive"),
        CheckConstraint("length(change_reason) > 0", name="reason_present"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from", name="window_ordered"
        ),
        CheckConstraint(
            "status <> 'rejected' OR (rejected_at IS NOT NULL AND rejection_reason IS NOT NULL)",
            name="rejection_complete",
        ),
        CheckConstraint(
            "status NOT IN ('active', 'superseded') OR activated_at IS NOT NULL",
            name="activation_stamped",
        ),
        # One current basis per project. The service takes the project lock so
        # the loser is told what happened, but the database is what makes two
        # active versions impossible rather than merely unlikely.
        Index(
            "uq_ue_versions_one_active",
            "project_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_ue_versions_project_status", "project_id", "status"),
        Index("ix_ue_versions_project_effective", "project_id", "effective_from"),
    )


class CostPool(Base):
    """One shared amount, and the rule for dividing it among units.

    A pool belongs to exactly one version, which is why it carries no status of
    its own: the version's lifecycle governs whether this amount is a draft
    input, an approved basis or history.
    """

    __tablename__ = "unit_economics_cost_pools"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    allocation_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    pool_number: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False, default=SOURCE_MANUAL)
    #: Denominated in the version's currency, which is the project's base
    #: currency. For a ``project_land`` pool this is a snapshot of the land
    #: register's total, re-derived and compared at activation.
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    scope_kind: Mapped[str] = mapped_column(String(16), nullable=False, default=SCOPE_PROJECT)
    phase_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    building_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    allocation_method: Mapped[str] = mapped_column(String(24), nullable=False)
    #: Which area a ``raw_area`` pool divides on. "Raw area" is one measured
    #: type Finance names, never the sum of every area a unit has.
    area_type_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

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

    __table_args__ = (
        ForeignKeyConstraint(
            ["allocation_version_id", "project_id"],
            [
                "unit_economics_allocation_versions.id",
                "unit_economics_allocation_versions.project_id",
            ],
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
            ["building_id", "project_id"],
            ["buildings.id", "buildings.project_id"],
            name="building",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["area_type_id", "project_id"],
            ["area_types.id", "area_types.project_id"],
            name="area_type",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("allocation_version_id", "pool_number", name="uq_ue_pool_number"),
        UniqueConstraint("id", "project_id", name="ue_pool_project"),
        #: The key an allocation's three-column parentage points at, so that a
        #: row cannot name a pool from one version and a version from another.
        UniqueConstraint(
            "id", "allocation_version_id", "project_id", name="ue_pool_version_project"
        ),
        # Land comes from the land register, project-wide, or it is not a land
        # pool. Service refusals give the operator a sentence; this is what
        # holds when the service is not the one writing.
        CheckConstraint(
            "category <> 'land' OR source_kind = 'project_land'",
            name="land_is_canonical",
        ),
        CheckConstraint(
            "source_kind <> 'project_land' OR scope_kind = 'project'",
            name="land_is_project_wide",
        ),
        CheckConstraint(in_list("category", POOL_CATEGORIES), name="category_ok"),
        CheckConstraint(in_list("source_kind", POOL_SOURCE_KINDS), name="source_ok"),
        CheckConstraint(in_list("scope_kind", POOL_SCOPES), name="scope_ok"),
        CheckConstraint(in_list("allocation_method", ALLOCATION_METHODS), name="method_ok"),
        CheckConstraint("amount >= 0", name="amount_nonneg"),
        CheckConstraint("length(name) > 0", name="name_present"),
        # The scope shape, in the database rather than only in the service. A
        # phase pool without a phase is not a pool anybody can allocate.
        CheckConstraint(
            "(scope_kind = 'project' AND phase_id IS NULL AND building_id IS NULL) "
            "OR (scope_kind = 'phase' AND phase_id IS NOT NULL AND building_id IS NULL) "
            "OR (scope_kind = 'building' AND building_id IS NOT NULL AND phase_id IS NULL)",
            name="scope_shape",
        ),
        # An area type is required by raw area and meaningless elsewhere.
        CheckConstraint(
            "(allocation_method = 'raw_area') = (area_type_id IS NOT NULL)",
            name="area_type_shape",
        ),
        # Only land may claim to come from the land register.
        CheckConstraint(
            "source_kind <> 'project_land' OR category = 'land'", name="land_source_shape"
        ),
        # One canonical land pool per version. Two of them each draw the whole
        # project land total, so the land cost doubles while every pool still
        # reconciles exactly — a false result nothing downstream can detect.
        Index(
            "uq_ue_pools_one_project_land",
            "allocation_version_id",
            unique=True,
            postgresql_where=text("source_kind = 'project_land'"),
        ),
        Index("ix_ue_pools_version", "allocation_version_id"),
    )


class Allocation(Base):
    """One unit's share of one pool, and the evidence for it.

    Immutable once its version is submitted. The snapshot columns are why: an
    allocation that cannot say which approved measurement and which price
    version produced it is a number with no audit trail, and recomputing it from
    today's inputs would answer a different question from the one asked.
    """

    __tablename__ = "unit_economics_allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    allocation_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    cost_pool_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    #: What this unit brought to the denominator: a weighted area, a raw area, a
    #: count of one, a reference revenue, or a Finance-entered driver.
    driver_value: Mapped[Decimal] = mapped_column(MEASURE, nullable=False)
    #: This unit's fraction of the pool, recorded for explanation rather than
    #: for arithmetic — ``allocated_amount`` is what reconciles.
    driver_share: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    allocated_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    source_area_schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    source_price_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    #: The one unit per pool that absorbed the rounding residual, so a reader
    #: asking why this unit is a cent above its share has an answer.
    is_rounding_recipient: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # Three columns, not two. With separate pool and version keys both
        # foreign keys pass while the allocation claims version two and its pool
        # belongs to version one — and the row then reconciles against the wrong
        # pool, drills down into the wrong basis, and prices a sold unit on a
        # version it was never governed by. Service discipline is not enough for
        # an invariant that decides what a unit cost.
        ForeignKeyConstraint(
            ["cost_pool_id", "allocation_version_id", "project_id"],
            [
                "unit_economics_cost_pools.id",
                "unit_economics_cost_pools.allocation_version_id",
                "unit_economics_cost_pools.project_id",
            ],
            name="pool",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["allocation_version_id", "project_id"],
            [
                "unit_economics_allocation_versions.id",
                "unit_economics_allocation_versions.project_id",
            ],
            name="version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_area_schedule_id", "project_id"],
            ["unit_area_schedules.id", "unit_area_schedules.project_id"],
            name="schedule",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_price_version_id", "project_id"],
            ["unit_price_versions.id", "unit_price_versions.project_id"],
            name="price_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("cost_pool_id", "unit_id", name="uq_ue_allocation_unit"),
        CheckConstraint("driver_value >= 0", name="driver_nonneg"),
        CheckConstraint("driver_share >= 0", name="share_nonneg"),
        Index("ix_ue_allocations_version_unit", "allocation_version_id", "unit_id"),
        Index("ix_ue_allocations_pool", "cost_pool_id"),
    )


class UnitCost(Base):
    """A cost attributable to one unit without dividing anything.

    A furniture package for unit 402 is not a shared pool with one eligible
    unit; modelling it that way would put a version lifecycle and an approval
    round in front of a supplier invoice. It is recorded here, reversed here,
    and never edited.
    """

    __tablename__ = "unit_economics_unit_costs"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: Required on an actual cost where the unit has a live contract: a
    #: commission is earned on a specific deal, and a cost that cannot name its
    #: deal cannot be kept out of the next one.
    sale_contract_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    #: The project's base currency, checked on recording. Costs and revenue in
    #: different currencies are reported side by side and never combined.
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    cost_type: Mapped[str] = mapped_column(String(32), nullable=False)
    basis: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=COST_ACTIVE)

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
    reversal_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        CheckConstraint(in_list("cost_type", UNIT_COST_TYPES), name="type_ok"),
        CheckConstraint(in_list("basis", COST_BASES), name="basis_ok"),
        CheckConstraint(in_list("status", UNIT_COST_STATUSES), name="status_ok"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "status <> 'reversed' OR "
            "(reversed_at IS NOT NULL AND reversal_reason IS NOT NULL "
            "AND reversed_by_user_id IS NOT NULL)",
            name="reversal_complete",
        ),
        Index("ix_ue_unit_costs_unit_status", "unit_id", "status"),
        Index("ix_ue_unit_costs_project_status", "project_id", "status"),
        Index("ix_ue_unit_costs_sale", "sale_contract_id"),
    )
