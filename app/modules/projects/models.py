"""Project, land, planning, permit and document-reference tables.

Factual development-control records. Nothing here values land, forecasts a
permit, or derives a development yield: those belong to later roadmap PRs, and
only once there is a modelled development to reason about.

Constraint names are kept deliberately short. PostgreSQL truncates identifiers
at 63 characters, and a truncated name no longer matches the metadata, which is
what makes Alembic autogenerate report permanent drift.
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
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MEASURE, MONEY, RATE, Base, in_list

#: Floor area ratio. Not a fraction of one — an FAR of 4.5 is ordinary.
RATIO = Numeric(12, 4)

#: Machine states for a project. Local display wording stays in reference
#: configuration; these are what the system reasons about.
PROJECT_STATUSES = (
    "setup",
    "predevelopment",
    "active",
    "on_hold",
    "completed",
    "cancelled",
)

#: The one status in which the legal and monetary basis of a project may still
#: be corrected. See :func:`app.modules.projects.service.update_project`.
PROJECT_STATUS_SETUP = "setup"

#: How much of a project's inventory a member may see. The column lives on
#: ``user_project_access`` because it narrows that membership, so the closed set
#: lives here beside it; the phase grants it points at are inventory's.
#: ``all`` is the historical behaviour and the default — every row that existed
#: before phases did means it, and must keep meaning it.
PHASE_SCOPES = ("all", "selected")
PHASE_SCOPE_ALL = "all"
PHASE_SCOPE_SELECTED = "selected"

#: Machine states for a permit. Fixed rather than configurable because system
#: behaviour depends on their meaning — a workflow whose states are data is a
#: workflow engine, and this PR does not build one.
PERMIT_STATUSES = (
    "not_started",
    "preparing",
    "submitted",
    "accepted_for_review",
    "comments_received",
    "resubmission",
    "approved_with_conditions",
    "issued",
    "expired",
    "renewed",
    "rejected",
    "on_hold",
    "withdrawn",
)

PERMIT_STATUS_NOT_STARTED = "not_started"
PERMIT_STATUS_SUBMITTED = "submitted"

#: Reference-value categories this module names against Settings. Listed here so
#: the module never invents a category string inline.
#:
#: Two kinds live in this list since PR-V2-01, and the difference matters.
#: ``project_type``, ``permit_type`` and ``document_type`` are *validated*: a
#: record carrying one of them is refused unless the value is configured, because
#: a register that cannot reliably tell a Building Permit from a Planning
#: Approval cannot be filtered or reported on. ``ownership_type``,
#: ``title_status`` and ``zoning_class`` are *suggested*: a parcel stores the
#: wording on its own title and planning record as text, and these categories
#: survive only so a screen can offer what the jurisdiction usually says.
#: Nothing refuses a parcel for not matching them.
CATEGORY_PROJECT_TYPE = "project_type"
CATEGORY_OWNERSHIP_TYPE = "ownership_type"
CATEGORY_TITLE_STATUS = "title_status"
CATEGORY_ZONING_CLASS = "zoning_class"
CATEGORY_PERMIT_TYPE = "permit_type"
CATEGORY_DOCUMENT_TYPE = "document_type"


class Project(Base):
    """One development project: the root of every record in this module."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: Human-readable and system-wide unique, but never the identity: rows point
    #: at ``id`` so a project can be renamed without rewriting its history.
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    developer_entity: Mapped[str] = mapped_column(String(200), nullable=False)
    country_pack_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("country_packs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: Plain coordinates. No GIS, no geocoding, no map SDK.
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    project_type_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=PROJECT_STATUS_SETUP)
    #: Amounts recorded anywhere under this project are denominated in the base
    #: currency. Reporting currency is recorded, never converted to: there is no
    #: FX table and no rate source in this MVP.
    base_currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    reporting_currency_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=False
    )
    #: Defaulted from the country pack at creation, then owned by the project as
    #: its own explicit operating baseline.
    fiscal_year_start_month: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    planned_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_completion: Mapped[date | None] = mapped_column(Date, nullable=True)
    project_manager_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("length(code) > 0", name="code_not_blank"),
        CheckConstraint("code = upper(code)", name="code_upper"),
        CheckConstraint("length(name) > 0", name="name_not_blank"),
        CheckConstraint(in_list("status", PROJECT_STATUSES), name="status_allowed"),
        CheckConstraint("fiscal_year_start_month BETWEEN 1 AND 12", name="fiscal_month_range"),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)", name="latitude_range"
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="longitude_range",
        ),
        CheckConstraint(
            "planned_start IS NULL OR planned_completion IS NULL "
            "OR planned_completion >= planned_start",
            name="planned_dates_ordered",
        ),
        Index("ix_projects_status", "status"),
    )


