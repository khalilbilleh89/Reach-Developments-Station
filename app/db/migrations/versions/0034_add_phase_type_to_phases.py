"""add phase_type to phases

Revision ID: 0034
Revises: 0033
Create Date: 2026-03-20

PR-9 — Project Lifecycle & Phase Management Engine

Extends the phases table with a phase_type column that captures the
lifecycle stage of each phase:

  concept       Initial concept and vision phase.
  design        Architectural and engineering design phase.
  approvals     Regulatory and permit approvals phase.
  construction  Active construction phase.
  sales         Sales and marketing launch phase.
  handover      Unit handover and completion phase.

The column is nullable to allow backward-compatible creation of phases
without a specific lifecycle type.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "phases",
        sa.Column("phase_type", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("phases", "phase_type")
