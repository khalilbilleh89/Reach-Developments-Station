"""add feasibility result profit_per_sqm

Revision ID: 0057
Revises: 0056
Create Date: 2026-03-27

PR-V6-01 — Feasibility Run Detail Page Completion / Unit Economics

Changes
-------
feasibility_results
  profit_per_sqm  NUMERIC(20, 2) NULL — developer profit per sellable sqm,
                  computed as developer_profit / sellable_area_sqm by the
                  calculation engine and persisted for display in the Unit
                  Economics panel.

Existing rows default to NULL until recalculated.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0057"
down_revision: Union[str, None] = "0056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "feasibility_results",
        sa.Column("profit_per_sqm", sa.Numeric(20, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("feasibility_results", "profit_per_sqm")
