"""create commission tables

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-14

Creates the commission persistence layer:
  commission_plans
  commission_slabs
  commission_payouts
  commission_payout_lines

FK relationships
----------------
  commission_plans.project_id              → projects.id         (CASCADE)
  commission_slabs.commission_plan_id      → commission_plans.id (CASCADE)
  commission_payouts.project_id            → projects.id         (CASCADE)
  commission_payouts.sale_contract_id      → sales_contracts.id  (CASCADE)
  commission_payouts.commission_plan_id    → commission_plans.id (RESTRICT)
  commission_payout_lines.commission_payout_id → commission_payouts.id (CASCADE)
  commission_payout_lines.slab_id          → commission_slabs.id (SET NULL)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # commission_plans
    op.create_table(
        "commission_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("pool_percentage", sa.Numeric(8, 4), nullable=False),
        sa.Column(
            "calculation_mode",
            sa.String(50),
            nullable=False,
            server_default="marginal",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_commission_plans_project_id", "commission_plans", ["project_id"]
    )

    # commission_slabs
    op.create_table(
        "commission_slabs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "commission_plan_id",
            sa.String(36),
            sa.ForeignKey("commission_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("range_from", sa.Numeric(14, 2), nullable=False),
        sa.Column("range_to", sa.Numeric(14, 2), nullable=True),
        sa.Column("sales_rep_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("team_lead_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("manager_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("broker_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("platform_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "commission_plan_id",
            "sequence",
            name="uq_commission_slabs_plan_sequence",
        ),
    )
    op.create_index(
        "ix_commission_slabs_plan_id",
        "commission_slabs",
        ["commission_plan_id"],
    )

    # commission_payouts
    op.create_table(
        "commission_payouts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sale_contract_id",
            sa.String(36),
            sa.ForeignKey("sales_contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "commission_plan_id",
            sa.String(36),
            sa.ForeignKey("commission_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("gross_sale_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("commission_pool_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("calculation_mode", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_commission_payouts_project_id", "commission_payouts", ["project_id"]
    )
    op.create_index(
        "ix_commission_payouts_sale_contract_id",
        "commission_payouts",
        ["sale_contract_id"],
    )
    op.create_index(
        "ix_commission_payouts_plan_id",
        "commission_payouts",
        ["commission_plan_id"],
    )

    # commission_payout_lines
    op.create_table(
        "commission_payout_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "commission_payout_id",
            sa.String(36),
            sa.ForeignKey("commission_payouts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("party_type", sa.String(50), nullable=False),
        sa.Column("party_reference", sa.String(200), nullable=True),
        sa.Column(
            "slab_id",
            sa.String(36),
            sa.ForeignKey("commission_slabs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("percentage", sa.Numeric(8, 4), nullable=False),
        sa.Column("units_covered", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_commission_payout_lines_payout_id",
        "commission_payout_lines",
        ["commission_payout_id"],
    )
    op.create_index(
        "ix_commission_payout_lines_slab_id",
        "commission_payout_lines",
        ["slab_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_commission_payout_lines_slab_id",
        table_name="commission_payout_lines",
    )
    op.drop_index(
        "ix_commission_payout_lines_payout_id",
        table_name="commission_payout_lines",
    )
    op.drop_table("commission_payout_lines")

    op.drop_index(
        "ix_commission_payouts_plan_id", table_name="commission_payouts"
    )
    op.drop_index(
        "ix_commission_payouts_sale_contract_id", table_name="commission_payouts"
    )
    op.drop_index(
        "ix_commission_payouts_project_id", table_name="commission_payouts"
    )
    op.drop_table("commission_payouts")

    op.drop_index("ix_commission_slabs_plan_id", table_name="commission_slabs")
    op.drop_table("commission_slabs")

    op.drop_index(
        "ix_commission_plans_project_id", table_name="commission_plans"
    )
    op.drop_table("commission_plans")
