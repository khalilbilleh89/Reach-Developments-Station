"""Project price escalation strategy; independent of approved unit prices."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import RATE, Base


class PriceEscalation(Base):
    __tablename__ = "project_price_escalations"
    __table_args__ = (
        CheckConstraint(
            "escalation_rate_fraction > 0 AND escalation_rate_fraction < 1000", name="rate"
        ),
        CheckConstraint("length(trim(project_status)) BETWEEN 1 AND 200", name="status"),
        CheckConstraint("version > 0", name="version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    escalation_rate_fraction: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    project_status: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
