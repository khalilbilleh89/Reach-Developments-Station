"""Optional company master details and bank-account instructions, owned by a project."""

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
    LargeBinary,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProjectCompany(Base):
    __tablename__ = "project_companies"
    __table_args__ = (
        CheckConstraint(
            "NOT no_related_company OR related_company_id IS NULL", name="related_company_choice"
        ),
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
    project_role: Mapped[str | None] = mapped_column(String(32))
    other_role: Mapped[str | None] = mapped_column(String(320))
    relationship: Mapped[str | None] = mapped_column(String(32))
    related_company_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("project_companies.id", ondelete="RESTRICT")
    )
    no_related_company: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    ownership_percentage: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    incorporation_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(String(2000))
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CompanyBankAccount(Base):
    __tablename__ = "company_bank_accounts"
    __table_args__ = (
        Index(
            "uq_company_bank_default",
            "company_id",
            unique=True,
            postgresql_where=text("NOT is_deleted AND default_for_payments"),
        ),
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
    beneficiary_name: Mapped[str | None] = mapped_column(String(320))
    beneficiary_bank: Mapped[str | None] = mapped_column(String(320))
    account_number: Mapped[str | None] = mapped_column(String(320))
    iban: Mapped[str | None] = mapped_column(String(320))
    swift_code: Mapped[str | None] = mapped_column(String(320))
    bank_address: Mapped[str | None] = mapped_column(String(2000))
    correspondent_bank: Mapped[str | None] = mapped_column(String(320))
    correspondent_swift_code: Mapped[str | None] = mapped_column(String(320))
    account_purpose: Mapped[str | None] = mapped_column(String(32))
    currency_code: Mapped[str | None] = mapped_column(String(3))
    default_for_payments: Mapped[bool | None] = mapped_column(Boolean)
    last_verified_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(32))
    bank_country: Mapped[str | None] = mapped_column(String(320))
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
        CheckConstraint(
            "(document IS NOT NULL AND filename IS NOT NULL AND sha256 IS NOT NULL "
            "AND source_url IS NULL) OR (document IS NULL AND filename IS NULL "
            "AND sha256 IS NULL AND source_url IS NOT NULL)",
            name="one_source",
        ),
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
    filename: Mapped[str | None] = mapped_column(String(255))
    document: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    sha256: Mapped[str | None] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(String(2000))
    category: Mapped[str | None] = mapped_column(String(320))
    other_category: Mapped[str | None] = mapped_column(String(320))
    linked_record: Mapped[str | None] = mapped_column(String(500))
    issue_date: Mapped[date | None] = mapped_column(Date)
    issue_date_not_stated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    expiry_note: Mapped[str | None] = mapped_column(String(32))
    reminder_date: Mapped[date | None] = mapped_column(Date)
    reminder_days: Mapped[int | None] = mapped_column(Integer)
    verification_status: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CompanyLogo(Base):
    __tablename__ = "company_logos"
    __table_args__ = (
        Index(
            "uq_company_logos_active",
            "company_id",
            unique=True,
            postgresql_where=text("NOT is_deleted"),
        ),
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
    image: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
