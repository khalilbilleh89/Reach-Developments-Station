"""create feasibility tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-13

Adds the feasibility engine tables:
  feasibility_runs → feasibility_assumptions + feasibility_results
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feasibility_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scenario_name", sa.String(255), nullable=False),
        sa.Column("scenario_type", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feasibility_runs_project_id", "feasibility_runs", ["project_id"])

    op.create_table(
        "feasibility_assumptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("feasibility_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("sellable_area_sqm", sa.Numeric(14, 2), nullable=True),
        sa.Column("avg_sale_price_per_sqm", sa.Numeric(14, 2), nullable=True),
        sa.Column("construction_cost_per_sqm", sa.Numeric(14, 2), nullable=True),
        sa.Column("soft_cost_ratio", sa.Numeric(6, 4), nullable=True),
        sa.Column("finance_cost_ratio", sa.Numeric(6, 4), nullable=True),
        sa.Column("sales_cost_ratio", sa.Numeric(6, 4), nullable=True),
        sa.Column("development_period_months", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feasibility_assumptions_run_id", "feasibility_assumptions", ["run_id"])

    op.create_table(
        "feasibility_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("feasibility_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("gdv", sa.Numeric(20, 2), nullable=True),
        sa.Column("construction_cost", sa.Numeric(20, 2), nullable=True),
        sa.Column("soft_cost", sa.Numeric(20, 2), nullable=True),
        sa.Column("finance_cost", sa.Numeric(20, 2), nullable=True),
        sa.Column("sales_cost", sa.Numeric(20, 2), nullable=True),
        sa.Column("total_cost", sa.Numeric(20, 2), nullable=True),
        sa.Column("developer_profit", sa.Numeric(20, 2), nullable=True),
        sa.Column("profit_margin", sa.Numeric(10, 6), nullable=True),
        sa.Column("irr_estimate", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feasibility_results_run_id", "feasibility_results", ["run_id"])


def downgrade() -> None:
    op.drop_table("feasibility_results")
    op.drop_table("feasibility_assumptions")
    op.drop_table("feasibility_runs")
