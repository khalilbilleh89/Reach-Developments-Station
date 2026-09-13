"""Inventory common areas; no inferred measurements or backfill."""

import sqlalchemy as sa
from alembic import op

revision = "0026_common_areas"
down_revision = "0025_prelaunch_master"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_common_areas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("apartment_id", sa.Uuid(), nullable=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("area_sqm", sa.Numeric(18, 4), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "label"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["apartment_id", "project_id"],
            ["units.id", "units.project_id"],
            ondelete="RESTRICT",
            name="apartment",
        ),
        sa.CheckConstraint(
            "category IN ('common', 'garage', 'community', 'roads_pavements')",
            name="category_allowed",
        ),
        sa.CheckConstraint("apartment_id IS NULL OR category = 'common'", name="allocation_common"),
        sa.CheckConstraint("area_sqm >= 0", name="area_nonneg"),
        sa.CheckConstraint(
            "length(trim(label)) > 0 AND length(trim(source_reference)) > 0",
            name="labels_not_blank",
        ),
    )
    op.create_index(
        "ix_inventory_common_areas_project_id", "inventory_common_areas", ["project_id"]
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM inventory_common_areas)")):
        raise RuntimeError(
            "Common area measurements exist; export and remove through the "
            "audited workflow before downgrade."
        )
    op.drop_table("inventory_common_areas")
