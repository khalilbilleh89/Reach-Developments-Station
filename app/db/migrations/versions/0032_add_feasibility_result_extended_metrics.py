"""add feasibility result extended metrics

Revision ID: 0032
Revises: 0031
Create Date: 2026-03-20

PR-7 — Feasibility Financial Engine Hardening

Extends the feasibility_results table with new financial metrics produced
by the IRR, break-even, and scenario runner engines:

  irr              Annualized IRR (Newton-Raphson, monthly cashflows).
  equity_multiple  GDV / total cost ratio.
  break_even_price Minimum sale price per sqm to recover all costs.
  break_even_units Minimum sellable area (sqm) to recover all costs.
  scenario_outputs JSON blob — base / upside / downside / investor outputs.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "feasibility_results",
        sa.Column("irr", sa.Numeric(10, 6), nullable=True),
    )
    op.add_column(
        "feasibility_results",
        sa.Column("equity_multiple", sa.Numeric(10, 4), nullable=True),
    )
    op.add_column(
        "feasibility_results",
        sa.Column("break_even_price", sa.Numeric(20, 2), nullable=True),
    )
    op.add_column(
        "feasibility_results",
        sa.Column("break_even_units", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "feasibility_results",
        sa.Column("scenario_outputs", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("feasibility_results", "scenario_outputs")
    op.drop_column("feasibility_results", "break_even_units")
    op.drop_column("feasibility_results", "break_even_price")
    op.drop_column("feasibility_results", "equity_multiple")
    op.drop_column("feasibility_results", "irr")
