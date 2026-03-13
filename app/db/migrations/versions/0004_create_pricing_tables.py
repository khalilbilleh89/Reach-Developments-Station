"""create pricing tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-13

Adds the unit pricing persistence layer:
  unit_pricing_attributes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unit_pricing_attributes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "unit_id",
            sa.String(36),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("base_price_per_sqm", sa.Numeric(14, 2), nullable=True),
        sa.Column("floor_premium", sa.Numeric(14, 2), nullable=True),
        sa.Column("view_premium", sa.Numeric(14, 2), nullable=True),
        sa.Column("corner_premium", sa.Numeric(14, 2), nullable=True),
        sa.Column("size_adjustment", sa.Numeric(14, 2), nullable=True),
        sa.Column("custom_adjustment", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_unit_pricing_attributes_unit_id", "unit_pricing_attributes", ["unit_id"])


def downgrade() -> None:
    op.drop_index("ix_unit_pricing_attributes_unit_id", table_name="unit_pricing_attributes")
    op.drop_table("unit_pricing_attributes")
