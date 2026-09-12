"""Project-local inventory choice lists; snapshot existing reference choices.

Revision ID: 0023_inventory_options
Revises: 0022_land_analytics
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_inventory_options"
down_revision: str | Sequence[str] | None = "0022_land_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = (
    "unit_type",
    "floor_band",
    "orientation",
    "view_class",
    "furnishing_specification",
    "accessibility",
    "garden_class",
    "sub_asset_subtype",
)


def upgrade() -> None:
    op.create_table(
        "inventory_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "category", "code"),
        sa.CheckConstraint(
            "category IN (" + ", ".join(repr(c) for c in CATEGORIES) + ")",
            name=op.f("ck_inventory_options_category_allowed"),
        ),
        sa.CheckConstraint(
            "length(trim(code)) > 0 AND length(trim(label)) > 0",
            name=op.f("ck_inventory_options_labels_not_blank"),
        ),
    )
    # A one-time snapshot, never a runtime fallback. A country's override wins
    # even if retired; units and pricing rules keep their existing stored codes.
    op.execute("""
        INSERT INTO inventory_options (id, project_id, category, code, label, sort_order, is_active)
        SELECT gen_random_uuid(), project_id, category, code, label, sort_order,
               is_active AND (valid_from IS NULL OR valid_from <= CURRENT_DATE)
                         AND (valid_to IS NULL OR valid_to >= CURRENT_DATE)
        FROM (
            SELECT DISTINCT ON (p.id, r.category, r.code)
                p.id AS project_id, r.category, r.code, r.label, r.sort_order,
                r.is_active, r.valid_from, r.valid_to
            FROM projects p JOIN reference_values r
              ON r.country_pack_id = p.country_pack_id OR r.country_pack_id IS NULL
            WHERE r.category IN ('unit_type','floor_band','orientation','view_class',
                'furnishing_specification','accessibility','garden_class','sub_asset_subtype')
            ORDER BY p.id, r.category, r.code, r.country_pack_id NULLS LAST
        ) effective
    """)


def downgrade() -> None:
    # Original reference values and unit facts are untouched. Project-local
    # configuration must be exported before a deliberate downgrade.
    op.drop_table("inventory_options")
