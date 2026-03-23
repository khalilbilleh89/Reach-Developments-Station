"""add financial_scenario_runs table

Revision ID: 0044
Revises: 0043
Create Date: 2026-03-23

PR-FIN-034 — Financial Scenario Modeling

Changes
-------
financial_scenario_runs
  id                          VARCHAR(36)    PK (UUID)
  scenario_id                 VARCHAR(36)    FK → scenarios.id (CASCADE on delete)
  label                       VARCHAR(255)   human-readable run label
  notes                       TEXT           optional run notes
  is_baseline                 BOOLEAN        marks this run as the comparison baseline
  assumptions_json            JSON           merged assumptions actually used
  results_json                JSON           full engine result (returns + cashflows)
  irr                         FLOAT          denormalised for fast querying
  npv                         FLOAT          denormalised for fast querying
  roi                         FLOAT          denormalised for fast querying
  developer_margin            FLOAT          denormalised for fast querying
  gross_profit                FLOAT          denormalised for fast querying
  created_at                  TIMESTAMP
  updated_at                  TIMESTAMP

Indexes
-------
  financial_scenario_runs(scenario_id)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_scenario_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String(36),
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("label", sa.String(255), nullable=False, server_default="Base Case"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_baseline", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("assumptions_json", sa.JSON, nullable=True),
        sa.Column("results_json", sa.JSON, nullable=True),
        sa.Column("irr", sa.Float, nullable=True),
        sa.Column("npv", sa.Float, nullable=True),
        sa.Column("roi", sa.Float, nullable=True),
        sa.Column("developer_margin", sa.Float, nullable=True),
        sa.Column("gross_profit", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("financial_scenario_runs")
