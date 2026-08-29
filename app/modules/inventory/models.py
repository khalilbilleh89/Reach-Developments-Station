"""Inventory: the physical product catalogue of a development.

The Unit is the primary operating record of the whole platform. Everything a
later module records — a price, a sale, an installment, a cost, a handover —
will point at ``units.id``, so that identifier is a UUID that never changes.
``unit_reference`` is the human-facing label and is deliberately editable: a
project that renumbers ``A-101`` to ``A1-101`` must not lose its history.

Two structural rules shape most of this file.

**Hierarchy truth is stored once.** A Unit knows its Floor. Building and Phase
are reached through the Floor, never duplicated onto the Unit, because two
copies of the same fact are two things to disagree. ``project_id`` is the one
deliberate exception: it is the security scope every query filters on, and it is
held to the hierarchy by composite foreign keys rather than by hope — each level
carries a ``UNIQUE (id, project_id)`` so its child can reference the pair.

**Status is four facts, not one.** Commercial, legal, collection and delivery
answer different questions for different departments, and collapsing them into
``status`` is the design mistake that makes a system unable to say "sold but not
registered, paid but not handed over".

Constraint names are kept short: PostgreSQL truncates identifiers at 63
characters, and a truncated name no longer matches the metadata.
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

from app.db.base import MEASURE, RATE, Base, in_list

#: ``none_as_null`` is not optional. Without it SQLAlchemy stores Python ``None``
#: as the JSON scalar ``null``, which is *not* SQL NULL: ``'null'::jsonb IS NOT
#: NULL`` is true, so every ``IS NULL`` check — in a CHECK constraint, an index
#: predicate or an ordinary query — quietly stops meaning what it says.
NULLABLE_JSONB = JSONB(none_as_null=True)

# --------------------------------------------------------------------------- #
# Closed sets
# --------------------------------------------------------------------------- #

#: Machine states for a phase. Small and fixed: a phase whose states are data is
#: a workflow engine, and this PR does not build one. Local wording lives in
#: reference configuration; these are what the system reasons about.
PHASE_STATUSES = ("planning", "active", "on_hold", "completed", "cancelled")
PHASE_STATUS_PLANNING = "planning"

#: What kind of thing a unit is. Parking and storage are deliberately absent:
#: they are sub-assets, because pretending a parking bay is an apartment makes
#: every count, area and price downstream wrong.
ASSET_CLASSES = ("apartment", "villa", "townhouse", "commercial", "other")

#: The commercial life of a unit. Only the first three are reachable from this
#: module — the rest are created by real sales transactions in PR-MVP-05, and a
#: button that fakes them would put invented sales in the register.
COMMERCIAL_STATUSES = (
    "unreleased",
    "available",
    "held",
    "reserved",
    "contracted",
    "cancelled",
    "returned",
)
COMMERCIAL_STATUS_UNRELEASED = "unreleased"
COMMERCIAL_STATUS_AVAILABLE = "available"
COMMERCIAL_STATUS_HELD = "held"

#: Statuses Inventory may move a unit between. Anything outside this set belongs
#: to Sales.
INVENTORY_COMMERCIAL_STATUSES = frozenset(
    {COMMERCIAL_STATUS_UNRELEASED, COMMERCIAL_STATUS_AVAILABLE, COMMERCIAL_STATUS_HELD}
)

#: The legal life of a unit. Established here so the column exists and starts
#: honestly at ``not_started``; the transitions belong to Sales / Legal.
LEGAL_STATUSES = (
    "not_started",
    "eligible",
    "spa_in_progress",
    "spa_signed",
    "registration_in_progress",
    "registered",
    "title_transferred",
    "cancelled",
)

#: The collection life of a unit. Owned by PR-MVP-07.
COLLECTION_STATUSES = (
    "not_started",
    "current",
    "partially_paid",
    "overdue",
    "disputed",
    "cleared",
    "cancelled",
)

#: The delivery life of a unit. Owned by the construction and handover PRs.
DELIVERY_STATUSES = (
    "not_started",
    "under_construction",
    "ready",
    "handover_blocked",
    "handover_ready",
    "handed_over",
)

STATUS_NOT_STARTED = "not_started"

#: Which of the four status dimensions an event describes.
STATUS_DIMENSIONS = ("commercial", "legal", "collection", "delivery")
DIMENSION_COMMERCIAL = "commercial"

#: What an area measures. ``internal`` is the legal saleable interior and a
#: project may configure at most one active one — see the partial index below.
AREA_ROLES = ("internal", "outdoor", "ancillary", "plot", "gross", "other")
AREA_ROLE_INTERNAL = "internal"

#: The life of an area schedule. Approved schedules are immutable; a correction
#: is a new revision, so the measurement history stays readable.
AREA_SCHEDULE_STATUSES = ("draft", "approved", "superseded")
AREA_SCHEDULE_DRAFT = "draft"
AREA_SCHEDULE_APPROVED = "approved"
AREA_SCHEDULE_SUPERSEDED = "superseded"

#: Separately identifiable physical inventory that is not a unit.
SUB_ASSET_TYPES = ("parking", "storage", "other")

#: Whether a sub-asset transfers with its unit or can be dealt with separately.
TRANSFER_MODES = ("attached", "independent")

#: The entities a custom field may extend in this PR. Each has its own value
#: table with a real foreign key; there is no polymorphic entity_type/entity_id
#: table, because one without referential integrity is how orphan rows and
#: cross-tenant reads both arrive.
CUSTOM_FIELD_ENTITIES = ("project", "land_parcel", "unit")

#: What a custom field can hold. Deliberately six data types and nothing else:
#: no formula, no expression, no lookup query, no arbitrary JSON. This is
#: metadata, not programming.
CUSTOM_FIELD_DATA_TYPES = ("text", "integer", "decimal", "boolean", "date", "option")
CUSTOM_FIELD_TYPE_OPTION = "option"
CUSTOM_FIELD_TYPE_DECIMAL = "decimal"
CUSTOM_FIELD_TYPE_INTEGER = "integer"
CUSTOM_FIELD_TYPE_BOOLEAN = "boolean"
CUSTOM_FIELD_TYPE_DATE = "date"
CUSTOM_FIELD_TYPE_TEXT = "text"

#: Where a custom field applies. Company scope is absent on purpose: there is no
#: Company master in this system, and inventing a table to satisfy a label would
#: be the abstraction-first mistake this rebuild exists to avoid.
CUSTOM_FIELD_SCOPES = ("global", "country", "project", "unit_type")
SCOPE_GLOBAL = "global"
SCOPE_COUNTRY = "country"
SCOPE_PROJECT = "project"
SCOPE_UNIT_TYPE = "unit_type"

#: Reference-value categories this module validates newly assigned codes against.
CATEGORY_UNIT_TYPE = "unit_type"
CATEGORY_FLOOR_BAND = "floor_band"
CATEGORY_ORIENTATION = "orientation"
CATEGORY_VIEW_CLASS = "view_class"
CATEGORY_FURNISHING = "furnishing_specification"
CATEGORY_ACCESSIBILITY = "accessibility"
CATEGORY_GARDEN_CLASS = "garden_class"
CATEGORY_SUB_ASSET_SUBTYPE = "sub_asset_subtype"

#: Audit entity labels.
ENTITY_PHASE = "phase"
ENTITY_PHASE_ACCESS = "user_phase_access"
ENTITY_BUILDING = "building"
ENTITY_FLOOR = "floor"
ENTITY_UNIT = "unit"
ENTITY_SUB_ASSET = "inventory_sub_asset"
ENTITY_AREA_TYPE = "area_type"
ENTITY_AREA_SCHEDULE = "unit_area_schedule"
ENTITY_CUSTOM_FIELD = "custom_field_definition"
ENTITY_CUSTOM_VALUE = "custom_field_value"
ENTITY_IMPORT = "inventory_import"


# --------------------------------------------------------------------------- #
# Hierarchy
# --------------------------------------------------------------------------- #


class Phase(Base):
    """A delivery stage of a project, and the unit of inventory-level access.

    A phase is what a restricted member is granted or denied, so it is also a
    security boundary: see ``UserPhaseAccess`` and the ``phase_scope`` column on
    ``user_project_access``.
    """

    __tablename__ = "phases"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    #: Immutable once issued. Rows point at ``id``, so the code is a label.
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=PHASE_STATUS_PLANNING)
    planned_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_completion: Mapped[date | None] = mapped_column(Date, nullable=True)
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
        UniqueConstraint("project_id", "code"),
        # The composite target every child references, so "this building's phase
        # belongs to this building's project" is a foreign key rather than a
        # Python check somebody can forget to write.
        UniqueConstraint("id", "project_id", name="phase_project"),
        CheckConstraint("length(code) > 0", name="code_not_blank"),
        CheckConstraint("code = upper(code)", name="code_upper"),
        CheckConstraint("length(name) > 0", name="name_not_blank"),
        CheckConstraint(in_list("status", PHASE_STATUSES), name="status_allowed"),
        CheckConstraint(
            "planned_completion IS NULL OR planned_start IS NULL "
            "OR planned_completion >= planned_start",
            name="dates_ordered",
        ),
        Index("ix_phases_project_id_status", "project_id", "status"),
    )


class UserPhaseAccess(Base):
    """Which phases a member restricted to ``selected`` scope may see.

    Meaningless without a project membership, so ``(project_id, user_id)`` is a
    real foreign key into ``user_project_access`` rather than something the
    service checks and a later refactor forgets. Likewise the phase must belong
    to the same project, which is the second composite key below.
    """

    __tablename__ = "user_phase_access"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    phase_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "user_id"],
            ["user_project_access.project_id", "user_project_access.user_id"],
            name="membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        # One row per pairing, ever. Re-granting reactivates it so the
        # grant/revoke history stays on a single line.
        UniqueConstraint("user_id", "phase_id"),
        Index("ix_user_phase_access_user_id", "user_id"),
    )


class Building(Base):
    """A building within a phase."""

    __tablename__ = "buildings"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    phase_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    zone: Mapped[str | None] = mapped_column(String(120), nullable=True)
    block: Mapped[str | None] = mapped_column(String(120), nullable=True)
    entrance_wing: Mapped[str | None] = mapped_column(String(120), nullable=True)
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
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("phase_id", "code"),
        UniqueConstraint("id", "project_id", name="building_project"),
        CheckConstraint("length(code) > 0", name="code_not_blank"),
        CheckConstraint("code = upper(code)", name="code_upper"),
        CheckConstraint("length(name) > 0", name="name_not_blank"),
        Index("ix_buildings_phase_id", "phase_id"),
    )


class Floor(Base):
    """A floor within a building.

    ``code`` is a string because real buildings have B2, B1, GF, M, 01 and RF.
    Forcing an integer identity loses the mezzanine and the roof. ``level_number``
    carries optional numeric ordering context for the floors that have one.
    """

    __tablename__ = "floors"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    building_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    level_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
            ["building_id", "project_id"],
            ["buildings.id", "buildings.project_id"],
            name="building",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("building_id", "code"),
        UniqueConstraint("id", "project_id", name="floor_project"),
        CheckConstraint("length(code) > 0", name="code_not_blank"),
        CheckConstraint("code = upper(code)", name="code_upper"),
        CheckConstraint("length(label) > 0", name="label_not_blank"),
        Index("ix_floors_building_id", "building_id"),
    )


# --------------------------------------------------------------------------- #
# Unit
# --------------------------------------------------------------------------- #


class Unit(Base):
    """The primary operating record of the platform.

    ``id`` is permanent and is what every later domain will reference.
    ``unit_reference`` is the editable business label; correcting it must never
    disturb identity, which is the whole reason the two are separate columns.

    Phase and Building are absent by design: they are reached through the floor.
    """

    __tablename__ = "units"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    floor_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: Unique on its floor: "101" recurs in every building of every project.
    unit_number: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Unique in the project and shown to people. Editable, and audited.
    unit_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Classification
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_type_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_maid_room: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_duplex: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_penthouse: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    furnishing_specification_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Recurring commercial features. Explicit columns rather than custom fields
    # because pricing in PR-MVP-04 must be able to rely on them being there.
    floor_band_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    orientation_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    view_class_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_corner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pool_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accessibility_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    garden_class_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: A fraction of one: 0.450000 is 45% of the plot.
    plot_coverage_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)

    # Four independent status dimensions. Never one `status` column.
    commercial_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=COMMERCIAL_STATUS_UNRELEASED
    )
    legal_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=STATUS_NOT_STARTED
    )
    collection_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=STATUS_NOT_STARTED
    )
    delivery_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=STATUS_NOT_STARTED
    )

    # Release controls. Each is owned by a different role; see permissions.py.
    drawings_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    legal_sale_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Set by PR-MVP-04 when an approved price exists. No API in this PR writes
    #: it: a button that did would be a pricing approval with no price behind it.
    pricing_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    release_batch: Mapped[str | None] = mapped_column(String(64), nullable=True)
    block_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

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
            ["floor_id", "project_id"],
            ["floors.id", "floors.project_id"],
            name="floor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "unit_reference"),
        UniqueConstraint("floor_id", "unit_number"),
        UniqueConstraint("id", "project_id", name="unit_project"),
        CheckConstraint("length(unit_number) > 0", name="number_not_blank"),
        CheckConstraint("length(unit_reference) > 0", name="reference_not_blank"),
        CheckConstraint(in_list("asset_class", ASSET_CLASSES), name="asset_class_allowed"),
        CheckConstraint(in_list("commercial_status", COMMERCIAL_STATUSES), name="commercial_ok"),
        CheckConstraint(in_list("legal_status", LEGAL_STATUSES), name="legal_ok"),
        CheckConstraint(in_list("collection_status", COLLECTION_STATUSES), name="collection_ok"),
        CheckConstraint(in_list("delivery_status", DELIVERY_STATUSES), name="delivery_ok"),
        CheckConstraint("bedrooms IS NULL OR bedrooms >= 0", name="bedrooms_nonneg"),
        CheckConstraint("bathrooms IS NULL OR bathrooms >= 0", name="bathrooms_nonneg"),
        CheckConstraint(
            "plot_coverage_fraction IS NULL "
            "OR (plot_coverage_fraction >= 0 AND plot_coverage_fraction <= 1)",
            name="coverage_range",
        ),
        Index("ix_units_project_id_commercial_status", "project_id", "commercial_status"),
        Index("ix_units_project_id_unit_type_code", "project_id", "unit_type_code"),
        Index("ix_units_floor_id", "floor_id"),
    )


class UnitStatusEvent(Base):
    """One recorded movement of a unit on one status dimension.

    Append-only: no update path, no delete path. This is operational status
    history — what the business did and why — and is deliberately separate from
    the audit trail, which records who changed which field through which
    request. Both exist because they answer different questions.
    """

    __tablename__ = "unit_status_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )
    dimension: Mapped[str] = mapped_column(String(16), nullable=False)
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(in_list("dimension", STATUS_DIMENSIONS), name="dimension_allowed"),
        CheckConstraint("from_status <> to_status", name="status_changed"),
        Index("ix_unit_status_events_unit_id_dimension", "unit_id", "dimension"),
    )


class InventorySubAsset(Base):
    """A parking bay, a storage room, or another separately identifiable asset.

    One physical thing is one row. There are deliberately no ``parking_1``,
    ``parking_2`` columns on the unit: a unit with two bays has two rows, and
    counts are derived from them.
    """

    __tablename__ = "inventory_sub_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    floor_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    linked_unit_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    asset_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subtype_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    area: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    transfer_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="attached")
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
            ["floor_id", "project_id"],
            ["floors.id", "floors.project_id"],
            name="floor",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["linked_unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "asset_reference"),
        CheckConstraint("length(asset_reference) > 0", name="reference_not_blank"),
        CheckConstraint(in_list("asset_type", SUB_ASSET_TYPES), name="type_allowed"),
        CheckConstraint(in_list("transfer_mode", TRANSFER_MODES), name="transfer_allowed"),
        CheckConstraint("area IS NULL OR area >= 0", name="area_nonneg"),
        Index("ix_inventory_sub_assets_linked_unit_id_asset_type", "linked_unit_id", "asset_type"),
    )


# --------------------------------------------------------------------------- #
# Areas
# --------------------------------------------------------------------------- #


class AreaType(Base):
    """A kind of area a project measures, and the factor that weights it.

    The factor never changes a raw area. It only decides how much of that area
    counts toward the weighted saleable figure a commercial team quotes on. Both
    numbers are shown, and the raw one is always the legal one.
    """

    __tablename__ = "area_types"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    area_role: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(16), nullable=False, default="sqm")
    #: An explicit fraction of one: 0.500000 means half this area counts.
    weight_factor: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    required_for_release: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
        UniqueConstraint("project_id", "code"),
        UniqueConstraint("id", "project_id", name="area_type_project"),
        CheckConstraint("length(code) > 0", name="code_not_blank"),
        CheckConstraint("code = upper(code)", name="code_upper"),
        CheckConstraint(in_list("area_role", AREA_ROLES), name="role_allowed"),
        CheckConstraint("weight_factor >= 0 AND weight_factor <= 1", name="factor_range"),
        # At most one active internal area per project. Two would make "the legal
        # area" ambiguous, which is the one thing this table must never be.
        Index(
            "uq_area_types_one_internal",
            "project_id",
            unique=True,
            postgresql_where=text("area_role = 'internal' AND is_active"),
        ),
    )


class UnitAreaSchedule(Base):
    """One measured revision of a unit's areas.

    Areas change as design develops, and a development that silently overwrites
    the approved measurement it sold against cannot answer a dispute. Approved
    schedules are immutable; a correction is a new revision that supersedes the
    old one, which stays readable.
    """

    __tablename__ = "unit_area_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    revision_code: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=AREA_SCHEDULE_DRAFT)
    measurement_standard: Mapped[str | None] = mapped_column(String(120), nullable=True)
    plan_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    measured_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: The measurer's confirmation that this revision was checked against the
    #: drawing it claims to come from. Approval refuses without it.
    reconciled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("unit_id", "revision_code"),
        UniqueConstraint("id", "project_id", name="schedule_project"),
        CheckConstraint("length(revision_code) > 0", name="revision_not_blank"),
        CheckConstraint(in_list("status", AREA_SCHEDULE_STATUSES), name="status_allowed"),
        CheckConstraint(
            "(status <> 'approved') "
            "OR (approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL AND reconciled)",
            name="approved_complete",
        ),
        # One current approved schedule per unit, enforced by the database rather
        # than by whichever transaction happened to read first.
        Index(
            "uq_unit_area_schedules_current",
            "unit_id",
            unique=True,
            postgresql_where=text("status = 'approved'"),
        ),
        Index("ix_unit_area_schedules_unit_id_status", "unit_id", "status"),
    )


class UnitAreaValue(Base):
    """One measured area of one type on one schedule."""

    __tablename__ = "unit_area_values"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    unit_area_schedule_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    area_type_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    raw_area: Mapped[Decimal] = mapped_column(MEASURE, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["unit_area_schedule_id", "project_id"],
            ["unit_area_schedules.id", "unit_area_schedules.project_id"],
            name="schedule",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["area_type_id", "project_id"],
            ["area_types.id", "area_types.project_id"],
            name="area_type",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("unit_area_schedule_id", "area_type_id"),
        CheckConstraint("raw_area >= 0", name="area_nonneg"),
    )


# --------------------------------------------------------------------------- #
# Configurable fields
# --------------------------------------------------------------------------- #


class CustomFieldDefinition(Base):
    """A constrained extension field, not a dynamic schema.

    A custom field adds a fact the product did not anticipate. It can never
    redefine one it did: identity, hierarchy, status dimensions, release control
    and anything monetary are core columns, and ``field_key`` is checked against
    a reserved list so a field called ``commercial_status`` cannot exist.

    There is no expression language here. ``data_type`` admits six kinds of
    value and validation is bounds, length, pattern and option membership. A
    field that could execute something would be a programming environment with
    no review process.
    """

    __tablename__ = "custom_field_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Lowercase machine key, immutable once created: values are stored against
    #: the definition, and renaming the key would reinterpret them.
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data_type: Mapped[str] = mapped_column(String(16), nullable=False)
    unit_of_measure: Mapped[str | None] = mapped_column(String(32), nullable=True)
    help_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: The one transition-specific rule this PR implements. A general dependency
    #: language would be a rules engine; the concrete requirement is "a unit is
    #: not complete until this is filled in", so that is what exists.
    required_for_release: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    minimum_value: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    maximum_value: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    regex_pattern: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_unique: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    country_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("country_packs.id", ondelete="RESTRICT"), nullable=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=True
    )
    unit_type_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: Role keys from the fixed catalogue. NULL means ordinary entity visibility.
    visible_role_keys: Mapped[list[str] | None] = mapped_column(NULLABLE_JSONB, nullable=True)
    editable_role_keys: Mapped[list[str] | None] = mapped_column(NULLABLE_JSONB, nullable=True)
    sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    filterable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    groupable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dashboard_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    export_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(in_list("entity_type", CUSTOM_FIELD_ENTITIES), name="entity_allowed"),
        CheckConstraint(in_list("data_type", CUSTOM_FIELD_DATA_TYPES), name="type_allowed"),
        CheckConstraint(in_list("scope_type", CUSTOM_FIELD_SCOPES), name="scope_allowed"),
        CheckConstraint("field_key = lower(field_key)", name="key_lower"),
        CheckConstraint("length(field_key) > 0", name="key_not_blank"),
        # Each scope names exactly the columns it needs and no others, so a
        # "project" field cannot quietly carry a country pack nobody reads.
        CheckConstraint(
            "(scope_type = 'global' AND country_pack_id IS NULL AND project_id IS NULL "
            "AND unit_type_code IS NULL) "
            "OR (scope_type = 'country' AND country_pack_id IS NOT NULL AND project_id IS NULL "
            "AND unit_type_code IS NULL) "
            "OR (scope_type = 'project' AND project_id IS NOT NULL AND country_pack_id IS NULL "
            "AND unit_type_code IS NULL) "
            "OR (scope_type = 'unit_type' AND project_id IS NOT NULL "
            "AND unit_type_code IS NOT NULL AND country_pack_id IS NULL)",
            name="scope_columns",
        ),
        # Unit-type scope only means something for units.
        CheckConstraint(
            "scope_type <> 'unit_type' OR entity_type = 'unit'", name="unit_type_scope_is_unit"
        ),
        CheckConstraint(
            "minimum_value IS NULL OR maximum_value IS NULL OR maximum_value >= minimum_value",
            name="bounds_ordered",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="validity_ordered",
        ),
        # A sensitive field with no explicit audience would be visible to every
        # project member, which is the opposite of what the flag claims.
        CheckConstraint(
            "NOT sensitive OR visible_role_keys IS NOT NULL", name="sensitive_needs_roles"
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        # Exact duplicates are refused by the database. Broader overlap between
        # scopes is decided in the service, which can explain which existing
        # definition conflicts.
        Index(
            "uq_custom_field_definitions_scope",
            "entity_type",
            "field_key",
            "scope_type",
            "country_pack_id",
            "project_id",
            "unit_type_code",
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("is_active"),
        ),
        Index("ix_custom_field_definitions_entity_type_scope_type", "entity_type", "scope_type"),
    )


class CustomFieldOption(Base):
    """One allowed choice of an ``option`` custom field.

    Retiring an option stops it being assigned; it does not invalidate the rows
    that already carry it, because configuration moving on is not a reason to
    rewrite history.
    """

    __tablename__ = "custom_field_options"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("custom_field_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("definition_id", "code"),
        CheckConstraint("length(code) > 0", name="code_not_blank"),
    )


def _value_table_args(table: str, entity_column: str) -> tuple[object, ...]:
    """The uniqueness rules every custom value table needs.

    One value per (definition, entity), and — for a definition marked unique —
    one entity per canonical value, enforced by a partial index so the race two
    concurrent writers would otherwise win together is decided by PostgreSQL.
    """
    return (
        UniqueConstraint("definition_id", entity_column),
        Index(
            f"uq_{table}_unique_value",
            "definition_id",
            "unique_value",
            unique=True,
            postgresql_where=text("unique_value IS NOT NULL"),
        ),
    )


class ProjectCustomFieldValue(Base):
    """A custom value recorded against a project."""

    __tablename__ = "project_custom_field_values"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("custom_field_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    #: NULL means cleared. The row survives so the audit trail has both sides.
    value_json: Mapped[object | None] = mapped_column(NULLABLE_JSONB, nullable=True)
    #: Canonical text form, set only when the definition is unique.
    unique_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = _value_table_args("project_custom_field_values", "project_id")


class LandParcelCustomFieldValue(Base):
    """A custom value recorded against a land parcel."""

    __tablename__ = "land_parcel_custom_field_values"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("custom_field_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parcel_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("land_parcels.id", ondelete="RESTRICT"), nullable=False
    )
    value_json: Mapped[object | None] = mapped_column(NULLABLE_JSONB, nullable=True)
    unique_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = _value_table_args("land_parcel_custom_field_values", "parcel_id")


class UnitCustomFieldValue(Base):
    """A custom value recorded against a unit."""

    __tablename__ = "unit_custom_field_values"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("custom_field_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )
    value_json: Mapped[object | None] = mapped_column(NULLABLE_JSONB, nullable=True)
    unique_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = _value_table_args("unit_custom_field_values", "unit_id")
