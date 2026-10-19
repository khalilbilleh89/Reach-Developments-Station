"""Project strategy matrices with retained history."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0050_project_matrices"
down_revision = "0049_price_escalation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_matrices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("version > 0", name=op.f("ck_project_matrices_version")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_matrices_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_matrices"),
    )
    op.create_index("ix_project_matrices_project_id", "project_matrices", ["project_id"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM project_matrices)")).scalar():
        raise RuntimeError("Matrix history exists; retain this migration and roll forward.")
    op.drop_table("project_matrices")
