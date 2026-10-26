"""Project-level consultant and design-delivery truth, never construction progress."""

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
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MONEY, Base, in_list

ENGAGEMENT_STATUSES = ("draft", "active", "completed", "terminated")
DISCIPLINE_STATUSES = ("not_started", "active", "completed", "on_hold")
STAGE_STATUSES = ("not_started", "in_progress", "completed", "on_hold", "cancelled")
DELIVERABLE_STATUSES = (
    "not_started",
    "in_progress",
    "submitted",
    "accepted",
    "superseded",
    "cancelled",
)


class ConsultantStagePayment(Base):
    """An attribution link, never a second source of cash or payment amounts."""

    __tablename__ = "consultant_stage_payments"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    stage_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    movement_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False, unique=True
    )
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="ce_payment_project"),
        UniqueConstraint("project_id", "request_id", name="ce_payment_request"),
        ForeignKeyConstraint(
            ["stage_id", "project_id"],
            ["consultant_design_stages.id", "consultant_design_stages.project_id"],
            ondelete="RESTRICT",
            name="ce_payment_stage",
        ),
        ForeignKeyConstraint(
            ["movement_id", "project_id"],
            ["cashflow_development_movements.id", "cashflow_development_movements.project_id"],
            ondelete="RESTRICT",
            name="ce_payment_movement",
        ),
    )


class ConsultantPaymentProof(Base):
    __tablename__ = "consultant_payment_proofs"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    payment_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    document: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["payment_id", "project_id"],
            ["consultant_stage_payments.id", "consultant_stage_payments.project_id"],
            ondelete="RESTRICT",
            name="ce_proof_payment",
        ),
        CheckConstraint("octet_length(document) BETWEEN 1 AND 10485760", name="document_size"),
        CheckConstraint("length(trim(filename)) > 0", name="filename_present"),
    )


class ConsultantEngagement(Base):
    __tablename__ = "consultant_engagements"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    engagement_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="main", server_default=text("'main'")
    )
    consultant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    agreement_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    agreement_date: Mapped[date | None] = mapped_column(Date)
    planned_start_date: Mapped[date | None] = mapped_column(Date)
    planned_completion_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    scope_summary: Mapped[str | None] = mapped_column(String(2000))
    notes: Mapped[str | None] = mapped_column(String(2000))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="ce_engagement_project"),
        CheckConstraint("length(trim(consultant_name)) > 0", name="consultant_name_present"),
        CheckConstraint("length(trim(agreement_reference)) > 0", name="agreement_ref_present"),
        CheckConstraint(in_list("status", ENGAGEMENT_STATUSES), name="status_ok"),
        CheckConstraint("engagement_type IN ('main', 'subconsultant')", name="type_ok"),
        CheckConstraint(
            "planned_start_date IS NULL OR planned_completion_date IS NULL "
            "OR planned_completion_date >= planned_start_date",
            name="planned_dates_ordered",
        ),
        Index(
            "uq_ce_one_active_engagement",
            "project_id",
            unique=True,
            postgresql_where=text("status = 'active' AND engagement_type = 'main'"),
        ),
    )


class ConsultantDiscipline(Base):
    __tablename__ = "consultant_disciplines"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    engagement_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    lead_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="not_started")
    notes: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["engagement_id", "project_id"],
            ["consultant_engagements.id", "consultant_engagements.project_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="ce_discipline_project"),
        UniqueConstraint("engagement_id", "normalized_name", name="uq_ce_discipline_name"),
        CheckConstraint("length(trim(name)) > 0", name="name_present"),
        CheckConstraint(in_list("status", DISCIPLINE_STATUSES), name="status_ok"),
    )


class ConsultantDesignStage(Base):
    __tablename__ = "consultant_design_stages"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    engagement_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_date: Mapped[date | None] = mapped_column(Date)
    forecast_date: Mapped[date | None] = mapped_column(Date)
    actual_completion_date: Mapped[date | None] = mapped_column(Date)
    agreed_payment_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="not_started")
    notes: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["engagement_id", "project_id"],
            ["consultant_engagements.id", "consultant_engagements.project_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", name="ce_stage_project"),
        UniqueConstraint("engagement_id", "sequence", name="uq_ce_stage_sequence"),
        CheckConstraint("length(trim(name)) > 0", name="name_present"),
        CheckConstraint("sequence > 0", name="sequence_positive"),
        CheckConstraint(
            "agreed_payment_amount IS NULL OR agreed_payment_amount >= 0",
            name="payment_nonnegative",
        ),
        CheckConstraint(in_list("status", STAGE_STATUSES), name="status_ok"),
        CheckConstraint(
            "status <> 'completed' OR actual_completion_date IS NOT NULL", name="completed_has_date"
        ),
    )


class ConsultantDeliverable(Base):
    __tablename__ = "consultant_deliverables"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    engagement_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    stage_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    discipline_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    revision_reference: Mapped[str | None] = mapped_column(String(120))
    document_reference: Mapped[str | None] = mapped_column(String(500))
    due_date: Mapped[date | None] = mapped_column(Date)
    submitted_date: Mapped[date | None] = mapped_column(Date)
    accepted_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="not_started")
    notes: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["engagement_id", "project_id"],
            ["consultant_engagements.id", "consultant_engagements.project_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["stage_id", "project_id"],
            ["consultant_design_stages.id", "consultant_design_stages.project_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["discipline_id", "project_id"],
            ["consultant_disciplines.id", "consultant_disciplines.project_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("length(trim(name)) > 0", name="name_present"),
        CheckConstraint(in_list("status", DELIVERABLE_STATUSES), name="status_ok"),
        CheckConstraint(
            "status NOT IN ('submitted', 'accepted') OR submitted_date IS NOT NULL",
            name="submitted_has_date",
        ),
        CheckConstraint(
            "status <> 'accepted' OR accepted_date IS NOT NULL", name="accepted_has_date"
        ),
    )