class UserProjectAccess(Base):
    """Whether a user may see a project. Not what they may do once inside.

    Roles stay in the fixed catalogue from PR-MVP-01. Deliberately carries no
    ``role_id``, no resource type and no permission string: this row answers one
    question, and a table that answers one question cannot grow into an ACL
    engine by accident.
    """

    __tablename__ = "user_project_access"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Whether this membership reaches every phase or only the ones explicitly
    #: granted in ``user_phase_access``. Added in PR-MVP-03, when Phase became
    #: real; existing rows default to ``all``, which is exactly what they meant.
    phase_scope: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PHASE_SCOPE_ALL, server_default=PHASE_SCOPE_ALL
    )
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
        # One row per pairing, ever. Re-granting reactivates the existing row so
        # the grant/revoke history stays on a single line. Also the composite
        # key ``user_phase_access`` points at: a phase grant without a project
        # membership behind it is a foreign-key violation, not a service check.
        UniqueConstraint("project_id", "user_id"),
        CheckConstraint(in_list("phase_scope", PHASE_SCOPES), name="phase_scope_allowed"),
        Index("ix_user_project_access_user_id", "user_id"),
    )


class LandParcel(Base):
    """A parcel of land under a project: a factual register, not a valuation."""

    __tablename__ = "land_parcels"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    plot_number: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Nullable on purpose: title work is often incomplete at acquisition, and a
    #: register that cannot record an early-stage parcel is not used.
    title_deed_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cadastral_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    land_area: Mapped[Decimal] = mapped_column(MEASURE, nullable=False)
    #: Defaults from the country pack; overridable where the legal record
    #: genuinely uses the other supported unit. Nothing converts between them.
    area_unit: Mapped[str] = mapped_column(String(8), nullable=False)
    #: Free text since PR-V2-01. Ownership wording is a jurisdiction and deal
    #: fact — "Freehold", "75% acquired, balance under negotiation" — and a
    #: closed dictionary made the register refuse the truth on the deed.
    ownership_type: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ownership_share_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    acquisition_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Denominated in the owning project's base currency.
    purchase_price: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    acquisition_fees: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    seller: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: Free text, as ownership is. A title office says "Transfer pending" or
    #: "Mortgage release pending" in its own words, and the register records
    #: what it said.
    title_status: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: The authority's classification *as issued* — "Residential B",
    #: "Special development zone". Not the planning envelope: that is
    #: :class:`PlanningControl`, and conflating the two loses both.
    zoning: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Physical facts. Management records, not engineering analysis.
    frontage: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    road_access: Mapped[str | None] = mapped_column(String(500), nullable=True)
    topography: Mapped[str | None] = mapped_column(String(500), nullable=True)
    geotechnical_status: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contamination_status: Mapped[str | None] = mapped_column(String(500), nullable=True)
    flood_drainage_status: Mapped[str | None] = mapped_column(String(500), nullable=True)
    archaeology_heritage_status: Mapped[str | None] = mapped_column(String(500), nullable=True)

    #: Tri-state on purpose: NULL is "not yet established", which is different
    #: from a surveyed "no".
    power_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    water_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sewer_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stormwater_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    telecom_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    utility_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    easements: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    encroachments: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    constraints_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", "plot_number"),
        CheckConstraint("length(plot_number) > 0", name="plot_not_blank"),
        CheckConstraint("land_area > 0", name="land_area_positive"),
        CheckConstraint("area_unit IN ('sqm', 'sqft')", name="area_unit_allowed"),
        CheckConstraint(
            "ownership_share_fraction IS NULL "
            "OR (ownership_share_fraction > 0 AND ownership_share_fraction <= 1)",
            name="share_range",
        ),
        CheckConstraint("purchase_price IS NULL OR purchase_price >= 0", name="price_non_negative"),
        CheckConstraint(
            "acquisition_fees IS NULL OR acquisition_fees >= 0", name="fees_non_negative"
        ),
        CheckConstraint("frontage IS NULL OR frontage >= 0", name="frontage_non_negative"),
        # A classification is either recorded or not yet established. An empty
        # string is neither, and it reads on screen as the second while
        # sorting, filtering and exporting as the first.
        CheckConstraint(
            "ownership_type IS NULL OR length(btrim(ownership_type)) > 0",
            name="ownership_type_not_blank",
        ),
        CheckConstraint(
            "title_status IS NULL OR length(btrim(title_status)) > 0",
            name="title_status_not_blank",
        ),
        CheckConstraint("zoning IS NULL OR length(btrim(zoning)) > 0", name="zoning_not_blank"),
    )


