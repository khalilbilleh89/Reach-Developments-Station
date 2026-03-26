"""add feasibility run status

Revision ID: 0056
Revises: 0055
Create Date: 2026-03-26

PR-FEAS-03 — Feasibility Run Lifecycle State

Changes
-------
feasibility_runs
  status  VARCHAR(50) NOT NULL DEFAULT 'draft' — explicit lifecycle state for
          feasibility runs.

Allowed values: draft | assumptions_defined | calculated

Existing rows default to 'draft' (the initial lifecycle state).

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: Union[str, None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "feasibility_runs",
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="draft",
        ),
    )


def downgrade() -> None:
    op.drop_column("feasibility_runs", "status")
