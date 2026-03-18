"""add construction engineering items table

Revision ID: 0027
Revises: 0026
Create Date: 2026-03-18

PR-C2 — Construction Module Split: Engineering & Contractor

Adds the construction_engineering_items table which anchors the Engineering
workspace under each ConstructionScope. Engineering items represent technical
tasks, deliverables, and consultant cost entries for the pre-construction /
technical coordination phase.

This migration is fully additive and non-breaking — it does not alter any
existing table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "construction_engineering_items",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "scope_id",
            sa.String(36),
            sa.ForeignKey("construction_scopes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("item_type", sa.String(100), nullable=True),
        sa.Column("consultant_name", sa.String(255), nullable=True),
        sa.Column("consultant_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("target_date", sa.Date, nullable=True),
        sa.Column("completion_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_construction_engineering_items_scope_id",
        "construction_engineering_items",
        ["scope_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_construction_engineering_items_scope_id",
        table_name="construction_engineering_items",
    )
    op.drop_table("construction_engineering_items")