class PlanningControl(Base):
    """The current planning envelope for one parcel.

    One row per parcel: this is the standing baseline, not a scenario set. The
    audit trail carries what it used to say.
    """

    __tablename__ = "planning_controls"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: Denormalised from the parcel so every project-scoped query can filter on
    #: one column without a join. Kept consistent by the service.
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("land_parcels.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    permitted_uses: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    site_coverage_rate_fraction: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    far_ratio: Mapped[Decimal | None] = mapped_column(RATIO, nullable=True)
    maximum_gfa: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    maximum_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maximum_height: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    front_setback: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    side_setback: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    rear_setback: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    #: Free text: parking rules are expressed in ratios, tables and exemptions
    #: that differ per authority, and a number would lose the rule.
    parking_requirement: Mapped[str | None] = mapped_column(String(500), nullable=True)
    minimum_plot_area: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    minimum_frontage: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    density: Mapped[Decimal | None] = mapped_column(MEASURE, nullable=True)
    exclusions: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    variance_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    variance_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "site_coverage_rate_fraction IS NULL "
            "OR (site_coverage_rate_fraction >= 0 AND site_coverage_rate_fraction <= 1)",
            name="coverage_range",
        ),
        CheckConstraint("far_ratio IS NULL OR far_ratio >= 0", name="far_non_negative"),
        CheckConstraint("maximum_gfa IS NULL OR maximum_gfa >= 0", name="gfa_non_negative"),
        CheckConstraint("maximum_floors IS NULL OR maximum_floors > 0", name="floors_positive"),
        CheckConstraint("maximum_height IS NULL OR maximum_height >= 0", name="height_non_neg"),
        CheckConstraint("front_setback IS NULL OR front_setback >= 0", name="front_non_neg"),
        CheckConstraint("side_setback IS NULL OR side_setback >= 0", name="side_non_neg"),
        CheckConstraint("rear_setback IS NULL OR rear_setback >= 0", name="rear_non_neg"),
        CheckConstraint(
            "minimum_plot_area IS NULL OR minimum_plot_area >= 0", name="min_area_non_neg"
        ),
        CheckConstraint(
            "minimum_frontage IS NULL OR minimum_frontage >= 0", name="min_frontage_non_neg"
        ),
        CheckConstraint("density IS NULL OR density >= 0", name="density_non_neg"),
    )


class Permit(Base):
    """One statutory application and its current standing.

    ``status`` is the current state only. Every change to it is an appended
    :class:`PermitStatusEvent`; the column exists so the register can be read
    without replaying history.
    """

    __tablename__ = "permits"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("land_parcels.id", ondelete="RESTRICT"), nullable=True
    )
    permit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    permit_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    authority: Mapped[str] = mapped_column(String(200), nullable=False)
    #: The authority's own reference, which usually does not exist until issue.
    authority_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prerequisite_permit_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("permits.id", ondelete="RESTRICT"), nullable=True
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    consultant: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PERMIT_STATUS_NOT_STARTED
    )
    status_effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    planned_submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    forecast_submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    accepted_for_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    comments_received_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resubmission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    forecast_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    renewal_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    statutory_sla_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Denominated in the owning project's base currency. Nothing accrues it.
    fee_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    conditions: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    #: Management judgement, not an inferred schedule. There is no CPM here.
    is_blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_critical_path: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    next_action: Mapped[str | None] = mapped_column(String(500), nullable=True)
    escalation_owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", "permit_code"),
        CheckConstraint("length(permit_code) > 0", name="code_not_blank"),
        CheckConstraint(in_list("status", PERMIT_STATUSES), name="status_allowed"),
        CheckConstraint("fee_amount IS NULL OR fee_amount >= 0", name="fee_non_negative"),
        CheckConstraint(
            "statutory_sla_days IS NULL OR statutory_sla_days > 0", name="sla_positive"
        ),
        CheckConstraint("prerequisite_permit_id <> id", name="prereq_not_self"),
        Index("ix_permits_status", "status"),
        Index("ix_permits_owner_user_id", "owner_user_id"),
        Index("ix_permits_project_blocking", "project_id", "is_blocking"),
        Index("ix_permits_project_critical", "project_id", "is_critical_path"),
    )


class PermitStatusEvent(Base):
    """One recorded movement of a permit between states.

    Append-only: there is no update path and no delete path, in the API or in
    the service. A permit register whose history can be rewritten is not a
    record of what the authority actually did.
    """

    __tablename__ = "permit_status_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    permit_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("permits.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
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
        CheckConstraint(in_list("from_status", PERMIT_STATUSES), name="from_allowed"),
        CheckConstraint(in_list("to_status", PERMIT_STATUSES), name="to_allowed"),
        CheckConstraint("from_status <> to_status", name="status_changed"),
    )


class DocumentReference(Base):
    """A pointer to a document that lives somewhere else.

    Deliberately a reference, not a document store: no upload, no blob storage,
    no versioning, no parsing. The record says which evidence supports a fact
    and where to find it.
    """

    __tablename__ = "document_references"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("land_parcels.id", ondelete="RESTRICT"), nullable=True
    )
    permit_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("permits.id", ondelete="RESTRICT"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    document_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("length(title) > 0", name="title_not_blank"),
        # A reference attaches to at most one child. Attaching to both would
        # make "which record does this evidence support" unanswerable.
        CheckConstraint(
            "parcel_id IS NULL OR permit_id IS NULL",
            name="single_attachment",
        ),
        Index("ix_document_references_parcel_id", "parcel_id"),
        Index("ix_document_references_permit_id", "permit_id"),
    )
