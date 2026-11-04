"""Unposted, reviewable Sales workbook drafts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0058_sales_import_drafts"
down_revision = "0057_workspace_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_import_drafts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "project_id",
            sa.UUID(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "unit_id", sa.UUID(), sa.ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("source_key", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "reservation_id", sa.UUID(), sa.ForeignKey("reservations.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "created_by_user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("project_id", "source_key"),
        sa.CheckConstraint("status IN ('draft', 'added')", name="status"),
        sa.CheckConstraint("version > 0", name="version"),
        sa.CheckConstraint("(status = 'added') = (reservation_id IS NOT NULL)", name="added_link"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM sales_import_drafts)")):
        raise RuntimeError("Sales import drafts exist; retain their data and roll forward.")
    op.drop_table("sales_import_drafts")
