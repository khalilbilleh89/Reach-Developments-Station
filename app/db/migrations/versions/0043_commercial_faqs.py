"""Add project commercial FAQs; no existing business records change."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0043_commercial_faqs"
down_revision = "0042_marketing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commercial_faqs",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("length(trim(question)) > 0", name="question_nonempty"),
        sa.CheckConstraint("length(trim(answer)) BETWEEN 1 AND 20000", name="answer_length"),
        sa.CheckConstraint("version > 0", name="version_positive"),
    )
    op.create_index("ix_commercial_faqs_project_id", "commercial_faqs", ["project_id"])


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM commercial_faqs)")):
        raise RuntimeError("Retained FAQs prevent downgrade. Export and resolve records first.")
    op.drop_index("ix_commercial_faqs_project_id", table_name="commercial_faqs")
    op.drop_table("commercial_faqs")
