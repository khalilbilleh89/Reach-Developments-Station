"""One retained instruction per letting cycle; source identities stay linked."""

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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MONEY, Base


class LeasingInstruction(Base):
    __tablename__ = "leasing_instructions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="leasing_unit",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["owner_client_id", "project_id"],
            ["clients.id", "clients.project_id"],
            name="leasing_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('draft','marketing','negotiating','leased','closed')", name="status"
        ),
        CheckConstraint("asking_rent_monthly IS NULL OR asking_rent_monthly >= 0", name="asking"),
        CheckConstraint("agreed_rent_monthly IS NULL OR agreed_rent_monthly >= 0", name="agreed"),
        CheckConstraint("security_deposit IS NULL OR security_deposit >= 0", name="deposit"),
        CheckConstraint(
            "lease_start IS NULL OR lease_end IS NULL OR lease_end > lease_start", name="dates"
        ),
        CheckConstraint(
            "status NOT IN ('marketing','negotiating','leased') OR (owner_client_id IS "
            "NOT NULL AND mandate_date IS NOT NULL AND length(trim(mandate_reference)) "
            "> 0 AND asking_rent_monthly IS NOT NULL AND asking_rent_monthly > 0)",
            name="mandate",
        ),
        CheckConstraint(
            "status != 'leased' OR (length(trim(tenant_name)) > 0 AND lease_start IS "
            "NOT NULL AND lease_end IS NOT NULL AND agreed_rent_monthly IS NOT NULL "
            "AND agreed_rent_monthly > 0 AND length(trim(agreement_reference)) > 0)",
            name="tenancy",
        ),
        Index(
            "uq_leasing_open_unit",
            "unit_id",
            unique=True,
            postgresql_where=text("NOT is_deleted AND status != 'closed'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID)
    owner_client_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    currency_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("currencies.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(20), default="draft")
    mandate_date: Mapped[date | None] = mapped_column(Date)
    mandate_reference: Mapped[str] = mapped_column(String(200), default="", server_default="")
    asking_rent_monthly: Mapped[Decimal | None] = mapped_column(MONEY)
    available_from: Mapped[date | None] = mapped_column(Date)
    tenant_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    agreed_rent_monthly: Mapped[Decimal | None] = mapped_column(MONEY)
    security_deposit: Mapped[Decimal | None] = mapped_column(MONEY)
    lease_start: Mapped[date | None] = mapped_column(Date)
    lease_end: Mapped[date | None] = mapped_column(Date)
    agreement_reference: Mapped[str] = mapped_column(String(200), default="", server_default="")
    next_action: Mapped[str] = mapped_column(String(300), default="", server_default="")
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(String(4000), default="", server_default="")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
