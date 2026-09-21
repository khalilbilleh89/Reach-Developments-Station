"""Project-owned buyer checklists; commercial and legal sources remain authoritative."""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OperationPipeline(Base):
    __tablename__ = "operation_pipelines"
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="RESTRICT"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OperationStage(Base):
    __tablename__ = "operation_stages"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("operation_pipelines.project_id", ondelete="RESTRICT"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    section: Mapped[str] = mapped_column(String(24), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_operation_stage_project"),
        CheckConstraint("length(trim(label)) > 0", name="label_nonempty"),
        CheckConstraint("section IN ('property_purchase', 'golden_visa')", name="section_ok"),
        CheckConstraint("source IN ('manual', 'buyer_signed_spa')", name="source_ok"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
    )


class OperationBuyer(Base):
    __tablename__ = "operation_buyers"
    client_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(24))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (
        ForeignKeyConstraint(
            ["client_id", "project_id"],
            ["clients.id", "clients.project_id"],
            ondelete="RESTRICT",
            name="fk_operation_buyer_client",
        ),
        UniqueConstraint("client_id", "project_id", name="uq_operation_buyer_project"),
        CheckConstraint(
            "purpose IS NULL OR purpose IN ('investment_only', 'golden_visa')", name="purpose_ok"
        ),
    )


class OperationProgress(Base):
    __tablename__ = "operation_progress"
    client_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    stage_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    completed: Mapped[bool | None] = mapped_column(Boolean)
    completed_date: Mapped[date | None]
    __table_args__ = (
        ForeignKeyConstraint(
            ["client_id", "project_id"],
            ["operation_buyers.client_id", "operation_buyers.project_id"],
            ondelete="RESTRICT",
            name="fk_operation_progress_buyer",
        ),
        ForeignKeyConstraint(
            ["stage_id", "project_id"],
            ["operation_stages.id", "operation_stages.project_id"],
            ondelete="RESTRICT",
            name="fk_operation_progress_stage",
        ),
        CheckConstraint("completed IS TRUE OR completed_date IS NULL", name="date_requires_yes"),
    )
