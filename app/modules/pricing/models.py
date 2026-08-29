"""Pricing: what a unit costs, why, and what that number replaced.

PR-MVP-03 established what physically exists. This module establishes what it
is offered at — and, more importantly, makes that number explicable. A price
that cannot be taken apart into the areas, rates, premiums and escalations that
produced it is a spreadsheet cell with a database around it.

Three rules shape every table here.

**A price is never overwritten.** Changing a price creates a new
:class:`UnitPriceVersion`; the one it replaces becomes ``superseded`` and stays
readable for ever. There is no update path to an approved amount and no delete
path to any of it.

**A price is a frozen decision.** A version records the pricing configuration,
the approved area schedule, the raw areas, the features and the sub-asset counts
it was calculated from. Inventory keeps moving underneath; the version does not.
That is what lets an auditor ask what the calculation saw in March and get an
answer that is not today's data.

**Every amount is exact.** ``NUMERIC`` in the database, ``Decimal`` in Python,
strings on the wire. No binary float touches a price at any point.

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
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MEASURE, MONEY, RATE, Base, in_list

# --------------------------------------------------------------------------- #
# Closed sets
# --------------------------------------------------------------------------- #

#: The lifecycle a pricing configuration and a unit price version both follow.
#: One vocabulary rather than two, because they are the same governance shape:
#: somebody prepares, somebody else approves, and only then does it go live.
PRICING_STATUSES = ("draft", "submitted", "approved", "active", "superseded")
STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_APPROVED = "approved"
STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"

#: Statuses nothing may edit. Everything a submitted price says has already been
#: shown to an approver, and everything an active one says has been sold on.
IMMUTABLE_STATUSES = frozenset(
    {STATUS_SUBMITTED, STATUS_APPROVED, STATUS_ACTIVE, STATUS_SUPERSEDED}
)

#: How an area type contributes to the base price.
#:
#: ``internal_base`` is the area the configuration's headline rate is quoted
#: against. ``fixed_rate_per_area`` prices an attached area at its own rate, and
#: ``factor_of_internal_rate`` prices it as a share of the internal rate, which
#: is how balconies and terraces are usually written down. ``excluded`` says the
#: area is measured but not sold — a plot boundary, say.
AREA_PRICING_METHODS = (
    "internal_base",
    "fixed_rate_per_area",
    "factor_of_internal_rate",
    "excluded",
)
AREA_METHOD_INTERNAL_BASE = "internal_base"
AREA_METHOD_FIXED_RATE = "fixed_rate_per_area"
AREA_METHOD_FACTOR = "factor_of_internal_rate"
AREA_METHOD_EXCLUDED = "excluded"

#: What a premium rule may look at. A closed list, and deliberately so: the
#: alternative is a field name, an operator and a value, which is an expression
#: language with a table around it. Every entry here names a real column of the
#: inventory model or a real configured field.
PREMIUM_SOURCE_KINDS = (
    "phase",
    "building",
    "unit_type",
    "view_class",
    "floor_band",
    "orientation",
    "corner",
    "pool_access",
    "accessibility",
    "garden_class",
    "parking",
    "storage",
    "area_type",
    "custom_field",
)

#: Source kinds that match on a code the row carries. The rest are either
#: boolean facts about the unit or counted things.
PREMIUM_CODE_SOURCES = frozenset(
    {
        "phase",
        "building",
        "unit_type",
        "view_class",
        "floor_band",
        "orientation",
        "accessibility",
        "garden_class",
        "area_type",
    }
)

#: Source kinds that are a plain yes/no on the unit.
PREMIUM_FLAG_SOURCES = frozenset({"corner", "pool_access"})

#: Source kinds counted from linked sub-assets.
PREMIUM_ASSET_SOURCES = frozenset({"parking", "storage"})

#: How a premium turns into money.
PREMIUM_METHODS = ("percentage", "fixed", "per_area", "fixed_per_asset")
PREMIUM_METHOD_PERCENTAGE = "percentage"
PREMIUM_METHOD_FIXED = "fixed"
PREMIUM_METHOD_PER_AREA = "per_area"
PREMIUM_METHOD_PER_ASSET = "fixed_per_asset"

#: What a percentage premium is a percentage *of*. Named explicitly because
#: "5%" with no stated base is the ambiguity that makes two people compute two
#: different prices from one rule.
ELIGIBLE_BASES = ("base_area_value", "base_with_adjustments")
ELIGIBLE_BASE_AREAS = "base_area_value"
ELIGIBLE_BASE_WITH_ADJUSTMENTS = "base_with_adjustments"

#: Additive is the default and the safe reading: 5% and 3% add 8% of one base,
#: not 8.15% of a base that grew in between. Compounding is available but must
#: be asked for on the rule, in a stated sequence.
STACKING_METHODS = ("additive", "compound")
STACKING_ADDITIVE = "additive"
STACKING_COMPOUND = "compound"

#: What makes an escalation eligible. Only ``date`` can be evaluated by this PR
#: from data the system already holds; the other three are configured here and
#: activated against evidence a CFO records, because the transactions that would
#: prove them — sales, certified milestones, an index feed — do not exist yet.
#: Faking those sources would put invented facts in a price.
ESCALATION_TRIGGERS = ("date", "sales_percentage", "construction_milestone", "market_index")
TRIGGER_DATE = "date"
TRIGGER_SALES_PERCENTAGE = "sales_percentage"
TRIGGER_CONSTRUCTION_MILESTONE = "construction_milestone"
TRIGGER_MARKET_INDEX = "market_index"

#: The one fact each trigger is *about*. A rule carries exactly its own and none
#: of the others: "escalate when we are 30% sold" with no 30% in it is not a
#: policy, it is a policy-shaped row, and the day somebody tries to activate it
#: there is nothing to check the evidence against.
ESCALATION_TRIGGER_INPUTS = {
    TRIGGER_DATE: "threshold_date",
    TRIGGER_SALES_PERCENTAGE: "threshold_fraction",
    TRIGGER_CONSTRUCTION_MILESTONE: "milestone_reference",
    TRIGGER_MARKET_INDEX: "market_index_reference",
}

#: How far an escalation rule reaches.
ESCALATION_SCOPES = ("project", "phase", "unit_type")
ESCALATION_SCOPE_PROJECT = "project"
ESCALATION_SCOPE_PHASE = "phase"
ESCALATION_SCOPE_UNIT_TYPE = "unit_type"

#: How an escalation moves the price.
ADJUSTMENT_METHODS = ("percentage", "fixed")
ADJUSTMENT_PERCENTAGE = "percentage"
ADJUSTMENT_FIXED = "fixed"

#: Which area a benchmark is quoted per. Two denominators, both real, and the
#: one used is always published beside the comparison: a price per internal
#: metre and a price per weighted metre are different numbers, and a market
#: flag that does not say which it used is not a flag anybody can act on.
BENCHMARK_AREA_BASES = ("internal", "weighted")
BASIS_INTERNAL = "internal"
BASIS_WEIGHTED = "weighted"

#: What the benchmark comparison concluded.
MARKET_FLAGS = ("within_tolerance", "above_tolerance", "below_tolerance", "no_benchmark")
FLAG_WITHIN = "within_tolerance"
FLAG_ABOVE = "above_tolerance"
FLAG_BELOW = "below_tolerance"
FLAG_NONE = "no_benchmark"

#: Whether the configuration's prices are quoted with tax in them. The reference
#: price a version stores is ex tax either way; this records the commercial
#: convention so a quote can say what it is showing.
TAX_TREATMENTS = ("exclusive", "inclusive")
TAX_EXCLUSIVE = "exclusive"

#: The lines a price is made of. Each one names a real kind of contribution;
#: there is no "formula" component, because there is no formula.
COMPONENT_TYPES = (
    "base_internal",
    "base_attached",
    "scope_adjustment",
    "feature_premium",
    "sub_asset_premium",
    "escalation",
    "paid_upgrade",
    "premium_cap_adjustment",
    "manual_override",
)
COMPONENT_BASE_INTERNAL = "base_internal"
COMPONENT_BASE_ATTACHED = "base_attached"
COMPONENT_SCOPE_ADJUSTMENT = "scope_adjustment"
COMPONENT_FEATURE_PREMIUM = "feature_premium"
COMPONENT_SUB_ASSET_PREMIUM = "sub_asset_premium"
COMPONENT_ESCALATION = "escalation"
COMPONENT_PAID_UPGRADE = "paid_upgrade"
COMPONENT_PREMIUM_CAP = "premium_cap_adjustment"

#: Audit entity types. Written once so an audit query never depends on a string
#: literal being spelled the same way in six places.
ENTITY_CONFIGURATION = "pricing_configuration"
ENTITY_AREA_RULE = "pricing_area_rule"
ENTITY_PREMIUM_RULE = "pricing_premium_rule"
ENTITY_ESCALATION_RULE = "pricing_escalation_rule"
ENTITY_ESCALATION_ACTIVATION = "pricing_escalation_activation"
ENTITY_BENCHMARK = "market_benchmark"
ENTITY_PRICE_VERSION = "unit_price_version"


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


class PricingConfiguration(Base):
    """One governed commercial pricing policy for a project.

    A configuration is what turns areas and features into money. It is versioned
    for the same reason a price is: changing the balcony factor changes every
    price generated afterwards, and a project has to be able to say which policy
    a given unit was priced under.

    Exactly one configuration per project may be ``active``, enforced by a
    partial unique index rather than by whichever transaction read first.
    """

    __tablename__ = "pricing_configurations"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_DRAFT)

    #: Pricing carries its currency explicitly. Inferring it from the project
    #: would make a currency change silently reinterpret every stored amount.
    pricing_currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    #: Money per unit of internal area. The headline number a project is priced
    #: from, and the anchor every ``factor_of_internal_rate`` area refers to.
    base_internal_rate: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    premium_stacking_default: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STACKING_ADDITIVE
    )
    #: An explicit fraction of the eligible base. NULL means premiums are not
    #: capped, which is a decision, not an oversight.
    maximum_premium_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)

    # Quote controls. Policy this PR records and a quote preview reports; the
    # transactions that consume them are PR-MVP-05's and PR-MVP-06's.
    offer_valid_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_lock_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reservation_expiry_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: A signed fraction: 0.030000 adds 3% for extended terms, -0.020000 gives
    #: 2% away for payment up front.
    default_payment_plan_adjustment_fraction: Mapped[Decimal | None] = mapped_column(
        RATE, nullable=True
    )
    tax_treatment_code: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TAX_EXCLUSIVE
    )

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

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
        UniqueConstraint("project_id", "version_number"),
        UniqueConstraint("id", "project_id", name="config_project"),
        CheckConstraint("length(name) > 0", name="name_not_blank"),
        CheckConstraint(in_list("status", PRICING_STATUSES), name="status_allowed"),
        CheckConstraint(
            in_list("premium_stacking_default", STACKING_METHODS), name="stacking_allowed"
        ),
        CheckConstraint(in_list("tax_treatment_code", TAX_TREATMENTS), name="tax_allowed"),
        CheckConstraint("version_number >= 1", name="version_positive"),
        CheckConstraint("base_internal_rate >= 0", name="rate_nonneg"),
        CheckConstraint(
            "maximum_premium_fraction IS NULL "
            "OR (maximum_premium_fraction >= 0 AND maximum_premium_fraction <= 1)",
            name="cap_range",
        ),
        CheckConstraint(
            "default_payment_plan_adjustment_fraction IS NULL "
            "OR (default_payment_plan_adjustment_fraction >= -1 "
            "AND default_payment_plan_adjustment_fraction <= 1)",
            name="plan_adjust_range",
        ),
        CheckConstraint(
            "offer_valid_days IS NULL OR offer_valid_days > 0", name="offer_days_positive"
        ),
        CheckConstraint(
            "price_lock_days IS NULL OR price_lock_days > 0", name="lock_days_positive"
        ),
        CheckConstraint(
            "reservation_expiry_days IS NULL OR reservation_expiry_days > 0",
            name="expiry_days_positive",
        ),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="valid_range"),
        # One live pricing policy per project. Two would mean two answers to
        # "what rate is this development priced at", which is the question the
        # whole module exists to answer.
        Index(
            "uq_pricing_configurations_active",
            "project_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_pricing_configurations_project_id_status", "project_id", "status"),
    )


class PricingAreaRule(Base):
    """How one area type of a project turns into money.

    Keyed by ``area_type_id`` and never by a name: "BALCONY" is a label a
    project chooses, and pricing that matched on it would break the day somebody
    renamed it.
    """

    __tablename__ = "pricing_area_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    pricing_configuration_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False
    )
    area_type_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    pricing_method: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Money per unit of this area. Set only for ``fixed_rate_per_area``.
    rate_per_area: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    #: A share of the configuration's internal rate. Set only for
    #: ``factor_of_internal_rate``: 0.500000 prices this area at half.
    internal_rate_factor: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
            ["pricing_configuration_id", "project_id"],
            ["pricing_configurations.id", "pricing_configurations.project_id"],
            name="config",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["area_type_id", "project_id"],
            ["area_types.id", "area_types.project_id"],
            name="area_type",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("pricing_configuration_id", "area_type_id"),
        UniqueConstraint("id", "project_id", name="area_rule_project"),
        CheckConstraint(in_list("pricing_method", AREA_PRICING_METHODS), name="method_allowed"),
        CheckConstraint("rate_per_area IS NULL OR rate_per_area >= 0", name="rate_nonneg"),
        CheckConstraint(
            "internal_rate_factor IS NULL OR internal_rate_factor >= 0", name="factor_nonneg"
        ),
        # Each method carries exactly the number it needs and nothing else, so a
        # rule can never hold a rate the calculation will not read.
        CheckConstraint(
            "(pricing_method = 'fixed_rate_per_area' "
            "  AND rate_per_area IS NOT NULL AND internal_rate_factor IS NULL) "
            "OR (pricing_method = 'factor_of_internal_rate' "
            "  AND internal_rate_factor IS NOT NULL AND rate_per_area IS NULL) "
            "OR (pricing_method IN ('internal_base', 'excluded') "
            "  AND rate_per_area IS NULL AND internal_rate_factor IS NULL)",
            name="method_inputs",
        ),
        Index("ix_pricing_area_rules_configuration_id", "pricing_configuration_id"),
        # One configuration, one internal base. The project lock is the friendly
        # mechanism and this is the backstop: "which area is the internal rate
        # quoted against" has to have one answer, or the price per internal
        # metre printed on every screen is a number with two meanings.
        Index(
            "uq_pricing_area_rules_internal_base",
            "pricing_configuration_id",
            unique=True,
            postgresql_where=text("pricing_method = 'internal_base' AND is_active"),
        ),
    )


class PricingPremiumRule(Base):
    """One priced characteristic of a unit.

    This is a matching table, not a rules engine. ``source_kind`` names a fixed
    place to look — a column of the unit, a linked sub-asset, a measured area, a
    configured field — and ``match_code`` names the value that qualifies. There
    is no field name, no operator and nothing that is later evaluated.

    ``percentage_fraction`` and ``amount`` are separate columns rather than one
    ``value`` whose meaning depends on ``method``: 0.05 and 5,000 are not the
    same kind of number, and a column that holds either is a column somebody
    eventually reads as the wrong one.
    """

    __tablename__ = "pricing_premium_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    pricing_configuration_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    #: The configured code that qualifies — a phase code, a view class, an area
    #: type code. Null for the boolean sources, where the fact is the match, and
    #: optional for parking and storage, where it narrows to one subtype.
    match_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    custom_field_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        # Named explicitly: the convention would render 76 characters, and
        # PostgreSQL truncates at 63, after which the name no longer matches
        # the metadata and `alembic check` reports drift for ever.
        ForeignKey("custom_field_definitions.id", ondelete="RESTRICT", name="custom_field"),
        nullable=True,
    )
    custom_option_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    method: Mapped[str] = mapped_column(String(16), nullable=False)
    #: An explicit fraction of the eligible base. Percentage method only.
    percentage_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    #: Money — a flat amount, an amount per unit of area, or an amount per
    #: counted asset, depending on ``method``.
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    eligible_base: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ELIGIBLE_BASE_WITH_ADJUSTMENTS
    )
    #: NULL means "whatever the configuration says". Compounding is never
    #: inherited by accident: a rule that compounds says so.
    stacking_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
            ["pricing_configuration_id", "project_id"],
            ["pricing_configurations.id", "pricing_configurations.project_id"],
            name="config",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("pricing_configuration_id", "code"),
        UniqueConstraint("id", "project_id", name="premium_rule_project"),
        CheckConstraint("length(code) > 0", name="code_not_blank"),
        CheckConstraint("code = upper(code)", name="code_upper"),
        CheckConstraint("length(label) > 0", name="label_not_blank"),
        CheckConstraint(in_list("source_kind", PREMIUM_SOURCE_KINDS), name="source_allowed"),
        CheckConstraint(in_list("method", PREMIUM_METHODS), name="method_allowed"),
        CheckConstraint(in_list("eligible_base", ELIGIBLE_BASES), name="base_allowed"),
        CheckConstraint(
            "stacking_method IS NULL OR " + in_list("stacking_method", STACKING_METHODS),
            name="stacking_allowed",
        ),
        CheckConstraint(
            "percentage_fraction IS NULL "
            "OR (percentage_fraction >= -1 AND percentage_fraction <= 1)",
            name="percentage_range",
        ),
        CheckConstraint(
            "(method = 'percentage' AND percentage_fraction IS NOT NULL AND amount IS NULL) "
            "OR (method <> 'percentage' AND amount IS NOT NULL AND percentage_fraction IS NULL)",
            name="method_inputs",
        ),
        # A custom-field premium must name the definition it reads; nothing else
        # may, because there is no other field for it to be about.
        CheckConstraint(
            "(source_kind = 'custom_field' AND custom_field_definition_id IS NOT NULL) "
            "OR (source_kind <> 'custom_field' AND custom_field_definition_id IS NULL "
            "    AND custom_option_code IS NULL)",
            name="custom_field_inputs",
        ),
        Index("ix_pricing_premium_rules_configuration_id", "pricing_configuration_id"),
    )


class PricingEscalationRule(Base):
    """A configured, scoped price movement waiting on evidence.

    Only ``date`` can be judged from what this system already knows. Absorption,
    certified construction progress and a market index are all real triggers and
    all belong to transactions that do not exist yet, so the rule is configured
    here and activated by a named approver against recorded evidence. Deriving
    them from invented data would put a fabricated fact inside a price.
    """

    __tablename__ = "pricing_escalation_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    pricing_configuration_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    phase_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    unit_type_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    threshold_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: The share of inventory sold that would make this eligible: 0.300000 is
    #: 30%. Recorded as policy; PR-MVP-05 can measure it.
    threshold_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    milestone_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    market_index_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)

    adjustment_method: Mapped[str] = mapped_column(String(16), nullable=False)
    adjustment_percentage_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    adjustment_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    #: Whether this stacks on the price as already escalated, or on the price
    #: before any escalation. Explicit, because "cumulative" is exactly the word
    #: two people read two ways.
    cumulative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
            ["pricing_configuration_id", "project_id"],
            ["pricing_configurations.id", "pricing_configurations.project_id"],
            name="config",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("pricing_configuration_id", "code"),
        UniqueConstraint("id", "project_id", name="escalation_rule_project"),
        CheckConstraint("length(code) > 0", name="code_not_blank"),
        CheckConstraint("code = upper(code)", name="code_upper"),
        CheckConstraint(in_list("trigger_type", ESCALATION_TRIGGERS), name="trigger_allowed"),
        CheckConstraint(in_list("scope_type", ESCALATION_SCOPES), name="scope_allowed"),
        CheckConstraint(in_list("adjustment_method", ADJUSTMENT_METHODS), name="method_allowed"),
        CheckConstraint(
            "(adjustment_method = 'percentage' AND adjustment_percentage_fraction IS NOT NULL "
            "  AND adjustment_amount IS NULL) "
            "OR (adjustment_method = 'fixed' AND adjustment_amount IS NOT NULL "
            "  AND adjustment_percentage_fraction IS NULL)",
            name="method_inputs",
        ),
        CheckConstraint(
            "adjustment_percentage_fraction IS NULL "
            "OR (adjustment_percentage_fraction >= -1 AND adjustment_percentage_fraction <= 1)",
            name="percentage_range",
        ),
        CheckConstraint(
            "threshold_fraction IS NULL OR (threshold_fraction >= 0 AND threshold_fraction <= 1)",
            name="threshold_range",
        ),
        # The scope carries exactly the pointer it names, and nothing else.
        CheckConstraint(
            "(scope_type = 'phase' AND phase_id IS NOT NULL AND unit_type_code IS NULL) "
            "OR (scope_type = 'unit_type' AND unit_type_code IS NOT NULL AND phase_id IS NULL) "
            "OR (scope_type = 'project' AND phase_id IS NULL AND unit_type_code IS NULL)",
            name="scope_inputs",
        ),
        # Exactly one trigger input family, in the database as well as the
        # service: a structural financial invariant, and a direct write is
        # exactly the path that would otherwise store a construction-milestone
        # escalation with no milestone in it.
        CheckConstraint(
            "(trigger_type = 'date' AND threshold_date IS NOT NULL "
            "  AND threshold_fraction IS NULL AND milestone_reference IS NULL "
            "  AND market_index_reference IS NULL) "
            "OR (trigger_type = 'sales_percentage' AND threshold_fraction IS NOT NULL "
            "  AND threshold_date IS NULL AND milestone_reference IS NULL "
            "  AND market_index_reference IS NULL) "
            "OR (trigger_type = 'construction_milestone' AND milestone_reference IS NOT NULL "
            "  AND threshold_date IS NULL AND threshold_fraction IS NULL "
            "  AND market_index_reference IS NULL) "
            "OR (trigger_type = 'market_index' AND market_index_reference IS NOT NULL "
            "  AND threshold_date IS NULL AND threshold_fraction IS NULL "
            "  AND milestone_reference IS NULL)",
            name="trigger_inputs",
        ),
        Index("ix_pricing_escalation_rules_config_id", "pricing_configuration_id"),
    )


class PricingEscalationActivation(Base):
    """The recorded decision that an escalation rule is now in force.

    Immutable once written. A mistake is reversed with a reason and replaced,
    which is the same discipline every other financial record in this system
    follows, and for the same reason: the wrong number having been believed for
    a week is itself a fact somebody may need to see.
    """

    __tablename__ = "pricing_escalation_activations"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    pricing_escalation_rule_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: The measured figure the approver acted on — an absorption fraction, an
    #: index level. Wide enough for either; never money, never a bare percentage
    #: with no stated meaning, which is why ``evidence_reference`` is required.
    evidence_value: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    evidence_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    evidence_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reversal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["pricing_escalation_rule_id", "project_id"],
            ["pricing_escalation_rules.id", "pricing_escalation_rules.project_id"],
            name="rule",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="activation_project"),
        CheckConstraint("length(evidence_reference) > 0", name="evidence_not_blank"),
        CheckConstraint("length(reason) > 0", name="reason_not_blank"),
        CheckConstraint(
            "is_active OR (reversed_at IS NOT NULL AND reversal_reason IS NOT NULL)",
            name="reversal_complete",
        ),
        # One live activation per rule. A second would escalate the same rule
        # twice into the same price.
        Index(
            "uq_pricing_escalation_activations_rule",
            "pricing_escalation_rule_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index("ix_pricing_escalation_activations_project_id", "project_id"),
    )


class MarketBenchmark(Base):
    """A recorded outside price, entered by a person and attributed to a source.

    There is no feed and no scraper. A benchmark is a governed observation with
    a date, a source and a tolerance, and a unit price is compared against
    exactly one of them — chosen by a stated precedence, never averaged.
    """

    __tablename__ = "market_benchmarks"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    phase_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    unit_type_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    area_basis: Mapped[str] = mapped_column(String(16), nullable=False)
    benchmark_price_per_area: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    comparison_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: How far a price may sit from the benchmark before it is called out.
    tolerance_fraction: Mapped[Decimal] = mapped_column(RATE, nullable=False)
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
        ForeignKeyConstraint(["project_id"], ["projects.id"], name="project", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="benchmark_project"),
        CheckConstraint(in_list("area_basis", BENCHMARK_AREA_BASES), name="basis_allowed"),
        CheckConstraint("benchmark_price_per_area > 0", name="price_positive"),
        CheckConstraint("length(source_name) > 0", name="source_not_blank"),
        CheckConstraint(
            "tolerance_fraction >= 0 AND tolerance_fraction <= 1", name="tolerance_range"
        ),
        # Two equally specific active benchmarks would make the comparison a
        # coin toss, so one scope holds one benchmark and that benchmark
        # declares its own area basis. NULLs count as equal here, which is what
        # makes "project-wide" collide with "project-wide" at all.
        Index(
            "uq_market_benchmarks_scope",
            "project_id",
            "phase_id",
            "unit_type_code",
            unique=True,
            postgresql_where=text("is_active"),
            postgresql_nulls_not_distinct=True,
        ),
    )


# --------------------------------------------------------------------------- #
# Unit prices
# --------------------------------------------------------------------------- #


class UnitPriceVersion(Base):
    """One priced decision about one unit, frozen at the moment it was made.

    Nothing here is recalculated later. The configuration can change, the area
    schedule can be superseded, the unit can gain a parking bay — and this row
    still says what the price was and what produced it. A new decision is a new
    row; the old one is superseded and stays.
    """

    __tablename__ = "unit_price_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pricing_configuration_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False
    )
    #: The approved measurement this price was calculated from. Frozen: if the
    #: unit is re-measured and re-approved, this price is stale and says so.
    unit_area_schedule_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_DRAFT)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    #: The date this price takes effect, decided once when it was calculated.
    #: Not nullable, because it is a calculation input rather than a label: it
    #: chose which escalations applied, so a version without one would be a
    #: price whose components nobody could reproduce.
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    base_area_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    scope_adjustment_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    premium_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    #: Negative or zero. The amount the cap removed, kept as its own line so the
    #: breakdown shows what was refused rather than quietly showing less.
    premium_cap_adjustment: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    escalation_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    paid_upgrade_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    reference_price_ex_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    internal_area_snapshot: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    weighted_area_snapshot: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    price_per_internal_area: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    price_per_weighted_area: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    market_benchmark_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    market_benchmark_price_snapshot: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    market_deviation_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    market_flag: Mapped[str] = mapped_column(String(24), nullable=False, default=FLAG_NONE)

    #: Everything the calculation looked at, as it looked at it. Not master
    #: data and never queried in place of inventory — it exists so an auditor
    #: can see what was true when this version was made.
    basis_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

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
            ["pricing_configuration_id", "project_id"],
            ["pricing_configurations.id", "pricing_configurations.project_id"],
            name="config",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["unit_area_schedule_id", "project_id"],
            ["unit_area_schedules.id", "unit_area_schedules.project_id"],
            name="schedule",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["market_benchmark_id", "project_id"],
            ["market_benchmarks.id", "market_benchmarks.project_id"],
            name="benchmark",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("unit_id", "version_number"),
        UniqueConstraint("id", "project_id", name="version_project"),
        CheckConstraint(in_list("status", PRICING_STATUSES), name="status_allowed"),
        CheckConstraint(in_list("market_flag", MARKET_FLAGS), name="flag_allowed"),
        CheckConstraint("version_number >= 1", name="version_positive"),
        CheckConstraint("reference_price_ex_tax >= 0", name="price_nonneg"),
        CheckConstraint("base_area_value >= 0", name="base_nonneg"),
        CheckConstraint("premium_cap_adjustment <= 0", name="cap_not_positive"),
        CheckConstraint("paid_upgrade_total >= 0", name="upgrade_nonneg"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="valid_range"),
        # One live list price per unit. This is the constraint the whole module
        # is built around; the service takes the unit lock so the second writer
        # loses cleanly rather than here.
        Index(
            "uq_unit_price_versions_active",
            "unit_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_unit_price_versions_project_id_status", "project_id", "status"),
        Index("ix_unit_price_versions_unit_id_status", "unit_id", "status"),
    )


class UnitPriceComponent(Base):
    """One line of the waterfall that produced a price.

    Every line carries the quantity, the rate or factor, the calculated amount,
    any override and the final amount, and points at the configured rule it came
    from with a real foreign key. A component that said only "premium: 12,000"
    would leave the number exactly as unexplainable as the spreadsheet this
    system replaces.

    The sum of ``final_amount`` over a version's components equals that version's
    ``reference_price_ex_tax`` exactly. That is asserted in tests, not hoped for.
    """

    __tablename__ = "unit_price_components"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    unit_price_version_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    component_type: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)

    #: The measured or counted thing this line multiplies — an area, a number of
    #: parking bays. Null for a line that is simply an amount.
    quantity: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: What a percentage line was a percentage of.
    basis_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    rate: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    factor: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)

    calculated_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    override_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    final_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    override_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    area_rule_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    premium_rule_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    escalation_activation_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["unit_price_version_id", "project_id"],
            ["unit_price_versions.id", "unit_price_versions.project_id"],
            name="version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["area_rule_id", "project_id"],
            ["pricing_area_rules.id", "pricing_area_rules.project_id"],
            name="area_rule",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["premium_rule_id", "project_id"],
            ["pricing_premium_rules.id", "pricing_premium_rules.project_id"],
            name="premium_rule",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["escalation_activation_id", "project_id"],
            [
                "pricing_escalation_activations.id",
                "pricing_escalation_activations.project_id",
            ],
            name="activation",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("unit_price_version_id", "sequence"),
        CheckConstraint(in_list("component_type", COMPONENT_TYPES), name="type_allowed"),
        CheckConstraint("length(code) > 0", name="code_not_blank"),
        CheckConstraint("length(label) > 0", name="label_not_blank"),
        # An override is a decision somebody has to justify, so the reason and
        # the amount arrive together or not at all.
        CheckConstraint(
            "(override_amount IS NULL AND override_reason IS NULL) "
            "OR (override_amount IS NOT NULL AND override_reason IS NOT NULL)",
            name="override_complete",
        ),
        CheckConstraint(
            "final_amount = COALESCE(override_amount, calculated_amount)", name="final_matches"
        ),
        Index("ix_unit_price_components_version_id", "unit_price_version_id"),
    )
