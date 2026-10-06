"""Optional retained job-description files for project team members."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0044_team_job_description"
down_revision = "0043_commercial_faqs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_job_descriptions",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("member_id", postgresql.UUID(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("document", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["member_id"], ["project_team_members.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "octet_length(document) BETWEEN 1 AND 10485760",
            name=op.f("ck_team_job_descriptions_size"),
        ),
    )
    op.create_index("ix_team_job_descriptions_member_id", "team_job_descriptions", ["member_id"])
    op.create_index(
        "uq_team_job_description_current",
        "team_job_descriptions",
        ["member_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM team_job_descriptions)")):
        raise RuntimeError(
            "Job description history prevents downgrade; retain the table and roll forward."
        )
    op.drop_table("team_job_descriptions")
