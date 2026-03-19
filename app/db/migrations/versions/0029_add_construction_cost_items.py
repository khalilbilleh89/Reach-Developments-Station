"""add construction cost items table

Revision ID: 0029
Revises: 0028
Create Date: 2026-03-18

PR-C4 — Construction Cost Tracking

Adds the construction_cost_items table which records budget, committed,
and actual cost line items linked to a ConstructionScope.  Each row
captures the cost category, type, description, vendor, amounts, currency,
and an optional cost date.

Variance is derived at the service/response layer — it is NOT stored.

This migration is fully additive and non-breaking — it does not alter
any existing table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "construction_cost_items",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "scope_id",
            sa.String(36),
            sa.ForeignKey("construction_scopes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cost_category", sa.String(50), nullable=False),
        sa.Column("cost_type", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("vendor_name", sa.String(255), nullable=True),
        sa.Column(
            "budget_amount",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "committed_amount",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "actual_amount",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("currency", sa.String(10), nullable=False, server_default="AED"),
        sa.Column("cost_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_construction_cost_items_scope_id",
        "construction_cost_items",
        ["scope_id"],
    )
    op.create_index(
        "ix_construction_cost_items_cost_category",
        "construction_cost_items",
        ["cost_category"],
    )
    op.create_index(
        "ix_construction_cost_items_scope_cost_date",
        "construction_cost_items",
        ["scope_id", "cost_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_construction_cost_items_scope_cost_date",
        table_name="construction_cost_items",
    )
    op.drop_index(
        "ix_construction_cost_items_cost_category",
        table_name="construction_cost_items",
    )
    op.drop_index(
        "ix_construction_cost_items_scope_id",
        table_name="construction_cost_items",
    )
    op.drop_table("construction_cost_items")
