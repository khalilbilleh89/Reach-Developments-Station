"""harden land and feasibility project independence

Revision ID: 0025
Revises: 0024
Create Date: 2026-03-18

PR-B1 — Land Independence Verification

Makes project_id nullable in land_parcels and feasibility_runs so that
parcels and feasibility scenarios can exist before any project is created.

Land and feasibility are independent pre-project domains. Linking to a
project is now an optional step that happens at acquisition decision time.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # land_parcels.project_id — make nullable so parcels can exist pre-project
    with op.batch_alter_table("land_parcels") as batch_op:
        batch_op.alter_column(
            "project_id",
            existing_type=sa.String(36),
            nullable=True,
        )

    # feasibility_runs.project_id — make nullable so runs can exist pre-project
    with op.batch_alter_table("feasibility_runs") as batch_op:
        batch_op.alter_column(
            "project_id",
            existing_type=sa.String(36),
            nullable=True,
        )


def downgrade() -> None:
    # feasibility_runs.project_id — restore non-nullable (requires no NULL rows)
    with op.batch_alter_table("feasibility_runs") as batch_op:
        batch_op.alter_column(
            "project_id",
            existing_type=sa.String(36),
            nullable=False,
        )

    # land_parcels.project_id — restore non-nullable (requires no NULL rows)
    with op.batch_alter_table("land_parcels") as batch_op:
        batch_op.alter_column(
            "project_id",
            existing_type=sa.String(36),
            nullable=False,
        )
