"""Project-owned reusable commercial bodys."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CommercialEmail(Base):
    __tablename__ = "commercial_emails"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (
        CheckConstraint("category IN ('internal', 'clients', 'external')", name="category_valid"),
        CheckConstraint("length(trim(subject)) > 0", name="subject_nonempty"),
        CheckConstraint("length(trim(title)) > 0", name="title_nonempty"),
        CheckConstraint("length(trim(body)) BETWEEN 1 AND 20000", name="body_length"),
        CheckConstraint("version > 0", name="version_positive"),
    )
