"""Project branding logos and categorized marketing materials."""

import sqlalchemy as sa
from alembic import op

revision = "0059_marketing_assets"
down_revision = "0058_sales_import_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketing_assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("placement", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("notes", sa.String(500), nullable=False, server_default=""),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_marketing_assets")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_marketing_assets_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "placement IN ('logo', 'material')", name=op.f("ck_marketing_assets_asset_placement")
        ),
        sa.CheckConstraint(
            "kind IN ('image', 'video', 'document')", name=op.f("ck_marketing_assets_asset_kind")
        ),
        sa.CheckConstraint(
            "placement <> 'logo' OR (kind = 'image' AND external_url IS NULL)",
            name=op.f("ck_marketing_assets_asset_logo"),
        ),
        sa.CheckConstraint(
            "(external_url IS NOT NULL AND data IS NULL AND filename IS NULL "
            "AND media_type IS NULL AND sha256 IS NULL AND byte_count = 0) OR "
            "(external_url IS NULL AND data IS NOT NULL AND filename IS NOT NULL "
            "AND media_type IS NOT NULL AND sha256 IS NOT NULL "
            "AND byte_count > 0 AND byte_count <= 52428800)",
            name=op.f("ck_marketing_assets_asset_payload"),
        ),
    )
    op.create_index(op.f("ix_marketing_assets_project_id"), "marketing_assets", ["project_id"])


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM marketing_assets")):
        raise RuntimeError("Marketing attachment history must be retained; downgrade refused.")
    op.drop_table("marketing_assets")
