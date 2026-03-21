"""add analytics fact tables

Revision ID: 0040
Revises: 0039
Create Date: 2026-03-21

PR-23 — Analytics Fact Layer

Creates three analytics fact tables that store materialized financial
metrics derived from the operational financial engines.  These tables
allow dashboards to query analytics-ready data quickly without
recomputing heavy joins on operational tables.

Tables
------
fact_revenue
    Monthly recognized revenue per project / unit.
    Columns: id, project_id, unit_id, month, recognized_revenue,
             contract_value, created_at, updated_at.

fact_collections
    Payments received by project, month, and payment method.
    Columns: id, project_id, payment_date, month, amount,
             payment_method, created_at, updated_at.

fact_receivables_snapshot
    Point-in-time receivable aging snapshot per project.
    Columns: id, project_id, snapshot_date, total_receivables,
             bucket_0_30, bucket_31_60, bucket_61_90, bucket_90_plus,
             created_at, updated_at.

Indexes
-------
  fact_revenue(project_id), fact_revenue(month)
  fact_collections(project_id), fact_collections(month)
  fact_receivables_snapshot(project_id), fact_receivables_snapshot(snapshot_date)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # fact_revenue
    # ------------------------------------------------------------------
    op.create_table(
        "fact_revenue",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "unit_id",
            sa.String(36),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "month",
            sa.String(7),
            nullable=False,
            comment="Calendar month in YYYY-MM format.",
            index=True,
        ),
        sa.Column(
            "recognized_revenue",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "contract_value",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # fact_collections
    # ------------------------------------------------------------------
    op.create_table(
        "fact_collections",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("payment_date", sa.Date, nullable=False, index=True),
        sa.Column(
            "month",
            sa.String(7),
            nullable=False,
            comment="Calendar month in YYYY-MM format.",
            index=True,
        ),
        sa.Column(
            "amount",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "payment_method",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'bank_transfer'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # fact_receivables_snapshot
    # ------------------------------------------------------------------
    op.create_table(
        "fact_receivables_snapshot",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("snapshot_date", sa.Date, nullable=False, index=True),
        sa.Column(
            "total_receivables",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "bucket_0_30",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "bucket_31_60",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "bucket_61_90",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "bucket_90_plus",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("fact_receivables_snapshot")
    op.drop_table("fact_collections")
    op.drop_table("fact_revenue")
