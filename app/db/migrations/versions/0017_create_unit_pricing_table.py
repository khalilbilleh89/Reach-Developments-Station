"""create unit pricing table

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-15

Adds the unit_pricing table — a formal per-unit pricing record:
  - base_price: the direct price input for the unit
  - manual_adjustment: upward or downward adjustment
  - final_price: computed as base_price + manual_adjustment (service layer)
  - currency: required, defaults to AED
  - pricing_status: draft | reviewed | approved
  - notes: optional free-text commentary

One record per unit enforced via unique constraint on unit_id.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unit_pricing",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "unit_id",
            sa.String(36),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("base_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("manual_adjustment", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("final_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default=sa.text("'AED'")),
        sa.Column("pricing_status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_unit_pricing_unit_id", "unit_pricing", ["unit_id"])
    op.create_check_constraint(
        "ck_unit_pricing_base_price_non_negative",
        "unit_pricing",
        "base_price >= 0",
    )
    op.create_check_constraint(
        "ck_unit_pricing_final_price_non_negative",
        "unit_pricing",
        "final_price >= 0",
    )
    op.create_check_constraint(
        "ck_unit_pricing_status",
        "unit_pricing",
        "pricing_status IN ('draft', 'reviewed', 'approved')",
    )


def downgrade() -> None:
    op.drop_index("ix_unit_pricing_unit_id", table_name="unit_pricing")
    op.drop_table("unit_pricing")
