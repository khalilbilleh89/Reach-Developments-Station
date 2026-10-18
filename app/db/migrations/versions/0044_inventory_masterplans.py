"""Drawing sources and project-scoped unit footprints; existing inventory is unchanged."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0044_inventory_masterplans"
down_revision = "0043_commercial_faqs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_masterplans",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("width_m", sa.Numeric(18, 4), nullable=True),
        sa.Column("pixel_width", sa.Integer(), nullable=False),
        sa.Column("pixel_height", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_data", sa.LargeBinary(), nullable=False),
        sa.Column("preview_data", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("id", "project_id"),
        sa.CheckConstraint("kind IN ('plan', 'render', 'elevation')", name="kind_allowed"),
        sa.CheckConstraint("width_m IS NULL OR width_m > 0", name="width_positive"),
        sa.CheckConstraint(
            "version > 0 AND page_number >= 0 AND pixel_width > 0 AND pixel_height > 0",
            name="dimensions_valid",
        ),
    )
    op.create_index("ix_inventory_masterplans_project_id", "inventory_masterplans", ["project_id"])
    op.create_table(
        "inventory_masterplan_mappings",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("plan_id", postgresql.UUID(), nullable=False),
        sa.Column("unit_id", postgresql.UUID(), nullable=False),
        sa.Column("points", postgresql.JSONB(), nullable=False),
        sa.Column("base_m", sa.Numeric(18, 4), nullable=False),
        sa.Column("height_m", sa.Numeric(18, 4), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["plan_id", "project_id"],
            ["inventory_masterplans.id", "inventory_masterplans.project_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id", "project_id"], ["units.id", "units.project_id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("plan_id", "unit_id"),
        sa.CheckConstraint("height_m > 0 AND base_m >= 0 AND version > 0", name="height_valid"),
    )
    op.create_index(
        "ix_inventory_masterplan_mappings_project_id",
        "inventory_masterplan_mappings",
        ["project_id"],
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM inventory_masterplans)")):
        raise RuntimeError("Drawing sources prevent downgrade. Export and resolve them first.")
    op.drop_table("inventory_masterplan_mappings")
    op.drop_table("inventory_masterplans")
