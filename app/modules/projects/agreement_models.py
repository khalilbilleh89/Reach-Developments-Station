"""Project purchase-package drafts; never evidence of a client's signature."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProjectAgreement(Base):
    __tablename__ = "project_agreements"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_present"),
        CheckConstraint("length(trim(signing_company)) > 0", name="company_present"),
        CheckConstraint("octet_length(document) BETWEEN 1 AND 10485760", name="document_size"),
        CheckConstraint("version > 0", name="positive_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(320), nullable=False)
    signing_company: Mapped[str] = mapped_column(String(320), nullable=False)
    draft_created_on: Mapped[date] = mapped_column(Date, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    document: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
