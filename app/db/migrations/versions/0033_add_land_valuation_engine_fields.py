"""add land valuation engine fields

Revision ID: 0033
Revises: 0032
Create Date: 2026-03-20

PR-8 — Land Valuation & Underwriting Engine

Extends the land_valuations table with new fields produced by the residual
land valuation engine:

  max_land_bid      Maximum land bid (= residual land value).
  residual_margin   Land value as a fraction of GDV.
  valuation_date    Date the engine valuation was run.
  valuation_inputs  JSON snapshot of the engine inputs used.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "land_valuations",
        sa.Column("max_land_bid", sa.Numeric(20, 2), nullable=True),
    )
    op.add_column(
        "land_valuations",
        sa.Column("residual_margin", sa.Numeric(8, 6), nullable=True),
    )
    op.add_column(
        "land_valuations",
        sa.Column("valuation_date", sa.Date, nullable=True),
    )
    op.add_column(
        "land_valuations",
        sa.Column("valuation_inputs", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("land_valuations", "valuation_inputs")
    op.drop_column("land_valuations", "valuation_date")
    op.drop_column("land_valuations", "residual_margin")
    op.drop_column("land_valuations", "max_land_bid")
