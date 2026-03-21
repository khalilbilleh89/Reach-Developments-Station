"""add pricing override fields

Revision ID: 0036
Revises: 0035
Create Date: 2026-03-21

PR-14 — Pricing Override & Premium Rules Engine

Adds override governance metadata columns to the unit_pricing table:

  1. ``override_reason`` (TEXT, nullable) — mandatory justification note
     captured when a manual price override is applied.

  2. ``override_requested_by`` (VARCHAR 255, nullable) — identifier of the
     user who requested the override.

  3. ``override_approved_by`` (VARCHAR 255, nullable) — identifier of the
     user whose role authority approved the override.

These columns store the audit trail for governed pricing adjustments applied
via POST /pricing/{id}/override.  They are nullable so that pricing records
created before this migration (and records where no override has been applied)
are unaffected.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "unit_pricing",
        sa.Column("override_reason", sa.Text, nullable=True),
    )
    op.add_column(
        "unit_pricing",
        sa.Column("override_requested_by", sa.String(255), nullable=True),
    )
    op.add_column(
        "unit_pricing",
        sa.Column("override_approved_by", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("unit_pricing", "override_approved_by")
    op.drop_column("unit_pricing", "override_requested_by")
    op.drop_column("unit_pricing", "override_reason")
