"""create cashflow forecasting tables

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-14

Creates the cashflow forecasting persistence layer:
  cashflow_forecasts
  cashflow_forecast_periods

FK relationships
----------------
  cashflow_forecasts.project_id           → projects.id          (CASCADE)
  cashflow_forecast_periods.cashflow_forecast_id → cashflow_forecasts.id (CASCADE)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # cashflow_forecasts
    op.create_table(
        "cashflow_forecasts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("forecast_name", sa.String(200), nullable=False),
        sa.Column(
            "forecast_basis",
            sa.String(50),
            nullable=False,
            server_default="actual_plus_scheduled",
        ),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column(
            "period_type",
            sa.String(20),
            nullable=False,
            server_default="monthly",
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "opening_balance",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("collection_factor", sa.Numeric(5, 4), nullable=True),
        sa.Column("assumptions_json", sa.Text, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_by", sa.String(200), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_cashflow_forecasts_project_id",
        "cashflow_forecasts",
        ["project_id"],
    )

    # cashflow_forecast_periods
    op.create_table(
        "cashflow_forecast_periods",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "cashflow_forecast_id",
            sa.String(36),
            sa.ForeignKey("cashflow_forecasts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column(
            "opening_balance",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "expected_inflows",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "actual_inflows",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "expected_outflows",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "net_cashflow",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "closing_balance",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "receivables_due",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "receivables_overdue",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_cashflow_forecast_periods_forecast_id",
        "cashflow_forecast_periods",
        ["cashflow_forecast_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cashflow_forecast_periods_forecast_id",
        table_name="cashflow_forecast_periods",
    )
    op.drop_table("cashflow_forecast_periods")

    op.drop_index(
        "ix_cashflow_forecasts_project_id",
        table_name="cashflow_forecasts",
    )
    op.drop_table("cashflow_forecasts")
