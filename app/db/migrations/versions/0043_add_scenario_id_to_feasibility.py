"""add scenario_id to feasibility and viability fields to feasibility_results

Revision ID: 0043
Revises: 0042
Create Date: 2026-03-22

PR-FEAS-001 — Feasibility Scenario Alignment

Changes
-------
feasibility_runs
  scenario_id   VARCHAR(36)   — optional FK → scenarios.id (SET NULL on delete)

feasibility_results
  viability_status  VARCHAR(50)  — VIABLE / MARGINAL / NOT_VIABLE
  risk_level        VARCHAR(50)  — LOW / MEDIUM / HIGH
  decision          VARCHAR(50)  — VIABLE / MARGINAL / NOT_VIABLE
  payback_period    NUMERIC(10,4) — payback period in years (nullable)

Indexes
-------
  feasibility_runs(scenario_id)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add scenario_id to feasibility_runs
    op.add_column(
        "feasibility_runs",
        sa.Column("scenario_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "ix_feasibility_runs_scenario_id",
        "feasibility_runs",
        ["scenario_id"],
    )
    op.create_foreign_key(
        "fk_feasibility_runs_scenario_id",
        "feasibility_runs",
        "scenarios",
        ["scenario_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add viability fields to feasibility_results
    op.add_column(
        "feasibility_results",
        sa.Column("viability_status", sa.String(50), nullable=True),
    )
    op.add_column(
        "feasibility_results",
        sa.Column("risk_level", sa.String(50), nullable=True),
    )
    op.add_column(
        "feasibility_results",
        sa.Column("decision", sa.String(50), nullable=True),
    )
    op.add_column(
        "feasibility_results",
        sa.Column("payback_period", sa.Numeric(10, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("feasibility_results", "payback_period")
    op.drop_column("feasibility_results", "decision")
    op.drop_column("feasibility_results", "risk_level")
    op.drop_column("feasibility_results", "viability_status")

    op.drop_constraint("fk_feasibility_runs_scenario_id", "feasibility_runs", type_="foreignkey")
    op.drop_index("ix_feasibility_runs_scenario_id", "feasibility_runs")
    op.drop_column("feasibility_runs", "scenario_id")
