"""Project training library and retained material evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0062_project_training"
down_revision = "0061_project_procedures"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_training",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("execution_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("description", sa.String(4000), nullable=False, server_default=""),
        sa.Column("external_url", sa.String(2000)),
        sa.Column("filename", sa.String(200)),
        sa.Column("media_type", sa.String(80)),
        sa.Column("byte_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(64)),
        sa.Column("data", sa.LargeBinary()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_training")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_training_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "kind IN ('video', 'document')", name=op.f("ck_project_training_asset_kind")
        ),
        sa.CheckConstraint(
            "(external_url IS NOT NULL AND data IS NULL AND filename IS NULL "
            "AND media_type IS NULL AND sha256 IS NULL AND byte_count = 0) OR "
            "(external_url IS NULL AND data IS NOT NULL AND filename IS NOT NULL "
            "AND media_type IS NOT NULL AND sha256 IS NOT NULL "
            "AND byte_count > 0 AND byte_count <= 52428800)",
            name=op.f("ck_project_training_asset_payload"),
        ),
    )
    op.create_index(op.f("ix_project_training_project_id"), "project_training", ["project_id"])


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM project_training")):
        raise RuntimeError("Training history must be retained; downgrade refused.")
    op.drop_table("project_training")
