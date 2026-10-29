"""Add project commercial email templates; no existing business records change."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0053_commercial_emails"
down_revision = "0052_design_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commercial_emails",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "category IN ('internal', 'clients', 'external')", name="category_valid"
        ),
        sa.CheckConstraint("length(trim(subject)) > 0", name="subject_nonempty"),
        sa.CheckConstraint("length(trim(title)) > 0", name="title_nonempty"),
        sa.CheckConstraint("length(trim(body)) BETWEEN 1 AND 20000", name="body_length"),
        sa.CheckConstraint("version > 0", name="version_positive"),
    )
    op.create_index("ix_commercial_emails_project_id", "commercial_emails", ["project_id"])


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM commercial_emails)")):
        raise RuntimeError(
            "Retained email templates prevent downgrade. Export and resolve records first."
        )
    op.drop_index("ix_commercial_emails_project_id", table_name="commercial_emails")
    op.drop_table("commercial_emails")
