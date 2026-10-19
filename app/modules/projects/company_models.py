"""Optional company master details and bank-account instructions, owned by a project."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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


class ProjectCompany(Base):
    __tablename__ = "project_companies"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    legal_name: Mapped[str | None] = mapped_column(String(320))
    trading_name: Mapped[str | None] = mapped_column(String(320))
    registration_number: Mapped[str | None] = mapped_column(String(320))
    tax_number: Mapped[str | None] = mapped_column(String(320))
    legal_form: Mapped[str | None] = mapped_column(String(320))
    country: Mapped[str | None] = mapped_column(String(320))
    registered_address: Mapped[str | None] = mapped_column(String(2000))
    contact_name: Mapped[str | None] = mapped_column(String(320))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(320))
    website: Mapped[str | None] = mapped_column(String(320))
    authorized_signatory: Mapped[str | None] = mapped_column(String(320))
    notes: Mapped[str | None] = mapped_column(String(2000))
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CompanyBankAccount(Base):
    __tablename__ = "company_bank_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project_companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    beneficiary_name: Mapped[str | None] = mapped_column(String(320))
    beneficiary_bank: Mapped[str | None] = mapped_column(String(320))
    account_number: Mapped[str | None] = mapped_column(String(320))
    iban: Mapped[str | None] = mapped_column(String(320))
    swift_code: Mapped[str | None] = mapped_column(String(320))
    bank_address: Mapped[str | None] = mapped_column(String(2000))
    correspondent_bank: Mapped[str | None] = mapped_column(String(320))
    correspondent_swift_code: Mapped[str | None] = mapped_column(String(320))
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CompanyDocument(Base):
    __tablename__ = "company_documents"
    __table_args__ = (
        CheckConstraint("length(trim(label)) > 0", name="label_present"),
        CheckConstraint("octet_length(document) BETWEEN 1 AND 10485760", name="document_size"),
        CheckConstraint("version > 0", name="positive_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project_companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(320), nullable=False)
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
